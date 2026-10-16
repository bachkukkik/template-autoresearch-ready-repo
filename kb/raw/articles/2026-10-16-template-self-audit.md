---
source_url: https://github.com/bachkukkik/template-autoresearch-ready-repo
ingested: 2026-10-16
sha256: 3730bd01728d5113934851678bbc9258121c6c45f81c56d0ddbfa67c64beab4f
kind: article
title: Template self-audit — contract, examples, harness and integrity
---

# Template self-audit — contract, examples, harness, integrity

A first-party audit of this template's own autoresearch artefacts, run
2026-10-16 on a working tree at the branch that adds the harness-neutral
contract and the OSS-landscape synthesis. Findings are grouped by surface, each
with a repo-relative reproduction. Leads that the audit **disproved** are listed
at the end so they are not re-raised.

## 1. The contract (`contract/program.md`, `contract/train.py`, `contract/prepare.py`)

- **`TIME_BUDGET=300` never gates.** `contract/prepare.py` declares
  `TIME_BUDGET = 300`, but the shipped `train.py` baseline is a smoothed bigram
  that finishes in ~0.06 s — the budget is decorative on the baseline and no
  candidate is ever measured against it. Repro: `grep -n TIME_BUDGET
  contract/prepare.py`; `time python3 contract/train.py`.
- **`train.py --results` hard-codes `status="keep"`.** The row writer at
  `contract/train.py:117-125` emits `status="keep"  # first run = baseline`
  unconditionally, so any invocation appends a *keep* row regardless of outcome.
  Repro: `grep -n 'status="keep"' contract/train.py`.
- **`memory_gb` is always `0.0`.** `peak_vram_mb = 0.0` (CPU-only demo) is divided
  by 1024 and written to `memory_gb`, so the column is a constant. Repro:
  `grep -n 'peak_vram_mb' contract/train.py`.
- **`prepare.py` immutability is claimed, but no byte pin enforces it.**
  `program.md` says "Do not modify", and `tests/unit/test_domain_hooks.py`
  (AC-TPL-041) asserts the object-identity `train.evaluate_bpb is
  prepare.evaluate_bpb` — which stops *redefinition in train.py* but not a textual
  edit to `prepare.py` itself (the identity still holds after an edit). There is
  no `sha256` pin of `prepare.py` anywhere. Repro: `grep -rn 'sha256'
  contract/`.
- **No noise-floor rule.** Nothing in `program.md` or `train.py` defines a
  minimum meaningful delta; the loop is exposed to run-to-run noise. Repro:
  `grep -in 'noise\|tolerance\|confidence\|mad' contract/program.md`.
- **`program.md` is ML-only.** The setup steps still name `~/.cache/autoresearch/`
  data shards and a tokenizer download in the upstream-derived prose; only the
  data-side note was rewritten for the embedded corpus. Repro: `sed -n '1,40p'
  contract/program.md`.

## 2. The worked examples (`contract/examples/ex1..ex3`)

- **None of the three `loop_driver.py` runs reproduce its committed
  `results.tsv` from tracked state.** Each example ships `train.py` in its
  **final kept state**, so re-running the driver starts from the end state, not
  the baseline.
  - ex1: `cd contract/examples/ex1-music-abc && python3 loop_driver.py` prints
    the baseline row at `val_bpb=2.178535` (the final bigram) and then aborts with
    `PATCH MISS for 'bigram interpolation lam=0.5'`.
  - ex2: the shipped `train.py` is `K=7` (`grep -n '^K =' train.py`), i.e. the
    final `keep`, so `python3 loop_driver.py`'s first row logs accuracy
    `1.000000`, **not** the recorded baseline `0.933333`.
  - ex3: the shipped `train.py` already carries the fast helpers
    (`grep -n 'def by_initial\|def rare_positions' train.py`), so the driver's
    naive-helper patches miss and it aborts with `PATCH MISS`.
  - Caveat: the drivers `git commit` and `git reset --hard` as they run, so a
    reproduction mutates the working tree; run them only on a throwaway clone.
