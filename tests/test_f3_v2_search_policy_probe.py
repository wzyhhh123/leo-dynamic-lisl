"""Real B/C structural policy tests; no traffic or controller objective."""
import itertools
import unittest
from dynamic_lisl.terminal_executor import TerminalExecutor, Connect
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog, TerminalPairWindow
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.operational_policy import OperationalPolicy
from dynamic_lisl.f3_v2.batch_executor import BatchPhysicalValidator, BatchSafetyValidator
from dynamic_lisl.f3_v2.joint_proposer import JointSearchBudget
from dynamic_lisl.f3_v2.joint_action import terminal_state_hash
from dynamic_lisl.f3_v2.search_policy_probe import scout, StructuralPolicyProbeProposer, old_order


def structural_fixture(window_side=6, reverse=False):
    nodes = tuple(sorted(c+str(i) for c, count in [('A',4),('B',4),('C',window_side),('D',window_side)] for i in range(count)))
    planes = {n: int(n[0] in ('B','D')) for n in nodes}
    old = tuple((("A"+str(i),'D1'),("B"+str(i),'D1')) for i in range(4))
    windows = tuple(TerminalPairWindow('C'+str(i),'D1','D'+str(j),'D1',0,30) for i in range(window_side) for j in range(window_side))
    if reverse:
        windows = windows[::-1]
    ex = TerminalExecutor(nodes)
    ex.submit(tuple(Connect(*ends,30,0,0,0) for ends in old))
    physical = TerminalPairPhysicalFeasibility(TerminalPairCatalog(windows,planes))
    fixed = tuple(zip(nodes[:-1],nodes[1:]))
    validator = BatchSafetyValidator(BatchPhysicalValidator(physical,max_batch_replace=4,
        observation_end_s=30,absolute_time_frame_id='PROBE_TEST'),fixed,OperationalPolicy('STRICT_CONNECTED'))
    return ex, physical, planes, validator


def source(ex, physical, planes, epoch_index=0):
    return scout(ex,physical,plane_by_satellite=planes,epoch_index=epoch_index,
                 retarget_a_s=1,retarget_b_s=1,acquisition_s=1,observation_end_s=30)


def budget(size=4):
    return JointSearchBudget(16,8,4,32 if size==4 else 16,size,184 if size==4 else 16,
                            184 if size==4 else 16,33 if size==4 else 17)


