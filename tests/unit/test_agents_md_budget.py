"""Unit tier — the repo's own context budget for AGENTS.md. IDs: AC-CTX-001..004.

Hermetic: file reads and the stdlib only — no subprocess, no service import, no
transport. The subject is a tracked document, not the example service.

The budget is a REPO budget, not a universal law. Harnesses that auto-load an agent
instruction file silently truncate one that exceeds their own context-file cap, and
those caps differ: Claude Code, Codex CLI and opencode load `AGENTS.md` with no such
cap (or with a much larger one of their own); Hermes applies a dynamic cap whose flat
floor is 20,000 characters (`CONTEXT_FILE_MAX_CHARS` in `agent/prompt_builder.py`,
`context_length x 4 x 0.06`, clamped 20,000-500,000). This repo targets the TIGHTEST
of those — currently the Hermes 20,000-char floor — so the file it ships is safe under
every harness on its support list.

Three budget guards, in escalating order: AC-CTX-001 the flat-floor budget, AC-CTX-002 the
host-pinned budget override, AC-CTX-003 the headroom floor that fails accretion LOUDLY
before the budget is ever reached. AC-CTX-004 pins the harness entry-point symlinks to the
same file the budget is measured on, so a trim cannot fork the doctrine.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = REPO_ROOT / "AGENTS.md"

# The tightest auto-load cap among the harnesses this template targets. Hermes is the
# binding one: `CONTEXT_FILE_MAX_CHARS = 20_000` in agent/prompt_builder.py is the flat
# floor of a dynamic cap (context_length x 4 x 0.06, clamped 20,000-500,000) and is the
# value that applies whenever the model window is not threaded through — i.e. most of
# the time. Overflow there is lossy in the MIDDLE: `_truncate_content()` keeps
# int(cap * 0.7) chars of the head and int(cap * 0.2) of the tail and drops everything
# between, so position, not importance, decides what the agent sees. The other harnesses
# on the support list (Claude Code, Codex CLI, opencode, Cursor, Aider) load the file
# without that cap, so a file under this budget is under all of them.
#
# It is a CHARACTERS rule — measure with len() / `LC_ALL=C.UTF-8 wc -m`. A bare `wc -m`
# is a BYTE count on a host with LC_CTYPE=C (as this container sets), so the file is
# measured in Python here and the byte reading is asserted too: a reviewer checking
# `ls -l` must not see an over-budget number either.
AGENTS_MD_BUDGET_CHARS = 20_000

# AC-CTX-002: the effective budget is HOST state, not repo state. A host profile may pin a
# LOWER `context_file_max_chars` than the flat floor, and that pin silently truncates a
# file AC-CTX-001 happily passes (docs/09-agents-md-context-budget.md, *What Fails*:
# "the budget is host-dependent"). Honor an explicit override so the lower cap becomes
# visible to CI whenever the host exports it; fall back to the flat floor otherwise.
CAP_ENV_VAR = "AGENTS_MD_CAP_CHARS"

# AC-CTX-003: headroom floor. The budget test only fires once the file has ALREADY crossed
# the budget — by then the middle of the file is gone. Demand a margin, so accretion fails
# the tier while the file still fits; ~500 chars is roughly 15 lines of prose.
HEADROOM_FLOOR_CHARS = 500

# The instruction-file symlinks every harness reads instead of a forked copy. The
# remaining harness entry points (.claude/skills, .claude/plugins) point at the skill
# tree, not at AGENTS.md, and are covered by AC-FUN-004.
ENTRY_SYMLINKS = ("CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md")

REMEDY = (
    "Remedy: trim AGENTS.md back under the budget (collapse a rule to one line plus a "
    "pointer to where its detail already lives rather than deleting it — see "
    "docs/09-agents-md-context-budget.md), pin a larger context_file_max_chars on the "
    "host, or use a larger-context model."
)


def _effective_budget() -> int:
    """Return the repo's AGENTS.md char budget.

    An explicit host pin (`AGENTS_MD_CAP_CHARS`, an integer number of characters) wins;
    absent or empty, the repo targets the flat floor of the tightest harness cap. A
    malformed pin cannot be honored and fails loudly rather than being silently ignored —
    ignoring it would assert a budget the host does not actually apply, which is the exact
    blind spot AC-CTX-002 closes.
    """
    raw = os.environ.get(CAP_ENV_VAR)
    if raw is None or raw.strip() == "":
        return AGENTS_MD_BUDGET_CHARS
    try:
        cap = int(raw)
    except ValueError:
        raise AssertionError(
            f"{CAP_ENV_VAR}={raw!r} is not an integer. The tripwire reads an explicit "
            "host-pinned context-file cap from this env var so a LOWER host limit is "
            "visible to CI (docs/09-agents-md-context-budget.md, *What Fails*: 'the "
            "budget is host-dependent'). A non-numeric value cannot be honored and is "
            "treated as a broken pin, not silently ignored. Remedy: export an integer "
            f"number of CHARACTERS (e.g. {CAP_ENV_VAR}=19800), or unset it to fall back "
            f"to the {AGENTS_MD_BUDGET_CHARS}-char repo budget."
        )
    if cap <= 0:
        raise AssertionError(
            f"{CAP_ENV_VAR}={cap} must be a positive number of characters. A non-positive "
            "cap can never hold any instruction file, so the tripwire cannot infer a "
            "meaningful limit from it. Remedy: export a positive integer "
            f"(e.g. {CAP_ENV_VAR}=19800), or unset it to use the "
            f"{AGENTS_MD_BUDGET_CHARS}-char repo budget."
        )
    return cap


def test_agents_md_fits_context_file_cap():
    """AC-CTX-001: AGENTS.md is under the repo's context budget, in characters."""
    text = AGENTS_MD.read_text(encoding="utf-8")
    n_chars = len(text)
    n_bytes = len(text.encode("utf-8"))
    assert n_chars < AGENTS_MD_BUDGET_CHARS, (
        f"AGENTS.md is {n_chars} chars ({n_bytes} bytes), over the "
        f"{AGENTS_MD_BUDGET_CHARS}-char repo context budget — the tightest auto-load cap "
        "among the harnesses this template targets (Hermes; Claude Code / Codex CLI / "
        "opencode load it uncapped). A harness that auto-loads this file truncates an "
        "oversized one SILENTLY: the head 70% and the tail 20% of the cap survive and the "
        f"MIDDLE is dropped, so whole sections vanish with no signal at task time. {REMEDY}"
    )
    assert n_bytes < AGENTS_MD_BUDGET_CHARS, (
        f"AGENTS.md is {n_chars} chars but {n_bytes} bytes, over the "
        f"{AGENTS_MD_BUDGET_CHARS}-char repo context budget when read as bytes. The budget "
        "is a CHARACTERS rule, but a reviewer checking `ls -l` / `wc -c` — or `wc -m` on "
        f"a host with LC_CTYPE=C — sees this number. {REMEDY}"
    )


