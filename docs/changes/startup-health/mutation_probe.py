"""Disable only the new library predicate in a temporary copy; require regression failures."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    source = Path(__file__).resolve().parents[3]
    text = (source/'tests/test_mcp_startup.py').read_text()
    enabled_hash = hashlib.sha256(text.encode()).hexdigest()
    before = 'if not library_ready(result):'
    after = 'if False:  # MUTATION: disable exact-library predicate'
    assert text.count(before) == 1
    with tempfile.TemporaryDirectory(prefix='sysml-mutation-') as tmp:
        root = Path(tmp)
        shutil.copytree(source/'tests', root/'tests', ignore=shutil.ignore_patterns('__pycache__'))
        (root/'mcp-server').symlink_to(source/'mcp-server', target_is_directory=True)
        command = [sys.executable,'-m','unittest','discover','-s','tests','-p','test_startup_controls.py','-v']
        enabled = subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=20)
        (root/'tests/test_mcp_startup.py').write_text(text.replace(before,after))
        disabled = subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=20)
        control = dict(enabled_exit=enabled.returncode,disabled_exit=disabled.returncode,
            enabled_source_sha256=enabled_hash,
            disabled_source_sha256=hashlib.sha256((root/'tests/test_mcp_startup.py').read_bytes()).hexdigest(),
            replacement=dict(before=before,after=after),
            disabled_failures=[line for line in disabled.stderr.splitlines() if line.startswith(('FAIL:','FAILED ('))],
            interpretation='test assertions must detect disabled predicate; real compiler NOT_RUN')
        print(json.dumps(control,indent=2))
        assert hashlib.sha256((source/'tests/test_mcp_startup.py').read_bytes()).hexdigest() == enabled_hash
        return 0 if enabled.returncode==0 and disabled.returncode==1 and 'FAIL: test_existing_empty_directory_rejected' in disabled.stderr and 'FAIL: test_unrelated_nonempty_mass_hit_rejected' in disabled.stderr else 1


if __name__ == '__main__':
    raise SystemExit(main())
