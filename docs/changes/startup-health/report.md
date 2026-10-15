# Round 3: startup-health correction

**Ready for independent ChatGPT review; draft PR [#10](https://github.com/3shn/skill-sysml/pull/10). No merge or deployment.**

An existing empty `sysml.library` directory previously yielded `query_library("mass") → []`, yet the startup script exited 0 and claimed standard-library resolution. The corrected smoke requires the known pinned `ISQBase::MassValue` attribute definition, validates the current JSON-text tool result, and accurately reports **MCP startup + library-index lookup; compiler validation NOT_RUN**. The separate existing hosted compiler smoke still checks a real valid and broken model.

## Scope and source history

Baseline main pinned/fetched at `eaff43723b7c3975466fd7b36f4b799e9b43838a`. Fresh branch: `codex/sysml-startup-health-round-3`. No owner AGENTS/CLAUDE or `.sdlc` marker exists at baseline; requested minimal change-folder records were adopted without installing a lifecycle tool.

- Plan first: `2d1debbc96046013a8a4b4cae285a992e7729c74`.
- Initial red tests: `2ffee45` against unchanged startup source; 10 tests, 19 failed assertions and one malformed-wire fixture timeout error.
- Corrected red fixture: `3d54c16`; closes its output after malformed JSON. Same unchanged startup source: 10 tests, 19 failed assertions, no errors. Both original runs retained; failure was not relabeled as a pass.
- Implementation: `08f4ede00cbb33fba59d92f28f6fbd9eef09f32e`. Later evidence/report-only commits do not alter those executable bytes. Final review head and final-head hosted status are recorded in the PR and Substrate result, avoiding a self-referential evidence commit.

Runtime correction is limited to `tests/test_mcp_startup.py`, the same entrypoint used by CI/toolchain. Added regression fixtures/tests, one unit-test step in existing owner CI, README scope explanation and these change/evidence records. No changes to server MCP behavior, library index, Java/compiler semantics, setup, packaging, runtime artifacts, other repositories, source locks, installed plugins, host permissions or SDLC draft PRs.

The independent Round 2 review's method correction is accepted: the earlier baseline/procedure labels shared decision logic; their counts were characterization, not independent A/B benefit or false-acceptance-rate estimates. No common acceptance contract or system-wide claim follows from this local correction.

## Exact readiness predicate

The unchanged server represents a list result as one JSON `text` block in `content` (it does not emit list `structuredContent`). The smoke requires that shape and fails closed for missing/malformed/ambiguous/structured-only results, JSON-RPC/tool errors, non-list/empty items and unrelated hits. It requires MCP initialization/capabilities plus the four current tools.

A matching result has name `MassValue`, package `ISQBase`, qualified name `ISQBase::MassValue`, kind `attribute def`, and declaration first line `attribute def MassValue :> ScalarQuantityValue {`. The official library source was inspected at commit [9baca5908ca28b53da085de69336fde48420ea8f, ISQBase.sysml:66](https://github.com/Systems-Modeling/SysML-v2-Release/blob/9baca5908ca28b53da085de69336fde48420ea8f/sysml.library/Domain%20Libraries/Quantities%20and%20Units/ISQBase.sysml#L66); blob `da34d2e5b887ebc8e1639a2bb9a8150da415e873`, file SHA-256 `cc5dc730d2a7167e914431a6f12d0318f792a5c6e2a204a37df9ab33f5e98435`. The actual unchanged heuristic index confirms that tuple over the full pinned library.

The four-line [reference fixture](../../../tests/fixtures/startup/expected-element.sysml) is an authored minimal declaration matching that reference, not a vendored upstream library, an authenticity test, a complete model or a compiler positive. A fake library deliberately reproducing the expected tuple could pass an index check. Cryptographic library identity and model/requirements correctness are outside this predicate.

`SYSML_RUNTIME` remains usable for the existing shared runtime; per-agent path variables are cleared as before. Future changes to structured result representation or the pinned library declaration need a corresponding explicit smoke update, rather than silent acceptance. No credentials or extra runtime dependencies are required.

## Test-first evidence and results

All local commands used Python 3.12.14. Raw outputs remain local under `/workspace/agentic-research/round3-local`; [provenance.json](evidence/provenance.json) binds originals and explicitly transformed publication excerpts separately. No production events, source-body dumps or credentials are published.

| Check | Result | Evidence / limit |
|---|---|---|
| Unmodified empty-directory counterexample | PASS characterization: observed exit 0 and empty result | [baseline-empty.json](evidence/baseline-empty.json); proves old overclaim only |
| Initial/corrected red | Expected FAIL: 19 failures +1 fixture error initially; corrected 19 failures | [red-initial.txt](evidence/red-initial.txt), [red.txt](evidence/red.txt), [red-binding.json](evidence/red-binding.json); timeout-API/success-wording assertions are distinguished from library false positives |
| New startup regression suite | PASS: 10 tests | [green.txt](evidence/green.txt); missing/empty/unrelated index, malformed/error results, wrong kind/declaration, initialization/tools, silence/partial-line timeout, stderr flood, child reaping, truthful positive fixture |
| Full existing + new local pytest | **FAIL overall: 19 passed, 1 failed** | [full-local.txt](evidence/full-local.txt); existing normal-path test cannot spawn missing `javac`; no compiler execution locally |
| Actual full pinned official library over unchanged MCP server | PASS for index/startup | [official-library.json](evidence/official-library.json); no jar/classes supplied, compiler NOT_RUN |
| Disable new library predicate in temporary source copy | PASS control: enabled suite exit 0, disabled exit 1 with 14 assertion failures | [mutation.json](evidence/mutation.json); empty and unrelated actual index controls fail when disabled; checkout bytes unchanged |
| Read-only existing toolchain consumer probe | PASS: check=True raises on real empty-library rejection before wrapper | [consumer.json](evidence/consumer.json); setup/download mocked; enclosing reconciliation/install NOT_RUN, so not a deployed-receipt proof |
| Hosted implementation-head `ci` | PASS provider metadata | [run 38729234949](https://github.com/3shn/skill-sysml/actions/runs/38729234949), job 116402607643; all steps success including regression controls, JDK21 setup, runtime provisioning and actual good/broken model assertions |
| Hosted implementation-head OOB | PASS provider metadata | [run 38729234896](https://github.com/3shn/skill-sysml/actions/runs/38729234896), job 116402607976; setup and revised OOB startup steps success |

Both hosted runs' head SHA is the implementation commit above. Raw job-log inspection is **NOT_RETRIEVED**: the connected API excludes logs and the CLI's signed storage redirect was forbidden by current network policy. No policy bypass, credential request or raw-log PASS is inferred. Workflow/job/step metadata and exact workflow source are available; raw stdout/tool version details beyond provider setup step are not claimed. Final evidence-head checks are tracked separately by PR/Substrate.

The smoke now reads pipe bytes with selector deadlines (including partial lines), limits buffered response size, drains stderr to a temporary file, and always terminates/awaits or kills/awaits the direct child in `finally`. Tests demonstrate the child PID disappears after success, protocol rejection and timeout. This covers the MCP child used by this index smoke, not arbitrary descendant trees or compiler processes. Selector/pipe behavior was tested on Linux; Windows is unverified and the existing runtime installer remains bash based.

## Reproduce

```sh
python3 -m unittest discover -s tests -p test_startup_controls.py -v
python3 docs/changes/startup-health/mutation_probe.py
python3 docs/changes/startup-health/consumer_probe.py --toolchain /path/to/agent-toolchain
```

The consumer probe checks toolchain.py bytes against `314cf082972adc723915ea5190cb79400d99bb94`. It creates an inert scratch jar placeholder solely to skip download, mocks setup, then invokes the **real** owner startup check with an existing empty library and `check=True`; no placeholder is executed. Full installation and receipt reconciliation remain NOT_RUN. [Toolchain source: provision_sysml](https://github.com/3shn/agent-toolchain/blob/314cf082972adc723915ea5190cb79400d99bb94/toolchain.py#L510) confirms this same check runs before wrapper creation; the exception propagates before the caller's final receipt write. No toolchain edits or lock bumps were made.

For a real index-only positive, place the unmodified official library at `$SYSML_RUNTIME/sysml.library` then run `python3 tests/test_mcp_startup.py`. For actual compiler tests, use the existing declared Java21/Pilot setup and CI good/broken assertions; no local privileged install was attempted to turn absent prerequisites into a pass.

No scientific adequacy, authenticated human approval, deployed host health, complete six-way workflow, merge eligibility or acceptance of future rounds is established. Stop for independent ChatGPT review.
