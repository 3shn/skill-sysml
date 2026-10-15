"""Real startup entrypoint against isolated index/protocol fixtures; no Java or network."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / 'tests/test_mcp_startup.py'
FIXTURES = ROOT / 'tests/fixtures/startup'


class StartupControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='startup-control-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'tests').mkdir()
        self.script = self.root / 'tests/test_mcp_startup.py'
        shutil.copyfile(SMOKE, self.script)
        self.runtime = self.root / 'runtime'
        self.library = self.runtime / 'sysml.library'
        self.pidfile = self.root / 'child.pid'
        self.env = dict(os.environ, SYSML_RUNTIME=str(self.runtime), STARTUP_TEST_PID=str(self.pidfile))

    def run_smoke(self, fake=None, timeout=None):
        command = [sys.executable, str(ROOT / 'mcp-server/server.py')]
        if fake:
            command = [sys.executable, str(FIXTURES / 'fake_mcp.py')]
            self.env['STARTUP_TEST_CASE'] = fake
        (self.root / '.mcp.json').write_text(json.dumps({'mcpServers': {'sysml': {
            'command': command[0], 'args': command[1:], 'cwd': '.'}}}))
        argv = [sys.executable, str(self.script)]
        if timeout is not None:
            # In-process timeout argument is test-only; command-line compatibility is unchanged.
            launcher = ('import importlib.util; '
                        's=importlib.util.spec_from_file_location("smoke",'+repr(str(self.script))+'); '
                        'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                        'm.main(response_timeout='+repr(timeout)+')')
            argv = [sys.executable, '-c', launcher]
        return subprocess.run(argv, cwd=self.root, env=self.env, text=True,
                              capture_output=True, timeout=5)

    def assert_rejected(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('SUCCESS:', result.stdout)

    def test_missing_directory_rejected(self):
        self.assert_rejected(self.run_smoke())

    def test_existing_empty_directory_rejected(self):
        self.library.mkdir(parents=True)
        self.assert_rejected(self.run_smoke())

    def test_unrelated_nonempty_mass_hit_rejected(self):
        self.library.mkdir(parents=True)
        (self.library / 'unrelated.sysml').write_text(
            'package Fixture {\n    attribute def MassValue;\n}\n')
        self.assert_rejected(self.run_smoke())

    def test_reference_element_index_fixture_passes_without_compiler_claim(self):
        self.library.mkdir(parents=True)
        shutil.copyfile(FIXTURES / 'expected-element.sysml', self.library / 'fixture.sysml')
        result = self.run_smoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ISQBase::MassValue', result.stdout)
        self.assertIn('Compiler validation: NOT_RUN', result.stdout)
        self.assertNotIn('resolved standard library OOB successfully', result.stdout)

    def test_malformed_or_unrelated_tool_results_rejected(self):
        for mode in ('empty', 'unrelated', 'wrong-kind', 'wrong-declaration',
                     'malformed-item', 'invalid-json-text', 'missing-content',
                     'result-string', 'structured-only', 'is-error', 'rpc-error'):
            with self.subTest(mode=mode):
                self.assert_rejected(self.run_smoke(fake=mode))

    def test_missing_expected_tool_rejected(self):
        self.assert_rejected(self.run_smoke(fake='missing-tool'))

    def test_malformed_initialization_and_wire_rejected(self):
        for mode in ('bad-initialize', 'malformed-wire', 'eof'):
            with self.subTest(mode=mode):
                self.assert_rejected(self.run_smoke(fake=mode))

    def test_child_reaped_after_success_and_rejection(self):
        for mode in ('valid', 'empty', 'rpc-error'):
            with self.subTest(mode=mode):
                result = self.run_smoke(fake=mode)
                self.assertEqual(result.returncode, 0 if mode == 'valid' else 1,
                                 result.stdout + result.stderr)
                pid = int(self.pidfile.read_text())
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)

    def test_silent_and_partial_line_timeout_reaps_child(self):
        for mode in ('silent', 'partial'):
            with self.subTest(mode=mode):
                result = self.run_smoke(fake=mode, timeout=0.15)
                self.assert_rejected(result)
                self.assertIn('Timeout', result.stderr)
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(self.pidfile.read_text()), 0)

    def test_stderr_cannot_block_startup(self):
        result = self.run_smoke(fake='stderr-flood', timeout=0.5)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(self.pidfile.read_text()), 0)


if __name__ == '__main__':
    unittest.main()
