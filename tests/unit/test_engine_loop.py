"""The loop — baseline, outcomes, resets and stop conditions. IDs: AC-ENG-050..059."""
import json
import sys
from pathlib import Path

# engine/ is not installed; the tests put it on sys.path themselves so
# `python3 -m pytest` works from the repo root with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

from test_engine_support import (  # noqa: E402
    DECREMENT,
    GUARD_BREAK,
    INCREMENT,
    NO_CHANGE,
    OUTSIDE_SCOPE,
    agent_cmd,
    git,
    head,
    init_args,
    init_run,
    make_target,
    outcomes,
    read_events,
    run_args,
    run_cli,
    stop_reason,
    value,
    write_agent,
)

from autoresearch import config as config_mod  # noqa: E402
from autoresearch import ledger as ledger_mod  # noqa: E402

SCORE_DIVIDES = '''"""A score that explodes on 0 — guard still passes, so this is a crash."""
import pathlib

value = int(pathlib.Path("src/value.txt").read_text().strip())
print(f"METRIC value={100 // value}")
'''


def commit_count(repo):
    return int(git(repo, "rev-list", "--count", "HEAD").stdout.strip())


# ─── dry run ─────────────────────────────────────────────────────────────────


def test_dry_run_validates_and_touches_nothing(tmp_path, capsys):
    """AC-ENG-050: a dry run proves the commands, the protected hashes and the
    adapter argv before a single commit exists."""
    repo = make_target(tmp_path)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, target=3) == 0
    before = head(repo)
    commits = commit_count(repo)

    assert run_cli(run_args(repo, script, extra=["--dry-run"])) == 0

    out = capsys.readouterr().out
    assert "adapter argv:" in out
    assert "<prompt: " in out
    assert "stops:" in out
    assert str(script) in out

    assert head(repo) == before
    assert commit_count(repo) == commits
    assert not (repo / ".autoresearch" / "events.jsonl").exists()


def test_dry_run_fails_when_a_precondition_is_broken(tmp_path, capsys, monkeypatch):
    """AC-ENG-050b: the dry run is a real preflight, so a broken guard or a
    missing binary exits 2 instead of printing a plan."""
    import shutil

    repo = make_target(tmp_path)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, extra=["--guard", f"{sys.executable} missing_guard.py"]) == 0

    assert run_cli(run_args(repo, script, extra=["--dry-run"])) == 2
    assert "guard fails" in capsys.readouterr().err

    # A harness binary that is not on PATH is also a config error — forced here,
    # because whether `claude` is installed is the host's business, not the test's.
    monkeypatch.setattr(shutil, "which", lambda *args, **kwargs: None)
    assert run_cli(run_args(repo, None, agent="claude", extra=["--dry-run"])) == 2
    assert "not on PATH" in capsys.readouterr().err


# ─── baseline ────────────────────────────────────────────────────────────────


