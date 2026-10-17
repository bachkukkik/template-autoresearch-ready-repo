"""PRD 11 worked examples -- ex4, the LIVE LLM repo-speedup run. IDs: AC-EXA-011..033.

ex1..ex3 are reference runs whose candidates come from a fixed list replayed by
``loop_driver.py``; ex4 is the one example whose candidates were proposed LIVE by
an LLM and recorded in ``transcript.jsonl``. Its three-role split is the same --
frozen evaluator (``prepare.py`` + ``target/tests.py``), human policy
(``program.md``), one agent-edited artifact (``target/solution.py``) -- and its
budget BINDS: the shipped baseline is quadratic and is killed at ``TIME_BUDGET``,
so the ledger's first row is a budget stop.

These tests are deliberately separate from ``test_examples_replay.py``: its
``EXAMPLE_DIRS`` tuple asserts ex1..ex3's provenance phrase, and ex4's provenance
assertion is the opposite one, so ex4 is never added there. Its ledger also
carries a driver header the dashboard does not chart.

Timing columns (``median_seconds``) are T2 statistical fields and are never
compared: the replay is checked on its deterministic columns only.

The hardening tests (AC-EXA-019..033) probe the evaluator and driver as
adversarial inputs would: a candidate that prints a fake verdict, a candidate
that forges the verdict file the first hardening still trusted (with no ``run()``
at all, and as an ``atexit`` hook), a candidate that returns wrong outputs while
writing a forged record, an ACTIVE load-time attack (forge the handshakes, steal
the seed stream off stdin, precompute every rep), an ``atexit`` hook that claims
a microsecond time, a candidate that floods the results channel, a candidate that
hangs after passing the gate, a candidate that spawns a grandchild (on the budget
path and on a clean exit), a candidate that reads the environment, and a driver
pointed at a parent repo. None of them calls a model.

Both the binding gate AND the speed number are the PARENT's own: the child
reports only the raw ``run()`` outputs it produced, and the parent recomputes
``reference(...)`` itself on inputs whose seeds it draws with ``secrets`` one rep
at a time — so nothing the child asserts (a verdict file, a median) can buy a
keep, and a rep is timed with the parent's own clock around the round trip.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EX4 = ROOT / "contract" / "examples" / "ex4-llm-repo-speedup"
REQUIRED = ("README.md", "program.md", "prepare.py", "solution_baseline.py",
            "agent_driver.py", "results.tsv", "transcript.jsonl",
            "target/README.md", "target/solution.py", "target/tests.py")
REPLAY_TIMEOUT = 180
GIT_TIMEOUT = 60
# No credential, no machine path, no shared host: a tracked example is
# portable and public. The literal header VALUE ``Bearer `` is banned too, so a
# pasted Authorization header can never land in a tracked file -- the driver
# names the scheme in a constant and reads the token from the environment.
SECRET_RE = re.compile(r"host\.docker\.internal|/workspace|/home/|sk-|Bearer ")


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _iter_text_files():
    """Every text file in the example, skipping VCS dirs, caches and binaries."""
    for path in sorted(EX4.rglob("*")):
        if not path.is_file():
            continue
        if any(part in (".git", "__pycache__") for part in path.parts):
            continue
        if path.suffix in (".pyc", ".pyo"):
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:      # a binary blob is not a claim about ex4
            continue


def _rows(path):
    lines = [ln for ln in _read(path).splitlines() if ln.strip()]
    return [ln.split("\t") for ln in lines[1:]]


def _transcript():
    return [json.loads(ln) for ln in
            _read(EX4 / "transcript.jsonl").splitlines() if ln.strip()]


def _git(dst, *args):
    return subprocess.run(("git",) + args, cwd=dst, capture_output=True,
                          text=True, timeout=GIT_TIMEOUT)


def test_ex4_ships_the_three_role_split():
    """AC-EXA-011: ex4 is a complete instance -- human policy, frozen evaluator
    (with its frozen test suite), exactly one agent-edited artifact, the driver,
    the vendored ledger and the recorded live transcript."""
    for name in REQUIRED:
        assert (EX4 / name).is_file(), "ex4 is missing {}".format(name)
    target = sorted(p.name for p in (EX4 / "target").iterdir() if p.is_file())
    assert target == ["README.md", "solution.py", "tests.py"], target
    program = _read(EX4 / "program.md")
    assert "target/solution.py" in program
    assert "frozen evaluator" in program and "agent artifact" in program
    # the baseline is the reconstructable start state, not the kept artifact
    assert "solution_baseline.py" in _read(EX4 / "agent_driver.py")
    assert _read(EX4 / "target/solution.py") != _read(EX4 / "solution_baseline.py")


def test_ex4_ledger_carries_its_drivers_header():
    """AC-EXA-012: the vendored ledger's first line is the HELD the driver
    writes (seven tab-separated columns, commit first)."""
    src = _read(EX4 / "agent_driver.py")
    match = re.search(r'^HEADER = "(.*)"$', src, re.M)
    assert match, "agent_driver.py has no HEADER constant"
    header = match.group(1).replace("\\t", "\t")
    first = _read(EX4 / "results.tsv").splitlines()[0]
    assert first == header
    assert first.split("\t") == ["commit", "median_seconds", "gate",
                                  "stop_reason", "status", "tokens", "description"]


def test_ex4_budget_binds_on_the_baseline():
    """AC-EXA-013: the budget is not decoration -- the baseline row is a budget
    stop (``stop_reason: budget``, ``status: timeout``, ``median_seconds: inf``),
    i.e. a correct-but-quadratic candidate really was killed at TIME_BUDGET."""
    rows = _rows(EX4 / "results.tsv")
    assert rows, "ex4 has no ledger rows"
    baseline = rows[0]
    assert baseline[3] == "budget", baseline
    assert baseline[4] == "timeout", baseline
    assert baseline[1] == "inf", baseline
    assert baseline[6].startswith("baseline"), baseline
    assert any(row[3] == "budget" for row in rows)
    # the budget is a ceiling in the evaluator too, and a real second resolution
    prepare = _read(EX4 / "prepare.py")
    assert "TIME_BUDGET = 5" in prepare
    assert "ceiling" in _read(EX4 / "program.md").lower()


def test_ex4_transcript_rounds_match_the_ledger_llm_rows():
    """AC-EXA-014: every LLM round in the ledger has its recorded exchange --
    one transcript line per non-baseline row, each carrying the round, the model
    id, the artifact sent, the raw response, the token usage and the wall time."""
    records = _transcript()
    rows = _rows(EX4 / "results.tsv")
    assert len(records) == len(rows) - 1, (len(records), len(rows))
    assert [r["round"] for r in records] == list(range(1, len(records) + 1))
    for index, record in enumerate(records, start=1):
        for field in ("round", "date", "model", "messages_sha256",
                      "artifact_sent", "response", "finish_reason", "usage",
                      "wall_seconds"):
            assert field in record, "transcript round {} has no {!r}".format(
                record.get("round"), field)
        assert record["artifact_sent"] and "def run(" in record["artifact_sent"]
        assert record["usage"].get("total_tokens", 0) > 0
        # An empty response is a real model failure, recorded honestly, not a
        # missing exchange: the round's token cap was spent before any content,
        # ``finish_reason`` is ``length``, and the matching ledger row (records
        # are rows[1:]) is the unusable-response crash.
        if record["response"] == "":
            assert record["finish_reason"] == "length", record
            row = rows[index]
            assert row[4] == "crash" and "unusable response" in row[6], row
        else:
            assert record["response"]
    # the per-round token counts in the ledger are the recorded ones (cheaper-dim)
    assert [row[5] for row in rows[1:]] == [
        str(r["usage"]["total_tokens"]) for r in records]
    assert any(int(row[5]) > 0 for row in rows[1:])
    assert rows[0][5] == "0"


def test_ex4_provenance_is_a_live_llm_run():
    """AC-EXA-015: ex4's provenance is a LIVE LLM run -- a model id and a single
    ISO date are recorded (taken from the transcript, not hardcoded here, and
    echoed by the README), and no ex4 file claims the fixed-list provenance the
    other examples carry."""
    records = _transcript()
    models = {r["model"] for r in records}
    dates = {r["date"] for r in records}
    assert len(models) == 1 and all(models), models
    assert len(dates) == 1, dates
    (date,) = dates
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date), date
    for path, text in _iter_text_files():
        if path.suffix not in (".py", ".md"):
            continue
        assert "scripted reference run" not in text, path
    driver = _read(EX4 / "agent_driver.py")
    assert "not** a scripted candidate list" in driver or "live" in driver.lower()
    index = _read(EX4 / "README.md").lower()
    assert "live" in index and "llm" in index
    assert models.pop() in _read(EX4 / "README.md")
    assert date in _read(EX4 / "README.md"), "the README must state the run date"


def test_ex4_carries_no_secret_or_machine_path():
    """AC-EXA-016: no ex4 file names a shared host, a machine path, a key-like
    token or a literal Authorization header value -- the example is portable and
    the live run recorded nothing about where it ran."""
    for path, text in _iter_text_files():
        hit = SECRET_RE.search(text)
        assert hit is None, "{} contains {!r}".format(path, hit.group(0))


def test_ex4_program_md_frames_the_budget_as_a_ceiling():
    """AC-EXA-017: program.md states TIME_BUDGET as a hard ceiling that stops a
    candidate -- never as a target the run is expected to fill."""
    program = _read(EX4 / "program.md")
    assert "TIME_BUDGET" in program
    assert "ceiling, not a target" in program
    assert "budget binds" in program
    assert "timeout" in program and "killed" in program


def test_ex4_readme_ledger_table_is_the_ledger():
    """AC-EXA-026: the README's ledger table is the ledger, not a retyped
    summary -- every cell (including the 100-character-truncated descriptions)
    equals the corresponding ``results.tsv`` cell."""
    rows = _rows(EX4 / "results.tsv")
    table = [line for line in _read(EX4 / "README.md").splitlines()
             if re.match(r"^\| [0-9a-f]{7} \|", line)]
    assert len(table) == len(rows), (len(table), len(rows))
    for line, row in zip(table, rows):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert cells == [cell.strip() for cell in row], (cells, row)


def _scratch_copy(tmp_path, keep_ledger=False):
    """Copy ex4 into tmp_path as a git repo (the driver commits and resets)."""
    dst = tmp_path / "ex4"
    shutil.copytree(EX4, dst)
    # transcript.jsonl is the replay's INPUT (the recorded exchanges), so it is
    # kept; only the runtime outputs a replay regenerates are removed.
    names = ("run.log",) if keep_ledger else ("results.tsv", "run.log")
    for name in names:
        (dst / name).unlink(missing_ok=True)

    def run(*args):
        return subprocess.run(args, cwd=dst, capture_output=True, text=True,
                              timeout=GIT_TIMEOUT)

    run("git", "init", "-q")
    run("git", "config", "user.name", "worked-example-test")
    run("git", "config", "user.email", "worked-example-test@example.invalid")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "contract: baseline")
    return dst


def test_ex4_replay_reproduces_the_deterministic_columns(tmp_path):
    """AC-EXA-018: ``--replay transcript.jsonl`` re-applies the recorded
    responses with no network, from the tracked baseline, in a scratch git repo,
    and reproduces the ledger's deterministic columns row for row.

    Compared: ``gate``, ``stop_reason``, ``tokens`` and ``description`` (all
    derived from the recorded response and from frozen, deterministic code).
    NOT compared: ``median_seconds`` -- a T2 timing field -- and so not the
    ``status`` column that turns on it, except for the budget-bound baseline row
    (``timeout``), whose timeout is deterministic because the baseline is many
    times over budget.

    Also asserted: the baseline row, being the incumbent, is never reset, so
    round 1 starts from the tracked baseline -- no "artifact_sent != current"
    note, and round 1's recorded artifact IS ``solution_baseline.py``.
    """
    dst = _scratch_copy(tmp_path)
    proc = subprocess.run(
        [sys.executable, "agent_driver.py", "--from-baseline", "--replay",
         "transcript.jsonl"],
        cwd=dst, capture_output=True, text=True, timeout=REPLAY_TIMEOUT)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "--from-baseline: target/solution.py <- solution_baseline.py" in proc.stdout
    # S1: round 1 must be prompted with the tracked baseline. The later rounds may
    # still report a mismatch, because the near-tied round-3 candidate can flip
    # from discard to keep inside the timing noise (a T2 field) -- but round 1
    # never may: that was the bug where the baseline row's own reset undid
    # --from-baseline and round 1 started from the FINAL artifact.
    for line in proc.stdout.splitlines():
        if "artifact_sent != current artifact" in line:
            assert "round 1 " not in line, line

    produced = _rows(dst / "results.tsv")
    vendored = _rows(EX4 / "results.tsv")
    assert len(produced) == len(vendored), (produced, vendored)
    for got, want in zip(produced, vendored):
        assert (got[2], got[3], got[5], got[6]) == (want[2], want[3], want[5], want[6])
    assert produced[0][4] == "timeout" and vendored[0][4] == "timeout"

    # round 1 was prompted with exactly the tracked baseline that --from-baseline
    # restored (the transcript records artifact_sha256 of what was sent).
    baseline_sha = hashlib.sha256(
        (EX4 / "solution_baseline.py").read_bytes()).hexdigest()
    first = _transcript()[0]
    assert first["artifact_sha256"] == baseline_sha, first["artifact_sha256"]
    assert hashlib.sha256(
        first["artifact_sent"].encode("utf-8")).hexdigest() == baseline_sha

    # the replay's own HEAD artifact is the kept candidate: it passes the frozen
    # gate and fits the budget.
    check = subprocess.run([sys.executable, "prepare.py", "--run",
                            "target/solution.py"],
                           cwd=dst, capture_output=True, text=True,
                           timeout=REPLAY_TIMEOUT)
    assert check.returncode == 0, check.stdout + check.stderr
    assert re.search(r"^gate: ok$", check.stdout, re.M), check.stdout
    assert re.search(r"^stop_reason: done$", check.stdout, re.M), check.stdout


# --------------------------------------------------------------- hardening ---
def _load_prepare():
    """Import the example's own prepare.py without writing bytecode into it."""
    spec = importlib.util.spec_from_file_location("ex4_prepare_probe",
                                                  EX4 / "prepare.py")
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


