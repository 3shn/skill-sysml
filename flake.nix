{
  description = "skill-sysml: SysML v2 skills and a headless validator for coding agents";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      # What mcp-server/setup.sh requires on PATH (java, javac, python3, curl, git, unzip), for CI on a
      # self-hosted NixOS runner, where setup-java and setup-python binaries do not run. Python 3.12 as in CI.
      devShells = forAllSystems (pkgs: {
        ci = pkgs.mkShell {
          packages = with pkgs; [
            jdk21_headless
            python312
            curl
            git
            unzip
          ];
        };
      });
    };
}
