"""The hypothesis claim — the reader, the prompt contract, the ledger object.

IDs: AC-HYP-001..009. The layer is opt-in, so half of this module is the *off*
path: the prompt, the ledger row and the report of a run that never asked for a
claim are the artefacts they were before PRD 29. The golden block in AC-HYP-001
was captured from the engine before this module existed, so it is a record of
the old bytes rather than a description of the new ones.
"""
import json
import sys
from pathlib import Path

import pytest

# autoresearch/engine/ is not installed; the tests put it on sys.path themselves
# so `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "autoresearch" / "engine"))

from test_engine_support import (  # noqa: E402
    DECREMENT,
    init_run,
    make_target,
    read_events,
    run_args,
    run_cli,
    write_agent,
)

from autoresearch import claim as claim_mod  # noqa: E402
from autoresearch import config as config_mod  # noqa: E402
from autoresearch import ledger as ledger_mod  # noqa: E402
from autoresearch import loop as loop_mod  # noqa: E402
from autoresearch import prompt as prompt_mod  # noqa: E402
from autoresearch import report as report_mod  # noqa: E402

STATE = ".autoresearch"

#: Every key a repeats-1 keep carries — PRD 29 adds ``hypothesis`` only when the
#: flag is on, PRD 30 adds ``cost`` to every settled trial, and neither flag's
#: absence may add a third.
OFF_TRIAL_KEYS = [
    "agent_api_calls", "agent_seconds", "agent_tokens", "commit", "cost",
    "description",
    "direction", "guard", "honest", "iteration", "log_tail", "margin", "metric",
    "noise_floor", "outcome", "provenance", "raw", "repeats", "se", "seconds",
    "seq", "spread", "ts", "type", "values",
]

#: The prompt rendered before PRD 29, captured from the engine byte for byte.
GOLDEN_PROMPT = """# autoresearch — one iteration

## Program
Always prefer the smaller diff.
Never touch the score.

## Goal
shrink the value

## Metric
name: value
direction: lower is better
baseline: 10
incumbent: 8
target: 3

## Scope — you may edit only these paths
- src

## Protected files — DO NOT EDIT
- guard.py
- score.py

## Rules
1. Make exactly ONE coherent change.
2. Edit only paths inside the scope above. Anything else is rejected and reverted.
3. Do NOT run git commit, git reset or git checkout — the harness owns git.
4. Do not modify the verify or guard commands or the files that implement them.
5. Keep behaviour correct: the guard must pass and the verify command must still print the metric.
6. Finish with a single line: CHANGE: <one-line summary>

## Recent trials
- iter 1: keep, metric 9 — shave one
- iter 2: discard, metric 11 — increment
- iter 3: inconclusive, metric 8.8 — shave two
- iter 4: guard_failed, metric unknown — go negative

## Inconclusive — unproven, retry only with a larger change
- shave two: improvement smaller than the measurement noise

## Dead ends — do not repeat
- go negative
- increment

## Last failure (tail)
```
Traceback (most recent call last):
ValueError: negative
```
"""


def make_cfg(**overrides):
    """The configuration the golden prompt was rendered from."""
    data = dict(
        repo="/tmp/repo",
        verify="python3 score.py",
        metric_name="value",
        direction="lower",
        scope=("src",),
        guard="python3 guard.py",
        target=3.0,
        noise_floor=0.01,
        protected={"score.py": "0" * 64, "guard.py": "1" * 64},
        program="Always prefer the smaller diff.\nNever touch the score.\n",
        goal="shrink the value",
    )
    data.update(overrides)
    return config_mod.RunConfig(**data)


def make_state(**overrides):
    """The loop state the golden prompt was rendered from."""
    data = dict(
        baseline=10.0,
        incumbent=8.0,
        incumbent_commit="abc1234def",
        trials=[
            {"iteration": 1, "outcome": "keep", "metric": 9.0, "description": "shave one"},
            {"iteration": 2, "outcome": "discard", "metric": 11.0, "description": "increment"},
            {"iteration": 3, "outcome": "inconclusive", "metric": 8.8, "description": "shave two"},
            {"iteration": 4, "outcome": "guard_failed", "metric": None, "description": "go negative"},
        ],
        last_failure_log="Traceback (most recent call last):\nValueError: negative\n",
    )
    data.update(overrides)
    return prompt_mod.PromptState(**data)


