"""Run provenance for every keep/discard decision.

IDs: AC-EVL-006, AC-EVL-007 (unit tier; the hundreds digit is the tier).

The ledger records *what* was decided; provenance records *under what* it was
decided. These tests pin both halves: the write-side block (six fields, profile
content hash, UTC timestamp, credential refusal) and the read-side gate
(``require_provenance`` fails a decision event that lacks the block, while
legacy ledgers without the flag keep validating).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

# autoresearch/engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "autoresearch" / "engine"))

import pytest

from autoresearch import __version__ as ENGINE_VERSION
from autoresearch import ledger as ledger_mod
from autoresearch.cli import EXIT_CONFIG, EXIT_LEDGER

# The engine path was just prepended, so these imports are deliberately not first.
import test_engine_support as support  # noqa: E402

ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

#: The ledger's vocabulary, pinned once as *data*: a JSON fixture outside the
#: ``*.py`` scan globs. Every other test references ``ledger_mod``'s own tuples,
#: so the values are stated in exactly one place that cannot drift from code.
VOCABULARY_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ledger_vocabulary.json"
)


def vocabulary():
    """The pinned vocabulary: outcomes, decisions and provenance fields."""
    return json.loads(VOCABULARY_PATH.read_text(encoding="utf-8"))


#: Every outcome the provenance gate must exempt, derived from the ledger's own
#: tuples so a newly added non-decision outcome is covered without an edit here.
NON_DECISION_OUTCOMES = tuple(
    outcome for outcome in ledger_mod.OUTCOMES if outcome not in ledger_mod.DECISION_OUTCOMES
)


@pytest.fixture
def profile(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text('{"metric": "value"}\n', encoding="utf-8")
    return path


def decision_block(profile, model="claude-sonnet-4-5", timestamp="2026-11-15T10:00:00Z"):
    return ledger_mod.provenance_block(
        model=model,
        model_route="anthropic/claude-sonnet-4-5",
        engine_version="0.1.0",
        referee_version="0.3.2",
        profile_path=profile,
        timestamp=timestamp,
    )


# ─── AC-EVL-006: the write-side block ────────────────────────────────────────


def test_provenance_block_has_all_six_fields(profile):
    """AC-EVL-006: the block carries model, route, both versions, the profile
    content hash and an ISO-8601 UTC timestamp."""
    block = decision_block(profile)
    assert set(block) == set(ledger_mod.PROVENANCE_FIELDS)
    assert block["model"] == "claude-sonnet-4-5"
    assert block["model_route"] == "anthropic/claude-sonnet-4-5"
    assert block["engine_version"] == "0.1.0"
    assert block["referee_version"] == "0.3.2"
    expected = hashlib.sha256(profile.read_bytes()).hexdigest()
    assert block["profile_sha256"] == expected
    assert block["timestamp"] == "2026-11-15T10:00:00Z"


def test_provenance_block_stamps_utc_now_when_timestamp_is_omitted(profile):
    """AC-EVL-006: without an explicit timestamp the block is stamped now, in
    the same UTC form the ledger's ``ts`` uses."""
    block = ledger_mod.provenance_block(
        model="m",
        model_route="r",
        engine_version="0.1.0",
        referee_version="0.3.2",
        profile_path=profile,
    )
    assert ISO_UTC.match(block["timestamp"]), block["timestamp"]


def test_profile_hash_tracks_profile_content(tmp_path):
    """AC-EVL-006: the hash is of the profile *bytes*, so editing the profile
    changes the recorded hash."""
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text("{}\n", encoding="utf-8")
    second.write_text('{"repeats": 3}\n', encoding="utf-8")
    left = decision_block(first)
    right = decision_block(second)
    assert left["profile_sha256"] != right["profile_sha256"]