def test_baseline_is_recorded_once_with_the_metric_and_head(tmp_path):
    """AC-ENG-051: the first run measures the incumbent and appends exactly one
    baseline event, keyed to the commit it measured."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, NO_CHANGE)
    assert init_run(repo, extra=[]) == 0
    before = head(repo)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    baselines = [e for e in read_events(repo) if e.get("type") == "baseline"]
    assert len(baselines) == 1
    assert baselines[0]["metric"] == 10.0
    assert baselines[0]["commit"] == before
    assert ledger_mod.validate(read_events(repo)) == []
    assert config_mod.load(repo).metric_name == "value"


def test_target_already_met_at_baseline_stops_immediately(tmp_path):
    """AC-ENG-051b: no point spending an agent call on a run that already won."""
    repo = make_target(tmp_path, value=2)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, target=3) == 0
    before = head(repo)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "5"])) == 0

    assert stop_reason(repo) == "target"
    assert outcomes(repo) == []
    assert head(repo) == before


def test_a_missing_agent_binary_is_a_config_error_before_the_baseline(tmp_path, capsys):
    """AC-ENG-051d: a harness that cannot be executed is a precondition error,
    not an agent failure — the run stops before it has measured anything, so no
    baseline event claims the run started."""
    repo = make_target(tmp_path, value=10)
    assert init_run(repo) == 0

    assert run_cli(
        [
            "run", "--repo", str(repo), "--agent", "command",
            "--agent-cmd", "/nonexistent/agent {prompt_file}",
            "--max-iterations", "1",
        ]
    ) == 2

    err = capsys.readouterr().err
    assert "not on PATH" in err
    assert "Traceback" not in err
    assert read_events(repo) == []
    assert git(repo, "status", "--porcelain").stdout == ""


def test_a_binary_that_vanishes_after_the_preflight_is_an_agent_error(tmp_path, monkeypatch):
    """AC-ENG-051e: the preflight cannot see a binary removed between the check
    and the fork, so a failed exec is still an outcome — never a traceback."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo) == 0
    before = head(repo)

    from autoresearch import adapters as adapters_mod

    def vanished(self, prompt, repo_path, timeout, iteration=1):
        raise FileNotFoundError(2, "No such file or directory", "agent")

    monkeypatch.setattr(adapters_mod.Adapter, "run", vanished)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0
    assert outcomes(repo) == ["agent_error"]
    assert head(repo) == before
    assert "could not be started" in (
        repo / ".autoresearch" / "last_agent.log"
    ).read_text(encoding="utf-8")


def test_baseline_refuses_a_failing_guard_and_an_unparsable_metric(tmp_path, capsys):
    """AC-ENG-051c: a baseline that breaks its own rules is a precondition error,
    not a run with a zero score."""
    broken_guard = make_target(
        tmp_path, name="guard_fails",
        guard_body="import sys\nsys.exit(1)\n",
    )
    assert init_run(broken_guard) == 0
    script = write_agent(tmp_path, NO_CHANGE)
    assert run_cli(run_args(broken_guard, script)) == 2
    assert "guard fails at baseline" in capsys.readouterr().err

    silent_score = make_target(
        tmp_path, name="no_metric", score_body="print('nothing useful')\n"
    )
    assert init_run(silent_score) == 0
    assert run_cli(run_args(silent_score, script)) == 2
    assert "no metric" in capsys.readouterr().err


def test_ctrl_c_during_the_baseline_exits_cleanly_and_records_nothing(tmp_path, monkeypatch, capsys):
    """AC-ENG-051f: Ctrl-C before the baseline exists must not print a traceback
    or leave half a baseline behind. A stop event without a baseline would make
    the ledger unreplayable, so an interrupted baseline appends nothing at all
    and the next invocation simply measures again."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, NO_CHANGE)
    assert init_run(repo) == 0

    from autoresearch import measure as measure_mod

    def interrupted(cfg):
        raise KeyboardInterrupt

    monkeypatch.setattr(measure_mod, "measure", interrupted)
    capsys.readouterr()

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "interrupted" in captured.out
    assert read_events(repo) == []
    assert not (repo / ".autoresearch" / "events.jsonl").exists()
    assert git(repo, "status", "--porcelain").stdout == ""


# ─── keep / discard ──────────────────────────────────────────────────────────


def test_keeps_accumulate_until_the_target(tmp_path):
    """AC-ENG-052: each keep moves the incumbent, and reaching the target stops
    the loop with the metric recorded on the final event."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, target=3) == 0

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "6"])) == 0

    assert stop_reason(repo) == "target"
    assert outcomes(repo) == ["keep", "keep", "keep", "keep"]
    assert value(repo) == 2
    trials = [e for e in read_events(repo) if e.get("type") == "trial"]
    assert [t["metric"] for t in trials] == [8.0, 6.0, 4.0, 2.0]
    assert head(repo) == trials[-1]["commit"]
    # every keep has its identity recorded by the engine, not the operator
    assert git(repo, "log", "-1", "--format=%an <%ae>").stdout.strip() == (
        "autoresearch <autoresearch@localhost>"
    )
    assert git(repo, "status", "--porcelain").stdout == ""