# ─── helpers ────────────────────────────────────────────────────────────────


def trials(repo):
    """Every trial event this run recorded, in ledger order."""
    return [event for event in read_events(repo) if event.get("type") == "trial"]


def claim_agent(tmp_path, *, hypothesis="shaving two is worth two points",
                predict="+2", step=2, name="agent.py", exit_line=""):
    """A scripted agent: it moves the value, then prints a claim as JSONL.

    The claim travels the way an opencode part event travels — a JSON object
    whose assistant text is escaped inside ``part.text`` — and a decoy claim is
    printed *after* it inside a tool result, so "last claim wins" only holds for
    a reader that refuses to read a tool result at all.
    """
    lines = [
        "import json, pathlib, sys",
        "path = pathlib.Path(sys.argv[1]) / 'src' / 'value.txt'",
        f"path.write_text(str(int(path.read_text().strip()) - {step}))",
        "def say(text):",
        "    print(json.dumps({'type': 'text', 'part': {'text': text}}))",
        "say(" + repr(
            f"CHANGE: shave {step} | HYPOTHESIS: {hypothesis} | "
            f"PREDICT: {predict} | FALSIFIED IF: the value rises"
        ) + ")",
        "print(json.dumps({'type': 'tool_result', 'tool_result': "
        "{'text': 'CHANGE: decoy | HYPOTHESIS: a tool echoed this | "
        "PREDICT: -99 | FALSIFIED IF: x'}}))",
    ]
    if exit_line:
        lines.append(exit_line)
    return write_agent(tmp_path, "\n".join(lines) + "\n", name=name)


def _capture_prompts(monkeypatch):
    """Record every prompt the adapter is handed, in iteration order."""
    from autoresearch import adapters as adapters_mod

    seen = []
    original = adapters_mod.Adapter.run

    def spy(self, prompt, repo, timeout, iteration=1, state=None):
        seen.append(prompt)
        return original(
            self, prompt, repo, timeout, iteration=iteration, state=state
        )

    monkeypatch.setattr(adapters_mod.Adapter, "run", spy)
    return seen


# ─── the off path (SC-hyp-1) ────────────────────────────────────────────────


def test_a_run_without_the_flag_renders_the_prompt_it_always_did():
    """AC-HYP-001: ``PromptState`` defaults ``hypotheses`` to False, so every
    existing caller renders the golden block — instruction 6 included. The block
    was captured from the engine *before* this PRD, so a reflow of the rules
    section fails here rather than in a season."""
    assert prompt_mod.PromptState(baseline=1.0, incumbent=2.0).hypotheses is False
    assert prompt_mod.build_prompt(make_cfg(), make_state()) == GOLDEN_PROMPT
    assert (
        prompt_mod.build_prompt(make_cfg(), make_state(hypotheses=False))
        == GOLDEN_PROMPT
    )


def test_a_run_without_the_flag_records_no_claim_and_no_memory(tmp_path, monkeypatch):
    """AC-HYP-001: with the flag off a run whose agent *does* print a claim
    still records the row it always did — no ``hypothesis`` key, no
    ``refuted.json``, no calibration line — and the agent is never asked for
    one."""
    repo = make_target(tmp_path, value=10)
    script = claim_agent(tmp_path)
    assert init_run(repo, repeats=1) == 0
    prompts = _capture_prompts(monkeypatch)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    assert len(prompts) == 1
    assert "HYPOTHESIS:" not in prompts[0]
    assert "6. Finish with a single line: CHANGE: <one-line summary>\n" in prompts[0]

    trial = trials(repo)[0]
    assert trial["outcome"] == "keep"
    assert sorted(trial) == OFF_TRIAL_KEYS
    assert not (repo / STATE / "refuted.json").exists()

    # run.json is the file it was too: neither opt-in is written when unchosen,
    # and a file that does carry them is read back rather than ignored.
    run_json = json.loads((repo / STATE / "run.json").read_text(encoding="utf-8"))
    assert "hypotheses" not in run_json
    assert "margin_quantile" not in run_json
    chosen = config_mod.RunConfig.from_dict(
        dict(run_json, hypotheses=True, margin_quantile="t")
    )
    assert (chosen.hypotheses, chosen.margin_quantile) == (True, "t")
    assert chosen.as_dict()["margin_quantile"] == "t"
    with pytest.raises(config_mod.ConfigError):
        config_mod.RunConfig.from_dict(dict(run_json, margin_quantile="f"))

    assert run_cli(["report", "--repo", str(repo)]) == 0
    text = (repo / STATE / "report.md").read_text(encoding="utf-8")
    assert "calibration" not in text
    assert ledger_mod.validate(read_events(repo)) == []


