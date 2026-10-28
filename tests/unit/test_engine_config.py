"""``init`` — validation, protected hashes and the immutable run.json. IDs: AC-ENG-040..045."""
import sys
from pathlib import Path

# engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

import json

from test_engine_support import git, init_run, make_target, run_cli

from autoresearch import config as config_mod


def test_init_writes_run_json_and_a_self_ignoring_state_dir(tmp_path):
    """AC-ENG-040: a good init records the config, hashes the protected files and
    leaves `git status` clean."""
    repo = make_target(tmp_path)
    assert init_run(repo, target=3) == 0

    cfg = config_mod.load(repo)
    assert cfg.direction == "lower"
    assert cfg.metric_name == "value"
    assert cfg.scope == ("src",)
    assert cfg.target == 3.0
    assert cfg.repo == str(repo)
    assert cfg.repeats == 1

    state = repo / ".autoresearch"
    assert (state / ".gitignore").read_text() == "*\n"
    assert state / "run.json" in list(state.iterdir())
    assert git(repo, "status", "--porcelain").stdout == ""


def test_default_protected_covers_the_measurement_and_the_guard(tmp_path):
    """AC-ENG-041: score.py and guard.py are named in --verify/--guard, so they
    are protected without being asked for."""
    repo = make_target(tmp_path)
    assert init_run(repo) == 0
    cfg = config_mod.load(repo)
    assert set(cfg.protected) == {"score.py", "guard.py"}
    assert cfg.protected["score.py"] == config_mod.hash_file(repo / "score.py")

    # An extra --protect adds to the set rather than replacing it.
    other = make_target(tmp_path, name="repo2")
    assert init_run(other, extra=["--protect", "src/value.txt"]) == 0
    assert set(config_mod.load(other).protected) == {"score.py", "guard.py", "src/value.txt"}


def test_init_refuses_a_dirty_tree(tmp_path, capsys):
    """AC-ENG-042: the loop's whole model assumes it owns the diff, so a dirty
    tree is a precondition error."""
    repo = make_target(tmp_path)
    (repo / "src" / "value.txt").write_text("11\n", encoding="utf-8")

    assert init_run(repo) == 2
    assert "not clean" in capsys.readouterr().err
    assert not (repo / ".autoresearch" / "run.json").exists()


def test_init_ignores_its_own_state_dir_when_checking_cleanliness(tmp_path):
    """AC-ENG-042b: a previous run's state must not make the tree "dirty"."""
    repo = make_target(tmp_path)
    assert init_run(repo) == 0
    assert (repo / ".autoresearch" / "events.jsonl").exists() is False
    # A second init still sees a clean tree and only objects to the existing run.
    assert init_run(repo) == 2
    assert init_run(repo, extra=["--force"]) == 0


def test_init_refuses_a_scope_that_does_not_exist(tmp_path, capsys):
    """AC-ENG-043: a scope must name something real, and a glob is not a scope."""
    repo = make_target(tmp_path)
    assert init_run(repo, scope="nope") == 2
    assert "does not exist" in capsys.readouterr().err

    assert init_run(repo, scope="src/*.py") == 2
    assert "glob" in capsys.readouterr().err

    assert init_run(repo, scope="../elsewhere") == 2


def test_init_refuses_an_existing_run_unless_forced(tmp_path, capsys):
    """AC-ENG-044: re-initialising silently would invalidate every past event, so
    it needs --force, and --force archives the old run instead of deleting it."""
    repo = make_target(tmp_path)
    assert init_run(repo, target=3) == 0
    first = config_mod.load(repo)

    assert init_run(repo, target=5) == 2
    assert "--force" in capsys.readouterr().err
    assert config_mod.load(repo).target == 3.0

    assert init_run(repo, target=5, extra=["--force"]) == 0
    assert config_mod.load(repo).target == 5.0

    archives = list((repo / ".autoresearch" / "archive").iterdir())
    assert len(archives) == 1
    archived = json.loads((archives[0] / "run.json").read_text())
    assert archived["target"] == first.target


def test_force_does_not_archive_before_it_validates_its_arguments(tmp_path, capsys):
    """AC-ENG-044b: --force archives only after the new arguments validate, so a
    typo cannot destroy the run it was meant to replace."""
    repo = make_target(tmp_path)
    assert init_run(repo, target=3) == 0
    state = repo / ".autoresearch"
    run_json, events = state / "run.json", state / "events.jsonl"
    events.write_text('{"type": "baseline", "seq": 1}\n', encoding="utf-8")
    before_run, before_events = run_json.read_text(), events.read_text()

    assert init_run(repo, target=5, extra=["--force", "--protect", "nope.txt"]) == 2
    assert "nope.txt" in capsys.readouterr().err
    assert run_json.read_text() == before_run
    assert events.read_text() == before_events
    assert not (state / "archive").exists()
    assert config_mod.load(repo).target == 3.0

    assert init_run(repo, target=5, extra=["--force", "--program", "nope.md"]) == 2
    assert "nope.md" in capsys.readouterr().err
    assert run_json.read_text() == before_run
    assert events.read_text() == before_events
    assert not (state / "archive").exists()
    assert config_mod.load(repo).target == 3.0

    assert init_run(repo, scope="nope", target=5, extra=["--force"]) == 2
    assert run_json.read_text() == before_run
    assert not (state / "archive").exists()
    assert config_mod.load(repo).target == 3.0

    # A --force that does validate still archives the previous run.
    assert init_run(repo, target=5, extra=["--force"]) == 0
    assert config_mod.load(repo).target == 5.0
    archived = list((state / "archive").iterdir())
    assert len(archived) == 1
    assert json.loads((archived[0] / "run.json").read_text())["target"] == 3.0


