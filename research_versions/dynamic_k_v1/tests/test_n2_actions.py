"""N2 atomic actions: analytic mechanism tests, no controller performance runs."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import unittest

V=Path(__file__).resolve().parents[1];P=V.parents[1]
sys.path.insert(0,str(V));sys.path.insert(0,str(P/'src'))
from runtime.n2_actions import Hold,Add,Drop,Replace,LinkRef,Setup,ActionValidator
from runtime.n2_candidates import CandidateSource
from runtime.n2_physical import N2PhysicalLayer,SyntheticWindowGuard,Sgp4PhysicalGuard,ReplayableSgp4Model
from runtime.n2_controller import AtomicTopologyController,validate_n2
from runtime.n1b_evaluator import DeliveredFluidEvaluator
from runtime.n1b_observer import ObservedD2Engine
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog,TerminalPairWindow
from dynamic_lisl.gate_c_terminal_geometry import TerminalGeometryConfig
from dynamic_lisl.commodity import Commodity
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace,TrafficSegment

NODES=tuple('S%03d'%i for i in range(160));A,B,C,D=NODES[:4]
A1,B1,C1,D1=((n,'D1') for n in (A,B,C,D));A2,B2,C2=((n,'D2') for n in (A,B,C))
SETUP=Setup(.5,.5,.5)
N1A_BINDING=N1B_BINDING=N2_BINDING=None
EXAMPLES={}

def window(a,b,end=100.):
    a,b=sorted((a,b))
    return TerminalPairWindow(a[0],a[1],b[0],b[1],0.,end,parent_start_s=0.,parent_end_s=end)

def physical(pairs=((A1,B1),),*,end=100.,rejections=None):
    cat=TerminalPairCatalog([window(a,b,end) for a,b in pairs],{n:i for i,n in enumerate(NODES)})
    return N2PhysicalLayer(TerminalPairPhysicalFeasibility(cat),SyntheticWindowGuard(rejections))

def activate(ex,a=A1,b=B1,end=100.):ex.submit([Connect(a,b,end,0.,0.,0.)])

def make(*,connected=False,pairs=((A1,B1),),end=100.,rate=10.,destination=B,T=4.,initial_expiry=None):
    ex=TerminalExecutor(NODES)
    if connected:activate(ex,end=end if initial_expiry is None else initial_expiry)
    trace=PiecewiseConstantTrafficTrace(('f',),[TrafficSegment(0.,1.,{'f':rate})])
    e=ObservedD2Engine(NODES,(),20.,[Commodity('f',A,destination)],trace,lambda edge,t:1.,ex)
    ev=DeliveredFluidEvaluator(e,T_s=T,time_tolerance_s=1e-9,energy_tolerance_J=1e-6,
        business_tolerance_bits=1e-6,n1a_binding=N1A_BINDING,n1b_binding=N1B_BINDING)
    return AtomicTopologyController(ev,physical(pairs,end=end),binding=N2_BINDING)

def oldref(ex,ends=(A1,B1)):
    return LinkRef.from_link(next(l for l in ex.links.values() if l.endpoints==tuple(sorted(ends))))


class ActionValidationTests(unittest.TestCase):
    def test_K0_independent_ADD_and_HOLD_candidates(self):
        ex=TerminalExecutor(NODES)
        source=CandidateSource(ActionValidator(physical()))
        result=source.generate(ex,SETUP)
        self.assertEqual([a.kind for a in result['candidates']],['HOLD','ADD'])
        self.assertEqual(result['diagnostics']['ADD']['legal'],1)
        self.assertEqual(result['diagnostics']['DROP']['status'],'NO_LEGAL_PHYSICAL_ACTION')

    def test_budget_truncation_distinct_and_DROP_not_lost(self):
        ex=TerminalExecutor(NODES);activate(ex)
        source=CandidateSource(ActionValidator(physical(((A1,C1),(A2,C2)))))
        r=source.generate(ex,SETUP,retention_budgets={'ADD':0,'REPLACE':0})
        self.assertEqual([a.kind for a in r['candidates']],['HOLD','DROP'])
        self.assertEqual(r['diagnostics']['ADD']['status'],'LEGAL_BUT_BUDGET_TRUNCATED')
        self.assertGreater(r['diagnostics']['REPLACE']['truncated'],0)

    def test_deterministic_candidate_sort_independent_catalog_order(self):
        ex=TerminalExecutor(NODES);activate(ex)
        pairs=((A1,C1),(A2,C2),(B2,C2))
        x=CandidateSource(ActionValidator(physical(pairs))).generate(ex,SETUP)
        y=CandidateSource(ActionValidator(physical(pairs[::-1]))).generate(ex,SETUP)
        self.assertEqual(x,y)

    def test_illegal_ADD_no_implicit_release_or_live_mutation(self):
        ex=TerminalExecutor(NODES);activate(ex)
        before=deepcopy(ex.snapshot());log=deepcopy(ex.log)
        for a,b in ((A1,C1),(A2,B2)):
            v=ActionValidator(physical(((a,b),))).validate(ex,Add(a,b,SETUP))
            self.assertFalse(v['accepted']);self.assertEqual(v['reason'],'ADD_WOULD_IMPLICITLY_RELEASE')
        self.assertEqual(before,ex.snapshot());self.assertEqual(log,ex.log)

    def test_reservations_and_parallel_satellite_pair_conflicts(self):
        ex=TerminalExecutor(NODES);activate(ex)
        ex.submit([Connect(A2,C2,100.,1.,1.,1.)])
        v=ActionValidator(physical(((A2,B2),))).validate(ex,Add(A2,B2,SETUP))
        self.assertEqual(v['reason'],'RESERVATION_CONFLICT')
        v=ActionValidator(physical(((A1,C1),))).validate(ex,Replace((oldref(ex),),A1,C1,SETUP,'BBM'))
        self.assertEqual(v['reason'],'RESERVATION_CONFLICT')

    def test_REPLACE_rejects_undeclared_third_party(self):
        ex=TerminalExecutor(NODES);activate(ex);activate(ex,C1,D1)
        before=ex.snapshot()
        v=ActionValidator(physical(((A1,C1),))).validate(ex,Replace((oldref(ex),),A1,C1,SETUP,'BBM'))
        self.assertEqual(v['reason'],'UNDECLARED_THIRD_PARTY_RELEASE');self.assertEqual(before,ex.snapshot())
        refs=tuple(LinkRef.from_link(l) for _,l in sorted(ex.links.items()))
        v=ActionValidator(physical(((A1,C1),))).validate(ex,Replace(refs,A1,C1,SETUP,'BBM'))
        self.assertTrue(v['accepted']);self.assertEqual(v['actual_immediate_release_ids'],['L1','L2'])

    def test_MBB_requires_real_free_resources(self):
        ex=TerminalExecutor(NODES);activate(ex)
        v=ActionValidator(physical(((A1,C1),))).validate(ex,Replace((oldref(ex),),A1,C1,SETUP,'MBB'))
        self.assertEqual(v['reason'],'MBB_REQUIRES_FREE_TERMINALS')

    def test_window_too_short_and_visibility_failure(self):
        ex=TerminalExecutor(NODES)
        v=ActionValidator(physical(end=.5)).validate(ex,Add(A1,B1,SETUP))
        self.assertEqual(v['reason'],'INSUFFICIENT_LIFETIME')
        ex.advance(1.)
        v=ActionValidator(physical(end=.5)).validate(ex,Add(A1,B1,SETUP))
        self.assertFalse(v['accepted'])

    def test_LOS_local_remote_bilateral_reasons(self):
        ex=TerminalExecutor(NODES)
        for reason in ('LOS_BLOCKED','FOR_FAIL_LOCAL','FOR_FAIL_REMOTE','FOR_FAIL_BILATERAL'):
            v=ActionValidator(physical(rejections={tuple(sorted((A1,B1))):reason})).validate(ex,Add(A1,B1,SETUP))
            self.assertEqual(v['reason'],reason)

    def test_unknown_wrong_stale_reference_and_invalid_setup(self):
        ex=TerminalExecutor(NODES);activate(ex)
        validator=ActionValidator(physical())
        self.assertEqual(validator.validate(ex,object())['reason'],'UNKNOWN_ACTION')
        self.assertEqual(validator.validate(ex,Hold('ADD'))['reason'],'ACTION_KIND_MISMATCH')
        self.assertEqual(validator.validate(ex,Drop(LinkRef('L999',(A1,B1))))['reason'],'STALE_OR_WRONG_LINK_REFERENCE')
        self.assertEqual(validator.validate(ex,Add(A2,C2,Setup(float('nan'),1.,1.)))['reason'],'INVALID_SETUP')


class ActionExecutionTests(unittest.TestCase):
    def test_ADD_setup_K_and_energy_exact(self):
        c=make();receipt=c.submit(Add(A1,B1,SETUP))
        self.assertTrue(receipt['accepted']);self.assertEqual(c.last_result['K_admit'],0)
        r=c.advance_to(.5);self.assertEqual(r['K_admit'],0)
        self.assertEqual({s['phase'] for s in r['dynamic_terminal_states'] if tuple(s['terminal_id']) in (A1,B1)},{'ACQUIRING'})
        self.assertEqual(c.advance_to(1.)['K_admit'],1)
        r=c.run();core=r['n1b_result']['n1a_result']
        self.assertEqual(core['E_LCT_J'],6710.)
        self.assertEqual(r['n1b_result']['delivered_bit_age_integral_bit_s'],17.5)
        self.assertEqual(r['n1b_result']['mean_delivered_fluid_delay_s'],1.75)
        self.assertEqual(core['N_T_bits'],0.);self.assertTrue(core['evaluation_completed_normally'])
        EXAMPLES['K0_ADD_setup_FIFO_energy']=r

    def test_DROP_draining_partial_delivery_age_exact(self):
        c=make(connected=True);c.advance_to(.5)
        c.engine.executor.start_tx(A1,1.5)
        ref=oldref(c.engine.executor)
        self.assertTrue(c.submit(Drop(ref))['accepted'])
        self.assertEqual((c.last_result['K_admit'],c.last_result['K_draining']),(0,1))
        self.assertEqual(c.submit(Add(A1,B1,SETUP))['accepted'],False)
        r=c.run();core=r['n1b_result']['n1a_result']
        self.assertEqual((r['K_admit'],r['K_draining']),(0,0))
        self.assertEqual(core['E_LCT_J'],6520.)
        self.assertEqual(core['J_T_bit_s'],21.25)
        self.assertEqual((core['delivered_bits'],core['N_T_bits']),(5.,5.))
        self.assertEqual(r['n1b_result']['delivered_bit_age_integral_bit_s'],5.)
        self.assertEqual(r['n1b_result']['mean_delivered_fluid_delay_s'],1.)
        self.assertEqual(r['release_audit'][0]['status'],'COMPLETE')
        EXAMPLES['DROP_draining_partial_FIFO']=r

    def test_partition_backlog_reADD_resources_FIFO_restore(self):
        c=make(connected=True);c.advance_to(.5);c.engine.executor.start_tx(A1,1.5)
        c.submit(Drop(oldref(c.engine.executor)))
        c.advance_to(1.5)
        self.assertEqual(c.engine.executor.terminals[A1].phase,'IDLE')
        self.assertTrue(c.submit(Add(A1,B1,SETUP))['accepted'])
        r=c.run();age=r['n1b_result'];core=age['n1a_result']
        self.assertEqual(core['delivered_bits'],10.);self.assertEqual(core['N_T_bits'],0.)
        self.assertEqual(age['delivered_bit_age_integral_bit_s'],19.375)
        self.assertEqual(core['J_T_bit_s'],19.375)
        self.assertEqual(core['E_LCT_J'],6710.)
        EXAMPLES['partition_backlog_reADD_FIFO']=r

    def test_BBM_waits_registered_TX_and_actual_release_set(self):
        c=make(connected=True,pairs=((A1,C1),),destination=C)
        c.engine.executor.start_tx(A1,1.)
        ref=oldref(c.engine.executor)
        receipt=c.submit(Replace((ref,),A1,C1,Setup(1.,1.,1.),'BBM'))
        self.assertTrue(receipt['accepted']);self.assertEqual(receipt['actual_immediate_release_ids'],[ref.link_id])
        self.assertEqual(c.last_result['K_draining'],1);self.assertEqual(c.last_result['K_admit'],0)
        self.assertEqual(c.advance_to(2.)['K_admit'],0)
        self.assertEqual(c.advance_to(3.)['K_admit'],1)
        r=c.run();self.assertEqual(r['release_audit'][0]['status'],'COMPLETE')
        EXAMPLES['real_BBM_registered_TX']=r

    def test_MBB_spare_terminal_then_old_draining(self):
        c=make(connected=True,pairs=((A2,C2),),destination=C)
        c.engine.executor.start_tx(A1,3.)
        ref=oldref(c.engine.executor)
        receipt=c.submit(Replace((ref,),A2,C2,Setup(1.,1.,1.),'MBB'))
        self.assertTrue(receipt['accepted']);self.assertEqual(receipt['actual_immediate_release_ids'],[])
        self.assertEqual(c.last_result['K_admit'],1)
        r=c.advance_to(2.);self.assertEqual((r['K_admit'],r['K_draining']),(1,1))
        self.assertEqual(r['release_audit'][0]['draining_times_s'],[2.])
        r=c.advance_to(3.);self.assertEqual(r['release_audit'][0]['status'],'COMPLETE')
        EXAMPLES['real_MBB_spare_resources']=c.run()

    def test_MBB_natural_expiry_is_not_claimed_uninterrupted(self):
        c=make(connected=True,pairs=((A2,C2),),initial_expiry=.5,rate=0.)
        receipt=c.submit(Replace((oldref(c.engine.executor),),A2,C2,SETUP,'MBB'))
        self.assertTrue(receipt['accepted'])
        r=c.advance_to(.75);self.assertEqual(r['K_admit'],0)
        r=c.run();self.assertEqual(r['release_audit'][0]['status'],'NATURAL_END_BEFORE_REQUESTED_RELEASE')

    def test_MBB_abort_and_locked_DROP_preserve_old_connection(self):
        c=make(connected=True,pairs=((A2,C2),),rate=0.)
        ref=oldref(c.engine.executor)
        self.assertTrue(c.submit(Replace((ref,),A2,C2,SETUP,'MBB'))['accepted'])
        self.assertEqual(c.submit(Drop(ref))['reason'],'RELEASE_OWNERSHIP_CONFLICT')
        c.engine.executor.expire_visibility(A2,C2)
        r=c.run()
        self.assertEqual(r['K_admit'],1)
        self.assertEqual(r['release_audit'][0]['status'],'SETUP_ABORTED_NO_RELEASE')

    def test_zero_duration_MBB_is_real_instant_execution(self):
        c=make(connected=True,pairs=((A2,C2),),rate=0.)
        ref=oldref(c.engine.executor)
        receipt=c.submit(Replace((ref,),A2,C2,Setup(0.,0.,0.),'MBB'))
        self.assertTrue(receipt['accepted']);self.assertEqual(receipt['actual_immediate_release_ids'],[ref.link_id])
        self.assertEqual(c.last_result['K_admit'],1)

    def test_HOLD_natural_expiry_and_no_active_command(self):
        c=make(connected=True,end=3.,rate=0.)
        before=deepcopy(c.engine.executor.log)
        c.submit(Hold());self.assertEqual(before,c.engine.executor.log)
        r=c.run();self.assertEqual(r['K_admit'],0)
        self.assertEqual(r['n1b_result']['n1a_result']['E_LCT_J'],6640.)

    def test_clone_checkpoint_restore_replay_identical(self):
        c=make(connected=True);c.advance_to(.5);c.engine.executor.start_tx(A1,1.5)
        c.submit(Drop(oldref(c.engine.executor)))
        clone=c.clone();restore=AtomicTopologyController.restore(c.checkpoint())
        outcomes=[]
        for obj in (c,clone,restore):
            obj.advance_to(1.5);obj.submit(Add(A1,B1,SETUP));outcomes.append(obj.run())
        self.assertEqual(outcomes[0],outcomes[1]);self.assertEqual(outcomes[0],outcomes[2])

    def test_original_N1a_N1b_exactly_equal_for_same_real_commands(self):
        c=make();old=c.evaluator.clone()
        plan=c.validator.validate(old.base.engine.executor,Add(A1,B1,SETUP))
        old.base.engine.executor.submit(plan['commands']);old.advance_to(0.)
        c.submit(Add(A1,B1,SETUP))
        self.assertEqual(c.run()['n1b_result'],old.run())

    def test_rejection_no_live_change_and_joint_interface_unfrozen(self):
        c=make(connected=True,pairs=((A1,C1),))
        before=deepcopy(c.engine.canonical_state())
        self.assertFalse(c.submit(Add(A1,C1,SETUP))['accepted'])
        self.assertEqual(before,c.engine.canonical_state())
        result=c.submit_batch((Hold(),Hold()))
        self.assertFalse(result['accepted']);self.assertIsNone(result['maximum_concurrent_actions'])

    def test_N2_cross_field_and_physical_input_mutation_rejected(self):
        c=make();r=c.advance_to(0.)
        for field,value in (('K_admit',1),('setup_terminal_count',1),('K_draining',-1)):
            bad=deepcopy(r);bad[field]=value
            with self.assertRaises(ValueError):validate_n2(bad)
        c.validator.physical.guard.rejections[tuple(sorted((A1,B1)))]='LOS_BLOCKED'
        with self.assertRaisesRegex(ValueError,'PHYSICAL_INPUT_CHANGED'):c.submit(Hold())


class PhysicalGeometryTests(unittest.TestCase):
    def test_live_sphere_LOS_rejects_even_with_claimed_window(self):
        import numpy as np
        class RecordedCartesian:
            def state(self,t,ids):
                return np.array([[[7000.,0.,0.],[-7000.,0.,0.]]]),np.array([[[0.,7.,0.],[0.,-7.,0.]]])
        cfg=TerminalGeometryConfig.from_dict(json.loads((P/'configs/hardware_gate_c_simplified_v1.json').read_text()))
        layer=physical();layer.guard=Sgp4PhysicalGuard(RecordedCartesian(),cfg,earth_radius_km=6378.137)
        verdict=ActionValidator(layer).validate(TerminalExecutor(NODES),Add(A1,B1,SETUP))
        self.assertEqual(verdict['reason'],'LOS_BLOCKED')

    def test_live_bilateral_FOR_local_remote_and_both(self):
        import numpy as np
        class RecordedCartesian:
            def state(self,t,ids):
                return np.array([[[7000.,0.,0.],[7000.,0.,1000.]]]),np.array([[[0.,7.,0.],[0.,7.,0.]]])
        cfg=TerminalGeometryConfig.from_dict(json.loads((P/'configs/hardware_gate_c_simplified_v1.json').read_text()))
        guard=Sgp4PhysicalGuard(RecordedCartesian(),cfg,earth_radius_km=6378.137)
        self.assertTrue(guard.evaluate(A1,B2,0.)['accepted'])
        self.assertEqual(guard.evaluate(A2,B2,0.)['reason'],'FOR_FAIL_LOCAL')
        self.assertEqual(guard.evaluate(A1,B1,0.)['reason'],'FOR_FAIL_REMOTE')
        self.assertEqual(guard.evaluate(A2,B1,0.)['reason'],'FOR_FAIL_BILATERAL')

    def test_ready_geometry_is_rechecked(self):
        import numpy as np
        class RecordedCartesian:
            def state(self,t,ids):
                z=1000. if t[0]<.5 else -1000.
                return np.array([[[7000.,0.,0.],[7000.,0.,z]]]),np.array([[[0.,7.,0.],[0.,7.,0.]]])
        cfg=TerminalGeometryConfig.from_dict(json.loads((P/'configs/hardware_gate_c_simplified_v1.json').read_text()))
        layer=physical(((A1,B2),));layer.guard=Sgp4PhysicalGuard(RecordedCartesian(),cfg,earth_radius_km=6378.137)
        verdict=ActionValidator(layer).validate(TerminalExecutor(NODES),Add(A1,B2,SETUP))
        self.assertEqual(verdict['reason'],'READY_FOR_FAIL_BILATERAL')


class Real160GeometryIntegrationTests(unittest.TestCase):
    def test_controlled_short_feedback_loop_and_clone_real_SGP4(self):
        from dynamic_lisl.gate_d_scenarios import Sgp4EdgeDelayProvider
        reference=json.loads((P/'outputs/gate_c_simplified_20260922T064019_313843Z/z_ref.json').read_text())
        fixed=tuple(tuple(edge) for edge in reference['fixed_edges'])
        nodes=tuple(sorted({n for edge in fixed for n in edge}))
        self.assertEqual(len(nodes),160)
        records=[]
        path=P/'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl'
        with path.open(encoding='utf-8') as f:
            for line in f:
                row=json.loads(line)
                if row['sat_a'] in nodes and row['sat_b'] in nodes and row['start_s']==0 and row['end_s']>=8:
                    records.append(row)
        model=ReplayableSgp4Model.load(P/'data/raw/sgp4_x720')
        cfg=TerminalGeometryConfig.from_dict(json.loads((P/'configs/hardware_gate_c_simplified_v1.json').read_text()))
        guard=Sgp4PhysicalGuard(model,cfg,earth_radius_km=6378.137)
        chosen=None
        for row in sorted(records,key=lambda x:(x['sat_a'],x['terminal_a'],x['sat_b'],x['terminal_b'])):
            a=(row['sat_a'],row['terminal_a']);b=(row['sat_b'],row['terminal_b'])
            if guard.evaluate(a,b,0.)['accepted'] and guard.evaluate(a,b,.4)['accepted']:
                chosen=row;break
        self.assertIsNotNone(chosen,'No real LOS/FoR window in the controlled asset')
        cat=TerminalPairCatalog.from_records([chosen],{n:int(n.split('_')[0][1:]) for n in nodes})
        layer=N2PhysicalLayer(TerminalPairPhysicalFeasibility(cat),guard)
        a,b=cat.terminal_pair_candidates(0.)[0].endpoint_a,cat.terminal_pair_candidates(0.)[0].endpoint_b
        trace=PiecewiseConstantTrafficTrace(('real160',),[TrafficSegment(0.,1.,{'real160':1.})])
        e=ObservedD2Engine(nodes,fixed,10.,[Commodity('real160',a[0],b[0])],trace,
            Sgp4EdgeDelayProvider(model,nodes),TerminalExecutor(nodes))
        ev=DeliveredFluidEvaluator(e,T_s=4.,time_tolerance_s=1e-9,energy_tolerance_J=1e-6,
            business_tolerance_bits=1e-6,n1a_binding=N1A_BINDING,n1b_binding=N1B_BINDING)
        c=AtomicTopologyController(ev,layer,binding=N2_BINDING)
        profile=Setup(.2,.2,.2)
        initial=c.candidates(profile)
        action=next(x for x in initial['candidates'] if x.kind=='ADD')
        self.assertTrue(c.submit(action)['accepted'])
        self.assertEqual(c.advance_to(.1)['K_admit'],0)
        clone=c.clone()
        results=[]
        for obj in (c,clone):
            obj.submit(Hold())
            self.assertEqual(obj.advance_to(.4)['K_admit'],1)
            delivered=obj.advance_to(1.25)
            self.assertAlmostEqual(delivered['n1b_result']['delivered_bits'],1.)
            ref=LinkRef.from_link(next(iter(obj.engine.executor.links.values())))
            self.assertTrue(obj.submit(Drop(ref))['accepted'])
            self.assertEqual(obj.last_result['K_admit'],0)
            obj.advance_to(2.)
            add=next(x for x in obj.candidates(profile)['candidates'] if x.kind=='ADD')
            self.assertTrue(obj.submit(add)['accepted'])
            final=obj.run();results.append(final)
        self.assertEqual(results[0],results[1])
        self.assertEqual(results[0]['K_admit'],1)
        self.assertAlmostEqual(results[0]['n1b_result']['n1a_result']['E_LCT_J'],6652.)
        self.assertTrue(results[0]['n1b_result']['n1a_result']['all_offered_business_delivered'])
        EXAMPLES['real160_controlled_geometry_loop']=dict(scope='ENGINEERING_CONTROLLED_SHORT_LOOP_ONLY',
            geometry_catalog_coverage='ONE_EXPLICIT_TERMINAL_PAIR_FROM_FROZEN_ASSET',
            selected_window=chosen,test_parameters=dict(T_s=4.,injection_end_s=1.,rate_bit_s=1.,
                capacity_bit_s=10.,setup=asdict(profile),earth_radius_km=6378.137),result=results[0])


if __name__=='__main__':unittest.main()
