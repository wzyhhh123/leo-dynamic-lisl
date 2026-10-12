"""Read-only checkpoint capture follows the real production decision timeline."""
from pathlib import Path
import unittest

from dynamic_lisl.common import read_json
from dynamic_lisl.gate_e2_experiments import GateE2Assets
from dynamic_lisl.gate_f3_p1_execution import P1RunExecutor

ROOT=Path(__file__).resolve().parents[1]


class CheckpointAlignmentTests(unittest.TestCase):
    def test_bypass_init_without_sink_is_disabled(self):
        legacy=P1RunExecutor.__new__(P1RunExecutor)
        legacy._checkpoint('H_pre_call',0.)
        self.assertEqual(legacy.__dict__,{})

    def test_checkpoint_capture_is_passive_and_in_order(self):
        assets=GateE2Assets()
        manifest=read_json(ROOT/'configs/gate_f3_execution_manifest_v1.json')
        row=next(item for item in manifest['runs']
                 if item['block_id']=='P1' and item['controller']=='B0'
                 and item['rho']==0.5)
        row={**row,'run_id':'ENGINEERING_PROFILE_ONLY-CHECKPOINT',
             'block_id':'ENGINEERING_PROFILE_ONLY'}
        records=[]
        plain=P1RunExecutor(assets,row)
        audited=P1RunExecutor(assets,row,checkpoint_sink=records.append)
        pre=audited.engine.canonical_state_sha256()
        try:
            plain._decision(0.,0)
            audited._decision(0.,0)
            self.assertEqual([item['checkpoint'] for item in records],
                ['H_pre_call','H_decision_root','H_post_observe','H_post_decision'])
            hashes={item['checkpoint']:item['canonical_state_sha256']
                    for item in records}
            self.assertEqual(hashes['H_pre_call'],pre)
            self.assertEqual(hashes['H_decision_root'],hashes['H_post_observe'])
            self.assertEqual(hashes['H_post_decision'],audited.engine.canonical_state_sha256())
            self.assertEqual(plain.engine.canonical_state(),audited.engine.canonical_state())
        finally:
            plain.close();audited.close()


if __name__=='__main__':
    unittest.main()
