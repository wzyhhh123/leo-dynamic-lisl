"""Real Gate C/B and frozen V_v2; no mocked score in these tiny fixtures."""
from dataclasses import replace
import unittest

from test_f3_v2_batch_executor import fixture,FRAME
from dynamic_lisl.commodity import Commodity
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace,TrafficSegment
from dynamic_lisl.gate_d2_fixtures import ConstantDelay
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.f3_v2.service_adapter import BatchNetworkServiceEngine
from dynamic_lisl.f3_v2.tiny_oracle import enumerate_tiny_joint_actions
from dynamic_lisl.f3_v2.tiny_diagnostics import audit_tiny_eta
from dynamic_lisl.f3_v2.structural import ObservedPhysicalLayer,legal_edge_inventory
from dynamic_lisl.f3_v2.snapshot_controllers import batch_target_edges,current_snapshot_view
from dynamic_lisl.scientific_snapshot import ScientificSnapshotEvaluator


def eta_fixture(short_end_s=30):
    executor,action,validator,fixed=fixture(('MBB','MBB'))
    pv=validator.physical_validator
    old=pv.physical_layer.catalog
    windows=[replace(w,end_s=short_end_s if w.sat_a=='A1' else w.end_s)
             for values in old.windows.values() for w in values]
    pv.physical_layer=TerminalPairPhysicalFeasibility(TerminalPairCatalog(windows,old.plane_by_satellite))
    commodities=(Commodity('f0','A0','D0'),Commodity('f1','A1','D1'))
    trace=PiecewiseConstantTrafficTrace(('f0','f1'),(TrafficSegment(0,4,{'f0':60,'f1':60},'FIXED_TINY_HIGH_LOAD'),))
    engine=BatchNetworkServiceEngine(executor.satellite_ids,fixed,40,commodities,trace,
        ConstantDelay(.05),executor,absolute_time_frame_id=FRAME)
    engine.advance_to(1)
    pool=enumerate_tiny_joint_actions(engine,validator,action.members,max_members=2)
    return engine,validator,pool


class TinyEtaTests(unittest.TestCase):
    def test_real_scores_full_graph_exact_and_no_mutation(self):
        engine,_,pool=eta_fixture(3.25);before=engine.canonical_state_sha256()
        report=audit_tiny_eta(engine,pool)
        evaluator=ScientificSnapshotEvaluator(current_snapshot_view(engine))
        hold=evaluator.evaluate_hold().value_bit_s
        for row in report['candidates']:
            action=next(a for a in pool.actions if a.batch_id==row['batch_id'])
            target=evaluator.evaluate_edges(batch_target_edges(engine,action)).value_bit_s
            self.assertEqual(row['deltaV'],hold-target)
            self.assertEqual(row['eta'],min(row['member_eta']))
            self.assertEqual(row['score'],max(0,row['deltaV'])*row['eta'])
        self.assertEqual(engine.canonical_state_sha256(),before)
        self.assertFalse(report['multi_step_rollout']);self.assertFalse(report['coefficients_tuned'])

    def test_same_current_world_short_window_only_changes_eta_not_deltaV(self):
        long,_,long_pool=eta_fixture();short,_,short_pool=eta_fixture(3.25)
        self.assertEqual(long.canonical_state_sha256(),short.canonical_state_sha256())
        a=audit_tiny_eta(long,long_pool);b=audit_tiny_eta(short,short_pool)
        by_id={r['batch_id']:r for r in a['candidates']}
        for row in b['candidates']:
            self.assertEqual(row['snapshot'],by_id[row['batch_id']]['snapshot'])
            self.assertEqual(row['deltaV'],by_id[row['batch_id']]['deltaV'])
        joint=next(r for r in b['candidates'] if r['batch_size']==2)
        self.assertLess(joint['eta'],by_id[joint['batch_id']]['eta'])
        self.assertEqual(joint['eta'],.25/2.25)

    def test_equal_eta_has_no_additional_batch_size_factor(self):
        engine,_,pool=eta_fixture();report=audit_tiny_eta(engine,pool)
        etas={r['eta'] for r in report['candidates']}
        self.assertEqual(etas,{27/29})
        for row in report['candidates']:self.assertEqual(row['score'],max(0,row['deltaV'])*(27/29))

    def test_observed_physical_layer_preserves_exact_results_and_root(self):
        executor,_,validator,_=fixture(('MBB','MBB'))
        physical=validator.physical_validator.physical_layer
        planes=physical.catalog.plane_by_satellite
        args=dict(retarget_a_s=1,retarget_b_s=1,acquisition_s=1,observation_end_s=30)
        before=executor.snapshot();reference=legal_edge_inventory(executor,physical,planes,**args)
        wrapped=ObservedPhysicalLayer(physical)
        actual=legal_edge_inventory(executor,wrapped,planes,**args)
        self.assertEqual(reference,actual);self.assertEqual(executor.snapshot(),before)
        self.assertEqual(len(wrapped.observations),len(reference['edges'])+len(reference['rejected']))
        self.assertTrue(all(row['wall_s']>=0 for row in wrapped.observations))


if __name__=='__main__':unittest.main(verbosity=2)
