# 13 — Output-Medium Doctrine

## What

The output-medium doctrine is Standing Order 7 in `AGENTS.md`. An agent must consume or
produce explanatory output at the richest useful rung of a five-rung ladder: prose →
controlled English (ASD-STE100-style) → diagram → HTML page → explainer video. Each rung
is code or text. A program renders it. A program parses it to verify it — never the
agent's eyes.

## Why

- Prose is the default medium. A richer rung carries the reader's understanding better.
  The cost is build effort, so the rung is a per-task choice, not a default.
- A non-visual engine cannot answer "did it render?" unless each rung is code/text that
  a program renders and a program parses.
- The doctrine spans three funnel layers — the instruction file, stage-2 raw knowledge
  and stage-3 confirmed knowledge. Drift in one layer is invisible without a tripwire.
- `AGENTS.md` is auto-loaded under a 20,000-character cap, so the order stays
  pointer-based: one line per rule plus a pointer to the detail.

## How

### The ladder

Each rung is richer than the one below it. Escalation is per task.

| # | Rung | Grounding |
|---|------|-----------|
| 1 | Prose | the source's default medium |
| 2 | Controlled English (ASD-STE100-style) | the source; sentence ≤ 20 words procedural, ≤ 25 descriptive, noun cluster ≤ 3 |
| 3 | Diagram / image | the source — easier to process and parse |
| 4 | HTML web page | the source — interactive |
| 5 | Explainer video | the source — the format the author is most bullish on |

### Where the doctrine lives

| Funnel stage | Path | Role |
|---|---|---|
| 6 — instruction file | `AGENTS.md` § *7. Output-Medium Escalation* (line 243) | the pointer-based standing order |
| 4 — intent | `docs/prd/13-output-medium-doctrine.md` | SC list, test mapping, CI gate |
| 2 — raw knowledge | `kb/raw/articles/karpathy-output-medium-escalation.md` | verbatim source post, body sha256 recorded |
| 3 — confirmed knowledge | `kb/concepts/output-medium-escalation.md` | ladder, meta-thesis, code-first constraint |
| guard | `tests/unit/test_output_medium_doctrine.py` | AC-OM-001..003 |
| guard | `tests/unit/test_agents_md_budget.py` | AC-CTX-001..004 |

### Code-first render → parse

The load-bearing constraint is that every rung is code or text, verified by parse. This
is this repo's reading, not a claim in the source post (`[ASSUMPTION]`, PRD *Assumptions*).
A model authors an artifact. A program — not the model's eyes — decides whether the
artifact is correct. SVG/DOM structure, pixel buffers and `ffprobe` are the parse targets
that make the ladder usable to a non-visual engine.

### The tripwires

| ID | Asserts |
|----|---------|
| AC-CTX-001 | `AGENTS.md` is under the 20,000-character cap, in characters and bytes |
| AC-CTX-002 | `AGENTS.md` fits the host-pinned cap (`AGENTS_MD_CAP_CHARS`) |
| AC-CTX-003 | `AGENTS.md` keeps at least 500 characters of headroom |
| AC-CTX-004 | the harness entry-point symlinks resolve to `AGENTS.md` |
| AC-OM-001 | the `### 7. Output-Medium Escalation` heading exists and its body names every rung, the `render → parse` rule, the `discardable` rule and the funnel-rule-6 pointer |
| AC-OM-002 | the raw source body's sha256 equals its frontmatter `sha256` |
| AC-OM-003 | the concept page cites the raw source and is indexed in `kb/index.md` |

All are unit-tier and hermetic — a file read and the stdlib only, no subprocess and no
transport.

## Verification

Run from the repo root, 2026-10-03.