def test_worse_candidate_is_discarded_and_history_is_unchanged(tmp_path):
    """AC-ENG-053: a discard leaves no commit behind — that is the whole point of
    the script owning git."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, INCREMENT)
    assert init_run(repo) == 0
    before = head(repo)
    commits = commit_count(repo)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    assert outcomes(repo) == ["discard"]
    assert head(repo) == before
    assert commit_count(repo) == commits
    assert value(repo) == 10
    trial = [e for e in read_events(repo) if e.get("type") == "trial"][0]
    assert trial["metric"] == 11.0        # the candidate's own measurement is kept
    assert trial["guard"] == "pass"


def test_no_change_is_its_own_outcome(tmp_path):
    """AC-ENG-054: an agent that touched nothing did not fail — it also did not
    earn a commit."""
    repo = make_target(tmp_path)
    script = write_agent(tmp_path, NO_CHANGE)
    assert init_run(repo) == 0
    commits = commit_count(repo)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "2"])) == 0

    assert outcomes(repo) == ["no_change", "no_change"]
    assert stop_reason(repo) == "max_iterations"
    assert commit_count(repo) == commits


# ─── the prompt the agent actually receives ──────────────────────────────────


def _capture_prompts(monkeypatch):
    """Record every prompt handed to the adapter, in iteration order."""
    from autoresearch import adapters as adapters_mod

    prompts = []
    original = adapters_mod.Adapter.run

    def spy(self, prompt, repo_path, timeout, iteration=1):
        prompts.append(prompt)
        return original(self, prompt, repo_path, timeout, iteration=iteration)

    monkeypatch.setattr(adapters_mod.Adapter, "run", spy)
    return prompts


def test_a_guard_failure_tail_reaches_the_next_prompt(tmp_path, monkeypatch):
    """AC-ENG-077: a guard failure is only useful if the agent is told what it
    was — the guard's output therefore rides into the next prompt."""
    repo = make_target(tmp_path)
    script = write_agent(tmp_path, GUARD_BREAK)
    assert init_run(repo) == 0
    prompts = _capture_prompts(monkeypatch)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "2"])) == 0

    assert len(prompts) == 2
    assert "Last failure" not in prompts[0]
    assert "## Last failure (tail)" in prompts[1]
    assert "guard exit 1" in prompts[1]


def test_a_crash_tail_reaches_the_next_prompt(tmp_path, monkeypatch):
    """AC-ENG-078: same for a verify that died — the traceback is the only clue."""
    repo = make_target(tmp_path, value=5, score_body=SCORE_DIVIDES)
    script = write_agent(
        tmp_path,
        "import pathlib, sys\n"
        "path = pathlib.Path(sys.argv[1]) / 'src' / 'value.txt'\n"
        "path.write_text('0')\n"
        "print('CHANGE: zero the value')\n",
    )
    assert init_run(repo) == 0
    prompts = _capture_prompts(monkeypatch)

    assert run_cli(
        run_args(repo, script, extra=["--max-iterations", "2", "--max-crashes", "9"])
    ) == 0

    assert len(prompts) == 2
    assert "Last failure" not in prompts[0]
    assert "ZeroDivisionError" in prompts[1].split("## Last failure (tail)")[1]


def test_an_agent_error_tail_reaches_the_next_prompt(tmp_path, monkeypatch):
    """AC-ENG-079: an agent that died has its own output carried forward."""
    repo = make_target(tmp_path)
    script = write_agent(
        tmp_path,
        "import sys\nprint('BOOM: the agent gave up', file=sys.stderr)\nsys.exit(1)\n",
    )
    assert init_run(repo) == 0
    prompts = _capture_prompts(monkeypatch)

    assert run_cli(
        run_args(repo, script, extra=["--max-iterations", "2", "--max-crashes", "9"])
    ) == 0

    assert len(prompts) == 2
    assert "Last failure" not in prompts[0]
    assert "BOOM: the agent gave up" in prompts[1].split("## Last failure (tail)")[1]