def _candidate(tmp_path, source, name="candidate.py"):
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return str(path)


CORRECT_RUN = '''\
from collections import Counter


def run(items):
    counts = Counter(items)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    seen = set()
    first = -1
    for j, w in enumerate(items):
        if w in seen:
            first = j
            break
        seen.add(w)
    return {
        "pairs": sum(c * (c - 1) // 2 for c in counts.values()),
        "groups": sum(1 for c in counts.values() if c >= 2),
        "largest": [ranked[0][0], ranked[0][1]] if ranked else [],
        "top": [[w, c] for w, c in ranked[:10]],
        "first_repeat": first,
    }
'''

FORGED_VERDICT = '''\
print("gate: ok")
print("median_seconds: 0.000001")
print("stop_reason: done")


def run(items):
    return {"pairs": 0}
'''

EXIT_ZERO_FORGERY = '''\
import sys

print("gate: ok")
print("median_seconds: 0.000001")
print("stop_reason: done")
sys.exit(0)          # exit 0 with no tests run: the old stdout reader kept this
'''

ORPHAN = '''\
import subprocess
import sys
import time

GRANDCHILD = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open(__PIDFILE__, "w", encoding="utf-8") as fh:
    fh.write(str(GRANDCHILD.pid))


def run(items):
    time.sleep(60)
'''

