"""PRD 11 worked examples -- ex4, the LIVE LLM repo-speedup run. IDs: AC-EXA-011..018.

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
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EX4 = ROOT / "contract" / "examples" / "ex4-llm-repo-speedup"
REQUIRED = ("README.md", "program.md", "prepare.py", "solution_baseline.py",
            "agent_driver.py", "results.tsv", "transcript.jsonl",
            "target/README.md", "target/solution.py", "target/tests.py")
REPLAY_TIMEOUT = 180
# No credential, no machine path, no shared host: a tracked example is
# portable and public. The literal header VALUE ``Bearer `` is banned too, so a
# pasted Authorization header can never land in a tracked file -- the driver
# names the scheme in a constant and reads the token from the environment.
SECRET_RE = re.compile(r"host\.docker\.internal|/workspace|/home/|sk-|Bearer ")


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _rows(path):
    lines = [ln for ln in _read(path).splitlines() if ln.strip()]
    return [ln.split("\t") for ln in lines[1:]]


def _transcript():
    return [json.loads(ln) for ln in
            _read(EX4 / "transcript.jsonl").splitlines() if ln.strip()]


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
    """AC-EXA-015: ex4's provenance is a LIVE LLM run -- a model id and a date
    are recorded, and no ex4 file claims the fixed-list provenance the other
    examples carry."""
    records = _transcript()
    models = {r["model"] for r in records}
    dates = {r["date"] for r in records}
    assert len(models) == 1 and all(models), models
    assert dates == {"2026-10-17"}, dates
    for path in sorted(EX4.rglob("*")):
        if path.is_file() and path.suffix in (".py", ".md"):
            text = _read(path)
            assert "scripted reference run" not in text, path
    driver = _read(EX4 / "agent_driver.py")
    assert "not** a scripted candidate list" in driver or "live" in driver.lower()
    index = _read(EX4 / "README.md").lower()
    assert "live" in index and "llm" in index
    assert models.pop() in _read(EX4 / "README.md")


def test_ex4_carries_no_secret_or_machine_path():
    """AC-EXA-016: no ex4 file names a shared host, a machine path, a key-like
    token or a literal Authorization header value -- the example is portable and
    the live run recorded nothing about where it ran."""
    for path in sorted(EX4.rglob("*")):
        if not path.is_file() or path.name.endswith((".pyc",)):
            continue
        text = _read(path)
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


def _scratch_copy(tmp_path):
    """Copy ex4 into tmp_path as a git repo (the driver commits and resets)."""
    dst = tmp_path / "ex4"
    shutil.copytree(EX4, dst)
    # transcript.jsonl is the replay's INPUT (the recorded exchanges), so it is
    # kept; only the runtime outputs a replay regenerates are removed.
    for name in ("results.tsv", "run.log"):
        (dst / name).unlink(missing_ok=True)

    def run(*args):
        return subprocess.run(args, cwd=dst, capture_output=True, text=True)

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
    """
    dst = _scratch_copy(tmp_path)
    proc = subprocess.run(
        [sys.executable, "agent_driver.py", "--from-baseline", "--replay",
         "transcript.jsonl"],
        cwd=dst, capture_output=True, text=True, timeout=REPLAY_TIMEOUT)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "--from-baseline: target/solution.py <- solution_baseline.py" in proc.stdout

    produced = _rows(dst / "results.tsv")
    vendored = _rows(EX4 / "results.tsv")
    assert len(produced) == len(vendored), (produced, vendored)
    for got, want in zip(produced, vendored):
        assert (got[2], got[3], got[5], got[6]) == (want[2], want[3], want[5], want[6])
    assert produced[0][4] == "timeout" and vendored[0][4] == "timeout"

    # the replay's own HEAD artifact is the kept candidate: it passes the frozen
    # gate and fits the budget.
    check = subprocess.run([sys.executable, "prepare.py", "--run",
                            "target/solution.py"],
                           cwd=dst, capture_output=True, text=True,
                           timeout=REPLAY_TIMEOUT)
    assert check.returncode == 0, check.stdout + check.stderr
    assert re.search(r"^gate: ok$", check.stdout, re.M), check.stdout
    assert re.search(r"^stop_reason: done$", check.stdout, re.M), check.stdout
