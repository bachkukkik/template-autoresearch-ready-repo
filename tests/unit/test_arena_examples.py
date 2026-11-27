"""PRD 31. IDs: AC-ARN-020..032 — the two scripted counterparts, verified.

Every replay runs into a pytest temp directory (never inside the worktree) and
is then compared byte for byte with the vendored record, so the record has to
earn its numbers: `play.py` is re-run as a subprocess with an explicit timeout,
the banks are re-added from the rows, and every captain digest is re-computed.
The README assertions are structural — a section that loses its entries fails.
"""

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "autoresearch" / "contract" / "examples"
ARENA = EXAMPLES / "arena"
PLAY = ARENA / "play.py"
COUNTERPARTS = ("ex1-music-abc-cs", "ex2-iris-knn-cs")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rules = _load(ARENA / "rules.py", "arena_rules_examples")


def _game(name):
    module = _load(EXAMPLES / name / "game.py", "arena_game_" + name.replace(
        "-", "_"))
    return module.GAME


def _record(name):
    return json.loads((EXAMPLES / name / "scoreboard.json").read_text())


def _section(text, heading):
    """The body of one `##` section, up to the next `##` heading."""
    assert heading in text, f"README lost its {heading!r} section"
    body = text.split(heading, 1)[1]
    return body.split("\n## ", 1)[0]


def _bullets(section):
    """Bullet blocks, continuation lines folded in."""
    blocks, current = [], None
    for line in section.splitlines():
        if line.startswith("- "):
            if current is not None:
                blocks.append(current)
            current = line
        elif current is not None and line.strip():
            current += " " + line.strip()
        elif current is not None:
            blocks.append(current)
            current = None
    if current is not None:
        blocks.append(current)
    return blocks


@pytest.fixture(scope="module")
def replays(tmp_path_factory):
    """One replay per counterpart, into a temp dir; the record is per module."""
    out = {}
    for name in COUNTERPARTS:
        target = tmp_path_factory.mktemp(name)
        done = subprocess.run(
            [sys.executable, str(PLAY), "replay",
             "--game", str(EXAMPLES / name / "game.py"), "--out", str(target)],
            capture_output=True, text=True, timeout=180,
        )
        assert done.returncode == 0, done.stderr
        out[name] = target
    return out


# --- AC-ARN-020 ---


def test_ac_arn_020_ex1_replay_reproduces_the_record(replays):
    """AC-ARN-020: an ex1-cs replay in a temp dir equals the vendored record."""
    for name in ("scoreboard.json", "scoreboard.md"):
        fresh = (replays["ex1-music-abc-cs"] / name).read_bytes()
        vendored = (EXAMPLES / "ex1-music-abc-cs" / name).read_bytes()
        assert fresh == vendored, f"{name} is not byte-identical"


# --- AC-ARN-021 ---


def test_ac_arn_021_ex1_void_round_is_injected_and_unpaid():
    """AC-ARN-021: ex1-cs's void round is labelled injected, banks unchanged."""
    record = _record("ex1-music-abc-cs")
    voids = [row for row in record["rounds"] if row["void"]]
    assert len(voids) == 1, "the scripted story has exactly one void round"
    row = voids[0]
    assert row["void"] == "B not served"
    assert row["injected"] == ["B"], "the fault is scripted, not a real timeout"
    assert row["payoff"] == [0.0, 0.0]
    assert row["cost"] == {"A": 0, "B": 0}
    assert row["winner"] is None
    assert row["landed"] == {"A": False, "B": False}
    previous = record["rounds"][row["round"] - 2]["banks"]
    assert row["banks"] == previous, "a void round must not move a bank"
    matrix = [pair for pair in record["matrix"] if pair.get("void")]
    assert len(matrix) == 1 and matrix[0]["void"] == "B not served"
    assert matrix[0]["payoff"] == [0.0, 0.0]
    # A kept a candidate and was still paid nothing: the round never played out.
    assert row["results"]["A"]["keeps"]
    assert row["results"]["B"]["attempts"] == 0


# --- AC-ARN-022 ---


@pytest.mark.parametrize("name", COUNTERPARTS)
def test_ac_arn_022_banks_are_the_sum_of_the_rows(name):
    """AC-ARN-022: bank == start_bank + sum(payoff - cost) over the rows."""
    record = _record(name)
    start = {"PORTABLE": rules.PORTABLE,
             "LEAGUE_S38": rules.LEAGUE_S38}[record["economy"]].start_bank
    assert record["banks"] == record["rounds"][-1]["banks"]
    for index, team in enumerate(("A", "B")):
        total = float(start)
        for row in record["matrix"]:
            total += row["payoff"][index] - row["cost"][team]
        assert record["banks"][team] == pytest.approx(total, abs=1e-6), team