```bash
python3 -m pytest tests/unit/test_output_medium_doctrine.py tests/unit/test_agents_md_budget.py -q
# -> 7 passed
python3 -m pytest tests/unit -q
# -> 135 passed
bash tests/run.sh
# -> unit 135 passed / integration 16 passed / e2e SKIPPED / RESULT: PASSED
python3 scripts/audit-ste.py ; echo "exit=$?"
# -> exit=0
LC_ALL=C.UTF-8 wc -m AGENTS.md
# -> 19464 AGENTS.md
wc -c AGENTS.md
# -> 19697 AGENTS.md
grep -n '^### 7\. Output-Medium Escalation' AGENTS.md
# -> 243:### 7. Output-Medium Escalation
python3 - <<'PY'
import hashlib
from pathlib import Path
t = Path("kb/raw/articles/karpathy-output-medium-escalation.md").read_text(encoding="utf-8")
body = t[t.index("\n---", 3) + 4:].strip()
print(hashlib.sha256(body.encode("utf-8")).hexdigest())
PY
# -> 6d68f2ffa96b5221c566bc3ba861131792a0241f700d34f94ba89fe08aa696e6
```

Expected: `7 passed`; `135 passed`; `RESULT: PASSED` with the e2e tier skipped by default;
`19464` characters and `19697` bytes; the heading at line 243; the hash equal to the
frontmatter `sha256`.

## What Works

- `AGENTS.md` carries the `### 7. Output-Medium Escalation` standing order at line 243.
  Its body names all five rungs, the `render → parse` rule, the `discardable` rule and the
  `(funnel rule 6)` pointer — AC-OM-001 passes.
- `AGENTS.md` is 19,464 characters / 19,697 bytes against the 20,000-character cap, with
  536 characters of headroom above the AC-CTX-003 floor — AC-CTX-001 and AC-CTX-003 pass.
- The raw source body sha256 (`6d68f2ff…`) equals its frontmatter `sha256` under this
  repo's `body.strip()` convention — AC-OM-002 passes.
- The concept page cites `raw/articles/karpathy-output-medium-escalation.md` and appears in
  `kb/index.md` under both Concepts and Raw Sources — AC-OM-003 passes.
- The full default suite is green: 135 unit tests and 16 integration tests,
  `RESULT: PASSED`.
- The four harness entry-point symlinks resolve, and `scripts/audit-ste.py` over this
  repo's own docs exits 0.

## What Fails

- **AC-OM-001 is a token tripwire, not a semantic one.** It asserts the literal tokens
  `prose`, `diagram`, `html`, `explainer video`, `controlled English`/`ASD-STE100`,
  `render → parse`, `discardable` and `funnel rule 6`. A §7 rewrite that keeps the rule's
  meaning but changes its wording turns red.
- **The raw-hash convention differs from upstream.** Upstream's tripwire hashes
  `body.lstrip("\n")`; this repo's AC-EXC-002 hashes `body.strip()`. The ported test was
  adapted to this repo, so the two test files are not byte-identical.
- **The upper rungs are unverified here.** No `simple-english`, `diagrams`, `render-verify`
  or `explainer-video` output is produced or parsed in this template's CI.

## Resolution

- **Token tripwire:** when rewriting §7, keep the literal tokens AC-OM-001 names, or
  update the test in the same change — the tripwire and the standing order move together.
- **Hash convention:** the ingest stamp is finalized to this repo's `body.strip()`
  convention, and upstream keeps its own. Neither convention is "the" convention; each
  repo's guard is the contract.
- **Unverified upper rungs:** the doctrine is a standing order for consumers, not a built
  pipeline. A consuming repo adds render → parse tests where it actually produces a rung.

## Verdict

**works** — The order ships inside the cap at 536 characters of headroom, the three
AC-OM tripwires and the four AC-CTX guards are green, the raw and concept layers
round-trip, and the full default suite passes. The recorded limits are token-level
anchoring (a tripwire property, not a defect), the deliberate hash-convention divergence
from upstream, and the fact that the upper rungs are a standing order rather than a
verified pipeline in this repo.