def test_keep_and_discard_round_trip_with_provenance(tmp_path, profile):
    """AC-EVL-006: a keep and a discard written with the block read back with
    all six fields intact (a real append/read, not a dict in memory)."""
    path = tmp_path / "events.jsonl"
    ledger = ledger_mod.Ledger(path)
    ledger.append(support.baseline())
    ledger.append(
        {**support.trial(2, 1, "keep", 8.0, guard="pass"), "provenance": decision_block(profile)}
    )
    ledger.append(
        {**support.trial(3, 2, "discard", 9.9, guard="pass"), "provenance": decision_block(profile)}
    )

    events = ledger.read()
    assert ledger_mod.validate(events, require_provenance=True) == []
    decisions = [e for e in events if e.get("outcome") in ("keep", "discard")]
    assert len(decisions) == 2
    for event in decisions:
        block = event["provenance"]
        assert set(block) == set(ledger_mod.PROVENANCE_FIELDS)
        assert block["profile_sha256"] == hashlib.sha256(profile.read_bytes()).hexdigest()


def test_profile_hash_raises_ledger_error_when_the_profile_cannot_be_read(tmp_path):
    """AC-EVL-006: an unreadable profile is a ``LedgerError`` at the seam, not a
    traceback — a missing file and a directory both land on the same named error,
    so a caller cannot record a decision it never proved."""
    missing = tmp_path / "absent.json"
    directory = tmp_path / "profile-dir"
    directory.mkdir()
    for bad_path in (missing, directory):
        with pytest.raises(ledger_mod.LedgerError) as caught:
            ledger_mod.provenance_block(
                model="m",
                model_route="r",
                engine_version="0.1.0",
                referee_version="0.3.2",
                profile_path=bad_path,
            )
        assert "cannot hash profile" in str(caught.value)
        assert str(bad_path) in str(caught.value)


def test_provenance_block_refuses_a_route_that_embeds_credentials(profile):
    """AC-EVL-006: a route carrying ``user:token@`` userinfo is refused outright.
    The ledger is append-only, so a secret written there could only be rotated,
    never edited out — the only safe moment to reject it is before the write."""
    with pytest.raises(ledger_mod.LedgerError) as caught:
        ledger_mod.provenance_block(
            model="m",
            model_route="https://user:token@gateway.example/v1",
            engine_version="0.1.0",
            referee_version="0.3.2",
            profile_path=profile,
        )
    assert "model_route embeds credentials" in str(caught.value)
    # The error names no part of the secret — a refusal must not become a leak.
    assert "token" not in str(caught.value)
    # A route that merely names the host still builds a block.
    assert ledger_mod.provenance_block(
        model="m",
        model_route="https://gateway.example/v1",
        engine_version="0.1.0",
        referee_version="0.3.2",
        profile_path=profile,
    )["model_route"] == "https://gateway.example/v1"


def test_provenance_block_refuses_a_model_that_embeds_credentials(profile):
    """AC-EVL-006: ``--model`` is recorded *verbatim*, so it is held to the same
    rule as the route. A value carrying ``user:token@`` userinfo is refused at
    the seam that builds the block — the ledger is append-only, so a secret
    written there can only be rotated away, never edited out."""
    with pytest.raises(ledger_mod.LedgerError) as caught:
        ledger_mod.provenance_block(
            model="https://user:token@gateway.example/v1",
            model_route="command",
            engine_version="0.1.0",
            referee_version="0.3.2",
            profile_path=profile,
        )
    assert "model embeds credentials" in str(caught.value)
    # A refusal must not become the leak it prevents.
    assert "token" not in str(caught.value)

    # A model *name* — the only thing this field is for — still builds a block.
    block = ledger_mod.provenance_block(
        model="deepseek-v4",
        model_route="command",
        engine_version="0.1.0",
        referee_version="0.3.2",
        profile_path=profile,
    )
    assert block["model"] == "deepseek-v4"


def test_provenance_block_refuses_an_empty_model(profile):
    """AC-EVL-006: an empty (or blank) ``model`` makes a block that *looks*
    complete — the field is present — while naming nothing, so it is refused at
    the seam that builds it rather than appended as a hollow claim."""
    for empty in ("", "   "):
        with pytest.raises(ledger_mod.LedgerError) as caught:
            decision_block(profile, model=empty)
        assert "model is empty" in str(caught.value)


