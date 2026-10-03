# PRD 13 — Output-Medium Doctrine

> Funnel stage 4 (intent), grounded in `kb/concepts/output-medium-escalation.md`
> (stage 3) and `kb/raw/articles/karpathy-output-medium-escalation.md` (stage 2).
> Claims the raw source does not literally state are `[ASSUMPTION]`-marked.

## Context

`AGENTS.md` is this repo's single agent instruction file every harness symlink resolves
to, and it is delivered whole only while it stays under the harness context-file cap
(20,000 characters). This repo already carries the verified *AGENTS.md context budget*
doctrine (`docs/09-agents-md-context-budget.md`, tripwire
`tests/unit/test_agents_md_budget.py`). This topic adds one standing order to that file:
**output-medium escalation**. The intent is that an agent consuming or producing model
output picks the richest useful rung of the medium ladder — prose → controlled English →
diagram → HTML page → explainer video — always as code/text rendered by a deterministic
program and verified by render → parse, never by looking. The doctrine must be
*pointer-based* so the added characters do not push `AGENTS.md` over the cap.

Grounded source: `kb/concepts/output-medium-escalation.md`; raw provenance
`kb/raw/articles/karpathy-output-medium-escalation.md` (`source_url`
`https://x.com/karpathy/status/2105819303471976479`).

## Success Criteria

- **SC-om-1** — `AGENTS.md` carries an **"Output-Medium Escalation"** standing order
  (numbered §7 in Standing Orders), written pointer-based (one line per rule + a pointer
  to the detail), and `AGENTS.md` remains under the 20,000-character context-file cap.
  _Verify:_ `tests/unit/test_agents_md_budget.py` (AC-CTX-001) — the cap tripwire stays
  green after the standing order is added.

- **SC-om-2** — The standing order exists and its text names the ladder rungs
  (prose → controlled English → diagram → HTML → explainer video), the render → parse
  verification rule, and the discardable-artifact rule.
  _Verify:_ `tests/unit/test_output_medium_doctrine.py` (AC-OM-001).

- **SC-om-3** — The raw source is present in the repo at
  `kb/raw/articles/karpathy-output-medium-escalation.md`, byte-identical to the ingest,
  with the body sha256 matching its frontmatter `sha256`.
  _Verify:_ `tests/unit/test_output_medium_doctrine.py` (AC-OM-002).

- **SC-om-4** — The kb layer-2 concept page `kb/concepts/output-medium-escalation.md`
  exists, is indexed in `kb/index.md` under Concepts and Raw Sources, and cites the raw
  source in its `sources:` frontmatter.
  _Verify:_ `tests/unit/test_output_medium_doctrine.py` (AC-OM-003).

- **SC-om-5** — `AGENTS.md` keeps at least the 500-character headroom floor under the
  effective cap, so accretion fails the tier before the cap is ever crossed.
  _Verify:_ `tests/unit/test_agents_md_budget.py` (AC-CTX-003).

## Test Mapping

| Expected behavior | Test file | Test IDs |
|---|---|---|
| `AGENTS.md` stays under the 20,000-char context-file cap | `tests/unit/test_agents_md_budget.py` | AC-CTX-001 |
| The effective cap honours a host pin and keeps a 500-char headroom floor | `tests/unit/test_agents_md_budget.py` | AC-CTX-002, AC-CTX-003 |
| `AGENTS.md` has the "Output-Medium Escalation" §7 standing order naming the ladder rungs + render → parse + discardable-artifact rule | `tests/unit/test_output_medium_doctrine.py` | AC-OM-001 |
| The raw source exists with matching body sha256 | `tests/unit/test_output_medium_doctrine.py` | AC-OM-002 |
| The kb concept page exists, cites the raw source, and is indexed twice | `tests/unit/test_output_medium_doctrine.py` | AC-OM-003 |

The hundreds digit encodes the tier — `0NN` unit, `1NN` e2e, `2NN` integration
(AGENTS.md §5). All criteria here are unit-tier (a file read + the stdlib, no transport).

## CI/CD Gate

All ACs run in the **unit** job (`python3 -m pytest tests/unit -v` in
`.github/workflows/ci.yml`; locally `act push -j unit` or `bash tests/run.sh`). No PR
merges with a red test. The `AC-CTX-*` tripwires are the cap guards; `AC-OM-001..003`
are the doctrine's own presence/consistency guards.

## Source Attribution

- Concept page — [`kb/concepts/output-medium-escalation.md`](../kb/concepts/output-medium-escalation.md)
  (ladder, meta-thesis, code-first render → parse constraint, six principles).
- Raw source — `kb/raw/articles/karpathy-output-medium-escalation.md`
  (`source_url: https://x.com/karpathy/status/2105819303471976479`, ingested 2026-10-02,
  body sha256 `21961aa850036fc5ca5003bdd655b6cf7a9f5d004ce6f0c51bb29ab686b0785c`).
- Cap doctrine and the `AC-CTX-*` tripwires — `docs/09-agents-md-context-budget.md`.
- Upstream origin — `bachkukkik/template-agentic-ready-repo` (PRD 03, commits #11/#13).

## Assumptions

- [ASSUMPTION] The raw post presents the chemistry ladder as a readability aid; that
  **every rung must be code/text verified by render → parse** is this repo's reading, not
  a claim in the post. The post itself only says HTML and explainer videos are generated
  artifacts the author is bullish on.
- [ASSUMPTION] The "discardable artifact" rule is taken literally from the post's
  "large, custom, discardable software artifacts" phrasing, but applying it as a
  standing order to *this* template repo's agents is an inference.
- [ASSUMPTION] Numbering the standing order exactly "§7" is satisfied by appending it as
  Standing Order 7; existing cross-references (`§5`, `§6`, `§Security`) keep resolving
  after the edit because all trimming was confined to regions below the line-pinned
  guards.
- [ASSUMPTION] The cap margin after adding the order stays positive and above the
  500-char floor by compressing two non-load-bearing sections, each of whose dropped
  facts has a published home (`README.md` § Skills, `ops/README.md`).

## Confidence

**Medium** — single primary source (the Karpathy post) plus this repo's own verified cap
doctrine; the escalation ladder and meta-thesis are directly grounded, the code-first
render → parse constraint and the six-principle framing are repo inference.
