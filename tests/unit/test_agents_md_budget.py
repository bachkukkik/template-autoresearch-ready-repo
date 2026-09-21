"""Unit tier — the context-file budget tripwire for AGENTS.md. IDs: AC-CTX-001..002.

Hermetic: file reads and the stdlib only — no subprocess, no service import, no
transport. The subject is a tracked document, not the example service.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = REPO_ROOT / "AGENTS.md"

# Every harness auto-loads an agent instruction file (AGENTS.md, CLAUDE.md, .hermes.md,
# .cursorrules, SOUL.md) into each prompt and SILENTLY truncates one that exceeds the
# context-file cap. CONTEXT_FILE_MAX_CHARS = 20_000 in agent/prompt_builder.py is the flat
# floor of a dynamic cap (context_length x 4 x 0.06, clamped 20,000-500,000) and is the
# value that applies whenever the model window is not threaded through — i.e. most of the
# time. Overflow is lossy in the MIDDLE: `_truncate_content()` keeps
# int(cap * 0.7) chars of the head and int(cap * 0.2) of the tail and drops everything
# between, so position, not importance, decides what the agent sees.
#
# It is a CHARACTERS rule — measure with len() / `LC_ALL=C.UTF-8 wc -m`. A bare `wc -m`
# is a BYTE count on a host with LC_CTYPE=C (as this container sets), so the file is
# measured in Python here and the byte reading is asserted too: a reviewer checking
# `ls -l` must not see an over-cap number either.
CONTEXT_FILE_MAX_CHARS = 20_000

# The instruction-file symlinks every harness reads instead of a forked copy. The
# remaining harness entry points (.claude/skills, .claude/plugins) point at the skill
# tree, not at AGENTS.md, and are covered by AC-FUN-004.
ENTRY_SYMLINKS = ("CLAUDE.md", ".github/copilot-instructions.md")

REMEDY = (
    "Remedy: trim AGENTS.md back under the cap (collapse a rule to one line plus a "
    "pointer to where its detail already lives rather than deleting it — see "
    "docs/09-agents-md-context-budget.md), pin a larger context_file_max_chars on the "
    "host, or use a larger-context model."
)


def test_agents_md_fits_context_file_cap():
    """AC-CTX-001: AGENTS.md is under the harness context-file cap, in characters."""
    text = AGENTS_MD.read_text(encoding="utf-8")
    n_chars = len(text)
    n_bytes = len(text.encode("utf-8"))
    assert n_chars < CONTEXT_FILE_MAX_CHARS, (
        f"AGENTS.md is {n_chars} chars ({n_bytes} bytes), over the "
        f"{CONTEXT_FILE_MAX_CHARS}-char context-file cap. Every harness loads this file into "
        "each prompt and truncates an oversized one SILENTLY: the head 70% and the tail 20% "
        "of the cap survive and the MIDDLE is dropped, so whole sections vanish with no "
        f"signal at task time. {REMEDY}"
    )
    assert n_bytes < CONTEXT_FILE_MAX_CHARS, (
        f"AGENTS.md is {n_chars} chars but {n_bytes} bytes, over the "
        f"{CONTEXT_FILE_MAX_CHARS}-char context-file cap when read as bytes. The cap is a "
        "CHARACTERS rule, but a reviewer checking `ls -l` / `wc -c` — or `wc -m` on a host "
        f"with LC_CTYPE=C — sees this number. {REMEDY}"
    )


def test_harness_entry_symlinks_resolve_to_agents_md():
    """AC-CTX-002: every harness entry-point instruction symlink still resolves to
    AGENTS.md and is the same file, so the trim cannot fork the doctrine."""
    agents_text = AGENTS_MD.read_text(encoding="utf-8")
    for rel in ENTRY_SYMLINKS:
        path = REPO_ROOT / rel
        assert os.path.islink(path), (
            f"{rel} is not a symlink. It must point at AGENTS.md — a plain copy forks the "
            "doctrine and every harness then reads a different file (see "
            "docs/09-agents-md-context-budget.md and AC-FUN-004)."
        )
        assert os.path.exists(path), (
            f"{rel} is a dangling symlink — its target does not exist, so that harness "
            "reads no instruction file at all."
        )
        assert path.resolve() == AGENTS_MD.resolve(), (
            f"{rel} resolves to {path.resolve()}, not to {AGENTS_MD} — the harness reading "
            "it gets a different document from the one the context-file cap is measured on."
        )
        assert path.read_text(encoding="utf-8") == agents_text, (
            f"{rel} resolves to AGENTS.md but does not read back the same bytes — the "
            "parent directory is probably on another filesystem, or the symlink family "
            "has drifted."
        )
