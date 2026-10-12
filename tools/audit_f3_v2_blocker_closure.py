"""Predeclared structural/cost closure probes; no registered run or tuning."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
import multiprocessing
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tests'))
from dynamic_lisl.f3_v2 import search_policy_probe as policy
from dynamic_lisl.f3_v2.batch_executor import BatchPhysicalValidator, BatchSafetyValidator
from dynamic_lisl.f3_v2.joint_action import BatchReplaceMember, JointAction, canonical_sha256, terminal_state_hash
from dynamic_lisl.f3_v2.joint_proposer import JointSearchBudget
from dynamic_lisl.f3_v2.evidence import file_sha256
from dynamic_lisl.terminal_executor import TerminalExecutor, Connect, pair
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.operational_policy import OperationalPolicy


def read(p): return json.loads((ROOT/p).read_text(encoding='utf-8'))
def write(p, d):
    if p.exists(): raise ValueError('IMMUTABLE_NEW_ATTEMPT_REQUIRED')
    p.write_bytes((json.dumps(d, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode('utf-8'))
def seal(out):
    write(out/'artifact_hashes.json', {p.relative_to(out).as_posix(): file_sha256(p)
        for p in sorted(out.rglob('*')) if p.is_file()})
def budget(): return JointSearchBudget(16,8,4,32,4,184,184,33)


def natural_root(K, t):
    topo = read('configs/z_moderate_v1.json')
    fixed = tuple(tuple(e) for e in topo['fixed_edges'])
    nodes = tuple(sorted({n for e in fixed for n in e}))
    planes = {n:int(n.split('_')[0][1:]) for n in nodes}
    records = [json.loads(l) for l in (ROOT/'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl').read_text(encoding='utf-8').splitlines()]
    physical = TerminalPairPhysicalFeasibility(TerminalPairCatalog.from_records(records, planes))
    setup = read('configs/hardware_gate_c_simplified_v1.json')['audit_setup_fixture']
    ex = TerminalExecutor(nodes); ex.advance(t)
    if K == 4:
        for row in topo['bindings']:
            ex.submit((Connect(tuple(row['a']),tuple(row['b']),row['end_s'],0.,0.,0.),))
    else:
        folders = {24:'20261008T152937_945871Z',48:'20261008T155517_075334Z',80:'20261008T155623_744449Z'}
        cert = read('outputs/f3_v2_structural_cost_probe_'+folders[K]+'/analytic_certificate_cost.json')
        assert cert['status']=='EXACT' and cert['target_K']==K
        commands = []
        for b in cert['bindings']:
            p = physical.evaluate(ex,*pair(*b),retarget_a=setup['retarget_a_s'],retarget_b=setup['retarget_b_s'],acquisition=setup['acquisition_s'])
            assert p['accepted'],p['reason']
            commands.append(replace(p['command'],retarget_a=0.,retarget_b=0.,acquisition=0.))
        ex.submit(commands)
    ex.assert_invariants(); assert len(ex.links)==K
    return ex,physical,planes,fixed,setup


def measured_source(ex, physical, planes, setup, t, epoch_index):
    calls = []
    original = policy.BatchPhysicalValidator
    class Observed(original):
        def evaluate(self,*a,**kw):
            start=time.perf_counter(); result=super().evaluate(*a,**kw)
            calls.append({'wall_s':time.perf_counter()-start,'accepted':result.accepted,'reason':result.reason})
            return result
    with patch.object(policy,'BatchPhysicalValidator',Observed):
        result = policy.scout(ex,physical,plane_by_satellite=planes,epoch_index=epoch_index,
            retarget_a_s=setup['retarget_a_s'],retarget_b_s=setup['retarget_b_s'],
            acquisition_s=setup['acquisition_s'],observation_end_s=600 if t is not None else 30)
    assert policy.BatchPhysicalValidator is original
    assert len(calls)==result['audit']['source_physical_calls']
    result['timing']['source_Gate_B_C_calls']=len(calls)
    result['timing']['source_Gate_B_C_wall_s']=sum(r['wall_s'] for r in calls)
    return result


def measured_proposer(ex, validator, raw, epoch_index, root=None):
    pv=validator.physical_validator
    original_p,original_joint=pv.evaluate,validator.evaluate
    physical_rows,joint_rows=[],[]
    def timed_p(*a,**kw):
        start=time.perf_counter();r=original_p(*a,**kw)
        physical_rows.append({'wall_s':time.perf_counter()-start,'members':len(a[1].members),'accepted':r.accepted})
        return r
    def timed_j(*a,**kw):
        start=time.perf_counter();r=original_joint(*a,**kw)
        joint_rows.append({'wall_s':time.perf_counter()-start,'members':len(a[1].members),'accepted':r.accepted})
        return r
    started=time.perf_counter()
    with patch.object(pv,'evaluate',timed_p),patch.object(validator,'evaluate',timed_j):
        pool=policy.StructuralPolicyProbeProposer(validator,budget(),epoch_index=epoch_index).propose(ex,raw['members'],decision_root_sha256=root)
    assert len(joint_rows)==pool.audit['joint_validation_calls']
    return pool,{'joint_proposer_wall_s':time.perf_counter()-started,
        'proposer_Gate_B_C_calls':len(physical_rows),'proposer_Gate_B_C_wall_s':sum(r['wall_s'] for r in physical_rows),
        'joint_safety_calls':len(joint_rows),'joint_safety_wall_s':sum(r['wall_s'] for r in joint_rows),
        'timing_note':'Nested totals overlap: do not add Gate_B_C and joint_safety to proposer wall.'}


def structure(out):
    from test_f3_v2_search_policy_probe import structural_fixture
    records=[]
    cases=[('KNOWN_20_NODE_WITNESS',None,None),('NATURAL_K4_T0',4,0),('NATURAL_K24_T0',24,0),('NATURAL_K48_T270',48,270),('NATURAL_K80_T570',80,570)]
    for label,K,t in cases:
        point=out/label;point.mkdir()
        if K is None:
            ex,p,planes,v=structural_fixture();setup={'retarget_a_s':1.,'retarget_b_s':1.,'acquisition_s':1.}
        else:
            ex,p,planes,fixed,setup=natural_root(K,t)
            v=BatchSafetyValidator(BatchPhysicalValidator(p,max_batch_replace=4,observation_end_s=600,absolute_time_frame_id='ENGINEERING_CLOSURE'),fixed,OperationalPolicy('STRICT_CONNECTED'))
        before=terminal_state_hash(ex)
        raw=measured_source(ex,p,planes,setup,t,0)
        write(point/'source.json',{'audit':raw['audit'],'timing':raw['timing']})
        pool,cost=measured_proposer(ex,v,raw,0)
        write(point/'pool.json',pool.public_document())
        replay=policy.StructuralPolicyProbeProposer(v,budget(),epoch_index=0).propose(ex,raw['members'][::-1])
        assert replay.public_document()==pool.public_document(),'STRUCTURAL_REPLAY_MISMATCH'
        witness=[]
        if K is None:
            for i in range(4):
                old=pair(('A'+str(i),'D1'),('B'+str(i),'D1'));new=pair(('C'+str(i),'D1'),('D'+str(i),'D1'))
                witness.append(BatchReplaceMember('V2-RAW-'+canonical_sha256({'time_s':ex.now,'old':old,'new':new}),i,old,new,1,1,1))
        elif K==4:
            doc=read('outputs/f3_v2_natural_source_coverage_20261008T162145_156464Z/structural_witness.json')
            witness=[BatchReplaceMember(**m) for m in doc['action']['members']]
        witness_proof=None
        if witness:
            a=JointAction(ex.now,v.physical_validator.absolute_time_frame_id,before,canonical_sha256([]),tuple(witness))
            witness_proof=v.evaluate(ex,a)
            write(point/'known_witness_current_validation.json',witness_proof.to_dict())
            assert witness_proof.accepted,'KNOWN_WITNESS_CURRENT_PHYSICAL_REJECTION'
        visited={r['member_id'] for r in raw['audit']['visited_rows']};rawids={m.member_id for m in raw['members']}
        single={m.member_id for m in pool.physical_singletons}
        record={'case':label,'K':K,'time_s':t,'source':raw['timing'],'proposer':cost,
            'scout_visits':raw['audit']['scout_visits'],'source_physical_calls':raw['audit']['source_physical_calls'],
            'old_binding_visited_count':raw['audit']['old_binding_visited_count'],'raw_count':len(rawids),
            'raw_old_count':len({m.old_binding for m in raw['members']}),'singleton_old_count':len({m.old_binding for m in pool.physical_singletons}),
            'stratum_counts':raw['audit']['stratum_counts'],'unvisited_identity_count':raw['audit']['unvisited_identity_count'],
            'coverage_by_size':pool.audit['coverage_by_size'],'pool_count':len(pool.actions),
            'deterministic_replay':True,'live_unchanged':terminal_state_hash(ex)==before,
            'known_safe_size4':bool(witness_proof and witness_proof.accepted),
            'known_witness_stage_coverage':[{'id':m.member_id,'scouted':m.member_id in visited,'raw':m.member_id in rawids,'singleton':m.member_id in single} for m in witness],
            'physics_nonexistence_proved':False,'policy_structural_acceptance':'PASS_SIZES_2_3_4_FOUND' if all(pool.audit['coverage_by_size'].get(str(s),0)>0 for s in (2,3,4)) else 'FAIL_OR_OMISSION_REPORTED_NOT_PHYSICAL_NONEXISTENCE',
            'controller_J_read':False,'initialization':'independent engineering pre-established fixture; not formal K1'}
        if K is None:
            C={n for m in raw['members'] for n,term in m.new_terminal_pair if n.startswith('C')}
            record['raw_C_terminal_vertex_cover']=sorted(C)
            record['resource_independent_batch_upper_bound_in_raw']=len(C)
            record['failure_cause']='FULL_SCOUT_COVERAGE_RAW_TRUNCATION_OMISSION'
        assert record['live_unchanged']
        write(point/'report.json',record);records.append(record)
        print(json.dumps({'case':label,'coverage':record['coverage_by_size'],'source_s':raw['timing']['source_wall_s'],'proposer_s':cost['joint_proposer_wall_s']}),flush=True)
    write(out/'report.json',{'status':'STRUCTURAL_POLICY_FAILURE_AND_COST_EVIDENCE_COMPLETE','records':records,
        'HF_SEARCH_final_freeze_recommended':False,'production_policy_changed':False,'K_star_selected':False,'registered_experiment_started':False})


def rollout(out):
    from check_f3_v2_natural_prefix import load_scene, scientific_metadata
    from dynamic_lisl.f3_v2.batch_rollout import JointRolloutController,PersistentBatchBranchPool
    from dynamic_lisl.f3_v2.service_adapter import ScriptedBatchProposal
    serial,v,planes,setup=load_scene();parallel=serial.clone()
    start=time.perf_counter();records=[];children={p.pid for p in multiprocessing.active_children()}
    try:
        with PersistentBatchBranchPool(worker_count=8,sgp4_asset_folder=str(ROOT/'data/raw/sgp4_x720')) as workers:
            sc=JointRolloutController(v,rollout_cap=33)
            pc=JointRolloutController(v,rollout_cap=33,branch_pool=workers)
            for epoch,t in enumerate((0,5)):
                before_s,before_p=serial.canonical_state_sha256(),parallel.canonical_state_sha256()
                assert before_s==before_p
                serial.advance_to(t);parallel.advance_to(t)
                root=serial.canonical_state_sha256();assert root==parallel.canonical_state_sha256()
                raw=measured_source(serial.executor,v.physical_validator.physical_layer,planes,setup,t,epoch)
                pool,cost=measured_proposer(serial.executor,v,raw,epoch,serial.decision_root_sha256())
                replay=policy.StructuralPolicyProbeProposer(v,budget(),epoch_index=epoch).propose(parallel.executor,raw['members'],decision_root_sha256=parallel.decision_root_sha256())
                assert replay.public_document()==pool.public_document()
                write(out/('epoch_%d_pool.json'%epoch),pool.public_document())
                write(out/('epoch_%d_source.json'%epoch),{'audit':raw['audit'],'timing':raw['timing']})
                started=time.perf_counter();ds=sc.observe(serial,pool,horizon_s=10);serial_wall=time.perf_counter()-started
                write(out/('epoch_%d_serial.json'%epoch),ds.metadata)
                started=time.perf_counter();dp=pc.observe(parallel,replay,horizon_s=10);parallel_wall=time.perf_counter()-started
                write(out/('epoch_%d_parallel.json'%epoch),dp.metadata)
                assert scientific_metadata(ds.metadata)==scientific_metadata(dp.metadata),'ALL_BRANCH_EXACT_MISMATCH'
                assert ds.action.to_dict()==dp.action.to_dict()
                assert serial.canonical_state_sha256()==parallel.canonical_state_sha256()==root
                for engine,decision in ((serial,ds),(parallel,dp)):
                    engine.schedule_action(ScriptedBatchProposal(t,decision.action.batch_id,decision.action,v,True));engine.settle_current_time()
                post=serial.canonical_state_sha256();assert post==parallel.canonical_state_sha256()
                row={'time_s':t,'H_pre_call':before_s,'H_decision_root':root,'H_post_observe':root,'H_post_decision':post,
                     'source':raw['timing'],'proposer':cost,'pool_size':len(pool.actions),'coverage_by_size':pool.audit['coverage_by_size'],
                     'serial_rollout_wall_s':serial_wall,'eight_worker_rollout_wall_s':parallel_wall,'speedup':serial_wall/parallel_wall,
                     'queue_bits':serial.queues.total(),'inflight_bits':serial.in_flight.total(),'delivered_bits':sum(serial.delivered.values()),
                     'selected_action_size':len(ds.action.members),'all_branch_exact':True,'state_chain_exact':True}
                write(out/('epoch_%d_report.json'%epoch),row);records.append(row)
                print(json.dumps({'epoch':t,'pool':len(pool.actions),'serial_s':serial_wall,'eight_worker_s':parallel_wall}),flush=True)
                if time.perf_counter()-start>1800:
                    break
            serial.advance_to(10);parallel.advance_to(10)
            assert serial.canonical_state_sha256()==parallel.canonical_state_sha256()
        assert {p.pid for p in multiprocessing.active_children()}==children,'ORPHAN_WORKER'
        write(out/'report.json',{'status':'CURRENT_NATURAL_ENGINEERING_TWO_EPOCH_EXACT_PASS' if len(records)==2 else 'COST_BUDGET_UNKNOWN_INCOMPLETE_PREFIX',
            'records':records,'total_wall_s':time.perf_counter()-start,'final_state_sha256':serial.canonical_state_sha256(),
            'no_orphan_process':True,'registered_experiment_started':False,'K_star_acceptance':False,'B4_overall_engineering_PASS':False,
            'short_prefix_not_episode_cost_bound':True,'fixture_was_not_selected_by_J':True})
    except BaseException as e:
        write(out/'failure_summary.json',{'type':type(e).__name__,'reason':str(e),'completed_epochs':records})
        write(out/'serial_failure_state.json',serial.canonical_state());write(out/'parallel_failure_state.json',parallel.canonical_state())
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('structure','rollout'),required=True)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args();out=(ROOT/args.output_dir).resolve()
    assert out.is_relative_to(ROOT)
    out.mkdir(parents=True,exist_ok=False)
    write(out/'protocol.json',{'scope':'ENGINEERING_ONLY','mode':args.mode,'tool_sha256':file_sha256(Path(__file__)),
        'code_sha256':{p.relative_to(ROOT).as_posix():file_sha256(p) for p in (ROOT/'src/dynamic_lisl/f3_v2').glob('*.py')},
        'policy':'RR_STRUCTURAL_SCOUT256_RAW64_SINGLE16_SEED4_V1','formal_freeze':False,'registered_experiment':False})
    try:
        (structure if args.mode=='structure' else rollout)(out)
    except BaseException as error:
        if not (out/'failure_summary.json').exists():write(out/'failure_summary.json',{'type':type(error).__name__,'reason':str(error)})
        raise
    finally:seal(out)


if __name__=='__main__':main()
