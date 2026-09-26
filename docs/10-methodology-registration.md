# 10 — Methodology Registration

## What

The registration of the autoresearch methodology into the knowledge base: a
deep-research ingest dated 2026-09-26 that adds one raw article, five layer-2
concept pages and two page updates, distilled from `karpathy/autoresearch`
(upstream master, files sha256-verified) and its first real-world instance, the
slash-commerce pipeline. It registers the invariant pattern — three mutability
classes inside one loop — rather than the ML training loop that carries it.

## Why

- The template's contract (`contract/`) and the vendored skill state the loop,
  but nothing in `kb/` grounded *why* the three-role split is the invariant or
  what an instantiation is allowed to change.
- The pattern's portability is a claim until the instance's `contract/` is
  shown byte-identical to this template's — the registration records that proof
  at the source, so an adopter can cite it.
- The optional scaling layers (queue, adversary, optimizer, watchdog) need a
  rule for when each is added and a set of measured failure modes to warn
  about; both are registered here and citable by name from any harness.

## How

### Artifacts written

| Artifact | Path | Role |
|---|---|---|
| Raw ingest | `kb/raw/articles/2026-09-26-autoresearch-methodology-registration.md` | immutable source; sha256 over `body.strip()` (AC-EXC-002) |
| Concept pages (new) | `kb/concepts/methodology-registration.md`, `kanban-factory.md`, `adversarial-optimization-layer.md`, `better-cheaper-faster-metrics.md`, `formal-mapping-autoresearch.md` | layer-2 synthesis of the registered pattern |
| Page updates | `kb/entities/karpathy-autoresearch.md`, `kb/concepts/evaluator-legitimacy.md` | Goodhart-caveat provenance correction; operational answers |
| Catalog | `kb/index.md`, `kb/log.md` | 21 → 26 pages, 15 → 16 raw sources; action log entries |
| Skill | `.agents/skills/autoresearch-methodology/SKILL.md` | vendored instantiation recipe; ingest pointer held repo-relative |

### The distilled pattern

| Mutability class | Owner | Upstream | Instance equivalent | Rule |
|---|---|---|---|---|
| Evaluator (metric, eval inputs, budget) | nobody | `prepare.py` (`evaluate_bpb`, `TIME_BUDGET=300`) | `pipeline/scripts/metrics-contract.py` + policy YAML | import-only; object-identity anti-cheat test in CI |
| Policy (job, rules, simplicity, crash policy) | the human | `program.md` | `program.md` | the only human lever during a run |
| Artifact | the agent | `train.py` | exactly one editable file | the only file the agent may mutate |

Two structural commitments sit beside the split: a **fixed resource budget per
candidate** (iso-compute — no candidate wins by spending more) and an
**append-only keep/discard ledger** (`results.tsv`, untracked) where the metric
is read from the run LOG, never the agent's self-report. The loop is
tune → commit → run → read scalar metric → strict improvement advances the
branch, otherwise `git reset`; the first run is always the baseline.

Evaluator/optimizer separation makes the objective **exogenous**: "make the
metric easier" leaves the action space, and residual risk moves from cheating
(supervisable) to proxy-legitimacy / Goodhart (designable).

### Portability proof

The slash-commerce instance changed the upstream `contract/` by exactly zero
bytes — all three files byte-identical to this template's — and met its
objective by re-instantiating the same shape one layer down in `pipeline/`.
Only the DATA side of an instantiation ever moves (embedded corpus, domain
hooks, `--results` auto-append).

### Scaling ladder — add a layer only on an observed failure

| Add | Only when |
|---|---|
| Kanban candidate queue (cards, ≤3 workstreams, 7200 s per-card ceiling, re-seed cron = closure operator) | wall-time/cost are themselves objectives |
| Watchdog / janitor (deterministic, LLM-free, dry-run default) | silent stalls or wedges observed |
| Adversary board (PoV contract: no proof-of-violation, no points; context rationing) | the metric saturates or lies (Goodhart) |
| Optimizer board (dual ascent: λ prices the attacker-yield floor, μ prices a slot) | two producers compete for one budget |
| Conductor referee (pins, information asymmetry, hot-fixes) | pinning / asymmetry abuse observed |

### Formal mapping

| Mechanism | Formal concept |
|---|---|
| keep/discard branch loop | elitist (1+1)-ES / stochastic hill climbing; MDP (state = codebase+ledger, action = edit, reward = Δmetric) |
| board chain | finite Markov chain; statuses = states, dispatcher = transition kernel; the re-seed cron is the closure operator making it ergodic |
| defender × attacker | Stackelberg security game; scored by minimax exploitability gap |
| optimizer λ / μ | Lagrange multipliers / projected dual ascent |
| league / Pareto seasons | population-based training (PBT) + AlphaStar-league selection |
| metric risk | Regressional Goodhart — sample real output on-policy, never trust the frozen scalar alone |

## Verification