def test_provenance_block_refuses_a_field_over_the_length_cap(profile):
    """AC-EVL-006: ``model``/``model_route`` are identifiers written verbatim
    into an append-only file, so a pasted payload is refused by field name
    instead of appended forever; exactly at the cap still builds a block."""
    too_long = "m" * (ledger_mod.MAX_PROVENANCE_FIELD + 1)
    with pytest.raises(ledger_mod.LedgerError) as caught:
        decision_block(profile, model=too_long)
    assert "model is longer than" in str(caught.value)
    assert str(ledger_mod.MAX_PROVENANCE_FIELD) in str(caught.value)
    with pytest.raises(ledger_mod.LedgerError) as caught:
        ledger_mod.provenance_block(
            model="m",
            model_route=too_long,
            engine_version="0.1.0",
            referee_version="0.3.2",
            profile_path=profile,
        )
    assert "model_route is longer than" in str(caught.value)
    at_cap = decision_block(profile, model="m" * ledger_mod.MAX_PROVENANCE_FIELD)
    assert len(at_cap["model"]) == ledger_mod.MAX_PROVENANCE_FIELD


def test_provenance_block_refuses_a_non_string_field(profile):
    """AC-EVL-006: a non-string ``model_route`` is a *type* error, not a length
    error — the refusal names the field and the type it got, so an operator is
    not sent chasing 512 characters that were never there."""
    with pytest.raises(ledger_mod.LedgerError) as caught:
        ledger_mod.provenance_block(
            model="m",
            model_route=12345,
            engine_version="0.1.0",
            referee_version="0.3.2",
            profile_path=profile,
        )
    message = str(caught.value)
    assert "model_route is not a string" in message
    assert "int" in message
    assert "longer than" not in message


def test_non_decision_outcomes_do_not_need_provenance():
    """AC-EVL-006: provenance attaches to decisions; a crash or a no-change
    trial is not a keep/discard and stays valid without a block."""
    events = [support.baseline(), support.trial(2, 1, "no_change", None), support.stop(3)]
    assert ledger_mod.validate(events, require_provenance=True) == []


def test_the_ledger_vocabulary_matches_its_pinned_fixture():
    """AC-EVL-006: one intentional restatement of the vocabulary exists, as data
    (``tests/fixtures/ledger_vocabulary.json``), and this test holds the ledger
    to it. A name added, dropped or renamed — or a seventh provenance field —
    fails here, so the fixture cannot quietly become stale."""
    pinned = vocabulary()
    assert list(ledger_mod.OUTCOMES) == pinned["outcomes"]
    assert list(ledger_mod.DECISION_OUTCOMES) == pinned["decision_outcomes"]
    assert list(ledger_mod.PROVENANCE_FIELDS) == pinned["provenance_fields"]


def test_every_non_decision_outcome_is_exempt_from_the_gate():
    """AC-EVL-006: the set the parametrized gate test below walks is pinned here
    — seven non-decision outcomes exist today, and the gate owes each of them an
    exemption just as it owes keep/discard a block. ``inconclusive`` is a
    recorded outcome (PRD 20 SC-evl-2) but not a decision: the margin could not
    separate the runs, so there is no claim for provenance to underwrite.

    The names are read from the pinned fixture rather than restated: this module
    already imports ``ledger_mod``, and a second copy of the vocabulary in code
    is the copy that silently drifts.
    """
    pinned = vocabulary()
    assert NON_DECISION_OUTCOMES == tuple(
        outcome
        for outcome in pinned["outcomes"]
        if outcome not in pinned["decision_outcomes"]
    )
    assert len(NON_DECISION_OUTCOMES) == 7


