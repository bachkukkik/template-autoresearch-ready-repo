"""The loop end-to-end emits scientific records. ID: AC-EVL-202.

PRD 20 SC-evl-6: an engine keep with ``repeats >= 3`` writes dispersion
(``repeats``/``spread``/``honest``/``se``/``margin``), provenance, and cost
fields (``agent_tokens`` / ``agent_api_calls`` — an explicit ``null`` where the
harness exposes none, which must stay distinguishable from zero) into the ledger
event; and a delta the margin cannot separate is recorded ``inconclusive`` and
reverted instead of being kept on a coin flip (SC-evl-2).

The contract under test is the one a wrapper script sees: the real
``python3 -m autoresearch`` CLI, a throwaway git repo, a scripted agent, no
model and no network. The score deliberately *jitters between repeats* — a
counter file at the repo root (outside the scoped files) is bumped by each run
and adds a multiple of 0.2 — because a deterministic verify would report a
spread of 0.0 and the margin would collapse to the configured floor, which is
the case the unit tier already covers. The counter is an untracked artifact, so
the loop's own artifact sweep removes it after each measurement.
"""
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import pytest

# tests/unit owns the engine harness (repo builder, argv builders, subprocess
# runner); the integration tier imports it rather than re-cloning it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))

import test_engine_support as support  # noqa: E402

sys.path.insert(0, str(support.ENGINE))

from autoresearch import ledger as ledger_mod  # noqa: E402  the vocabulary the block must match

STATE = ".autoresearch"

#: ``measure.MEDIAN_CONSISTENCY`` restated here so the arithmetic in these
#: assertions does not depend on the implementation under test.
MEDIAN_CONSISTENCY = 1.2533

ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

SCORE_PY = '''"""The measurement: the file's value plus a per-run jitter."""
import pathlib

value = float(pathlib.Path("src/value.txt").read_text().strip())
counter = pathlib.Path("jitter.count")
count = int(counter.read_text().strip()) if counter.exists() else 0
counter.write_text(str(count + 1))
print(f"METRIC value={value + 0.2 * (count % 3)}")
'''

GUARD_PY = '''"""The guard: a candidate that breaks behaviour has no business scoring."""
import pathlib
import sys

raw = float(pathlib.Path("src/value.txt").read_text().strip())
sys.exit(0 if raw >= 0 else 1)
'''

FLOAT_DECREMENT = '''
import pathlib, sys

path = pathlib.Path(sys.argv[1]) / "src" / "value.txt"
value = float(path.read_text().strip()) - STEP
path.write_text(str(round(value, 6)))
print("CHANGE: shave the value by STEP")
'''


# ─── fixtures ────────────────────────────────────────────────────────────────


def make_repo(path, value=10.0):
    """A git repo on ``main`` whose metric is the number in ``src/value.txt``."""
    return support.make_target(
        path.parent, value=value, name=path.name, score_body=SCORE_PY, guard_body=GUARD_PY
    )


def write_agent(tmp_path, *, step):
    """The ``--agent-cmd`` template of a float-shrinking script outside the repo."""
    script = support.write_agent(tmp_path, FLOAT_DECREMENT.replace("STEP", str(step)))
    return script


def trials(events):
    return [event for event in events if event.get("type") == "trial"]


def expected_se(spread, repeats):
    """The independent two-sample SE of a difference of medians, both sides equal."""
    return MEDIAN_CONSISTENCY * math.sqrt(2 * spread**2 / repeats)


# ─── tests ───────────────────────────────────────────────────────────────────


