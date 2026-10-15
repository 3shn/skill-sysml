# Plan before changes

**Change class:** substantive

1. Commit these records before tests/product changes. Capture unmodified empty-directory exit0 and baseline source hashes.
2. Add stdlib subprocess/fixture regressions before correcting startup smoke; retain actual red output and exact source/test binding. Positive index fixture derives from the pinned official declaration, never a simulated compiler pass.
3. Modify only owned startup check and tests, documentation and minimal test wiring in existing owner CI if useful. Keep command/OOB placement and stdlib dependencies. Validate exact library item and truthful success wording; bound reads and reap child in finally.
4. Run regression suite, actual pinned-library startup, malformed/empty/unrelated/error controls, cleanup/deadline tests, one temporary-copy predicate-disable mutation, and read-only mocked toolchain consumer proof.
5. Publish sanitized reproducible evidence and a draft PR. Inspect exact-head CI; retain FAIL/NOT_RUN if prerequisites or upstream resources fail. Stop for independent review.

## CHECK

| check | command | expect |
|---|---|---|
| startup regression controls | `python3 -m unittest discover -s tests -p 'test_startup_controls.py' -v` | 0 |
| existing regression evals | `python3 -m pytest evals -q` with declared pytest/runtime prerequisites | 0 or explicitly prerequisite FAIL |
| real-library index startup | `SYSML_RUNTIME=<scratch-with-pinned-library> python3 tests/test_mcp_startup.py` | 0; compiler NOT_RUN |
| diff hygiene | `git diff --check` | 0 |

No live installation, merge, deployment, lock bump or cross-repo write. All mutable runtime fixtures and original logs stay in scratch; only deliberately selected sanitized outputs/provenance are published.
