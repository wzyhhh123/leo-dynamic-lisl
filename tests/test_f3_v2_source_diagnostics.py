"""The observer must return the real source result or explicit UNKNOWN/FAIL."""
import unittest
from unittest.mock import patch
from dynamic_lisl.f3_v2 import candidate_source
from dynamic_lisl.f3_v2.source_diagnostics import observe_replacement_source
from dynamic_lisl.f3_v2.joint_action import terminal_state_hash
from test_f3_v2_batch_executor import fixture


class SourceDiagnosticTests(unittest.TestCase):
    def inputs(self):
        ex,action,validator,planes=fixture(('MBB','MBB'))
        physical=validator.physical_validator.physical_layer
        # Fixture nodes are explicitly divided by each catalog endpoint.
        mapping=physical.catalog.plane_by_satellite
        return ex,physical,dict(plane_by_satellite=mapping,retarget_a_s=1,
            retarget_b_s=1,acquisition_s=1,observation_end_s=30,
            raw_budget=candidate_source.RawCandidateBudget(32,32,64))

    def test_completed_observation_exact_raw_identity_order_and_hash(self):
        ex,physical,kwargs=self.inputs();reference=candidate_source.replacement_inventory(ex,physical,**kwargs)
        observed=observe_replacement_source(ex,physical,max_evaluations=1000,wall_budget_s=10,**kwargs)
        self.assertEqual(observed['status'],'SOURCE_OBSERVATION_COMPLETE')
        self.assertEqual(observed['source_result'],reference)
        self.assertTrue(observed['rows']);self.assertTrue(observed['live_unchanged'])
        self.assertTrue(observed['wrapper_restored']);self.assertTrue(observed['complete_raw_coverage_known'])

    def test_budget_returns_unknown_never_a_truncated_production_source(self):
        ex,physical,kwargs=self.inputs();before=terminal_state_hash(ex);original=candidate_source.BatchPhysicalValidator
        result=observe_replacement_source(ex,physical,max_evaluations=1,wall_budget_s=10,**kwargs)
        self.assertEqual(result['status'],'SOURCE_OBSERVATION_BUDGET_UNKNOWN')
        self.assertIsNone(result['source_result']);self.assertEqual(result['evaluations_completed'],1)
        self.assertFalse(result['complete_raw_coverage_known']);self.assertTrue(result['partial_result_not_usable_as_source'])
        self.assertEqual(terminal_state_hash(ex),before);self.assertIs(candidate_source.BatchPhysicalValidator,original)

    def test_original_validation_error_is_fail_not_budget_or_complete(self):
        ex,physical,kwargs=self.inputs()
        with patch.object(physical,'evaluate',side_effect=RuntimeError('engineering failure')):
            result=observe_replacement_source(ex,physical,max_evaluations=1000,wall_budget_s=10,**kwargs)
        self.assertEqual(result['status'],'SOURCE_OBSERVATION_FAIL_STOP')
        self.assertIn('engineering failure',result['error']);self.assertTrue(result['wrapper_restored'])

    def test_passive_row_sink_and_repeated_calls_preserve_source_result(self):
        ex,physical,kwargs=self.inputs();sink=[]
        one=observe_replacement_source(ex,physical,max_evaluations=1000,wall_budget_s=10,row_sink=sink.append,**kwargs)
        two=observe_replacement_source(ex,physical,max_evaluations=1000,wall_budget_s=10,**kwargs)
        self.assertEqual(one['source_result'],two['source_result']);self.assertEqual(one['rows'],sink)
        self.assertEqual([r['member_id'] for r in one['rows']],[r['member_id'] for r in two['rows']])

    def test_observer_mutation_is_explicit_failure(self):
        ex,physical,kwargs=self.inputs()
        def unsafe_sink(row):ex.now+=1
        result=observe_replacement_source(ex,physical,max_evaluations=1000,wall_budget_s=10,row_sink=unsafe_sink,**kwargs)
        self.assertEqual(result['status'],'SOURCE_OBSERVATION_FAIL_STOP')
        self.assertFalse(result['live_unchanged']);self.assertIsNone(result['source_result'])


if __name__=='__main__':unittest.main(verbosity=2)
