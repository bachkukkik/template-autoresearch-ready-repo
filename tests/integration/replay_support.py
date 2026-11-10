"""A real replay patch for the integration tier's ``run_*`` cases (AC-SVC-201/202).

The service provisions each job from ``autoresearch/contract/``, so the patch must
apply to exactly that content. It is generated with ``git diff`` against a
temporary copy, which is also how a recorded run is produced — a hand-written
hunk with line numbers would rot the moment ``train.py`` gained a line.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "autoresearch" / "contract"


def replay_records(count: int = 2) -> list:
    """Return ``count`` replay records whose patch edits ``train.py``."""
    work = Path(tempfile.mkdtemp(prefix="ar-integration-patch-"))
    for name in ("prepare.py", "train.py", "program.md"):
        shutil.copy2(CONTRACT / name, work / name)

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        ).stdout

    git("init", "-b", "main")
    git("add", "-A")
    git(
        "-c",
        "user.name=integration",
        "-c",
        "user.email=integration@localhost",
        "commit",
        "--no-verify",
        "-m",
        "baseline",
    )
    source = (work / "train.py").read_text(encoding="utf-8")
    (work / "train.py").write_text(
        source.replace("STEP_WINDOW = 256", "STEP_WINDOW = 64"), encoding="utf-8"
    )
    patch = git("diff")
    if not patch.strip():
        raise AssertionError("the generated replay patch is empty")
    return [
        {"iteration": iteration, "description": f"window {iteration}", "patch": patch}
        for iteration in range(1, count + 1)
    ]