# ─── the prompt contract (SC-hyp-2) ─────────────────────────────────────────


def test_the_opt_in_prompt_asks_for_one_claim_on_the_mandatory_line():
    """AC-HYP-002: with the flag on, instruction 6 is one physical line carrying
    the four labels, and the word ``HYPOTHESIS:`` appears exactly once in the
    whole prompt — the reader scores one claim, so the prompt asks for one."""
    off = prompt_mod.build_prompt(make_cfg(), make_state())
    on = prompt_mod.build_prompt(make_cfg(), make_state(hypotheses=True))

    old = "6. Finish with a single line: CHANGE: <one-line summary>"
    assert on == off.replace(old, prompt_mod.CLAIM_INSTRUCTION)
    assert on.count("HYPOTHESIS:") == 1

    line = prompt_mod.CLAIM_INSTRUCTION
    assert line in on.splitlines()          # one physical line, not a wrapped one
    for label in ("CHANGE:", "HYPOTHESIS:", "PREDICT:", "FALSIFIED IF:"):
        assert label in line
    assert line.startswith("6. Finish with a single line:")


# ─── the reader (SC-hyp-3, SC-hyp-4) ────────────────────────────────────────


def test_a_plain_line_carrying_the_labels_is_one_claim():
    """AC-HYP-003: the grammar. Four labels on one line make a claim; labels are
    case-insensitive and need no ``|``; a hypothesis with no number is still a
    claim; a number with no hypothesis is not."""
    claim = claim_mod.parse_claim(
        "CHANGE: shave 2 | HYPOTHESIS: fewer steps is faster | "
        "PREDICT: -2 | FALSIFIED IF: the value rises"
    )
    assert claim == {
        "text": "fewer steps is faster",
        "predict": -2.0,
        "falsified_if": "the value rises",
        "change": "shave 2",
    }
    assert claim_mod.CLAIM_KEYS == (
        "change", "hypothesis", "predict", "falsified_if"
    )

    padded = claim_mod.parse_claim(
        "change:a  hypothesis:b  predict:+1.5  falsified if:c"
    )
    assert (padded["change"], padded["text"], padded["predict"]) == ("a", "b", 1.5)

    assert claim_mod.parse_claim("HYPOTHESIS: an unmeasured guess")["predict"] is None
    assert claim_mod.parse_claim("CHANGE: b | PREDICT: 3") is None
    assert claim_mod.parse_claim("") is None
    assert claim_mod.parse_claim("no labels on this line") is None

    revised = "HYPOTHESIS: first guess\nHYPOTHESIS: the final statement"
    assert claim_mod.parse_claim(revised)["text"] == "the final statement"


def test_the_reader_takes_assistant_text_out_of_the_harness_jsonl():
    """AC-HYP-004: the channel. A claim arrives as JSONL — the text escaped
    inside a part object — so the reader decodes the line and takes assistant
    text only. A claim a tool result, a tool call or a captured stream carries
    is not a claim, and a claim echoed after the real one cannot displace it."""
    claim = (
        "CHANGE: shave 2 | HYPOTHESIS: the real one | PREDICT: -2 | "
        "FALSIFIED IF: it rises"
    )
    decoy = (
        "CHANGE: decoy | HYPOTHESIS: a tool echoed this | PREDICT: -99 | "
        "FALSIFIED IF: x"
    )

    shapes = (
        {"type": "text", "part": {"text": claim}},
        {"part": {"type": "text", "text": claim}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": claim}]}},
    )
    for shape in shapes:
        found = claim_mod.claim_from_transcript(json.dumps(shape))
        assert found is not None and found["text"] == "the real one", shape

    payloads = (
        {"type": "tool_result", "tool_result": {"text": decoy}},
        {"type": "tool", "tool_call": {"arguments": {"text": decoy}}},
        {"type": "function", "function": {"text": decoy}},
        {"type": "tool_result", "stdout": decoy, "stderr": decoy},
    )
    for payload in payloads:
        assert claim_mod.claim_from_transcript(json.dumps(payload)) is None, payload

    mixed = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "text": decoy},
                {"type": "text", "text": claim},
            ]
        },
    }
    assert claim_mod.claim_from_transcript(json.dumps(mixed))["text"] == "the real one"

    stream = "\n".join([json.dumps(shapes[0]), json.dumps(payloads[0])])
    assert claim_mod.claim_from_transcript(stream)["text"] == "the real one"

    prose = "some noise\nHYPOTHESIS: read as prose | PREDICT: 4"
    assert claim_mod.claim_from_transcript(prose)["text"] == "read as prose"


