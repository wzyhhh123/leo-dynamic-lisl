"""Fail-closed bootstrap registry checks without production preflight."""
import json
from pathlib import Path
import tempfile
import unittest
from dynamic_lisl.b4_runtime_seal import canonical, executor_compatibility_successor

class ExecutorSuccessorTests(unittest.TestCase):
    def test_missing_registry_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(executor_compatibility_successor(Path(tmp),'a'*64,'b'*64))

    def test_missing_gate_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'configs').mkdir()
            doc={'status':'AUTHORIZED_RUNTIME_SUCCESSOR','parent_hash':'a'*64,
                 'successor_hash':'b'*64,'evidence':{'report':'missing.json','report_sha256':'c'*64}}
            doc['canonical_sha256']=canonical(doc)
            (root/'configs/b4_executor_compatibility_successor_v1.json').write_text(json.dumps(doc))
            self.assertFalse(executor_compatibility_successor(root,'a'*64,'b'*64))
            self.assertFalse(executor_compatibility_successor(root,'d'*64,'b'*64))
            self.assertFalse(executor_compatibility_successor(root,'a'*64,'e'*64))

    def test_modified_registry_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'configs').mkdir()
            (root/'configs/b4_executor_compatibility_successor_v1.json').write_text(
                json.dumps({'canonical_sha256':'0'*64,'status':'AUTHORIZED_RUNTIME_SUCCESSOR'}))
            self.assertFalse(executor_compatibility_successor(root,'a'*64,'b'*64))
