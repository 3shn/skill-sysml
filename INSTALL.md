# Install the SysML v2 co-pilot in any agent (not just Claude Code)

This plugin bundles a standard **stdio MCP server** (`mcp-server/server.py`, exposing
`validate_sysml_file`, `query_library`, `get_library_element`, `dump_model`) and a skill. The
"plugin" wrapper (`.claude-plugin/plugin.json`, `${CLAUDE_PLUGIN_ROOT}`) is Claude-Code-specific,
but the MCP server is universal — every MCP-capable agent (Codex, OpenCode, Cursor, Windsurf,
Antigravity, Factory/Droid, …) can run the same server. Only the config file/format differs.

## Layers and portability

| Layer | Portable? | How it travels |
|---|---|---|
| **MCP server** | Universal (MCP-over-stdio) | Same command; per-agent config snippet below |
| **Skill** (`sysml-copilot`) | No cross-agent skill standard | Put the guidance in the consuming repo's `AGENTS.md` (Codex/OpenCode/Cursor/Droid read it) |
| **Plugin wrapper** | Claude-Code-only | Ignore it elsewhere |

## Step 1 — path-stable launch (one-time per machine)

`pyproject.toml` exposes the server as a console script:

```toml
[project.scripts]
sysml     = "sysml_mcp.cli:main"     # headless dump/validate CLI
sysml-mcp = "sysml_mcp.server:main"  # the MCP server
```

Install it so `sysml-mcp` is on PATH:

```bash
pipx install <path-to-this-plugin>      # or: uvx --from <path-to-this-plugin> sysml-mcp
```

Then provision the compiler + standard library (one-time, needs Java 21+; downloads ~120 MB):

```bash
bash <path-to-this-plugin>/mcp-server/setup.sh
```

`setup.sh` fetches the SysML v2 Pilot kernel jar and the standard library into a plugin-local
`mcp-server/.runtime/` and compiles the validator. The server finds them there by default — **no
environment variables required**. (Override only for a custom resource location via
`SYSML_LIBRARY_PATH` / `SYSML_KERNEL_JAR`.)

(Skip packaging? Substitute `command: python3`, `args: ["<path-to-this-plugin>/mcp-server/server.py"]`
everywhere below — works locally, just not path-portable.)

## Step 2 — per-agent config

**Claude Code / Cursor / Windsurf / Antigravity / Droid** share the `mcpServers` JSON shape
(Claude: project `.mcp.json`; Cursor: `.cursor/mcp.json`; Windsurf:
`~/.codeium/windsurf/mcp_config.json`; Antigravity/Droid: their MCP settings JSON):

```json
{
  "mcpServers": {
    "sysml": {
      "command": "sysml-mcp"
    }
  }
}
```

(After `setup.sh`, no `env` block is needed — the server resolves resources from
`mcp-server/.runtime/`. Add `SYSML_LIBRARY_PATH` / `SYSML_KERNEL_JAR` only to override.)

**Codex CLI** — `~/.codex/config.toml` (or project `.codex/config.toml`):

```toml
[mcp_servers.sysml]
command = "sysml-mcp"
```
or: `codex mcp add sysml -- sysml-mcp` (env vars only needed to override the `.runtime/` defaults)

**OpenCode** — `opencode.json` (project root) or `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "sysml": {
      "type": "local",
      "command": ["sysml-mcp"],
      "enabled": true
    }
  }
}
```

## Step 3 — the skill, universally

No cross-agent skill format exists. Carry the operative guidance (SysML is the SSOT; validate
before commit; ground every type in the standard library) in the consuming repo's **`AGENTS.md`**,
which Codex/OpenCode/Cursor/Droid read automatically. Claude Code keeps the native skill + plugin.

## Why no single universal installer
As of 2026 there is no one config file all agents read — MCP standardized the *protocol* and
`AGENTS.md` the *instructions*, but each agent still owns its config path/format (JSON vs TOML,
`mcpServers` vs `mcp`). Practical "universal install" = one path-stable command (`sysml-mcp`) +
the per-agent snippets above (paste once per machine/agent).

Sources: [Codex MCP](https://developers.openai.com/codex/mcp) · [OpenCode MCP](https://opencode.ai/docs/mcp-servers/)
