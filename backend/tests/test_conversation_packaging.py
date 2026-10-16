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
