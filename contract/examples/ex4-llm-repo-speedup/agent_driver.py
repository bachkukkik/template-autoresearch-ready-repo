#!/usr/bin/env python3
"""agent_driver.py -- the LIVE LLM loop for ex4-llm-repo-speedup.

Unlike the other worked examples this driver is **not** a scripted candidate
list: each round it asks a live model for the complete new
``target/solution.py``, applies it, commits it, runs the FROZEN evaluator under
``prepare.TIME_BUDGET``, and keeps or resets -- the karpathy loop with a model in
the mutation slot. ``transcript.jsonl`` records every exchange, which is what
makes the run reproducible: ``--replay transcript.jsonl`` re-applies the
RECORDED responses in order with no network at all.

Harness-neutral: any OpenAI-compatible chat-completions endpoint works. Three
environment variables, NAMES only (never a value in a tracked file):

    OPENAI_BASE_URL   e.g. http://127.0.0.1:4000/v1   (default: api.openai.com)
    OPENAI_API_KEY    the bearer token
    OPENAI_MODEL      the model id, e.g. deepseek/deepseek-v4-pro

The evaluator owns the decision. This driver only (a) posts the prompt, (b)
writes the returned file, (c) calls ``prepare.run_evaluator`` and
``prepare.status_for`` -- the keep/discard/timeout vocabulary is computed by
frozen evaluator code from the run log, never self-awarded by the model.

Modes (all run in a scratch git repo -- the driver commits and hard-resets):

    python3 agent_driver.py --from-baseline --rounds 8            # LIVE
    python3 agent_driver.py --from-baseline --replay transcript.jsonl

Stdlib only. No third-party HTTP client, no ``shell=True``, every network call
carries an explicit ``timeout``.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ARTIFACT = os.path.join("target", "solution.py")
BASELINE = "solution_baseline.py"
LEDGER = "results.tsv"
TRANSCRIPT = "transcript.jsonl"
RUN_LOG = "run.log"
HEADER = "commit\tmedian_seconds\tgate\tstop_reason\tstatus\ttokens\tdescription"
BASELINE_DESC = "baseline (quadratic scan + per-value rescan; over budget by construction)"
AUTH_SCHEME = "Bearer"     # the Authorization scheme; the token comes from the env
HTTP_TIMEOUT = 300         # seconds per chat-completions call
MAX_TOKENS = 12000         # bound on one response: a reasoning model spends a
                           # large hidden chain of thought before the file, so a
                           # tight cap truncates to empty content.
LEDGER_TAIL_LINES = 12
LOG_TAIL_LINES = 14

sys.path.insert(0, HERE)
import prepare                                                    # noqa: E402

SYSTEM_PROMPT = (
    "You are an autonomous optimization agent working on a small Python "
    "repository. You may edit exactly one file: target/solution.py. Reply with "
    "the COMPLETE new content of that file inside a single fenced ```python "
    "block and nothing else. Standard library only. Your edit is scored by the "
    "repository's frozen test suite (a failure makes the run invalid) and by "
    "wall-clock median seconds on a fixed workload -- lower is better. One "
    "evaluated run has a hard wall-clock ceiling; an implementation that is "
    "correct but too slow is killed and scored 0. Begin your answer with a "
    "single line 'CHANGE: <one-line summary of your edit>', then the fenced "
    "code block -- no other prose."
)


# ------------------------------------------------------------------ shell ----
def sh(*args, check=False):
    """Run a command (no shell). Returns the CompletedProcess."""
    proc = subprocess.run(args, cwd=HERE, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise SystemExit("command failed: {}\n{}".format(" ".join(args), proc.stderr))
    return proc


def git(*args, check=False):
    return sh("git", *args, check=check)


def head_commit():
    return git("rev-parse", "--short", "HEAD").stdout.strip()


def read(path):
    with open(os.path.join(HERE, path), encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    with open(os.path.join(HERE, path), "w", encoding="utf-8") as fh:
        fh.write(text)


def tail(text, lines):
    return "\n".join(text.splitlines()[-lines:])


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- the model --
def call_model(messages, base_url, api_key, model, max_tokens=MAX_TOKENS,
               timeout=HTTP_TIMEOUT):
    """POST /chat/completions and return the decoded JSON body.

    ``max_tokens`` bounds ONE response so a rambling completion cannot outlive
    the round; a truncated response is handled like any other unusable one.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": model, "messages": messages,
                       "temperature": 0, "stream": False,
                       "max_tokens": max_tokens}).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": AUTH_SCHEME + " " + api_key})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def build_messages(artifact, ledger_tail, log_tail):
    """program.md + the artifact + the ledger tail + the last run log tail."""
    prompt = "\n".join([
        "## Human policy (program.md -- follow it exactly)",
        read("program.md"),
        "",
        "## The only file you may edit: target/solution.py (current content)",
        "```python",
        artifact,
        "```",
        "",
        "## Ledger so far (results.tsv)",
        "```",
        ledger_tail,
        "```",
        "",
        "## Last evaluator run log (tail)",
        "```",
        log_tail,
        "```",
        "",
        "Rewrite target/solution.py so it passes the frozen test suite AND the "
        "held-out exact-output gate, and completes the timed workload as fast "
        "as possible within the budget. Start your reply with one line "
        "'CHANGE: <one-line summary of this edit>', then return the COMPLETE "
        "file in ONE fenced ```python block and nothing else.",
    ])
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}]