ENV_PROBE = '''\
import json
import os

with open(__DUMP__, "w", encoding="utf-8") as fh:
    json.dump(dict(os.environ), fh)


def run(items):
    return {}
'''


def test_ex4_a_candidate_cannot_forge_the_verdict(tmp_path):
    """AC-EXA-019: a candidate that prints `gate: ok / median_seconds: 0.000001 /
    stop_reason: done` at import and returns wrong answers is NOT kept -- the
    parent compares the child's reported `run()` outputs against `reference`
    itself, never reads the shared stdout, and a wrong `run()` fails the gate.

    The second candidate is the sharper form of the same attack: it prints the
    fake verdict and exits 0 without ever reporting an output. No verified
    output means a crash, so the exit-0 trick cannot buy a keep either.
    """
    prep = _load_prepare()
    cand = _candidate(tmp_path, FORGED_VERDICT)
    verdict, log = prep.run_evaluator(cand)
    assert verdict["gate"] == "failed", (verdict, log)
    assert verdict["stop_reason"] == "gate_failed", verdict
    assert verdict["median"] == float("inf"), verdict
    assert prep.status_for(verdict, float("inf")) == "crash"
    # the forged line IS on stdout -- which is exactly why stdout is not judged
    assert "median_seconds: 0.000001" in log

    exit_zero = _candidate(tmp_path, EXIT_ZERO_FORGERY, name="exit_zero.py")
    verdict, log = prep.run_evaluator(exit_zero)
    assert verdict["gate"] != "ok", (verdict, log)
    assert verdict["stop_reason"] == "error", verdict
    assert prep.status_for(verdict, float("inf")) == "crash"