```bash
python3 -m pytest tests/unit/test_corpus_integrity.py -q
# ....                                                                     [100%]
# 4 passed in 0.01s

grep -c "concepts/" kb/index.md
# 16
grep -c "2026-09-26-autoresearch-methodology-registration" kb/index.md
# 1

git log --oneline -1 -- kb/raw/articles/2026-09-26-autoresearch-methodology-registration.md
# 80b78b2 contract/examples: three worked autoresearch runs + progression dashboard

# supporting evidence, same run
python3 -m pytest tests/unit/test_kb_synthesis.py -q
# 4 passed in 0.01s
grep -n "Total pages" kb/index.md
# 6:> Last updated: 2026-09-26 | Total pages: 26
git status --short
# (no output — working tree clean as measured at write time, before the catalog
#  rows landed; a later tree with untracked stage-6 docs shows them here)

# the strip convention the first stamp missed
python3 - <<'EOF'
import hashlib, pathlib, re
p = pathlib.Path("kb/raw/articles/2026-09-26-autoresearch-methodology-registration.md")
m = re.match(r"^---\n(.*?)\n---\n?(.*)$", p.read_text(), re.S)
stamp = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)["sha256"].strip()
print(stamp == hashlib.sha256(m.group(2).strip().encode()).hexdigest())
EOF
# True
```

All commands were run from the repo root on 2026-09-26. The corpus and
synthesis tests are read-only, stdlib-only, and run on every CI `unit` job, so
a sha drift or an orphaned page fails the PR rather than being read past.

## What Works

- The registration is a committed, test-gated raw source:
  `kb/raw/articles/2026-09-26-autoresearch-methodology-registration.md` passes
  `tests/unit/test_corpus_integrity.py` (4 passed), and recomputing
  `sha256(body.strip())` matches the frontmatter stamp.
- Five new layer-2 pages (`methodology-registration`, `kanban-factory`,
  `adversarial-optimization-layer`, `better-cheaper-faster-metrics`,
  `formal-mapping-autoresearch`) plus two updates (`entities/karpathy-autoresearch`,
  `concepts/evaluator-legitimacy`) are committed and indexed — `kb/index.md`
  carries 16 `concepts/` rows and 26 total pages, and the registration article
  appears exactly once under Raw Sources.
- `tests/unit/test_kb_synthesis.py` passes (4 passed): every new page is
  indexed with no orphans, wikilinks resolve, and each page traces to `raw/`.
- The ingest landed as the two ingest commits — `4813d98` (registration + skill) and
  `80b78b2` (stamp correction + worked examples), with unrelated commits between them —
  `git log -1` over the raw path reports `80b78b2`, and the working tree is clean.
- The instantiation recipe travels as a skill at
  `.agents/skills/autoresearch-methodology/SKILL.md`, with its canonical ingest
  pointer held repo-relative so it resolves from any clone.
- The provenance correction is recorded: `entities/karpathy-autoresearch.md`
  now states the Goodhart / "always sample generated output" caveat is NOT
  upstream but added by this template lineage's own `contract/`, grounded in
  the 2026-09-26 sha verification of the upstream files.

## What Fails

- **First ingest stamp missed the `body.strip()` convention:** the raw article
  was committed in `4813d98` with `sha256: f1264f80…`, a value that is not
  `sha256(body.strip())` — AC-EXC-002 was red against it until `80b78b2`
  re-stamped the frontmatter to `2879373f…`, the value it carries today.
- **`kb/log.md` still records the pre-correction hash:** the 2026-09-26 ingest
  line carries `sha256 f1264f80…` while the article's frontmatter reads
  `2879373f…`; because the log is append-only, the two disagree until a later
  line supersedes the ingest entry.
- **The game/optimizer layer is registered, not measured:** the dual regulator
  is implemented-but-inert (λ = μ = 0 across 22 live cycles), the season / PBT
  loop is designed-not-observed, and the Markov transition matrix was never
  estimated from data — three of the five formal layers are structural
  readings, not measured dynamics.

## Resolution

- **First ingest stamp missed the strip convention:** re-stamp over
  `body.strip()`; AC-EXC-002 now enforces the convention on every `unit`-tier
  run, so a fresh ingest that hashes the wrong body fails CI instead of being
  read past — the same gate `docs/04-examples-corpus.md` documents.
- **`kb/log.md` still records the pre-correction hash:** the frontmatter
  (test-enforced) is authoritative; the log is the historical record, and the
  next entry written for this path records the correction — appending, never
  editing, preserves the add-only contract.
- **Game/optimizer layer unmeasured:** read the formal mapping as a structural
  reading and apply the ladder rule before trusting a layer — verify the
  multipliers actually move (λ, μ ≠ 0) and estimate the chain from data before
  relying on the regulator or the season loop.

## Verdict

**works** — the methodology is registered as a committed, catalogued, test-gated corpus
addition (4 corpus-integrity + 4 kb-synthesis tests green over 16 raw sources and 26
indexed pages, `sha256(body.strip())` matching), with the one recorded drift already
caught by AC-EXC-002 and the residual log-hash / unmeasured-layer items being
record-and-scope limits rather than a broken path.