def test_agents_md_respects_host_pinned_cap():
    """AC-CTX-002: AGENTS.md fits the EFFECTIVE budget, honoring a host-pinned override."""
    cap = _effective_budget()
    text = AGENTS_MD.read_text(encoding="utf-8")
    n_chars = len(text)
    n_bytes = len(text.encode("utf-8"))
    pinned = os.environ.get(CAP_ENV_VAR)
    source = (
        f"pinned by {CAP_ENV_VAR}={pinned!r}"
        if pinned not in (None, "")
        else f"the repo budget (AGENTS_MD_BUDGET_CHARS); export {CAP_ENV_VAR} to pin a lower host cap"
    )
    assert n_chars < cap, (
        f"AGENTS.md is {n_chars} chars ({n_bytes} bytes), over the effective {cap}-char "
        f"context budget — {source}. The cap is host state, not repo state: a host "
        "profile that pins a lower context_file_max_chars truncates a file that AC-CTX-001 "
        "passes, and the truncation is silent and mid-file (head 70% + tail 20% survive), "
        "so the Standing Orders and Security sections vanish from the prompt with no signal "
        "at task time (docs/09-agents-md-context-budget.md, *What Fails*). Remedy: trim "
        "AGENTS.md under the EFFECTIVE cap — collapse a rule to one line + a pointer to its "
        "detail rather than deleting it — or raise the host pin so it matches the file."
    )


def test_agents_md_keeps_headroom_floor():
    """AC-CTX-003: AGENTS.md keeps >= HEADROOM_FLOOR_CHARS of headroom under the budget."""
    cap = _effective_budget()
    text = AGENTS_MD.read_text(encoding="utf-8")
    n_chars = len(text)
    headroom = cap - n_chars
    assert headroom >= HEADROOM_FLOOR_CHARS, (
        f"AGENTS.md leaves only {headroom} chars of headroom under the effective {cap}-char "
        f"budget ({n_chars} chars used); the floor is {HEADROOM_FLOOR_CHARS} chars. The file "
        "still fits, but AC-CTX-001 only fires once the cap is ALREADY crossed — and an "
        "overshooting file is truncated in the MIDDLE (head 70% + tail 20% survive), so the "
        "growth that re-crosses the cap silently drops whole sections. This floor fails the "
        "tier BEFORE that happens, reserving room for ~15 lines of prose "
        "(docs/09-agents-md-context-budget.md, *What Fails*: 'headroom is thin'). Remedy: do "
        "not append — collapse the new rule to one line + a pointer to where its detail "
        "already lives, per docs/09 *Resolution*."
    )


def test_harness_entry_symlinks_resolve_to_agents_md():
    """AC-CTX-004: every harness entry-point instruction symlink still resolves to
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
            "it gets a different document from the one the context budget is measured on."
        )
        assert path.read_text(encoding="utf-8") == agents_text, (
            f"{rel} resolves to AGENTS.md but does not read back the same bytes — the "
            "parent directory is probably on another filesystem, or the symlink family "
            "has drifted."
        )
