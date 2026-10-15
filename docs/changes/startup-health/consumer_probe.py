"""Read-only toolchain consumer proof with setup mocked and no installation."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    args = parser.parse_args()
    checkout = args.toolchain.resolve()
    path = checkout / 'toolchain.py'
    pinned = '314cf082972adc723915ea5190cb79400d99bb94'
    original_run = subprocess.run
    expected = subprocess.check_output(['git', 'show', pinned + ':toolchain.py'], cwd=checkout)
    assert path.read_bytes() == expected
    spec = importlib.util.spec_from_file_location('toolchain_probe', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    source = Path(__file__).resolve().parents[3]
    calls = []
    with tempfile.TemporaryDirectory(prefix='sysml-consumer-') as tmp:
        root = Path(tmp)
        runtime = root / '.cache/sysml-copilot/0.59.0'
        runtime.mkdir(parents=True)
        # Skip artifact download; no fake binary is executed. Setup is explicitly mocked.
        (runtime / 'jupyter-sysml-kernel-0.59.0-all.jar').write_text('fixture, not executable')
        (runtime / 'sysml.library').mkdir()
        def controlled_run(command, **kwargs):
            if command == [str(source / 'mcp-server/setup.sh')]:
                calls.append('setup mocked, not executed')
                return subprocess.CompletedProcess(command, 0)
            if command == ['python3', str(source / 'tests/test_mcp_startup.py')]:
                calls.append('real startup check with check=True')
                assert kwargs['check'] is True
                return original_run(command, **kwargs, capture_output=True, text=True)
            raise AssertionError('unexpected subprocess')
        rejected = False
        try:
            with patch.object(module.subprocess, 'run', controlled_run):
                module.provision_sysml(source, root, {})
        except subprocess.CalledProcessError as error:
            rejected = error.returncode == 1
        wrapper = root / module.STATE / 'bin/sysml-mcp'
        receipt = root / module.STATE / 'receipt.json'
        proof = dict(toolchain_commit=pinned, toolchain_source_sha256=hashlib.sha256(expected).hexdigest(),
            startup_source_sha256=hashlib.sha256((source/'tests/test_mcp_startup.py').read_bytes()).hexdigest(),
            setup='MOCKED_NOT_RUN', startup='REAL_EMPTY_LIBRARY_REJECTED', rejected=rejected,
            wrapper_created=wrapper.exists(), receipt_created=receipt.exists(), calls=calls,
            scope='provision_sysml only; enclosing reconcile/install NOT_RUN; receipt noncreation is not a full install test')
        print(json.dumps(proof, indent=2))
        return 0 if rejected and not wrapper.exists() and not receipt.exists() else 1


if __name__ == '__main__':
    raise SystemExit(main())
