# Changelog

## [0.4.1] - 2026-06-13
### Fixed
- `sysml setup` (the pip/CI provisioner) now matches `setup.sh`: it compiles the
  **whole** `java/` tree (not just `SysmlValidatorServer.java`), so the sibling
  `SafeJsonFacade.java` resolves instead of failing with `cannot find symbol`.
- `sysml setup` now also provisions the SysML v2 **standard library** (pinned
  clone of the Release repo). The kernel jar does not bundle it, so without this
  `sysml dump`/validate could not resolve `Requirements::`/`ISQ::`/… and emitted
  "must specialize Requirements::RequirementCheck" errors. `setup` is now a
  complete, `gh`-free provisioner equivalent to `setup.sh`.

## [0.4.0] - 2026-06-06
### Added
- Portable multi-agent install (sysml-mcp entrypoint + INSTALL.md)
- Marketplace ship-readiness: clean-VM install proof + doc/identity fixes
- SysML v2 standard library auto-provisioning via `setup.sh`
- Added CHANGELOG.md
- Pinned SysML v2 standard library commit to ensure reproducible behavior

### Fixed
- Fixed data exposure via unhandled exception messages
- Fixed protocol injection via unsanitized input paths
- Optimized LibraryIndex.get bare name lookup
- Optimized library index search loop performance

## [0.3.0] - 2026-06-05
### Added
- Initial Marketplace distribution release
- MCP server providing `validate_sysml_file`, `query_library`, `get_library_element`