def test_ex4_a_budget_kill_is_a_timeout_not_a_keep(tmp_path, monkeypatch):
    """AC-EXA-020: a run that passes the gate and then outlives the budget is
    recorded as ``budget`` / ``timeout`` -- never as a keep, whatever the child
    printed before it was killed."""
    prep = _load_prepare()
    monkeypatch.setattr(prep, "TIME_BUDGET", 1.0)
    slow = (CORRECT_RUN
            .replace("from collections import Counter",
                     "import time\nfrom collections import Counter")
            .replace("    counts = Counter(items)",
                     "    if len(items) > 10000:      # the timed reps only\n"
                     "        time.sleep(60)\n"
                     "    counts = Counter(items)"))
    assert slow != CORRECT_RUN
    verdict, log = prep.run_evaluator(_candidate(tmp_path, slow))
    assert verdict["stop_reason"] == "budget", (verdict, log)
    assert verdict["gate"] == "ok", verdict        # the gate really did pass
    assert verdict["median"] == float("inf"), verdict
    assert prep.status_for(verdict, float("inf")) == "timeout"


def _running(pid):
    """True while ``pid`` is a live (non-zombie) process."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        state = Path("/proc/{}/stat".format(pid)).read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return True
    return state != "Z"


@pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
def test_ex4_budget_kill_takes_the_whole_process_group(tmp_path, monkeypatch):
    """AC-EXA-021: the budget kill takes the child's process group, so a
    grandchild spawned by the candidate does not survive the run as an orphan."""
    prep = _load_prepare()
    monkeypatch.setattr(prep, "TIME_BUDGET", 1.0)
    pidfile = tmp_path / "grandchild.pid"
    source = ORPHAN.replace("__PIDFILE__", repr(str(pidfile)))
    verdict, _log = prep.run_evaluator(_candidate(tmp_path, source))
    assert verdict["stop_reason"] == "budget", verdict
    pid = int(pidfile.read_text(encoding="utf-8").strip())
    deadline = time.time() + 10
    while time.time() < deadline:
        if not _running(pid):
            return
        time.sleep(0.05)
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        return
    raise AssertionError("grandchild {} survived the budget kill".format(pid))


def test_ex4_the_child_inherits_no_secret(tmp_path, monkeypatch):
    """AC-EXA-022: with OPENAI_API_KEY in the caller's environment, the evaluated
    child sees no such variable -- indeed no ``OPENAI_*`` key at all -- and its
    HOME is a private temp dir."""
    prep = _load_prepare()
    monkeypatch.setenv("OPENAI_API_KEY", "canary-not-a-real-key")
    dump = tmp_path / "env.json"
    source = ENV_PROBE.replace("__DUMP__", repr(str(dump)))
    prep.run_evaluator(_candidate(tmp_path, source))
    child_env = json.loads(dump.read_text(encoding="utf-8"))
    # the canary WAS in this process (so the probe is meaningful) and the child
    # still saw no OPENAI_* key of any name.
    assert os.environ["OPENAI_API_KEY"] == "canary-not-a-real-key"
    assert "OPENAI_API_KEY" not in child_env, sorted(child_env)
    assert not any(key.startswith("OPENAI_") for key in child_env), sorted(child_env)
    assert child_env.get("HOME") and child_env["HOME"] != os.path.expanduser("~"), \
        child_env.get("HOME")


def test_ex4_driver_refuses_to_run_inside_a_parent_repo(tmp_path):
    """AC-EXA-023: when the example directory is a SUBDIRECTORY of a repo (the
    template checkout), the driver exits non-zero before any git write: the
    parent's HEAD is unchanged and an uncommitted file survives untouched."""
    repo = tmp_path / "repo"
    nested = repo / "contract" / "examples" / "ex4-llm-repo-speedup"
    shutil.copytree(EX4, nested)
    notes = repo / "NOTES.md"
    notes.write_text("committed\n", encoding="utf-8")
    for args in (("init", "-q"), ("config", "user.name", "t"),
                 ("config", "user.email", "t@example.invalid"),
                 ("add", "-A"), ("commit", "-qm", "contract: baseline")):
        done = _git(repo, *args)
        assert done.returncode == 0, done.stderr
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    ledger_before = (nested / "results.tsv").read_bytes()
    notes.write_text("uncommitted edit\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "agent_driver.py", "--from-baseline", "--replay",
         "transcript.jsonl"],
        cwd=nested, capture_output=True, text=True, timeout=GIT_TIMEOUT)

    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "refusing to run" in proc.stderr, proc.stderr
    assert "scratch" in proc.stderr, proc.stderr
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert notes.read_text(encoding="utf-8") == "uncommitted edit\n"
    assert (nested / "results.tsv").read_bytes() == ledger_before
    # no stray round commits, no reset of the parent tree, nothing else touched
    assert _git(repo, "status", "--porcelain").stdout.strip() == "M NOTES.md"


