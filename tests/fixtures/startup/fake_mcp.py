"""Synthetic MCP responses for startup-check controls; never a compiler."""
import json
import os
from pathlib import Path
import sys
import time

mode = os.environ.get('STARTUP_TEST_CASE', 'valid')
if os.environ.get('STARTUP_TEST_PID'):
    Path(os.environ['STARTUP_TEST_PID']).write_text(str(os.getpid()))
item = dict(name='MassValue', qualified_name='ISQBase::MassValue', package='ISQBase',
            kind='attribute def', declaration='attribute def MassValue :> ScalarQuantityValue {',
            file='fixture.sysml', line=2)
for line in sys.stdin:
    request = json.loads(line)
    if mode == 'silent':
        time.sleep(30)
        continue
    if mode == 'partial':
        sys.stdout.write('{'); sys.stdout.flush(); time.sleep(30)
        continue
    if mode == 'eof':
        break
    if mode == 'malformed-wire':
        print('{bad json}', flush=True)
        continue
    if mode == 'stderr-flood':
        sys.stderr.write('x' * 262144); sys.stderr.flush()
    method = request['method']
    if method == 'initialize':
        result = dict(protocolVersion='2024-11-05', capabilities={'tools': {}},
                      serverInfo={'name': 'synthetic', 'version': '0'})
        if mode == 'bad-initialize':
            result = []
    elif method == 'tools/list':
        names = ['validate_sysml_file', 'query_library', 'get_library_element', 'dump_model']
        if mode == 'missing-tool':
            names.remove('query_library')
        result = {'tools': [{'name': name} for name in names]}
    else:
        rows = [item.copy()]
        if mode == 'empty': rows = []
        if mode == 'unrelated': rows[0]['qualified_name'] = 'Fixture::MassValue'
        if mode == 'wrong-kind': rows[0]['kind'] = 'attribute'
        if mode == 'wrong-declaration': rows[0]['declaration'] = 'attribute MassValue;'
        if mode == 'malformed-item': rows = [42]
        result = {'content': [{'type': 'text', 'text': json.dumps(rows)}]}
        if mode == 'invalid-json-text': result['content'][0]['text'] = 'not-json'
        if mode == 'missing-content': result = {}
        if mode == 'result-string': result = 'not-an-object'
        if mode == 'is-error': result['isError'] = True
        if mode == 'structured-only': result = {'structuredContent': {'items': rows}}
    packet = {'jsonrpc': '2.0', 'id': request['id'], 'result': result}
    if mode == 'rpc-error':
        packet = {'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -1, 'message': 'synthetic failure'}}
    print(json.dumps(packet), flush=True)