# ─── violations and failures ─────────────────────────────────────────────────


def test_scope_violation_is_reverted_and_recorded(tmp_path, capsys):
    """AC-ENG-055: an edit outside the scope is reverted whole — including the
    untracked file the agent created outside it."""
    repo = make_target(tmp_path)
    script = write_agent(tmp_path, OUTSIDE_SCOPE)
    assert init_run(repo) == 0
    before = head(repo)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "2"])) == 0

    assert outcomes(repo) == ["scope_violation", "scope_violation"]
    assert head(repo) == before
    assert value(repo) == 10
    assert not (repo / "notes.txt").exists()
    trial = [e for e in read_events(repo) if e.get("type") == "trial"][0]
    assert "notes.txt" in trial["paths"]
    assert git(repo, "status", "--porcelain").stdout == ""


def test_protected_violation_is_reverted_and_recorded(tmp_path):
    """AC-ENG-056: the files that define the measurement cannot be edited by the
    thing being measured. A protected file *inside* the scope is what separates
    this from a plain scope violation (the scope check runs first, so editing
    ``score.py`` at the repo root is already rejected as ``scope_violation``)."""
    repo = make_target(tmp_path)
    original = (repo / "src" / "value.txt").read_text()
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, extra=["--protect", "src/value.txt"]) == 0
    before = head(repo)
    assert set(config_mod.load(repo).protected) == {
        "score.py", "guard.py", "src/value.txt",
    }

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "2"])) == 0

    assert outcomes(repo) == ["protected_violation", "protected_violation"]
    assert head(repo) == before
    assert (repo / "src" / "value.txt").read_text() == original
    trial = [e for e in read_events(repo) if e.get("type") == "trial"][0]
    assert trial["paths"] == ["src/value.txt"]


FAIL_OUTSIDE = '''
import pathlib, sys

repo = pathlib.Path(sys.argv[1])
(repo / "src" / "value.txt").write_text("8")
(repo / "notes.txt").write_text("out of scope\\\\n")
(repo / "docs").mkdir(exist_ok=True)
(repo / "docs" / "plan.md").write_text("left behind\\\\n")
print("CHANGE: edit and then fail")
sys.exit(1)
'''


def test_agent_error_removes_untracked_files_outside_the_scope(tmp_path):
    """AC-ENG-055b: an agent that dies still leaves its files behind. Every
    non-keep reset must clean them, or the next run refuses to start because
    the tree it inherits is dirty."""
    repo = make_target(tmp_path)
    script = write_agent(tmp_path, FAIL_OUTSIDE)
    assert init_run(repo) == 0
    before = head(repo)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "2"])) == 0

    assert outcomes(repo) == ["agent_error", "agent_error"]
    assert head(repo) == before
    assert value(repo) == 10
    assert not (repo / "notes.txt").exists()
    assert not (repo / "docs" / "plan.md").exists()
    assert git(repo, "status", "--porcelain").stdout == ""

    # and a following run proceeds instead of exiting 2 on a dirty tree
    # (--max-iterations bounds the whole run, so it must cover the two failures)
    fixed = write_agent(tmp_path, DECREMENT.format(step=2), name="fixed.py")
    assert run_cli(run_args(repo, fixed, extra=["--max-iterations", "3"])) == 0
    assert outcomes(repo)[-1] == "keep"


