# SysML v2 Co-Pilot — Marketplace ship-readiness audit

_Assessed 2026-06-05 (v0.3.0). Original verdict: **functionally mature, distribution-immature.**_

## STATUS UPDATE (2026-06-05) — all P0 blockers cleared

The four P0 blockers below are **done and verified** (portable provisioning tested end-to-end on a
clean `.runtime/` with env vars unset: the validator accepts valid SysML and rejects the broken
fixture). Remaining before publish is a founder decision, not engineering:

- ✅ **P0-1 LICENSE + NOTICE** — `LICENSE` (MIT) + `NOTICE.md` (jar/library are downloaded, not
  redistributed; LGPL-family upstreams documented).
- ✅ **P0-2 portable paths** — `.mcp.json` no longer hardcodes author paths; `server.py` defaults to
  a plugin-local `.runtime/`; `INSTALL.md` examples use `<path-to-this-plugin>` / no env block.
- ✅ **P0-3 auto-provision the library** — `setup.sh` now shallow-clones the standard library (was
  only a WARN) and fetches the kernel jar; both land in `.runtime/` (gitignored).
- ✅ **P0-4 marketplace manifest** — `.claude-plugin/marketplace.json` (plugin at `source: "./"`).
- ✅ **P1-5 curl not gh** — jar fetched with `curl -fL` (no GitHub auth).
- ✅ **P1-6 CI evals** — `.github/workflows/ci.yml` runs `setup.sh` + a validator smoke test (good
  passes, broken fails) on JDK 21 + Python 3.12.

**Remaining to publish (founder):** (a) push the plugin repo + create the marketplace; (b) optional
version bump 0.3.0→0.4.0 to mark "distributable"; (c) P2 polish (CHANGELOG, demo GIF, pin the
library commit). The P1 cross-platform gap (bash-only `setup.sh`) is documented, not closed.

---
_Original audit below (for the record)._

The capability is real and tested — this is not a rebuild, it's a "fix the install story +
license + marketplace manifest" pass. Below: what's already strong, the blockers, and a
prioritized punch list with a go/no-go.

## Verdict

**Conditional go.** Publishable after the P0 blockers below (license, author-specific absolute
paths, library auto-provisioning, marketplace manifest). Estimate: a focused half-day. The hard
part — a validated, self-correcting MCP toolchain over the real Pilot compiler — is done.

## What's already strong (keep)

- **Real, self-correcting capability.** `validate_sysml_file` runs the actual SysML v2 Pilot
  compiler (warm Java validator server), so the skill's "authors valid SysML in a self-correcting
  loop" claim is backed by a real oracle, not vibes.
- **Stdlib-only Python MCP server** — no pip deps, instant/offline startup, launched with a
  PATH-resolved `python3`. Good portability instinct.
- **Idempotent `setup.sh`** that downloads the kernel jar from the upstream GitHub release and
  compiles the validator. Re-runnable, documented prerequisites.
- **6 evals** (`evals/evals.json`) with concrete compile-clean assertions and a broken-model
  fixture — the right shape for a quality bar.
- **Thoughtful `INSTALL.md`** covering cross-agent portability (Codex/Cursor/Windsurf/Droid),
  console-script entrypoints, and the skill-travels-via-AGENTS.md story.
- **Clean plugin manifest** (`.claude-plugin/plugin.json`): name, displayName, version, keywords,
  author. Marketplace-shaped already.

## P0 blockers (must fix before publishing)

1. **No LICENSE file.** A Marketplace plugin must declare a license. Add one (MIT/Apache-2.0 for
   your code). Separately, the **redistributed/downloaded SysML Pilot jar and the SysML-v2-Release
   standard library carry their own licenses** (Eclipse/LGPL family) — add a `NOTICE.md`
   documenting them and confirming the setup-time *download* (not vendoring) is compliant.

2. **Author-specific absolute paths committed.** `.mcp.json` hardcodes
   `SYSML_LIBRARY_PATH=/home/u/gh/Systems-Modeling/...` and
   `SYSML_KERNEL_JAR=/home/u/gh/3shn/skills/SysML_v2/...`; `setup.sh` defaults to `$HOME/gh/3shn/...`;
   `INSTALL.md`'s pipx example uses `/home/u/gh/3shn/skills/sysml`. **None of these exist on anyone
   else's machine.** Fix: provision both resources *inside the plugin dir* (e.g.
   `${CLAUDE_PLUGIN_ROOT}/.runtime/`) and make the committed `.mcp.json` reference
   `${CLAUDE_PLUGIN_ROOT}` only; replace absolute examples with `${CLAUDE_PLUGIN_ROOT}` / a
   placeholder.

3. **Standard library is not auto-provisioned.** `setup.sh` *downloads the jar* but only **WARNs**
   if `SYSML_LIBRARY_PATH` (the SysML-v2-Release `sysml.library`) is missing — leaving the user to
   clone a separate repo by hand. Either clone/download it in `setup.sh` (it's the same upstream org)
   or vendor a pinned copy. Without this the validator silently lacks the stdlib that every
   `ISQ::`/`SI::` reference resolves against — the core value prop.

4. **No marketplace manifest / distribution channel decided.** Anthropic plugin marketplaces are
   git repos with a `.claude-plugin/marketplace.json` listing plugins. Decide: stand up your own
   marketplace repo (e.g. `3shn/claude-plugins`) with this listed, or submit to an existing one.
   Add the `marketplace.json` entry + install instructions.

## P1 (should fix — quality/credibility)

5. **`setup.sh` needs `gh` auth to download the jar.** Use `curl -L` against the public release
   asset URL instead, so setup works without a logged-in `gh`.
6. **No CI running the evals.** Wire a GitHub Action that runs `setup.sh` + the 6 evals on push, so
   the "compiles clean / self-correcting" claim is enforced, not asserted. This is also your
   strongest Marketplace trust signal.
7. **Cross-platform gap.** `setup.sh` is bash-only (no Windows). At minimum document "macOS/Linux
   (WSL on Windows)"; ideally a PowerShell sibling later.
8. **Java 21+ is a heavyweight, unstated-at-listing dependency.** Make the prerequisite (JDK 21+)
   loud in the README/marketplace description so installs don't fail surprisingly.

## P2 (nice-to-have)

9. `CHANGELOG.md` (you're at 0.3.0 with real history in git — surface it).
10. A short demo GIF/asciinema in the README (model → validate → self-correct loop) — converts on
    a marketplace listing.
11. Pin the kernel/library versions together and assert them at server startup (you pin
    `KERNEL_VERSION=0.59.0`; pin the library commit too, so the stdlib and compiler can't drift).

## Suggested sequence (half-day)

P0-2 (paths → `${CLAUDE_PLUGIN_ROOT}`) and P0-3 (auto-provision the library) are the same edit to
`setup.sh`/`.mcp.json`, so do them together. Then P0-1 (LICENSE + NOTICE), then P0-4 (marketplace
manifest), then P1-6 (CI evals) as the credibility capstone. P1-5 (curl not gh) folds into the
setup.sh edit. Ship after P0 + ideally P1-6.
