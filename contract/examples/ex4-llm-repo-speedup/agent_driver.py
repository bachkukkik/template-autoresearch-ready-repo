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

    OPENAI_BASE_URL   e.g. http://127.0.0.1:4000/v1  # your OpenAI-compatible endpoint
    OPENAI_API_KEY    the bearer token
    OPENAI_MODEL      the model id, e.g. deepseek/deepseek-v4-pro

The evaluator owns the decision. This driver only (a) posts the prompt, (b)
writes the returned file, (c) calls ``prepare.run_evaluator`` and
``prepare.status_for`` -- the keep/discard/timeout vocabulary is computed by
frozen evaluator code from its OWN comparison of the child's reported ``run()``
outputs, never self-awarded by the model, never read from the candidate's stdout
and never taken from a verdict the candidate could write.

Modes (all run in a scratch git repo -- the driver commits and hard-resets, so
it REFUSES to run unless the git ROOT is this directory):

    python3 agent_driver.py --from-baseline --rounds 8            # LIVE
    python3 agent_driver.py --from-baseline --replay transcript.jsonl

Live mode executes **model-written Python unsandboxed, with your privileges**:
run it in a disposable container/VM with no credentials beyond the endpoint key
(which the evaluated child does not inherit -- ``prepare.child_env`` scrubs it)
and no host mounts. See README.md § Live mode.