def test_guard_failure_reverts_the_candidate(tmp_path):
    """AC-ENG-057: a candidate that breaks behaviour never gets a score, even if
    its metric would have looked good."""
    repo = make_target(tmp_path)
    script = write_agent(tmp_path, GUARD_BREAK)
    assert init_run(repo) == 0
    before = head(repo)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    assert outcomes(repo) == ["guard_failed"]
    trial = [e for e in read_events(repo) if e.get("type") == "trial"][0]
    assert trial["guard"] == "fail"
    assert trial["metric"] is None
    assert head(repo) == before
    assert value(repo) == 10
    assert "guard exit" in Path(repo, ".autoresearch", "last_agent.log").read_text() \
        or (repo / ".autoresearch" / "last_agent.log").exists()


def test_crashes_stop_the_run_after_max_crashes(tmp_path):
    """AC-ENG-058: a verify that cannot produce a number is a crash, and repeated
    crashes are bounded instead of burning the whole budget."""
    repo = make_target(tmp_path, value=5, score_body=SCORE_DIVIDES)
    script = write_agent(
        tmp_path,
        "import pathlib, sys\n"
        "path = pathlib.Path(sys.argv[1]) / 'src' / 'value.txt'\n"
        "path.write_text('0')\n"
        "print('CHANGE: zero the value')\n",
    )
    assert init_run(repo) == 0
    before = head(repo)

    assert run_cli(
        run_args(repo, script, extra=["--max-iterations", "9", "--max-crashes", "2"])
    ) == 0

    assert outcomes(repo) == ["crash", "crash"]
    assert stop_reason(repo) == "max_crashes"
    assert head(repo) == before
    assert value(repo) == 5


def test_plateau_stops_after_consecutive_non_keeps(tmp_path):
    """AC-ENG-059: K non-keeps in a row means the agent is out of ideas."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, INCREMENT)
    assert init_run(repo) == 0

    assert run_cli(
        run_args(repo, script, extra=["--max-iterations", "9", "--plateau", "2"])
    ) == 0

    assert stop_reason(repo) == "plateau"
    assert outcomes(repo) == ["discard", "discard"]
    assert value(repo) == 10


# ─── resumption and safety ───────────────────────────────────────────────────


def test_resume_continues_from_the_incumbent(tmp_path, capsys):
    """AC-ENG-059b: a second invocation picks up the iteration counter and the
    incumbent instead of starting over or resetting silently."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, target=3) == 0

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "2"])) == 0
    assert stop_reason(repo) == "max_iterations"
    assert value(repo) == 6
    capsys.readouterr()

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "4"])) == 0
    assert stop_reason(repo) == "target"
    assert [t["iteration"] for t in read_events(repo) if t.get("type") == "trial"] == [
        1, 2, 3, 4,
    ]
    assert value(repo) == 2

    # The resumed ledger still replays: the stop that ended the first
    # invocation was superseded by a resume event, not duplicated.
    assert "resume:" in capsys.readouterr().out
    assert ledger_mod.validate(read_events(repo)) == []
    assert run_cli(["status", "--repo", str(repo)]) == 0
    assert "ledger: valid" in capsys.readouterr().out


def test_resume_after_a_stop_records_one_stop_per_segment(tmp_path, capsys):
    """AC-ENG-059g: a resume appends a ``resume`` event, so the ledger keeps at
    most one stop per segment instead of gaining a second final stop."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, target=3) == 0

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0
    assert stop_reason(repo) == "max_iterations"
    capsys.readouterr()

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "4"])) == 0

    events = read_events(repo)
    assert [e["type"] for e in events] == [
        "baseline", "trial", "stop", "resume", "trial", "trial", "trial", "stop",
    ]
    stops = [e for e in events if e.get("type") == "stop"]
    assert [s["reason"] for s in stops] == ["max_iterations", "target"]
    assert ledger_mod.validate(events) == []
    assert run_cli(["status", "--repo", str(repo)]) == 0
    assert "ledger: valid" in capsys.readouterr().out


def test_resume_refuses_when_head_is_not_the_incumbent(tmp_path, capsys):
    """AC-ENG-059c: the engine will not guess which commit is the incumbent, and
    it will not reset work it did not make."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=1))
    assert init_run(repo) == 0
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0
    kept = head(repo)

    git(repo, "commit", "--allow-empty", "-m", "operator work")

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "2"])) == 2
    err = capsys.readouterr().err
    assert "incumbent" in err
    assert head(repo) != kept  # nothing was reset


