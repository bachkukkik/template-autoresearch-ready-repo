---
source_url: https://github.com/karpathy/autoresearch (research synthesis: upstream repo + 11 YouTube transcripts + bachkukkik doctrine; artifacts in scratchpads/autoresearch-research/)
ingested: 2026-09-04
sha256: 9fda3a6e53dc8a696f6fa5c51d7332d15a4398cbd393ec5054e46fc56bbe8f0e
title: Autoresearch template build — deep research conclusions
---

# Autoresearch Template Build — Deep Research Conclusions

> Synthesis of the 2026-09-04 deep-research run for building
> **template-autoresearch-ready-repo** (a template for karpathy/autoresearch that
> follows the bachkukkik/template-agentic-ready-repo doctrine and ships extensive
> worked examples).
> Research artifacts (structured results, per-item snapshots, raw notes) live in
> `scratchpads/autoresearch-research/` (gitignored). Raw sources ingested here:
> upstream program.md (`articles/autoresearch-program-md-reference.md`) and 11
> YouTube transcripts (`transcripts/`).

## 1. Executive summary

**Karpathy's autoresearch is a three-file contract, not a codebase.** The transferable pattern is: one human-edited instruction file (`program.md`, "a super lightweight skill") defines the job; one agent-edited artifact (`train.py`) is the thing to optimize; one immutable evaluator (`prepare.py`) owns the metric (`val_bpb`, lower is better) and a fixed 5-minute wall-clock budget. The agent loops: hypothesize → edit → run → measure → keep/discard → repeat, ~12 experiments/hour, ~100 overnight. **Everything the videos demonstrate is this same contract transplanted to other domains** (music, TSP, cold email, website load time, Claude skills). The bachkukkik doctrine is the repo-scale version of the same idea: AGENTS.md ≈ program.md at repo scale, every `.agents/skills/*/SKILL.md` ≈ program.md at task scale, `docs/NN-slug.md` verdicts ≈ `results.tsv` rows. The template should therefore be explicit about this mapping and ship a library of worked examples, each one a complete instance of the contract.

## 2. Verified facts about karpathy/autoresearch

- Repo: `github.com/karpathy/autoresearch`, created 2026-03-06, MIT (README states; no LICENSE file tracked), Python, `master` branch, ~95.2K★ / ~13.4K forks at 2026-09-04 snapshot. Description: "AI agents running research on single-GPU nanochat training automatically".
- Three files that matter:
  - `prepare.py` — fixed/read-only: constants (`TIME_BUDGET=300`, `MAX_SEQ_LEN=2048`, `EVAL_TOKENS=40*524288`, `VOCAB_SIZE=8192`), data prep (climbmix-400b-shuffle shards), BPE tokenizer, dataloader, and the ground-truth `evaluate_bpb`.
  - `train.py` — the single file the agent edits: simplified single-GPU nanochat (GPT, Muon+AdamW, SSSL window pattern, `DEPTH=8`, `TOTAL_BATCH_SIZE=2**19`). Prints a run summary (val_bpb, training_seconds, peak_vram_mb, mfu_percent, total_tokens_M, num_steps, num_params_M, depth).
  - `program.md` — human-edited skill: Setup (branch `autoresearch/<tag>`, baseline first, verify data), Experimentation CAN/CANNOT rules, simplicity criterion, VRAM soft constraint, output/`results.tsv` format, "NEVER STOP" (do not ask the human; continue until manually stopped).
- `val_bpb` = total per-token CE nats / (log 2 × total utf-8 bytes) — vocab-size-independent by construction, so architectural changes are compared fairly.
- Fixed 5-minute budget rationale: experiments are directly comparable regardless of what the agent changes; the loop finds the optimal model *for your platform in that budget*; the downside is cross-platform incomparability.
- Experiment log: `results.tsv` (tab-separated, 5 columns: commit, val_bpb, memory_gb, status keep/discard/crash, notes), untracked; crashes logged with val_bpb 0.000000.
- Design choices: single file to modify (reviewable diffs), fixed time budget, self-contained (PyTorch + few small deps, one GPU).
- Small-compute tuning (README guidance): TinyStories dataset; lower `vocab_size` (8192→4096/2048/1024/256); lower `MAX_SEQ_LEN`; lower `EVAL_TOKENS`; lower `DEPTH` (e.g. 4); `WINDOW_PATTERN="L"`; lower `TOTAL_BATCH_SIZE` (keep powers of 2).
- Notable forks: miolini/autoresearch-macos (MPS), trevin-creator/autoresearch-mlx (MLX, no PyTorch, plus a `rigor.py` statistical keep/discard gate for run noise ~0.03 val_bpb), jsegov/autoresearch-win-rtx (consumer RTX, tiered VRAM), andyluo7/autoresearch (AMD ROCm/HIP). Curated extension list: `github.com/yibie/awesome-autoresearch` (153 entries).

