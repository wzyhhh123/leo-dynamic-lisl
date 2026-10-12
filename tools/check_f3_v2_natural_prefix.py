"""160-star K4 engineering prefix: serial/8-worker, never registered P1-v2.

Uses a predeclared small structural fixture pool, not a production-universe or
approved K* acceptance. No J-driven fixture selection or controller comparison.
"""
from datetime import datetime,timezone
import hashlib
import json
import multiprocessing
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256
from dynamic_lisl.f3_v2.joint_action import BatchReplaceMember,canonical_sha256
from dynamic_lisl.f3_v2.batch_executor import BatchPhysicalValidator,BatchSafetyValidator
from dynamic_lisl.f3_v2.service_adapter import ScriptedBatchProposal
from dynamic_lisl.f3_v2.natural_engine import NaturalGeometryBatchEngine
from dynamic_lisl.f3_v2.joint_proposer import BoundedJointProposer,JointSearchBudget
from dynamic_lisl.f3_v2.batch_rollout import JointRolloutController,PersistentBatchBranchPool
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect,pair
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.operational_policy import OperationalPolicy
from dynamic_lisl.commodity import Commodity
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace,TrafficSegment
from dynamic_lisl.common_router import DeterministicShortestPropagationDelayRouter
from dynamic_lisl.sgp4_model import Sgp4Model
from dynamic_lisl.gate_e2_experiments import E2Sgp4EdgeDelayProvider

FRAME='V2_NATURAL_K4_ENGINEERING_WORLD'
EPOCHS=(0,2,4,6,8,10)
HORIZON=10


def require(condition,reason):
    if not condition:raise AssertionError(reason)


def load_scene():
    read=lambda rel:json.loads((ROOT/rel).read_text(encoding='utf-8'))
    topology=read('configs/z_moderate_v1.json')
    contract=read('configs/gate_d0_traffic_contract.json')
    traffic=read('configs/gate_f3_traffic_hotspot_migration_v1.json')
    od=read('configs/gate_d0_od_manifest_16.json')
    hardware=read('configs/hardware_gate_c_simplified_v1.json')
    fixed=tuple(tuple(e) for e in topology['fixed_edges'])
    nodes=tuple(sorted({n for edge in fixed for n in edge}));planes={n:int(n.split('_')[0][1:]) for n in nodes}
    records=[json.loads(line) for line in (ROOT/'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl').read_text(encoding='utf-8').splitlines()]
    physical=TerminalPairPhysicalFeasibility(TerminalPairCatalog.from_records(records,planes))
    executor=TerminalExecutor(nodes)
    for row in topology['bindings']:executor.submit((Connect(tuple(row['a']),tuple(row['b']),row['end_s'],0,0,0),))
    commodities=tuple(Commodity.from_dict(row) for row in od['commodities'])
    trace=PiecewiseConstantTrafficTrace(tuple(c.commodity_id for c in commodities),tuple(
        TrafficSegment(row['start_s'],row['end_s'],{c.commodity_id:.5*traffic['alpha_star_bit_s']*row['g'][c.commodity_id] for c in commodities},row['label'])
        for row in traffic['segments']))
    engine=NaturalGeometryBatchEngine(nodes,fixed,contract['link_capacity_bit_s_per_direction'],commodities,
        trace,E2Sgp4EdgeDelayProvider(Sgp4Model.load(ROOT/'data/raw/sgp4_x720'),nodes),executor,
        router=DeterministicShortestPropagationDelayRouter(),absolute_time_frame_id=FRAME,
        conservation_abs_tolerance_bits=contract['conservation_abs_tolerance_bits'],
        conservation_relative_tolerance=contract['conservation_relative_tolerance'],state_tolerance_bits=contract['state_tolerance_bits'])
    pv=BatchPhysicalValidator(physical,max_batch_replace=4,observation_end_s=600,absolute_time_frame_id=FRAME)
    validator=BatchSafetyValidator(pv,fixed,OperationalPolicy('STRICT_CONNECTED'))
    return engine,validator,planes,hardware['audit_setup_fixture']


