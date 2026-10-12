"""Passive caps/resource checks plus failure-first real tiny episode integration."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from test_f3_v2_engineering_episode import scene
from dynamic_lisl.f3_v2.candidate_source import RawCandidateBudget
from dynamic_lisl.f3_v2.epoch_validation import validate_epoch_inputs
from dynamic_lisl.f3_v2.episode_execution import execute_episode


def inputs():
    args = scene('B1-v2'); engine = args['engine']
    members, _ = args['source'](engine, args['validator'])
    pool = args['proposer'].propose(engine.executor, members,
        decision_root_sha256=engine.decision_root_sha256())
    audit = {'selected_member_ids': [m.member_id for m in members],
        'stratum_counts': {'BBM': 1, 'MBB': 1}}
    return args, pool, audit


class EpochValidationTests(unittest.TestCase):
    def validate(self, args, pool, audit):
        return validate_epoch_inputs(args['engine'], pool, audit,
            raw_budget=RawCandidateBudget(1, 1, 2), search_budget=args['proposer'].budget)

    def test_real_valid_pool_exact_no_mutation(self):
        args, pool, audit = inputs(); before = args['engine'].canonical_state_sha256()
        result = self.validate(args, pool, audit)
        self.assertEqual(result['status'], 'PASS', result)
        self.assertEqual(before, args['engine'].canonical_state_sha256())
        self.assertTrue(result['source_output_caps_do_not_bound_screening'])

    def test_static_empty_source_is_valid(self):
        args = scene('B0-v2'); engine = args['engine']
        pool = args['proposer'].propose(engine.executor, (), decision_root_sha256=engine.decision_root_sha256())
        result = self.validate(args, pool, {'role': 'STATIC_NO_CANDIDATE_SEARCH'})
        self.assertEqual(result['status'], 'PASS', result)

    def test_corrupted_counts_expansions_and_root_are_not_clamped(self):
        for mode in ('raw', 'expansion', 'root'):
            with self.subTest(mode=mode):
                args, pool, audit = inputs()
                if mode == 'raw':audit['stratum_counts']['BBM'] = 3
                elif mode == 'expansion':
                    changed = deepcopy(pool.audit); changed['structural_expansions'] = 999
                    pool = replace(pool, audit=changed)
                else:pool = replace(pool, root_sha256='f' * 64)
                result = self.validate(args, pool, audit)
                self.assertEqual(result['status'], 'FAIL')
                if mode == 'raw':self.assertEqual(result['items']['raw_BBM_cap']['observed'], 3)
                elif mode == 'expansion':self.assertEqual(result['items']['structural_expansions']['observed'], 999)
                else:self.assertFalse(result['items']['same_decision_root']['pass'])

    def test_order_corruption_breaks_identity_hash_and_HOLD_rule(self):
        args, pool, audit = inputs()
        self.assertGreater(len(pool.actions), 1)
        changed = replace(pool, actions=tuple(reversed(pool.actions)))
        result = self.validate(args, changed, audit)
        self.assertFalse(result['items']['proposal_identity_order_hash']['pass'])
        self.assertFalse(result['items']['HOLD_and_batch_permissions']['pass'])

    def test_failure_evidence_before_controller_or_real_action(self):
        args, _, audit = inputs(); calls = []
        members, _ = args['source'](args['engine'], args['validator'])
        audit['stratum_counts']['BBM'] = 3
        args['source'] = lambda live, validator: (members, audit)
        def check(live, pool, source_audit):
            calls.append(live.now)
            return self.validate(args, pool, source_audit)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'new_attempt'
            report = execute_episode(**args, output_dir=out, engineering_only=True,
                epoch_audit_validator=check)
            self.assertEqual(report['status'], 'FAIL_STOP')
            self.assertEqual(calls, [0])
            self.assertEqual(report['failure']['completed_controller_observations'], 0)
            self.assertEqual(args['engine'].batch_count, 0)
            saved = json.loads((out / 'run_evidence/invariant_report.json').read_text())
            self.assertFalse(saved['items']['epoch_candidate_resource_checks']['pass'])
            self.assertEqual(saved['items']['epoch_candidate_resource_checks']['observations'][0]
                ['items']['raw_BBM_cap']['observed'], 3)
            self.assertTrue((out / 'run_evidence/final_state_evidence.json').is_file())


if __name__ == '__main__':
    unittest.main()