def test_an_inconclusive_trial_validates_without_a_provenance_block():
    """AC-EVL-006: ``inconclusive`` is in the event vocabulary but not in
    ``DECISION_OUTCOMES``, so a trial the margin could not separate replays
    clean under ``require_provenance=True`` even though nothing was stamped."""
    assert "inconclusive" in ledger_mod.OUTCOMES
    assert "inconclusive" not in ledger_mod.DECISION_OUTCOMES

    events = [support.baseline(), support.trial(2, 1, "inconclusive", 9.99), support.stop(3)]
    assert ledger_mod.validate(events, require_provenance=True) == []
    # And the outcome is genuinely known to the vocabulary: a misspelling of it
    # would still be rejected, so the pass above is the exemption at work.
    typo = [support.baseline(), support.trial(2, 1, "inconclusiv", 9.99), support.stop(3)]
    assert ledger_mod.validate(typo, require_provenance=True) != []


@pytest.mark.parametrize("outcome", NON_DECISION_OUTCOMES)
def test_any_non_decision_outcome_skips_the_provenance_gate(outcome):
    """AC-EVL-006: only keep/discard are decisions. Every other recorded outcome
    — an inconclusive trial, a failed guard, a crash, a scope or protected-path
    violation, an agent error, a no-change trial — validates with
    ``require_provenance=True`` even though no block was stamped."""
    events = [support.baseline(), support.trial(2, 1, outcome, None), support.stop(3)]
    assert ledger_mod.validate(events, require_provenance=True) == []


# ─── AC-EVL-007: the read-side gate ──────────────────────────────────────────


def test_require_provenance_fails_on_a_missing_block_and_names_the_event():
    """AC-EVL-007: a decision event without the block is a validation error
    naming its seq, not a silent accept."""
    events = [support.baseline(), support.trial(2, 1, "keep", 8.0, guard="pass"), support.stop(3)]
    problems = ledger_mod.validate(events, require_provenance=True)
    assert len(problems) == 1
    assert "seq 2" in problems[0]
    assert "provenance" in problems[0]


def test_require_provenance_fails_on_a_missing_field_and_names_it(profile):
    """AC-EVL-007: a partial block fails on the missing field, naming the event
    and the field."""
    block = decision_block(profile)
    del block["model_route"]
    events = [
        support.baseline(),
        {**support.trial(2, 1, "discard", 9.9), "provenance": block},
    ]
    problems = ledger_mod.validate(events, require_provenance=True)
    assert len(problems) == 1
    assert "seq 2" in problems[0]
    assert "model_route" in problems[0]


def test_require_provenance_passes_when_the_block_is_present(profile):
    """AC-EVL-007: a complete block satisfies the gate."""
    events = [
        support.baseline(),
        {**support.trial(2, 1, "keep", 8.0, guard="pass"), "provenance": decision_block(profile)},
        support.stop(3),
    ]
    assert ledger_mod.validate(events, require_provenance=True) == []


def test_legacy_ledger_still_validates_without_the_flag():
    """AC-EVL-007: backward compatibility — the same decision event that fails
    with the flag is valid without it, so old ledgers keep replaying."""
    events = [support.baseline(), support.trial(2, 1, "keep", 8.0, guard="pass"), support.stop(3)]
    assert ledger_mod.validate(events) == []


def test_require_provenance_rejects_a_non_object_block():
    """AC-EVL-007: a provenance value that is not an object is a validation
    error — a string marker is not a provenance record."""
    events = [
        support.baseline(),
        {**support.trial(2, 1, "keep", 8.0, guard="pass"), "provenance": "model=x"},
    ]
    problems = ledger_mod.validate(events, require_provenance=True)
    assert len(problems) == 1
    assert "seq 2" in problems[0]
    assert "provenance" in problems[0]