- **The drivers are hard-coded candidate lists, not LLM-driven runs.** Their
  docstrings say the edits "are the mutation operator's choices (LLM-driven)",
  but `CANDIDATES = [...]` is a static Python list of string patches. Repro:
  `grep -n 'CANDIDATES\|LLM-driven' contract/examples/ex1-music-abc/loop_driver.py`.
- **ex2's seed-42 "no headroom" note is false.** `contract/examples/ex2-iris-knn/prepare.py`
  (the seed pre-registration note above `SPLIT_SEED = 23`) claims seed 42's 1-NN
  raw baseline "already sits at the ceiling of the whole kNN family (0.977778 …
  every config in the K × metric × normalize × weighted grid ties)". On seed 42
  the raw 1-NN baseline is `0.977778`, and the full grid's maximum is
  `1.000000` — so seed 42 does leave headroom; the real reason seed 23 was picked
  is that seeds 0..39 were scanned for a split on which the *baseline* is low
  (`0.933333 → 1.000000`, a larger apparent gain). Repro: toggle `SPLIT_SEED`
  between 42 and 23 and re-run the grid.
- **`TIME_BUDGET` is nominal in every example** (`TIME_BUDGET = 60` while a run
  takes milliseconds), so the budget bounds nothing. Repro: `grep -n TIME_BUDGET
  contract/examples/ex2-iris-knn/{prepare.py,program.md}`.
