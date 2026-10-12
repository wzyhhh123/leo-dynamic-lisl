"""Gate V2-A/B/C synthetic correctness, not registered performance runs."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest

from dynamic_lisl.terminal_executor import Connect, TerminalExecutor, ACTIVE
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog, TerminalPairWindow
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.operational_policy import OperationalPolicy
from dynamic_lisl.commodity import Commodity
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from dynamic_lisl.gate_d2_fixtures import ConstantDelay, fixture_d_draining_split
from dynamic_lisl.f3_v2.joint_action import (
    BatchReplaceMember, JointAction, canonical_sha256, terminal_state_hash)
from dynamic_lisl.f3_v2.batch_executor import (
    BatchPhysicalValidator, BatchSafetyValidator, AtomicBatchExecutor)
from dynamic_lisl.f3_v2.service_adapter import (
    BatchNetworkServiceEngine, ScriptedBatchProposal, DecisionSchedule, BatchCadenceAdapter)


FRAME = "SYNTHETIC_TRANSLATABLE_WORLD_V2"
POOL = canonical_sha256([])


def fixture(modes=("BBM", "BBM"), ends=30.0, retarget=1.0, acquisition=1.0):
    nodes = tuple("%s%d" % (c, i) for i in range(len(modes)) for c in "ABCD")
    ex = TerminalExecutor(nodes)
    members, windows = [], []
    for i, mode in enumerate(modes):
        old = (("A%d" % i, "D1"), ("B%d" % i, "D1"))
        ex.submit([Connect(*old, ends, 0.0, 0.0, 0.0)])
        new = (("A%d" % i, "D1"), ("C%d" % i, "D1")) if mode == "BBM" else (
            ("A%d" % i, "D2"), ("C%d" % i, "D2"))
        members.append(BatchReplaceMember("m%d" % i, i, old, new, retarget, retarget, acquisition))
        windows.append(TerminalPairWindow(*new[0], *new[1], 0.0, ends))
    # Fixed chain makes fixtures connected independently of dynamic links.
    fixed = tuple(zip(sorted(nodes)[:-1], sorted(nodes)[1:]))
    physical = TerminalPairPhysicalFeasibility(TerminalPairCatalog(windows, {n: i for i,n in enumerate(nodes)}))
    pv = BatchPhysicalValidator(physical, max_batch_replace=4, observation_end_s=30,
                                absolute_time_frame_id=FRAME)
    safety = BatchSafetyValidator(pv, fixed, OperationalPolicy("STRICT_CONNECTED"))
    action = JointAction(ex.now, FRAME, terminal_state_hash(ex), POOL, tuple(members))
    return ex, action, safety, fixed


def network(ex, fixed, horizon=6.0, rates=20.0):
    commodity = Commodity("f0", ex.satellite_ids[0], ex.satellite_ids[-1])
    trace = PiecewiseConstantTrafficTrace(("f0",), (TrafficSegment(0.0, horizon, {"f0": rates}, "synthetic"),))
    return BatchNetworkServiceEngine(ex.satellite_ids, fixed, 40.0, (commodity,), trace,
        ConstantDelay(0.05), ex, absolute_time_frame_id=FRAME)


class GateV2BatchTests(unittest.TestCase):
    def test_independent_2_3_4_bbm(self):
        for size in (2,3,4):
            with self.subTest(size=size):
                ex, a, v, _ = fixture(("BBM",)*size)
                before = terminal_state_hash(ex)
                p = v.evaluate(ex, a)
                self.assertTrue(p.accepted, p.reason)
                self.assertEqual(terminal_state_hash(ex), before)
                self.assertEqual([r["transition_mode"] for r in p.member_results], ["BBM"]*size)
                AtomicBatchExecutor(v).commit(ex, p)
                self.assertEqual(len(ex.reservations), size)
                self.assertEqual(len(ex.links), 0)
                ex.advance(2)
                self.assertEqual(len(ex.links), size)
                self.assertTrue(all(t.phase == ACTIVE for t in ex.terminals.values() if t.current_peer))
                ex.assert_invariants()

    def test_independent_2_3_4_mbb(self):
        for size in (2,3,4):
            with self.subTest(size=size):
                ex,a,v,_ = fixture(("MBB",)*size)
                p=v.evaluate(ex,a)
                self.assertTrue(p.accepted,p.reason)
                AtomicBatchExecutor(v).commit(ex,p)
                self.assertEqual(len(ex.links),size)
                self.assertEqual(len(ex.reservations),size)
                ex.advance(2)
                self.assertEqual(len(ex.links),size)
                self.assertTrue(all(ex._link(m.new_terminal_pair) for m in a.members))
                self.assertTrue(all(ex._link(m.old_binding) is None for m in a.members))

    def test_mixed_and_independent_second_terminal(self):
        ex,a,v,_=fixture(("BBM","MBB","BBM","MBB"))
        spare = ex.terminals[("D0","D2")].__dict__.copy()
        p=v.evaluate(ex,a)
        self.assertTrue(p.accepted,p.reason)
        AtomicBatchExecutor(v).commit(ex,p)
        self.assertEqual(len(ex.reservations),4)
        self.assertEqual(len(ex.links),2)
        self.assertEqual(ex.terminals[("D0","D2")].__dict__,spare)
        self.assertEqual(len(ex.fixed_ports),2*len(ex.satellite_ids))

    def test_duplicate_old_and_terminal_contention(self):
        ex,a,v,_=fixture()
        dupe=replace(a.members[0],member_id="different",canonical_index=1)
        p=v.evaluate(ex,replace(a,members=(a.members[0],dupe)))
        self.assertEqual(p.reason,"DUPLICATE_OLD_BINDING")
        conflict=replace(a.members[1],new_terminal_pair=(("A0","D1"),("C1","D1")))
        self.assertEqual(v.evaluate(ex,replace(a,members=(a.members[0],conflict))).reason,
                         "TERMINAL_FOOTPRINT_CONFLICT")

    def test_shared_satellite_distinct_terminals_allowed(self):
        ex=TerminalExecutor(("A","B","C","D","E"))
        old1=(("A","D1"),("B","D1"));old2=(("A","D2"),("C","D1"))
        ex.submit([Connect(*p,30,0,0,0) for p in (old1,old2)])
        ms=(BatchReplaceMember("a",0,old1,(("A","D1"),("D","D1")),1,1,1),
            BatchReplaceMember("b",1,old2,(("A","D2"),("E","D1")),1,1,1))
        windows=[TerminalPairWindow(*m.new_terminal_pair[0],*m.new_terminal_pair[1],0,30) for m in ms]
        pv=BatchPhysicalValidator(TerminalPairPhysicalFeasibility(TerminalPairCatalog(windows,{})),
            max_batch_replace=4,observation_end_s=30,absolute_time_frame_id=FRAME)
        p=pv.evaluate(ex,JointAction(0,FRAME,terminal_state_hash(ex),POOL,ms))
        self.assertTrue(p.accepted,p.reason)

    def test_reservation_conflict_and_cross_release(self):
        ex,a,v,_=fixture(("MBB",))
        ex.submit([Connect(("C0","D2"),("D0","D2"),30,1,1,1)])
        a=replace(a,decision_root_sha256=terminal_state_hash(ex))
        self.assertEqual(v.evaluate(ex,a).reason,"RESERVATION_CONFLICT")
        ex,a,v,_=fixture()
        cross=replace(a.members[0],new_terminal_pair=(("A1","D1"),("C0","D1")))
        self.assertEqual(v.evaluate(ex,replace(a,members=(cross,))).reason,
                         "CROSS_ACTION_RELEASE_OR_OTHER_OLD_BINDING")

    def test_parallel_satellite_pair_rejected_even_different_terminals(self):
        ex,a,v,_=fixture(("BBM","BBM"))
        ex.submit([Connect(("A0","D2"),("C0","D2"),30,0,0,0)])
        a=replace(a,decision_root_sha256=terminal_state_hash(ex))
        self.assertEqual(v.evaluate(ex,a).reason,"ILLEGAL_PARALLEL_ACTIVE_PAIR")

    def test_two_singletons_legal_joint_disconnect_rejected(self):
        ex=TerminalExecutor(("A","B","C","D"))
        old1=(("A","D1"),("C","D1"));old2=(("B","D1"),("D","D1"))
        ex.submit([Connect(*p,30,0,0,0) for p in (old1,old2)])
        # Two cross-cut links. Each individual removal retains the other bridge.
        ms=(BatchReplaceMember("a",0,old1,(("A","D1"),("D","D2")),1,1,1),
            BatchReplaceMember("b",1,old2,(("B","D1"),("C","D2")),1,1,1))
        ws=[TerminalPairWindow(*m.new_terminal_pair[0],*m.new_terminal_pair[1],0,30) for m in ms]
        pv=BatchPhysicalValidator(TerminalPairPhysicalFeasibility(TerminalPairCatalog(ws,{})),
            max_batch_replace=4,observation_end_s=30,absolute_time_frame_id=FRAME)
        v=BatchSafetyValidator(pv,(("A","B"),("C","D")),OperationalPolicy("STRICT_CONNECTED"))
        a=JointAction(0,FRAME,terminal_state_hash(ex),POOL,ms)
        self.assertTrue(v.evaluate(ex,replace(a,members=(ms[0],))).accepted)
        self.assertTrue(v.evaluate(ex,replace(a,members=(ms[1],))).accepted)
        before=terminal_state_hash(ex)
        p=v.evaluate(ex,a)
        self.assertFalse(p.accepted)
        self.assertEqual(p.reason,"STRICT_CONNECTIVITY_VIOLATION")
        self.assertEqual(p.profile["outage_duration"],2.0)
        self.assertEqual(terminal_state_hash(ex),before)

    def test_late_member_failure_full_rollback(self):
        ex,a,v,_=fixture()
        invalid=replace(a.members[1],retarget_a_s=30)
        before=deepcopy(ex.__dict__)
        p=v.evaluate(ex,replace(a,members=(a.members[0],invalid)))
        self.assertFalse(p.accepted)
        self.assertEqual(ex.__dict__,before)
        with self.assertRaises(ValueError): AtomicBatchExecutor(v).commit(ex,p)
        self.assertEqual(ex.__dict__,before)

    def test_mbb_profile_includes_late_old_tx_draining(self):
        ex,a,v,_=fixture(("MBB",))
        ex.start_tx(a.members[0].old_binding[0],4.5)
        a=replace(a,decision_root_sha256=terminal_state_hash(ex))
        p=v.evaluate(ex,a)
        self.assertTrue(p.accepted,p.reason)
        self.assertEqual(p.member_results[0]["ready_time_s"],2)
        self.assertEqual(p.safety_completion_s,4.5)
        self.assertIsNone(p.profile["final_executor"]._link(a.members[0].old_binding))
        self.assertTrue(any(x["time_s"]==4.5 and "LINK_DOWN" in x["events"] for x in p.profile["timeline"]))

    def test_profile_sees_unrelated_expiry_before_old_release(self):
        ex,a,v,_=fixture(("MBB",))
        # Fixed A0-B0-C0-D0 chain replaced by an unrelated expiring bridge.
        ex.submit([Connect(("B0","D2"),("D0","D1"),3,0,0,0)])
        ex.start_tx(a.members[0].old_binding[0],4.5)
        v=BatchSafetyValidator(v.physical_validator,(("A0","B0"),("B0","C0")),OperationalPolicy("STRICT_CONNECTED"))
        a=replace(a,decision_root_sha256=terminal_state_hash(ex))
        p=v.evaluate(ex,a)
        self.assertFalse(p.accepted)
        self.assertEqual(p.profile["first_partition_time"],3)

    def test_draining_rejects_tx_ready_waits_both_endpoints(self):
        ex,a,v,_=fixture(("BBM",))
        ex.start_tx(a.members[0].old_binding[0],1.3)
        a=replace(a,decision_root_sha256=terminal_state_hash(ex))
        p=v.evaluate(ex,a)
        self.assertEqual(p.member_results[0]["ready_time_s"],3.3)
        AtomicBatchExecutor(v).commit(ex,p)
        with self.assertRaises(ValueError): ex.start_tx(a.members[0].old_binding[0],2)
        self.assertEqual(ex.terminals[("A0","D1")].phase,"DRAINING")
        ex.advance(1.3)
        self.assertEqual(ex.terminals[("A0","D1")].phase,"RETARGETING")
        ex.advance(2.3)
        self.assertEqual(ex.terminals[("A0","D1")].phase,"ACQUIRING")
        ex.advance(3.3)
        self.assertIsNotNone(ex._link(a.members[0].new_terminal_pair))

    def test_equal_timestamp_tx_down_and_setup_order(self):
        ex,a,v,_=fixture(("BBM",),retarget=0,acquisition=0)
        ex.start_tx(a.members[0].old_binding[0],1.3)
        a=replace(a,decision_root_sha256=terminal_state_hash(ex))
        p=v.evaluate(ex,a);AtomicBatchExecutor(v).commit(ex,p)
        ex.advance(1.3)
        names=[x["event"] for x in ex.log if x["time"]==1.3]
        self.assertLess(names.index("TX_DONE"),names.index("LINK_DOWN"))
        self.assertLess(names.index("LINK_DOWN"),names.index("LINK_UP"))

    def test_future_visibility_abort_independent_member_survives_stale_ready(self):
        ex,a,v,_=fixture(("BBM","BBM"))
        p=v.evaluate(ex,a);AtomicBatchExecutor(v).commit(ex,p)
        ex.advance(.5);ex.expire_visibility(*a.members[0].new_terminal_pair)
        ex.advance(2)
        self.assertIsNone(ex._link(a.members[0].new_terminal_pair))
        self.assertIsNotNone(ex._link(a.members[1].new_terminal_pair))
        self.assertTrue(any(x["event"]=="STALE_EVENT" for x in ex.log))
        ex.advance(30)
        self.assertEqual(ex.links,{})

    def test_ready_equal_end_and_right_censored_observation(self):
        ex,a,v,_=fixture(("BBM",),ends=2)
        self.assertEqual(v.evaluate(ex,a).reason,"INSUFFICIENT_LIFETIME")
        ex,a,v,_=fixture(("BBM",),ends=30)
        vals=v.physical_validator.physical_layer.catalog.windows
        key=next(iter(vals));vals[key]=[replace(vals[key][0],right_censored=True)]
        p=v.evaluate(ex,a)
        self.assertTrue(p.accepted)
        self.assertTrue(p.member_results[0]["window"]["right_censored"])
        self.assertEqual(p.member_results[0]["end_semantics"],"prediction_horizon")
        limited=BatchPhysicalValidator(v.physical_validator.physical_layer,max_batch_replace=4,
            observation_end_s=1,absolute_time_frame_id=FRAME)
        self.assertEqual(limited.evaluate(ex,a).reason,"WINDOW_OUTSIDE_OBSERVATION_COVERAGE")

    def test_hash_stale_and_time_frame_validation(self):
        ex,a,v,_=fixture()
        p=v.evaluate(ex,a);ex.advance(.1)
        with self.assertRaisesRegex(ValueError,"STALE_VALIDATION_ROOT"):AtomicBatchExecutor(v).commit(ex,p)
        self.assertEqual(v.evaluate(ex,a).reason,"DECISION_ROOT_MISMATCH")
        ex,a,v,_=fixture()
        self.assertEqual(v.evaluate(ex,replace(a,absolute_time_frame_id="WRONG")).reason,"ABSOLUTE_TIME_FRAME_MISMATCH")
        self.assertEqual(v.evaluate(ex,replace(a,decision_time_s=1)).reason,"DECISION_TIME_MISMATCH")

    def test_same_peer_new_terminals_new_bbm_not_keep(self):
        ex,a,v,_=fixture(("BBM",))
        new=(("A0","D2"),("B0","D2"))
        m=replace(a.members[0],new_terminal_pair=new)
        v.physical_validator.physical_layer.catalog.windows[new]=[TerminalPairWindow(*new[0],*new[1],0,30)]
        a=replace(a,members=(m,))
        p=v.evaluate(ex,a)
        self.assertTrue(p.accepted,p.reason)
        self.assertEqual(p.member_results[0]["transition_mode"],"BBM")
        AtomicBatchExecutor(v).commit(ex,p);ex.advance(2)
        self.assertIsNotNone(ex._link(new))

    def test_hold_no_mutation_no_setup(self):
        ex,a,v,_=fixture()
        a=replace(a,members=())
        old=deepcopy(ex.__dict__)
        p=v.evaluate(ex,a);AtomicBatchExecutor(v).commit(ex,p)
        self.assertEqual(ex.__dict__,old)

    def test_action_identity_canonical_and_setup_sensitive(self):
        ex,a,_,_=fixture()
        self.assertEqual(a.batch_id,deepcopy(a).batch_id)
        self.assertNotEqual(a.batch_id,replace(a,members=(replace(a.members[0],retarget_a_s=2),a.members[1])).batch_id)
        with self.assertRaises(ValueError):replace(a,members=a.members[::-1])

    def test_batch_network_work_capacity_and_one_graph_refresh(self):
        ex,a,v,fixed=fixture(("BBM","MBB","BBM","MBB"))
        e=network(ex,fixed);e.advance_to(1)
        a=replace(a,decision_time_s=1,decision_root_sha256=e.decision_root_sha256())
        e.schedule_action(ScriptedBatchProposal(1,a.batch_id,a,v,True));e.settle_current_time()
        self.assertEqual(e.batch_count,1);self.assertEqual(e.switch_count,4)
        self.assertEqual(e.BBM_count,2);self.assertEqual(e.MBB_count,2)
        commits=[x for x in e.executor.log if x["time"]==1 and x["event"]=="BATCH_COMMIT"]
        self.assertEqual(len(commits),1);self.assertEqual(commits[0]["details"]["command_count"],4)
        self.assertEqual(len([x for x in e.graph_event_sequence if x["time_s"]==1]),1)
        e.advance_to(10)
        self.assertLessEqual(e.max_abs_conservation,e.abs_tol+e.rel_tol*max(1,sum(e.arrived.values())))
        self.assertEqual(e.max_capacity_violation,0)
        self.assertTrue(all(q>=0 for q in e.queues.bits.values()))
        self.assertLess(e.queues.total()+e.in_flight.total(),.01)

    def test_rejected_network_batch_no_terminal_or_queue_mutation(self):
        ex,a,v,fixed=fixture()
        e=network(ex,fixed);e.settle_current_time()
        a=replace(a,decision_root_sha256=e.decision_root_sha256(),
                  members=(a.members[0],replace(a.members[1],retarget_a_s=40)))
        terminal=terminal_state_hash(e.executor);q=e.queues.snapshot();i=e.in_flight.snapshot()
        e.schedule_action(ScriptedBatchProposal(0,a.batch_id,a,v,False));e.settle_current_time()
        self.assertEqual(terminal_state_hash(e.executor),terminal)
        self.assertEqual(e.queues.snapshot(),q);self.assertEqual(e.in_flight.snapshot(),i)
        self.assertEqual(e.batch_count,0)

    def test_singleton_matches_old_d2_physical_service_events(self):
        old=fixture_d_draining_split()
        old.advance_to(1)
        fresh=fixture_d_draining_split();fresh.actions=();fresh.action_index=0
        ex=deepcopy(fresh.executor)
        e=BatchNetworkServiceEngine(fresh.nodes,fresh.fixed_edges,fresh.capacity_bit_s,
            fresh.commodities,fresh.trace,fresh.delay,ex,absolute_time_frame_id=FRAME,
            conservation_abs_tolerance_bits=fresh.abs_tol,
            conservation_relative_tolerance=fresh.rel_tol,state_tolerance_bits=fresh.state_tol)
        e.advance_to(1)
        m=BatchReplaceMember("legacy",0,(("B","D1"),("C","D1")),(("B","D1"),("D","D1")),.5,.5,.5)
        a=JointAction(1,FRAME,e.decision_root_sha256(),POOL,(m,))
        legacy=old.actions[0]
        pv=BatchPhysicalValidator(legacy.physical_layer,max_batch_replace=1,observation_end_s=30,absolute_time_frame_id=FRAME)
        v=BatchSafetyValidator(pv,e.fixed_edges,legacy.policy)
        e.schedule_action(ScriptedBatchProposal(1,a.batch_id,a,v,True));e.settle_current_time()
        old.advance_to(10);e.advance_to(10)
        for field in ("queues","in_flight","arrived","delivered","objective_by_commodity",
                      "transmitted","service_rates","routes","propagation_agenda","terminal_event_sequence"):
            left=getattr(old,field);right=getattr(e,field)
            if field in ("queues","in_flight"):left=left.snapshot();right=right.snapshot()
            self.assertEqual(left,right,field)
        self.assertEqual(old.executor.snapshot(),e.executor.snapshot())

    def test_deterministic_clone_isolation_and_replay(self):
        ex,a,v,fixed=fixture()
        e=network(ex,fixed);e.advance_to(1)
        a=replace(a,decision_time_s=1,decision_root_sha256=e.decision_root_sha256())
        clones=[e.clone(),e.clone()]
        before=e.canonical_state_sha256()
        for c in clones:
            c.schedule_action(ScriptedBatchProposal(1,a.batch_id,a,v,True));c.advance_to(8)
        self.assertEqual(clones[0].canonical_state_sha256(),clones[1].canonical_state_sha256())
        self.assertEqual(e.canonical_state_sha256(),before)
        self.assertNotEqual(clones[0].canonical_state_sha256(),before)

    def test_five_second_cadence_does_not_delay_non_epoch_physics(self):
        ex,a,v,fixed=fixture(("BBM",),ends=7.25,retarget=.8,acquisition=.5)
        e=network(ex,fixed,horizon=9)
        schedule=DecisionSchedule(5,9,10,10,.01,True)
        adapter=BatchCadenceAdapter(e,schedule,v)
        def callback(live,root,h):
            return JointAction(live.now,FRAME,root,POOL,a.members if live.now==0 else ())
        r=adapter.run(callback)
        self.assertEqual([x["time_s"] for x in r["checkpoints"]],[0,5])
        events=e.terminal_event_sequence
        self.assertTrue(any(x["event"]=="LINK_UP" and x["time"]==1.3 for x in events))
        self.assertTrue(any(x["event"]=="LINK_DOWN" and x["time"]==7.25 for x in events))
        self.assertTrue(all(x["H_decision_root"]==x["H_post_observe"] for x in r["checkpoints"]))

    def test_schedule_end_drain_and_horizon_contract_parameterized(self):
        schedule=DecisionSchedule(5,240,600,10,.01,True)
        epochs=list(schedule.epochs())
        self.assertEqual(len(epochs),120);self.assertEqual(epochs[-1],595)
        self.assertEqual(schedule.horizon_at(595),5)
        self.assertEqual(len(list(replace(schedule,cadence_s=2).epochs())),300)
        with self.assertRaises(ValueError):schedule.horizon_at(600)
        with self.assertRaises(ValueError):replace(schedule,clip_horizon_at_end=False).horizon_at(595)


if __name__ == "__main__":
    unittest.main(verbosity=2)
