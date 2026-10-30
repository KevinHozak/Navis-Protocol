import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import forge_service as forge
from services.ai_provider import ProviderError


class Provider:
    async def generate(self, prompt, **kwargs):
        return json.dumps(
            {
                field: (
                    "Aster"
                    if field == "name"
                    else "en-US-JennyNeural"
                    if field == "voice_id"
                    else "A calm ally"
                )
                for field in forge.FIELDS
            }
        )


class ForgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "vault"
        self.root.mkdir()
        self.store = Path(self.temp.name) / "proposals"
        self.store.mkdir()
        self.mock = patch.object(forge, "store", return_value=self.store)
        self.mock.start()

    def tearDown(self):
        self.mock.stop()
        self.temp.cleanup()

    def preview(self, kind="companion"):
        return asyncio.run(
            forge.submit(
                self.root,
                {"entity_type": kind, "name": "Aster", "prompt": "test concept"},
                Provider(),
            )
        )

    def approval(self, p):
        return {"proposal_id": p["proposal_id"], "approved": True}

    def test_preview_and_rejected_approval_never_write(self):
        p = self.preview()
        for approved in (False, None, "true", 1):
            with self.assertRaises(forge.ForgeError):
                forge.approve(
                    self.root, {"proposal_id": p["proposal_id"], "approved": approved}
                )
        self.assertEqual(list(self.root.iterdir()), [])

    def test_controlled_scripts_all_types_and_retry(self):
        for kind in forge.SECTORS:
            p = self.preview(kind)
            updates = []
            forge.approve(self.root, self.approval(p), updates.append)
            target = forge.destination(self.root, kind, "Aster")
            before = {f.name: f.read_bytes() for f in target.iterdir() if f.is_file()}
            forge.approve(self.root, self.approval(p))
            self.assertEqual(
                before,
                {f.name: f.read_bytes() for f in target.iterdir() if f.is_file()},
            )
            self.assertEqual(len(updates), 3)

    def test_discard_revokes(self):
        p = self.preview()
        forge.discard(self.root, p)
        with self.assertRaises(forge.ForgeError):
            forge.approve(self.root, self.approval(p))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_names_types_fields(self):
        for name in ("../escape", "..", "CON", "C:\\evil", "a/b", "-flag", "a.", " a"):
            with self.assertRaises(forge.ForgeError):
                forge.validate("companion", name)
        with self.assertRaises(forge.ForgeError):
            forge.validate("mission", "Aster")
        p = self.preview()
        for field, value in (
            ("name", "Other"),
            ("description", "<script>x</script>"),
            ("voice_id", "--evil"),
            ("height", {}),
        ):
            bad = dict(p["blueprint"])
            bad[field] = value
            with self.assertRaises(forge.ForgeError):
                forge.validate("companion", "Aster", bad)

    def test_script_failure_rolls_back_and_can_retry(self):
        p = self.preview()
        with patch.object(
            forge.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)
        ):
            with self.assertRaises(forge.ForgeError):
                forge.approve(self.root, self.approval(p))
        self.assertFalse(forge.destination(self.root, "companion", "Aster").exists())
        self.assertFalse(
            any(
                f.name.startswith(".forge-")
                for f in (self.root / "Companions").iterdir()
            )
        )
        forge.approve(self.root, self.approval(p))

    def test_provider_failure_and_malformed_output(self):
        class Broken:
            async def generate(self, *args, **kwargs):
                raise ProviderError("Unavailable")

        class Malformed:
            async def generate(self, *args, **kwargs):
                return '{"name":"Aster"}'

        for provider, error in (
            (Broken(), ProviderError),
            (Malformed(), forge.ForgeError),
        ):
            with self.assertRaises(error):
                asyncio.run(
                    forge.submit(
                        self.root,
                        {
                            "entity_type": "companion",
                            "name": "Aster",
                            "prompt": "concept",
                        },
                        provider,
                    )
                )
        self.assertEqual(list(self.root.iterdir()), [])

    def test_lock_prevents_concurrent_writes(self):
        p = self.preview()
        target = forge.destination(self.root, "companion", "Aster")
        lock = self.store / (hashlib.sha256(str(target).encode()).hexdigest() + ".lock")
        with forge.destination_lock(lock):
            with self.assertRaises(forge.ForgeError):
                forge.approve(self.root, self.approval(p))
        forge.approve(self.root, self.approval(p))

    def test_expiry(self):
        p = self.preview()
        path = forge.proposal_path(self.root, p["proposal_id"])
        record = json.loads(path.read_text())
        record["created"] = 0
        path.write_text(json.dumps(record))
        with self.assertRaises(forge.ForgeError):
            forge.approve(self.root, self.approval(p))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_occupied_destination_is_preserved(self):
        p = self.preview()
        target = forge.destination(self.root, "companion", "Aster")
        target.mkdir(parents=True)
        (target / "Profile.md").write_text("existing")
        with self.assertRaises(forge.ForgeError):
            forge.approve(self.root, self.approval(p))
        self.assertEqual((target / "Profile.md").read_text(), "existing")

    def test_redirected_path_rejected(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        try:
            (self.root / "Companions").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink creation not supported")
        with self.assertRaises(forge.ForgeError):
            self.preview()
        self.assertEqual(list(outside.iterdir()), [])

    def test_web_routes_preview_strict_approval_and_discard(self):
        import ast
        from fastapi import FastAPI, BackgroundTasks, HTTPException
        from fastapi.testclient import TestClient
        from pydantic import BaseModel, StrictBool, model_validator
        from typing import Optional

        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "main.py").read_text(
                encoding="utf-8-sig"
            )
        )
        selected = {
            "ForgeSubmitRequest",
            "ForgeApproveRequest",
            "ForgeDiscardRequest",
            "forge_submit",
            "forge_discard",
            "forge_approve",
            "run_forge_sequence_in_background",
        }
        module = ast.Module(
            body=[n for n in tree.body if getattr(n, "name", None) in selected],
            type_ignores=[],
        )
        ns = {
            "app": FastAPI(),
            "BaseModel": BaseModel,
            "StrictBool": StrictBool,
            "model_validator": model_validator,
            "Optional": Optional,
            "BackgroundTasks": BackgroundTasks,
            "HTTPException": HTTPException,
            "NAVIS_ROOT": str(self.root),
            "active_jobs": {},
        }
        exec(compile(module, "main.py", "exec"), ns)
        client = TestClient(ns["app"])
        with patch.object(forge, "get_provider", return_value=Provider()):
            preview = client.post(
                "/api/forge/submit",
                json={"entity_type": "companion", "name": "Aster", "prompt": "concept"},
            )
        self.assertEqual(preview.status_code, 200)
        p = preview.json()
        self.assertEqual(
            client.post(
                "/api/forge/approve",
                json={"proposal_id": p["proposal_id"], "approved": 1},
            ).status_code,
            422,
        )
        self.assertEqual(
            client.post(
                "/api/forge/approve",
                json={"proposal_id": p["proposal_id"], "approved": False},
            ).status_code,
            400,
        )
        self.assertEqual(list(self.root.iterdir()), [])
        response = client.post("/api/forge/approve", json=self.approval(p))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ns["active_jobs"][response.json()["job_id"]]["status"], "completed"
        )
        self.assertEqual(
            client.post(
                "/api/forge/discard", json={"proposal_id": p["proposal_id"]}
            ).status_code,
            200,
        )

    def test_native_dispatch_cannot_bypass_approval(self):
        env = os.environ.copy()
        env["NAVIS_ROOT"] = str(self.root)
        result = subprocess.run(
            [sys.executable, "-m", "services.forge_service", "approve"],
            input=json.dumps({"approved": False}),
            text=True,
            capture_output=True,
            cwd=Path(__file__).resolve().parents[1],
            env=env,
        )
        self.assertEqual(json.loads(result.stdout)["http_status"], 400)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_native_and_web_share_approved_proposal(self):
        self.mock.stop()
        p = self.preview("realm")
        env = os.environ.copy()
        env["NAVIS_ROOT"] = str(self.root)
        result = subprocess.run(
            [sys.executable, "-m", "services.forge_service", "approve"],
            input=json.dumps(self.approval(p)),
            text=True,
            capture_output=True,
            cwd=Path(__file__).resolve().parents[1],
            env=env,
        )
        self.assertEqual(json.loads(result.stdout)["http_status"], 200)
        self.assertEqual(
            forge.approve(self.root, self.approval(p))["status"], "success"
        )
        self.mock.start()


if __name__ == "__main__":
    unittest.main()
