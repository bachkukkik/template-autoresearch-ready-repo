<!-- PR template (AC-QC-005). Advisory: routes the author and the checklist, does not gate (docs/prd/16). -->

## Summary / Scope

<!-- What changes, and what is deliberately out of scope. -->

## Files touched

<!-- The paths, and which document-funnel stage each belongs to (AGENTS.md §Document Funnel). -->

## Test evidence

<!-- The command you ran and its result — files and commands, not adjectives. -->
- Command:
- Result:

## Checklist

- [ ] CI is green (unit + integration + e2e + secret-scan + doctrine + ops-drift + zizmor + qc-gate)
- [ ] No secrets committed (only `.example` shapes; see AGENTS.md §Security)
- [ ] Document funnel followed (AGENTS.md §Document Funnel) — no stray `.md` at root
- [ ] Docs and tests updated to match the change

## AI-assistance disclosure

- [ ] This PR was authored with AI assistance (agent name)
