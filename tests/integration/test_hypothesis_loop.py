"""The hypothesis layer end-to-end — a claim in, a graded claim out. AC-HYP-201.

PRD 29 SC-hyp-5: an opted-in trial records the claim it pre-registered beside
the result it measured, and the report states how many claims were read and how
many signs held.

The contract under test is the one a wrapper script sees: the real
``python3 -m autoresearch`` CLI, a throwaway git repo, a scripted agent, no
model and no network. The agent writes its claim the way a harness emits one
— JSONL, the text escaped inside a part object — and prints a decoy claim
inside a tool result *after* the real one, so a reader that scans raw lines
records the decoy and this file says so.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))

import test_engine_support as support  # noqa: E402

sys.path.insert(0, str(support.ENGINE))

from autoresearch import ledger as ledger_mod  # noqa: E402

STATE = ".autoresearch"

CLAIM_TEXT = "one fewer step halves the cost"

#: A scripted seat. It shaves two from the value, prints its claim as an
#: opencode part event, then prints a decoy claim from a tool result. The
#: prediction is the one the *current* value makes sensible: +2 when the value
#: is still 10 (the shave helps), -2 once it is 8 (the shave should now cost).
AGENT = '''
import json, pathlib, sys

path = pathlib.Path(sys.argv[1]) / "src" / "value.txt"
value = int(path.read_text().strip())
path.write_text(str(value - 2))
predict = "+2" if value >= 10 else "\u22122"


def say(text):
    print(json.dumps({"type": "text", "part": {"text": text}}))


say(
    "CHANGE: shave the value by 2 | HYPOTHESIS: @@CLAIM@@ | "
    "PREDICT: " + predict + " | FALSIFIED IF: the value rises"
)
print(json.dumps({"type": "tool_result", "tool_result": {
    "text": "CHANGE: decoy | HYPOTHESIS: a tool echoed this | PREDICT: -99 | "
            "FALSIFIED IF: x"}}))
'''


def make_repo(tmp_path, value=10):
    """A throwaway git repo whose metric is the integer in ``src/value.txt``."""
    return support.make_target(tmp_path, value=value, name="repo")


def write_agent(tmp_path):
    """The scripted seat, outside the repo — what ``--agent command`` is for."""
    return support.write_agent(tmp_path, AGENT.replace("@@CLAIM@@", CLAIM_TEXT))


def trials(repo):
    return [event for event in support.read_events(repo) if event.get("type") == "trial"]


def run_one(tmp_path, repo, agent, *extra):
    """``init`` then one opted-in run; both must exit 0."""
    assert support.run_engine(*support.init_args(repo, repeats=1), cwd=tmp_path).returncode == 0
    argv = support.run_args(repo, agent, extra=["--hypotheses", *extra])
    proc = support.run_engine(*argv, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    return proc


def test_a_claim_is_read_graded_and_reported(tmp_path):
    """AC-HYP-201: the claim travels as JSONL, is read from assistant text
    only (the tool-result decoy after it does not displace it), and is recorded
    beside a keep with ``sign_match: true``. The report then states 1/1 claims
    read and 1 sign match — and the ledger still replays."""
    repo = make_repo(tmp_path)
    agent = write_agent(tmp_path)
    run_one(tmp_path, repo, agent, "--max-iterations", "1")

    trial = trials(repo)[0]
    assert trial["outcome"] == "keep"
    assert set(trial["hypothesis"]) == {
        "text", "predict", "falsified_if", "sign_match", "calibration"
    }
    assert trial["hypothesis"]["text"] == CLAIM_TEXT
    assert trial["hypothesis"]["predict"] == 2.0
    assert trial["hypothesis"]["falsified_if"] == "the value rises"
    assert trial["hypothesis"]["sign_match"] is True
    assert trial["hypothesis"]["calibration"] == "sign"
    assert ledger_mod.validate(support.read_events(repo)) == []

    proc = support.run_engine("report", "--repo", str(repo), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    text = (repo / STATE / "report.md").read_text(encoding="utf-8")
    assert "calibration: 1/1 claims read, 1 sign matches" in text

    proc = support.run_engine(
        "status", "--repo", str(repo), "--require-provenance", cwd=tmp_path
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ledger: valid" in proc.stdout


def test_a_refuted_claim_is_remembered_end_to_end(tmp_path):
    """AC-HYP-201: the second iteration predicts the opposite of what happens —
    its claim is recorded with ``sign_match: false`` and lands in the run's
    refutation memory with the reason that earned it, while the first,
    confirmed claim does not."""
    repo = make_repo(tmp_path)
    agent = write_agent(tmp_path)
    run_one(tmp_path, repo, agent, "--max-iterations", "2")

    records = [trial["hypothesis"] for trial in trials(repo)]
    assert [record["sign_match"] for record in records] == [True, False]
    assert records[1]["predict"] == -2.0

    memory = repo / STATE / "refuted.json"
    assert json.loads(memory.read_text(encoding="utf-8")) == [
        {"text": CLAIM_TEXT, "reason": "sign", "count": 1}
    ]
    assert not (repo / STATE / "refuted.json.tmp").exists()

    proc = support.run_engine("report", "--repo", str(repo), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    text = (repo / STATE / "report.md").read_text(encoding="utf-8")
    assert "calibration: 2/2 claims read, 1 sign matches" in text