## 3. The loop contract (what a template must teach)

Every worked example decomposes to the same five ingredients:

1. **A scalar objective metric with a clear direction** — one number, lower/better, defined in an agent-untouchable evaluator. "If you can score it, you can auto research it" (relayed Karpathy quote).
2. **An automated, no-human-in-the-loop measurement tool** — the loop cannot run unattended overnight otherwise.
3. **One editable artifact** — the thing the agent mutates (`train.py`, a skill's `SKILL.md`, a website's JS, an email template, an algorithm script).
4. **A fixed, modest time budget per experiment** — comparability device; the agent cannot win by simply working/training longer.
5. **A keep/discard loop with explicit selection rules** — baseline first, simplicity criterion, rerun-to-confirm noise handling, `git commit` / `git reset` discipline, artifact + result logging.

Human roles in this contract: write the instruction file, define the metric, seed data/algorithms, and review notifications — not run the experiments.

## 4. What the examples teach (findings per source)

### Success conditions (all three required — video uBWuKh1nZ2Y)
- Clear metric; automated eval with no human in the loop; something to change. Missing any one degrades the loop to non-autonomous research or random optimization.
- **Fails where "better" is subjective**: brand design, UX, pricing (unless huge traffic + fast A/B). Wrong metric = confidently optimizing the wrong thing.

### Problem selection (video bMoNOb0iXpA — TSP / Kaggle Traveling Santa)
- **Well-suited**: cheap fast evaluation that fits the budget; scalar cost; local-move improvement structure.
- **Step back when**: heavy compute per eval, expensive evaluation, need for non-greedy exploration, domain knowledge the LM lacks.
- Wins observed: warm starts from best-so-far; steering (inspecting artifacts and redirecting); pre-research feeding the LM plausible algorithm names; saving best-so-far artifacts + tests. Pitfall: parallel-10 runs lost the best solution; no tests → invalid tours.

### New-domain adaptation (videos -Ip9EtoBjbk, T6pQVgIt8ZY, 9jxrmk_Xses)
- Recipe: get data → adapt prepare.py per domain → train tokenizer → keep val_bpb → 5-min runs. Small, low-entropy, highly regular data (stories, ABC sheet music, D&D dialogue) works; complex varied data (Python code) fails at generation despite metric wins.
- Music run: TinyStories warm-up (laptop GPU, gibberish→coherent in ~2h), then ABC sheet music: baseline val_bpb ≈ 2.08 → 0.978 (~53% improvement), 18 experiments, batch-size reduction the biggest win; depth increases hurt (throughput-bound).
- **Flagship negative result (U4kZ0t7Onhw)**: Python code run cut val_bpb 1.85 → 0.82 (~55%) yet generated "import torch CH CH CH…" loops — teacher-forced eval vs autoregressive generation gap, tiny models exploit popular tokens. **Always sample generated output; metrics can lie.**
- Near-human TinyStories on a consumer laptop (RTX 4060): 1.173 → 0.511 in ~2h.

### Choosing the research agent (video jCNeVZJAYGM — 4 local LLMs on DGX Spark, ~6h each)
- Ranking: Qwen 3.8 27B won (final val_bpb 1.142, only 21 experiments — thinking mode, decisive wins on batch size + warm-up) > Nemotron 3.5 Lightning (1.143, 43 experiments — speed) > Ornith 1.5 35B (33 exp, 2 keeps, LR-divergence crash + compaction recovery issues) > Muse Glimmer (last; instruction-following failures, idle-stalling — fatal for unattended autonomy).
- Lessons: hypothesis quality beats iteration count at the margin; thinking capability is a selection criterion; speed is a legitimate alternative axis; autonomy (not stalling) is make-or-break; crashes are survivable with loop guards; context compaction degrades long sessions (need state-recovery strategy).