def extract_code(text):
    """The new file from the response: the LONGEST fenced code block.

    A full-file rewrite is the biggest block; taking the longest is robust to a
    model that shows a small snippet before the answer. Returns None when the
    response carries no block at all (recorded as an unusable response).
    """
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text or "", re.S)
    if not blocks:
        return None
    code = max(blocks, key=len).strip("\n")
    return code + "\n" if code.strip() else None


def describe(response, round_no):
    """The round's one-line summary, from the response's own ``CHANGE:`` line.

    The prompt asks for ``CHANGE: <summary>`` before the code block. The line is
    sanitised (no tabs, no newlines, bounded) so the TSV stays readable, and a
    missing summary falls back to a deterministic placeholder -- the description
    is derived from the recorded response only, so a replay reproduces it.
    """
    for raw in (response or "").splitlines():
        line = raw.strip().lstrip("\"*#`- ").strip()
        if line.lower().startswith("change:"):
            summary = " ".join(line.split(":", 1)[1].split())
            if summary:
                return summary.replace("\t", " ")[:100]
    return "round {} (no summary)".format(round_no)


# ---------------------------------------------------------------- the loop ---
def ledger_append(row):
    with open(os.path.join(HERE, LEDGER), "a", encoding="utf-8") as fh:
        fh.write("\t".join(row) + "\n")


def ledger_tail_text():
    try:
        return tail(read(LEDGER), LEDGER_TAIL_LINES)
    except OSError:
        return "(no ledger yet)"


def log_tail_text():
    try:
        return tail(read(RUN_LOG), LOG_TAIL_LINES)
    except OSError:
        return "(no run yet)"


def evaluate_and_record(state, tokens, description):
    """Run the FROZEN evaluator on the committed artifact and record one row.

    ``state["incumbent"]`` is the best valid median so far (``inf`` until the
    first keep). The status comes from ``prepare.status_for`` -- evaluator-owned
    code -- and every non-keep is reset hard.
    """
    verdict, log = prepare.run_evaluator(ARTIFACT)
    verdict["median"] = verdict["median"]        # parsed by the evaluator
    status = prepare.status_for(verdict, state["incumbent"])
    write(RUN_LOG, log)
    row = [head_commit(), prepare.format_median(verdict["median"]),
           verdict["gate"], verdict["stop_reason"], status,
           str(tokens), description]
    ledger_append(row)
    if status == "keep":
        state["incumbent"] = verdict["median"]
    else:
        # discard, timeout and crash all restore the last kept state: a
        # candidate that is not a keep stays neither in the tree nor in history
        # (the row survives in the ledger).
        git("reset", "--hard", "-q", "HEAD~1")
    print("{:<9} {:>12}  gate={:<6} {:<11} {:>7} tok  {}".format(
        head_commit(), prepare.format_median(verdict["median"]),
        verdict["gate"], verdict["stop_reason"], status, description))
    return row


def commit_artifact(message):
    """Commit ONLY the artifact, then leave one commit per round.

    The index is scoped to ``target/solution.py`` on purpose: staging the
    runtime state (results.tsv, transcript.jsonl) and then hard-resetting a
    discarded round would delete those untracked records from the tree.
    ``--allow-empty`` keeps the invariant one round == one commit, so a
    ``git reset --hard HEAD~1`` is always safe.
    """
    git("add", "--", ARTIFACT, check=True)
    git("commit", "-q", "--allow-empty", "-m", message, check=True)
    return head_commit()


def baseline_row(state, description=BASELINE_DESC):
    """The first ledger row: the reconstructed baseline, evaluated as shipped."""
    return evaluate_and_record(state, tokens=0, description=description)


def start(state):
    """--from-baseline: restore the tracked baseline artifact and commit it."""
    text = read(BASELINE)
    write(ARTIFACT, text)
    commit = commit_artifact("contract: baseline target/solution.py (reconstructed)")
    print("--from-baseline: {} <- {} (HEAD {})".format(ARTIFACT, BASELINE, commit))
    write(LEDGER, HEADER + "\n")
    print(HEADER)


