# 28 — Seven veteran rules are declared, not enforced

**Layers:** prd ↔ code
**Status:** open
**Opened:** 2026-11-26

## Observation

PRD 28 adopts twenty rules from the mature downstream instance and states,
per row, whether this repository enforces it. Seven rows carry `declared:`
because the capability they govern does not exist here: a game with seats and
payment, a scheduler fleet, a situation router. Five more are `test-partial:`:
a mechanical half runs today, a settlement half does not. Two of those five —
VD-18 and VD-19 — are listed here because in each the missing half is a
payment, and this tree has no code that pays. The register would be a lie if
it claimed them as `test:`; it would be a dead document if it dropped them.
They are listed here instead, each with the layer that would close it.

| Rule | What is missing | Closed by |
|---|---|---|
| VD-06 | A brief sized to its own gate's margin | PRD 29's claim reader plus a measured margin; needs a per-metric margin in the objective record first |
| VD-08 | Retiring a metric a census shows unwinnable | an objective registry that can retire a leg — `autoresearch/objective/registry.json` already carries `status`, no consumer acts on it |
| VD-11 | Re-establish and re-measure the base before paying | a round/promote contract; PRD 22's target profile hashes an evaluator, it does not manage a trunk |
| VD-12 | One writer per target | a scheduler fleet; this repo ships one recipe and one job |
| VD-15 | Deterministic first, LLM last, ceiling in code | the steward router (downstream PRD 25); deliberately not ported |
| VD-16 | Facts fail closed | the steward's rule table |
| VD-17 | Digest the facts to stop a repeat fire | the steward's launcher |
| VD-18 | Landed gates payment — the `test-partial` half that runs records a landed keep, and nothing pays for one | a settlement; `tests/unit/test_engine_loop.py` covers the guard, not the price |
| VD-19 | Salvage a dead agent's tree — the `test-partial` half that runs salvages the tree and marks the keep `salvaged`, and no settlement pays for it | a settlement; `tests/unit/test_engine_loop.py` covers the salvage and the measurement, not the payment |

## Evidence

`docs/prd/28-veteran-layer.md` § *The register* — the seven rows whose
`Enforcement` cell reads `declared: none`, plus the two `test-partial` rows
this file lists (VD-18, VD-19).

`tests/unit/test_veteran_register.py` (AC-VET-004) asserts that every such row
is listed in this file by id, so the two cannot drift apart in silence.

## Impact

An adopter reading the register sees a rule that reads like a guarantee and is
not one. The damage is bounded and stated: the seven rules govern a
tournament, a scheduler fleet and a situation router that this template does
not ship, so no path in this tree behaves differently for their absence. The
cost is informational — a reader must follow the `declared:` cell to learn that
the rule is advice, not enforcement, and a generated repo may assume a
settlement exists when it does not.

## Why this is not a defect

A template that shipped a steward and a league to satisfy its own register would
be copying one domain's economics into every adopter — the exact failure PRD 28
names. The honest form of a rule this tree cannot enforce is a row that says so
and a gap that says who would.

## Resolution

Close this gap only by closing a row: the day a capability lands, its PRD moves
the row from `declared:` (or `test-partial:`) to `test:` and deletes its line
here. When the last row goes, archive this file. VD-09 closed that way: a
`_Verify:` payload checker now holds it and its line is gone.

Candidates in order of cost: VD-18 then VD-19 (one settlement, twice — payment
for a landed keep and for a salvaged one), then VD-06 (a measured brief
margin).
