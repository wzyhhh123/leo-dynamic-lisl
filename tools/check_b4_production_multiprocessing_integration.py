"""Engineering-only multi-epoch production B4 serial/8-worker comparison."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import psutil
import sys
import time
import traceback
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]

from dynamic_lisl.b4_branch_multiprocessing import branch_evidence
from dynamic_lisl.common import read_json
from dynamic_lisl.gate_e2_experiments import GateE2Assets
from dynamic_lisl.gate_f3_p1_execution import P1RunExecutor


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                               allow_nan=False), encoding='utf-8')


def digest(value):
    body=json.dumps(value,sort_keys=True,separators=(',',':'),
                    ensure_ascii=False,allow_nan=False).encode()
    return hashlib.sha256(body).hexdigest()


def live_state(engine):
    return {
        'time_s':float(engine.now),
        'canonical_state_sha256':engine.canonical_state_sha256(),
        'queue_bits':float(engine.queues.total()),
        'inflight_bits':float(engine.in_flight.total()),
        'delivered':dict(engine.delivered),
        'active_edges':engine.graph['active_edges'],
        'admit_edges':engine.graph['admit_edges'],
        'terminal':engine.executor.snapshot(),
    }


def one_epoch(runner, epoch, index, capture_serial, checkpoint_rows):
    branch_results=[]
    evidence=[]
    proposals=[]
    original_propose=runner.proposer.propose
    def capture_proposal(*args,**kwargs):
        result=original_propose(*args,**kwargs)
        proposals.append(result)
        return result
    original_finish=runner.controller.evaluator._finish
    checkpoint_start=len(checkpoint_rows)
    def capture_finish(*args,**kwargs):
        result=original_finish(*args,**kwargs)
        branch_results.append(asdict(result))
        evidence.append(branch_evidence(args[0]))
        return result
    with patch.object(runner.proposer,'propose',capture_proposal):
        if capture_serial:
            with patch.object(runner.controller.evaluator,'_finish',capture_finish):
                runner._decision(epoch,index)
        else:
            runner._decision(epoch,index)
    if len(proposals)!=1:
        raise AssertionError('ONE_PROPOSAL_SET_PER_EPOCH_REQUIRED')
    checkpoints=checkpoint_rows[checkpoint_start:]
    if [row['checkpoint'] for row in checkpoints] != [
            'H_pre_call','H_decision_root','H_post_observe','H_post_decision']:
        raise AssertionError('FOUR_CHECKPOINT_ORDER_MISMATCH')
    if not capture_serial:
        branch_results=[asdict(row) for row in runner.controller.last_parallel_branch_results]
        evidence=runner.controller.last_parallel_branch_evidence
    public={k:v for k,v in proposals[0].items() if k!='candidate_specs'}
    source_report=runner.source.last_report
    return {
        'proposal_set':public,
        'raw_source_report':source_report,
        'raw_candidate_ids':[row['proposal_id'] for row in source_report['selected_order']],
        'final_proposal_ids':[row['proposal_id'] for row in public['proposals']],
        'branch_results':branch_results,
        'branch_evidence':evidence,
        'decision':runner.controller.last_decision,
        'selected_action':runner.actions[-1]['selected_action'],
        'selected_proposal_id':runner.actions[-1]['selected_proposal_id'],
        'timing':runner.epoch_runtime_records[-1],
        'checkpoints':checkpoints,
        'after_decision':live_state(runner.engine),
    }


def compare_equal(left,right,label):
    if left!=right:
        raise AssertionError(f'MULTI_EPOCH_EXACT_MISMATCH:{label}')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    requested=parser.parse_args().output
    out=(requested or ROOT/'outputs'/('b4_production_multiprocessing_'+
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))).resolve()
    assert out.is_relative_to((ROOT/'outputs').resolve())
    out.mkdir()
    status={'schema':'b4_production_multiprocessing_integration_gate_v1',
            'status':'RUNNING','engineering_only':True,
            'registered_P1_executed':False,'P2_started':False,'RL_started':False}
    save(out/'status.json',status)
    serial=parallel=None
    try:
        assets=GateE2Assets()
        manifest=read_json(ROOT/'configs/gate_f3_execution_manifest_v1.json')
        frozen=next(row for row in manifest['runs'] if row['block_id']=='P1'
                    and row['controller']=='B4' and row['rho']==0.5)
        row={**frozen,'run_id':'ENGINEERING_PROFILE_ONLY-B4-PRODUCTION-MULTIEPOCH',
             'block_id':'ENGINEERING_PROFILE_ONLY'}
        serial_checkpoints=[];parallel_checkpoints=[]
        serial=P1RunExecutor(assets,row,b4_parallel_workers=0,
                             checkpoint_sink=serial_checkpoints.append)
        parallel=P1RunExecutor(assets,row,b4_parallel_workers=8,
                               checkpoint_sink=parallel_checkpoints.append)
        initial_serial=live_state(serial.engine)
        initial_parallel=live_state(parallel.engine)
        compare_equal(initial_serial,initial_parallel,'INITIAL_ROOT')
        rows=[];state_chain=[{'time_s':0.0,'state':initial_serial}]
        for index,epoch in enumerate((0.,2.,4.,6.,8.,10.)):
            before_s=live_state(serial.engine)
            before_p=live_state(parallel.engine)
            compare_equal(before_s,before_p,f'BEFORE_DECISION_{epoch}')
            s=one_epoch(serial,epoch,index,True,serial_checkpoints)
            p=one_epoch(parallel,epoch,index,False,parallel_checkpoints)
            for key in ('raw_source_report','raw_candidate_ids','final_proposal_ids',
                        'proposal_set','branch_results','branch_evidence',
                        'decision','selected_action','selected_proposal_id',
                        'checkpoints','after_decision'):
                compare_equal(s[key],p[key],f'{key}_{epoch}')
            for mode,observed,pre in (('SERIAL',s,before_s),
                                      ('PARALLEL',p,before_p)):
                cp={row['checkpoint']:row['canonical_state_sha256']
                    for row in observed['checkpoints']}
                if cp['H_pre_call']!=pre['canonical_state_sha256']:
                    raise AssertionError(f'{mode}_PRE_CALL_CHECKPOINT_MISMATCH')
                if cp['H_decision_root']!=observed['decision']['live_state_sha256_before']:
                    raise AssertionError(f'{mode}_DECISION_ROOT_CHECKPOINT_MISMATCH')
                if cp['H_post_observe']!=observed['decision']['live_state_sha256_after']:
                    raise AssertionError(f'{mode}_POST_OBSERVE_CHECKPOINT_MISMATCH')
                if cp['H_decision_root']!=cp['H_post_observe']:
                    raise AssertionError(f'{mode}_B4_ROLLOUT_MUTATED_LIVE_ROOT')
                if cp['H_post_decision']!=observed['after_decision']['canonical_state_sha256']:
                    raise AssertionError(f'{mode}_POST_DECISION_CHECKPOINT_MISMATCH')
            record={
                'time_s':epoch,'before_decision':before_s,
                'checkpoints':s['checkpoints'],
                'raw_candidate_ids':s['raw_candidate_ids'],
                'final_proposal_ids':s['final_proposal_ids'],
                'proposal_set_sha256':s['proposal_set']['proposal_set_sha256'],
                'branch_result_sha256':digest(s['branch_results']),
                'branch_evidence_sha256':digest(s['branch_evidence']),
                'branch_count':len(s['branch_results']),
                'decision':s['decision'],
                'after_decision':s['after_decision'],
                'serial_timing':s['timing'],'parallel_timing':p['timing'],
                'worker_pids':parallel.controller.last_parallel_worker_pids,
                'exact':True,
            }
            if record['branch_count']!=1+len(record['final_proposal_ids']):
                raise AssertionError('EPOCH_BRANCH_COUNT_MISMATCH')
            rows.append(record)
            save(out/'epoch_evidence.partial.json',rows)
            print(f'epoch {epoch:g}s exact; serial observe '
                  f'{s["timing"]["controller_observe_wall_s"]:.3f}s; 8w '
                  f'{p["timing"]["controller_observe_wall_s"]:.3f}s',flush=True)
            if epoch<10.:
                next_epoch=epoch+2.
                for runner in (serial,parallel):
                    started=time.perf_counter()
                    runner.engine.advance_to(next_epoch)
                    runner.engine.settle_current_time()
                    runner._pending_network_advance_wall_s=time.perf_counter()-started
                after_advance_s=live_state(serial.engine)
                after_advance_p=live_state(parallel.engine)
                compare_equal(after_advance_s,after_advance_p,
                              f'AFTER_ADVANCE_{next_epoch}')
                record['after_next_advance']=after_advance_s
                state_chain.append({'time_s':next_epoch,'state':after_advance_s})
                save(out/'epoch_evidence.partial.json',rows)
        if parallel.controller.parallel_pool_start_count!=1:
            raise AssertionError('POOL_NOT_PERSISTENT_ACROSS_EPOCHS')
        if len(parallel.controller.parallel_pool_pids)!=8:
            raise AssertionError('PRODUCTION_POOL_NOT_8_WORKERS')
        if len({row['state']['canonical_state_sha256'] for row in state_chain})<2:
            raise AssertionError('NO_NATURAL_STATE_EVOLUTION')
        if len({(row['state']['queue_bits'],row['state']['inflight_bits'],
                 tuple(sorted(row['state']['delivered'].items())))
                for row in state_chain})<2:
            raise AssertionError('NO_Q_I_D_EVOLUTION')
        pids=parallel.controller.parallel_pool_pids
        serial.close();parallel.close()
        if any(psutil.pid_exists(pid) for pid in pids):
            raise AssertionError('PRODUCTION_WORKER_ORPHAN_PROCESS')
        save(out/'epoch_evidence.json',rows)
        save(out/'state_chain.json',state_chain)
        serial_observe=sum(row['serial_timing']['controller_observe_wall_s'] for row in rows)
        parallel_observe=sum(row['parallel_timing']['controller_observe_wall_s'] for row in rows)
        report={**status,'status':'MULTI_EPOCH_EXACT_EQUIVALENCE_PASS',
                'epochs_s':[0,2,4,6,8,10],
                'all_epoch_branch_and_state_exact':True,
                'natural_state_evolution':True,
                'pool_created_once':True,'worker_pids':pids,
                'worker_shutdown_clean':True,
                'serial_observe_wall_s':serial_observe,
                'parallel_observe_wall_s':parallel_observe,
                'production_observe_speedup':serial_observe/parallel_observe,
                'final_state_sha256':state_chain[-1]['state']['canonical_state_sha256'],
                'source_hashes':{str(path.relative_to(ROOT)):
                    hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (ROOT/'src/dynamic_lisl').glob('*.py')}}
        save(out/'report.json',report);save(out/'status.json',report)
        print(json.dumps({'status':report['status'],'output':str(out),
            'observe_speedup':report['production_observe_speedup']}),flush=True)
    except BaseException as exc:
        status.update(status='MULTI_EPOCH_EXACT_EQUIVALENCE_FAIL',
                      failure_type=type(exc).__name__,failure=str(exc),
                      traceback=traceback.format_exc())
        save(out/'report.json',status);save(out/'status.json',status)
        raise
    finally:
        for runner in (serial,parallel):
            if runner is not None:
                runner.close()


if __name__=='__main__':
    main()