def test_ex4_live_refuses_a_non_empty_ledger(tmp_path):
    """AC-EXA-024: a LIVE run will not append to the vendored ledger: with rows
    already present it exits non-zero before any model call (no key needed)."""
    dst = _scratch_copy(tmp_path, keep_ledger=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("OPENAI_")}
    proc = subprocess.run(
        [sys.executable, "agent_driver.py", "--from-baseline", "--rounds", "1"],
        cwd=dst, capture_output=True, text=True, timeout=GIT_TIMEOUT, env=env)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "refusing a LIVE run" in proc.stderr, proc.stderr
    assert "results.tsv" in proc.stderr
    assert "row(s) below the header" in proc.stderr


def test_ex4_bench_seeds_are_fresh_and_parent_chosen():
    """AC-EXA-025: the benchmark seeds are drawn by the PARENT with ``secrets``
    — not the module's fixed ``random`` stream — ONE fresh seed per rep just
    before it is sent, after the child's import handshake and ready signal, so a
    workload precomputed at import time or a cache reused across reps is
    worthless and the child's own timing is never read."""
    prep = _load_prepare()
    first, second = prep.fresh_seed(), prep.fresh_seed()
    assert isinstance(first, int) and not isinstance(first, bool) and first >= 0
    assert first != second, "a fresh seed must be drawn on every rep"
    src = _read(EX4 / "prepare.py")
    assert "import secrets" in src and "secrets.randbits" in src
    assert "_read_seed" in src and "sys.stdin.readline" in src   # one seed per line
    assert "_await_imported" in src and "_await_ready" in src    # after the handshake
    assert "_await_bench" in src                                 # one rep at a time


