#!/usr/bin/env bash
# One-time setup for the sysml MCP server.
#   1. Ensure the SysML v2 Pilot kernel fat jar is present (downloads from GitHub if missing).
#   2. Compile the warm validator server against it.
# Re-running is safe and idempotent. Requires: java/javac 21+, gh (only if the jar must be downloaded).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KERNEL_VERSION="${KERNEL_VERSION:-0.59.0}"
KERNEL_RELEASE="${KERNEL_RELEASE:-2026-04}"
JAR="${SYSML_KERNEL_JAR:-$HOME/gh/3shn/skills/SysML_v2/runtime/sysml/jupyter-sysml-kernel-${KERNEL_VERSION}-all.jar}"
LIBRARY_PATH="${SYSML_LIBRARY_PATH:-$HOME/gh/Systems-Modeling/SysML-v2-Release/sysml.library}"
CLASSES="${SYSML_VALIDATOR_CLASSES:-$HERE/java/classes}"

command -v java >/dev/null  || { echo "ERROR: java 21+ required"; exit 1; }
command -v javac >/dev/null || { echo "ERROR: javac 21+ required"; exit 1; }

if [[ ! -f "$JAR" ]]; then
  echo "Kernel jar not found at: $JAR"
  command -v gh >/dev/null || { echo "ERROR: gh CLI needed to download the kernel jar"; exit 1; }
  mkdir -p "$(dirname "$JAR")"
  tmpdir="$(mktemp -d)"
  echo "Downloading jupyter-sysml-kernel-${KERNEL_VERSION}.zip from release ${KERNEL_RELEASE}..."
  gh release download "$KERNEL_RELEASE" \
    --repo Systems-Modeling/SysML-v2-Pilot-Implementation \
    --pattern "jupyter-sysml-kernel-${KERNEL_VERSION}.zip" --dir "$tmpdir"
  unzip -o -q "$tmpdir/jupyter-sysml-kernel-${KERNEL_VERSION}.zip" -d "$tmpdir"
  cp "$tmpdir/sysml/jupyter-sysml-kernel-${KERNEL_VERSION}-all.jar" "$JAR"
  rm -rf "$tmpdir"
fi
echo "Kernel jar: $JAR"

if [[ ! -d "$LIBRARY_PATH" ]]; then
  echo "WARNING: SYSML_LIBRARY_PATH not found: $LIBRARY_PATH"
  echo "  Clone Systems-Modeling/SysML-v2-Release and point SYSML_LIBRARY_PATH at its sysml.library dir."
fi

echo "Compiling validator server -> $CLASSES"
mkdir -p "$CLASSES"
javac -cp "$JAR" -d "$CLASSES" "$HERE/java/SysmlValidatorServer.java"

# The MCP server (server.py) is stdlib-only — no Python deps to install. The plugin's .mcp.json
# launches it with a system python3 directly, so startup is instant and offline. Nothing more to do.
echo "Setup complete. The MCP server runs on any system python3 (>=3.10); no venv needed."
