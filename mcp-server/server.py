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
SERVER_INFO = {"name": "sysml", "version": "0.4.0"}


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
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
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
def _check_path(path: str) -> str | None:
    if not isinstance(path, str):
        return f"Path must be a string, got {type(path).__name__}"
    if not path.isprintable():
        return f"Path contains invalid control characters: {repr(path)}"
    return None

def validate_sysml_file(content=None, path=None, context_paths=None) -> dict:
    if context_paths is None:
        context_paths = []
    elif not isinstance(context_paths, list):
        return {"ok": False, "diagnostics": [{"line": 0, "column": 0, "severity": "ERROR", "code": "bad-request", "syntax": False, "message": "context_paths must be a list."}]}
    for p in ([path] if path is not None else []) + context_paths:
        if err := _check_path(p):
            return {"ok": False, "diagnostics": [{"line": 0, "column": 0, "severity": "ERROR", "code": "invalid-path", "syntax": False, "message": err}]}
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
    if context_paths is None:
        context_paths = []
    elif not isinstance(context_paths, list):
        return {"ok": False, "diagnostics": [{"line": 0, "column": 0, "severity": "ERROR", "code": "bad-request", "syntax": False, "message": "context_paths must be a list."}]}
    for p in ([path] if path is not None else []) + context_paths:
        if err := _check_path(p):
            return {"ok": False, "diagnostics": [{"line": 0, "column": 0, "severity": "ERROR", "code": "invalid-path", "syntax": False, "message": err}]}
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
        res = _validator.dump(target, ctx)
        if res.get("ok") and "elements" in res:
            res["elements"] = _reduce_ast(res["elements"])
        return res
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