def test_resume_refuses_a_dirty_tree(tmp_path, capsys):
    """AC-ENG-059d: an uncommitted operator change would be swept into the next
    candidate commit, so the run refuses to start."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=1))
    assert init_run(repo) == 0
    (repo / "src" / "value.txt").write_text("99\n")

    assert run_cli(run_args(repo, script)) == 2
    assert "not clean" in capsys.readouterr().err


def test_json_output_is_one_object_per_event(tmp_path, capsys):
    """AC-ENG-059e: --json is machine-readable event output, not a summary."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, target=8) == 0
    capsys.readouterr()  # drop init's own banner

    assert run_cli(run_args(repo, script, extra=["--json", "--max-iterations", "3"])) == 0

    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    parsed = [json.loads(line) for line in lines]
    assert [e["type"] for e in parsed] == ["baseline", "trial", "stop"]
    assert parsed[-1]["reason"] == "target"
    assert all("seq" in e and "ts" in e for e in parsed)


def test_tampered_ledger_stops_the_run(tmp_path, capsys):
    """AC-ENG-059f: a run whose own history does not replay cannot continue."""
    repo = make_target(tmp_path, value=10)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo) == 0
    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    path = repo / ".autoresearch" / "events.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    events[-1]["seq"] = 99
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "2"])) == 3
    assert "ledger invalid" in capsys.readouterr().err


# ─── the revert must leave nothing behind (AC-ENG-057b/c, 058b) ──────────────

SYMLINK_ESCAPE = '''
import os, pathlib, sys

repo = pathlib.Path(sys.argv[1])
(repo / "src" / "value.txt").write_text("8")
os.symlink(sys.argv[2], repo / "escape")
print("CHANGE: link to a file outside the repo")
'''

IGNORED_WRITE = '''
import pathlib, sys

repo = pathlib.Path(sys.argv[1])
(repo / "src" / "cache.tmp").write_text("poisoned cache\\n")
(repo / "src" / "fresh.tmp").write_text("brand new\\n")
print("CHANGE: write ignored artifacts")
'''

NOISY_AGENT = '''
import sys

sys.stdout.write("x" * 60000 + "\\n")
print("CHANGE: noisy but harmless")
'''

SCORE_WRITES_ARTIFACT = '''"""The measurement, plus the artifact verify leaves behind each run."""
import json, pathlib

value = int(pathlib.Path("src/value.txt").read_text().strip())
pathlib.Path("results.json").write_text(json.dumps({"value": value}) + "\\n")
print(f"METRIC value={value}")
'''