def round_from_record(state, record):
    """Apply one recorded/returned response: write -> commit -> evaluate."""
    code = extract_code(record["response"])
    tokens = int((record.get("usage") or {}).get("total_tokens") or 0)
    if record.get("artifact_sent") is not None:
        current = read(ARTIFACT)
        if record["artifact_sent"] != current:
            print("note: round {} artifact_sent != current artifact "
                  "(a keep/discard flip upstream -- the response is a full file, "
                  "so the replay continues)".format(record["round"]))
    if code is None:
        commit_artifact("candidate: unusable response (round {})".format(record["round"]))
        write(RUN_LOG, "# no artifact written: response carried no fenced code block\n")
        row = [head_commit(), prepare.format_median(float("inf")), "n/a", "error",
               "crash", str(tokens), "unusable response (no fenced code block)"]
        ledger_append(row)
        git("reset", "--hard", "-q", "HEAD~1")
        print("{} unusable response (round {})".format(head_commit(), record["round"]))
        return row, code
    write(ARTIFACT, code)
    commit_artifact("candidate: round {}".format(record["round"]))
    return None, code


def finish(state, record, code):
    tokens = int((record.get("usage") or {}).get("total_tokens") or 0)
    if code is None:                       # already recorded as a crash
        return tokens, None
    row = evaluate_and_record(state, tokens,
                              describe(record["response"], record["round"]))
    return tokens, row


# ------------------------------------------------------------------ modes ----
def live(args):
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = args.model or os.environ.get("OPENAI_MODEL", "")
    if not api_key or not model:
        raise SystemExit("live mode needs OPENAI_API_KEY and OPENAI_MODEL "
                         "(and usually OPENAI_BASE_URL) in the environment")
    print("live model: {}".format(model))
    state = {"incumbent": float("inf")}
    start(state)
    baseline_row(state)

    with open(os.path.join(HERE, TRANSCRIPT), "w", encoding="utf-8") as fh:
        for number in range(1, args.rounds + 1):
            artifact = read(ARTIFACT)
            messages = build_messages(artifact, ledger_tail_text(), log_tail_text())
            started = time.time()
            try:
                body = call_model(messages, base_url, api_key, model,
                                  args.max_tokens, args.http_timeout)
                response = body["choices"][0]["message"].get("content") or ""
                finish_reason = body["choices"][0].get("finish_reason")
                usage = body.get("usage") or {}
            except (OSError, KeyError, IndexError, ValueError) as exc:
                print("round {}: model call failed ({}: {}); grinding to a "
                      "halt".format(number, type(exc).__name__, exc))
                break
            wall = time.time() - started
            record = {"round": number, "date": args.date, "model": model,
                      "messages_sha256": sha256(json.dumps(messages)),
                      "artifact_sha256": sha256(artifact),
                      "artifact_sent": artifact, "response": response,
                      "finish_reason": finish_reason, "usage": usage,
                      "wall_seconds": round(wall, 3)}
            fh.write(json.dumps(record) + "\n")
            fh.flush()
            print("round {}: model replied in {:.1f}s ({} chars, {} tokens, "
                  "finish={})".format(number, wall, len(response),
                                      usage.get("total_tokens", "?"),
                                      finish_reason))
            _, code = round_from_record(state, record)
            finish(state, record, code)
    summary(state)


def replay(args):
    with open(args.replay, encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh if line.strip()]
    print("replay: {} recorded round(s) from {} (no network)".format(
        len(records), args.replay))
    state = {"incumbent": float("inf")}
    start(state)
    baseline_row(state)
    for record in records:
        _, code = round_from_record(state, record)
        finish(state, record, code)
    summary(state)
    return 0


def summary(state):
    rows = [line.split("\t") for line in read(LEDGER).splitlines()[1:] if line.strip()]
    keeps = [row for row in rows if row[4] == "keep"]
    print("\nrows: {}  keep={} discard={} timeout={} crash={}".format(
        len(rows), len(keeps),
        sum(1 for r in rows if r[4] == "discard"),
        sum(1 for r in rows if r[4] == "timeout"),
        sum(1 for r in rows if r[4] == "crash")))
    print("best median: {}s (budget {}s)".format(
        prepare.format_median(state["incumbent"]), prepare.TIME_BUDGET))
    print("HEAD: {} | {}".format(head_commit(),
                                git("log", "-1", "--format=%s").stdout.strip()))


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-baseline", action="store_true",
                        help="restore the tracked baseline artifact, then commit")
    parser.add_argument("--rounds", type=int, default=8,
                        help="live rounds to run (default 8)")
    parser.add_argument("--replay", metavar="TRANSCRIPT",
                        help="re-apply a recorded transcript with no network")
    parser.add_argument("--model", default=None, help="override OPENAI_MODEL")
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS,
                        help="bound on one model response (default {})".format(
                            MAX_TOKENS))
    parser.add_argument("--http-timeout", type=int, default=HTTP_TIMEOUT,
                        help="per-call socket timeout (default {})".format(
                            HTTP_TIMEOUT))
    parser.add_argument("--date", default=time.strftime("%Y-%m-%d"),
                        help="run date stamped into the transcript")
    args = parser.parse_args(argv)
    if not args.from_baseline:
        raise SystemExit("refusing to run without --from-baseline: the driver "
                         "commits and hard-resets, so start from the tracked "
                         "baseline in a scratch clone")
    if args.replay:
        return replay(args)
    live(args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
