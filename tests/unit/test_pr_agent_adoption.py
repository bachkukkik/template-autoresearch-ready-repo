"""Unit tier — optional PR-Agent adoption. IDs: AC-PRA-0NN.

Hermetic: file reads + the stdlib only — no subprocess, no network, no service
import. The subjects are tracked config files (the workflow, `.env.example`,
`.pr_agent.toml`, `README.md`), not the example service.

This is the machine-checkable half of PRD 18 (docs/prd/18-pr-agent-adoption.md):
the reviewer exists as an opt-in, hardened workflow (AC-PRA-001..004); the
endpoint / key / model surface is customizable and never hardcoded (005, 006);
an agent reading `.env` can detect the feature (007); tuning is one committable
file (008); the instructions surface names it (009).

The workflow is dormant by design — its job gate is false until an adopter sets
the `PR_AGENT_ENABLED` repository variable — so these are structural guards,
not a run.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-agent.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
PR_AGENT_TOML = REPO_ROOT / ".pr_agent.toml"
README = REPO_ROOT / "README.md"
JOB = "pr_agent_job"

# AC-PRA-005: the conventional names an adopter (or agent) already knows. The
# mapping onto PR-Agent's own env lives inside the workflow only, so the surface
# stays recognizable and no PR-Agent-specific knowledge is required to opt in.
SURFACE_NAMES = (
    "secrets.OPENAI_API_KEY",
    "vars.OPENAI_BASE_URL",
    "vars.OPENAI_DEFAULT_MODEL",
)

# AC-PRA-007: the keys the optional `.env.example` block must expose.
ENV_KEYS = ("PR_AGENT_ENABLED", "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_DEFAULT_MODEL")


def _read(path):
    assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"
    return path.read_text(encoding="utf-8")


def _on_block(text):
    """The YAML text of the top-level `on:` block (until the next column-0 key)."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(r"^on:\s*$", line))
    block = []
    for line in lines[start + 1:]:
        if re.match(r"^\S", line):
            break
        block.append(line)
    return "\n".join(block)


