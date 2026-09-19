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
| `python3.12` | `tests/run.sh`, `contract/`, `service/`, `ops/sync.sh`'s tests | yes |
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

Symlinks are how this repo keeps **one** instruction file: `CLAUDE.md` and
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

## Step 3 — keep / replace / delete

The most useful table in this file. Nothing here is a rule — for every rule, read
`AGENTS.md`.

| Part | Verdict | Why |
|---|---|---|
| The funnel itself (`kb/` → `PRD.md` → `docs/gaps/` → `docs/NN-slug.md`) | **KEEP** | it is the doctrine: the stage order, the skill gates and the one-way flow are what you came for |
| `kb/raw/` + `kb/` | **REPLACE** | ingest your own sources into `kb/raw/`, then run the `llm-wiki` synthesis over `./kb/`; a layer-2 page is never hand-written |
| `PRD.md` + `docs/prd/` | **REPLACE** | this template's intent, not yours — rewrite the master PRD and start your topic PRDs at `01` |
| `docs/NN-slug.md` + `docs/README.md` | **REPLACE** | the empirical layer records what *this* project verified; start your own `NN` set at `01`, keep the catalog format |
| `contract/` (the autoresearch loop) | **REPLACE** | the loop's objective and its immutable evaluator are this template's; keep the `program.md` / `train.py` / `prepare.py` shape, swap the subject |
| `service/` (the example harness) | **REPLACE-OR-DELETE** | the example service is not your product — keep it only if your project ships a service; if not, delete `service/`, `docker-compose.yml` and the `e2e` tier together |
| `ops/` | **DELETE if you have no externally-operated subject** | vendored config earns its place only when a process *outside* the repo reads it (`ops/README.md`, *How to adopt this*) |
| `tests/` | **KEEP the shape, REPLACE the tests** | three tiers, each with a runner *and* a CI job, is the contract; the `AC-*` tests are this repo's |
| `.github/workflows/` | **KEEP** | `ci.yml` is the gate; `sources-readonly.yml` enforces the add-only rule for `kb/raw/` |
| `ADOPTING.md` | **REPLACE or REUSE** | it is a root entry doc, not a stray document; re-point it at your project or drop it once your own README carries onboarding |

Deleting a funnel stage is not an option: a repo without `kb/` or without `docs/NN-slug.md`
has no grounding direction, and the `doctrine` job will tell you so.

## Step 4 — wire your harness

**No vendor entry file or config needs to be created for any harness.** `AGENTS.md` is
the one instruction file; the harness-specific entry points are symlinks that already
exist.

| Harness | Entry instruction file | What you create |
|---|---|---|
| Hermes | `AGENTS.md` — read **natively** | nothing |
| Claude Code | `CLAUDE.md` — symlink → `AGENTS.md` | nothing |
| opencode | `AGENTS.md` — read **natively**; `.agents/skills` is honoured natively too | nothing |
| DeepSeek / OpenAI-compatible | `AGENTS.md` — read **manually** (no vendor entry file exists to read) | nothing — inline a skill's `SKILL.md` into the prompt when a gate names one |
| Copilot / anything else | `.github/copilot-instructions.md` — symlink → `AGENTS.md` | nothing |

Reproducing the full capability-by-capability binding — skills, sub-agents, code graph,
KB synthesis, pipeline invocation — is `AGENTS.md`'s *Harness Adapter*, including its
*Per-harness rows* table for opencode and DeepSeek. Adding a harness later is two
symlinks plus a row in that table.

## Step 5 — the first change loop

`AGENTS.md`'s *`/goal` Orchestration Workflow* is the entry point for a substantive
request. `/goal` itself is a **Hermes-only** convenience: the canonical cross-harness
contract is the **`sub1`–`sub4` phase blocks and their phase table**, and
"go through sub1-4" is a valid instruction on any harness. Report each phase's *Done
when* before starting the next; if a phase surfaces a problem, re-enter kickoff triage
for that problem first.

## Step 6 — adding a tracked root

Adding a top-level tracked directory is a five-file edit — the five places move
together. Checklist (the rule is `AGENTS.md` funnel rule 11):

- [ ] the funnel stage table in `AGENTS.md`
- [ ] the *Where does this text go?* table in `AGENTS.md`
- [ ] the Repository Structure block in `AGENTS.md`
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
