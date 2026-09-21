# 09 — AGENTS.md Context Budget

## What

`AGENTS.md` is this repo's single agent instruction file — `CLAUDE.md` and
`.github/copilot-instructions.md` are symlinks to it — and every harness auto-loads it
into each prompt, silently truncating it above a 20,000-character context-file cap. This
doc records the trim that brought it from 42,936 to 19,467 chars, which regions were
preserved byte-for-byte versus compressed, the guard expectations the trim invalidated,
and the unit tripwire that keeps the file under the cap.

## Why

- Every harness loads the instruction file into each prompt. An oversized file is not an
  error — it is truncated with a warning the agent never sees at task time.
- Overflow is lossy in the **middle**: head 70% plus tail 20% of the cap survive and the
  middle is dropped. Position, not importance, decides what the agent reads, so whole
  sections of the doctrine vanish with no signal.
- At 42,936 chars the file was 22,936 chars over the cap and the builder was delivering
  18,372 chars of it — less of the doctrine reached the agent than after the trim, even
  though the file was more than twice the size.
- A doctrine the agent cannot read is not a doctrine. The failure is silent and
  positional, so the fix had to keep every rule and end in a structural guard rather than
  a note asking the next author to be careful.
- This repo is the largest of its family: unlike its sibling repositories it cannot keep
  its load-bearing regions byte-identical (see *The 19,791-char arithmetic*), so the
  preservation claim had to be made per region rather than uniformly.

## How

### The cap

`CONTEXT_FILE_MAX_CHARS = 20_000` in `agent/prompt_builder.py` is the flat floor of a
dynamic cap — `context_length × 4 × 0.06` characters, clamped to 20,000–500,000. The floor
applies whenever the model window is not threaded through, which is the common case, so it
is the number this repo targets. Read off the staged tree:

```text
floor 20000 | head 0.7 | tail 0.2
cap(None)     20,000   <- the flat floor, in force when context_length is not threaded
cap(32,768)   20,000
cap(131,072)  31,457
cap(200,000)  48,000
```

It is a **characters** rule, not a bytes rule. Measure with `len(text)` in Python, or with
`LC_ALL=C.UTF-8 wc -m`; a bare `wc -m` on this host counts bytes (see *What Fails*).

### Truncation behaviour

`_truncate_content()` keeps `head_chars = int(max_chars * 0.7)` and
`tail_chars = int(max_chars * 0.2)` — the ratios apply to the **cap**, not to the file —
replaces the middle with a `[...truncated AGENTS.md: kept 14000+4000 of 42949 chars. …]`
marker, and logs:

```text
⚠️  Context file AGENTS.md TRUNCATED: 42949 chars exceeds limit of 20000 — trim the file, pin a larger context_file_max_chars, or use a larger-context model!
```

`[ASSUMPTION]` At the pre-edit size the omitted window was therefore characters
`[14000, 38949)` of the 42,949 the builder counted (42,949 − 14,000 − 4,000 = 24,949
dropped). The window is derived from the builder's own `kept 14000+4000 of 42949 chars`
marker and the head/tail constants; the before-state delivery probe was not re-run for
this doc.

### The trim — before and after

Measured through the real builder (`pb.build_context_files_prompt(cwd=…,
context_length=None)`), not inferred from size:

| Revision | chars | bytes | sha256 (`AGENTS.md`) | delivered block | whole file verbatim | `TRUNCATED` warnings |
|---|---|---|---|---|---|---|
| before — `main` @ `f4008c2` | 42,936 | 43,859 | `17e064e16c2443ac…` | 18,372 chars | `False` | 1 |
| after — this branch | 19,467 | 19,691 | `17a663d392b92c0b…` | 19,577 chars | `True` | 0 |

Reduction: 23,469 chars (54.7%) / 24,168 bytes (55.1%). Headroom under the floor: 533
chars (2.7% of the cap); the byte reading is 19,691, also under 20,000, so a reviewer
checking `ls -l` or a byte-counting `wc -m` sees no over-cap number either.