def test_the_reader_accepts_the_glyph_the_agent_typed():
    """AC-HYP-005: U+2212 MINUS SIGN, the en and em dashes, a leading ``+``,
    padding, a non-breaking space and a trailing unit all read as the number the
    agent meant — including escaped inside JSONL. A value that is still not
    a number yields ``predict: None``, the claim survives, nothing is scored."""
    ascii_minus = claim_mod.parse_claim("HYPOTHESIS: x | PREDICT: -1")["predict"]
    for glyph in ("\u2212", "\u2013", "\u2014"):
        claim = claim_mod.parse_claim(f"HYPOTHESIS: x | PREDICT: {glyph}1")
        assert claim["predict"] == ascii_minus == -1.0, glyph

    assert claim_mod.parse_claim("HYPOTHESIS: x | PREDICT: + 2.5")["predict"] == 2.5
    assert claim_mod.parse_claim("HYPOTHESIS: x | PREDICT:   3  points")["predict"] == 3.0
    assert claim_mod.parse_claim("HYPOTHESIS: x | PREDICT: \u00a0+7  %")["predict"] == 7.0

    escaped = json.dumps(
        {"type": "text", "part": {"text": "HYPOTHESIS: x | PREDICT: \u22121"}}
    )
    assert "\\u2212" in escaped        # the transcript carries the escape
    assert claim_mod.claim_from_transcript(escaped)["predict"] == -1.0

    for junk in ("nope", "", "1-2", "1e999", "NaN", "--1", "-"):
        claim = claim_mod.parse_claim(f"HYPOTHESIS: x | PREDICT: {junk}")
        assert claim is not None, junk
        assert claim["predict"] is None, junk


# ─── the ledger object (SC-hyp-5) ───────────────────────────────────────────


def test_a_settled_trial_records_the_claim_beside_the_result(tmp_path):
    """AC-HYP-006: an opted-in keep carries ``hypothesis`` with the claim, the
    prediction, the falsifier, ``sign_match: true`` for a result that moved the
    way it was predicted, and ``calibration: sign``."""
    repo = make_target(tmp_path, value=10)
    script = claim_agent(tmp_path)
    assert init_run(repo, repeats=1) == 0

    argv = run_args(repo, script, extra=["--hypotheses", "--max-iterations", "1"])
    assert run_cli(argv) == 0

    trial = trials(repo)[0]
    assert trial["outcome"] == "keep"
    assert trial["hypothesis"] == {
        "text": "shaving two is worth two points",
        "predict": 2.0,
        "falsified_if": "the value rises",
        "sign_match": True,
        "calibration": "sign",
    }
    assert ledger_mod.validate(read_events(repo)) == []


def test_a_claim_the_result_opposes_is_recorded_as_a_miss(tmp_path):
    """AC-HYP-006: a wrong-signed prediction is still a claim, recorded with
    ``sign_match: false``. The claim grades nothing: the verdict is the metric's
    and the margin's, so this trial is the keep it would have been anyway."""
    repo = make_target(tmp_path, value=10)
    script = claim_agent(tmp_path, predict="-2")
    assert init_run(repo, repeats=1) == 0

    argv = run_args(repo, script, extra=["--hypotheses", "--max-iterations", "1"])
    assert run_cli(argv) == 0

    trial = trials(repo)[0]
    assert trial["outcome"] == "keep"
    assert trial["hypothesis"]["predict"] == -2.0
    assert trial["hypothesis"]["sign_match"] is False
    assert trial["hypothesis"]["calibration"] == "sign"