# --- AC-ARN-023 ---


@pytest.mark.parametrize("name", COUNTERPARTS)
def test_ac_arn_023_captain_digests_verify(name):
    """AC-ARN-023: each vendored .sha256 equals the sha256 of its .json."""
    record = _record(name)
    digests = sorted((EXAMPLES / name).glob("round-*/captain-*.sha256"))
    assert len(digests) == 8, "four rounds, two sealed captains each"
    for path in digests:
        body = (path.parent / f"{path.stem}.json").read_text(encoding="utf-8")
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        assert path.read_text(encoding="utf-8").strip() == digest
        # The same digest the rules produce, so the text is canonical JSON.
        assert digest == rules.seal(json.loads(body))[1]
        team = path.stem.split("-")[1]
        round_no = int(path.parent.name.split("-")[1])
        sealed = record["rounds"][round_no - 1]["captains"][team]["sha256"]
        assert sealed == digest


# --- AC-ARN-024 ---


@pytest.mark.parametrize("name", COUNTERPARTS)
def test_ac_arn_024_seat_copies_keep_frozen_files(name, replays):
    """AC-ARN-024: a seat's frozen files are byte-identical to the base's."""
    game = _game(name)
    base = (EXAMPLES / name / game["base"]).resolve()
    assert game["files"], "a seat needs at least one frozen file"
    seats = sorted(replays[name].glob("round-*/seat-*"))
    # A seat directory appears only when the seat actually ran something.
    assert len(seats) >= 4
    for workdir in seats:
        for frozen in game["files"]:
            here = (workdir / frozen).read_bytes()
            assert here == (base / frozen).read_bytes()
        assert (workdir / game["editable"]).is_file()
    # The trunk copy is the start file verbatim: the referee does not mutate it
    # either, so a seat is the only place a candidate can appear.
    trunk = replays[name] / "round-1" / "trunk-measure" / game["editable"]
    assert trunk.read_bytes() == (base / game["start"]).read_bytes()


# --- AC-ARN-025 ---


def test_ac_arn_025_ex2_replay_reproduces_the_record(replays):
    """AC-ARN-025: an ex2-cs replay in a temp dir equals the vendored record."""
    for file_name in ("scoreboard.json", "scoreboard.md"):
        fresh = (replays["ex2-iris-knn-cs"] / file_name).read_bytes()
        vendored = (EXAMPLES / "ex2-iris-knn-cs" / file_name).read_bytes()
        assert fresh == vendored, f"{file_name} is not byte-identical"


# --- AC-ARN-026 ---


def test_ac_arn_026_ex2_records_a_fallback_and_a_clamp():
    """AC-ARN-026: ex2-cs records one fallback captain and one clamped buy."""
    record = _record("ex2-iris-knn-cs")
    choices = [row["captains"][team]["choice"] for row in record["rounds"]
               for team in ("A", "B")]
    fallbacks = [c for c in choices if c["reason"] == "captain fallback"]
    clamped = [c for c in choices if c.get("clamped")]
    assert len(fallbacks) == 1, "one malformed reply, one fallback"
    assert fallbacks[0] == {"strategy": "k", "buy": 0,
                            "reason": "captain fallback"}
    assert len(clamped) == 1, "one over-limit buy, one clamp"
    assert clamped[0]["buy"] == 2, "clamped to the economy's buy_max"
    game = _game("ex2-iris-knn-cs")
    raw = [text for round_replies in game["captains"].values()
           for text in round_replies.values() if '"buy": 3' in text]
    assert len(raw) == 1, "the raw reply asked for 3"
    pool = list(game["strategies"])
    reparsed = rules.parse_captain(
        raw[0], rules.fallback_choice("k", False, pool), pool, 2,
        rules.PORTABLE)
    assert reparsed == clamped[0]


# --- AC-ARN-027 ---


def test_ac_arn_027_ex2_exact_tie_goes_to_the_opener():
    """AC-ARN-027: ex2-cs's exact tie at the ceiling goes to the opener."""
    record = _record("ex2-iris-knn-cs")
    ties = [row for row in record["rounds"]
            if not row["void"] and row["payoff"][0] == row["payoff"][1]]
    assert ties, "the vendored record must contain an exact tie"
    for row in ties:
        assert row["winner"] == row["opener"]
        assert rules.round_winner(row["payoff"][0], row["payoff"][1],
                                  row["opener"]) == row["winner"]
    ceiling = [row for row in ties if row["payoff"][0] > 0]
    assert ceiling, "the ceiling tie is a tie at a positive profit"
    assert ceiling[0]["landed"][ceiling[0]["winner"]] is True
    assert record["final_trunk_metric"] == 1.0


