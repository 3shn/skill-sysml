#!/usr/bin/env python3
import json
import subprocess
import sys
import time
from pathlib import Path

def main():
    root_dir = Path(__file__).resolve().parent.parent
    mcp_config = root_dir / ".mcp.json"

    if not mcp_config.exists():
        print(f"Error: Could not find {mcp_config}", file=sys.stderr)
        sys.exit(1)

    config = json.loads(mcp_config.read_text())
    server = config["mcpServers"]["sysml"]
    command = [server["command"], *server.get("args", [])]
    cwd = root_dir / server.get("cwd", ".")
    print(f"Starting MCP server through {mcp_config}...")
    
    # We clear the specific env vars to simulate an OOB user
    # who hasn't explicitly set SYSML_LIBRARY_PATH etc.
    import os
    env = os.environ.copy()
    env.pop("SYSML_LIBRARY_PATH", None)
    env.pop("SYSML_KERNEL_JAR", None)
    env.pop("SYSML_VALIDATOR_CLASSES", None)
    # Codex does not provide Claude's plugin-root variable. The plugin config
    # must therefore start successfully from its declared working directory.
    env.pop("CLAUDE_PLUGIN_ROOT", None)

    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
        cwd=cwd,
    )

    def send_request(req):
        print(f"-> {json.dumps(req)}")
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()

    def wait_for_response(expected_id, timeout=10.0):
        start = time.time()
        while time.time() - start < timeout:
            if proc.poll() is not None:
                stderr = proc.stderr.read()
                print(f"Error: Process died unexpectedly. Stderr: {stderr}", file=sys.stderr)
                sys.exit(1)
            
            line = proc.stdout.readline()
            if not line:
                continue
            
            print(f"<- {line.strip()}")
            try:
                resp = json.loads(line)
                if resp.get("id") == expected_id:
                    return resp
            except json.JSONDecodeError:
                pass
        
        print("Error: Timeout waiting for response", file=sys.stderr)
        proc.kill()
        sys.exit(1)

    # 1. Initialize
    send_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
    resp = wait_for_response(1)
    if "error" in resp:
        print(f"Error during initialize: {resp['error']}", file=sys.stderr)
        sys.exit(1)

    # 2. tools/list
    send_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    resp = wait_for_response(2)
    if "error" in resp:
        print(f"Error during tools/list: {resp['error']}", file=sys.stderr)
        sys.exit(1)
    
    # Check that tools are returned
    tools = resp.get("result", {}).get("tools", [])
    tool_names = [t["name"] for t in tools]
    print(f"Available tools: {tool_names}")
    
    if "validate_sysml_file" not in tool_names:
        print("Error: validate_sysml_file tool not found!", file=sys.stderr)
        sys.exit(1)

    # 3. Test querying the library to ensure dependencies (sysml.library) are accessible
    send_request({
        "jsonrpc": "2.0", 
        "id": 3, 
        "method": "tools/call", 
        "params": {
            "name": "query_library",
            "arguments": {"query": "mass"}
        }
    })
    resp = wait_for_response(3, timeout=30.0) # Library load can take a moment
    if "error" in resp or resp.get("result", {}).get("isError"):
        print(f"Error during tools/call query_library: {resp}", file=sys.stderr)
        sys.exit(1)
    
    print("\nSUCCESS: MCP server started, initialized, and resolved standard library OOB successfully!")
    proc.terminate()

if __name__ == "__main__":
    main()
