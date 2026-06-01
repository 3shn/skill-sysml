import argparse
import json
import os
import sys
import tempfile
import urllib.request
import zipfile
import subprocess
from pathlib import Path

# When installed as a package, we are sysml_mcp.cli. When run directly, we might need sys.path adjustments.
try:
    from sysml_mcp.server import dump_model, _validator, HERE, KERNEL_JAR
except ImportError:
    # If not installed via pip, assume we are in mcp-server
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from server import dump_model, _validator, HERE, KERNEL_JAR


def run_setup():
    """
    Downloads the SysML Pilot kernel JAR and compiles the Java validator.
    This replaces the need for `gh` CLI in CI environments.
    """
    print("Running sysml setup...")
    
    # 1. Download the kernel JAR if missing
    kernel_version = os.environ.get("KERNEL_VERSION", "0.59.0")
    kernel_release = os.environ.get("KERNEL_RELEASE", "2026-04")
    
    jar_path = Path(KERNEL_JAR).expanduser().resolve()
    
    if not jar_path.exists():
        print(f"Kernel jar not found at: {jar_path}")
        jar_path.parent.mkdir(parents=True, exist_ok=True)
        
        url = f"https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation/releases/download/{kernel_release}/jupyter-sysml-kernel-{kernel_version}.zip"
        print(f"Downloading {url}...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "kernel.zip"
            try:
                urllib.request.urlretrieve(url, zip_path)
            except Exception as e:
                print(f"ERROR: Failed to download kernel jar from {url}\n{e}", file=sys.stderr)
                sys.exit(1)
                
            print("Extracting JAR...")
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # The zip contains a folder e.g. "sysml/jupyter-sysml-kernel-0.59.0-all.jar"
                target_filename = f"sysml/jupyter-sysml-kernel-{kernel_version}-all.jar"
                try:
                    jar_data = zf.read(target_filename)
                    with open(jar_path, 'wb') as f:
                        f.write(jar_data)
                except KeyError:
                    print(f"ERROR: Failed to find {target_filename} inside the zip.", file=sys.stderr)
                    sys.exit(1)
    else:
        print(f"Kernel jar already exists at: {jar_path}")

    # 2. Compile the warm validator server
    print("Compiling Java validator server...")
    try:
        # We need java and javac
        subprocess.run(["javac", "-version"], check=True, capture_output=True)
    except FileNotFoundError:
        print("ERROR: javac 21+ is required but not found on PATH.", file=sys.stderr)
        sys.exit(1)
        
    try:
        _validator._ensure_compiled()
        print("Setup complete.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to compile Java server.\n{e.stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def run_dump(args):
    """
    Invokes the dump_model logic to export the SysML model as JSON.
    """
    result = dump_model(path=args.file, context_paths=args.context)
    
    if not result.get("ok", False):
        print("Parse error(s) occurred:", file=sys.stderr)
        diagnostics = result.get("diagnostics", [])
        for d in diagnostics:
            print(f"[{d.get('severity', 'ERROR')}] line {d.get('line', '?')}, col {d.get('column', '?')}: {d.get('message', '')}", file=sys.stderr)
        sys.exit(1)
        
    # The JSON must match byte-for-byte with the original dump_model output,
    # but dump_model itself returns a dict. We serialize it similarly.
    # Actually, EconVPP uses generate_records.py which loads the JSON.
    out = json.dumps(result, indent=2, sort_keys=True)
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        print(out)


def main():
    parser = argparse.ArgumentParser(prog="sysml", description="SysML v2 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    setup_p = subparsers.add_parser("setup", help="Download kernel jar and compile validator")
    
    dump_p = subparsers.add_parser("dump", help="Dump SysML model to JSON")
    dump_p.add_argument("file", help="SysML file to dump")
    dump_p.add_argument("--context", action="append", default=[], help="Context SysML files")
    dump_p.add_argument("-o", "--output", help="Output JSON file")
    
    args = parser.parse_args()
    
    if args.command == "setup":
        run_setup()
    elif args.command == "dump":
        run_dump(args)


if __name__ == "__main__":
    main()
