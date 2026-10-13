"""ONE 160-star PERSIST/BBM short prefix 3->3.125, never full branch."""
import json,time,os
from copy import deepcopy
from dataclasses import asdict
import common as c
from runtime.n4_p0r_handle_reader import HandleReaderLease
from runtime.n4_p0 import ForecastInput,causal_view,make_sanitized_root
from runtime.n4_p0f_events import ExactObservedD2Engine
from runtime.n2_actions import Replace,LinkRef,Setup
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect
from dynamic_lisl.commodity import Commodity
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace,TrafficSegment

def main():
    assert json.loads((c.A/'CORRECTNESS.json').read_text())['status']=='PASS_EXACT_FIELDS_AND_ORDER'
    assert json.loads((c.A/'FIXTURE_PERFORMANCE.json').read_text())['status']=='PASS_PAIRED_EQUIVALENCE_AND_MEASURED_COST'
    c.source_verify();start=time.perf_counter();old=c.old_context();deps=old.old.dependencies();g=old.guard()
    c.write('REAL_PREFIX_PLAN.json',dict(scene='NEW_BOUND_P0F_160_PERSIST_BBM_SHORT_PREFIX',
        start_s=3.,stop_s=3.125,original0016_full_branch_replayed=False,full_catalog_enumerated=False,
        controller_epoch_executed=False,maximum_child_wall_s=60,hashseed=os.environ.get('PYTHONHASHSEED')))
    with HandleReaderLease(deps+[g],old.vc) as lease:
        binding_start=time.perf_counter();f=old.setup(lease);template,rows=f.real_fixture(full_catalog=True)
        ex=TerminalExecutor(template.engine.nodes)
        ex.submit([Connect(('X0_1','D2'),('X1_1','D1'),600.,0.,0.,0.)])
        trace=PiecewiseConstantTrafficTrace(('f_bg','f_hot'),[
            TrafficSegment(0.,8.,{'f_bg':200000.,'f_hot':400000.},'CURRENT'),
            TrafficSegment(8.,20.,{'f_bg':200000.,'f_hot':1200000.},'REAL_FUTURE_NOT_EXPOSED')])
        e=ExactObservedD2Engine(template.engine.nodes,template.engine.fixed_edges,1e6,
            [Commodity('f_bg','X0_1','X1_1'),Commodity('f_hot','X0_10','X1_10')],trace,
            template.engine.delay,ex,variant_binding=c.variant_binding())
        live=f.wrap(e,template.validator.physical,30.);live.advance_to(3.)
        forecast=ForecastInput.from_current(causal_view(live).observation,T_s=30.,H_s=6.,mode='PERSIST')
        root=make_sanitized_root(live,forecast,binding=lease.guard(g));root.verify_isolation()
        root_bind=json.loads((c.V/'acceptance/0015/ROOT_BASELINE/root_binding.json').read_text())
        assert root.view.state_sha256==root_bind['causal_root_sha256'],'ROOT_CAUSAL_STATE_DRIFT'
        c.write('REAL_ROOT_VERIFICATION.json',dict(causal_sha256=root.view.state_sha256,
            expected_sha256=root_bind['causal_root_sha256'],exact_match=True,forecast_sha256=forecast.sha256,
            prefix_sha256=root.prefix_sha256,registered_catalog_rows=len(rows),legal_candidates_enumerated=None,
            root_build_and_guard_s=time.perf_counter()-binding_start))
        action=Replace((LinkRef.from_link(next(iter(root.atomic.engine.executor.links.values()))),),
            ('X0_10','D2'),('X1_10','D1'),Setup(.5,.5,.5),'BBM')
        branches={};timings={};outputs={}
        for mode in ('reference','sweep'):
            tick=time.perf_counter();branch=root.atomic.clone();clone_s=time.perf_counter()-tick
            tick=time.perf_counter()
            if mode=='sweep':branch.evaluator.age=c.SweepDeliveredAgeLedger.from_ledger(branch.evaluator.age)
            install_s=time.perf_counter()-tick
            assert causal_view(branch).state_sha256==root.view.state_sha256
            tick=time.perf_counter();receipt=branch.submit(action);submit_s=time.perf_counter()-tick
            assert receipt['accepted'],'BBM_PREFIX_ACTION_REJECTED'
            tick=time.perf_counter();result=branch.advance_to(3.125);advance_s=time.perf_counter()-tick
            final=c.data_hash((branch.engine.canonical_state(),vars(branch.evaluator.age)))
            timings[mode]=dict(clone_s=clone_s,seam_install_s=install_s,submit_s=submit_s,
                advance_network_FIFO_energy_validation_s=advance_s,total_from_clone_s=clone_s+install_s+submit_s+advance_s)
            outputs[mode]=dict(receipt=receipt,result=result,state_sha256=final,causal_sha256=causal_view(branch).state_sha256)
            branches[mode]=branch
            c.write('REAL_PREFIX_'+mode.upper()+'.json',dict(timings=timings[mode],output=outputs[mode],
                observation_count=len(branch.engine.age_observations),age_cursor=branch.evaluator.age.cursor))
        assert outputs['reference']==outputs['sweep'],'REAL_PREFIX_OUTPUT_OR_HASH_MISMATCH'
        assert c.norm(vars(branches['reference'].evaluator.age))==c.norm(vars(branches['sweep'].evaluator.age))
        # Independent light phase timings on identical observed prefix; never re-advance network.
        light=[];measured=c.counted_sweep_class(light).from_ledger(root.atomic.evaluator.age)
        tick=time.perf_counter();measured.consume(branches['reference'].engine);light_fifo_s=time.perf_counter()-tick
        # submit itself records REPORTED_DELIVERY; reproduce that observation at t=3 before consuming suffix.
        # The complete state comparator above is authoritative; light ledger is a timing-only observer.
        c.write('REAL_PREFIX_LIGHT.json',dict(rows=light,FIFO_observer_s=light_fifo_s,
            scope='REPLAY_OF_SAME_REAL_OBSERVER_PREFIX_WITHOUT_NETWORK_ADVANCE',
            original_state_modified=False,full_BBM_rerun=False))
        c.write('REAL_PREFIX_COMPARISON.json',dict(status='PASS_SHORT_PREFIX_EXACT',start_s=3.,stop_s=3.125,
            outputs_exact=True,ledger_fields_exact=True,existing_causal_and_business_state_hashes_exact=True,
            timings=timings,plain_order='REFERENCE_THEN_SWEEP_ONE_PAIR',
            measured_prefix_seconds=.125,full_BBM_speedup_claim=False,process_elapsed_s=time.perf_counter()-start))
    c.source_verify();print('REAL_PREFIX_EXACT_PASS',flush=True)
if __name__=='__main__':main()
