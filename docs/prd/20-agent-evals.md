# PRD 20 — Agent Evals: Making better/cheaper/faster Falsifiable in the Engine

> Intent: make the engine's keep/discard decision a *measurement* rather than a
> comparison of two numbers. A candidate must clear a margin derived from the
> dispersion of the actual repeats; a delta inside that margin has its own
> verdict instead of being banked as progress; and every adjudicated decision
> records the provenance it was made under, so a result survives a model swap.
> **Domain:** `evl` — the evaluation layer.
> **Canonical tests:** `tests/unit/test_eval_statistics.py` (`AC-EVL-001..004`),
> `tests/unit/test_eval_provenance.py` (`AC-EVL-006..007`),
> `tests/unit/test_engine_ledger.py` (`AC-EVL-005`),
> `tests/integration/test_eval_loop_stats.py` (`AC-EVL-202`).
> **Grounding:**
> [deterministic-keep-gate](../../kb/concepts/deterministic-keep-gate.md),
> [better-cheaper-faster-metrics](../../kb/concepts/better-cheaper-faster-metrics.md),
> [loop-stop-conditions](../../kb/concepts/loop-stop-conditions.md),
> [run-record-contract](../../kb/concepts/run-record-contract.md),
> raw source
> [2026-11-15 downstream frontier distillation](../../kb/raw/articles/2026-11-15-downstream-frontier-distillation.md).
> **Builds on:** PRD 17 (engine). It does not change that PRD's contracts; it
> tightens what a keep is allowed to mean.
> **Stage 6:** `docs/21-agent-evals.md` — **pending**; it is written from a
> verification run, not from this plan.

## Context

The engine measured honestly in the small and dishonestly in the aggregate. Read
at the pre-port tree:

1. **The margin was a bare fraction.** `decide()` gated a keep on
   `|incumbent| * noise_floor` with `DEFAULT_REPEATS = 1`. A relative floor is
   not a measurement: for a proportion metric at n=100 the standard error alone
   is 0.038–0.05, i.e. 3.8–5× the 0.01 floor, so a recorded keep could be pure
   jitter. `measure()` reduced repeats to a bare median and discarded the
   dispersion it had just observed.
2. **A keep had two possible readings where it needed three.** A delta too small
   to separate the runs was recorded `discard`, which claims a judgement nobody
   made and spends a plateau slot.
3. **Decisions were not reproducible.** No ledger event recorded the model, the
   route, the engine version, the scoring command or the profile content, so
   after a model or evaluator change a result could be neither re-run nor
   credited.
4. **The repeat count was the wrong default.** `n = 1` means the standard error
   is undefined, the margin collapses to the floor and the dispersion gate is
   *dormant* while any prose describing it says it is live — the failure the
   downstream repo hit after it had already shipped the layer.

**Users.** (a) An adopter who runs the loop overnight and needs its `results.tsv`
to mean something; (b) a reviewer who must re-derive a keep from the ledger
months later.

**Constraints.** Stdlib only; no `shell=True`; every subprocess bounded by a
timeout; no secret value in the append-only ledger (identifiers and version
strings only); the engine's CLI surface stays as it is apart from
`status --require-provenance`.

## Scope

In: `autoresearch/engine/autoresearch/{measure,decide,ledger,loop,prompt,cli}.py`
— dispersion fields, `margin()`, `decide_with_margin()`, the `inconclusive`
outcome, the six-field provenance block and its read-side gate, the
`DEFAULT_REPEATS = 3` default, the prompt's inconclusive section, and the new
tests above.

Out: the *referee* half of the downstream eval layer — measured A/A noise floor,
evaluator drift canary, cheat probes, seeded-defect audit scoring, the bearing
`faster` leg. This repo has no arena or scoring layer to host them; shipping
them here would be dead code (see *Out of Scope*).

