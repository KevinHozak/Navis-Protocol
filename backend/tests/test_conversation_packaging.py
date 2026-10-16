import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ConversationPackagingTests(unittest.TestCase):
    def test_bootstrap_discards_noise_and_redacts_unexpected_failure(self):
        from services import conversation_runtime
        async def broken(*args):
            print('private conversation')
            raise RuntimeError('private token and path')
        with patch('services.conversation_service.dispatch', broken), patch('sys.stdin', io.StringIO('{}')), patch('sys.argv', ['runtime', 'warroom_chat']):
            output = conversation_runtime.run()
        self.assertEqual(output['http_status'], 503)
        self.assertNotIn('private', json.dumps(output))

    def test_missing_root_is_reported_without_a_machine_path_fallback(self):
        from services import conversation_runtime
        with patch.dict(os.environ, {"NAVIS_ROOT": "", "NAVIS_VAULT_ROOT": ""}), patch('sys.stdin', io.StringIO('{}')), patch('sys.argv', ['runtime', 'reid_history']):
            output = conversation_runtime.run()
        self.assertEqual(output['http_status'], 400)
        self.assertEqual(output['body']['code'], 'invalid_request')
        self.assertIn('Configure NAVIS_ROOT', output['body']['detail'])

    def test_note_configuration_errors_cross_runtime_boundary_safely(self):
        backend = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="navis-runtime-test-") as directory:
            cases = [
                ("private-invalid-json", "JSON array"),
                ('{"private": "value"}', "JSON array"),
                ('["../private-outside.md"]', "inside the Vault"),
                ('["private-note.txt"]', "inside the Vault"),
                (json.dumps([str(Path(directory) / "private-note.md")]), "inside the Vault"),
            ]
            for setting, expected in cases:
                with self.subTest(setting=setting):
                    environment = {**os.environ, "NAVIS_ROOT": directory,
                                   "NAVIS_REID_NOTE_FILES": setting}
                    result = subprocess.run(
                        [sys.executable, "-m", "services.conversation_runtime", "reid_chat"],
                        input='{"message":"Synthetic test"}', text=True,
                        capture_output=True, cwd=backend, env=environment, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, "")
                    output = json.loads(result.stdout)
                    self.assertEqual(output["http_status"], 400)
                    self.assertEqual(output["body"]["code"], "invalid_request")
                    self.assertEqual(output["body"]["status"], "error")
                    self.assertIn(expected, output["body"]["detail"])
                    self.assertNotIn("private", result.stdout)
                    self.assertNotIn(directory, result.stdout)

    def test_unexpected_value_error_remains_redacted(self):
        from services import conversation_runtime
        async def broken(*args):
            raise ValueError("private internal details")
        with patch('services.conversation_service.dispatch', broken), patch('sys.stdin', io.StringIO('{}')), patch('sys.argv', ['runtime', 'reid_chat']):
            output = conversation_runtime.run()
        self.assertEqual(output['http_status'], 503)
        self.assertNotIn('private', json.dumps(output))

    def test_packaged_modules_and_missing_dependencies_have_structured_responses(self):
        repo = Path(__file__).resolve().parents[2]
        resources = json.loads((repo / 'frontend/src-tauri/tauri.conf.json').read_text())['bundle']['resources']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source, destination in resources.items():
                if destination.startswith('backend/services/'):
                    target = root / destination
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(repo / 'frontend/src-tauri' / source, target)
            environment = {**os.environ, 'NAVIS_ROOT': str(root / 'vault')}
            def execute(*flags):
                result = subprocess.run([sys.executable, *flags, '-m', 'services.conversation_runtime', 'warroom_history'],
                    input='{}', text=True, capture_output=True, cwd=root / 'backend', env=environment, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            self.assertEqual(execute()['body']['history'], [])
            missing = execute('-S')  # No site-packages: aiohttp cannot be imported.
            self.assertEqual(missing['http_status'], 503)
            self.assertIn('dependencies', missing['body']['detail'])
            self.assertNotIn(str(root), json.dumps(missing))
            self.assertEqual(execute()['http_status'], 200)


if __name__ == '__main__':
    unittest.main()