- **ex1's `results.tsv` has no header row** (ex2 and ex3 do). Repro: `head -1
  contract/examples/ex1-music-abc/results.tsv`.
- **The dashboard hand-transcribes numbers.** `contract/examples/dashboard.html`
  carries the per-example series as literal arrays (`["baseline 1-NN raw
  euclidean", 0.933333, "keep"]`) rather than reading the `results.tsv` files, so
  it can silently drift from the ledgers. Repro: `grep -n '0.933333'
  contract/examples/dashboard.html`.

## 3. The harness story

- **7 of the 8 mandated skills are not vendored.** `AGENTS.md` §1 mandates eight
  skills (`karpathy-guidelines`, `security-best-practices`, `webapp-testing`,
  `coding-agents-docs-guideline`, `llm-wiki`, `root-cause`, `yeet`,
  `opencode-plan-build-orchestrator`); `ls .agents/skills/` shows only
  `root-cause` (plus `autoresearch-methodology`, which is not in the mandated
  list). Repro: `ls .agents/skills/`.
- **The documented fallback path does not exist.** `AGENTS.md` funnel rule 8 and
  §1 promise the last-resort fallback of inlining a skill's `SKILL.md`, and the
  SCHEMA spec line nominates `.agents/skills/llm-wiki/SKILL.md`, but that path is
  absent. Repro: `ls .agents/skills/llm-wiki/` → `No such file or directory`.
- **The stage-3 spec points at an external URL, not a vendored file.**
  `kb/SCHEMA.md` names the upstream Hermes `SKILL.md` URL rather than a revision
  that travels with the repo. Repro: `sed -n '1,8p' kb/SCHEMA.md`.
- **The 20,000-char context cap is stated as every-harness law.**
  `tests/unit/test_agents_md_budget.py` asserts a `CONTEXT_FILE_MAX_CHARS =
  20_000` cap as if every harness enforced it; that is a Hermes value. Repro:
  `grep -n CONTEXT_FILE_MAX_CHARS tests/unit/test_agents_md_budget.py`.
- **The harness test is an exact allowlist.** `test_harness_neutrality.py`'s
  `KNOWN_HARNESS_LABEL_RE` names only Hermes / Claude Code / opencode / Copilot /
  DeepSeek-OpenAI-compatible, so adding a harness fails until the test is edited —
  the adapter cannot grow without touching the guard. Repro: `grep -n
  KNOWN_HARNESS_LABEL_RE tests/unit/test_harness_neutrality.py`.
- **opencode skill discovery paths verified correct.** Per `opencode.ai/docs/skills`,
  opencode honours `.opencode/skills`, `~/.config/opencode/skills`,
  `.claude/skills` and `.agents/skills`; this repo's `.agents/skills` (canonical)
  and `~/.config/opencode/skills` bindings are right, and the entry file is
  `AGENTS.md` (native) per `opencode.ai/docs/rules`. No defect here.

## 4. Baseline drift from the foundation template

The QC baseline in `PRD 06 quality controls` of `bachkukkik/template-agentic-ready-repo`
at `11b00e1` is **not adopted** here. Absent against `.github/workflows/ci.yml`:
top-level `permissions:` on workflows, SHA-pinned `uses:` (`actions/checkout@v4`,
`actions/setup-python@v5` are tag-pinned), `persist-credentials: false`,
`SECURITY.md`, `CODEOWNERS`, `.github/dependabot.yml`, a PR template, an
aggregate `if: always()` qc-gate job, and zizmor. Repro: `grep -n 'permissions:\|
@v4\|@v5' .github/workflows/ci.yml`; `ls SECURITY.md CODEOWNERS
.github/dependabot.yml`. (The ported QC concept pages record the doctrine these
diff against.)

## 5. Integrity / hygiene

- **Three broken relative links** — `kb/concepts/output-medium-escalation.md`
  links `../docs/prd/13-output-medium-doctrine.md` and `../docs/15-ste-audit.md`
  from inside `kb/concepts/`, which resolves to the non-existent `kb/docs/`
  (should be `../../docs/`); and one more in the same class. Repro:
  `git grep -n '](\.\./docs/' -- kb/`.
- **Stale counts.** `kb/index.md`'s header and Stats claim 30 layer-2 pages while
  the tree holds 28; `AGENTS.md`'s structure note and the index disagree.
  Repro: `find kb/concepts kb/entities kb/comparisons kb/queries -name '*.md' |
  wc -l`.
- **An absolute host path in `docs/14-gen-env-script.md`.** Two usage lines invoke
  `python3 <absolute-checkout-path>/scripts/gen-env.py`; a checked-out path on one
  machine is meaningless on another (funnel rule 6/9 violation shape). Repro:
  `grep -n 'gen-env.py' docs/14-gen-env-script.md`.
- **A private-instance name in ~9 tracked files.** A private commerce-pipeline
  instance is named (with its owner) across `.agents/skills/autoresearch-methodology/SKILL.md`,
  `contract/examples/ex1-music-abc/README.md`,
  `contract/examples/ex3-hotpath-speedup/README.md`,
  `docs/10-methodology-registration.md`, `docs/README.md`,
  `kb/concepts/better-cheaper-faster-metrics.md`, `kb/concepts/kanban-factory.md`,
  `kb/concepts/methodology-registration.md` and the methodology-registration raw.
  The `kb/` half is remediated by this wave (supersede + de-identify); the
  `docs/` and `contract/` halves remain. Repro: `git grep -rn -i '<instance-token>'
  -- docs/ contract/ .agents/`.

## Leads DISPROVED (do not re-raise)

- **"No object-identity anti-cheat test"** — false. `tests/unit/test_domain_hooks.py`
  carries **AC-TPL-041** (`assert train.evaluate_bpb is prepare.evaluate_bpb`), and
  ex2's driver re-checks the same identity for `evaluate_accuracy`.
- **"The KB copy of upstream `program.md` has drifted"** — false. The raw reference
  at `kb/raw/articles/autoresearch-program-md-reference.md` is byte-identical to the
  upstream program.md; it is simply not the same file as this repo's rewritten
  `contract/program.md`.
- **"`setup` with-user vs `NEVER STOP` wording diverges from upstream"** — false.
  The `## Setup` step and the `NEVER STOP` clause in `contract/program.md` are the
  upstream wording, unmodified.