`inconclusive` is a new name in the **engine's** outcome vocabulary, and it
appears verbatim in the engine's own `results.tsv` (whose header fixes the
columns, not the set of outcomes). The frozen contract ledger under
`autoresearch/contract/` is a different artifact with its own
`keep|discard|crash` vocabulary (PRD 02 SC9) and is untouched by this PRD.

## Success Criteria

- **SC-evl-1 — A measurement reports the dispersion it observed.** `measure()`
  returns, besides the median, the repeat count, the sample standard deviation
  and an `honest` flag that is `True` only with `repeats >= 2` *and* a point
  estimate; a single repeat reports `spread: null`, `honest: false` and never a
  fabricated zero. `DEFAULT_REPEATS` is **3**, so the gate is live where the
  decision is made; `--repeats 1` stays available and stays honest.
  _Verify:_ `tests/unit/test_eval_statistics.py` (AC-EVL-001, AC-EVL-002).
- **SC-evl-2 — A keep clears a margin; a delta inside it is `inconclusive`.**
  The threshold is `max(noise floor, 1.96 × SE of the difference of the two
  medians)`, with the median's consistency factor (1.2533) inside the SE; a
  delta inside it is recorded `inconclusive`, reverted exactly like a discard,
  counted as a non-keep by the plateau rule and never moved into the incumbent.
  The loop computes the margin **once** and records that number with the
  dispersion it was derived from (`repeats`/`spread`/`honest`/`se`/`margin`);
  the configured floor keeps its pre-port *relative* reading, so every margin
  keep is also a legacy keep.
  _Verify:_ `tests/unit/test_eval_statistics.py` (AC-EVL-003, AC-EVL-004).
