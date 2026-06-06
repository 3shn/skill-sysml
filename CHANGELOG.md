# Changelog

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
