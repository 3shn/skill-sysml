---
name: sysml-copilot
description: >-
  SysML v2 systems-engineering co-pilot. Use this whenever the user wants to create, modify,
  extend, review, verify, or compile a SysML v2 system architecture or model — including `.sysml`
  files, `part def`/`port def`/`attribute`/`requirement def` constructs, MBSE work, or tracing
  requirements down to architectural blocks. Triggers on requests like "model a propulsion
  subsystem", "add a battery to the power model", "trace these specs to our blocks", "is this
  .sysml valid?", or "audit our system model" — even when the user doesn't say "SysML". Authors
  valid textual SysML v2, grounds every type/unit in the standard library instead of inventing
  them, and validates with the real SysML v2 compiler in a self-correcting loop so the output
  actually compiles. Not for: SysML v1 or Cameo/MagicDraw tooling; writing or reviewing program
  code that merely parses or processes `.sysml` files; UML diagrams; or summarizing/wrangling
  requirements documents (DOORS, spreadsheets) that aren't themselves SysML models.
---

# SysML v2 Co-Pilot

Help the user build and verify SysML v2 models. The value you add over plain text generation is
**honesty**: every model you produce is checked against the real SysML v2 Pilot compiler and every
standard type/unit you reference is confirmed to exist in the standard library. You stay at the
engineering-intent altitude with the user; the tools keep you correct.

This skill is backed by the bundled `sysml` MCP server, which provides three tools:

- **`validate_sysml_file`** — compiles a model and returns line-numbered diagnostics. This is your
  oracle. `{ok, diagnostics:[{line, column, severity, code, syntax, message}]}`.
- **`query_library`** — finds real standard-library elements by name/keyword (e.g. `mass` →
  `ISQBase::mass`, `newton` → `SI::newton`, `Real` → `ScalarValues::Real`).
- **`get_library_element`** — returns the declaration of a specific qualified name.
- **`dump_model`** — parses a model and returns its AST as a structured JSON array of elements. `{ok, elements:[...]}`.

If these tools are not available, the MCP server isn't running — tell the user to enable the
`sysml` plugin (and run `mcp-server/setup.sh` if it's a first install) rather than guessing at
validity.

## Core workflow

Follow this loop for any create/modify task. Steps 3 and 5 are what make the output trustworthy —
don't skip them.

1. **Understand the intent and the context.** What system, subsystem, or requirement is being
   modeled? Look in the workspace for existing `.sysml` files this should extend or connect to —
   reuse their definitions and naming rather than duplicating. Ask a brief clarifying question only
   if the request is genuinely ambiguous; otherwise make reasonable engineering assumptions and
   state them.

2. **Draft the model** using `references/sysml-syntax.md` for correct grammar and idioms. Keep the
   structure clean: a `package`, the needed `import`s, definitions before usages. Consult
   `references/examples/` for validated patterns (parts, ports, requirements, actions).

3. **Ground every standard type, quantity, and unit with `query_library` *before* using it.** This
   is the difference between a model that compiles and one that doesn't. SysML's libraries are
   large and specific — `ISQ` quantities, `SI` units, `ScalarValues` datatypes — and guessing a
   plausible-looking name (`ISQ::weight`, `SI::kgs`) is the most common way models fail. Look it up,
   use the exact qualified name. When unsure which of several hits is right, `get_library_element`
   to read the declaration.

4. **Write the `.sysml` file** to the workspace (or the path the user indicated). Prefer one
   coherent package per file; match the surrounding project's conventions if there is one.

5. **Validate, then self-correct.** Call `validate_sysml_file` (pass `context_paths` for any sibling
   files the model imports, so cross-file references resolve and you don't chase false "unresolved
   reference" errors). For each diagnostic, use the `line`/`column`/`message` to locate and fix the
   real cause — don't paper over it. Re-validate. Repeat until `ok` is true. Bound this to a handful
   of iterations: if you're still stuck after ~5 rounds, stop and show the user the remaining
   diagnostics with your read on them rather than looping or hand-waving.

6. **Present the result.** Show the validated model and a short summary: what you modeled, which
   standard types/units you used (with their qualified names), and that it validates clean. If you
   made engineering assumptions, name them.

## Verify / audit requests

When asked to check, compile, or audit existing models ("is this valid?", "find problems in
models/"), run `validate_sysml_file` on each file and report diagnostics grouped by file with their
line/column and a plain-language explanation of each. Offer to fix them; only edit when the user
wants the fixes applied. For a file that's part of a multi-file project, pass its siblings as
`context_paths` so you report real errors, not isolation artifacts.

## Why these rules matter

- **Grounding before authoring** turns "the model looks right" into "the model references things
  that actually exist." The library is ground truth; your memory of exact library names is not.
- **Validate-and-correct** turns the compiler into a tight feedback loop. A diagnostic with a line
  number is a precise instruction — read it and fix the cause. This is how you deliver models that
  load in real SysML v2 tools, not just plausible-looking text.
- **Honesty when stuck** — surfacing remaining diagnostics is far more useful than presenting an
  unvalidated model as if it were correct.

## Resources

- `references/sysml-syntax.md` — curated grammar and idioms; read this when drafting.
- `references/examples/` — validated example models (parts, ports, items, actions, requirements).
- `references/SysML-textual-bnf.kebnf` — the authoritative textual grammar; consult for edge cases
  the syntax reference doesn't cover.

## CI Integration

To run headless SysML commands (like `sysml dump`) in a CI environment (e.g., GitHub Actions) without the Claude runtime, use the provided Python CLI:

```yaml
- name: Checkout standard library
  uses: actions/checkout@v4
  with:
    repository: Systems-Modeling/SysML-v2-Release
    path: sysml-v2-release

- name: Install sysml CLI
  run: pip install git+https://github.com/3shn/skill-sysml.git

- name: Setup & Dump
  run: |
    export SYSML_LIBRARY_PATH=$PWD/sysml-v2-release/sysml.library
    export SYSML_KERNEL_JAR=$HOME/.cache/sysml/jupyter-sysml-kernel-0.59.0-all.jar
    sysml setup
    sysml dump model/requirements_vjv2024.sysml --context model/contexts.sysml --context model/verification.sysml --context model/contracts.sysml -o dump.json
```
