"""SC1/SC6 — program.md is the human-edited skill file. IDs: AC-TPL-00N."""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
PROGRAM_MD = os.path.join(REPO_ROOT, "contract", "program.md")


def _read_program_md():
    assert os.path.isfile(PROGRAM_MD), "contract/program.md missing"
    with open(PROGRAM_MD) as f:
        return f.read()


def test_program_md_run_tag_and_branch():
    """AC-TPL-001: setup specifies a date-based run tag and autoresearch/<tag>."""
    text = _read_program_md()
    assert "run tag" in text
    assert "autoresearch/<tag>" in text
    assert "git checkout -b autoresearch/<tag>" in text
    assert "fresh run" in text


def test_program_md_can_cannot_rules():
    """AC-TPL-002: CAN/CANNOT rules — prepare.py is off-limits, train.py only."""
    text = _read_program_md()
    assert "**What you CAN do:**" in text
    assert "**What you CANNOT do:**" in text
    assert "Modify `prepare.py`" in text
    assert "this is the only file you edit" in text
    assert "get the lowest val_bpb" in text


def test_program_md_never_stop_and_summary_keys():
    """AC-TPL-003: NEVER STOP loop + output-format summary keys."""
    text = _read_program_md()
    assert "NEVER STOP" in text
    assert "LOOP FOREVER" in text
    for key in ("val_bpb:", "training_seconds:", "total_seconds:",
                "peak_vram_mb:", "num_steps:", "num_params_M:"):
        assert key in text


def test_program_md_sc6_caveats():
    """AC-TPL-004: platform-bound results, sample generated output, Goodhart."""
    text = _read_program_md()
    assert "platform-bound" in text
    assert "sample" in text or "Sample" in text
    assert "Goodhart" in text
    assert "frozen metric" in text


def test_program_md_porting_noise_floor_and_hard_kill():
    """AC-TPL-005: porting to any X — the four invariants, the noise floor, the
    hard kill, and evaluator-owned status."""
    text = _read_program_md()
    # a porting section naming the four invariants
    assert "## Porting to any X" in text
    assert "One editable artifact" in text
    for owned in ("evaluate_bpb", "DIRECTION", "NOISE_FLOOR", "TIME_BUDGET"):
        assert owned in text, owned
    assert "append-only" in text
    assert "check-ledger" in text
    assert "run.log" in text
    assert "never self-reported" in text
    assert "T2" in text
    # the noise floor lives in the simplicity criterion
    assert "noise floor" in text
    assert "shrinks" in text
    # the status is the evaluator's, not the agent's
    assert "prepare.decide" in text
    # the in-loop ceiling has an outer hard kill, and a kill is a crash
    assert "timeout 600 python3 train.py" in text
    assert "hard kill" in text