def fixture_members(engine,validator,planes,setup):
    """At most four disjoint genuine-MBB witnesses preserving plane pairs.

    Lexical first legal window per current old binding, end>t+H. A structural
    engineering fixture only; cannot be used as the production candidate source.
    """
    start=time.perf_counter();members=[];footprint=set();inspected=0;rejects=[]
    windows=sorted(validator.physical_validator.physical_layer.catalog.terminal_pair_candidates(engine.now,engine.nodes),
        key=lambda w:pair(w.endpoint_a,w.endpoint_b))
    for old in sorted(engine.executor.links.values(),key=lambda link:link.endpoints):
        old_planes=tuple(sorted(planes[e[0]] for e in old.endpoints))
        if footprint.intersection(old.endpoints) or old.draining or old.release_owner:continue
        for window in windows:
            new=pair(window.endpoint_a,window.endpoint_b)
            if tuple(sorted(planes[e[0]] for e in new))!=old_planes or window.end_s<=engine.now+HORIZON:continue
            if new==old.endpoints or footprint.intersection(new):continue
            if any(engine.executor.terminals[e].phase!='IDLE' or engine.executor.terminals[e].reservation_id for e in new):continue
            inspected+=1
            identity={'t':engine.now,'old':old.endpoints,'new':new}
            member=BatchReplaceMember('NATURAL-FIXTURE-'+canonical_sha256(identity),len(members),old.endpoints,new,
                setup['retarget_a_s'],setup['retarget_b_s'],setup['acquisition_s'])
            from dynamic_lisl.f3_v2.joint_action import JointAction
            action=JointAction(engine.now,FRAME,engine.decision_root_sha256(),canonical_sha256([]),(member,))
            plan=validator.evaluate(engine.executor,action,decision_root_sha256=engine.decision_root_sha256())
            if not plan.accepted:rejects.append({'member_id':member.member_id,'reason':plan.reason});continue
            if plan.member_results[0]['transition_mode']!='MBB':raise AssertionError('FIXTURE_EXPECTED_GENUINE_MBB')
            members.append(member);footprint.update(member.footprint);break
        if len(members)==4:break
    return tuple(members),{'role':'BOUNDED_STRUCTURAL_FIXTURE_NOT_PRODUCTION_SOURCE','inspected':inspected,
        'rejections':rejects,'member_ids':[m.member_id for m in members],'wall_s':time.perf_counter()-start,
        'no_performance_read':True}


def scientific_metadata(metadata):
    return {k:v for k,v in metadata.items() if k!='engineering_worker_timing'}