Stdlib only. No third-party HTTP client, no ``shell=True``, every network and
subprocess call carries an explicit ``timeout``.
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
GIT_TIMEOUT = 120          # seconds per git/subprocess call: never wedge

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
def sh(*args, check=False, timeout=GIT_TIMEOUT):
    """Run a command (no shell). Returns the CompletedProcess.

    Every call carries an explicit ``timeout``: a hung git command must fail the
    run with a message, never wedge the driver.
    """
    try:
        proc = subprocess.run(args, cwd=HERE, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SystemExit("command timed out after {}s: {}".format(
            timeout, " ".join(args)))
    if check and proc.returncode != 0:
        raise SystemExit("command failed: {}\n{}".format(" ".join(args), proc.stderr))
    return proc


def git(*args, check=False, timeout=GIT_TIMEOUT):
    return sh("git", *args, check=check, timeout=timeout)


def head_commit():
    return git("rev-parse", "--short", "HEAD").stdout.strip()


def git_prefix():
    """``git rev-parse --show-prefix`` from HERE: '' at a repo root, None if no repo."""
    proc = git("rev-parse", "--show-prefix")
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def require_scratch_repo():
    """Refuse to run unless HERE is the ROOT of its own git repository.

    The driver commits and ``git reset --hard``s. Inside the template checkout
    HERE is a subdirectory, so ``git rev-parse --show-toplevel`` resolves to the
    template root: a reset there would revert the user's tracked (and
    uncommitted) work and litter their clone with ``candidate: round N``
    commits. The check runs before the first git write.
    """
    prefix = git_prefix()
    if prefix == "":
        return
    where = ("not inside a git repository" if prefix is None
             else "a subdirectory of one (prefix {!r})".format(prefix))
    raise SystemExit(
        "refusing to run: {} is {} -- this driver commits and hard-resets, so "
        "the example directory must be the git ROOT.\n"
        "Use a disposable scratch copy:\n"
        "  mkdir -p \"${{TMPDIR:-/tmp}}/ex4\"\n"
        "  git archive HEAD contract/examples/ex4-llm-repo-speedup | "
        "tar -x -C \"${{TMPDIR:-/tmp}}/ex4\" --strip-components=3\n"
        "  cd \"${{TMPDIR:-/tmp}}/ex4\" && git init -q && git add -A && "
        "git commit -qm 'contract: baseline'\n"
        "  rm -f results.tsv          # a LIVE run starts from an empty ledger\n"
        "  python3 agent_driver.py --from-baseline --rounds 8".format(HERE, where))


def require_empty_ledger():
    """A LIVE run starts from an empty ledger: the vendored one is the record."""
    try:
        text = read(LEDGER)
    except OSError:
        return
    rows = [line for line in text.splitlines()[1:] if line.strip()]
    if rows:
        raise SystemExit(
            "refusing a LIVE run: {} already has {} row(s) below the header. "
            "The vendored ledger is the worked run's record, not a starting "
            "point -- delete it in the scratch copy (`rm -f {}`) before a live "
            "run; `--replay` regenerates its own.".format(
                LEDGER, len(rows), LEDGER))


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


def evaluate_and_record(state, tokens, description, reset=True):
    """Run the FROZEN evaluator on the committed artifact and record one row.

    ``state["incumbent"]`` is the best valid median so far (``inf`` until the
    first keep). The verdict comes from ``prepare.run_evaluator`` -- frozen
    evaluator code comparing the child's reported ``run()`` outputs itself -- and
    the status from ``prepare.status_for``; neither is ever self-awarded by the
    model.

    A non-keep is reset hard, unless ``reset`` is False: the baseline row is the
    incumbent by definition, so a reset there would undo ``--from-baseline`` and
    make round 1 start from the FINAL kept artifact instead of the baseline the
    run actually began with.
    """
    verdict, log = prepare.run_evaluator(ARTIFACT)
    status = prepare.status_for(verdict, state["incumbent"])
    write(RUN_LOG, log)
    # The commit column is the commit this row evaluates: for a non-keep that is
    # the candidate commit discarded by the reset below (it is in no branch's
    # history afterwards, only in this row).
    row = [head_commit(), prepare.format_median(verdict["median"]),
           verdict["gate"], verdict["stop_reason"], status,
           str(tokens), description]
    ledger_append(row)
    if status == "keep":
        state["incumbent"] = verdict["median"]
    elif reset:
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

    The commit is path-limited (``-- target/solution.py``) on purpose: a bare
    ``git commit`` commits the whole index, i.e. anything else the caller had
    staged. Runtime state is not committed at all -- ``.gitignore`` keeps
    ``results.tsv`` / ``transcript.jsonl`` / ``run.log`` untracked, so a
    ``git reset --hard`` in the driver's own scratch repo leaves those records
    alone (it would only touch them if they were staged, which is exactly what
    the path limit prevents). ``--allow-empty`` keeps the invariant one round ==
    one commit, so ``git reset --hard HEAD~1`` is always safe.
    """
    git("add", "--", ARTIFACT, check=True)
    git("commit", "--no-verify", "-q", "--allow-empty", "-m", message,
        "--", ARTIFACT, check=True)
    return head_commit()


def baseline_row(state, description=BASELINE_DESC):
    """The first ledger row: the reconstructed baseline, evaluated as shipped.

    Never reset -- the baseline IS the incumbent the run started from, even when
    it is a budget stop.
    """
    return evaluate_and_record(state, tokens=0, description=description,
                               reset=False)


def start():
    """--from-baseline: restore the tracked baseline artifact and commit it."""
    text = read(BASELINE)
    write(ARTIFACT, text)
    commit = commit_artifact("contract: baseline target/solution.py (reconstructed)")
    print("--from-baseline: {} <- {} (HEAD {})".format(ARTIFACT, BASELINE, commit))
    write(LEDGER, HEADER + "\n")
    print(HEADER)


def round_from_record(record):
    """Apply one recorded/returned response: write -> commit -> evaluate.

    Returns the new artifact text, or None when the response carried no fenced
    block (already recorded as an unusable-response crash). The prompt a round
    was built from is not rebuilt here: ``--replay`` warns separately when the
    recorded ``messages_sha256`` differs, then re-applies the response verbatim.
    """
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
        # The commit column is the discarded candidate commit (reset below).
        row = [head_commit(), prepare.format_median(float("inf")), "n/a", "error",
               "crash", str(tokens), "unusable response (no fenced code block)"]
        ledger_append(row)
        git("reset", "--hard", "-q", "HEAD~1")
        print("{} unusable response (round {})".format(head_commit(), record["round"]))
        return None
    write(ARTIFACT, code)
    commit_artifact("candidate: round {}".format(record["round"]))
    return code


def finish(state, record, code):
    """Evaluate a round whose artifact was written (a crash row is already done)."""
    if code is None:
        return
    tokens = int((record.get("usage") or {}).get("total_tokens") or 0)
    evaluate_and_record(state, tokens,
                        describe(record["response"], record["round"]))


# ------------------------------------------------------------------ modes ----
def live(args):
    require_empty_ledger()
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = args.model or os.environ.get("OPENAI_MODEL", "")
    if not api_key or not model:
        raise SystemExit("live mode needs OPENAI_API_KEY and OPENAI_MODEL "
                         "(and usually OPENAI_BASE_URL) in the environment")
    print("live model: {}".format(model))
    state = {"incumbent": float("inf")}
    start()
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
            code = round_from_record(record)
            finish(state, record, code)
    summary(state)


def prompt_sha256():
    """sha256 of the prompt this replay would send now (soft comparison only)."""
    messages = build_messages(read(ARTIFACT), ledger_tail_text(), log_tail_text())
    return sha256(json.dumps(messages))


def replay(args):
    with open(args.replay, encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh if line.strip()]
    print("replay: {} recorded round(s) from {} (no network)".format(
        len(records), args.replay))
    state = {"incumbent": float("inf")}
    start()
    baseline_row(state)
    for record in records:
        expected = record.get("messages_sha256")
        current = prompt_sha256()
        if expected and current != expected:
            # Soft, never fatal: a prompt embeds the ledger tail and the run-log
            # tail, and the log carries timing, so the sha cannot be stable
            # across runs. The response is re-applied verbatim regardless.
            print("WARNING: round {} prompt sha256 differs from the recorded "
                  "one ({} != {}); prompts embed timing -- the recorded "
                  "response is re-applied verbatim".format(
                      record.get("round"), current[:12], expected[:12]))
        code = round_from_record(record)
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
    require_scratch_repo()
    if args.replay:
        return replay(args)
    live(args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