`/context` source status went `AGENTS.md status=truncated chars=42935` →
`AGENTS.md status=loaded chars=19466`, with `CLAUDE.md` reported `shadowed` in both
readings — the symlink families resolve to one loaded copy, so the trim cannot be
double-counted. The committed file is byte-identical to the measured draft
(sha256 `17a663d392b92c0b80a80cf4164c3d160bb4970c9b47fcde1370e076d7f23248`), so the
measurement still describes the shipped artifact.

### What was preserved vs compressed

**Byte-identical to the pre-edit snapshot — 1 region, 377 chars.** Nothing in it was
retyped or reworded:

| Region | chars | Treatment |
|---|---|---|
| H1 + top blockquote (the symlink families) | 377 | **byte-identical** |

**Compressed — every rule, table row, harness binding and CI-asserted string retained**,
each rule ending in a pointer to where the detail already lives:

| Region | orig → draft chars | Treatment |
|---|---|---|
| `## Document Funnel` | 9,170 → 5,477 | stage diagram and stage table tightened; all eleven funnel rules and the three CI-enforcement strings (rules 3, 9, 10) intact |
| `## Harness Adapter` | 5,141 → 3,486 | capability table tightened; every harness binding, both symlink families (four symlinks) and the `root-cause` / `investigator.md` gate binding intact |
| `## The /goal Orchestration Workflow` | 5,103 → 4,569 | kickoff prompt, `sub1`–`sub4` blocks and both phase tables tightened; the phase contract intact |
| `## Standing Orders` | 11,162 → 2,520 | collapsed to one line per rule `§1`–`§6` plus `→` pointers |
| `## Repository Structure` | 4,863 → 254 | load-bearing lines plus a `README.md` pointer |
| `## Development Commands` | 306 → 298 | the real commands kept |
| `## Security` | 926 → 603 | one line per rule |
| `## codegraph` | 3,485 → 1,200 | routing rule, install/init and the CLI twins kept; explanation delegated to the stage-4 PRD |

No rule was deleted and no pointer was left unresolved: every `→ docs/…`, `README.md` and
`PRD.md` target in the trimmed file was checked to exist and to carry the fact delegated
to it, and `bash scripts/verify-clone.sh` re-confirms the doctrine paths are tracked.

### The 19,791-char arithmetic — why byte-exact preservation is impossible here

The four regions this repo regards as a cross-harness contract total:

```text
H1 + top blockquote        377 chars   (pre-edit snapshot)
## Document Funnel       9,170 chars   (pre-edit snapshot)
## Harness Adapter       5,141 chars   (pre-edit snapshot)
`/goal` cluster          5,103 chars   (pre-edit snapshot)
------------------------------
TOTAL (byte-protected)  19,791 chars
working budget          19,500 chars   (target ceiling, cap 20,000 minus headroom)
overrun if preserved       +291 chars
```

The protected regions **alone** are 291 chars more than the working budget, leaving
−291 chars for *Read First*, *Standing Orders*, *Repository Structure*, *Development
Commands*, *Security* and *codegraph*. Byte-exact preservation of all four is therefore
arithmetically impossible in this repo, and any claim that they survive byte-for-byte
would be false. The honest preservation statement is per region: the H1 + top blockquote
is byte-identical; the other three are **tightened, not retyped away** — every funnel
rule, table row, harness binding, symlink family and CI-asserted string is still present.

### Guard expectations recomputed, not relaxed

Three assertions elsewhere in the tree parse `AGENTS.md` and were invalidated by the
compression. Each was recomputed against the new file rather than loosened:

| Guard | Old expectation | New expectation |
|---|---|---|
| `AC-HRN-011` (`tests/unit/test_harness_neutrality.py`) | `/goal` occurrence lines `[183, 240, 242, 293, 295, 298]` | `[109, 145, 147, 196, 198, 201]` — still every occurrence outside a fence, so a dropped or added one fails |
| `AC-CG-001` / `AC-CG-002` (`tests/unit/test_codegraph_adoption.py`) | literal `one tool by design` / `without an MCP client` | `One MCP tool by design` / `Without an MCP client` — matched case-insensitively, still failing if the claim is removed |
| `AC-CG-003` (same file) | `CI or scripted` asserted **inside** `## codegraph` | asserted inside `## codegraph` **and** followed through its stage-4 PRD pointer, which now carries the full `CI or scripted` scope — deleting it from either file fails |

