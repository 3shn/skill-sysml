import pytest
import sys
import os

# Add mcp-server to path so we can import LibraryIndex
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../mcp-server')))

from library_index import LibraryIndex, Element

@pytest.fixture
def index():
    idx = LibraryIndex("/dummy/path")
    return idx

def make_element(name, qn, kind="attribute"):
    return Element(
        name=name,
        qualified_name=qn,
        kind=kind,
        package="Pkg",
        file="/dummy/path/file.sysml",
        line=1
    )

def populate_index(idx, elements_with_tuples):
    # Populate both elements and _searchable_elements to ensure tests are robust
    # regardless of whether search() iterates over elements or _searchable_elements
    idx.elements = [e for _, _, e in elements_with_tuples]
    idx._searchable_elements = elements_with_tuples

def test_search_empty_query(index):
    # Empty queries should return empty list
    assert index.search("") == []
    assert index.search("   ") == []
    assert index.search("''") == []

def test_search_exact_match(index):
    e = make_element("mass", "ISQ::mass")
    populate_index(index, [("mass", "isq::mass", e)])

    results = index.search("mass")
    assert len(results) == 1
    assert results[0]["name"] == "mass"

def test_search_ranking(index):
    # Setup elements that will match in different ways
    e_exact = make_element("target", "Pkg::target") # Exact match (100)
    e_starts = make_element("targetValue", "Pkg::targetValue") # Starts with (80)
    e_in = make_element("myTarget", "Pkg::myTarget") # In name (60)
    e_qn = make_element("other", "Pkg::target::other") # In qn (40)
    e_nomatch = make_element("hello", "Pkg::hello") # No match

    populate_index(index, [
        ("targetvalue", "pkg::targetvalue", e_starts),
        ("hello", "pkg::hello", e_nomatch),
        ("other", "pkg::target::other", e_qn),
        ("target", "pkg::target", e_exact),
        ("mytarget", "pkg::mytarget", e_in),
    ])

    results = index.search("target")
    # Should not include hello
    assert len(results) == 4

    # Check ranking order (highest score first)
    assert results[0]["name"] == "target"
    assert results[1]["name"] == "targetValue"
    assert results[2]["name"] == "myTarget"
    assert results[3]["name"] == "other"

def test_search_bonus_and_penalty(index):
    # Kind ending with "def" gets +10 bonus
    e_usage = make_element("mass", "Pkg::mass", kind="attribute")
    e_def = make_element("mass", "Pkg::mass", kind="attribute def")

    # Shorter QN gets less penalty
    # Penalty is min(len(qn) // 10, 8)
    e_short_qn = make_element("mass", "A::mass", kind="attribute def") # len 7 -> penalty 0
    e_long_qn = make_element("mass", "VeryLongPackage::mass", kind="attribute def") # len 21 -> penalty 2

    populate_index(index, [
        ("mass", "pkg::mass", e_usage),
        ("mass", "verylongpackage::mass", e_long_qn),
        ("mass", "a::mass", e_short_qn),
        ("mass", "pkg::mass", e_def),
    ])

    results = index.search("mass")

    # A::mass has +10 bonus and 0 penalty -> highest
    assert results[0]["qualified_name"] == "A::mass"
    # Pkg::mass (def) has +10 bonus and len 9 -> penalty 0
    assert results[1]["qualified_name"] == "Pkg::mass"
    assert results[1]["kind"] == "attribute def"
    # VeryLongPackage::mass has +10 bonus and len 21 -> penalty 2
    assert results[2]["qualified_name"] == "VeryLongPackage::mass"
    # Pkg::mass (usage) has 0 bonus and len 9 -> penalty 0
    assert results[3]["qualified_name"] == "Pkg::mass"
    assert results[3]["kind"] == "attribute"

def test_search_limit(index):
    elements = []
    for i in range(50):
        e = make_element(f"item{i}", f"Pkg::item{i}")
        elements.append((f"item{i}", f"pkg::item{i}", e))

    populate_index(index, elements)

    results = index.search("item")
    assert len(results) == 25 # Default limit

    results = index.search("item", limit=10)
    assert len(results) == 10

def test_search_single_quotes(index):
    # Single quotes in query should be stripped for matching logic
    e = make_element("'mass'", "ISQ::'mass'")
    # Note: _searchable_elements stores name stripped of single quotes
    populate_index(index, [("mass", "isq::'mass'", e)])

    results = index.search("'mass'")
    assert len(results) == 1
    assert results[0]["name"] == "'mass'"
