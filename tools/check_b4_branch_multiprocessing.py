"""ENGINEERING_PROFILE_ONLY Windows spawn B4 exactness and worker scaling."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import pickle
import psutil
import os
import subprocess
import statistics
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from dynamic_lisl.b4_branch_multiprocessing import (
    BranchTask, ParallelB4BranchPool, branch_evidence, encode_root)
from dynamic_lisl.common import read_json
from dynamic_lisl.controller_runner import controller_visible_state
from dynamic_lisl.gate_e2_experiments import GateE2Assets
from dynamic_lisl.gate_f3_p1_execution import P1RunExecutor
from run_gate_f3_p1_execution import preflight


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')


def setup(*, check_preflight=True):
    pre=preflight()[0] if check_preflight else {'pass':None,'status':'DEFERRED_TO_FINAL_ACCEPTANCE'}
    if check_preflight and not pre['pass']:raise AssertionError('P1_PREFLIGHT_FAIL')
    assets=GateE2Assets()
    manifest=read_json(ROOT/'configs/gate_f3_execution_manifest_v1.json')
    row=next(x for x in manifest['runs'] if x['block_id']=='P1'
             and x['controller']=='B4' and x['rho']==0.5)
    engineering={**row,'run_id':'ENGINEERING_PROFILE_ONLY-B4-MULTIPROCESSING',
                 'block_id':'ENGINEERING_PROFILE_ONLY'}
    runner=P1RunExecutor(assets,engineering)
    engine=runner.engine
    state=controller_visible_state(engine)
    specs=tuple(runner.candidate_source(state,{
        'epoch_index':0,'regime':'Z_MODERATE',
        'terminal_executor':engine.executor}))
    proposals=runner.proposer.propose(engine.executor,specs,
                                      assets.physical,assets.fixed,'Z_MODERATE')
    if len(proposals['proposals'])!=16:
        raise AssertionError('EXPECTED_EXACTLY_16_PRODUCTION_PROPOSALS')
    if sum(x['stratum']=='BBM_REQUIRED' for x in proposals['proposals'])!=8:
        raise AssertionError('EXPECTED_8_BBM_8_MBB')
    runner.controller.bind_candidate_specs(specs,engine.now)
    return pre,assets,runner,state,proposals


def serial_reference(controller,state,proposals):
    evidence=[];branch_results=[];total=[]
    evaluator=controller.evaluator
    original_finish=evaluator._finish
    def capture(*args,**kwargs):
        result=original_finish(*args,**kwargs)
        evidence.append(branch_evidence(args[0]))
        branch_results.append(asdict(result))
        return result
    def timed(name,fn):
        def wrapper(*args,**kwargs):
            start=time.perf_counter()
            result=fn(*args,**kwargs)
            total.append({'branch_id':result.branch_id,'action_kind':name,
                          'wall_s':time.perf_counter()-start})
            return result
        return wrapper
    before=controller.engine.canonical_state_sha256()
    start=time.perf_counter()
    with patch.object(evaluator,'_finish',capture),\
         patch.object(evaluator,'evaluate_hold',timed('HOLD',evaluator.evaluate_hold)),\
         patch.object(evaluator,'evaluate_candidate',timed('REPLACE',evaluator.evaluate_candidate)):
        decision=controller.evaluate_root_actions(state,proposals,{})
    wall=time.perf_counter()-start
    after=controller.engine.canonical_state_sha256()
    if before!=after:raise AssertionError('SERIAL_LIVE_MUTATION')
    if not all(row['valid'] for row in decision['branches']):
        raise AssertionError('EXPECTED_17_VALID_BRANCHES')
    return {'decision':decision,'branch_results':branch_results,'final_evidence':evidence,
            'branch_wall':total,'wall_s':wall,'live_before':before,'live_after':after}


def merge_using_frozen_controller(controller,state,proposals,by_index):
    evaluator=controller.evaluator
    expected_ids=[None]+[r['proposal_id'] for r in proposals['proposals']]
    if sorted(by_index)!=list(range(len(expected_ids))):
        raise AssertionError('MISSING_OR_DUPLICATE_BRANCH_RESULT')
    ordered=[by_index[i]['result'] for i in range(len(expected_ids))]
    if [r.proposal_id for r in ordered]!=expected_ids:
        raise AssertionError('COMPLETION_ORDER_AFFECTED_BRANCH_ORDER')
    by_id={r.proposal_id:r for r in ordered[1:]}
    with patch.object(evaluator,'evaluate_hold',lambda *a,**k:ordered[0]),\
         patch.object(evaluator,'evaluate_candidate',
                      lambda _forecast,record,_spec,**k:by_id[record['proposal_id']]):
        return controller.evaluate_root_actions(state,proposals,{})


def run_count(workers,assets,runner,state,proposals,reference):
    engine=runner.engine;controller=runner.controller
    before=engine.canonical_state_sha256()
    forecast=controller._forecast(state)
    forecast_hash=forecast.sha256()
    folder=ROOT/'data/raw/sgp4_x720'
    specs=controller._candidate_specs
    proc=psutil.Process()
    parent_peak=proc.memory_info().rss
    launched=time.perf_counter()
    with ParallelB4BranchPool(workers,folder) as pool:
        created=time.perf_counter()
        warm=pool.warm()
        startup=time.perf_counter()-launched
        pids=sorted({x['pid'] for x in warm})
        if len(pids)!=workers:raise AssertionError('WORKER_STARTUP_COUNT_MISMATCH')
        workers_proc={pid:psutil.Process(pid) for pid in pids}
        cpu_before={pid:sum(workers_proc[pid].cpu_times()[:2]) for pid in pids}
        root_start=time.perf_counter()
        root=encode_root(engine,pool.token)
        root_serial=time.perf_counter()-root_start
        physical_start=time.perf_counter()
        physical=pickle.dumps(assets.physical,protocol=pickle.HIGHEST_PROTOCOL)
        physical_serial=time.perf_counter()-physical_start
        records=(None,*proposals['proposals'])
        tasks=[BranchTask(i,root,physical,tuple(assets.fixed),'Z_MODERATE',
                 forecast,record,None if record is None else specs[record['proposal_id']],
                 before,forecast_hash) for i,record in enumerate(records)]
        payload_sizes=[len(pickle.dumps(task,protocol=pickle.HIGHEST_PROTOCOL)) for task in tasks]
        result_order=[];futures=[];dispatch_start=time.perf_counter()
        for i,task in enumerate(tasks):
            future=pool.submit(task)
            future.add_done_callback(lambda _future,index=i:result_order.append(index))
            futures.append(future)
        dispatch_s=time.perf_counter()-dispatch_start
        by_index={};result_bytes=[];decode_s=0.0;worker_encode_s=0.0
        # Canonical index order, regardless of callback completion order.
        for i,future in enumerate(futures):
            payload,encoded_elapsed,encoded_size=future.result()
            start=time.perf_counter()
            result=pickle.loads(payload)
            decode_s+=time.perf_counter()-start
            if encoded_size!=len(payload) or result['index']!=i:
                raise AssertionError('RESULT_TRANSPORT_CORRUPTION')
            result_bytes.append(encoded_size)
            worker_encode_s+=encoded_elapsed
            by_index[i]=result
            parent_peak=max(parent_peak,proc.memory_info().rss)
        completion=time.perf_counter()
        cpu_after={pid:sum(workers_proc[pid].cpu_times()[:2]) for pid in pids}
        final_rss={pid:workers_proc[pid].memory_info().rss for pid in pids}
        merge_start=time.perf_counter()
        decision=merge_using_frozen_controller(controller,state,proposals,by_index)
        merge_s=time.perf_counter()-merge_start
        total_wall=time.perf_counter()-root_start
    after=engine.canonical_state_sha256()
    if any(psutil.pid_exists(pid) for pid in pids):
        raise AssertionError('WORKER_PROCESS_LEAK_AFTER_POOL_SHUTDOWN')
    if after!=before or before!=reference['live_before']:
        raise AssertionError('PARALLEL_LIVE_MUTATION')
    branch_results=[asdict(by_index[i]['result']) for i in range(17)]
    evidence=[by_index[i]['evidence'] for i in range(17)]
    if branch_results!=reference['branch_results']:
        raise AssertionError('SCIENTIFIC_BRANCH_RESULT_MISMATCH')
    if evidence!=reference['final_evidence']:
        raise AssertionError('SCIENTIFIC_FINAL_STATE_OR_EVENT_MISMATCH')
    if decision!=reference['decision']:
        raise AssertionError('CONTROLLER_ORDER_OR_TIE_MISMATCH')
    compute=[by_index[i]['worker_compute_s'] for i in range(17)]
    cpu=sum(cpu_after[pid]-cpu_before[pid] for pid in pids)
    return {
      'workers':workers,'wall_s':total_wall,'pool_creation_s':created-launched,
      'worker_startup_s':startup,'root_serialization_s':root_serial,
      'physical_serialization_s':physical_serial,'task_dispatch_s':dispatch_s,
      'result_deserialization_s':decode_s,'result_serialization_s':worker_encode_s,
      'parent_merge_s':merge_s,'serialized_root_bytes':len(root),
      'physical_bytes':len(physical),'per_task_payload_bytes':payload_sizes,
      'per_result_payload_bytes':result_bytes,'completion_order':result_order,
      'worker_pids':pids,'worker_start_rss_bytes':warm,
      'worker_shutdown_clean':True,
      'worker_end_rss_bytes':final_rss,
      'worker_observed_peak_rss_bytes':max(max(x['rss_bytes'] for x in warm),
          *(by_index[i]['worker_rss_bytes'] for i in range(17))),
      'parent_observed_peak_rss_bytes':parent_peak,
      'worker_cpu_s':cpu,'cpu_utilization_fraction':cpu/(workers*total_wall),
      'worker_compute_total_s':sum(compute),'worker_idle_proxy_s':max(0.,workers*total_wall-sum(compute)),
      'branch_fastest_s':min(compute),'branch_slowest_s':max(compute),
      'branch_mean_s':statistics.mean(compute),
      'branch_load_imbalance_ratio':max(compute)/statistics.mean(compute),
      'branch_runtime':[{'index':i,'branch_id':by_index[i]['result'].branch_id,
         'worker_pid':by_index[i]['worker_pid'],
         'worker_decode_s':by_index[i]['worker_decode_s'],
         'worker_compute_s':by_index[i]['worker_compute_s'],
         'worker_rss_bytes':by_index[i]['worker_rss_bytes']} for i in range(17)],
      'decision':decision,'branch_results':branch_results,'final_evidence':evidence,
      'live_before':before,'live_after':after,'exact':True,
    }


def run_test_suite(out,name,args):
    env=dict(os.environ)
    env['PYTHONPATH']=str(ROOT/'src')+(os.pathsep+env['PYTHONPATH']
        if env.get('PYTHONPATH') else '')
    completed=subprocess.run([sys.executable,'-m','unittest',*args],
        cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    (out/name).write_text(completed.stdout,encoding='utf-8')
    if completed.returncode:
        raise AssertionError(f'{name}_FAIL_EXIT_{completed.returncode}')
    return {'command':['-m','unittest',*args],
            'exit_code':completed.returncode,'report_file':name}


def previous_attempt_hashes():
    old=ROOT/'outputs/b4_branch_multiprocessing_20261002T110603_454356Z'
    if not old.is_dir():
        raise AssertionError('PREVIOUS_FAIL_ATTEMPT_MISSING')
    return {str(p.relative_to(old)):sha(p) for p in old.rglob('*') if p.is_file()}


def validate_worker_liveness(out):
    folder=ROOT/'data/raw/sgp4_x720'
    rows=[]
    for count in (1,2,4,8):
        started=time.perf_counter()
        with ParallelB4BranchPool(count,folder) as pool:
            ready=pool.warm()
            pids=sorted({row['pid'] for row in ready})
            if len(pids)!=count:
                raise AssertionError('WORKER_CONCURRENT_OCCUPANCY_PID_MISMATCH')
        if any(psutil.pid_exists(pid) for pid in pids):
            raise AssertionError('WORKER_LIVENESS_PROCESS_LEAK')
        row={'workers':count,'status':'PASS','ready_count':len(ready),
             'unique_pids':pids,'simultaneously_occupied_before_release':True,
             'all_tasks_completed':True,'pool_shutdown_clean':True,
             'wall_s':time.perf_counter()-started}
        rows.append(row)
        save(out/'worker_liveness.json',{'status':'IN_PROGRESS','rows':rows})
        print(f'liveness {count} workers PASS',flush=True)
    result={'status':'PASS','rows':rows,'start_method':'spawn',
            'worker_function_picklable':True,'safe_main_guard':True,
            'recursive_spawn_observed':False,'orphan_process_observed':False}
    save(out/'worker_liveness.json',result)
    return result


def main():
    out=ROOT/'outputs'/('b4_branch_multiprocessing_retry_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir()
    status={'label':'ENGINEERING_PROFILE_ONLY','status':'RUNNING','run_id':'ENGINEERING_PROFILE_ONLY-B4-MULTIPROCESSING',
            'registered_P1_executed':False,'P2_started':False,'RL_started':False}
    save(out/'status.json',status)
    try:
        old_hashes=previous_attempt_hashes()
        focused=run_test_suite(out,'focused_tests.txt',
            ['-v','tests.test_b4_branch_multiprocessing'])
        regression=run_test_suite(out,'full_regression.txt',
            ['discover','-s','tests','-v'])
        save(out/'test_status.json',{'focused':focused,'full_regression':regression})
        pre,assets,runner,state,proposals=setup()
        save(out/'preflight.json',pre)
        liveness=validate_worker_liveness(out)
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'src/dynamic_lisl').glob('*.py')}
        config_hashes={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'configs').glob('*.json')}
        reference=serial_reference(runner.controller,state,proposals)
        save(out/'serial_reference.json',{'label':'ENGINEERING_PROFILE_ONLY',**reference})
        print(f"serial complete {reference['wall_s']:.3f}s",flush=True)
        rows=[]
        for workers in (1,2,4,8):
            row=run_count(workers,assets,runner,state,proposals,reference)
            rows.append(row)
            save(out/'worker_results.partial.json',rows)
            print(f"{workers} workers complete {row['wall_s']:.3f}s exact",flush=True)
        if any(sha(ROOT/k)!=v for k,v in {**source_hashes,**config_hashes}.items()):
            raise AssertionError('FROZEN_INPUT_CHANGED_DURING_GATE')
        if previous_attempt_hashes()!=old_hashes:
            raise AssertionError('PREVIOUS_FAIL_ATTEMPT_CHANGED')
        base=rows[0]['wall_s']
        scaling=[{'workers':r['workers'],'wall_s':r['wall_s'],
                  'speedup_vs_1worker':base/r['wall_s'],
                  'parallel_efficiency':base/(r['wall_s']*r['workers']),
                  'speedup_vs_serial':reference['wall_s']/r['wall_s'],
                  'exact':True,'rss_bytes':r['worker_observed_peak_rss_bytes']}
                 for r in rows]
        fastest=min(rows,key=lambda r:r['wall_s'])['workers']
        speedup=reference['wall_s']/min(r['wall_s'] for r in rows)
        next_step=('PRODUCTION_MULTIPROCESSING_INTEGRATION' if speedup>=1.5
                   else 'MULTIPROCESSING_NOT_SUFFICIENT')
        save(out/'equivalence_by_worker_count.json',{'label':'ENGINEERING_PROFILE_ONLY',
            'exact':True,'branch_count':17,'checks':[
                'all RolloutBranchResult fields','all final terminal/reservation/event states',
                'G_active/G_admit','Q/I/D/objective','outage/transition diagnostics',
                'controller decision/tie metadata','live before/after hash'],
            'workers':[{'workers':r['workers'],'exact':r['exact'],
                        'live_unchanged':r['live_before']==r['live_after'],
                        'completion_order':r['completion_order']} for r in rows]})
        save(out/'scaling_summary.json',{'label':'ENGINEERING_PROFILE_ONLY',
            'serial_production_wall_s':reference['wall_s'],'rows':scaling,
            'fastest_valid_worker_count':fastest,
            'NEXT_OPTIMIZATION_CANDIDATE':next_step})
        save(out/'branch_runtime_distribution.json',{'label':'ENGINEERING_PROFILE_ONLY',
            'serial':reference['branch_wall'],
            'workers':{str(r['workers']):r['branch_runtime'] for r in rows}})
        save(out/'memory_ipc_summary.json',{'label':'ENGINEERING_PROFILE_ONLY',
            'workers':[{k:r[k] for k in (
                'workers','pool_creation_s','worker_startup_s','root_serialization_s',
                'physical_serialization_s','task_dispatch_s','result_deserialization_s',
                'result_serialization_s','parent_merge_s','serialized_root_bytes',
                'per_task_payload_bytes','per_result_payload_bytes',
                'worker_observed_peak_rss_bytes','parent_observed_peak_rss_bytes',
                'worker_cpu_s','cpu_utilization_fraction','worker_idle_proxy_s')}
                for r in rows]})
        report={**status,'status':'B4_BRANCH_MULTIPROCESSING_GATE_PASS',
            'serial_wall_s':reference['wall_s'],'scaling':scaling,
            'worker_liveness':liveness,'focused_tests':focused,
            'full_regression':regression,'p1_preflight':'PASS',
            'previous_fail_attempt_preserved':True,
            'fastest_valid_worker_count':fastest,
            'NEXT_OPTIMIZATION_CANDIDATE':next_step,
            'scientific_exact_equivalence':True,'source_hashes':source_hashes,
            'config_hashes':config_hashes,'proposal_set_sha256':proposals['proposal_set_sha256'],
            'proposal_ids':[x['proposal_id'] for x in proposals['proposals']],
            'new_production_integration':False}
        save(out/'report.json',report)
        save(out/'status.json',report)
        print(json.dumps({'status':report['status'],'output':str(out),
                          'fastest':fastest,'speedup_vs_serial':speedup}),flush=True)
    except BaseException as exc:
        status.update(status='B4_BRANCH_MULTIPROCESSING_GATE_FAIL',
                      failure_type=type(exc).__name__,failure=str(exc),
                      traceback=traceback.format_exc())
        save(out/'report.json',status);save(out/'status.json',status)
        raise


if __name__=='__main__':
    main()