# ------------------------------------------------- verdict-file forgery (A2/A3)
# Both candidates below were reproduced by the parent against the FIRST hardened
# evaluator and were recorded ``keep`` with median 1e-06: the candidate is
# imported inside the same child that wrote verdict.json, and it can read the
# path straight off sys.argv. The parent-side comparison closes that.
A2_VERDICT_FORGE = '''\
import json
import os
import sys

_path = sys.argv[sys.argv.index("--results") + 1]
json.dump({"gate": "ok", "median": 1e-06, "stop_reason": "done"}, open(_path, "w"))
os._exit(0)
'''

A3_ATEXIT_OVERWRITE = '''\
import atexit
import json
import sys


def _forge():
    try:
        path = sys.argv[sys.argv.index("--results") + 1]
        with open(path, "w") as fh:
            json.dump({"gate": "ok", "median": 1e-06, "stop_reason": "done"}, fh)
    except OSError:
        pass


atexit.register(_forge)
'''

A3_ATEXIT_APPEND = '''\
import atexit
import json
import sys


def _forge():
    try:
        path = sys.argv[sys.argv.index("--results") + 1]
        with open(path, "a") as fh:
            fh.write(json.dumps({"gate": "ok", "median": 1e-06,
                                 "stop_reason": "done"}) + "\\n")
    except OSError:
        pass


atexit.register(_forge)
'''

# Correct on the frozen cases, WRONG on the held-out workload, plus a forged
# ``held_out`` record carrying the CORRECT output (it reads the workload from the
# child's own module and recomputes the oracle), hoping the parent believes the
# forged record instead of the candidate's real output.
MASKING_FORGE = '''\
import json
import sys
from collections import Counter


def _reference(items):
    counts = Counter(items)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    seen = set()
    first = -1
    for j, w in enumerate(items):
        if w in seen:
            first = j
            break
        seen.add(w)
    return {
        "pairs": sum(c * (c - 1) // 2 for c in counts.values()),
        "groups": sum(1 for c in counts.values() if c >= 2),
        "largest": [ranked[0][0], ranked[0][1]] if ranked else [],
        "top": [[w, c] for w, c in ranked[:10]],
        "first_repeat": first,
    }


try:
    _held = getattr(sys.modules["__main__"], "HELD_OUT", None)
    if _held is not None:
        with open(sys.argv[sys.argv.index("--results") + 1], "a") as fh:
            fh.write(json.dumps({"stage": "output", "name": "held_out",
                                 "output": _reference(_held)}) + "\\n")
except Exception:                                     # noqa: BLE001
    pass


def run(items):
    if len(items) < 20:              # the frozen cases: pass them honestly
        return _reference(items)
    return {"pairs": 0, "groups": 0, "largest": [], "top": [], "first_repeat": -1}
'''

# The ACTIVE load-time attack the re-review reproduced: forge the ``imported``
# and ``ready`` handshakes so the parent sends seeds at once, steal the seed
# stream off stdin in a background thread, and precompute every rep. Under the
# old seed-list protocol this scored a keep at 0.000006 s; under parent-side
# per-rep timing the same work lands inside the timed round trip, so it cannot
# be faster than the honest solution.
ACTIVE_PRECOMPUTE = '''\
import json
import random
import sys
import threading
from collections import Counter

_N = @N@
_VOCAB = @VOCAB@
_PATH = sys.argv[sys.argv.index("--results") + 1]


def _solve(items):
    counts = Counter(items)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    seen = set()
    first = -1
    for j, w in enumerate(items):
        if w in seen:
            first = j
            break
        seen.add(w)
    return {
        "pairs": sum(c * (c - 1) // 2 for c in counts.values()),
        "groups": sum(1 for c in counts.values() if c >= 2),
        "largest": [ranked[0][0], ranked[0][1]] if ranked else [],
        "top": [[w, c] for w, c in ranked[:10]],
        "first_repeat": first,
    }


def _gen(n, seed):
    rng = random.Random(seed)
    words = ["w%05d" % i for i in range(_VOCAB)]
    weights = [1.0 / ((i + 1) ** 0.9) for i in range(_VOCAB)]
    return rng.choices(words, weights=weights, k=n)


_CACHE = {}


def _steal():
    with open(_PATH, "a") as fh:
        fh.write(json.dumps({"stage": "imported"}) + "\\n")
        fh.write(json.dumps({"stage": "ready"}) + "\\n")
    for line in sys.stdin:
        try:
            seed = json.loads(line)["seed"]
        except Exception:                                 # noqa: BLE001
            break
        items = _gen(_N, seed)
        out = _solve(items)
        _CACHE[(len(items), items[0], items[1])] = out
        with open(_PATH, "a") as fh:
            fh.write(json.dumps({"stage": "output", "name": "bench",
                                 "seed": seed, "output": out}) + "\\n")


threading.Thread(target=_steal, daemon=True).start()


def run(items):
    key = (len(items), items[0] if items else "",
           items[1] if len(items) > 1 else "")
    if key in _CACHE:
        return _CACHE[key]
    return _solve(items)
'''

