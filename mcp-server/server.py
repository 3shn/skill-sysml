#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""sysml MCP server — the engine behind the SysML v2 co-pilot skill.

Stdlib-only: implements the MCP stdio JSON-RPC protocol directly, so it launches with any
system python3 — no venv, no `uv`, no dependency install, instant and offline. That makes the
plugin robust to launch and trivially distributable.

Tools exposed to the agent:
  • validate_sysml_file — compile a .sysml model and return line-numbered diagnostics
                          (backed by a *warm* SysML v2 Pilot kernel process).
  • query_library       — find real standard-library elements (ISQ::mass, SI::newton, …)
                          so the agent references existing types instead of inventing them.
  • get_library_element — fetch the declaration of a specific qualified name.

Configuration (env, normally set by .mcp.json):
  SYSML_LIBRARY_PATH      path to the sysml.library directory (Kernel/Systems/Domain Libraries)
  SYSML_KERNEL_JAR        path to jupyter-sysml-kernel-<ver>-all.jar (the Pilot fat jar)
  SYSML_VALIDATOR_CLASSES path to compiled SysmlValidatorServer classes (default: ./java/classes)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from library_index import LibraryIndex

HERE = Path(__file__).resolve().parent
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "sysml", "version": "0.3.0"}


def _env_path(name: str, default: str) -> str:
    return os.path.expanduser(os.environ.get(name, default))


# Resources are provisioned into a plugin-local `.runtime/` by mcp-server/setup.sh, so the
# defaults are machine-agnostic (relative to this file, not anyone's home dir). The env vars
# still override for custom installs / CI.
RUNTIME = HERE / ".runtime"
LIBRARY_PATH = _env_path("SYSML_LIBRARY_PATH", str(RUNTIME / "sysml.library"))
KERNEL_JAR = _env_path("SYSML_KERNEL_JAR",
                       str(RUNTIME / "jupyter-sysml-kernel-0.59.0-all.jar"))
CLASSES_DIR = _env_path("SYSML_VALIDATOR_CLASSES", str(HERE / "java" / "classes"))


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Library index (cheap; built lazily on first use)
# ---------------------------------------------------------------------------
_index: LibraryIndex | None = None


def _library() -> LibraryIndex:
    global _index
    if _index is None:
        _index = LibraryIndex(LIBRARY_PATH).build()
    return _index