class StructuralPolicyProbeTests(unittest.TestCase):
    def test_known_witness_domain_discovers_every_registered_size_without_J(self):
        ex,p,planes,v=structural_fixture()
        initial=terminal_state_hash(ex)
        raw=source(ex,p,planes)
        pool=StructuralPolicyProbeProposer(v,budget(),epoch_index=0).propose(ex,raw['members'])
        self.assertEqual(raw['audit']['scout_visits'],144)
        self.assertEqual(raw['audit']['source_physical_calls'],144)
        self.assertEqual(len({m.old_binding for m in raw['members']}),4)
        for size in (2,3,4):
            self.assertGreater(pool.audit['coverage_by_size'][str(size)],0)
            for plan in pool.plans:
                if len(plan.action.members)==size:
                    self.assertTrue(plan.accepted)
                    for a,b in itertools.combinations(plan.action.members,2):
                        self.assertFalse(a.footprint & b.footprint)
        self.assertEqual(terminal_state_hash(ex),initial)
        self.assertFalse(raw['audit']['performance_input_read'])

    def test_repeat_shuffle_exact_order_hash_and_same_root(self):
        ex,p,planes,v=structural_fixture()
        ex2,p2,planes2,v2=structural_fixture(reverse=True)
        a,b=source(ex,p,planes),source(ex2,p2,planes2)
        self.assertEqual(a['audit'],b['audit'])
        proposer=StructuralPolicyProbeProposer(v,budget(),epoch_index=0)
        first=proposer.propose(ex,a['members'])
        second=proposer.propose(ex,a['members'][::-1])
        self.assertEqual(first.public_document(),second.public_document())
        self.assertEqual(first.public_document(),StructuralPolicyProbeProposer(v2,budget(),epoch_index=0).propose(ex2,b['members']).public_document())

    def test_visit256_cap_not_raw64_computational_claim_and_omissions_unknown(self):
        ex,p,planes,v=structural_fixture(window_side=9)
        raw=source(ex,p,planes)
        self.assertEqual(raw['audit']['metadata_domain_size'],324)
        self.assertEqual(raw['audit']['scout_visits'],256)
        self.assertEqual(raw['audit']['source_physical_calls'],256)
        self.assertEqual(raw['audit']['outside_domain_status'],'UNKNOWN_OUTSIDE_SCOUTED_DOMAIN')
        self.assertEqual(raw['audit']['unvisited_identity_count'],68)
        self.assertFalse(raw['audit']['raw_output_cap_is_compute_cap'])
        ids=[r['member_id'] for r in raw['audit']['visited_rows']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertLessEqual(len(raw['members']),64)

    def test_group_shortage_backfill_footprint_cover_and_batch1_same_singletons(self):
        ex,p,planes,v=structural_fixture()
        raw=source(ex,p,planes)
        self.assertEqual(raw['audit']['stratum_counts'],{'MBB':32,'BBM':0})
        a=StructuralPolicyProbeProposer(v,budget(),epoch_index=0).propose(ex,raw['members'])
        b=StructuralPolicyProbeProposer(v,budget(1),epoch_index=0).propose(ex,raw['members'])
        self.assertEqual(a.audit['singleton_member_ids'],b.audit['singleton_member_ids'])
        self.assertEqual(len(a.physical_singletons),16)
        self.assertEqual(len({m.old_binding for m in a.physical_singletons}),4)
        self.assertTrue(all(len(x.members)<=1 for x in b.actions))
        self.assertLessEqual(len(b.actions),17)

    def test_seed_beam_de_dup_shared_count_exact_canonical_members(self):
        ex,p,planes,v=structural_fixture()
        raw=source(ex,p,planes)
        pool=StructuralPolicyProbeProposer(v,budget(),epoch_index=0).propose(ex,raw['members'])
        ids=pool.audit['evaluated_index_tuples']
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(len(ids),pool.audit['joint_validation_calls'])
        self.assertEqual(len(ids),pool.audit['structural_expansions'])
        self.assertLessEqual(len(ids),184)
        self.assertTrue(all(i==tuple(sorted(i)) for i in ids))
        self.assertLessEqual(len(pool.audit['structural_seed_index_tuples']),12)
        self.assertEqual(pool.actions[0].members,())
        self.assertLessEqual(len(pool.actions),33)
        self.assertGreater(pool.audit['cache_hits_same_index_tuple'],0)

    def test_epoch_rotation_includes_HOLD_schedule_index(self):
        ex,p,planes,v=structural_fixture()
        _,a=old_order(ex,0);_,b=old_order(ex,1);_,c=old_order(ex,4)
        self.assertEqual(b,a[1:]+a[:1]);self.assertEqual(c,a)
        raw=source(ex,p,planes,1)
        self.assertEqual(raw['audit']['visited_rows'][0]['old'],b[0])
        with self.assertRaises(ValueError):old_order(ex,True)

    def test_zero_old_and_zero_window_guard(self):
        ex,p,planes,v=structural_fixture()
        idle=TerminalExecutor(ex.satellite_ids)
        self.assertEqual(source(idle,p,planes)['audit']['scout_visits'],0)
        empty=TerminalPairPhysicalFeasibility(TerminalPairCatalog((),planes))
        self.assertEqual(source(ex,empty,planes)['audit']['source_physical_calls'],0)
        raw=source(idle,p,planes)
        pool=StructuralPolicyProbeProposer(v,budget(),epoch_index=0).propose(idle,raw['members'])
        self.assertEqual(len(pool.actions),1)

    def test_real_mixed_BBM_MBB_strata_and_exact_current_readiness(self):
        from test_f3_v2_batch_executor import fixture
        ex,action,v,_=fixture(('BBM','MBB','BBM','MBB'))
        p=v.physical_validator.physical_layer
        raw=source(ex,p,p.catalog.plane_by_satellite)
        self.assertGreater(raw['audit']['stratum_counts']['BBM'],0)
        self.assertGreater(raw['audit']['stratum_counts']['MBB'],0)
        for row in raw['audit']['visited_rows']:
            if row['accepted']:
                self.assertEqual(row['ready_time_s'],2.)
        pool=StructuralPolicyProbeProposer(v,budget(),epoch_index=0).propose(ex,raw['members'])
        self.assertLessEqual(pool.audit['joint_validation_calls'],184)
        self.assertEqual(terminal_state_hash(ex),v.evaluate(ex,action).root_terminal_sha256)

    def test_expiring_window_rejections_preserved_not_called_absence_outside_scout(self):
        ex,p,planes,v=structural_fixture()
        windows=tuple(TerminalPairWindow(w.sat_a,w.terminal_a,w.sat_b,w.terminal_b,0,1.) for values in p.catalog.windows.values() for w in values)
        short=TerminalPairPhysicalFeasibility(TerminalPairCatalog(windows,planes))
        raw=source(ex,short,planes)
        self.assertEqual(raw['members'],())
        self.assertEqual(raw['audit']['source_physical_calls'],144)
        self.assertTrue(all(not r['accepted'] and r['reason'] for r in raw['audit']['visited_rows']))
