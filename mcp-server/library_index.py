"""Builds a lightweight name -> element index over the SysML v2 standard library
(.sysml / .kerml sources) so the co-pilot can look up *real* qualified names
(e.g. ISQ::mass, SI::kilogram, ScalarValues::Real) instead of inventing them.

This is a heuristic text index, not a full parser: it tracks package nesting by
brace depth and captures definitions/usages with their qualified names. That is
enough for "what's the standard type for mass?" lookups; the validator is the
authority on whether a reference actually resolves.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

# An identifier is a normal name or a single-quoted name (which may contain spaces).
_ID = r"(?:'[^']+'|[A-Za-z_][A-Za-z0-9_]*)"

# Optional `<shortName>` alias that may precede a declared name, e.g. `<kg> kilogram`.
_SHORT = r"(?:<([^>]+)>\s+)?"

_PACKAGE_RE = re.compile(
    r"^\s*(?:standard\s+)?(?:library\s+)?package\s+" + _SHORT + r"(" + _ID + r")"
)
# `<modifiers> <kind> def <Name>`  e.g. "abstract part def Part", "attribute def MassValue"
_DEF_RE = re.compile(
    r"^\s*(?:(?:abstract|variation|individual|standard|library|ref)\s+)*"
    r"([a-z][a-z ]*?)\s+def\s+" + _SHORT + r"(" + _ID + r")"
)
# KerML classifier-style decls: `datatype Real specializes ...`, `class X`, `feature f`
_KERML_RE = re.compile(
    r"^\s*(?:(?:abstract|readonly|derived|standard|library)\s+)*"
    r"(datatype|class|struct|assoc(?:iation)?|classifier|type|function|predicate|"
    r"behavior|interaction|metaclass|feature)\s+" + _SHORT + r"(" + _ID + r")\b"
)
# Named usages we care about for type/unit lookup: `attribute mass:`, `attribute <kg> kilogram:`.
_USAGE_RE = re.compile(
    r"^\s*(?:(?:abstract|readonly|derived|ref|in|out|inout|composite|portion)\s+)*"
    r"(attribute|part|port|item|action|state|connection|flow|calc|constraint|requirement|enum)\s+"
    + _SHORT + r"(" + _ID + r")\s*[:;=\[{]"
)


@dataclass
class Element:
    name: str
    qualified_name: str
    kind: str
    package: str
    file: str
    line: int


class LibraryIndex:
    def __init__(self, library_path: str):
        self.library_path = library_path
        self.elements: list[Element] = []
        self._by_qname: dict[str, Element] = {}
        self._file_lines: dict[str, list[str]] = {}

    # ---- building -------------------------------------------------------
    def build(self) -> "LibraryIndex":
        root = Path(self.library_path)
        if not root.is_dir():
            raise FileNotFoundError(f"SYSML_LIBRARY_PATH not found: {self.library_path}")
        for path in sorted(root.rglob("*")):
            if path.suffix in (".sysml", ".kerml") and path.is_file():
                self._index_file(path)
        for e in self.elements:
            # First definition wins for a given qualified name.
            self._by_qname.setdefault(e.qualified_name, e)
        return self

    def _index_file(self, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        lines = text.splitlines()
        self._file_lines[str(path)] = lines
        # package stack of (name, brace_depth_at_open)
        stack: list[tuple[str, int]] = []
        depth = 0
        for i, raw in enumerate(lines):
            line = raw.split("//", 1)[0]  # strip line comments for matching
            pkg = _PACKAGE_RE.match(line)
            if pkg:
                stack.append((_clean(pkg.group(2)), depth))
            else:
                is_def = _DEF_RE.match(line)
                m = is_def or _KERML_RE.match(line) or _USAGE_RE.match(line)
                if m:
                    kind = m.group(1).strip().replace("  ", " ")
                    if is_def:
                        kind = f"{kind} def"
                    short, name = m.group(2), _clean(m.group(3))
                    prefix = "::".join(n for n, _ in stack)
                    # index the declared name and, if present, its <short> alias
                    for nm in [name] + ([short.strip()] if short else []):
                        qn = f"{prefix}::{nm}" if prefix else nm
                        self.elements.append(Element(
                            name=nm, qualified_name=qn, kind=kind,
                            package=prefix, file=str(path), line=i + 1))
            # adjust depth, pop packages whose block closed
            depth += line.count("{") - line.count("}")
            while stack and depth <= stack[-1][1]:
                stack.pop()

    # ---- querying -------------------------------------------------------
    def search(self, query: str, limit: int = 25) -> list[dict]:
        q = query.strip().strip("'").lower()
        if not q:
            return []
        scored: list[tuple[int, Element]] = []
        for e in self.elements:
            name = e.name.strip("'").lower()
            qn = e.qualified_name.lower()
            if name == q:
                score = 100
            elif name.startswith(q):
                score = 80
            elif q in name:
                score = 60
            elif q in qn:
                score = 40
            else:
                continue
            # prefer real definitions over plain usages, and shorter qualified names
            if e.kind.endswith("def") or e.kind in ("datatype", "class", "struct"):
                score += 10
            score -= min(len(e.qualified_name) // 10, 8)
            scored.append((score, e))
        scored.sort(key=lambda t: (-t[0], len(t[1].qualified_name)))
        return [_with_excerpt(self, e) for _, e in scored[:limit]]

    def get(self, qualified_name: str) -> dict | None:
        e = self._by_qname.get(qualified_name)
        if e is None:
            # tolerate lookups by bare name if unambiguous
            target_name = qualified_name.strip("'")
            cands = [x for x in self.elements if x.name.strip("'") == target_name]
            if len(cands) == 1:
                e = cands[0]
        return _with_excerpt(self, e, excerpt_lines=20) if e else None


def _clean(identifier: str) -> str:
    return identifier  # keep single quotes; they are part of the SysML name


def _with_excerpt(idx: LibraryIndex, e: Element, excerpt_lines: int = 6) -> dict:
    d = asdict(e)
    lines = idx._file_lines.get(e.file, [])
    start = e.line - 1
    snippet = "\n".join(lines[start:start + excerpt_lines]).rstrip()
    d["declaration"] = snippet
    # report the file relative to the library root for readability
    try:
        d["file"] = os.path.relpath(e.file, idx.library_path)
    except ValueError:
        pass
    return d