def _reduce_ast(elements_list):
    by_id = {}
    for entry in elements_list:
        payload = entry.get("payload")
        if payload and "@id" in payload:
            by_id[payload["@id"]] = payload

    def get_qualified_name(elem):
        if not elem: return None
        names = []
        curr = elem
        while curr:
            if curr.get("declaredName"):
                names.append(curr.get("declaredName"))
            elif curr.get("declaredShortName"):
                names.append(curr.get("declaredShortName"))
            elif curr.get("@type") == "Package" and curr.get("name"):
                 names.append(curr.get("name"))

            owner_ref = curr.get("owner")
            if owner_ref and "@id" in owner_ref:
                curr = by_id.get(owner_ref["@id"])
            elif curr.get("owningRelationship") and "@id" in curr.get("owningRelationship"):
                rel = by_id.get(curr["owningRelationship"]["@id"])
                if rel and rel.get("owner") and "@id" in rel["owner"]:
                     curr = by_id.get(rel["owner"]["@id"])
                elif rel and rel.get("owningRelatedElement") and "@id" in rel["owningRelatedElement"]:
                     curr = by_id.get(rel["owningRelatedElement"]["@id"])
                else:
                     curr = None
            else:
                curr = None
        if not names:
            return None
        return "::".join(reversed(names))

    def expr_to_text(elem):
        if not elem: return ""
        typ = elem.get("@type")
        if typ == "LiteralString": return f'"{elem.get("value", "")}"'
        if typ in ("LiteralInteger", "LiteralReal"): return str(elem.get("value", ""))
        if typ == "LiteralBoolean": return str(elem.get("value", "")).lower()
        if typ == "FeatureReferenceExpression":
            return get_qualified_name(elem) or "<ref>"
        if typ == "OperatorExpression":
            op = elem.get("operator", "")
            rels = [by_id.get(r["@id"]) for r in elem.get("ownedRelationship", []) if r.get("@id")]
            ops = []
            for rel in rels:
                if rel and rel.get("ownedRelatedElement"):
                    for oe in rel.get("ownedRelatedElement", []):
                        child = by_id.get(oe.get("@id"))
                        if child: ops.append(expr_to_text(child))
            if op: return f"({f' {op} '.join(ops)})" if len(ops) > 1 else f"{op}{ops[0] if ops else ''}"
            return "".join(ops)
        return ""

    docs_by_owner = {}
    attr_by_owner = {}
    subjects_by_req = {}
    constraints_by_req = {}
    targets_by_verify = {}
    satisfy_edges = []
    verify_edges = []
    specialization_edges = []

    for eid, elem in by_id.items():
        typ = elem.get("@type")
        if typ == "Documentation":
            owner_ref = elem.get("owner")
            if owner_ref and "@id" in owner_ref:
                docs_by_owner[owner_ref["@id"]] = elem.get("body", "")
        
        elif typ == "SubjectMembership":
            owner_ref = elem.get("owner")
            if owner_ref and "@id" in owner_ref:
                owned_ref = elem.get("ownedRelatedElement", [])
                for o in owned_ref:
                    tgt = by_id.get(o.get("@id"))
                    if tgt: subjects_by_req.setdefault(owner_ref["@id"], []).append(get_qualified_name(tgt))
                    
        elif typ == "RequirementConstraintMembership":
            owner_ref = elem.get("owner")
            if owner_ref and "@id" in owner_ref:
                owned_ref = elem.get("ownedRelatedElement", [])
                for o in owned_ref:
                    tgt = by_id.get(o.get("@id"))
                    if tgt:
                        constraints_by_req.setdefault(owner_ref["@id"], []).append({
                            "kind": elem.get("kind", "require"),
                            "text": expr_to_text(tgt) or "<constraint>"
                        })

        elif typ == "SatisfyRequirementUsage":
            src = elem.get("source", [])
            tgt = elem.get("target", [])
            if src and tgt:
                s_elem = by_id.get(src[0].get("@id"))
                t_elem = by_id.get(tgt[0].get("@id"))
                if s_elem and t_elem:
                    satisfy_edges.append({
                        "source": get_qualified_name(s_elem),
                        "target": get_qualified_name(t_elem)
                    })

        elif typ == "VerifyRequirementUsage":
            src = elem.get("source", [])
            tgt = elem.get("target", [])
            if src and tgt:
                s_elem = by_id.get(src[0].get("@id"))
                t_elem = by_id.get(tgt[0].get("@id"))
                if s_elem and t_elem:
                    verify_edges.append({
                        "source": get_qualified_name(s_elem),
                        "target": get_qualified_name(t_elem)
                    })
                    
        elif typ == "Subclassification":
            src = elem.get("source", [])
            tgt = elem.get("target", [])
            if src and tgt:
                s_elem = by_id.get(src[0].get("@id"))
                t_elem = by_id.get(tgt[0].get("@id"))
                if s_elem and t_elem:
                    specialization_edges.append({
                        "source": get_qualified_name(s_elem),
                        "target": get_qualified_name(t_elem)
                    })

        elif typ in ("LiteralString", "LiteralInteger", "LiteralReal", "LiteralBoolean"):
            rel_ref = elem.get("owningRelationship")
            if rel_ref and "@id" in rel_ref:
                rel = by_id.get(rel_ref["@id"])
                if rel and rel.get("@type") == "FeatureMembership":
                    name = rel.get("memberName") or rel.get("declaredName") or elem.get("declaredName")
                    if name:
                        owner_ref = rel.get("owner")
                        if owner_ref and "@id" in owner_ref:
                            attr_by_owner.setdefault(owner_ref["@id"], []).append({
                                "name": name,
                                "value": elem.get("value"),
                                "unit": "extracted_via_sysml" # Simplification for literal bound units
                            })

    reduced = []
    for eid, elem in by_id.items():
        if elem.get("isLibraryElement", False):
            continue
            
        metatype = elem.get("@type")
        if metatype not in (
            "RequirementDefinition", "RequirementUsage", 
            "PartDefinition", "PortDefinition",
            "VerificationCaseDefinition", "AttributeUsage", "ConstraintUsage",
            "Package", "ActionDefinition", "ItemDefinition", "StateDefinition"
        ):
            continue

        out = {
            "id": eid,
            "metatype": metatype,
            "declaredName": elem.get("declaredName"),
            "declaredShortName": elem.get("declaredShortName"),
            "qualifiedName": get_qualified_name(elem),
        }

        if eid in docs_by_owner:
            out["documentation"] = docs_by_owner[eid]
        
        if eid in attr_by_owner:
            out["attributes"] = attr_by_owner[eid]

        if metatype in ("RequirementDefinition", "RequirementUsage"):
            if eid in subjects_by_req:
                out["subjects"] = subjects_by_req[eid]
            if eid in constraints_by_req:
                out["constraints"] = constraints_by_req[eid]
        
        # Determine nesting from owner
        owner_ref = elem.get("owner")
        if owner_ref and "@id" in owner_ref:
            out["ownerId"] = owner_ref["@id"]
            
        reduced.append(out)

    # Rebuild nesting
    nested_by_id = {e["id"]: e for e in reduced}
    top_level = []
    for e in reduced:
        owner_id = e.get("ownerId")
        if owner_id and owner_id in nested_by_id:
            parent = nested_by_id[owner_id]
            parent.setdefault("ownedElements", []).append(e)
        else:
            top_level.append(e)
            
    # Clean up ownerId and id
    def clean(node):
        node.pop("ownerId", None)
        node.pop("id", None)
        for child in node.get("ownedElements", []):
            clean(child)
    for t in top_level:
        clean(t)

    return {
        "nodes": top_level,
        "relationships": {
            "satisfy": satisfy_edges,
            "verify": verify_edges,
            "specialization": specialization_edges
        }
    }


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
