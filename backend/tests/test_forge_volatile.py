"""Generated Portal previews only; never reads a real Vault or provider."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from services import forge_service as forge, forge_volatile as volatile

class GeneratedProvider:
    def __init__(self): self.calls=0
    async def generate(self, *args, **kwargs):
        self.calls+=1
        return json.dumps({field:("Aster" if field=="name" else "en-US-JennyNeural" if field=="voice_id" else "GENERATED_OUTPUT_CANARY") for field in forge.FIELDS})

class VolatileForgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"empty-vault";self.root.mkdir()
        self.proposals=Path(self.tmp.name)/"proposals";self.proposals.mkdir()
        self.patch=patch.object(forge,"store",return_value=self.proposals);self.patch.start();self.addCleanup(self.patch.stop)
        self.ids=[]
        self.addCleanup(self.clear)
        self.provider=GeneratedProvider()
    def clear(self):
        for identity in self.ids:volatile.discard(self.root,identity)
    def preview(self):
        p=asyncio.run(forge.submit(self.root,{"entity_type":"companion","name":"Aster","prompt":"GENERATED_REQUEST_CANARY"},self.provider,transient=True))
        self.ids.append(p["proposal_id"]);return p
    def test_preview_is_memory_only_and_discard_revokes_without_disk_fallback(self):
        p=self.preview();self.assertTrue(p["proposal_id"].startswith("portal-"))
        self.assertEqual(list(self.proposals.iterdir()),[]);self.assertEqual(list(self.root.iterdir()),[])
        self.assertEqual(volatile.read(self.root,p["proposal_id"])["blueprint"]["description"],"GENERATED_OUTPUT_CANARY")
        forge.discard(self.root,p)
        with self.assertRaises(forge.ForgeError):forge.approve(self.root,{**p,"approved":True})
    def test_foreign_root_and_expired_session_cannot_recover_preview(self):
        p=self.preview()
        with self.assertRaises(ValueError):volatile.read(self.root/"other",p["proposal_id"])
        with patch.object(volatile,"_clock",return_value=10**15):
            with self.assertRaises(ValueError):volatile.read(self.root,p["proposal_id"])
        self.assertEqual(list(self.proposals.iterdir()),[])
    def test_capacity_refuses_before_another_provider_call(self):
        with patch.object(volatile,"LIMIT",len(volatile._ITEMS)+1):
            self.preview()
            with self.assertRaises(forge.ForgeError):self.preview()
        self.assertEqual(self.provider.calls,1)
    def test_explicit_approval_only_writes_requested_generated_entity(self):
        p=self.preview()
        with self.assertRaises(forge.ForgeError):forge.approve(self.root,{**p,"approved":False})
        self.assertEqual(list(self.root.iterdir()),[])
        result=forge.approve(self.root,{**p,"approved":True})
        self.assertEqual(result["status"],"success")
        self.assertTrue(forge.destination(self.root,"companion","Aster").exists())
        with self.assertRaises(ValueError):volatile.read(self.root,p["proposal_id"])
        self.assertFalse(any(path.suffix==".json" for path in self.proposals.iterdir()))
    def test_timer_drop_clears_content_and_non_portal_storage_is_unchanged(self):
        p=self.preview();volatile._timed_drop(volatile._key(self.root,p["proposal_id"]))
        with self.assertRaises(ValueError):volatile.read(self.root,p["proposal_id"])
        legacy=asyncio.run(forge.submit(self.root,{"entity_type":"companion","name":"Aster","prompt":"generated"},self.provider))
        self.assertTrue(forge.proposal_path(self.root,legacy["proposal_id"]).is_file())