### The tripwire

`tests/unit/test_agents_md_budget.py` (unit tier) carries `AC-CTX-001` — `AGENTS.md` is
under the 20,000-char cap, in characters and in bytes — and `AC-CTX-002` — the harness
entry-point symlinks still resolve to `AGENTS.md` and are the same file. It is hermetic:
file reads and the stdlib only, no subprocess, no service import, no transport. The
failure message names the actual count, the cap, the lossy head-70/tail-20 middle
truncation and the remedy. This repo keeps no separate test-index file, so the tripwire is
registered here.

## Verification

Run from the repo root, 2026-09-21.

```bash
# Size in both readings. chars is the binding one.
# NB: this host sets LC_CTYPE=C, under which a bare `wc -m` counts BYTES (19,691,
# identical to `wc -c`). LC_ALL=C.UTF-8 or len() is required for the char count.
LC_ALL=C.UTF-8 wc -m AGENTS.md
# -> 19467 AGENTS.md
wc -c AGENTS.md
# -> 19691 AGENTS.md
python3 -c "t=open('AGENTS.md',encoding='utf-8').read(); print(len(t), len(t.encode()))"
# -> 19467 19691

# The cap this repo targets, read off the live prompt builder (constants + resolution only)
/app/venv/bin/python3 -c "import sys; sys.path.insert(0,'/opt/hermes-agent-staging'); \
from agent import prompt_builder as pb; print(pb.CONTEXT_FILE_MAX_CHARS, pb._get_context_file_max_chars(None))"
# -> 20000 20000

# Delivered through the REAL prompt builder: whole file present, no truncation warning
/app/venv/bin/python3 - <<'PY'
import sys; sys.path.insert(0, "/opt/hermes-agent-staging")
from agent import prompt_builder as pb
raw = open("AGENTS.md", encoding="utf-8").read()
out = pb.build_context_files_prompt(cwd=".", context_length=None)
warn = [w for w in (pb.drain_truncation_warnings() or []) if "TRUNCATED" in w]
print("chars", len(raw), "| delivered", len(out), "| verbatim", raw in out, "| warnings", warn)
PY
# -> chars 19467 | delivered 19577 | verbatim True | warnings []

# The tripwire, and the two guard files whose expectations the trim recomputed
python3 -m pytest tests/unit/test_agents_md_budget.py tests/unit/test_harness_neutrality.py \
  tests/unit/test_docs_template.py tests/unit/test_codegraph_adoption.py -q

# The full tier, via the repo's own runner
bash tests/run.sh
```

Expected: `LC_ALL=C.UTF-8 wc -m` reports 19,467 against `wc -c`'s 19,691; the cap probe
prints `20000 20000`; the delivery probe prints `verbatim True` with an empty warning
list; the four guard files end `39 passed`; `bash tests/run.sh` ends
`RESULT: PASSED` with **122 passed** in the unit tier (120 before this change, plus
`AC-CTX-001` and `AC-CTX-002`) and 16 passed in the integration tier.

## What Works

- `AGENTS.md` is under the cap in both readings — 19,467 chars / 19,691 bytes against a
  20,000-char cap, with 533 chars (2.7%) of headroom
- The real prompt builder delivers the file verbatim and queues **zero** `TRUNCATED`
  warnings, down from one at 42,936 chars; delivered chars went **18,372 → 19,577** while
  the file got 23,469 chars smaller, because the whole file now arrives instead of a
  head-70%/tail-20% slice
- `/context` reports `AGENTS.md status=loaded` (was `status=truncated`) with `CLAUDE.md`
  `shadowed`, so the four harness entry points still resolve to one loaded copy
- The H1 + top blockquote is byte-identical to the pre-edit snapshot (sha256
  `ff059aa1bd17b8a4…`, 377 chars), and every tightened region keeps all eleven funnel
  rules, the three CI-enforcement strings (rules 3, 9, 10), the two Harness Adapter tables
  — every harness binding: Hermes, Claude Code, Copilot/other, the generic fallback, plus
  the opencode and DeepSeek/OpenAI-compatible rows — and the `/goal` phase contract
- Every pointer the trim left behind resolves and carries the fact delegated to it —
  `docs/`, `docs/prd/`, `PRD.md` and `README.md` targets were checked one by one