- **SC-evl-3 — Every keep/discard decision carries provenance.** The event
  records `model`, `model_route`, `engine_version`, `referee_version` (the
  sha256 of the verify command — the engine's referee *is* that command),
  `profile_sha256` (the run.json content) and an ISO-8601 UTC `timestamp`; it is
  built **before** the candidate is committed, so a block that cannot be built
  aborts on a clean tree. `model` and `model_route` are refused (never scrubbed)
  when they embed URL userinfo, and `--model` is refused in preflight: the
  ledger is append-only, so a secret there could only be rotated, never edited
  out.
  _Verify:_ `tests/unit/test_eval_provenance.py` (AC-EVL-006),
  `tests/integration/test_eval_loop_stats.py` (AC-EVL-202).
- **SC-evl-4 — Provenance is a gate a caller can switch on, not a silent
  default.** `status --require-provenance` fails (exit 3) with the offending
  `seq` when a decision carries no block, a block is missing a field, or the
  timestamp / profile digest is not in canonical form; without the flag the same
  ledger still replays, so old runs are not invalidated by the new claim.
  _Verify:_ `tests/unit/test_eval_provenance.py` (AC-EVL-007).
- **SC-evl-5 — Replay re-checks the margin that was recorded, and old ledgers
  replay unchanged.** A keep whose recorded `margin` the delta does not exceed
  is a violation (a fabricated plausible margin must not validate); an unusable
  margin (non-numeric, NaN, infinite, negative) is a violation; a keep with no
  `margin` — every pre-PRD-20 event — is replayed by the legacy floor rule, and
  an `inconclusive` trial replays as a non-keep that never moves the incumbent.
  _Verify:_ `tests/unit/test_engine_ledger.py` (AC-EVL-005).
  Corroborated by `tests/integration/test_engine_loop.py` and
  `tests/unit/test_engine_loop.py` (AC-ENG-050..059), which replay whole runs.
- **SC-evl-6 — The loop end-to-end emits a scientific record.** A keep earned at
  the default `--repeats 3` writes dispersion, the standard error, the margin
  actually applied, the six-field provenance block and both cost fields as an
  explicit `null` (`agent_tokens`, `agent_api_calls` — `0` would claim the agent
  was free); an improvement inside the margin is recorded `inconclusive` and
  reverted; `status --require-provenance` accepts what the run wrote.
  _Verify:_ `tests/integration/test_eval_loop_stats.py` (AC-EVL-202).

## Test Mapping

| SC | AC ids | Test file | Tier |
|----|--------|-----------|------|
| SC-evl-1 | AC-EVL-001, AC-EVL-002 | `tests/unit/test_eval_statistics.py` | unit |
| SC-evl-2 | AC-EVL-003, AC-EVL-004 | `tests/unit/test_eval_statistics.py` | unit |
| SC-evl-3 | AC-EVL-006, AC-EVL-202 | `tests/unit/test_eval_provenance.py` + `tests/integration/test_eval_loop_stats.py` | unit + integration |
| SC-evl-4 | AC-EVL-007 | `tests/unit/test_eval_provenance.py` | unit |
| SC-evl-5 | AC-EVL-005 | `tests/unit/test_engine_ledger.py` | unit |
| SC-evl-6 | AC-EVL-202 | `tests/integration/test_eval_loop_stats.py` | integration |

## CI/CD Gate

- The unit ACs run in the existing `unit` job (`pytest tests/unit`) and the
  integration AC in the existing `integration` job
  (`.github/workflows/ci.yml`). No new job is required: the engine is
  stdlib-only and every test is hermetic (throwaway git repos, a scripted
  `command` adapter, no model and no network).
- `scripts/audit_pyramid.py` (the `unit` tier's potato-pyramid gate) holds the
  new code to the comment budget and the banned-pattern list.
- The engine files are on the protected list, so this layer ships through the
  normal funnel (branch + PR + review), never through an engine keep.

## Out of Scope (deliberately not ported here)

- **A/A noise floor, drift canary, cheat probes, seeded-defect audit rate, the
  `faster` leg.** Each needs an evaluator surface the engine does not have (a
  referee binary, an arena round, a defect corpus). The rules are recorded in
  `kb/concepts/deterministic-keep-gate.md` and
  `kb/concepts/better-cheaper-faster-metrics.md` so a future PRD can implement
  them with tests rather than port them as dead code.
- **Salvage and the wall reservation.** Ported in the same wave but owned by
  PRD 17 (engine behaviour: a dead agent's tree is still a candidate; the wall
  funds a whole iteration or starts none) — AC-ENG-082..083.
- **A multi-metric `better` composite** and an LLM judge — both change PRD 17's
  contract and need their own PRD.

## Assumptions

- [ASSUMPTION] `Z = 1.96` is the asymptotic 95% quantile and the repeats are
  few: at `n = 2` the exact `t(0.975, df=1)` is 12.7, so the margin is
  optimistic by roughly an order of magnitude at the smallest honest sample. A
  `t`-based margin is a future PRD; the current rule is still strictly wider
  than the floor it replaces.
- [ASSUMPTION] Three repeats is the right default for this template's targets
  (a verify in the seconds-to-minutes range). The wall reservation is no
  longer a fixed tail: it is `agent_timeout + guard_timeout + repeats ×
  verify_timeout` (3300 s at the defaults), so a slower verify widens it
  automatically and a wall that cannot fund one iteration is refused in
  preflight instead of starting a baseline it can never iterate on.
  Deliberate divergence from the downstream engine, whose `ITERATION_TAIL =
  120` under-reserves a repeats × timeout verify; the template's arithmetic is
  exact and downstream parity is not required here.
- The engine handles only `SIGINT`; an outer `SIGTERM`/`SIGKILL` cannot be
  salvaged. The wall reservation is the defence there, not a promise that a
  kill is safe.

## Confidence

**High for the measurement half, medium for the provenance half as a
*sufficiency* claim.** Every SC above is a test on the ported code, and the
backward-compatibility direction is mechanical: `margin >= floor`, so a margin
keep is never a new keep under the old rule (a brute-force sweep over the
single-repeat grid finds no counter-example). What is *not* proved is that three
repeats is enough for any particular metric — that is a property of the target's
noise, and the ledger now records enough (`spread`, `se`, `honest`) for a reader
to see it.
