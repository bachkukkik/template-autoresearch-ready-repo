# Adopting this template

This is a template for **autonomous research**: the Karpathy-style
[autoresearch](https://github.com/karpathy/autoresearch) loop (one human-edited
`program.md`, one agent-edited artifact, one immutable evaluator, a fixed time budget, a
keep/discard decision per run) wired onto the
[bachkukkik/template-agentic-ready-repo](https://github.com/bachkukkik/template-agentic-ready-repo)
doctrine — document funnel, harness adapter, PRD → success criteria → test → CI. The
code, the `kb/`, the PRDs and the `docs/` you are looking at are all **worked examples
for one concrete project**; adopt the pattern, replace the example.

**[`AGENTS.md`](AGENTS.md) is the canonical rule set** — the funnel and its rules, the
harness adapter, the test tiers, the security rules. This file only says *what to do in
what order*, and links there for every rule rather than restating it.

```bash
git clone <repo-url> && cd <repo>        # step 1
git config core.symlinks true            # step 1
bash scripts/verify-clone.sh             # step 2 — read-only, one PASS/FAIL line per check
```

## Prerequisites

| Need | Why | Required |
|---|---|---|
| `git`, with `git config core.symlinks true` | every harness entry point is a symlink to `AGENTS.md` (step 1) | yes |
| `python3.12` | `tests/run.sh`, `autoresearch/contract/`, `autoresearch/service/` | yes |
| Docker + Compose | the `e2e` tier and `docker compose up -d` | for the container tier |
| `bats` | `tests/e2e/` runs under bats (the tier skips loudly without it) | optional |
| [`nektos/act`](https://github.com/nektos/act) | the pre-PR local-CI command in `AGENTS.md` §6 | optional |
| `npm` + [`@colbymchenry/codegraph`](https://github.com/colbymchenry/codegraph) | the primary structural code search (`AGENTS.md` *codegraph*) | optional, recommended |
| `gh` CLI | funnel stage 7 — issues | optional |

## Step 1 — get the clone and enable symlinks

```bash
git clone <repo-url>
cd <repo>
git config core.symlinks true
```

Symlinks are how this repo keeps **one** instruction file: `CLAUDE.md`, `GEMINI.md` and
`.github/copilot-instructions.md` point at `AGENTS.md`, and `.claude/skills` /
`.claude/plugins` point into `.agents/`. `core.symlinks` defaults to **false on
Windows**, where the clone then gets *plain text files containing a path* instead of
links — every harness entry point breaks, and a forked copy can drift from `AGENTS.md`
with nothing to notice it. The `doctrine` CI job fails the build for either state, and
`scripts/verify-clone.sh` catches it locally.

## Step 2 — prove the clone is healthy

```bash
bash scripts/verify-clone.sh
```

One command, **read-only** — it writes no files, no git index and no git config, so it
runs on a fresh clone, on a deploy host and in CI. It checks, one PASS/FAIL line each:

1. every harness entry point is a **resolving** symlink;
2. the doctrine paths are git-tracked and not gitignored;
3. every tracked top-level directory is declared in the `doctrine` job's list;
4. `.credentials/` ships its `.example` shape and ignores real files;
5. `graphify-out/` artifacts are ignored by rule;
6. `python3` and `tests/run.sh` are present — then prints the next command
   (`bash tests/run.sh --with-e2e`).

Checks 1–3 mirror the `doctrine` job, so a clone that passes here is a clone CI accepts.
Non-zero exit and a named failure per problem; the first FAIL is the one to fix first.

## Step 2.5 — run one loop in 5 minutes

Two proofs, in order. **First see the contract** — no Docker, no service, no
harness wiring. From the repo root:

```bash
python3 autoresearch/contract/prepare.py    # -> prepare.py OK — TIME_BUDGET=300s, vocab_size=31
python3 autoresearch/contract/train.py      # -> the summary block: val_bpb: 3.795531, stop_reason: converged
```

`prepare.py` is the frozen evaluator (the corpus lives inside it — no external
cache to download); `train.py` is the one agent-edited artifact and prints the
summary block ending in `val_bpb` / `stop_reason`. To record a run in the ledger,
pass `--results results.tsv` — `results.tsv` is gitignored (untracked, per
upstream) and its columns are `commit` / `val_bpb` / `memory_gb` / `status` /
`description`, with the note at the top of `autoresearch/contract/program.md` describing each.
Prefer a throwaway copy? `cp -r autoresearch/contract /tmp/loop && cd /tmp/loop && python3
prepare.py && python3 train.py` runs the same loop outside the repo.

That is one measured run — no keep/discard, no engine. **Then run the engine**,
where the script, not the agent, commits, measures and reverts:

```bash
autoresearch/engine/bin/autoresearch doctor   # each harness binary; key set/unset
bash autoresearch/contract/examples/ex5-real-oss-speedup/setup.sh \
  "${TMPDIR:-/tmp}/ex5"
# setup.sh copies ex5, commits a baseline and runs init for it — the general form:
#   init --repo <repo> --verify "python3 bench.py" --guard "python3 guard.py"
#        --metric-name seconds --direction lower --scope target
cd "${TMPDIR:-/tmp}/ex5"                      # disposable repo, already init'd
PYTHONPATH=<repo>/autoresearch/engine python3 -m autoresearch run --repo . \
  --agent claude --dry-run                    # validate + print argv, no agent run
PYTHONPATH=<repo>/autoresearch/engine python3 -m autoresearch run --repo . \
  --agent claude --max-iterations 8           # the loop: keep | revert per trial
PYTHONPATH=<repo>/autoresearch/engine python3 -m autoresearch status --repo .
PYTHONPATH=<repo>/autoresearch/engine python3 -m autoresearch report --repo .
```

`run` needs an agent harness — `--agent claude|opencode|hermes|dsh|command|replay`
— and `--dry-run` proves the wiring without calling it.

## Step 2.6 — start the example service (optional)

Only if your project ships the service. It builds and runs **without Docker**:

```bash
cd autoresearch && uv sync --locked --extra service
AUTH_DISABLED=1 uv run --no-sync uvicorn autoresearch_service.main:app --port 8000   # dev only
```

Or the container path: `docker compose up -d --build` from the repo root, then
`curl localhost:8000/health` → `{"status":"ok"}`. The service is optional —
`autoresearch/contract/` (the loop above) is the template's core; delete
`autoresearch/service/`, `docker-compose.yml` and the `e2e` tier together if you do not
ship one (Step 3).

## Step 3 — keep / replace / delete

The most useful table in this file. Nothing here is a rule — for every rule, read
`AGENTS.md`.

| Part | Verdict | Why |
|---|---|---|
| The funnel itself (`kb/` → `PRD.md` → `docs/gaps/` → `docs/NN-slug.md`) | **KEEP** | it is the doctrine: the stage order, the skill gates and the one-way flow are what you came for |
| `kb/raw/` + `kb/` | **REPLACE** | ingest your own sources into `kb/raw/`, then run the `llm-wiki` synthesis over `./kb/`; a layer-2 page is never hand-written |
| `PRD.md` + `docs/prd/` | **REPLACE** | this template's intent, not yours — rewrite the master PRD and start your topic PRDs at `50` |
| `docs/NN-slug.md` + `docs/README.md` | **REPLACE** | the empirical layer records what *this* project verified; start your own `NN` set at `50`, keep the catalog format |
| `autoresearch/contract/` (the autoresearch loop) | **REPLACE** | the loop's objective and its immutable evaluator are this template's; keep the `program.md` / `train.py` / `prepare.py` shape, swap the subject |
| `autoresearch/contract/examples/` (the worked runs) | **KEEP as reference** | reference, not scaffolding: ex5 is the engine's real-code demo; ex1–ex4 predate the engine and each carries its own copy of the keep/discard driver — do not copy those drivers (closed gap 17) |
| `autoresearch/engine/` (the loop itself) | **KEEP** | layer 0 — the script owns commit/measure/revert, the margin and the bounded stops; inherit it verbatim and point it at your code (step 2.5) |
| `autoresearch/objective/` + `autoresearch/targets/` (what a run optimises) | **KEEP the mechanism, REPLACE the records** | layer 0/1 — the validator and the relativity split are the contract; replace the example profile and the `template-val-bpb` objective with your own |
| `autoresearch/commands/` (the command registry) | **KEEP** | layer 0 — one declaration per command (PRD 23); a new script outside the registry is a defect, not a shortcut |
| `autoresearch/supervisor/` (the unattended recipe) | **KEEP** | layer 0 — the schema, the idempotent installer and the guard ladder; parameterise the target and the scheduler binding, never fork the recipe |
| `autoresearch/service/` (the example harness) | **REPLACE-OR-DELETE** | the example service is not your product — keep it only if your project ships a service; if not, delete `autoresearch/service/`, `docker-compose.yml` and the `e2e` tier together |
| `tests/` | **KEEP the shape, REPLACE the tests** | three tiers, each with a runner *and* a CI job, is the contract; the `AC-*` tests are this repo's |
| `.github/workflows/` | **KEEP** | `ci.yml` is the gate; `sources-readonly.yml` enforces the add-only rule for `kb/raw/` |
| `ADOPTING.md` | **REPLACE or REUSE** | it is a root entry doc, not a stray document; re-point it at your project or drop it once your own README carries onboarding |

Deleting a funnel stage is not an option: a repo without `kb/` or without `docs/NN-slug.md`
has no grounding direction, and the `doctrine` job will tell you so.

## Layer model — inherit, parameterise, configure

Before you replace anything, sort what you are adopting into three layers. The
rule that saves the most work is the third: **a game layer is configured
downstream, never forked.**

| Layer | What it is | What you do |
|---|---|---|
| **0 — core** | the funnel, the CI gate, the three test tiers, the engine, the objective and run records, the command registry, the unattended recipe | **inherit verbatim**; replace the subject, not the mechanism |
| **1 — instruments** | domain-neutral machinery for what a reading *is*: noise floors and margins, claim grading, cost beside score, attempt records | **inherit and parameterise** with your target profile and your metric |
| **2 — game** | your domain's own economics: what scores, what pays, who competes, how a season closes | **configure downstream, never fork** |

A layer-2 game is legitimate and expected. What it must not do is re-declare a
layer-0 or layer-1 contract. It names three things the template gives it — a
declared target profile, a referee command that prints one parseable number per
leg, and the evaluator hash taken at both ends of a round — and it keeps its
pricing, its seats and its seasons to itself.

The failure this rule prevents is on record. A sibling repo built on this
template grew its own referee, its own economy, its own round runner and its own
supervisor as four new PRDs, re-deriving contracts this template already owns,
because nothing said where the game layer lives. The register in
[PRD 28](docs/prd/28-veteran-layer.md) is the answer: twenty decisions with the
failure that earned each one, and one column saying whether this tree enforces it
or defers it.

That register's `Source` paths (`docs/41-…`) point into the private downstream
instance `vanilla-open-design-autoresearch`, not this tree; the load-bearing
quotes are captured in `kb/raw/articles/2026-11-26-veteran-decisions.md`.

Two consequences worth stating plainly. A layer-2 omission is **not** a template
defect — a repo with no tournament does not need a referee, and the register marks
those rules `declared` instead of pretending. And a layer-1 gap **is** a template
defect, because every adopter pays it: that is why PRDs 29 and 30 exist.

The numbers are part of the inheritance. PRD, `docs/NN` and `docs/gaps/` numbers
`01`–`49` are reserved for the template's own core and instruments, which a later
sync may extend; an adopter numbers its own PRDs, records and gaps from `50` up.
A sibling that spent `28`–`31` on its game layer collided with the template's own
`28`–`30` on the next pull, and the merge cost more than renumbering would have.

## Step 4 — wire your harness

**No vendor entry file or config needs to be created for any harness.** `AGENTS.md` is
the one instruction file; the harness-specific entry points are symlinks that already
exist.

| Harness | Entry instruction file | What you create |
|---|---|---|
| Hermes | `AGENTS.md` — read **natively** | nothing |
| Claude Code | `CLAUDE.md` — symlink → `AGENTS.md` | nothing |
| opencode | `AGENTS.md` — read **natively**; `.agents/skills` is honoured natively too | nothing |
| Codex CLI | `AGENTS.md` — read **natively**; `.agents/skills` honoured natively | nothing |
| Cursor | `AGENTS.md` — read **natively** (`.cursor/rules` also read) | nothing |
| Gemini CLI | `GEMINI.md` — symlink → `AGENTS.md` (its default context file) | nothing |
| Aider | `AGENTS.md` — read via `aider --read AGENTS.md` (or `.aider.conf.yml` `read:`) | add `read: AGENTS.md` to `.aider.conf.yml` if you want it automatic |
| DeepSeek / OpenAI-compatible | `AGENTS.md` — read **manually** (no vendor entry file exists to read) | nothing — inline a skill's `SKILL.md` into the prompt when a gate names one |
| Copilot / anything else | `.github/copilot-instructions.md` — symlink → `AGENTS.md` | nothing |

Entry files are symlinks this repo already ships; only Aider needs one line of your own
config, because it has no default instruction filename. The pipeline (the `sub1`–`sub4`
phase blocks) is run by prompting those blocks in order — see `README.md` § *Harness
Support* for the per-harness row and the doc link.

Reproducing the full capability-by-capability binding — skills, sub-agents, code graph,
KB synthesis, pipeline invocation — is `AGENTS.md`'s *Harness Adapter*, including its
*Per-harness rows* table for opencode and DeepSeek. Adding a harness later is two
symlinks plus a row in that table.

## Step 5 — the first change loop

`AGENTS.md`'s *Lifecycle — Zero to Deployment* is the entry point for a
substantive request: the development stage `D0`–`D4` (entry → prompt → gaps →
implement → empirical docs), then the delivery stage `sub1`–`sub4`, with the UAT
variant adding `sub5` to promote `uat` into `main`. `/goal` itself is a
**Hermes-only** convenience: *Running the pipeline without `/goal`*, in the same
section, is the canonical cross-harness contract — the `D0`–`D4` / `sub1`–`sub4`
labels plus the phase table — so "go through sub1-4" is a valid instruction on
any harness. Report each step's *Done when* before starting the next; if a step
surfaces a problem, re-enter `D1` triage for that problem first.

## Step 6 — adding a tracked root

Adding a top-level tracked directory is a five-file edit — the five places move
together. Checklist (the rule is `AGENTS.md` funnel rule 11):

- [ ] the funnel stage table in `AGENTS.md`
- [ ] the *Where does this text go?* table in `AGENTS.md`
- [ ] the *Repository Structure* block in `README.md`
- [ ] the `doctrine` job's tracked-path list in `.github/workflows/ci.yml`
- [ ] `AC-FUN-002`'s required-dirs list in `tests/unit/test_funnel_structure.py`, when
      the root is a funnel stage

`scripts/verify-clone.sh` check 3 fails, naming the root, if step 4 is skipped — the
same way the `doctrine` job does.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `CLAUDE.md` is a text file, not a symlink | the clone did not enable symlinks — `git config core.symlinks true`, then re-checkout the entry points. A plain-text `CLAUDE.md` silently forks the doctrine |
| `scripts/verify-clone.sh` fails check 3, naming a directory | that root is missing from the tracked-path list in `.github/workflows/ci.yml` — see step 6 |
| `scripts/verify-clone.sh` fails check 1 with a *dangling* link | the link's target is absent or gitignored; `.agents/` is tracked, so a checkout that drops it leaves a dangling `.claude/skills` |
| `docker compose up -d` → *port is already in use* | another stack owns the published port; change the published port in `docker-compose.yml` or stop that stack |
| `act push` replaced your running containers | never run `act push` unqualified (or `-j e2e`) on a host that serves this compose project — the project name derives from the directory name. `AGENTS.md` §6 has the hazard and the safe chain |
| `graphify-out/` noise in `git status` | the ignore should cover it **by rule**; if you deliberately track the graph, un-ignore `graphify-out/graph.json` *and* register the merge driver — `AGENTS.md` *graphify* |
| An agent wrote a `NOTES.md` / `TODO.md` | not a funnel stage — that content is an issue, or it belongs in `scratchpads/` (AGENTS.md funnel rule 1). File it with `gh issue create` |