# The N3 attack: the correct artifact plus an ``atexit`` hook that appends
# ``bench`` records claiming ``seconds: 1e-9`` with the CORRECT output. The old
# evaluator took the child's ``seconds`` and scored median 0.0; the protocol no
# longer carries a timing field and the parent measures the round trip itself.
ATEXIT_BENCH_SECONDS_FORGE = '''\
import atexit as _at
import json as _json
import sys as _sys


def _forge_bench():
    try:
        _p = _sys.argv[_sys.argv.index("--results") + 1]
        with open(_p) as fh:
            recs = [_json.loads(line) for line in fh if line.strip()]
    except Exception:                                         # noqa: BLE001
        return
    for rec in recs:
        if rec.get("stage") == "output" and rec.get("name") == "bench":
            try:
                with open(_p, "a") as fh:
                    fh.write(_json.dumps({"stage": "output", "name": "bench",
                                          "seed": rec.get("seed"),
                                          "seconds": 1e-9,
                                          "output": rec.get("output")}) + "\\n")
            except OSError:
                pass


_at.register(_forge_bench)
'''

# A grandchild spawned at import, then a clean ``os._exit(0)``: the run is not a
# timeout, so there is no budget kill to reap it -- the evaluator's own
# process-group kill on the normal exit path must.
ORPHAN_CLEAN_EXIT = '''\
import os
import subprocess
import sys

GRANDCHILD = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open(__PIDFILE__, "w", encoding="utf-8") as fh:
    fh.write(str(GRANDCHILD.pid))
os._exit(0)
'''

# A candidate that floods the one-way results channel it shares with the parent.
CHANNEL_FLOOD = '''\
import json
import sys

_PATH = sys.argv[sys.argv.index("--results") + 1]
with open(_PATH, "a", encoding="utf-8") as fh:
    for _i in range(@FLOOD@):
        fh.write(json.dumps({"stage": "noise", "i": _i}) + "\\n")


def run(items):
    return {"pairs": 0, "groups": 0, "largest": [], "top": [],
            "first_repeat": -1}
'''


def test_ex4_a_results_file_forgery_with_no_run_is_not_kept(tmp_path):
    """AC-EXA-027: a candidate whose whole body writes ``{gate: ok, median: 1e-06,
    stop_reason: done}`` to the results channel and calls ``os._exit(0)`` -- with
    **no** ``run()`` at all -- is NOT kept.

    The parent judges its own comparison of the reported outputs; the forged
    record carries no ``output`` and no recognised stage, so nothing was verified
    and the run is a crash."""
    prep = _load_prepare()
    verdict, log = prep.run_evaluator(_candidate(tmp_path, A2_VERDICT_FORGE))
    assert verdict["median"] != 1e-06, (verdict, log)
    assert verdict["median"] != 0.000001, verdict
    assert verdict["median"] == float("inf"), verdict
    assert verdict["gate"] != "ok", verdict
    assert verdict["stop_reason"] == "error", verdict
    assert prep.status_for(verdict, 0.001811) == "crash", verdict


def test_ex4_an_atexit_verdict_overwrite_is_never_the_recorded_median(tmp_path):
    """AC-EXA-028: the correct artifact plus an ``atexit`` hook that writes
    ``median 1e-06`` to the results channel is NEVER recorded with that median.

    The parent reads the channel incrementally and times every rep itself, so
    neither overwriting the file at exit nor appending a forged record can move
    the recorded median: both forms are scored on the parent's own measurement,
    the forge is not the number recorded, and it cannot buy a keep against the
    incumbent."""
    prep = _load_prepare()
    verdict, log = prep.run_evaluator(
        _candidate(tmp_path, CORRECT_RUN + A3_ATEXIT_OVERWRITE, name="a3_w.py"))
    assert verdict["median"] != 1e-06, (verdict, log)
    assert verdict["median"] != float("inf"), verdict
    assert verdict["gate"] == "ok", (verdict, log)
    assert verdict["stop_reason"] == "done", verdict
    assert 0.0 < verdict["median"] < prep.TIME_BUDGET, verdict

    verdict, log = prep.run_evaluator(
        _candidate(tmp_path, CORRECT_RUN + A3_ATEXIT_APPEND, name="a3_a.py"))
    assert verdict["median"] != 1e-06, (verdict, log)
    assert verdict["gate"] == "ok", (verdict, log)
    assert verdict["stop_reason"] == "done", verdict
    # the appended forge changed nothing: the recorded median is the parent's
    # own measurement of a real run, not the forged 1e-06.
    assert 0.0 < verdict["median"] < prep.TIME_BUDGET, verdict