def main():
    out=ROOT/'outputs'/('f3_v2_natural_prefix_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir()
    budget=JointSearchBudget(4,2,2,8,4,100,100,9)
    files=['configs/z_moderate_v1.json','configs/gate_d0_traffic_contract.json','configs/gate_d0_od_manifest_16.json',
        'configs/gate_f3_traffic_hotspot_migration_v1.json','configs/hardware_gate_c_simplified_v1.json',
        'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl']
    files+=sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'data/raw/sgp4_x720').glob('*') if p.is_file())
    hashes={p:file_sha256(ROOT/p) for p in files}
    write_new_json(out/'fixture_contract.json',{'scope':'ENGINEERING_ONLY','epochs':EPOCHS,'horizon_s':HORIZON,
        'scene':'160_STAR_K4_HISTORICAL_REFERENCE','rho':.5,'commodities':16,'workers':8,'budget':budget.__dict__,
        'member_rule':'first lexical genuine MBB preserving old plane pair; >10s natural window; disjoint resources; max4',
        'budget_status':'EXPLICIT_FIXTURE_PARAMETER_NOT_SCIENTIFIC_FREEZE','production_candidate_universe_validated':False,
        'K_star_acceptance':False,'registered_experiment':False,'parent_hashes':hashes,
        'code_hashes':{p.relative_to(ROOT).as_posix():file_sha256(p) for p in (ROOT/'src/dynamic_lisl/f3_v2').glob('*.py')},
        'tool_sha256':file_sha256(Path(__file__))})
    print(str(out),flush=True)
    serial=parallel=None;records=[];children_before={p.pid for p in multiprocessing.active_children()}
    started=time.perf_counter()
    try:
        serial,validator,planes,setup=load_scene();parallel=serial.clone()
        proposer=BoundedJointProposer(validator,budget)
        serial_controller=JointRolloutController(validator,rollout_cap=9)
        with PersistentBatchBranchPool(worker_count=8,sgp4_asset_folder=str(ROOT/'data/raw/sgp4_x720')) as workers:
            parallel_controller=JointRolloutController(validator,rollout_cap=9,branch_pool=workers)
            pool_identity=None
            for index,t in enumerate(EPOCHS):
                checkpoint={'time_s':t,'H_pre_call_serial':serial.canonical_state_sha256(),
                    'H_pre_call_parallel':parallel.canonical_state_sha256()}
                require(checkpoint['H_pre_call_serial']==checkpoint['H_pre_call_parallel'],'PRE_CALL_STATE_CHAIN_MISMATCH')
                advance_start=time.perf_counter()
                serial.advance_to(t);parallel.advance_to(t)
                checkpoint['advance_wall_s']=time.perf_counter()-advance_start
                checkpoint['H_decision_root_serial']=serial.canonical_state_sha256()
                checkpoint['H_decision_root_parallel']=parallel.canonical_state_sha256()
                require(checkpoint['H_decision_root_serial']==checkpoint['H_decision_root_parallel'],'DECISION_ROOT_MISMATCH')
                members,audit=fixture_members(serial,validator,planes,setup)
                require(members,'NO_STRUCTURAL_FIXTURE_MEMBER')
                proposal_start=time.perf_counter()
                ps=proposer.propose(serial.executor,members,decision_root_sha256=serial.decision_root_sha256())
                pp=proposer.propose(parallel.executor,members,decision_root_sha256=parallel.decision_root_sha256())
                checkpoint['proposer_pair_wall_s']=time.perf_counter()-proposal_start
                require(ps.public_document()==pp.public_document(),'NATURAL_PROPOSAL_MISMATCH')
                write_new_json(out/('epoch_%02d_inputs.json'%index),{'checkpoints':checkpoint,'pool':ps.public_document(),
                    'source_audit':audit,'decision_root_state':serial.canonical_state()})
                start=time.perf_counter();ds=serial_controller.observe(serial,ps,horizon_s=HORIZON)
                checkpoint['serial_observe_wall_s']=time.perf_counter()-start
                write_new_json(out/('epoch_%02d_serial_evaluation.json'%index),ds.metadata)
                start=time.perf_counter();dp=parallel_controller.observe(parallel,pp,horizon_s=HORIZON)
                checkpoint['parallel_observe_wall_s']=time.perf_counter()-start
                require(scientific_metadata(ds.metadata)==scientific_metadata(dp.metadata),'NATURAL_BRANCH_EXACT_MISMATCH')
                require(ds.action.to_dict()==dp.action.to_dict(),'NATURAL_SELECTED_ACTION_MISMATCH')
                checkpoint['H_post_observe_serial']=serial.canonical_state_sha256()
                checkpoint['H_post_observe_parallel']=parallel.canonical_state_sha256()
                require(checkpoint['H_post_observe_serial']==checkpoint['H_decision_root_serial'],'SERIAL_LIVE_STATE_MUTATION')
                require(checkpoint['H_post_observe_parallel']==checkpoint['H_decision_root_parallel'],'PARALLEL_LIVE_STATE_MUTATION')
                if pool_identity is None:pool_identity=workers._pool
                require(workers._pool is pool_identity,'WORKER_POOL_RECREATED')
                start=time.perf_counter()
                for engine,decision in ((serial,ds),(parallel,dp)):
                    engine.schedule_action(ScriptedBatchProposal(t,decision.action.batch_id,decision.action,validator,True));engine.settle_current_time()
                checkpoint['real_commit_pair_wall_s']=time.perf_counter()-start
                checkpoint['H_post_decision_serial']=serial.canonical_state_sha256()
                checkpoint['H_post_decision_parallel']=parallel.canonical_state_sha256()
                require(checkpoint['H_post_decision_serial']==checkpoint['H_post_decision_parallel'],'POST_DECISION_MISMATCH')
                checkpoint.update({'pool_sha256':ps.pool_sha256,'branch_count':len(ps.actions),
                    'selected_batch_id':ds.action.batch_id,'selected_batch_size':len(ds.action.members),
                    'queue_bits':serial.queues.total(),'inflight_bits':serial.in_flight.total(),
                    'delivered_bits':sum(serial.delivered.values()),'arrived_bits':sum(serial.arrived.values()),
                    'active_links':len(serial.executor.links),'reservations':len(serial.executor.reservations),
                    'exact_equivalence':True,'source_audit':audit})
                write_new_json(out/('epoch_%02d.json'%index),{'checkpoints':checkpoint,'pool':ps.public_document(),
                    'serial_decision':ds.metadata,'parallel_decision':dp.metadata,'post_decision_state':serial.canonical_state()})
                records.append(checkpoint)
            serial.advance_to(12);parallel.advance_to(12)
            require(serial.canonical_state_sha256()==parallel.canonical_state_sha256(),'FINAL_NEXT_ADVANCE_MISMATCH')
        require({p.pid for p in multiprocessing.active_children()}==children_before,'ORPHAN_WORKER')
        require(len({(r['arrived_bits'],r['delivered_bits'],r['queue_bits'],r['inflight_bits']) for r in records})>1,'REPEATED_INITIAL_STATE')
        require(all(file_sha256(ROOT/p)==h for p,h in hashes.items()),'FROZEN_INPUT_CHANGED')
        report={'status':'NATURAL_K4_FIXTURE_EXACT_EQUIVALENCE_PASS','epochs':len(records),
            'state_chain_exact':True,'persistent_pool_reused':True,'no_orphan_process':True,
            'natural_state_evolution':True,'records':records,'total_wall_s':time.perf_counter()-started,
            'production_candidate_universe_validated':False,'K_star_acceptance':False,
            'B4_v2_engineering_PASS':False,'registered_P1_v2_executed':False,'P2_started':False,'RL_started':False}
    except BaseException as error:
        report={'status':'ENGINEERING_FAIL_STOP','exception_type':type(error).__name__,'exception_message':str(error),
            'epochs_completed':len(records),'completed_epoch_records':records,'wall_s':time.perf_counter()-started,
            'B4_v2_engineering_PASS':False,'registered_P1_v2_executed':False}
        if serial is not None:write_new_json(out/'serial_failure_state.json',serial.canonical_state())
        if parallel is not None:write_new_json(out/'parallel_failure_state.json',parallel.canonical_state())
        if 'workers' in locals() and workers.last_failure_evidence is not None:
            write_new_json(out/'worker_failure_evidence.json',workers.last_failure_evidence)
    write_new_json(out/'report.json',report)
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps({'status':report['status'],'output_dir':str(out)},indent=2))
    return 0 if report['status'].endswith('_PASS') else 1


if __name__=='__main__':raise SystemExit(main())