def _job_block(text, job):
    """Return the YAML text of one top-level job (2-space indent) in a workflow."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^  {re.escape(job)}:\s*$", line):
            start = i
            break
    assert start is not None, f"job {job!r} not found in workflow"
    block = [lines[start]]
    for line in lines[start + 1:]:
        if re.match(r"^  \S", line):  # next job key at 2-space indent
            break
        block.append(line)
    return "\n".join(block)


def _trigger_types(on_block, trigger):
    """The `types:` list under one trigger in the `on:` block, as a set."""
    section = re.search(rf"^  {trigger}:\s*\n((?:    .*\n?)*)", on_block, re.M)
    assert section, f"trigger {trigger!r} not found in the on: block"
    types = re.search(r"types:\s*\[([^\]]*)\]", section.group(1))
    assert types, f"trigger {trigger!r} declares no `types:` list"
    return {t.strip() for t in types.group(1).split(",") if t.strip()}


# ── AC-PRA-001..004 the opt-in, hardened workflow ─────────────────────────────

def test_ac_pra_001_workflow_triggers_on_pr_events_and_comments():
    on_block = _on_block(_read(WORKFLOW))
    assert _trigger_types(on_block, "pull_request") == {
        "opened", "reopened", "ready_for_review", "synchronize"
    }, (
        "the pull_request trigger must fire on exactly opened, reopened, "
        "ready_for_review and synchronize — the events that open a PR, add commits "
        "to it, or make it reviewable (AC-PRA-001)"
    )
    assert _trigger_types(on_block, "issue_comment") == {"created"}, (
        "issue_comment must fire on `created` only: it carries the on-demand "
        "/review, /describe and /improve commands (AC-PRA-001)"
    )


def test_ac_pra_002_job_is_gated_on_the_opt_in_variable_and_not_a_bot():
    block = _job_block(_read(WORKFLOW), JOB)
    gate = re.search(r"^    if:\s*(.+)$", block, re.M)
    assert gate, "pr_agent_job must carry a job-level `if:` (AC-PRA-002)"
    condition = gate.group(1)
    assert "vars.PR_AGENT_ENABLED == 'true'" in condition, (
        "the job gate must require the PR_AGENT_ENABLED repository variable to be the "
        "string 'true'. A variable, not a secret: job-level `if:` cannot read "
        "`secrets.*` reliably, and the switch is not sensitive (AC-PRA-002)"
    )
    assert "github.event.sender.type != 'Bot'" in condition, (
        "the job gate must exclude bot senders, so a bot's own comment (e.g. this "
        "reviewer's) cannot re-trigger the run in a loop (AC-PRA-002)"
    )
    assert "secrets" not in condition.lower(), (
        "the job gate must not test secrets — the context is unreliable at job "
        "gating time; use the repository variable (AC-PRA-002)"
    )


def test_ac_pra_003_permissions_are_deny_all_then_minimal():
    text = _read(WORKFLOW)
    assert re.search(r"^permissions:\s*\{\}\s*$", text, re.M), (
        "pr-agent.yml must set a deny-all top-level `permissions: {}` at column 0 "
        "(AC-PRA-003 / AC-QC-001)"
    )
    block = _job_block(text, JOB)
    job_perms = re.search(r"^    permissions:\s*\n((?:      .*\n?)+)", block, re.M)
    assert job_perms, "pr_agent_job must declare its own `permissions:` mapping (AC-PRA-003)"
    keys = set(re.findall(r"^\s+([\w-]+):", job_perms.group(1), re.M))
    assert keys == {"contents", "issues", "pull-requests"}, (
        f"pr_agent_job permissions must be exactly contents/issues/pull-requests, got "
        f"{sorted(keys)}. `contents: read` reads the diff, `issues: write` replies on "
        "issue_comment threads and `pull-requests: write` posts reviews — nothing "
        "else is needed, so nothing else is granted (AC-PRA-003)"
    )


def test_ac_pra_004_action_is_sha_pinned_with_a_version_comment():
    text = _read(WORKFLOW)
    refs = re.findall(r"uses:\s*(\S+)", text)
    assert len(refs) == 1, (
        f"pr-agent.yml must carry exactly one `uses:` (the reviewer action), got {refs}"
    )
    ref = refs[0]
    assert ref.startswith("The-PR-Agent/pr-agent@"), (
        f"the reviewer action must be The-PR-Agent/pr-agent, got {ref!r} (AC-PRA-004)"
    )
    _, _, rev = ref.rpartition("@")
    assert re.fullmatch(r"[0-9a-f]{40}", rev), (
        f"{ref!r} is not SHA-pinned. A mutable tag can be re-pointed at attacker "
        "code; pin the full 40-hex commit SHA (AC-PRA-004 / AC-QC-002)"
    )
    line = next(line for line in text.splitlines() if "uses:" in line)
    assert re.search(r"#\s*v\d+\.\d+\.\d+\s*$", line), (
        f"the pinned `uses:` line must carry its release as a `# vX.Y.Z` comment, so "
        f"the pin is readable and updatable: {line.strip()!r} (AC-PRA-004)"
    )


# ── AC-PRA-005, 006 the customizable, never-hardcoded surface ─────────────────

def test_ac_pra_005_conventional_surface_names_are_mapped():
    text = _read(WORKFLOW)
    missing = [name for name in SURFACE_NAMES if name not in text]
    assert not missing, (
        f"the workflow does not reference the conventional names {missing}. The "
        "surface is `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_DEFAULT_MODEL` so "
        "an adopter recognizes it without PR-Agent-specific knowledge (AC-PRA-005)"
    )
    assert re.search(r"^\s+OPENAI_KEY:\s*\$\{\{", text, re.M), (
        "the conventional key must be mapped onto PR-Agent's own env name "
        "`OPENAI_KEY` inside the workflow (AC-PRA-005)"
    )
    assert re.search(r"^\s+OPENAI_API_BASE:\s*\$\{\{", text, re.M), (
        "the conventional base URL must be mapped onto PR-Agent's own env name "
        "`OPENAI_API_BASE` inside the workflow (AC-PRA-005)"
    )


def test_ac_pra_006_no_hardcoded_endpoint_model_or_credential():
    text = _read(WORKFLOW)
    urls = re.findall(r"https?://\S+", text)
    hosts = {url.split("/")[2].rstrip(".,)") for url in urls}
    assert hosts <= {"docs.pr-agent.ai"}, (
        f"the only URLs allowed are documentation links, got {sorted(hosts)}. An "
        "endpoint belongs in the OPENAI_BASE_URL variable, never in the file "
        "(AC-PRA-006)"
    )
    assert "api.openai.com" not in text, (
        "no provider endpoint may be hardcoded — `OPENAI_BASE_URL` exists exactly so "
        "the adopter picks the endpoint (AC-PRA-006)"
    )
    assert "sk-" not in text.lower(), "a credential-shaped literal ('sk-…') is present (AC-PRA-006)"
    literal = re.search(
        r"OPENAI_API_KEY\s*[:=]\s*(?!\$\{\{\s*secrets\.OPENAI_API_KEY\s*\}\})", text
    )
    assert not literal, (
        "OPENAI_API_KEY must only ever appear as the `secrets.OPENAI_API_KEY` "
        "reference, never assigned a value (AC-PRA-006). A credential belongs in repo "
        "secrets, and variable NAMES only in tracked files (AGENTS.md §Security)"
    )


# ── AC-PRA-007..009 the agent- and human-facing surfaces ──────────────────────

def test_ac_pra_007_env_example_documents_the_optional_block():
    text = _read(ENV_EXAMPLE)
    assert re.search(r"^# ─── PR-Agent \(optional\)", text, re.M), (
        ".env.example must carry a `# ─── PR-Agent (optional) ───` section so "
        "`scripts/gen-env.py` copies its comments into `.env` and an agent reading "
        "`.env` sees the feature (AC-PRA-007)"
    )
    values = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2)
    for key in ENV_KEYS:
        assert key in values, f".env.example is missing the `{key}=` line (AC-PRA-007)"
        assert values[key] in ("", "changeme"), (
            f".env.example `{key}` must be a placeholder ('' or 'changeme'), got "
            f"{values[key]!r} — a tracked example never carries a live value "
            "(AC-PRA-007 / AGENTS.md §Security)"
        )


def test_ac_pra_008_tuning_file_is_committable_and_credential_free():
    text = _read(PR_AGENT_TOML)
    assert "https://docs.pr-agent.ai/usage-guide/configuration_options/" in text, (
        ".pr_agent.toml must point at the upstream configuration reference so the "
        "knobs are discoverable (AC-PRA-008)"
    )
    assert "18-pr-agent-adoption" in text or "PRD 18" in text, (
        ".pr_agent.toml must name its intent source (PRD 18) (AC-PRA-008)"
    )
    assert "sk-" not in text.lower(), ".pr_agent.toml contains a credential-shaped literal (AC-PRA-008)"
    uncommented = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    credentialed = re.search(
        r"(?im)^\s*[A-Za-z0-9_.-]*(API_KEY|API_KEY[SZ]|TOKEN|SECRET|_KEY|_KEYS)\s*=",
        uncommented,
    )
    assert not credentialed, (
        f".pr_agent.toml carries a credential-shaped assignment {credentialed.group(0)!r}. "
        "Credentials arrive from the workflow env or the local `.env`; this file is "
        "committed (AC-PRA-008)"
    )


def test_ac_pra_009_readme_documents_the_optional_feature():
    text = _read(README)
    assert re.search(r"^#{1,6} PR-Agent \(optional", text, re.M), (
        "README must carry a `PR-Agent (optional …)` section next to the other "
        "optional tools (AC-PRA-009)"
    )
    assert "18-pr-agent-adoption.md" in text, (
        "the README section must point at its intent source "
        "(docs/prd/18-pr-agent-adoption.md) (AC-PRA-009)"
    )
    missing = [name for name in ENV_KEYS if name not in text]
    assert not missing, (
        f"the README section does not name the opt-in surface {missing} — an adopter "
        "cannot enable the feature from the README alone (AC-PRA-009)"
    )
