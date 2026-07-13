#!/usr/bin/env bash
# One-time setup for the sysml MCP server. Idempotent — safe to re-run.
#   1. Provision the SysML v2 Pilot kernel fat jar     -> .runtime/  (curl, no auth)
#   2. Provision the SysML v2 standard library         -> .runtime/sysml.library (shallow git clone)
#   3. Compile the warm validator server against the jar.
# Everything lands in a plugin-local `.runtime/` (gitignored), so no machine-specific paths and
# nothing to clean up outside the plugin. Requires: java/javac 21+, python3 >=3.10, curl, git, unzip.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME="${SYSML_RUNTIME:-${XDG_CACHE_HOME:-$HOME/.cache}/sysml-copilot/0.59.0}"
KERNEL_VERSION="${KERNEL_VERSION:-0.59.0}"
KERNEL_RELEASE="${KERNEL_RELEASE:-2026-04}"
JAR="${SYSML_KERNEL_JAR:-$RUNTIME/jupyter-sysml-kernel-${KERNEL_VERSION}-all.jar}"
LIBRARY_PATH="${SYSML_LIBRARY_PATH:-$RUNTIME/sysml.library}"
CLASSES="${SYSML_VALIDATOR_CLASSES:-$RUNTIME/validator-classes/0.4.2}"
PILOT_REPO="Systems-Modeling/SysML-v2-Pilot-Implementation"
LIBRARY_REPO="Systems-Modeling/SysML-v2-Release"
LIBRARY_COMMIT="${SYSML_LIBRARY_COMMIT:-9baca5908ca28b53da085de69336fde48420ea8f}"

for tool in java javac python3 curl git unzip; do
  command -v "$tool" >/dev/null || { echo "ERROR: '$tool' required on PATH"; exit 1; }
done
echo "Using python3: $(command -v python3) ($(python3 --version 2>&1))"
mkdir -p "$RUNTIME"

# 1. Kernel jar — public release asset, fetched with curl (no GitHub auth needed).
if [[ ! -f "$JAR" ]]; then
  echo "Provisioning kernel jar (release ${KERNEL_RELEASE}, v${KERNEL_VERSION})..."
  tmpdir="$(mktemp -d)"
  url="https://github.com/${PILOT_REPO}/releases/download/${KERNEL_RELEASE}/jupyter-sysml-kernel-${KERNEL_VERSION}.zip"
  curl -fL --retry 3 --no-progress-meter -o "$tmpdir/kernel.zip" "$url"
  unzip -o -q "$tmpdir/kernel.zip" -d "$tmpdir"
  cp "$tmpdir/sysml/jupyter-sysml-kernel-${KERNEL_VERSION}-all.jar" "$JAR"
  rm -rf "$tmpdir"
fi
echo "Kernel jar: $JAR"

# 2. Standard library — shallow clone of the Release repo, copy the sysml.library subtree.
if [[ ! -d "$LIBRARY_PATH" ]]; then
  echo "Provisioning SysML v2 standard library (pinned to ${LIBRARY_COMMIT})..."
  tmpdir="$(mktemp -d)"
  git clone "https://github.com/${LIBRARY_REPO}.git" "$tmpdir/release"
  git -C "$tmpdir/release" checkout "$LIBRARY_COMMIT"
  cp -r "$tmpdir/release/sysml.library" "$LIBRARY_PATH"
  rm -rf "$tmpdir"
fi
echo "Standard library: $LIBRARY_PATH"

# 3. Compile the warm validator server against the jar.
echo "Compiling validator server -> $CLASSES"
mkdir -p "$CLASSES"
javac -cp "$JAR" -d "$CLASSES" $(find "$HERE/java" -name "*.java")

# server.py is stdlib-only (no pip deps); it launches with a system python3, instant and offline.
echo "Setup complete. Resources in $RUNTIME; the MCP server runs on any system python3 (>=3.10)."