### Harness integration (videos 4Cb_l2LJAW8, 9jxrmk_Xses; tutorial uBWuKh1nZ2Y)
- Claude Code is the most common driver; Codex had issues in at least one run; harness-friction is real (agent-written scripts can be buggy).
- Business transplant (cold email): Claude Code scaffolds orchestrator/client/utilities/config/CI from the karpathy repo + one directive; GitHub Actions cron (hourly); Slack webhook review; learnings accumulate in `resource.md` so each fresh agent "grows more intelligent"; cadence scaling 4h → 1h → 5min. Expect most challengers to initially lose.
- Tutorial flow: define success conditions → scaffold eval (Puppeteer benchmark) → baseline → adapt program.md → run loop with "record results.tsv, do not stop or ask me anything" → rerun-to-confirm noise protocol.

### Self-improving skills (video qKU-e0x2EmE — the pattern this template embodies)
- Mapping: skill.md ≈ train.py (mutable artifact), program.md ≈ the agent/objective, binary yes/no eval suite ≈ the measurement tool, mutate-and-keep-winner loop every 2–5 min.
- Ingredients: objective metric; automated measurement (agent-written test suite); something to change. Use **binary evals** (Likert scales compound variance); run many times and aggregate (mode+median); eval suite is the human's lever; watch for eval-parroting/Goodhart gaming.
- Reported results: diagram-generator skill 32/40 → 39/40; website 1100ms → 67ms (~81%); ~$0.02/gen.

### Ecosystem and the bottleneck thesis (Badkur & Dak 2026 survey + systems)
- Systems: SkyPilot (parallel grid-wave scaling: 16 GPUs, ~910 experiments/8h, 9× faster, factorial grids capture interaction effects), Bilevel Autoresearch (outer loop code-generates search mechanisms), Centaur (CMA-ES+LLM hybrid sharing optimizer state), Sibyl (self-evolving trial-and-error harnesses), AutoResearchClaw (23-stage pipeline: debate, self-healing, VerifiedRegistry, HITL, +54.7% vs AI Scientist v2 on ARC-Bench).
- Survey thesis: every system improves search prior / execution evaluator; none fully solves **research-evaluator legitimacy** and **judgment preservation**. Humans add most value at high-leverage evaluator-design/validation points (AutoResearchClaw CoPilot 87.5% accept rate > full-auto).
- Cautionary case: Shopify/liquid (53% faster parse+render, 93 commits, PR unmerged) — execution-evaluator wins are not research wins; production/held-out validation must gate adoption.
- Practical noise lesson: fixed-metric loops Goodhart-converge; declining edit entropy is the early warning; ~0.03 val_bpb run-to-run noise means naive keep/discard chases noise — statistical gates help.

## 5. Doctrinal mapping (autoresearch ↔ bachkukkik doctrine)

| Autoresearch | template-agentic-ready-repo doctrine |
|---|---|
| `program.md` (human-edited skill) | `AGENTS.md` (repo-scale) + `.agents/skills/*/SKILL.md` (task-scale) |
| `train.py` (agent-edited artifact) | the artifact under optimization (service code, skill files, docs examples) |
| `prepare.py` + `evaluate_bpb` (immutable metric) | `kb/` semantics + PRD success criteria + CI gates (tests) |
| `results.tsv` (per-experiment log) | `docs/NN-slug.md` verdicts + `kb/log.md` action record |
| Setup → experiment → keep/discard loop | document funnel: scratchpads → kb/raw → kb → PRD → gaps → docs/NN → issues |
| 5-minute budget, NEVER STOP | `sub1`–`sub4` orchestration phases; local-CI-then-remote pipeline |
| Human edits program.md, reviews notifications | Human writes PRD/SC, reviews PRs, monitors CI |

