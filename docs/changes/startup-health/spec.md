# Scoped predicate and falsifiers

**Change class:** substantive

1. Required smoke: launch the declared `.mcp.json` command with the existing OOB environment semantics; initialize MCP; require the expected validator, query, element and dump tools. Library query is JSON text in a tool-result `content` block, as emitted for lists by current `server._handle`. Missing/malformed result shape, tool error or invalid JSON fails closed.
2. Query `MassValue` and require a matching `name=MassValue`, `qualified_name=ISQBase::MassValue`, `package=ISQBase`, `kind=attribute def`, and first declaration line `attribute def MassValue :> ScalarQuantityValue {`. This is a heuristic-index readiness assertion, not library authenticity or semantic correctness.
3. Reference inspected: official Systems-Modeling/SysML-v2-Release commit `9baca5908ca28b53da085de69336fde48420ea8f`, `sysml.library/Domain Libraries/Quantities and Units/ISQBase.sysml`, line 66. Git blob `da34d2e5b887ebc8e1639a2bb9a8150da415e873`. Local whole-library index confirms the exact tuple. Fixtures use a minimal authored declaration matching that source, not a vendored upstream library. No arbitrary nonempty mass hit suffices.
4. Fail missing/empty library, unrelated nonempty hit, wrong kind/declaration, absent/malformed results, JSON-RPC/isError, bad initialization or missing tools. A minimal reference fixture and the actual downloaded pinned library pass the INDEX smoke only.
5. Success says MCP + expected library-index lookup passed and compiler validation NOT_RUN. No compiler-health claim unless a real compiler positive/negative test ran separately. Existing CI already has that separate check.
6. Bound response waits, including silent/partial-line output, and always terminate/kill as necessary and wait for the child on success and failure. Do not leak an unreaped MCP child or block on stderr.
7. Read-only consumer proof: unmodified toolchain `provision_sysml` calls this entrypoint `check=True`; a rejected check aborts before success wrapper creation. No toolchain product edits or installed apply.

Tests are bounded synthetic protocol/index fixtures, not independent scientific or person-identity validation. Disabling the qualified-name predicate must reintroduce the empty/unrelated false positives. Real compiler is NOT_RUN locally if Javac/jar/classes are unavailable; hosted configured checks provide separate evidence if they execute.