def test_init_refuses_a_detached_head_and_a_non_repo(tmp_path, capsys):
    """AC-ENG-045: a run needs a named branch to move, and a repo to commit to."""
    repo = make_target(tmp_path)
    first = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "checkout", "--detach", first)
    assert init_run(repo) == 2
    assert "detached" in capsys.readouterr().err

    plain = tmp_path / "plain"
    plain.mkdir()
    assert init_run(plain) == 2
    assert "not a git repository" in capsys.readouterr().err


def test_run_json_round_trips_the_whole_config(tmp_path):
    """AC-ENG-045b: run.json is the replay source, so every field survives."""
    repo = make_target(tmp_path)
    program = tmp_path / "program.md"
    program.write_text("Always prefer the smaller diff.\n", encoding="utf-8")
    assert (
        init_run(
            repo,
            target=1.5,
            repeats=3,
            extra=[
                "--goal", "shrink the value",
                "--program", str(program),
                "--noise-floor", "0.05",
                "--verify-timeout", "30",
                "--guard-timeout", "20",
            ],
        )
        == 0
    )
    cfg = config_mod.load(repo)
    assert cfg.goal == "shrink the value"
    assert cfg.program.strip() == "Always prefer the smaller diff."
    assert cfg.noise_floor == 0.05
    assert cfg.repeats == 3
    assert (cfg.verify_timeout, cfg.guard_timeout) == (30.0, 20.0)

    raw = json.loads((repo / ".autoresearch" / "run.json").read_text())
    assert raw["scope"] == ["src"]
    assert raw["direction"] == "lower"
    assert raw["verify"].endswith("score.py")


def test_protected_mismatch_is_detected(tmp_path):
    """AC-ENG-045c: editing a protected file is detectable by hash alone."""
    repo = make_target(tmp_path)
    assert init_run(repo) == 0
    cfg = config_mod.load(repo)
    assert config_mod.protected_mismatches(cfg) == []

    (repo / "score.py").write_text("print('METRIC value=0')\n", encoding="utf-8")
    assert config_mod.protected_mismatches(cfg) == ["score.py"]


def test_path_tokens_only_returns_things_that_could_be_files():
    """AC-ENG-045d: the protected default is derived from the command's path
    tokens, so flags, URLs and shell metacharacters must not become "files"."""
    tokens = config_mod.path_tokens("python3 score.py --flag -x https://e.com/a $HOME/x")
    assert tokens == ["python3", "score.py"]


# ─── scope matching and scope validity (AC-ENG-045e/f/g) ─────────────────────


def test_under_scope_strips_one_leading_dot_slash_not_a_character_set():
    """AC-ENG-045e: ``lstrip('./')`` ate every leading dot and slash, so a
    dot-directory scope owned nothing: ``.github/x`` became ``github/x``."""
    assert config_mod.under_scope(".github/workflows/x.yml", [".github"])
    assert config_mod.under_scope("./.github/workflows/x.yml", [".github"])
    assert config_mod.under_scope(".gitignore", [".gitignore"])
    assert config_mod.under_scope("./.env.d/keys", [".env.d"])
    assert not config_mod.under_scope(".githubfoo/x", [".github"])
    assert not config_mod.under_scope("src/x.py", [".github"])


def test_scope_cannot_be_the_repo_root(tmp_path, capsys):
    """AC-ENG-045f: a scope of ``.`` makes ``git clean -fd`` repo-wide, so a
    revert would delete every untracked file the operator owns."""
    import pytest

    repo = make_target(tmp_path)
    for raw in (".", "./", ".//"):
        with pytest.raises(config_mod.ConfigError):
            config_mod.normalize_scope(repo, [raw])
        assert init_run(repo, scope=raw) == 2
        assert "--scope" in capsys.readouterr().err
    assert not (repo / ".autoresearch" / "run.json").exists()


def test_non_finite_limits_are_rejected(tmp_path, capsys):
    """AC-ENG-045g: nan/inf make every comparison and every bound meaningless —
    ``nan < 0`` is False, so the old checks let them through."""
    repo = make_target(tmp_path)
    for extra in (
        ["--noise-floor", "nan"],
        ["--target", "inf"],
        ["--verify-timeout", "inf"],
        ["--guard-timeout", "nan"],
    ):
        assert init_run(repo, extra=extra) == 2, extra
        assert "finite" in capsys.readouterr().err
    assert not (repo / ".autoresearch" / "run.json").exists()