def test_a_trial_that_states_no_claim_records_null(tmp_path):
    """AC-HYP-006: an agent that printed only ``CHANGE:`` records
    ``hypothesis: null`` — reported as missing, never as compliant. The report
    says the same thing: no numeric prediction was measured."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, repeats=1) == 0

    argv = run_args(repo, script, extra=["--hypotheses", "--max-iterations", "1"])
    assert run_cli(argv) == 0

    trial = trials(repo)[0]
    assert "hypothesis" in trial
    assert trial["hypothesis"] is None

    text = report_mod.render_markdown(config_mod.load(repo), read_events(repo))
    assert report_mod.CALIBRATION_NA in text
    assert "claims read" not in text


def test_sign_match_is_null_when_either_side_has_no_sign(tmp_path):
    """AC-HYP-007: ``sign_match`` is null — and ``calibration`` is ``n/a`` —
    when the prediction is missing, the prediction is zero, or the result was
    not measured. Null is not ``false``: an unscorable claim is not refuted."""
    no_number = {"text": "t", "predict": None, "falsified_if": "f"}
    record = loop_mod._hypothesis_record(no_number, 8.0, 10.0, "lower")
    assert record["sign_match"] is None
    assert record["calibration"] == "n/a"

    zero = {"text": "t", "predict": 0.0, "falsified_if": "f"}
    assert loop_mod._hypothesis_record(zero, 8.0, 10.0, "lower")["sign_match"] is None
    assert loop_mod._hypothesis_record(zero, None, 10.0, "lower")["sign_match"] is None
    assert loop_mod._hypothesis_record(zero, 8.0, None, "lower")["sign_match"] is None
    assert loop_mod._hypothesis_record(None, 8.0, 10.0, "lower") is None

    up = {"text": "t", "predict": 2.0, "falsified_if": "f"}
    assert loop_mod._hypothesis_record(up, 12.0, 10.0, "higher")["sign_match"] is True
    assert loop_mod._hypothesis_record(up, 12.0, 10.0, "lower")["sign_match"] is False


def test_a_zero_prediction_is_recorded_and_never_scored(tmp_path):
    """AC-HYP-007: through the loop, a ``PREDICT: 0`` claim rides on the event
    with ``sign_match: null`` — the claim is on the record, the score is not."""
    repo = make_target(tmp_path, value=10)
    script = claim_agent(tmp_path, predict="0")
    assert init_run(repo, repeats=1) == 0

    argv = run_args(repo, script, extra=["--hypotheses", "--max-iterations", "1"])
    assert run_cli(argv) == 0

    record = trials(repo)[0]["hypothesis"]
    assert record["predict"] == 0.0
    assert record["sign_match"] is None
    assert record["calibration"] == "n/a"


# ─── refutation memory (SC-hyp-6) ───────────────────────────────────────────


def test_a_refuted_claim_is_remembered_and_counted(tmp_path):
    """AC-HYP-008: a refuted claim appends one row with its reason; the
    identical text on the next trial increments ``count`` instead of
    duplicating, and the memory is written whole (a temp file renamed)."""
    repo = make_target(tmp_path, value=10)
    script = claim_agent(tmp_path, predict="-2")
    assert init_run(repo, repeats=1) == 0

    argv = run_args(repo, script, extra=["--hypotheses", "--max-iterations", "2"])
    assert run_cli(argv) == 0

    assert [t["hypothesis"]["sign_match"] for t in trials(repo)] == [False, False]
    path = repo / STATE / "refuted.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert rows == [
        {"text": "shaving two is worth two points", "reason": "sign", "count": 2}
    ]
    assert list((repo / STATE).glob("*.tmp")) == []


def test_the_refutation_memory_keeps_the_last_ten_distinct_texts(tmp_path):
    """AC-HYP-008: the memory is bounded — eleven distinct texts leave ten, the
    oldest dropped first, and an exact repeat still increments its own row."""
    repo = make_target(tmp_path, value=10)
    assert init_run(repo, repeats=1) == 0
    cfg = config_mod.load(repo)

    for index in range(12):
        loop_mod._record_refutation(cfg, f"claim {index}")

    path = repo / STATE / "refuted.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert [row["text"] for row in rows] == [f"claim {i}" for i in range(2, 12)]
    assert all(row["reason"] == "sign" and row["count"] == 1 for row in rows)

    loop_mod._record_refutation(cfg, "claim 11")
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert len(rows) == 10
    assert rows[-1] == {"text": "claim 11", "reason": "sign", "count": 2}


SCORE_DIVIDES = '''"""A score that explodes on 0 — the guard still passes: a crash."""
import pathlib

value = int(pathlib.Path("src/value.txt").read_text().strip())
print(f"METRIC value={100 // value}")
'''


def test_a_crash_agent_error_or_guard_failure_never_refutes(tmp_path):
    """AC-HYP-009: a crash, an agent error and a guard failure append nothing
    and increment nothing. A dead agent refuted nothing, and a trial that never
    settled carries no claim at all — the refutation memory stays absent."""
    cases = (
        ("guard_failed", dict(step=11), None, ""),
        ("crash", dict(step=10), SCORE_DIVIDES, ""),
        ("agent_error", dict(step=-2), None, "sys.exit(1)"),
    )
    for index, (outcome, kwargs, score_body, exit_line) in enumerate(cases):
        repo = make_target(tmp_path, name=f"repo{index}", score_body=score_body)
        script = claim_agent(
            tmp_path, name=f"agent{index}.py", exit_line=exit_line, **kwargs
        )
        assert init_run(repo, repeats=1) == 0

        argv = run_args(
            repo, script, extra=["--hypotheses", "--max-iterations", "1"]
        )
        assert run_cli(argv) == 0

        trial = trials(repo)[0]
        assert trial["outcome"] == outcome
        assert "hypothesis" not in trial
        assert not (repo / STATE / "refuted.json").exists(), outcome


# ─── the CLI wiring the quantile needs (SC-hyp-7) ───────────────────────────

#: A measurement that jitters between repeats, so the SE is a real number and a
#: quantile can be told apart from another one. The counter is an untracked
#: artifact the loop's own sweep removes after each measurement.
SCORE_JITTER = '''"""The measurement: the value plus a per-run jitter."""
import pathlib

value = float(pathlib.Path("src/value.txt").read_text().strip())
counter = pathlib.Path("jitter.count")
count = int(counter.read_text().strip()) if counter.exists() else 0
counter.write_text(str(count + 1))
print(f"METRIC value={value + 0.2 * (count % 3)}")
'''

GUARD_FLOAT = '''"""The guard: a candidate that breaks behaviour cannot score."""
import pathlib
import sys

raw = float(pathlib.Path("src/value.txt").read_text().strip())
sys.exit(0 if raw >= 0 else 1)
'''

FLOAT_AGENT = '''"""The seat: a float-shrinking script, outside the repo."""
import pathlib, sys

path = pathlib.Path(sys.argv[1]) / "src" / "value.txt"
path.write_text(str(round(float(path.read_text().strip()) - 2, 6)))
print("CHANGE: shave the value by 2")
'''


def test_the_margin_quantile_flag_reaches_the_margin_call(tmp_path):
    """SC-hyp-7: ``--margin-quantile t`` is threaded from the CLI into the margin
    the loop computes and records, so the same measurements are judged at
    ``t(0.975, df = n-1) * SE`` (4.303 at three repeats) instead of ``1.96 * SE``.
    The SE itself does not move: the quantile changed, not the arithmetic."""
    def margin_of(name, *extra):
        repo = make_target(
            tmp_path, name=f"repo-{name}", score_body=SCORE_JITTER,
            guard_body=GUARD_FLOAT,
        )
        script = write_agent(tmp_path, FLOAT_AGENT, name=f"agent-{name}.py")
        assert init_run(repo, repeats=3) == 0
        argv = run_args(repo, script, extra=["--max-iterations", "1", *extra])
        assert run_cli(argv) == 0
        return trials(repo)[0]

    z = margin_of("z")
    t = margin_of("t", "--margin-quantile", "t")

    assert z["repeats"] == t["repeats"] == 3
    assert t["se"] == z["se"]
    assert t["margin"] == pytest.approx(4.303 * t["se"])
    assert z["margin"] == pytest.approx(1.96 * z["se"])
    assert t["margin"] > z["margin"]