def test_require_provenance_rejects_a_malformed_timestamp(profile):
    """AC-EVL-007: a timestamp that is not ISO-8601 UTC is a named problem even
    though the field is present — an unreadable instant is not a provenance
    claim, and the block must not pass on presence alone."""
    block = decision_block(profile, timestamp="not-a-timestamp")
    events = [
        support.baseline(),
        {**support.trial(2, 1, "keep", 8.0, guard="pass"), "provenance": block},
    ]
    problems = ledger_mod.validate(events, require_provenance=True)
    assert problems == ["seq 2: provenance timestamp is not ISO-8601 UTC"]
    # The same block with a real instant passes, so the check is about shape.
    events[1]["provenance"] = decision_block(profile, timestamp="2026-11-15T10:00:00Z")
    assert ledger_mod.validate(events, require_provenance=True) == []


def test_require_provenance_rejects_a_timestamp_with_a_trailing_newline(profile):
    """AC-EVL-007: ``^…$`` matches *before* a trailing newline, so
    ``"2026-11-15T10:00:00Z\\n"`` would slip through a ``match``. The instant is
    the whole string or it is not a timestamp, so the check is ``fullmatch``."""
    block = decision_block(profile, timestamp="2026-11-15T10:00:00Z\n")
    events = [
        support.baseline(),
        {**support.trial(2, 1, "discard", 9.9), "provenance": block},
    ]
    problems = ledger_mod.validate(events, require_provenance=True)
    assert problems == ["seq 2: provenance timestamp is not ISO-8601 UTC"]
    # The same instant without the newline passes: the check is about shape.
    block["timestamp"] = "2026-11-15T10:00:00Z"
    assert ledger_mod.validate(events, require_provenance=True) == []


def test_require_provenance_rejects_a_timestamp_in_unicode_digits(profile):
    """AC-EVL-007: a digit class that matches Unicode decimal digits accepts an
    Arabic-Indic timestamp (U+0660..U+0669) that no tool on this host can parse.
    The class is ``[0-9]``, so only ASCII digits form an instant."""
    arabic_indic = "\u0662\u0660\u0662\u0666-11-15T10:00:00Z"
    block = decision_block(profile, timestamp=arabic_indic)
    events = [
        support.baseline(),
        {**support.trial(2, 1, "discard", 9.9), "provenance": block},
    ]
    problems = ledger_mod.validate(events, require_provenance=True)
    assert problems == ["seq 2: provenance timestamp is not ISO-8601 UTC"]


def test_require_provenance_rejects_a_profile_hash_that_is_not_a_digest(profile):
    """AC-EVL-007: ``profile_sha256`` must be 64 lowercase hex characters; a
    truncated marker such as ``deadbeef`` proves nothing about the profile and
    fails by name."""
    block = decision_block(profile)
    block["profile_sha256"] = "deadbeef"
    events = [
        support.baseline(),
        {**support.trial(2, 1, "discard", 9.9), "provenance": block},
    ]
    problems = ledger_mod.validate(events, require_provenance=True)
    assert problems == ["seq 2: provenance profile_sha256 is not a 64-hex digest"]
    # Restoring the real digest clears it — nothing else about the event changed.
    block["profile_sha256"] = hashlib.sha256(profile.read_bytes()).hexdigest()
    assert ledger_mod.validate(events, require_provenance=True) == []


def test_require_valid_raises_ledger_error_naming_the_event(tmp_path):
    """AC-EVL-007: the throwing path (the CLI's exit-3 seam) carries the same
    message, so a script sees the offending seq."""
    path = tmp_path / "events.jsonl"
    ledger = ledger_mod.Ledger(path)
    ledger.append(support.baseline())
    ledger.append(support.trial(2, 1, "discard", 9.9))
    with pytest.raises(ledger_mod.LedgerError) as caught:
        ledger_mod.require_valid(path, require_provenance=True)
    assert "seq 2" in str(caught.value)
    # The same file loads cleanly under legacy validation.
    assert ledger_mod.require_valid(path)[-1].get("outcome") == "discard"


# ─── AC-EVL-006/007, the engine as the writer: decisions are stamped ─────────


def _trials(repo):
    return [e for e in support.read_events(repo) if e.get("type") == "trial"]


