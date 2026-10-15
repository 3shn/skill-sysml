#!/usr/bin/env python3
"""OOB MCP + library-index smoke. Real compiler validation is a separate check."""
import json
import os
import selectors
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Verified against SysML-v2-Release 9baca5908ca28b53da085de69336fde48420ea8f,
# sysml.library/Domain Libraries/Quantities and Units/ISQBase.sysml:66.
EXPECTED_NAME = 'ISQBase::MassValue'
EXPECTED_DECLARATION = 'attribute def MassValue :> ScalarQuantityValue {'
EXPECTED_TOOLS = {'validate_sysml_file', 'query_library', 'get_library_element', 'dump_model'}


def library_ready(result):
    """Check the current server's JSON-text list, not transport success or any hit."""
    if not isinstance(result, dict) or result.get('isError', False) is not False:
        return False
    # Lists are emitted in content as JSON text, not structuredContent, by server._handle.
    if 'structuredContent' in result:
        return False
    content = result.get('content')
    if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict):
        return False
    block = content[0]
    if block.get('type') != 'text' or not isinstance(block.get('text'), str):
        return False
    try:
        items = json.loads(block['text'])
    except ValueError:
        return False
    fields = ('name', 'qualified_name', 'package', 'kind', 'declaration')
    if not isinstance(items, list) or not items or any(
            not isinstance(item, dict) or any(not isinstance(item.get(k), str) for k in fields)
            for item in items):
        return False
    return any(item['name'] == 'MassValue' and item['qualified_name'] == EXPECTED_NAME
               and item['package'] == 'ISQBase' and item['kind'] == 'attribute def'
               and item['declaration'].splitlines()
               and item['declaration'].splitlines()[0].strip() == EXPECTED_DECLARATION
               for item in items)


def main(response_timeout=None):
    root_dir = Path(__file__).resolve().parent.parent
    config_path = root_dir / '.mcp.json'
    proc = None
    try:
        server = json.loads(config_path.read_text())['mcpServers']['sysml']
        command = [server['command'], *server.get('args', [])]
        env = os.environ.copy()
        # Preserve explicit shared SYSML_RUNTIME, but simulate no per-agent path overrides.
        for key in ('SYSML_LIBRARY_PATH', 'SYSML_KERNEL_JAR', 'SYSML_VALIDATOR_CLASSES', 'CLAUDE_PLUGIN_ROOT'):
            env.pop(key, None)
        print(f'Starting MCP server through {config_path}...')
        # A file avoids deadlock when stderr fills while we wait for a response.
        with tempfile.TemporaryFile() as errors, selectors.DefaultSelector() as selector:
            try:
                proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=errors, env=env, cwd=root_dir / server.get('cwd', '.'))
                selector.register(proc.stdout, selectors.EVENT_READ)
                buffered = b''

                def request(ident, method, params):
                    nonlocal buffered
                    message = dict(jsonrpc='2.0', id=ident, method=method, params=params)
                    print(f'-> {json.dumps(message)}')
                    proc.stdin.write((json.dumps(message) + '\n').encode())
                    proc.stdin.flush()
                    timeout = response_timeout
                    if timeout is None:
                        timeout = 30.0 if method == 'tools/call' else 10.0
                    deadline = time.monotonic() + timeout
                    while True:
                        if b'\n' not in buffered:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0 or not selector.select(remaining):
                                raise ValueError(f'Timeout waiting for {method}')
                            chunk = os.read(proc.stdout.fileno(), 65536)
                            if not chunk:
                                raise ValueError(f'MCP process closed stdout before {method} response')
                            buffered += chunk
                            # Bound malformed/no-newline output as well as elapsed time.
                            if len(buffered) > 1024 * 1024:
                                raise ValueError('MCP response exceeds smoke-test size limit')
                            continue
                        line, buffered = buffered.split(b'\n', 1)
                        response = json.loads(line)
                        print(f'<- {line.decode()}')
                        if not isinstance(response, dict) or response.get('jsonrpc') != '2.0':
                            raise ValueError('Malformed JSON-RPC response')
                        if response.get('id') != ident or 'error' in response or 'result' not in response:
                            raise ValueError(f'Unexpected/error response for {method}')
                        return response['result']

                initialized = request(1, 'initialize', {'protocolVersion': '2024-11-05'})
                if (not isinstance(initialized, dict) or initialized.get('protocolVersion') != '2024-11-05'
                        or not isinstance(initialized.get('capabilities'), dict)
                        or not isinstance(initialized['capabilities'].get('tools'), dict)):
                    raise ValueError('Malformed MCP initialization/capabilities')
                listing = request(2, 'tools/list', {})
                tools = listing.get('tools') if isinstance(listing, dict) else None
                if not isinstance(tools, list) or any(
                        not isinstance(tool, dict) or not isinstance(tool.get('name'), str) for tool in tools):
                    raise ValueError('Malformed MCP tool list')
                names = {tool['name'] for tool in tools}
                if not EXPECTED_TOOLS <= names:
                    raise ValueError(f'Missing expected MCP tools: {sorted(EXPECTED_TOOLS - names)}')
                result = request(3, 'tools/call', {'name': 'query_library', 'arguments': {'query': 'MassValue'}})
                if not library_ready(result):
                    raise ValueError(f'Library index did not return the expected {EXPECTED_NAME} definition')
            finally:
                if proc is not None:
                    if proc.poll() is None:
                        proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=2)
                    proc.stdin.close()
                    proc.stdout.close()
            print(f'\nSUCCESS: MCP startup and library-index lookup {EXPECTED_NAME} passed.')
            print('Compiler validation: NOT_RUN (not part of this smoke).')
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f'Error: startup smoke failed: {exc}', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