Structural difference to surface: autoresearch runs **unattended autonomy** within fixed budget; the doctrine is **human-gated** at PR/merge. The template must present both modes explicitly and show where each applies (agent loop for experiment iteration; human gates for repo artifacts).

## 6. Template design implications (blueprint for the build)

1. **Clone the doctrine skeleton as-is** and extend the funnel explicitly for examples: funnel rule 1 forbids stray docs, so `examples/` must be either (a) added as a named funnel stage (with rules + doctrine CI check updated), or (b) housed as stage-3 knowledge + wired-through docs. Prefer making it a first-class, CI-checked stage: the user's core ask is "extensive examples to achieve objectives".
2. **Ship the three-file contract as the canonical example** — vendored/adapted mini-autoresearch workspace (program.md/train.py/prepare.py + results.tsv convention), replacing or sitting beside the skeleton's example microservice, so agents can literally run the loop in the template.
3. **Examples library layout**: one dir per objective (train-a-model, adapt-a-domain, choose-an-agent, harness-integration, self-improve-a-skill, apply-to-non-ML), each with: goal/intent, program.md-style spec, evaluator + metric, runnable verification, expected outcome, and the video/repo source it was distilled from. NN-mirrored numbering tied to docs (e.g., `examples/01-*` ↔ `docs/01-*.md`).
4. **Verdict docs for both audiences**: every example gets a `docs/NN-slug.md`-style verdict (What/Why/How/Verification/Works/Fails/Resolution) so humans see reality, agents see the contract.
5. **Pin skills in `.agents/skills/`**: root-cause (already), llm-wiki, coding-agents-docs-guideline, plus a new `program.md`-style autoresearch skill implementing the contract; consider a `skill-self-improver` example skill (from video qKU) as the showcase.
6. **CI additions**: besides the existing unit→integration→e2e→secret-scan→doctrine jobs, validate that every example has its required files (program.md, eval, verification command) and that `results` JSON artifacts conform to a schema; keep kb/raw add-only.
7. **Docs structure**: README for humans (what to expect, quick start), AGENTS.md pointer-style for agents (~100 lines, pointers not encyclopedia), docs/README verdict catalog for both; a PLATFORMS matrix (upstream + 4 forks + tuning guide) and a CHOOSING-AN-AGENT section grounded in the local-LLM benchmark.
8. **Positioning (marketer lens)**: one-liner — "A template repo for Karpathy-style autore research that runs the whole experiment loop inside the bachkukkik agentic-ready doctrine, with a library of worked examples that teach humans and agents how to achieve objectives." Audience: AI-curious engineers / agentic-team leads who want overnight research without writing agent glue.

## 7. Objectives mapping (user's intended usage)

| User goal | Template mechanism |
|---|---|
| Human understands what to expect | README + docs/README verdict catalog + examples gallery; "what the loop does" explainer |
| Agent understands what to do, follows examples | AGENTS.md + vendored program.md-style skills + examples each carrying a runnable spec/verification |
| Human understands how to work with agents | Program.md-as-contract tutorial, harness-adapter table, human roles (write spec, review notifications/PRs) |
| Humans+agents craft docs aligned with the doctrine | Funnel rules extended to examples; every example produces kb/raw source + docs/NN verdict; llm-wiki + coding-agents-docs-guideline pinned |

## 8. Assumptions & open questions

- [ASSUMPTION] The template will vendor a small, runnable autoresearch workspace (adapted from karpathy's repo, MIT) rather than only document it; CI-safe tiny-config CPU runs are feasible for the e2e tier.
- [ASSUMPTION] The final repo keeps the skeleton's CI/doctrine jobs intact (they are the enforcement the doctrine depends on) and extends rather than replaces them.
- [ASSUMPTION] "Extensive examples" = 6–10 worked example objectives, each with runnable verification, not a full mirror of the 153-entry awesome list.
- Open: exact examples-library funnel placement (new funnel stage vs kb-backed docs); how many examples to ship in v1; whether to keep the skeleton's example microservice as one of the examples; whether the template will be used predominantly on NVIDIA Linux (upstream), macOS (forks), or Windows.
- All quantitative findings above are as-reported by the sources (transcripts/READMEs/papers) and were not independently reproduced; see per-item `confidence` in the research results for granularity.
