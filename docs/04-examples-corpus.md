# 04 — Examples Corpus

## What

The examples deliverable: 15 immutable raw sources in `kb/raw/` (11 YouTube
transcripts of autoresearch-in-practice + 4 articles: upstream `program.md`
reference, template research conclusions, MCP-service research conclusions, and
the CodeGraph MCP code-intelligence evidence) and 21 synthesized layer-2 pages in
`kb/` (11 concepts, 4 entities, 6 comparisons), with integrity tests that keep the
corpus trustworthy. One superseded raw source — the pre-correction CodeGraph v1 —
sits in `kb/_archive/`.

## Why

The repo's second stated purpose: *"extensive examples to achieve objectives."*
Humans must set expectations from the template; agents must orient in `kb/`
before acting. Raw sources are immutable (add-only) and layer-2 pages are
llm-wiki-written — so the corpus needs machine-checked integrity (sha256 stamps,
index coverage, wikilink resolution, tag taxonomy) rather than trust
(PRD 04, grounded in `kb/comparisons/autoresearch-video-corpus.md`).

## How

- **Raw sources (`kb/raw/`):** `transcripts/*.txt` (11) and `articles/*.md` (4),
  each with YAML frontmatter `source_url` (http(s)), `ingested` (ISO date),
  `sha256` over `body.strip()` (the STRIP convention used at ingest). Add-only,
  enforced by `sources-readonly.yml`. The fourth article,
  `codegraph-mcp-code-intelligence.md`, is ingested 2026-09-16 and added to this
  KB 2026-09-18 — it carries the CodeGraph MCP evidence and is what moved the
  counts from 13 raw / 14 layer-2 to 15 raw / 21 layer-2.
- **Layer-2 pages (`kb/`):** 11 concepts, 4 entities, 6 comparisons — each with
  `sources:` frontmatter pointing to raw paths, `^[raw/...]` footers, tags from
  the SCHEMA taxonomy, and wikilinks to sibling pages.
- **Integrity tests (new):** `test_corpus_integrity.py` (AC-EXC-001..003, 011 —
  every raw file's frontmatter/keys/sha; counts ≥11 transcripts / ≥2 articles;
  value shape) and `test_kb_synthesis.py` (AC-EXC-021..024 — page counts,
  index coverage/no orphans, wikilink resolution, sources/tag traceability).

## Verification

```bash
ls kb/raw/transcripts/*.txt | wc -l && ls kb/raw/articles/*.md | wc -l
# 11 / 4  -> 15 raw sources; 1 further superseded source under kb/_archive/
for d in concepts entities comparisons queries; do echo "$d $(ls kb/$d/*.md | wc -l)"; done
# concepts 11, entities 4, comparisons 6, queries 0  -> 21 layer-2 pages
python3 -m pytest tests/unit/test_corpus_integrity.py tests/unit/test_kb_synthesis.py -v
# 8 passed (AC-EXC-001..003, 011, 021..024) in 0.02s
python3 - <<'EOF'
import hashlib, pathlib, re
n = ok = 0
for p in pathlib.Path("kb/raw").rglob("*"):
    if p.suffix not in (".md", ".txt"):
        continue
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", p.read_text(), re.S)
    stamp = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)["sha256"].strip()
    n += 1
    ok += stamp == hashlib.sha256(m.group(2).strip().encode()).hexdigest()
print(f"{ok}/{n} sha256(body.strip()) matches")
EOF
# 15/15 sha256(body.strip()) matches
bash tests/run.sh
# unit 68 passed | integration 16 passed | e2e SKIPPED (needs a running service) | RESULT: PASSED
bash tests/run.sh --with-e2e        # against the compose stack
# unit 68 | integration 16 | e2e ok 1..4 | RESULT: PASSED
```

All commands above were run 2026-09-18. The corpus tests are read-only,
stdlib-only, and fast — they run on every CI `unit` job, so a sha drift or a new
orphaned page fails the PR.

## What Works

- All 15 raw sources sha-verified against the STRIP convention — recomputing
  `sha256(body.strip())` over every file under `kb/raw/` on 2026-09-18 returns
  15/15 matches, and AC-EXC-001/AC-EXC-002 enforce the same at test time.
- All 21 layer-2 pages indexed in `kb/index.md`; no orphans; no broken wikilinks;
  every page traces to `raw/`; all tags are in the SCHEMA taxonomy
  (AC-EXC-022..024).
- Count checks are lower-bounded (≥) so the corpus can grow without breaking CI.
- The tests catch real drift: during the 2026-09-04 run they flagged a concurrently
  ingested `kb/raw/articles/mcp-autoresearch-service-conclusions.md` whose sha256
  stamp mismatched its body. The file was re-stamped and is now committed and
  verifies clean — the gate worked as designed.
- The CodeGraph ingest is committed: commit `0e96572` (PR #9) tracks
  `kb/raw/articles/codegraph-mcp-code-intelligence.md`, its three layer-2 pages
  (`kb/concepts/agent-code-graph-search.md`, `kb/entities/codegraph.md`,
  `kb/comparisons/codegraph-vs-graphify.md`), and the archived v1 under
  `kb/_archive/raw/`, so `git ls-files` and the working tree agree at 15 raw
  sources and 21 layer-2 pages (11 concepts / 4 entities / 6 comparisons).

## What Fails

- **Not a content checker:** the tests verify integrity (stamps, links, tags),
  not the accuracy of the synthesized claims — claim correctness still comes
  from the llm-wiki workflow + the `sources:` traceability.

## Resolution

- **Committed CodeGraph ingest:** resolved by commit `0e96572` (PR #9) — the
  article `kb/raw/articles/codegraph-mcp-code-intelligence.md`, its three layer-2
  pages (`kb/concepts/agent-code-graph-search.md`, `kb/entities/codegraph.md`,
  `kb/comparisons/codegraph-vs-graphify.md`), and `kb/_archive/raw/` are tracked,
  so the committed corpus and the working tree both read 15 raw / 21 layer-2.
- **Not a content checker:** by design — keep claim review in the llm-wiki
  stage; AC-EXC-024 verifies traceability, which is what makes review possible.

## Verdict

**works** — the corpus is ingested, synthesized, cataloged, and now machine-gated:
8 integrity tests pass over 15 sha-verified raw sources and 21 indexed layer-2
pages. The CodeGraph ingest is committed (commit `0e96572`, PR #9), so the
tracked corpus and the working tree both read 15 raw / 21 layer-2.
