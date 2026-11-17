# 27 — The 20 KB file-size cap cannot hold in this repo

**Layers:** prd ↔ code
**Status:** open
**Opened:** 2026-11-16

## Observation

PRD 27 ports upstream's file-size gate with its policy intact — a per-file cap
of 20 KB (20,480 bytes), strict by default — and then adopts a different number
in the only place the gate is enforced. The corpus cannot meet the policy, and
nothing in the tree can be shrunk to fix that without breaking a doctrine rule
or a pin.

| Side | Source | Claim |
|------|--------|-------|
| A | `docs/prd/27-file-size-audit.md` (*Deliverable*, *Assumptions*) | The cap is 20 KB by default, 20,480 bytes, inclusive, and strict: an over-cap tracked file fails the run. 20 KB is "the right default for a corpus the size of upstream's". |
| A | `scripts/audit-size.py:35` | `DEFAULT_MAX_KB = 20.0` — the script's own default is unchanged from upstream. |
| B | `.github/workflows/ci.yml` (*Machine gates*) | `python3 scripts/audit-size.py --max-kb 60` — CI runs 61,440 bytes, 3× the policy number. |
| B | `tests/unit/test_audit_size.py` (`ADOPTED_KB`) | The unit gate asserts the same 60 KB, so the test and the policy disagree too. |
| B | the tracked corpus | 30 of 423 regular files are over 20,480 bytes: 22 in the measured scope, 8 in the exempt classes. |

The two sides cannot both be true. Either 20 KB is the gate — and it fails 30
tracked files today, none of which this repo may shrink — or 60 KB is the gate,
and the "20 KB policy" is a default that no enforcement path uses.

## Evidence

Commands run from the repo root, 2026-11-16:

```
$ python3 scripts/audit-size.py > /dev/null; echo "exit=$?"
exit=1

$ python3 scripts/audit-size.py | grep -c 'over cap 20480'
22

$ python3 scripts/audit-size.py --max-kb 60 > /dev/null; echo "exit=$?"
exit=0

$ python3 scripts/audit-size.py --max-kb 60 | tail -1
largest: 56312 bytes  tests/unit/test_harness_neutrality.py
```

The 22 measured offenders, by byte count:

```
 56312 tests/unit/test_harness_neutrality.py
 45262 tests/unit/test_engine_loop.py
 42236 tests/unit/test_supervisor_recipe.py
 40166 docs/11-worked-example-pipelines.md
 39837 tests/unit/test_examples_ex4.py
 39417 autoresearch/engine/autoresearch/loop.py
 37083 autoresearch/contract/examples/ex4-llm-repo-speedup/prepare.py
 34921 PRD.md
 34897 docs/prd/22-target-profile.md
 34445 docs/21-agent-evals.md
 34429 autoresearch/commands/registry.py
 29476 .agents/skills/autoresearch/scripts/orchestrate.sh
 29411 docs/09-agents-md-context-budget.md
 28784 tests/unit/test_eval_provenance.py
 27379 README.md
 26399 autoresearch/contract/examples/ex5-real-oss-speedup/guard.py
 24628 autoresearch/service/autoresearch_service/main.py
 24251 tests/unit/test_eval_statistics.py
 22738 autoresearch/contract/examples/ex4-llm-repo-speedup/agent_driver.py
 22398 autoresearch/engine/autoresearch/config.py
 21791 autoresearch/engine/autoresearch/ledger.py
 20620 autoresearch/engine/autoresearch/objective.py
```

The other 8 are inside the exempt classes: `autoresearch/uv.lock` (317,842
bytes), `kb/log.md` (27,142) and six `kb/raw/` sources (21,665–41,169). None of
the 30 can be met by deleting bytes — `kb/raw/` is append-or-archive (funnel
rule 3), `kb/log.md` is append-only (rule 5), `uv.lock` is generated, and
`autoresearch/contract/examples/ex4-llm-repo-speedup/prepare.py` is a
sha256-pinned frozen evaluator (`AC-TPL-014`) that cannot be edited without
breaking its pin.

## Impact

The reviewability guarantee is weaker than the PRD states, and the gap between
the number and the code is invisible to CI by construction: the step passes at a
cap 3× the policy, so a file can grow by 5,128 bytes before anything speaks and
an agent reading PRD 27 will believe the ceiling is 20 KB. The second cost is
trust in the gate itself — a checker whose default fails the tree it ships with
teaches the next agent to run it with a flag, which is how a hard gate becomes
an advisory one.

## Resolution

A code change, in waves, with the gate tightened only when the corpus earns it.
The policy is unmet; the convergence is tracked as GitHub issue #64. The
converging path is: shrink the 22 measured files below 20,480 bytes, then delete
`--max-kb 60` from the `Machine gates` step and `ADOPTED_KB` from
`tests/unit/test_audit_size.py` — at which point PRD 27's default is the gate,
and this gap closes when `python3 scripts/audit-size.py` exits 0 with no flag.
Nothing here invents a new number: the target is the policy already written.

- **W1 — test modules (6 files, 231 KB of the debt).** Split by AC group, not by
line count: `test_harness_neutrality.py` (56,312) into entry-point/symlink,
budget and adapter-completeness modules; `test_engine_loop.py` (45,262) into
loop mechanics and salvage/wall-reservation; `test_supervisor_recipe.py`
(42,236) into recipe and guard-ladder modules; `test_examples_ex4.py` (39,837)
by fixture; `test_eval_provenance.py` (28,784) and `test_eval_statistics.py`
(24,251) into one statistics module plus one provenance module.
- **W2 — engine, contract and service modules (9 files).** `loop.py` (39,417)
into loop, salvage and wall modules; `registry.py` (34,429) into one entries
module per command group; `guard.py` (26,399), `main.py` (24,628),
`agent_driver.py` (22,738), `config.py` (22,398), `ledger.py` (21,791) and
`objective.py` (20,620) split along their existing class boundaries. The one
exception is `prepare.py` (37,083): a frozen evaluator shrinks only with a pin
bump, so it moves last and only with PRD-02 in the same change.
- **W3 — the three top-level documents (3 files).** `PRD.md` (34,921) is mostly
*Version History*; move superseded rows into a stage-4 changelog file by PR,
as the funnel rule 11 multi-file edit. `docs/11-worked-example-pipelines.md`
(40,166) splits per example group (ex1–ex3, ex4, ex5) with its
`docs/README.md` row and covers column updated in the same pass. `README.md`
(27,379) loses its duplicated reference tables to the documents that own them.
- **W4 — records and one vendored script (4 files).** `docs/21` (34,445),
`docs/prd/22` (34,897), `docs/09` (29,411) and
`.agents/skills/autoresearch/scripts/orchestrate.sh` (29,476) — the records
shrink by promoting their verification tables to a per-run appendix, and the
vendored script converges only by re-vendoring an upstream that has split it,
never by editing a vendored copy.

Backing topic files, for the walk from intent to reality by number alone:
`docs/prd/27-file-size-audit.md` (the deviation, the adopted cap and what it
costs) and `docs/27-file-size-audit.md` (the measured state, and the verdict
that flips to `works` when this gap closes).
`docs/prd/26-char-per-line-audit.md` and `docs/26-char-per-line-audit.md` are
the sibling gate and do not depend on this one.