# ---------------------------------------------------------------------------
# Warm validator process (the SysML v2 Pilot kernel, loaded once)
# ---------------------------------------------------------------------------
class _Validator:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def _ensure_compiled(self) -> None:
        if (Path(CLASSES_DIR) / "SysmlValidatorServer.class").exists():
            return
        Path(CLASSES_DIR).mkdir(parents=True, exist_ok=True)
        subprocess.run(["javac", "-cp", KERNEL_JAR, "-d", CLASSES_DIR,
                        str(HERE / "java" / "SysmlValidatorServer.java")],
                       check=True, capture_output=True, text=True)

    def _start(self) -> None:
        self._ensure_compiled()
        env = dict(os.environ, SYSML_LIBRARY_PATH=LIBRARY_PATH)
        self._proc = subprocess.Popen(
            ["java", "-cp", f"{CLASSES_DIR}{os.pathsep}{KERNEL_JAR}", "SysmlValidatorServer"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=env, text=True, bufsize=1)
        while True:
            line = self._proc.stdout.readline()
            if line == "":
                raise RuntimeError("validator process exited before becoming ready")
            if line.strip() == "READY":
                return

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def validate(self, target_path: str, context_paths: list[str]) -> dict:
        with self._lock:
            if not self._alive():
                self._start()
            self._proc.stdin.write("\t".join([target_path, *context_paths]) + "\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline()
            if line == "":
                self._proc = None
                raise RuntimeError("validator process died during validation")
            return json.loads(line)

    def dump(self, target_path: str, context_paths: list[str]) -> dict:
        with self._lock:
            if not self._alive():
                self._start()
            self._proc.stdin.write("DUMP\t" + "\t".join([target_path, *context_paths]) + "\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline()
            if line == "":
                self._proc = None
                raise RuntimeError("validator process died during dump")
            return json.loads(line)


_validator = _Validator()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def validate_sysml_file(content=None, path=None, context_paths=None) -> dict:
    context_paths = context_paths or []
    tmp = None
    try:
        if content is not None:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".sysml", delete=False, encoding="utf-8")
            tmp.write(content)
            tmp.close()
            target = tmp.name
        elif path is not None:
            target = os.path.abspath(os.path.expanduser(path))
            if not os.path.isfile(target):
                return {"ok": False, "diagnostics": [{"line": 0, "column": 0, "severity": "ERROR",
                        "code": "no-such-file", "syntax": False, "message": f"File not found: {target}"}]}
        else:
            return {"ok": False, "diagnostics": [{"line": 0, "column": 0, "severity": "ERROR",
                    "code": "bad-request", "syntax": False, "message": "Provide either 'content' or 'path'."}]}
        ctx = [os.path.abspath(os.path.expanduser(p)) for p in context_paths]
        return _validator.validate(target, ctx)
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


def dump_model(content=None, path=None, context_paths=None) -> dict:
    context_paths = context_paths or []
    tmp = None
    try:
        if content is not None:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".sysml", delete=False, encoding="utf-8")
            tmp.write(content)
            tmp.close()
            target = tmp.name
        elif path is not None:
            target = os.path.abspath(os.path.expanduser(path))
            if not os.path.isfile(target):
                return {"ok": False, "diagnostics": [{"line": 0, "column": 0, "severity": "ERROR",
                        "code": "no-such-file", "syntax": False, "message": f"File not found: {target}"}]}
        else:
            return {"ok": False, "diagnostics": [{"line": 0, "column": 0, "severity": "ERROR",
                    "code": "bad-request", "syntax": False, "message": "Provide either 'content' or 'path'."}]}
        ctx = [os.path.abspath(os.path.expanduser(p)) for p in context_paths]
        return _validator.dump(target, ctx)
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


def query_library(query: str, limit: int = 25) -> list:
    return _library().search(query, limit=limit)


def get_library_element(qualified_name: str):
    return _library().get(qualified_name)


TOOLS = [
    {
        "name": "validate_sysml_file",
        "description": (
            "Validate a textual SysML v2 model against the standard library and return diagnostics. "
            "Provide either `content` (raw .sysml text) or `path` (an existing .sysml file). "
            "`context_paths` lists sibling .sysml files the model imports, so cross-file references "
            "resolve without false 'unresolved reference' errors (only the target's diagnostics are "
            "reported). Returns {ok, diagnostics:[{line, column, severity, code, syntax, message}]}. "
            "`ok` is true when there are no ERROR diagnostics. Use line/column to fix each issue, then "
            "re-validate — this is the self-correction loop."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Raw .sysml source text"},
                "path": {"type": "string", "description": "Path to an existing .sysml file"},
                "context_paths": {"type": "array", "items": {"type": "string"},
                                  "description": "Sibling .sysml files the model depends on"},
            },
        },
    },
    {
        "name": "query_library",
        "description": (
            "Search the SysML v2 standard library for elements matching a name or keyword. Use this "
            "BEFORE referencing any standard type, quantity, or unit so you cite a real qualified name "
            "(e.g. 'mass' → ISQBase::MassValue, 'newton' → SI::newton, 'Real' → ScalarValues::Real) "
            "instead of inventing one. Returns a ranked list of "
            "{name, qualified_name, kind, package, file, line, declaration}."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Name or keyword to search for"},
                "limit": {"type": "integer", "description": "Max results (default 25)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_library_element",
        "description": (
            "Return the declaration of a specific standard-library element by qualified name "
            "(e.g. 'ISQBase::MassValue', 'SI::newton'). Returns the element with a declaration excerpt, "
            "or null if not found. Use after query_library to inspect an element's definition."),
        "inputSchema": {
            "type": "object",
            "properties": {"qualified_name": {"type": "string"}},
            "required": ["qualified_name"],
        },
    },
    {
        "name": "dump_model",
        "description": (
            "Parse a SysML v2 model and return its AST as a structured JSON array of elements. "
            "Provide either `content` (raw .sysml text) or `path` (an existing .sysml file). "
            "`context_paths` lists sibling .sysml files the model imports. "
            "Returns {ok, elements:[...]} on success, or {ok, diagnostics:[...]} if there are parse errors."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Raw .sysml source text"},
                "path": {"type": "string", "description": "Path to an existing .sysml file"},
                "context_paths": {"type": "array", "items": {"type": "string"},
                                  "description": "Sibling .sysml files the model depends on"},
            },
        },
    },
]
_DISPATCH = {
    "validate_sysml_file": validate_sysml_file,
    "query_library": query_library,
    "get_library_element": get_library_element,
    "dump_model": dump_model,
}


# ---------------------------------------------------------------------------
# Minimal MCP stdio JSON-RPC server
# ---------------------------------------------------------------------------
def _send(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _result(req_id, result) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code, message) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _handle(msg: dict) -> None:
    method = msg.get("method")
    req_id = msg.get("id")
    if method is None:  # a response, ignore
        return
    if req_id is None:  # a notification (e.g. notifications/initialized)
        return
    if method == "initialize":
        client_pv = (msg.get("params") or {}).get("protocolVersion", PROTOCOL_VERSION)
        _result(req_id, {"protocolVersion": client_pv,
                         "capabilities": {"tools": {}},
                         "serverInfo": SERVER_INFO})
    elif method == "ping":
        _result(req_id, {})
    elif method == "tools/list":
        _result(req_id, {"tools": TOOLS})
    elif method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        fn = _DISPATCH.get(name)
        if fn is None:
            _error(req_id, -32602, f"Unknown tool: {name}")
            return
        try:
            value = fn(**args)
            content = [{"type": "text", "text": json.dumps(value)}]
            payload = {"content": content}
            if isinstance(value, dict):
                payload["structuredContent"] = value
            _result(req_id, payload)
        except Exception as e:  # surface tool errors as MCP tool errors, not crashes
            log(f"tool {name} error: {e!r}")
            _result(req_id, {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True})
    else:
        _error(req_id, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            _handle(msg)
        except Exception as e:  # never let one bad message kill the server
            log(f"handler error: {e!r}")


if __name__ == "__main__":
    main()