- The three guard expectations the trim invalidated were recomputed from the new file
  (AC-HRN-011 line list, AC-CG-001/002 spellings, AC-CG-003 pointer scope) and all three
  still fail on a removed claim
- `AC-CTX-001`/`AC-CTX-002` make a future regression loud instead of silent — the cap
  breach and a forked entry-point symlink both fail the unit tier

## What Fails

- **Byte-exact preservation was impossible in this repo.** The four protected regions
  total 19,791 chars against a 19,500-char working budget, so only the H1 + top
  blockquote is byte-identical; the *Document Funnel*, *Harness Adapter* and `/goal`
  clusters are tightened wording. Any statement that all contract regions survive
  byte-for-byte is false for this repo.
- **Only one region is byte-identical, and nothing guards the rest byte-for-byte.** The
  per-region sha256s recorded here (H1 + top blockquote `ff059aa1…`; *Document Funnel*
  `945bac5a…`; *Harness Adapter* `91584049…`; `/goal` `d1a0d8a9…`; *Standing Orders*
  `4496ed57…`; *Repository Structure* `96705ab9…`; *Development Commands* `c99d1374…`;
  *Security* `62429f04…`; *codegraph* `0ee75c2d…`) are an audit reference, not an
  assertion — a later reflow of a contract region passes the tests that exist.
- **The cap is host-dependent.** The tripwire asserts the 20,000-char flat floor. A host
  profile that pins a *lower* `context_file_max_chars` truncates a file this test passes —
  the guard reads the repo, not host state.
- **A bare `wc -m` is a byte count on this host.** `LC_CTYPE=C` is set, so `wc -m AGENTS.md`
  prints 19,691 — the same output as `wc -c` — while the file carries 115 non-ASCII
  characters and the two readings differ by 224. A char check that reads a bare `wc -m` is
  really a byte check.
- **Headroom is thin — 533 chars (2.7% of the cap).** That is roughly 15 lines of prose. A
  few appended Standing Orders re-cross the cap; the tripwire reports that, it does not
  prevent it.

## Resolution

- **Byte-exact preservation impossible:** sum the preserve-set against the target budget
  *before* promising byte-identity, and state per region which are byte-identical versus
  compressed — this doc's two tables are that statement. Never claim uniform
  preservation; the 19,791-vs-19,500 arithmetic is the reason.
- **No byte-identity guard on the compressed regions:** treat the recorded sha256s as the
  audit reference for a manual diff, and after any edit to a contract region re-run the
  behavioural guards that do exist —
  `python3 -m pytest tests/unit/test_harness_neutrality.py tests/unit/test_codegraph_adoption.py
  tests/unit/test_funnel_structure.py -q` — plus `bash scripts/verify-clone.sh` for the
  symlink and tracked-path bindings. A future author who wants the byte half adds a
  snapshot-hash test; it is not claimed here.
- **Host-dependent cap:** read the effective value off the live host before quoting a
  number — the `CONTEXT_FILE_MAX_CHARS` probe above — and pin `context_file_max_chars`
  explicitly where the repo must not depend on the model window.
- **`wc -m` counts bytes under `LC_CTYPE=C`:** run it as `LC_ALL=C.UTF-8 wc -m`, or measure
  in Python with `len(text)` — which is what the tripwire does. Never trust a bare `wc -m`
  on a host whose locale is not UTF-8.
- **Thin headroom:** when adding a Standing Order or a funnel rule, collapse an existing
  line to a pointer rather than appending. The tripwire fails the unit tier before the
  file ships.

## Verdict

**partial** — The trim verifies end to end: the file reaches the prompt byte-for-byte
under the cap (19,467 chars / 19,691 bytes) with zero truncation warnings, the delivered
block grew from 18,372 to 19,577 chars, every tightened region retains its rules and
resolvable pointers, and a hermetic unit tripwire now fails loudly on both a cap breach
and a forked entry-point symlink. The open limits are that this repo cannot preserve its
contract regions byte-for-byte (19,791 chars of preserve-set against a 19,500-char
budget), that nothing guards those regions byte-for-byte, and that 533 chars of headroom
is thin for a file that grows by accretion.