# --- AC-ARN-028 ---


def test_ac_arn_028_ex2_equilibrium_stays_unreached():
    """AC-ARN-028: ex2-cs reports not-reached while a cell is unexplored."""
    record = _record("ex2-iris-knn-cs")
    eq = record["equilibrium"]
    assert eq["reached"] is False
    assert eq == record["rounds"][-1]["equilibrium"]
    assert any(eq["unknown"][team] for team in ("A", "B"))
    assert "distance" in eq["unknown"]["A"]
    assert eq["current"]["A"] == "k" and eq["current"]["B"] == "distance"
    # The floor ratchets once per settled round, so the last round judges
    # against start + 3 steps: 100 * 0.025 == 2.5.
    steps = len(record["rounds"]) - 1
    floor = rules.PORTABLE.default_floor + steps * rules.PORTABLE.ratchet_step
    assert eq["threshold"] == round(100.0 * floor, 6) == 2.5


# --- AC-ARN-029 ---


@pytest.mark.parametrize("name", COUNTERPARTS)
def test_ac_arn_029_no_absolute_path_or_timestamp(name):
    """AC-ARN-029: vendored output carries no absolute path or timestamp."""
    files = [path for path in (EXAMPLES / name).rglob("*")
             if path.is_file()
             and path.suffix in (".json", ".md", ".sha256")]
    assert files, "there is a vendored record to check"
    absolute = re.compile(r"(?<![\w.-])/(?:home|tmp|workspace|var|Users)\b")
    stamp = re.compile(r"\b20\d\d-\d\d-\d\d\b")
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not absolute.search(text), path
        assert not stamp.search(text), path
        assert "T00:0" not in text, path
        assert "elapsed" not in text.lower(), path
        assert not re.search(r"\bseconds\b", text), path


# --- AC-ARN-030 ---


def test_ac_arn_030_readme_states_what_it_can_and_cannot():
    """AC-ARN-030: the README has CAN and CANNOT sections naming ex4 and ex5."""
    text = (ARENA / "README.md").read_text(encoding="utf-8")
    can = _section(text, "## What this can do")
    cannot = _section(text, "## What this cannot do")
    for word in ("bank", "loss bonus", "audit", "jackpot", "void",
                 "equilibrium", "opener", "live-mode recipe"):
        assert word in can, f"CAN lost {word!r}"
    for word in ("untested in CI",):
        assert word in can, f"CAN lost {word!r}"
    for name in ("ex4", "ex5"):
        assert name in cannot, f"CANNOT must name {name}"
    ex4 = [b for b in _bullets(cannot) if "ex4" in b]
    ex5 = [b for b in _bullets(cannot) if "ex5" in b]
    assert len(ex4) == 1 and len(ex5) == 1
    assert "invented" in ex4[0], "ex4 is absent: a replay would be made up"
    assert "follow-up issue" in ex5[0], "ex5 is absent for a named reason"
    for name in ("ex4-llm-repo-speedup-cs", "ex5-real-oss-speedup-cs"):
        assert name in cannot
        assert not (EXAMPLES / name).exists()


# --- AC-ARN-031 ---


def test_ac_arn_031_nonsense_entries_and_the_examples_link():
    """AC-ARN-031: >= 6 nonsense entries, and the index links the arena."""
    text = (ARENA / "README.md").read_text(encoding="utf-8")
    section = _section(text, "## Requests that make no sense")
    entries = [block for block in _bullets(section) if block.startswith('- *"')]
    assert len(entries) >= 6, f"only {len(entries)} entries"
    for block in entries:
        assert "Instead:" in block, f"no alternative in {block[:60]!r}"
    index = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    assert "arena/README.md" in index
    assert (ARENA / "README.md").is_file()
    # The rules table and the live recipe are part of the same contract.
    assert "LEAGUE_S38" in text and "PORTABLE" in text
    assert "untested in CI" in text


# --- AC-ARN-032 ---


def test_ac_arn_032_no_ex4_or_ex5_counterpart():
    """AC-ARN-032: no ex4-cs or ex5-cs directory exists, and none is implied."""
    for prefix in ("ex4", "ex5"):
        assert not list(EXAMPLES.glob(f"{prefix}*-cs")), prefix
    assert (EXAMPLES / "ex4-llm-repo-speedup").is_dir()
    assert (EXAMPLES / "ex5-real-oss-speedup").is_dir()
    for name in COUNTERPARTS:
        game = _game(name)
        assert (EXAMPLES / name / "game.py").is_file()
        assert (EXAMPLES / name / "scoreboard.json").is_file()
        assert game["base"].startswith("..")
