---
name: coding-agents-docs-guideline
description: Documentation template and style guide for vanilla-n8n docs/ — enforces consistent structure, numbering, and writing conventions when creating or editing files in docs/.
---

<!-- Vendored from https://github.com/bachkukkik/coding-agents-docs-guideline/blob/f5d1535db000afb1f33794821e8d32b086d75f5f/SKILL.md at commit f5d1535 (2026-10-16), with examples/. No upstream LICENSE file exists; the repository is owner-authored by the same owner as this repo (bachkukkik) and redistributed here as part of the template. This is the funnel stage-6 gate. -->

## Activation

Load and apply this skill whenever you are asked to:

- Create a new file in `docs/`
- Edit or update an existing file in `docs/`
- Review whether documentation is complete or correct

---

## Template Structure

Every doc in `docs/` must follow this exact section order. No sections may be omitted, reordered, merged, or renamed.

```markdown
# NN — Title

## What

## Why

## How

## Verification

## What Works

## What Fails

## Resolution

## Verdict
```

### Section definitions

| Section | Content | Length |
|---------|---------|--------|
| `## What` | One-sentence definition of the component or concern. What it is, not why it exists. | 1–2 sentences |
| `## Why` | Reasons this component exists or why these choices were made. Use bullet list when listing multiple reasons. | Short paragraph or bullets |
| `## How` | Technical details: configuration, code snippets, env vars, tables, sub-headings. This is the longest section. | As needed |
| `## Verification` | Concrete shell commands or steps to confirm the thing works. Every command must be runnable. | Code block(s) |
| `## What Works` | Bullet list of confirmed working behaviors. | Bullet list |
| `## What Fails` | Bullet list of known issues, limitations, or edge cases. Use **bold** for the issue name. | Bullet list |
| `## Resolution` | How to fix or work around each failure listed in "What Fails". One resolution per failure, same order. | Bullets or short paragraphs |
| `## Verdict` | One-sentence assessment of the component's overall fitness. State what works, what doesn't, and the net conclusion. | 1–2 sentences |

---

## File Naming and Numbering

### Format

```
NN-slug.md
```

- `NN` — zero-padded two-digit integer (01, 02, … 09, 10, 11, …)
- `slug` — lowercase kebab-case, 1–3 words describing the component

### Rules

1. **Never renumber existing docs.** File numbers are permanent references. Gaps are intentional.
2. **Fill gaps for new topics that belong conceptually between existing docs** (e.g. 06 is currently missing — use it for a topic that fits between 05 and 07).
3. **Use the next available number** for entirely new topics that don't belong in a gap.
4. **Current files:** 01 through 12 (06 is missing). Next new doc after 12 → 13.

### Title format

```
# NN — Title
```

- `NN` must match the file number exactly.
- Title is title-case, 1–5 words, names the component or concern.
- Separator is ` — ` (space, em dash, space).

---

## When to Create vs. Update

### Create a new doc when:

- Documenting a new service or container not yet covered
- Documenting a new cross-cutting concern (e.g. logging, CI, secrets management)
- The existing closest doc would become a different topic if the content were added to it

### Update an existing doc when:

- A service configuration changes
- A known issue is discovered or resolved
- Verification steps need correction
- Additional "What Fails" / "Resolution" pairs are needed

### Never:

- Merge two docs into one without explicit instruction
- Split one doc into two without explicit instruction
- Create a doc for a concern that is already covered in another doc — update the existing one

---

## Writing Style

### Voice and tense

- **Present tense, active voice.** Write "RustFS runs as UID 10001", not "RustFS was configured to run as UID 10001".
- **Third person for components.** "mitmproxy intercepts HTTPS traffic", not "we configure mitmproxy to intercept".
- **Direct imperatives for commands and steps.** "Run `make init-certs` before first startup."

### Density

- No preamble. The first sentence of each section is content, not a transition.
- No filler phrases: "It is important to note that…", "Please be aware that…", "In order to…"
- Every sentence carries a fact, constraint, or action. Delete sentences that don't.

### Formatting

- **Tables** for structured multi-column data: service configs, env vars, API parameters, before/after comparisons.
- **Code blocks** with language tags for all shell commands, Python, SQL, YAML, and config snippets.
- **Bold** for issue names in "What Fails" bullets: `- **Volume ownership:** RustFS fails if…`
- **Sub-headings** (`### Sub-heading`) inside `## How` are allowed when a section covers multiple distinct mechanisms.
- No emojis. No decorative horizontal rules inside sections.

### Length guidance

- `## What` — 1–2 sentences. If you need more, the scope is too broad.
- `## Verdict` — 1–2 sentences. Summarize the net assessment. Do not restate every point from the doc.
- `## How` — no limit, but prefer tables and code blocks over prose where structure exists.

---

## How to use this skill

1. **Identify the task** from the request (create new doc, update existing doc, review doc)
2. **Load the appropriate example file** from the `examples/` directory:
    - `examples/new-service-doc.md` — Full worked example of documenting a service or container. Use when creating a new doc for a single service.
    - `examples/cross-cutting-concern.md` — Full worked example of documenting a concern that spans multiple services (logging, CI, secrets, networking, monitoring). Use when creating a new doc that is not tied to one service.
    - `examples/updating-existing-doc.md` — Guidelines and before/after examples for updating an existing doc. Use when editing any existing doc in `docs/`.
3. **Follow the template structure** (eight sections, exact order) and use the loaded example as a reference for tone, density, and formatting.