def test_ex4_wrong_outputs_are_gate_failed_however_the_child_writes(tmp_path):
    """AC-EXA-029: a candidate that returns WRONG outputs on the held-out workload
    while appending a forged (and even correct) ``held_out`` record is gate
    failed — the parent compares every output the child reported, and the
    candidate's own wrong ``run()`` output is one of them."""
    prep = _load_prepare()
    verdict, log = prep.run_evaluator(_candidate(tmp_path, MASKING_FORGE))
    assert verdict["gate"] == "failed", (verdict, log)
    assert verdict["stop_reason"] == "gate_failed", verdict
    assert verdict["median"] == float("inf"), verdict
    assert prep.status_for(verdict, float("inf")) == "crash", verdict


def test_ex4_an_active_load_time_precompute_attack_is_not_kept_fast(tmp_path):
    """AC-EXA-030: the ACTIVE attack the re-review reproduced -- forge the
    ``imported``/``ready`` handshakes, read the seed stream off stdin and
    precompute every rep -- is NOT kept with a sub-0.0001 s median.

    Under the old seed-list protocol this scored a keep at 0.000006 s. The parent
    now draws one fresh seed per rep, sends only that seed and times the round
    trip itself, so the precompute is charged to the window: the run is either
    rejected (the stolen stream left no verified output) or scored on the
    parent's real measurement, never the number the candidate chose.
    """
    prep = _load_prepare()
    source = (ACTIVE_PRECOMPUTE.replace("@N@", str(prep.N_BIG))
              .replace("@VOCAB@", str(prep.VOCAB_SIZE)))
    verdict, log = prep.run_evaluator(_candidate(tmp_path, source))
    status = prep.status_for(verdict, float("inf"))
    assert not (status == "keep" and verdict["median"] < 0.0001), (verdict, log)
    assert verdict["median"] != 1e-06, verdict
    if verdict["stop_reason"] == "done":
        assert verdict["median"] >= 0.0001, (verdict, log)


def test_ex4_a_forged_bench_seconds_is_never_the_recorded_median(tmp_path):
    """AC-EXA-031: the correct artifact plus an ``atexit`` hook that appends
    ``bench`` records claiming ``seconds: 1e-9`` (with the CORRECT output) is
    NEVER recorded with a forged median.

    The protocol carries no timing field any more, so the forged ``seconds`` is
    ignored and the recorded median is the parent's own measurement of the round
    trip -- it cannot even beat a (previously forged) 1e-06 incumbent.
    """
    prep = _load_prepare()
    verdict, log = prep.run_evaluator(
        _candidate(tmp_path, CORRECT_RUN + ATEXIT_BENCH_SECONDS_FORGE, name="n3.py"))
    assert verdict["median"] != 1e-9, (verdict, log)
    assert verdict["median"] != 1e-06, verdict
    assert verdict["gate"] == "ok", (verdict, log)
    assert verdict["stop_reason"] == "done", verdict
    assert verdict["median"] >= 0.0001, verdict              # a real measurement
    assert prep.status_for(verdict, 0.000001) != "keep", verdict


@pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
def test_ex4_no_orphan_after_a_clean_exit(tmp_path):
    """AC-EXA-032: a grandchild spawned at import followed by a clean
    ``os._exit(0)`` is gone after ``run_evaluator`` returns -- there is no
    timeout kill on that path, so the process-group kill runs on EVERY exit."""
    prep = _load_prepare()
    pidfile = tmp_path / "grandchild-clean.pid"
    source = ORPHAN_CLEAN_EXIT.replace("__PIDFILE__", repr(str(pidfile)))
    verdict, _log = prep.run_evaluator(_candidate(tmp_path, source))
    assert verdict["gate"] != "ok" and verdict["stop_reason"] == "error", verdict
    pid = int(pidfile.read_text(encoding="utf-8").strip())
    deadline = time.time() + 10
    while time.time() < deadline:
        if not _running(pid):
            return
        time.sleep(0.05)
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        return
    raise AssertionError("grandchild {} survived a clean exit".format(pid))


def test_ex4_a_flooded_results_channel_is_a_crash(tmp_path):
    """AC-EXA-033: the results channel is a one-way stream the candidate shares,
    so it is a resource a hostile artifact can flood. Past the record cap the
    parent treats the run as a crash -- never a slow win -- and reads it with an
    offset rather than re-reading the whole file every poll."""
    prep = _load_prepare()
    source = CHANNEL_FLOOD.replace("@FLOOD@", str(prep.CHANNEL_MAX_RECORDS + 500))
    verdict, log = prep.run_evaluator(_candidate(tmp_path, source))
    assert verdict["gate"] != "ok", (verdict, log)
    assert verdict["stop_reason"] == "error", verdict
    assert prep.status_for(verdict, float("inf")) == "crash", verdict