def test_a_symlink_pointing_outside_the_repo_is_removed_on_revert(tmp_path):
    """AC-ENG-057b: ``resolve()`` follows the link, so the revert skipped a
    symlink aimed outside the repo — the link survived, ``git status`` stayed
    dirty and every later invocation refused to start."""
    import os

    repo = make_target(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("precious\n", encoding="utf-8")
    script = write_agent(tmp_path, SYMLINK_ESCAPE)
    assert init_run(repo) == 0
    before = head(repo)

    assert run_cli(
        run_args(
            repo,
            script,
            extra=["--max-iterations", "1", "--agent-arg", str(outside)],
        )
    ) == 0

    assert outcomes(repo) == ["scope_violation"]
    assert not os.path.lexists(repo / "escape")
    assert outside.read_text() == "precious\n"      # the target is untouched
    assert head(repo) == before
    assert git(repo, "status", "--porcelain").stdout == ""

    # And the next invocation is not blocked by the leftover link. (Iteration 2
    # is the next one, so the bound has to allow it.)
    assert run_cli(
        run_args(
            repo,
            script,
            extra=["--max-iterations", "2", "--agent-arg", str(outside)],
        )
    ) == 0
    assert outcomes(repo) == ["scope_violation", "scope_violation"]


def test_a_changed_gitignored_file_inside_the_scope_is_a_violation(tmp_path):
    """AC-ENG-057c: the scope is a promise about the whole tree, and an ignored
    file inside it is invisible to ``git status`` — so a write to one used to be
    reported as ``no_change`` and left in place unguarded."""
    repo = make_target(tmp_path)
    (repo / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    (repo / "src" / "cache.tmp").write_text("cached\n", encoding="utf-8")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-m", "ignore scratch files")

    script = write_agent(tmp_path, IGNORED_WRITE)
    assert init_run(repo) == 0
    before = head(repo)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    assert outcomes(repo) == ["scope_violation"]
    trial = [e for e in read_events(repo) if e.get("type") == "trial"][0]
    assert trial["reason"] == "ignored file changed"
    assert "src/cache.tmp" in trial["paths"]
    assert "src/fresh.tmp" in trial["paths"]

    # The file the agent created is gone; the one that predates the run stays.
    assert not (repo / "src" / "fresh.tmp").exists()
    assert (repo / "src" / "cache.tmp").exists()
    assert head(repo) == before


def test_verify_artifacts_are_not_attributed_to_the_agent(tmp_path):
    """AC-ENG-058b: a verify that writes ``results.json`` is not an agent edit.
    The next iteration used to see it as a change outside the scope and reject
    every candidate, so a run could never keep a second improvement."""
    repo = make_target(tmp_path, value=10, score_body=SCORE_WRITES_ARTIFACT)
    script = write_agent(tmp_path, DECREMENT.format(step=2))
    assert init_run(repo, target=3) == 0

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "4"])) == 0

    assert outcomes(repo) == ["keep", "keep", "keep", "keep"]
    assert value(repo) == 2
    assert not (repo / "results.json").exists()
    assert git(repo, "status", "--porcelain").stdout == ""


def test_the_stored_log_tail_is_capped(tmp_path):
    """AC-ENG-059c: the tail is persisted to the ledger and last_agent.log, so it
    is capped — an agent that prints a megabyte must not grow events.jsonl by a
    megabyte per iteration."""
    repo = make_target(tmp_path)
    script = write_agent(tmp_path, NOISY_AGENT)
    assert init_run(repo) == 0

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0

    trial = [e for e in read_events(repo) if e.get("type") == "trial"][0]
    assert trial["log_tail"].startswith("x")
    assert len(trial["log_tail"]) <= 4000
    stored = (repo / ".autoresearch" / "last_agent.log").read_text(encoding="utf-8")
    assert len(stored) <= 4001


def test_a_second_run_refuses_the_state_lock(tmp_path, capsys):
    """AC-ENG-059b: two runs on one repo would interleave commits and resets, so
    the second one exits 2 instead of corrupting the first."""
    import fcntl

    repo = make_target(tmp_path)
    script = write_agent(tmp_path, NO_CHANGE)
    assert init_run(repo) == 0
    lock_path = repo / ".autoresearch" / "lock"

    with open(lock_path, "a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            assert run_cli(
                run_args(repo, script, extra=["--max-iterations", "1"])
            ) == 2
            assert "lock" in capsys.readouterr().err
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)

    assert run_cli(run_args(repo, script, extra=["--max-iterations", "1"])) == 0
    assert outcomes(repo) == ["no_change"]


def test_run_rejects_non_finite_limits(tmp_path, capsys):
    """AC-ENG-059d: an infinite agent timeout is no timeout at all."""
    repo = make_target(tmp_path)
    script = write_agent(tmp_path, NO_CHANGE)
    assert init_run(repo) == 0

    for extra in (["--agent-timeout", "nan"], ["--max-wall", "inf"]):
        assert run_cli(run_args(repo, script, extra=extra)) == 2, extra
        assert "finite" in capsys.readouterr().err
    assert outcomes(repo) == []
