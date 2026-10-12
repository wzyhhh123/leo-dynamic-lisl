"""Readonly audit of actual 42-run draft; no registered run or freeze."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from dynamic_lisl.f3_v2.manifest_review import prepare_execution_review
from dynamic_lisl.f3_v2.joint_action import canonical_sha256

ROOT=Path(__file__).resolve().parents[1]
REL='configs/F3_V2_PAPER_EXPERIMENT_MATRIX_DRAFT.json'


class ManifestReviewTests(unittest.TestCase):
    def read(self):return json.loads((ROOT/REL).read_text(encoding='utf-8'))
    def resign(self,m):
        m={k:v for k,v in m.items() if k!='draft_canonical_sha256'}
        return {**m,'draft_canonical_sha256':canonical_sha256(m)}

    def test_all_42_ids_axes_costs_and_pending_freezes_preserved(self):
        matrix=self.read();review=prepare_execution_review(ROOT,matrix,matrix_relative_path=REL)
        self.assertEqual([r['run_id'] for r in review['runs']],[r['run_id'] for r in matrix['runs']])
        self.assertTrue(all(review['checks'].values()));self.assertFalse(review['formal_ready'])
        self.assertFalse(review['frozen']);self.assertTrue(review['unresolved'])
        for row in review['runs']:
            self.assertFalse(row['execution_authorized'])
            self.assertIsNone(row['runtime_budget']['estimated_wall_clock_s'])
            self.assertEqual(row['K'],4 if row['topology_regime']=='K4_HISTORICAL_REFERENCE' else None)

    def test_changed_parent_false_freeze_order_id_and_action_grid_rejected(self):
        for fault in ('hash','frozen','order','id','cadence','permission'):
            with self.subTest(fault=fault):
                matrix=self.read()
                if fault=='hash':matrix['parent_artifact_sha256']['configs/z_moderate_v1.json']='0'*64
                elif fault=='frozen':matrix['frozen']=True
                elif fault=='order':matrix['runs'].reverse()
                elif fault=='id':matrix['runs'][1]['run_id']=matrix['runs'][0]['run_id']
                elif fault=='cadence':matrix['runs'][0]['decision_cadence_s']=3
                else:matrix['runs'][0]['max_batch_replace']=2
                with self.assertRaises(ValueError):prepare_execution_review(ROOT,self.resign(matrix),matrix_relative_path=REL)

    def test_missing_primary_pair_or_unequal_permissions_rejected(self):
        for fault in ('missing','unequal'):
            matrix=self.read()
            if fault=='missing':matrix['contrasts']=[c for c in matrix['contrasts'] if c['contrast_id']!='PRIMARY_CONTROLLER-01']
            else:matrix['runs'][0]['max_batch_replace']=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                prepare_execution_review(ROOT,self.resign(matrix),matrix_relative_path=REL)

    def test_resigned_in_memory_changes_cannot_claim_original_source_hash(self):
        matrix=self.read();matrix['runs'][0]['scientific_role']='unapproved replacement'
        with self.assertRaisesRegex(ValueError,'SOURCE_MATRIX_CONTENT_MISMATCH'):
            prepare_execution_review(ROOT,self.resign(matrix),matrix_relative_path=REL)
        with self.assertRaisesRegex(ValueError,'EXACT_LOCAL_SOURCE_MATRIX_REQUIRED'):
            prepare_execution_review(ROOT,self.read(),matrix_relative_path='../outside.json')


if __name__=='__main__':unittest.main(verbosity=2)
