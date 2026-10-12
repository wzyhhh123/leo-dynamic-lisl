from pathlib import Path
from unittest.mock import patch
import unittest
from dynamic_lisl import b4_runtime_seal as seal
ROOT=Path(__file__).resolve().parents[1]

class RuntimeSealTests(unittest.TestCase):
    def test_current_evidence(self):
        chain,_=seal.validate_runtime(ROOT)
        result=seal.paused_record(ROOT,ROOT/'outputs/gate_f3_p1_execution_20260925T161805_509200Z',chain)
        self.assertTrue(result['archive_verified'])
        self.assertFalse(result['resume_authorized'])

    def test_changed_current_source_rejected(self):
        real=seal.sha
        with patch.object(seal,'sha',side_effect=lambda p: '0'*64 if p.name=='rollout_clone.py' else real(p)):
            with self.assertRaises(AssertionError):seal.validate_runtime(ROOT)

    def test_changed_archive_rejected(self):
        chain,_=seal.validate_runtime(ROOT); real=seal.sha
        with patch.object(seal,'sha',side_effect=lambda p: '0'*64 if p.name=='pause_record.json' else real(p)):
            with self.assertRaises(AssertionError):
                seal.paused_record(ROOT,ROOT/'outputs/gate_f3_p1_execution_20260925T161805_509200Z',chain)

    def test_changed_live_evidence_rejected(self):
        chain,_=seal.validate_runtime(ROOT);real=seal.sha
        with patch.object(seal,'sha',side_effect=lambda p: '0'*64 if p.name=='run_ledger.jsonl' else real(p)):
            with self.assertRaises(AssertionError):
                seal.paused_record(ROOT,ROOT/'outputs/gate_f3_p1_execution_20260925T161805_509200Z',chain)