def _engine_run(repo, script, *, extra=(), init_extra=()):
    """Init + one iteration of the real loop, in-process."""
    assert support.init_run(repo, extra=list(init_extra)) == 0
    return support.run_cli(
        support.run_args(repo, script, extra=["--max-iterations", "1", *extra])
    )


def _expected_referee_version(repo):
    """``verify:<12 hex of sha256(cfg.verify)>`` — for the engine the verify
    command IS the referee, so its digest is the referee's identity."""
    cfg = json.loads((Path(repo) / ".autoresearch" / "run.json").read_text("utf-8"))
    return "verify:" + hashlib.sha256(cfg["verify"].encode("utf-8")).hexdigest()[:12]


def test_engine_stamps_provenance_on_decisions_only(tmp_path):
    """AC-EVL-006: a keep and a discard each carry the six-field block, built
    from the engine's own run config; an ``inconclusive`` trial — a fact, not a
    decision — carries none."""
    kept = support.make_target(tmp_path, name="kept", value=10)
    improving = support.write_agent(
        tmp_path, support.DECREMENT.format(step=2), name="improving.py"
    )
    assert _engine_run(kept, improving) == 0

    discarded = support.make_target(tmp_path, name="discarded", value=10)
    worsening = support.write_agent(tmp_path, support.INCREMENT, name="worsening.py")
    assert _engine_run(discarded, worsening) == 0

    unsure = support.make_target(tmp_path, name="unsure", value=10)
    assert _engine_run(unsure, improving, init_extra=["--noise-floor", "0.5"]) == 0

    keep_trial = _trials(kept)[0]
    discard_trial = _trials(discarded)[0]
    unsure_trial = _trials(unsure)[0]
    assert keep_trial["outcome"] == "keep"
    assert discard_trial["outcome"] == "discard"
    assert unsure_trial["outcome"] == "inconclusive"

    for repo, event in ((kept, keep_trial), (discarded, discard_trial)):
        block = event["provenance"]
        assert set(block) == set(ledger_mod.PROVENANCE_FIELDS)
        assert block["model"] == "command:default"
        assert block["model_route"] == Path(sys.executable).name
        assert block["engine_version"] == ENGINE_VERSION
        assert block["referee_version"] == _expected_referee_version(repo)
        assert block["profile_sha256"] == hashlib.sha256(
            (Path(repo) / ".autoresearch" / "run.json").read_bytes()
        ).hexdigest()
        assert ISO_UTC.match(block["timestamp"]), block["timestamp"]

    assert "provenance" not in unsure_trial
    # The written ledger satisfies the gate the reader will apply.
    assert ledger_mod.validate(support.read_events(kept), require_provenance=True) == []
    assert ledger_mod.validate(support.read_events(discarded), require_provenance=True) == []


def test_provenance_model_records_the_cli_model_when_one_is_given(tmp_path):
    """AC-EVL-006: ``--model`` lands in the block; without one the model is
    ``<agent>:default``, which says "the harness default" rather than naming a
    model the run never chose."""
    repo = support.make_target(tmp_path)
    script = support.write_agent(tmp_path, support.DECREMENT.format(step=2))
    assert _engine_run(repo, script, extra=["--model", "deepseek-v4"]) == 0

    block = _trials(repo)[0]["provenance"]
    assert block["model"] == "deepseek-v4"
    assert block["model_route"] == Path(sys.executable).name


def test_status_require_provenance_gates_the_ledger(tmp_path, capsys):
    """AC-EVL-007: ``status --require-provenance`` exits 0 on a ledger the engine
    wrote and ``EXIT_LEDGER`` once the blocks are gone; without the flag the same
    ledger still replays, so old runs are not invalidated by the new gate."""
    repo = support.make_target(tmp_path)
    script = support.write_agent(tmp_path, support.DECREMENT.format(step=2))
    assert _engine_run(repo, script) == 0
    capsys.readouterr()

    assert support.run_cli(["status", "--repo", str(repo), "--require-provenance"]) == 0
    assert "ledger: valid" in capsys.readouterr().out

    path = Path(repo) / ".autoresearch" / "events.jsonl"
    events = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]
    for event in events:
        event.pop("provenance", None)
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")

    assert (
        support.run_cli(["status", "--repo", str(repo), "--require-provenance"])
        == EXIT_LEDGER
    )
    err = capsys.readouterr().err
    assert "provenance" in err
    assert "seq 2" in err

    # Backward compatibility: the same ledger is accepted without the flag.
    assert support.run_cli(["status", "--repo", str(repo)]) == 0
    assert "ledger: valid" in capsys.readouterr().out