def test_a_three_repeat_keep_records_dispersion_provenance_and_cost(tmp_path):
    """AC-EVL-202 (a): a keep earned with ``--repeats 3`` writes the dispersion
    it was judged on, the standard error and the margin actually applied, the
    six-field provenance block, and both cost fields as an explicit null — and
    ``status --require-provenance`` accepts the ledger the run produced.
    """
    repo = make_repo(tmp_path / "repo", value=10.0)
    agent = write_agent(tmp_path, step=2)

    proc = support.run_engine(*support.init_args(repo, repeats=3, target=9), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr

    argv = support.run_args(repo, agent, extra=["--max-iterations", "3", "--json"])
    proc = support.run_engine(*argv, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr

    events = support.read_events(repo)
    assert [t["outcome"] for t in trials(events)] == ["keep"]
    assert [e["reason"] for e in events if e.get("type") == "stop"] == ["target"]
    trial = trials(events)[0]

    # The dispersion. Three jittered repeats: 8.0, 8.2, 8.4.
    assert trial["values"] == [8.0, 8.2, 8.4]
    assert trial["repeats"] == 3
    assert trial["spread"] == pytest.approx(0.2)
    assert trial["honest"] is True

    # The arbitration. The margin is z * SE here, not the 0.01 * 10.2 floor.
    se = expected_se(0.2, 3)
    assert trial["se"] == pytest.approx(se)
    assert trial["margin"] == pytest.approx(1.96 * se)
    assert trial["margin"] > abs(10.2) * 0.01

    # The provenance: the ledger's own six-field vocabulary, built from this
    # run's config (the vocabulary itself is pinned in test_eval_provenance).
    block = trial["provenance"]
    assert set(block) == set(ledger_mod.PROVENANCE_FIELDS)
    assert block["model"] == "command:default"
    assert block["model_route"] == Path(sys.executable).name
    version = support.run_engine("--version", cwd=tmp_path)
    assert version.returncode == 0, version.stderr
    assert block["engine_version"] == version.stdout.strip()
    run_json = repo / STATE / "run.json"
    verify = json.loads(run_json.read_text(encoding="utf-8"))["verify"]
    assert block["referee_version"] == (
        "verify:" + hashlib.sha256(verify.encode("utf-8")).hexdigest()[:12]
    )
    assert block["profile_sha256"] == hashlib.sha256(run_json.read_bytes()).hexdigest()
    assert ISO_UTC.match(block["timestamp"]), block["timestamp"]

    # The cost: unknown, which is a different claim from zero.
    assert "agent_tokens" in trial and trial["agent_tokens"] is None
    assert "agent_api_calls" in trial and trial["agent_api_calls"] is None
    assert trial["agent_tokens"] != 0

    proc = support.run_engine(
        "status", "--repo", str(repo), "--require-provenance", cwd=tmp_path
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ledger: valid" in proc.stdout


def test_an_improvement_inside_the_margin_is_inconclusive_and_reverted(tmp_path):
    """AC-EVL-202 (b): a genuine 0.2 improvement — beyond the legacy relative
    floor — that lands inside the measured margin is recorded ``inconclusive``
    and reverted: no commit, the incumbent untouched, no provenance (nothing was
    decided), and the ledger still passes ``--require-provenance``.
    """
    repo = make_repo(tmp_path / "repo", value=10.0)
    agent = write_agent(tmp_path, step=0.2)

    proc = support.run_engine(*support.init_args(repo, repeats=3), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    before = support.git(repo, "rev-parse", "HEAD").stdout.strip()

    argv = support.run_args(repo, agent, extra=["--max-iterations", "1", "--json"])
    proc = support.run_engine(*argv, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr

    events = support.read_events(repo)
    baseline = [e for e in events if e.get("type") == "baseline"][0]
    assert baseline["values"] == [10.0, 10.2, 10.4]
    assert [t["outcome"] for t in trials(events)] == ["inconclusive"]
    trial = trials(events)[0]

    # A real improvement (the legacy rule would have kept it), inside the noise.
    delta = baseline["metric"] - trial["metric"]
    assert delta == pytest.approx(0.2)
    assert delta > abs(baseline["metric"]) * 0.01
    assert trial["margin"] == pytest.approx(1.96 * expected_se(0.2, 3))
    assert trial["margin"] > delta
    assert trial["repeats"] == 3
    assert trial["honest"] is True
    assert trial["se"] == pytest.approx(expected_se(0.2, 3))

    # Reverted exactly like a discard: the improvement was not kept.
    assert (repo / "src" / "value.txt").read_text(encoding="utf-8").strip() == "10.0"
    assert support.git(repo, "rev-parse", "HEAD").stdout.strip() == before
    assert support.git(repo, "status", "--porcelain").stdout == ""

    # No decision, so no provenance block — and the gate must still pass.
    assert "provenance" not in trial
    proc = support.run_engine(
        "status", "--repo", str(repo), "--require-provenance", cwd=tmp_path
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
