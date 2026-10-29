import importlib.util
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_biometrics.py"


def load_biometrics_module():
    spec = importlib.util.spec_from_file_location("sync_biometrics", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


biometrics = load_biometrics_module()


class ReauthorizationTests(unittest.TestCase):
    def test_external_credential_paths_and_navis_root_are_configurable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "vault"
            client_file = Path(directory) / "external-client.json"
            token_file = Path(directory) / "external-biometrics-token.json"
            with patch.dict(os.environ, {
                "NAVIS_ROOT": str(root),
                "NAVIS_BIOMETRICS_CLIENT_SECRETS_FILE": str(client_file),
                "NAVIS_BIOMETRICS_TOKEN_FILE": str(token_file),
            }):
                configured = load_biometrics_module()
            self.assertEqual(configured.CLIENT_SECRETS_FILE, str(client_file))
            self.assertEqual(configured.BIOMETRICS_TOKEN_FILE, str(token_file))
            self.assertEqual(configured.FINAL_DB_PATH, str(root / "Keeper" / "FitbitChronicle.db"))

    def test_cli_reauthorization_does_not_call_import(self):
        with patch.object(biometrics, "reauthorize_only", return_value=True) as authorize, patch.object(
            biometrics, "import_data"
        ) as import_data:
            self.assertEqual(biometrics.main(["--reauthorize-only"]), 0)
        authorize.assert_called_once_with()
        import_data.assert_not_called()

    def test_cancel_or_failure_keeps_existing_biometrics_and_shared_token(self):
        for failure in (KeyboardInterrupt(), RuntimeError("redacted sensitive exception data")):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as directory:
                dedicated = Path(directory) / "biometrics_token.json"
                shared = Path(directory) / "token.json"
                dedicated.write_bytes(b"existing-biometrics-token")
                shared.write_bytes(b"shared-gmail-token")
                flow = Mock()
                flow.run_local_server.side_effect = failure
                with patch.object(biometrics, "CLIENT_SECRETS_FILE", str(Path(directory) / "client.json")), patch.object(
                    biometrics, "BIOMETRICS_TOKEN_FILE", str(dedicated)
                ), patch.object(biometrics, "InstalledAppFlow") as flow_factory, patch.object(
                    biometrics.os.path, "exists", return_value=True
                ):
                    flow_factory.from_client_secrets_file.return_value = flow
                    self.assertFalse(biometrics.reauthorize_only())
                self.assertEqual(dedicated.read_bytes(), b"existing-biometrics-token")
                self.assertEqual(shared.read_bytes(), b"shared-gmail-token")
                flow.run_local_server.assert_called_once()

    def test_success_atomically_replaces_biometrics_token_only(self):
        with tempfile.TemporaryDirectory() as directory:
            dedicated = Path(directory) / "biometrics_token.json"
            shared = Path(directory) / "token.json"
            dedicated.write_bytes(b"old-biometrics-token")
            shared.write_bytes(b"shared-gmail-token")
            credentials = Mock(valid=True, refresh_token="placeholder-refresh")
            credentials.has_scopes.return_value = True
            credentials.to_json.return_value = json.dumps({"access_token": "new-value"})
            flow = Mock()
            flow.run_local_server.return_value = credentials
            with patch.object(biometrics, "CLIENT_SECRETS_FILE", str(Path(directory) / "client.json")), patch.object(
                biometrics, "BIOMETRICS_TOKEN_FILE", str(dedicated)
            ), patch.object(biometrics, "InstalledAppFlow") as flow_factory, patch.object(
                biometrics.os.path, "exists", return_value=True
            ):
                flow_factory.from_client_secrets_file.return_value = flow
                self.assertTrue(biometrics.reauthorize_only())
            self.assertEqual(json.loads(dedicated.read_text(encoding="utf-8")), {"access_token": "new-value"})
            self.assertEqual(shared.read_bytes(), b"shared-gmail-token")
            self.assertEqual(list(Path(directory).glob(".biometrics-token-*.tmp")), [])
            flow_factory.from_client_secrets_file.assert_called_once_with(
                str(Path(directory) / "client.json"), biometrics.SCOPES
            )

    def test_incomplete_credentials_do_not_replace_existing_token(self):
        credentials_without_refresh = Mock(valid=True, refresh_token="")
        credentials_without_refresh.has_scopes.return_value = True
        credentials_without_scope = Mock(valid=True, refresh_token="placeholder-refresh")
        credentials_without_scope.has_scopes.return_value = False
        for credentials in (credentials_without_refresh, credentials_without_scope):
            with self.subTest(has_refresh=bool(credentials.refresh_token)), tempfile.TemporaryDirectory() as directory:
                dedicated = Path(directory) / "biometrics_token.json"
                dedicated.write_bytes(b"existing-biometrics-token")
                flow = Mock()
                flow.run_local_server.return_value = credentials
                with patch.object(biometrics, "CLIENT_SECRETS_FILE", str(Path(directory) / "client.json")), patch.object(
                    biometrics, "BIOMETRICS_TOKEN_FILE", str(dedicated)
                ), patch.object(biometrics, "InstalledAppFlow") as flow_factory, patch.object(
                    biometrics.os.path, "exists", return_value=True
                ):
                    flow_factory.from_client_secrets_file.return_value = flow
                    self.assertFalse(biometrics.reauthorize_only())
                self.assertEqual(dedicated.read_bytes(), b"existing-biometrics-token")

    def test_client_configuration_error_is_safe_and_keeps_existing_token(self):
        with tempfile.TemporaryDirectory() as directory:
            dedicated = Path(directory) / "biometrics_token.json"
            dedicated.write_bytes(b"existing-biometrics-token")
            output = StringIO()
            with patch.object(biometrics, "CLIENT_SECRETS_FILE", str(Path(directory) / "client.json")), patch.object(
                biometrics, "BIOMETRICS_TOKEN_FILE", str(dedicated)
            ), patch.object(biometrics.os.path, "exists", return_value=True), patch.object(
                biometrics.InstalledAppFlow,
                "from_client_secrets_file",
                side_effect=ValueError("private client details"),
            ), redirect_stdout(output):
                self.assertFalse(biometrics.reauthorize_only())
            self.assertEqual(dedicated.read_bytes(), b"existing-biometrics-token")
            self.assertNotIn("private client details", output.getvalue())

    def test_default_cli_command_still_imports(self):
        with patch.object(biometrics, "reauthorize_only") as authorize, patch.object(
            biometrics, "import_data", return_value="imported"
        ) as import_data:
            self.assertEqual(biometrics.main([]), "imported")
        import_data.assert_called_once_with()
        authorize.assert_not_called()

    def test_expired_refresh_failure_prompts_command_without_starting_oauth(self):
        credentials = Mock(valid=False, expired=True, refresh_token="placeholder")
        credentials.refresh.side_effect = biometrics.RefreshError("invalid_grant with private response")
        output = StringIO()
        with patch.object(biometrics, "BIOMETRICS_TOKEN_FILE", "dedicated-token-path"), patch.object(
            biometrics.os.path, "exists", return_value=True
        ), patch.object(biometrics.Credentials, "from_authorized_user_file", return_value=credentials) as load_token, patch.object(
            biometrics, "InstalledAppFlow"
        ) as flow_factory, redirect_stdout(output):
            self.assertIsNone(biometrics.get_authenticated_session())
        load_token.assert_called_once_with("dedicated-token-path", biometrics.SCOPES)
        flow_factory.from_client_secrets_file.assert_not_called()
        self.assertIn("--reauthorize-only", output.getvalue())
        self.assertNotIn("private response", output.getvalue())

    def test_cli_returns_nonzero_when_reauthorization_fails(self):
        with patch.object(biometrics, "reauthorize_only", return_value=False), patch.object(
            biometrics, "import_data"
        ) as import_data:
            self.assertEqual(biometrics.main(["--reauthorize-only"]), 1)
        import_data.assert_not_called()


if __name__ == "__main__":
    unittest.main()
