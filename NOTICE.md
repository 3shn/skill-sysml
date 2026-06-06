# NOTICE

This plugin (the MCP server, skill, CLI, and Java validator wrapper in this repository) is
licensed under the MIT License — see `LICENSE`. Copyright (c) 2026 Yu Shen.

## Third-party components (downloaded at setup time, not redistributed)

`mcp-server/setup.sh` **downloads** two upstream artifacts into a local, gitignored
`mcp-server/.runtime/` directory the first time it runs. This repository does **not** vendor or
redistribute them; each remains under its own upstream license, and the download is from the
official source:

- **SysML v2 Pilot Implementation — kernel fat jar**
  (`jupyter-sysml-kernel-<version>-all.jar`), from
  <https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation/releases>.
  © the SysML v2 Submission Team / Systems-Modeling contributors; licensed under the terms in
  that repository (LGPL-family). Used here unmodified as the validation/compilation engine.

- **SysML v2 Release — standard library** (`sysml.library`: Kernel/Systems/Domain libraries),
  shallow-cloned from <https://github.com/Systems-Modeling/SysML-v2-Release>.
  © the SysML v2 Submission Team / Systems-Modeling contributors; licensed under the terms in
  that repository (LGPL-family). Used here unmodified as the standard-library index against which
  `ISQ::`/`SI::`/etc. references are resolved.

Because these are fetched from their official distribution points and used unmodified (not
re-hosted or bundled in this plugin's published artifact), this plugin's MIT license applies only
to the code authored here. Users who run `setup.sh` obtain the upstream components directly from
Systems-Modeling under those projects' licenses. If you redistribute a *bundle* that includes the
downloaded jar or library, you must comply with their licenses (LGPL obligations) for those files.

Requires a Java runtime (JDK 21+) on the user's machine; the JDK is not distributed with this
plugin.
