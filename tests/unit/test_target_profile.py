"""PRD 22 — the target-profile contract. IDs: AC-TPR-001..014 (unit).

Hermetic: every case builds its own profiles root, checkout and evaluator under
``tmp_path``. Nothing here runs the engine or writes inside the repo.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TARGET_DIR = ROOT / "autoresearch" / "target"
TARGETS = ROOT / "autoresearch" / "targets"


def _module(stem: str):
    """Load one target/ module by path — it is a CLI surface, not an installed package."""
    name = f"target_profile_{stem}"
    spec = importlib.util.spec_from_file_location(name, TARGET_DIR / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


target = _module("target")
guard = _module("guard")
import_runs = _module("import_runs")
cli = _module("cli")

BASE = json.loads((TARGETS / "example.json").read_text(encoding="utf-8"))


def write_profile(tmp_path, name="demo", **overrides):
    """A profile under its own targets root; every key present unless overridden."""
    targets = tmp_path / "targets"
    targets.mkdir(parents=True, exist_ok=True)
    data = dict(BASE)
    data["name"] = name
    data.update(overrides)
    path = targets / f"{name}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return targets, data, path


@pytest.fixture
def checkout(tmp_path):
    """A checkout with the paths a generic Python profile names, and nothing else."""
    root = tmp_path / "checkout"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "program.md").write_text("edit src only\n", encoding="utf-8")
    (root / "src" / "keep.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests" / "test_keep.py").write_text("def test_ok():\n    assert 1\n", encoding="utf-8")
    return root


def ok_profile(tmp_path, checkout, **overrides):
    """A profile that applies cleanly: referee points at a real harness file."""
    overrides.setdefault("referee", str(TARGET_DIR / "target.py"))
    targets, data, path = write_profile(tmp_path, **overrides)
    return target.apply_profile(data, checkout, path), path


# ─── resolution ──────────────────────────────────────────────────────────────


def test_resolve_target_flag_then_env_then_cwd(tmp_path, monkeypatch):
    """AC-TPR-001: the target is the flag, else AUTORESEARCH_TARGET_REPO, else cwd."""
    env = {target.TARGET_ENV: str(tmp_path / "env")}
    assert target.resolve_target(str(tmp_path / "flag"), env, tmp_path / "cwd") == (
        tmp_path / "flag"
    ).resolve()
    assert target.resolve_target(None, env, tmp_path / "cwd") == (tmp_path / "env").resolve()
    assert target.resolve_target("  ", {}, tmp_path / "cwd") == (tmp_path / "cwd").resolve()
    assert target.resolve_target(None, {}, None) == Path.cwd().resolve()
    monkeypatch.setenv("HOME", str(tmp_path))
    assert target.resolve_target("~/repo", {}, None) == (tmp_path / "repo").resolve()


def test_load_profile_reads_a_declared_name_only(tmp_path):
    """AC-TPR-002: a declared name loads, from the argument or the env."""
    targets, data, path = write_profile(tmp_path)
    assert target.load_profile("demo", {}, targets) == data
    assert target.load_profile(None, {target.PROFILE_ENV: "demo"}, targets)["name"] == "demo"
    assert target.profile_path("demo", targets) == path


def test_undeclared_name_is_refused_naming_what_is_declared(tmp_path):
    """AC-TPR-003: an undeclared name refuses and lists the declared ones."""
    targets, _, _ = write_profile(tmp_path)
    with pytest.raises(target.TargetError) as exc:
        target.load_profile("absent", {}, targets)
    assert "not declared" in str(exc.value)
    assert "demo" in str(exc.value)


@pytest.mark.parametrize(
    "name", ["../demo", "sub/demo", "..", ".", "~demo", "demo.json", "sub\\demo", ""]
)
def test_traversal_shaped_names_are_refused(tmp_path, name):
    """AC-TPR-004: a path, a dot-name or an empty name never reaches the filesystem."""
    targets, _, _ = write_profile(tmp_path)
    with pytest.raises(target.TargetError) as exc:
        target.load_profile(name, {}, targets)
    reason = str(exc.value).split(" under ")[0]
    assert "declared name" in reason or "traversal" in reason, str(exc.value)


def test_malformed_profiles_are_refused_by_name(tmp_path):
    """AC-TPR-005: missing keys, a non-object, invalid JSON and a name mismatch refuse."""
    targets, data, path = write_profile(tmp_path)
    without = dict(data)
    del without["arena_test_files"]
    path.write_text(json.dumps(without), encoding="utf-8")
    with pytest.raises(target.TargetError, match="missing arena_test_files"):
        target.load_profile("demo", {}, targets)

    path.write_text("[]", encoding="utf-8")
    with pytest.raises(target.TargetError, match="not a JSON object"):
        target.load_profile("demo", {}, targets)

    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(target.TargetError, match="cannot read"):
        target.load_profile("demo", {}, targets)

    path.write_text(json.dumps({**data, "name": "other"}), encoding="utf-8")
    with pytest.raises(target.TargetError, match="calls itself"):
        target.load_profile("demo", {}, targets)


# ─── relativity ──────────────────────────────────────────────────────────────


def test_apply_profile_splits_harness_and_target_keys(tmp_path, checkout):
    """AC-TPR-006: harness keys resolve here; target keys resolve in the checkout."""
    resolution, path = ok_profile(
        tmp_path,
        checkout,
        protected=["src/keep.py"],
        scopes={"better": ["src"], "faster": ["tests"]},
        program="program.md",
        arena_test_files=[],
    )
    assert resolution.ok, resolution.reasons()
    assert resolution.harness["engine"] == (ROOT / "autoresearch/engine/bin/autoresearch").resolve()
    assert resolution.harness["referee"] == (TARGET_DIR / "target.py").resolve()
    assert str(checkout) in resolution.harness["verify"]
    assert resolution.harness["guard_command"].endswith("--target-repo " + str(checkout) + " guard")
    assert resolution.target_paths["program"] == (checkout / "program.md").resolve()
    assert resolution.target_paths["protected"] == ((checkout / "src/keep.py").resolve(),)
    assert resolution.target_paths["scopes"]["faster"] == ((checkout / "tests").resolve(),)
    assert resolution.target_paths["arena_test_files"] == ()
    assert resolution.profile_path == path


def test_harness_keys_do_not_move_with_the_target(tmp_path):
    """AC-TPR-006: two checkouts, one harness — the evaluator path is identical."""
    first = tmp_path / "a"
    second = tmp_path / "b"
    for root in (first, second):
        (root / "src").mkdir(parents=True)
    one, _ = ok_profile(tmp_path / "one", first)
    two, _ = ok_profile(tmp_path / "two", second)
    assert one.harness["engine"] == two.harness["engine"]
    assert one.harness["referee"] == two.harness["referee"]
    assert one.harness["verify"] != two.harness["verify"]
    assert one.target_paths["scopes"]["better"] != two.target_paths["scopes"]["better"]


def test_each_bad_key_returns_its_reason_without_raising(tmp_path, checkout):
    """AC-TPR-007: a misdescribed key is refused with a reason; the rest still resolve."""
    targets, data, path = write_profile(
        tmp_path,
        protected=["../outside.py"],
        program="/abs/program.md",
        scopes="src",
        direction="sideways",
        surprise=True,
    )
    data["name"] = "renamed"
    resolution = target.apply_profile(data, checkout, path)
    assert not resolution.ok
    assert "contains '..'" in resolution.refused["protected[0]"]
    assert "absolute" in resolution.refused["program"]
    assert "non-empty object" in resolution.refused["scopes"]
    assert "one of higher, lower" in resolution.refused["direction"]
    assert "not a declared profile key" in resolution.refused["surprise"]
    assert "declared under" in resolution.refused["name"]
    assert resolution.harness["engine"] is not None
    assert resolution.target_paths["protected"] == ()
    with pytest.raises(target.TargetError, match="refused"):
        resolution.engine_argv()
    assert len(resolution.reasons()) >= 6


def test_empty_arena_test_files_stays_and_a_deleted_key_refuses(tmp_path, checkout):
    """AC-TPR-008: [] is kept as empty; deleting the key is refused by name."""
    resolution, _ = ok_profile(tmp_path, checkout, arena_test_files=[])
    assert resolution.ok
    assert resolution.target_paths["arena_test_files"] == ()

    targets, data, path = write_profile(tmp_path / "b")
    del data["arena_test_files"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(target.TargetError, match="missing arena_test_files"):
        target.load_profile("demo", {}, targets)


def test_engine_argv_is_the_resolved_plan(tmp_path, checkout):
    """AC-TPR-009: argv names the harness engine, the checkout and every flag once."""
    resolution, _ = ok_profile(
        tmp_path,
        checkout,
        scopes={"better": ["src", "tests"], "cheaper": ["tests"]},
        protected=["src/keep.py"],
        program="program.md",
    )
    argv = resolution.engine_argv()
    assert argv[0] == str((ROOT / "autoresearch/engine/bin/autoresearch").resolve())
    assert argv[1] == "init"
    assert argv[argv.index("--repo") + 1] == str(checkout)
    assert argv[argv.index("--metric-name") + 1] == "tests_passed"
    assert argv[argv.index("--direction") + 1] == "higher"
    scopes = [argv[i + 1] for i, arg in enumerate(argv) if arg == "--scope"]
    assert scopes == ["src", "tests"]
    assert argv[argv.index("--protect") + 1] == "src/keep.py"
    assert argv[argv.index("--program") + 1] == "program.md"
    assert set(argv) >= {"--repo", "--verify", "--guard", "--scope", "--protect", "--state-dir"}


def test_engine_argv_puts_the_run_state_in_the_harness(tmp_path, checkout):
    """AC-TPR-015: the plan hands the engine a --state-dir under runs_dir, never the checkout."""
    resolution, _ = ok_profile(tmp_path, checkout)
    argv = resolution.engine_argv()
    state = Path(argv[argv.index("--state-dir") + 1])
    assert state == resolution.harness["runs_dir"] / "state"
    assert state == (ROOT / "autoresearch/runs/example/state").resolve()
    assert checkout not in state.parents


# ─── the evaluator guard ─────────────────────────────────────────────────────


def test_digest_and_tamper_are_pure_comparisons(tmp_path):
    """AC-TPR-010: a sha256 per file (None when gone); tamper names every change."""
    first = tmp_path / "a.py"
    second = tmp_path / "b.py"
    first.write_text("one\n", encoding="utf-8")
    second.write_text("two\n", encoding="utf-8")
    before = guard.digest([first, second, tmp_path / "gone.py"])
    assert before[first] and before[second]
    assert before[tmp_path / "gone.py"] is None
    assert guard.tamper(before, dict(before)) is None

    first.write_text("one changed\n", encoding="utf-8")
    second.unlink()
    record = guard.tamper(before, guard.digest([first, second]))
    assert record["round"] == "void" and record["void"] is True
    assert record["event"] == guard.TAMPER_EVENT
    assert str(first) in record["evaluator_tampered"]
    assert str(second) in record["evaluator_tampered"]
    assert "moved during the round" in record["reason"]


def test_round_guard_refuses_a_missing_evaluator(tmp_path, checkout):
    """AC-TPR-011: a round never starts when a file it is scored by is absent."""
    resolution, _ = ok_profile(
        tmp_path, checkout, referee=str(tmp_path / "no-such-evaluator.py")
    )
    assert resolution.ok
    with pytest.raises(guard.GuardError, match="missing"):
        guard.RoundGuard.start(resolution)
    assert not (checkout / "src" / "round.json").exists()


def test_round_guard_refuses_an_evaluator_inside_the_checkout(tmp_path, checkout):
    """AC-TPR-016: an evaluator the subject can edit is refused before the round opens."""
    evaluator = checkout / "score.py"
    evaluator.write_text("print('METRIC value=1')\n", encoding="utf-8")
    resolution, _ = ok_profile(tmp_path, checkout, referee=str(evaluator))
    assert resolution.ok
    with pytest.raises(guard.GuardError, match="inside the measured checkout"):
        guard.RoundGuard.start(resolution)


def test_round_guard_voids_a_tampered_round_and_keeps_the_evidence(tmp_path, checkout):
    """AC-TPR-012: the evaluator changing mid-round voids it; nothing is restored."""
    evaluator = tmp_path / "evaluator.py"
    evaluator.write_text("print('METRIC value=1')\n", encoding="utf-8")
    resolution, _ = ok_profile(tmp_path, checkout, referee=str(evaluator))
    before = sorted(p.relative_to(checkout).as_posix() for p in checkout.rglob("*"))

    round_guard = guard.RoundGuard.start(resolution)
    assert evaluator in round_guard.paths
    assert resolution.profile_path in round_guard.paths
    assert (ROOT / "autoresearch/engine/bin/autoresearch") in round_guard.paths
    assert round_guard.settle() is None

    evaluator.write_text("print('METRIC value=999')\n", encoding="utf-8")
    record = round_guard.settle()
    assert record["void"] is True
    assert str(evaluator) in record["evaluator_tampered"]
    assert evaluator.read_text(encoding="utf-8") == "print('METRIC value=999')\n"
    assert sorted(p.relative_to(checkout).as_posix() for p in checkout.rglob("*")) == before


# ─── import-runs and the shipped example ─────────────────────────────────────


def make_runs(root):
    """An external runs dir: state, scoreboard, an archive and runtime residue."""
    root.mkdir(parents=True)
    (root / "state.json").write_text('{"season": 19, "round": 7}', encoding="utf-8")
    (root / "scoreboard.md").write_text("# scoreboard\n", encoding="utf-8")
    (root / "season-001").mkdir()
    (root / "season-001" / "close.json").write_text("{}", encoding="utf-8")
    (root / "season-001" / "state.lock").write_text("", encoding="utf-8")
    (root / "season-001" / "__pycache__").mkdir()
    (root / "season-001" / "__pycache__" / "x.pyc").write_text("", encoding="utf-8")
    (root / "round-0001").mkdir()
    (root / "round-0001" / "record.json").write_text("{}", encoding="utf-8")
    return root


def test_import_runs_dry_run_copy_and_clobber_refusal(tmp_path, capsys):
    """AC-TPR-013: a copy command — dry-run writes nothing, an existing state.json refuses."""
    source = make_runs(tmp_path / "runs")
    dest = tmp_path / "dest"
    assert import_runs.main(["--from", str(source), "--to", str(dest), "--dry-run"]) == 0
    assert not dest.exists()
    assert "would copy state.json" in capsys.readouterr().out

    assert import_runs.main(["--from", str(source), "--to", str(dest)]) == 0
    out = capsys.readouterr().out
    assert "4 file(s)" in out
    assert (dest / "state.json").is_file()
    assert not (dest / "season-001" / "state.lock").exists()
    assert not (dest / "season-001" / "__pycache__").exists()
    assert import_runs.main(["--from", str(source), "--to", str(dest)]) == 1
    assert "already exists" in capsys.readouterr().err
    assert import_runs.main(["--from", str(source), "--to", str(dest), "--force"]) == 0


def test_import_runs_defaults_to_the_profile_runs_dir(tmp_path):
    """AC-TPR-013: without --to the destination is the profile's runs_dir, one validator."""
    assert import_runs.default_to("example") == (ROOT / "autoresearch/runs/example").resolve()
    with pytest.raises(ValueError, match="declared name"):
        import_runs.default_to("../example")
    with pytest.raises(ValueError, match="declared"):
        import_runs.default_to("absent")

    inside = str((ROOT / "autoresearch/runs/abs-demo").resolve())
    targets, _, _ = write_profile(tmp_path, runs_dir=inside)
    assert import_runs.default_to("demo", targets) == Path(inside)

    targets, _, _ = write_profile(tmp_path / "b", runs_dir=str(tmp_path / "elsewhere"))
    with pytest.raises(ValueError, match="not a directory under the harness repo"):
        import_runs.default_to("demo", targets)


def test_shipped_example_validates_and_states_the_split(tmp_path):
    """AC-TPR-014: the example carries every key, the split and an empty arena list;
    its referee is the documented stub, so a round refuses it as missing."""
    data = target.load_profile("example")
    assert [key for key in target.PROFILE_KEYS if key not in data] == []
    comment = " ".join(data["$comment"])
    assert "harness-relative" in comment and "target-relative" in comment
    assert data["arena_test_files"] == []
    assert data["protected"] == [] and data["guard_steps"] == []
    assert (ROOT / data["engine"]).is_file()
    assert data["guard_command"].count("{referee}") == 1
    assert target.profile_path("example") == TARGETS / "example.json"

    resolution = target.apply_profile(data, tmp_path)
    assert resolution.ok, resolution.reasons()
    with pytest.raises(guard.GuardError, match="evaluator file\\(s\\) missing"):
        guard.RoundGuard.start(resolution)


def test_cli_refuses_a_traversal_name_before_the_filesystem(capsys):
    """AC-TPR-014: the CLI exits 2 with the reason; a path never becomes a profile read."""
    assert cli.main(["../demo"]) == 2
    err = capsys.readouterr().err
    assert "declared name" in err and "autoresearch/targets" in err
