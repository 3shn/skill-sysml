# sysml — SysML v2 Systems-Engineering Co-Pilot (Claude Code plugin)

An AI-native SysML v2 co-pilot. It authors valid **textual SysML v2** (`.sysml`), grounds every
type/unit in the standard library (ISQ, SI, …) instead of inventing them, and validates with the
**real SysML v2 Pilot compiler** in a self-correcting loop so the output actually compiles.

## What's inside

```
sysml/
├── .claude-plugin/plugin.json     # plugin manifest (auto-loads as `sysml@skills-dir`)
├── .mcp.json                      # declares the `sysml` MCP server
├── skills/sysml-copilot/          # the co-pilot skill (SKILL.md + references + examples)
└── mcp-server/                    # the MCP server (validate + library introspection)
    ├── server.py                  # stdio MCP server (run via `python3`)
    ├── library_index.py           # name→element index over the standard library
    ├── java/SysmlValidatorServer.java   # warm Pilot-kernel validator (stdin/stdout JSON)
    └── setup.sh                   # downloads the kernel jar + compiles the validator
```

## MCP tools

- `validate_sysml_file(content | path, context_paths?)` → `{ok, diagnostics:[{line, column, severity, code, syntax, message}]}`
- `query_library(query, limit?)` → ranked standard-library elements with qualified names
- `get_library_element(qualified_name)` → an element's declaration excerpt

## Prerequisites & setup

- **Java 21+** and a **python3 (>=3.10)** on `PATH`. The MCP server is **stdlib-only** — no Python
  dependencies to install, no venv, no `uv`.
- The SysML v2 standard library (clone `Systems-Modeling/SysML-v2-Release`).
- The Pilot kernel fat jar (downloaded automatically by `setup.sh`).

```bash
# one-time: fetch the kernel jar and compile the validator
mcp-server/setup.sh
```

Configure paths via env if you need to override the defaults (which land in plugin-local `.runtime/`):

```bash
SYSML_LIBRARY_PATH=mcp-server/.runtime/sysml.library
SYSML_KERNEL_JAR=mcp-server/.runtime/jupyter-sysml-kernel-0.59.0-all.jar
```

## Launch configuration (`.mcp.json`)

The MCP server is **stdlib-only** and launched directly by a system `python3` (no venv, no `uv` — those
caused handshake timeouts `-32000` when deps were resolved at launch). The `.mcp.json` uses
`${CLAUDE_PLUGIN_ROOT}`-relative paths so the plugin is portable and works immediately after
running `setup.sh`.

Run `mcp-server/setup.sh` once (downloads the kernel jar if missing, compiles the Java validator),
launch Claude Code from the repo root, then `/reload-plugins` and verify `/plugin` shows `sysml`
connected. The Java validator also auto-compiles on first use if `setup.sh` wasn't run.

## Notes

- The validator runs as a **warm process**: the JVM + 94-file library load happens once, then
  validations run in well under a second. Cold-starting per call would be unusable in a loop.
- The full standard library and the kernel jar are **referenced by path**, not vendored — they are
  large and carry the upstream copyright-holders' license. Only small grounding assets (curated
  syntax reference, BNF grammar, example models) are bundled in the skill.
