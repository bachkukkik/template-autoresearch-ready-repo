---
title: Command Registry
created: 2026-11-16
updated: 2026-11-16
type: concept
tags: [agentic, architecture, doctrine]
sources: [raw/articles/2026-11-16-command-registry.md]
confidence: medium
---

# Command Registry

A command registry is the one file where every user-facing command is declared: its
name, a one-line help, a typed argument schema, what it costs, and the argv that
reaches the real implementation. Every surface — the CLI, a generated `--help`, a
catalog listing, a REST route, an MCP tool — is derived from those declarations.
The point is not tidiness. It is that **a surface cannot silently disagree with the
others**, because it was never written separately.

## One declaration, N surfaces

The failure this prevents is cheap to produce and expensive to notice: four
surfaces written by hand accept four slightly different value sets, and one of them
refuses a value the system already prices. Deriving every surface from one
declaration makes that disagreement a type error rather than a support ticket.

Two properties follow, and both are testable without a network:

* the catalog cannot name a tool that does not exist, and every flag it declares
  appears in **that tool's own** `--help` — so a renamed flag fails in CI, not in an
  overnight run;
* the generated `--help` contains exactly the declared flags, so a command's
  documentation is its schema rather than a second copy of it.

## Cost is the exposure function

Exposure is computed, not allowlisted a second time. Three booleans — does it
mutate, does it execute the target's code, does it read the **host** rather than
this deployment — decide whether a command may ever reach an injected surface
(HTTP, MCP). A mutating command has no HTTP route *at all*; the refusal is
structural, so it cannot be forgotten at a call site.

The hard part is marking the flags honestly. A flag name lies: `--dry-run` can
still stamp state before it branches, and `--check` can still execute the target's
code. The rule is to mark from the implementation, one command at a time, and to
declare the *maximum* cost — a command that can write is mutating even when one
mode does not.

## No orphan entry points

A repository accumulates runnable files: a tool, a generator, a pruner. Each is an
argv nobody enumerated, and the next request against one becomes a one-off script —
which is exactly what a "resolve every request to a command" rule forbids. The
check is mechanical: every runnable file under the tool roots is either named by a
catalog command or sits on an allowlist that states why it is not one. A stale
allowlist entry fails too, and a synthetic orphan is fed to the check so a green
run means something.

Two design choices keep it honest:

* **runnability** — a `__main__` guard, a `.sh`, a shebang — defines an entry point,
  not the file extension. A library module cannot be an ad-hoc script, so it cannot
  be an orphan, and the exception list stays short enough to read;
* the **detector's own boundary** is pinned by a test, so "we allowlisted it" cannot
  quietly become "we allowlisted the directory".

The rule needs all three pieces to be operational: an **order** in the agent
instruction file naming the catalog, a **procedure** an agent is handed (catalog →
describe → run; nothing fits → entry + test by PR, first), and the **check**. A
rule without a test is prose; a test without a negative control passes vacuously.

## Where it goes wrong

* Prose restating a tool's flags — the drift is silent and nothing fails.
* Inferring cost from flag names — see `--dry-run` above.
* Accepting a **path** where a declared name belongs: a remote caller then aims the
  measurement at a checkout of its choosing. Accept the name, resolve it, refuse
  the rest before a child starts.
* Scanning every `.py` and allowlisting the libraries — the exception list grows
  until the check means nothing.
* Declaring a surface that does not exist. If the catalog says `api` and no route
  exists, the catalog is a lie; say `cli` and let the derivation carry the day a
  route lands.

## In this repo

`autoresearch/commands/registry.py` declares 17 commands in four groups (`engine`,
`target`, `supervisor`, `commands`) plus the engine passthrough;
`autoresearch/bin/autoresearch` is the CLI; `AGENTS.md` standing order 8 states the
rule, `.agents/skills/repo-commands/SKILL.md` the procedure, and
`tests/unit/test_commands_rule.py` the check (`AC-CMD-009..012`). REST and MCP are
deliberately deferred — the service is job-shaped and policy-bounded, and a
synchronous command route would be a second execution path beside it — so the
generated surface tuple is `('cli',)` and `exposeable()` already refuses every
command whose cost would forbid an injected surface. See
[[target-profile-contract]] for the names-not-paths rule the `target` group enforces,
[[harness-portability]] for why the procedure lives in a repo skill rather than one
harness's mechanism, and [[document-funnel-doctrine]] for the order → skill → check
shape this page's rule copies.

Confidence is `medium`: the ported half is verified by its own tests, but the
downstream record's failure modes are self-reported and no injected surface exists
here yet to prove the refusal end to end.
