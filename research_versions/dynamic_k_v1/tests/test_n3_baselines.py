"""Engineering-only closed-loop tests; all physical execution is the N2 API."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
import json,hashlib
from pathlib import Path
import sys
import unittest

V=Path(__file__).resolve().parents[1];P=V.parents[1]
sys.path.insert(0,str(V));sys.path.insert(0,str(P/'src'))
from runtime.n3_baselines import (ClosedLoopBaseline,StaticHold,ReactiveDynamicK,CurrentObservation,
    observe_current,paired_runs,validate_n3,digest)
from runtime.n2_actions import Add,Drop,Hold,Setup,LinkRef,ActionValidator
from runtime.n2_controller import AtomicTopologyController
from runtime.n2_candidates import CandidateSource
from runtime.n2_physical import N2PhysicalLayer,SyntheticWindowGuard,Sgp4PhysicalGuard,ReplayableSgp4Model
from runtime.n1b_evaluator import DeliveredFluidEvaluator
from runtime.n1b_observer import ObservedD2Engine
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog,TerminalPairWindow
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.gate_c_terminal_geometry import TerminalGeometryConfig
from dynamic_lisl.commodity import Commodity
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace,TrafficSegment

NODES=tuple('S%03d'%i for i in range(160));A,B,C,D=NODES[:4]
A1,B1,C1,D1=((n,'D1') for n in (A,B,C,D));A2,B2,C2=((n,'D2') for n in (A,B,C))
PROFILE=Setup(.5,.5,.5)
N1A_BINDING=N1B_BINDING=N2_BINDING=N3_BINDING=None
EXAMPLES={};COVERAGE=None;PRIOR_CATALOG_EVIDENCE=None


def synthetic(*,connected=False,pairs=((A1,B1),),destination=B,rate=10.,T=4.,expiry=100.,
              windows=None,segments=None,tx_end=None,capacity=20.):
    ex=TerminalExecutor(NODES)
    if connected:
        ex.submit([Connect(A1,B1,expiry,0.,0.,0.)])
        if tx_end is not None:ex.start_tx(A1,tx_end)
    if windows is None:
        windows=[TerminalPairWindow(a[0],a[1],b[0],b[1],0.,100.) for a,b in pairs]
    cat=TerminalPairCatalog(windows,{n:i for i,n in enumerate(NODES)})
    layer=N2PhysicalLayer(TerminalPairPhysicalFeasibility(cat),SyntheticWindowGuard())
    trace=PiecewiseConstantTrafficTrace(('f',),segments or [TrafficSegment(0.,1.,{'f':rate})])
    e=ObservedD2Engine(NODES,(),capacity,[Commodity('f',A,destination)],trace,lambda edge,t:1.,ex)
    return wrap(e,layer,T)


def wrap(e,layer,T):
    ev=DeliveredFluidEvaluator(e,T_s=T,time_tolerance_s=1e-9,energy_tolerance_J=1e-6,
        business_tolerance_bits=1e-6,n1a_binding=N1A_BINDING,n1b_binding=N1B_BINDING)
    return AtomicTopologyController(ev,layer,binding=N2_BINDING)


def loop(c,*,policy=None,epochs=(0.,.5,1.,2.,3.),setup=PROFILE,budgets=None):
    return ClosedLoopBaseline(c,policy or ReactiveDynamicK(),test_epochs_s=epochs,test_setup=setup,
                              binding=N3_BINDING,test_retention_budgets=budgets)


def pair(c,epochs=(0.,.5,1.,2.,3.),setup=PROFILE):
    return paired_runs(c,test_epochs_s=epochs,test_setup=setup,binding=N3_BINDING)


def events(r):
    return [x for a in r['decision_audit'] for x in a['terminal_events_since_previous_epoch']]+r['terminal_events_after_last_epoch']


class ClosedLoopTests(unittest.TestCase):
    def test_01_STATIC_HOLD_natural_expiry_fixed_T(self):
        r=loop(synthetic(connected=True,rate=0.,expiry=3.),policy=StaticHold()).run()
        self.assertEqual(r['non_HOLD_accepted_count'],0)
        self.assertEqual(r['n2_result']['K_admit'],0)
        self.assertEqual(r['metrics']['E_LCT_J'],6640.)
        self.assertTrue(any(x['event']=='LINK_DOWN' and x['time']==3. for x in events(r)))
        EXAMPLES['STATIC_HOLD_natural_expiry']=r

    def test_02_paired_K0_ADD_then_idle_DROP_analytic_metrics(self):
        r=pair(synthetic());s=r['STATIC_HOLD'];d=r['REACTIVE_DYNAMIC_K']
        self.assertEqual(s['fixture_identity'],d['fixture_identity'])
        self.assertEqual((s['metrics']['E_LCT_J'],s['metrics']['J_T_bit_s'],s['metrics']['N_T_bits']),(6400.,35.,10.))
        self.assertIsNone(s['metrics']['mean_delivered_fluid_delay_s'])
        self.assertEqual([x['selected_action']['kind'] for x in d['decision_audit']],['ADD','HOLD','HOLD','HOLD','DROP'])
        self.assertEqual((d['metrics']['E_LCT_J'],d['metrics']['DeltaE_LCT_J']),(6630.,230.))
        self.assertEqual((d['metrics']['J_T_bit_s'],d['metrics']['mean_delivered_fluid_delay_s']),(17.5,1.75))
        self.assertEqual(d['metrics']['R_del_T'],1.)
        self.assertEqual(d['metrics']['delivered_bit_age_integral_bit_s'],d['metrics']['J_T_bit_s'])
        EXAMPLES['paired_K0_ADD_delivery_idle_DROP']=r

    def test_03_setup_not_counted_as_admit_K(self):
        x=loop(synthetic());a=x.step();b=x.step();c=x.step()
        self.assertEqual(a['after_observation']['K_admit'],0)
        self.assertEqual(b['after_observation']['K_admit'],0)
        self.assertEqual(c['current_observation']['K_admit'],1)
        self.assertEqual([t['event'] for t in b['terminal_events_since_previous_epoch']].count('LINK_UP'),0)
        self.assertTrue(any(t['event']=='LINK_UP' and t['time']==1. for t in c['terminal_events_since_previous_epoch']))

    def test_04_no_demand_DROP_real_DRAINING_and_energy_reduction(self):
        r=pair(synthetic(connected=True,rate=0.,tx_end=2.),epochs=(0.,.5,2.,3.))
        d=r['REACTIVE_DYNAMIC_K'];s=r['STATIC_HOLD']
        self.assertEqual(d['decision_audit'][0]['selected_action']['kind'],'DROP')
        self.assertEqual(d['decision_audit'][0]['after_observation']['K_admit'],0)
        self.assertEqual(d['n2_result']['release_audit'][0]['draining_times_s'],[0.])
        self.assertEqual(d['n2_result']['release_audit'][0]['link_down'][0]['time_s'],2.)
        self.assertEqual((d['metrics']['E_LCT_J'],s['metrics']['E_LCT_J']),(6560.,6720.))
        self.assertEqual(d['n2_result']['n1b_result']['n1a_result']['five_execution_state_dwell_s']['DRAINING'],4.)
        EXAMPLES['paired_no_demand_DROP_draining_energy']=r

    def test_05_REPLACE_resource_constrained_BBM(self):
        r=pair(synthetic(connected=True,pairs=((A1,C1),),destination=C,T=5.,tx_end=1.),
               epochs=(0.,.5,1.,2.,3.,4.))
        d=r['REACTIVE_DYNAMIC_K'];first=d['decision_audit'][0]
        self.assertEqual((first['selected_action']['kind'],first['selected_action']['mode']),('REPLACE','BBM'))
        self.assertEqual(first['actual_gate_receipt']['actual_immediate_release_ids'],['L1'])
        self.assertEqual(first['candidate_audit']['diagnostics']['ADD']['legal'],0)
        self.assertTrue(d['metrics']['all_offered_business_delivered'])
        self.assertEqual(d['n2_result']['release_audit'][0]['draining_times_s'],[0.])
        EXAMPLES['paired_resource_constrained_REPLACE_BBM']=r

    def test_06_REPLACE_MBB_only_real_spare_resources(self):
        r=pair(synthetic(connected=True,pairs=((A2,C2),),destination=C,T=5.,tx_end=2.),
               epochs=(0.,.5,1.,2.,3.,4.))
        d=r['REACTIVE_DYNAMIC_K'];first=d['decision_audit'][0]
        self.assertEqual((first['selected_action']['kind'],first['selected_action']['mode']),('REPLACE','MBB'))
        self.assertEqual(first['actual_gate_receipt']['actual_immediate_release_ids'],[])
        self.assertEqual(d['n2_result']['release_audit'][0]['draining_times_s'],[1.])
        self.assertEqual(d['n2_result']['release_audit'][0]['link_down'][0]['time_s'],2.)
        self.assertTrue(d['metrics']['all_offered_business_delivered'])
        EXAMPLES['paired_REPLACE_MBB_spare_terminals']=r

    def test_07_partition_expiry_Q_I_reconnect_FIFO(self):
        windows=[TerminalPairWindow(A,'D1',B,'D1',0.,2.),TerminalPairWindow(A,'D1',B,'D1',3.,100.)]
        c=synthetic(windows=windows,T=7.,capacity=15.,segments=[TrafficSegment(0.,4.,{'f':10.})])
        r=loop(c,epochs=(0.,1.,2.,2.5,3.,4.,5.,6.)).run()
        a=r['decision_audit'][2]['current_observation']
        self.assertEqual(a['K_admit'],0)
        self.assertGreater(sum(v for _,_,v in a['queues']),0.)
        self.assertGreater(sum(v for _,_,_,v in a['in_flight']),0.)
        self.assertEqual(r['decision_audit'][4]['selected_action']['kind'],'ADD')
        self.assertTrue(r['metrics']['all_offered_business_delivered'])
        self.assertAlmostEqual(r['metrics']['delivered_bits'],40.)
        self.assertAlmostEqual(r['metrics']['J_T_bit_s'],r['metrics']['delivered_bit_age_integral_bit_s'])
        EXAMPLES['natural_partition_Q_I_preserved_reconnected_FIFO']=r

    def test_08_unreachable_to_T_remaining_and_no_delivery_null(self):
        r=loop(synthetic(pairs=())).run()
        self.assertEqual((r['metrics']['N_T_bits'],r['metrics']['delivered_bits']),(10.,0.))
        self.assertIsNone(r['metrics']['mean_delivered_fluid_delay_s'])
        self.assertTrue(r['metrics']['evaluation_completed_normally'])
        self.assertFalse(r['metrics']['all_offered_business_delivered'])
        self.assertEqual(r['decision_audit'][0]['candidate_audit']['diagnostics']['ADD']['status'],'NO_LEGAL_PHYSICAL_ACTION')
        EXAMPLES['unreachable_until_T']=r

    def test_09_partial_delivery_age_and_remaining_age_identity(self):
        r=loop(synthetic(T=2.25),epochs=(0.,1.,2.)).run();m=r['metrics']
        self.assertEqual((m['delivered_bits'],m['N_T_bits']),(5.,5.))
        self.assertEqual(m['delivered_bit_age_integral_bit_s'],9.375)
        self.assertEqual(m['mean_delivered_fluid_delay_s'],1.875)
        self.assertEqual(m['J_T_bit_s'],16.875)
        self.assertFalse(m['all_offered_business_delivered'])
        EXAMPLES['partial_delivery_continuous_FIFO']=r

    def test_10_clone_checkpoint_restore_full_audit_exact(self):
        c=loop(synthetic());c.step();c.step()
        copied=c.clone();restored=ClosedLoopBaseline.restore(c.checkpoint())
        r=c.run();self.assertEqual(r,copied.run());self.assertEqual(r,restored.run())
        EXAMPLES['checkpoint_replay']=r

    def test_11_identical_real_actions_exact_N1a_N1b(self):
        original=synthetic();manual=original.clone();r=loop(original).run()
        for epoch in r['decision_audit']:
            manual.advance_to(epoch['time_s'])
            acts=manual.candidates(PROFILE)['candidates']
            action=next(a for a in acts if asdict(a)==epoch['selected_action'])
            manual.submit(action)
        self.assertEqual(r['n2_result']['n1b_result'],manual.run()['n1b_result'])

    def test_12_future_trace_not_visible_and_does_not_affect_selection(self):
        c=synthetic(segments=[TrafficSegment(0.,1.,{'f':10.}),TrafficSegment(1.,2.,{'f':0.})])
        other=synthetic(segments=[TrafficSegment(0.,1.,{'f':10.}),TrafficSegment(1.,2.,{'f':1000.})])
        self.assertNotEqual(c.engine.trace.sha256(),other.engine.trace.sha256())
        obs=observe_current(c);self.assertEqual(obs,observe_current(other))
        actions=tuple(c.candidates(PROFILE)['candidates'])
        self.assertEqual(ReactiveDynamicK().select(obs,actions),ReactiveDynamicK().select(observe_current(other),actions))
        self.assertFalse(any(hasattr(obs,k) for k in ('trace','evaluator','T','future_actions','results')))
        with self.assertRaises(ValueError):ReactiveDynamicK().select(c,actions)

    def test_13_candidate_budget_truncation_distinct_from_physical_absence(self):
        r=loop(synthetic(),budgets={'ADD':0}).run();first=r['decision_audit'][0]
        self.assertEqual(first['candidate_audit']['diagnostics']['ADD']['status'],'LEGAL_BUT_BUDGET_TRUNCATED')
        self.assertEqual(first['candidate_audit']['diagnostics']['ADD']['legal'],1)
        self.assertEqual(first['selected_action']['kind'],'HOLD')
        self.assertEqual(r['non_HOLD_accepted_count'],0)
        EXAMPLES['explicit_TEST_ONLY_budget_zero_not_physical_absence']=r

    def test_14_HOLD_while_demand_already_reachable(self):
        c=synthetic(connected=True);x=loop(c);first=x.step()
        self.assertEqual(first['selected_action']['kind'],'HOLD')
        self.assertEqual(first['current_observation']['K_admit'],1)

    def test_15_sort_reversal_and_no_candidate_or_policy_mutation(self):
        c=synthetic(pairs=((A1,B1),(A2,B2)));obs=observe_current(c);before=c.engine.canonical_state_sha256()
        candidates=c.candidates(PROFILE)['candidates'];p=ReactiveDynamicK()
        self.assertEqual(p.select(obs,candidates),p.select(obs,tuple(reversed(candidates))))
        self.assertEqual(before,c.engine.canonical_state_sha256())

    def test_16_fixed_T_idle_tail_320_dwell_and_nonnegative_delta(self):
        r=loop(synthetic(rate=0.)).run();core=r['n2_result']['n1b_result']['n1a_result']
        self.assertEqual(r['metrics']['E_LCT_J'],6400.)
        self.assertEqual(r['metrics']['DeltaE_LCT_J'],0.)
        self.assertEqual(sum(core['five_execution_state_dwell_s'].values()),1280.)
        self.assertEqual(r['metrics']['J_T_bit_s'],0.)

    def test_17_result_validation_rejects_mismatched_metrics_and_scope(self):
        r=loop(synthetic(rate=0.)).run()
        bad=deepcopy(r);bad['metrics']['E_LCT_J']+=1
        with self.assertRaises(ValueError):validate_n3(bad)
        bad=deepcopy(r);bad['scientific_gate_pass']=True
        with self.assertRaises(ValueError):validate_n3(bad)
        bad=deepcopy(r);bad['non_HOLD_accepted_count']=1
        with self.assertRaises(ValueError):validate_n3(bad)

    def test_18_invalid_epoch_inputs_and_no_formal_default(self):
        for values in ((1.,0.),(0.,0.),(-1.,),(5.,),(float('nan'),)):
            with self.assertRaises(ValueError):loop(synthetic(),epochs=values)
        c=json.loads((V/'configs/n3_baseline_semantics_v1.json').read_text(encoding='utf-8'))
        self.assertTrue(all(v is None for v in c['scientific_parameters'].values()))
        self.assertTrue(all(c[k] is None for k in ('decision_period_s','search_budget','maximum_concurrent_actions','Kmax')))


def real_fixture(*,full_catalog=False):
    from dynamic_lisl.gate_d_scenarios import Sgp4EdgeDelayProvider
    p=P/'outputs/gate_c_simplified_20260922T064019_313843Z'
    reference=json.loads((p/'z_ref.json').read_text());fixed=tuple(tuple(e) for e in reference['fixed_edges'])
    nodes=tuple(sorted({n for edge in fixed for n in edge}))
    rows=[json.loads(line) for line in (p/'terminal_pair_intervals.jsonl').read_text().splitlines()]
    model=ReplayableSgp4Model.load(P/'data/raw/sgp4_x720')
    cfg=TerminalGeometryConfig.from_dict(json.loads((P/'configs/hardware_gate_c_simplified_v1.json').read_text()))
    guard=Sgp4PhysicalGuard(model,cfg,earth_radius_km=6378.137)
    selected=rows
    if not full_catalog:
        selected=[]
        for row in sorted(rows,key=lambda x:(x['sat_a'],x['sat_b'],x['terminal_a'],x['terminal_b'],x['start_s'])):
            a=(row['sat_a'],row['terminal_a']);b=(row['sat_b'],row['terminal_b'])
            if row['sat_a'].startswith('X0_') and row['sat_b'].startswith('X1_') and row['start_s']==0. and row['end_s']>=4.:
                if guard.evaluate(a,b,0.)['accepted'] and guard.evaluate(a,b,.4)['accepted']:selected.append(row)
            if len(selected)==3:break
        if len(selected)!=3:raise ValueError('CONTROLLED_THREE_PAIR_GEOMETRY_INPUT_MISSING')
    cat=TerminalPairCatalog.from_records(selected,{n:int(n.split('_')[0][1:]) for n in nodes})
    layer=N2PhysicalLayer(TerminalPairPhysicalFeasibility(cat),guard)
    trace=PiecewiseConstantTrafficTrace(('real160',),[TrafficSegment(0.,1.,{'real160':1.})])
    e=ObservedD2Engine(nodes,fixed,10.,[Commodity('real160','X0_1','X1_1')],trace,
        Sgp4EdgeDelayProvider(model,nodes),TerminalExecutor(nodes))
    return wrap(e,layer,4.),rows


class Real160Tests(unittest.TestCase):
    def test_19_complete_registered_catalog_coverage_diagnostic(self):
        global COVERAGE
        c,rows=real_fixture(full_catalog=True);ex=c.engine.executor;setup=Setup(.2,.2,.2)
        if PRIOR_CATALOG_EVIDENCE is not None:
            path,expected_hash=PRIOR_CATALOG_EVIDENCE
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),expected_hash)
            prior=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(prior['status'],'PASS_COMPLETE_REGISTERED_RECORD_PROBES')
            self.assertEqual(prior['registered_rows'],len(rows))
            self.assertEqual(prior['record_probes'],len(rows))
            self.assertEqual(prior['omitted_registered_rows'],0)
            self.assertIsNone(prior['candidate_budget'])
            self.assertEqual(prior['current_t0_windows'],len(c.validator.physical.catalog.terminal_pair_candidates(0.,ex.satellite_ids)))
            self.assertEqual([p['row_index'] for p in prior['record_probes_evidence']],list(range(len(rows))))
            for row,probe in zip(rows,prior['record_probes_evidence']):
                self.assertEqual(probe['window_sha256'],digest(row));self.assertEqual(probe['time_s'],row['start_s'])
            first=json.loads((path.parent/'n3_test_report.json').read_text(encoding='utf-8'))
            self.assertEqual(first['tests_run'],20)
            self.assertFalse(any('test_19_' in r['test'] for r in first['failures']+first['errors']+first['skipped']))
            # Every original input is byte-identical, or retained as an explicit source snapshot.
            original=json.loads((path.parent.parent/'implementation_manifest.json').read_text(encoding='utf-8'))
            snapshots={r['source_path']:P/r['snapshot_path'] for name in ('source_snapshots.json','source_snapshots_extra.json')
                       for r in json.loads((path.parent/name).read_text(encoding='utf-8'))['files']}
            for row in original['files']+list(original['anchors'].values()):
                p=snapshots.get(row['path'],P/row['path'])
                data=p.read_bytes();self.assertEqual(len(data),row['byte_count'])
                self.assertEqual(hashlib.sha256(data).hexdigest(),row['sha256'])
            # Frozen N2 code/geometry used by the complete diagnostic are unchanged.
            N2_BINDING.verify()
            COVERAGE=deepcopy(prior)
            COVERAGE['retained_diagnostic_evidence']=dict(path=path.relative_to(P).as_posix(),sha256=expected_hash,
                status='INPUTS_AND_ALL_RECORD_MAPPINGS_REVALIDATED',execution='ACTUAL_FULL_DIAGNOSTIC_IN_ATTEMPT01')
            print('Revalidated the independently pinned full 2742-row diagnostic; no repeated physical scan.',flush=True)
            return
        before=digest(ex.snapshot());source=c.candidates(setup)
        windows=c.validator.physical.catalog.terminal_pair_candidates(0.,ex.satellite_ids)
        self.assertEqual(source['diagnostics']['ADD']['considered'],len(windows))
        self.assertEqual(len(windows),sum(r['start_s']<=0<r['end_s'] for r in rows))
        self.assertEqual(before,digest(ex.snapshot()))
        probes=[]
        # N2 sorted action_key uses repr; use endpoint identities instead of zip order.
        masks={(m['action'].a,m['action'].b):m for m in source['masks'] if m['action'].kind=='ADD'}
        for index,row in enumerate(rows):
            a=(row['sat_a'],row['terminal_a']);b=(row['sat_b'],row['terminal_b'])
            if row['start_s']==0.:
                m=masks[(a,b)];accepted=m['legal'];reason=m['reason'];time=0.
            else:
                probe=TerminalExecutor(ex.satellite_ids);probe.advance(row['start_s'])
                state=digest(probe.snapshot());m=c.validator.validate(probe,Add(a,b,setup))
                self.assertEqual(state,digest(probe.snapshot()));accepted=m['accepted'];reason=m['reason'];time=row['start_s']
            probes.append(dict(row_index=index,window_sha256=digest(row),time_s=time,accepted=accepted,reason=reason or 'ACCEPTED'))
            if (index+1)%500==0:print('catalog probe %d/%d'%(index+1,len(rows)),flush=True)
        self.assertEqual(len(probes),len(rows));self.assertEqual(len({x['row_index'] for x in probes}),len(rows))
        # Catalog paths for DROP and REPLACE with one genuine active connection.
        chosen=next(a for a in source['candidates'] if a.kind=='ADD')
        trial=ex.clone_for_transaction();plan=c.validator.validate(trial,Add(chosen.a,chosen.b,Setup(0.,0.,0.)))
        self.assertTrue(plan['accepted']);trial.submit(plan['commands'])
        occupied=CandidateSource(c.validator).generate(trial,setup)
        self.assertGreater(occupied['diagnostics']['DROP']['legal'],0)
        self.assertGreater(occupied['diagnostics']['REPLACE']['legal'],0)
        COVERAGE=dict(status='PASS_COMPLETE_REGISTERED_RECORD_PROBES',scope='FROZEN_160_SAT_CATALOG_AT_CONTROLLED_SAMPLE_TIMES_ONLY',
            registered_rows=len(rows),registered_nodes=len(ex.satellite_ids),record_probes=len(probes),
            current_t0_windows=len(windows),t0_diagnostics=source['diagnostics'],
            t0_rejection_counts=dict(Counter(m['reason'] for m in source['masks'] if m['action'].kind=='ADD' and not m['legal'])),
            all_record_reason_counts=dict(Counter(x['reason'] for x in probes)),record_probes_evidence=probes,
            occupied_current_catalog_diagnostics=occupied['diagnostics'],candidate_budget=None,
            omitted_registered_rows=0,unregistered_universe_coverage_claimed=False,
            replacement_subset_coverage=source['replacement_coverage'],
            scientific_gate_pass=False,formal_experiments_executed=False)

    def test_20_real160_controlled_catalog_multi_epoch_paired_loop_replay(self):
        c,rows=real_fixture();self.assertEqual(len(c.engine.nodes),160)
        profile=Setup(.2,.2,.2);epochs=(0.,.2,.4,1.25,2.,3.)
        r=pair(c,epochs,profile);d=r['REACTIVE_DYNAMIC_K'];s=r['STATIC_HOLD']
        self.assertEqual(s['fixture_identity'],d['fixture_identity'])
        self.assertGreater(d['non_HOLD_accepted_count'],0)
        self.assertTrue(any(a['selected_action']['kind']=='ADD' for a in d['decision_audit']))
        self.assertTrue(any(a['selected_action']['kind']=='DROP' for a in d['decision_audit']))
        self.assertTrue(d['metrics']['all_offered_business_delivered'])
        self.assertEqual(s['metrics']['delivered_bits'],0.)
        self.assertGreater(d['metrics']['mean_delay_absolute_error_bound_s'],0.)
        checkpoint=loop(c.clone(),epochs=epochs,setup=profile);checkpoint.step();checkpoint.step()
        restored=ClosedLoopBaseline.restore(checkpoint.checkpoint())
        self.assertEqual(checkpoint.run(),restored.run())
        # Fresh deterministic replay from identical full-catalog inputs.
        self.assertEqual(d,loop(c.clone(),epochs=epochs,setup=profile).run())
        EXAMPLES['real160_natural_SGP4_controlled_catalog_paired_multi_epoch']=dict(
            scope='ENGINEERING_TEST_ONLY',registered_catalog_rows=len(rows),catalog_scope='THREE_EXPLICIT_TERMINAL_PAIRS_FROM_REGISTERED_160_SAT_CATALOG',
            selected_windows=[w.to_dict() for values in c.validator.physical.catalog.windows.values() for w in values],
            engineering_fixture_omitted_window_rows=len(rows)-3,omission_is_retention_budget=False,
            paired_results=r,scientific_performance_claimed=False)


if __name__=='__main__':unittest.main()