# ─── AC-EVL-006, the seam that must refuse before a write ────────────────────

#: A token-shaped value that must not survive anywhere in the target tree.
LEAKED_SECRET = "SECRETVALUE-hunter2"


def _tree_text(root):
    """Every readable byte under ``root``, git metadata included, as one string."""
    return "".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(Path(root).rglob("*"))
        if path.is_file()
    )


def test_the_cli_refuses_a_credential_bearing_model_before_it_writes_anything(
    tmp_path,
):
    """AC-EVL-006: ``--model`` carrying URL userinfo is a configuration error
    (exit 2) caught in preflight — before the baseline is measured and before a
    trial can reach the keep path. No ledger line is written and the secret
    appears nowhere in the tree, which is why this drives the real CLI as a
    subprocess: the gate must hold on the path an operator actually takes.

    The value is *token-only* userinfo — ``https://TOKEN@host``, no colon, which
    RFC 3986 allows. A predicate that insisted on ``user:password@`` accepted it
    and wrote the token into ``.autoresearch/events.jsonl``.
    """
    repo = support.make_target(tmp_path)
    script = support.write_agent(tmp_path, support.DECREMENT.format(step=2))
    assert support.init_run(repo) == 0
    head_before = support.head(repo)

    # The sentinel is *interpolated*: a literal placeholder here would make the
    # leak assertions below vacuous, which is exactly what they exist to catch.
    bad_model = f"https://{LEAKED_SECRET}@gateway.example/v1"
    argv = support.run_args(
        repo, script, extra=["--model", bad_model, "--max-iterations", "1"]
    )
    proc = support.run_engine(*argv, cwd=tmp_path)

    assert proc.returncode == EXIT_CONFIG
    assert "--model" in proc.stderr and "credential" in proc.stderr
    assert LEAKED_SECRET not in proc.stdout + proc.stderr
    # Nothing recorded: no ledger file at all, and no baseline line either.
    assert not (Path(repo) / ".autoresearch" / "events.jsonl").exists()
    assert support.read_events(repo) == []
    assert support.head(repo) == head_before
    assert LEAKED_SECRET not in _tree_text(tmp_path)


def test_a_provenance_failure_leaves_the_incumbent_checked_out(tmp_path, monkeypatch, capsys):
    """AC-EVL-006: the block is built *before* the candidate is committed, so a
    provenance failure cannot leave HEAD on a candidate no event records.
    Nothing in the block depends on the commit sha; building it first makes the
    failure a clean abort — incumbent checked out, worktree clean, ledger still
    valid."""
    repo = support.make_target(tmp_path, value=10)
    script = support.write_agent(tmp_path, support.DECREMENT.format(step=2))
    assert support.init_run(repo) == 0
    head_before = support.head(repo)
    capsys.readouterr()

    def refuse(*args, **kwargs):
        raise ledger_mod.LedgerError("cannot hash profile: simulated")

    monkeypatch.setattr(ledger_mod, "provenance_block", refuse)

    code = support.run_cli(support.run_args(repo, script, extra=["--max-iterations", "1"]))

    assert code == EXIT_LEDGER
    # The candidate that would have been kept is neither checked out nor on disk.
    assert support.head(repo) == head_before
    assert support.value(repo) == 10
    assert support.git(repo, "status", "--porcelain").stdout == ""
    events = support.read_events(repo)
    assert [event["type"] for event in events] == ["baseline"]
    assert ledger_mod.validate(events) == []

