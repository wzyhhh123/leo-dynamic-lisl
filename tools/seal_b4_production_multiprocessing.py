"""Tests and runtime registration only. Never launches a registered P1 run."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import traceback
import argparse
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
OUT=None
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def canonical(doc):
    body=dict(doc);body.pop('canonical_sha256',None)
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def write(path,doc):
    path.write_text(json.dumps(doc,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def freeze(doc):return {**doc,'canonical_sha256':canonical(doc)}
def tree(path):return {str(p.relative_to(path)):sha(p) for p in path.rglob('*') if p.is_file()}


def suite(name,args,env):
    completed=subprocess.run([sys.executable,'-m','unittest',*args],cwd=ROOT,
        env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    path=OUT/name;path.write_text(completed.stdout,encoding='utf-8')
    if completed.returncode:
        raise AssertionError(f'{name}:TEST_FAILURE_EXIT_{completed.returncode}')
    matched=re.search(r'Ran (\d+) tests?',completed.stdout)
    if matched is None:raise AssertionError('TEST_COUNT_MISSING')
    return {'pass':True,'count':int(matched.group(1)),
            'report':str(path.relative_to(ROOT)).replace('\\','/'),
            'report_sha256':sha(path)}


def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    OUT=parser.parse_args().output.resolve()
    assert OUT.is_relative_to((ROOT/'outputs').resolve())
    assert not (OUT/'acceptance_report.json').exists(), 'REFUSE_REUSE_ACCEPTANCE_ATTEMPT'
    candidate_path=OUT/'production_runtime_candidate.json'
    old_fail=ROOT/'outputs/b4_production_multiprocessing_20261002T122028_592605Z'
    paused=ROOT/'outputs/b4_production_multiprocessing_20261002T123901_457830Z'
    previous_fail=ROOT/'outputs/b4_production_multiprocessing_20261002T124551_332297Z'
    compatibility_fail=ROOT/'outputs/b4_final_compatibility_20261002T141441_023441Z'
    history=(old_fail,paused,previous_fail,compatibility_fail)
    historical_before={str(p.relative_to(ROOT)):tree(p) for p in history}
    previous_env=os.environ.get('B4_ENGINEERING_RUNTIME_CANDIDATE')
    try:
        report=read(OUT/'report.json')
        assert report['status']=='MULTI_EPOCH_EXACT_EQUIVALENCE_PASS'
        chain_path='configs/gate_f3_b4_runtime_chain_v1.json'
        chain=read(ROOT/chain_path)
        clone=read(ROOT/'configs/gate_f3_b4_lightweight_clone_overlay_v1.json')
        reuse=read(ROOT/'configs/gate_f3_b4_decision_hash_reuse_overlay_v1.json')
        parents={
            'src/dynamic_lisl/gate_f3_p1_execution.py':clone['source_hashes']['src/dynamic_lisl/gate_f3_p1_execution.py'],
            'src/dynamic_lisl/rollout_controller.py':reuse['optimized_code_hashes']['src/dynamic_lisl/rollout_controller.py'],
        }
        hashes={name:sha(ROOT/name) for name in parents}
        reported={name.replace('\\','/'):value for name,value in report['source_hashes'].items()}
        assert all(reported[name]==value for name,value in hashes.items())
        bookkeeping={name:sha(ROOT/name) for name in (
            'src/dynamic_lisl/b4_runtime_seal.py',
            'src/dynamic_lisl/b4_branch_multiprocessing.py',
            'tools/run_gate_f3_p1_execution.py',
            'tools/runtime_successor_chain.py',
            'tools/check_b4_production_multiprocessing_integration.py')}
        candidate=freeze({
            'schema':'b4_production_multiprocessing_runtime_overlay_v1',
            'gate_id':'B4_FINAL_ACCEPTANCE_COMPATIBILITY_REPAIR',
            'date_utc':datetime.now(timezone.utc).isoformat(),
            'reason':'production B4 branch multiprocessing integration',
            'semantic_status':'exact-equivalent runtime successor',
            'status':'EQUIVALENCE_VALIDATED_PENDING_ACCEPTANCE',
            'parent_chain_canonical_sha256':chain['canonical_sha256'],
            'parent_chain_file_sha256':sha(ROOT/chain_path),
            'production_worker_count':8,'horizon_s':10,
            'decision_cadence_s':2,'top_k':16,
            'scope':'BRANCH_EXECUTION_SCHEDULING_AND_PASSIVE_CHECKPOINT_AUDIT_ONLY',
            'parent_code_hashes':parents,'optimized_code_hashes':hashes,
            'bookkeeping_code_hashes':bookkeeping,
            'frozen_scientific_semantics_changed':False,
            'registered_P1_executed':False,'P2_started':False,'RL_started':False,
            'equivalence_evidence':{
                'report':str((OUT/'report.json').relative_to(ROOT)).replace('\\','/'),
                'report_sha256':sha(OUT/'report.json')},
            'branch_equivalence_evidence':{
                'report':'outputs/b4_branch_multiprocessing_retry_20261002T114610_676786Z/report.json',
                'report_sha256':sha(ROOT/'outputs/b4_branch_multiprocessing_retry_20261002T114610_676786Z/report.json')},
            'authorized_executor_successor':{
                'registry':'configs/b4_executor_compatibility_successor_v1.json',
                'registry_sha256':sha(ROOT/'configs/b4_executor_compatibility_successor_v1.json'),
                'registration':read(ROOT/'configs/b4_executor_compatibility_successor_v1.json')},
        })
        write(candidate_path,candidate)
        env=dict(os.environ)
        env['PYTHONPATH']=str(ROOT/'src')+os.pathsep+str(ROOT/'tools')
        env['B4_ENGINEERING_RUNTIME_CANDIDATE']=str(candidate_path)
        focused=suite('focused_acceptance_tests.txt',['-v',
            'tests.test_runtime_successor_chain',
            'tests.test_b4_checkpoint_alignment','tests.test_b4_branch_multiprocessing',
            'tests.test_gate_f2_rollout','tests.test_gate_f3_runtime_phase1',
            'tests.test_gate_f3_runtime_phase2a','tests.test_gate_f3_runtime_phase2b1',
            'tests.test_gate_f3_runtime_phase2b2'],env)
        print(f'focused/multiprocessing/runtime {focused["count"]} PASS',flush=True)
        full=suite('full_acceptance_regression.txt',['discover','-s','tests','-v'],env)
        print(f'full repository regression {full["count"]} PASS',flush=True)
        os.environ['B4_ENGINEERING_RUNTIME_CANDIDATE']=str(candidate_path)
        from run_gate_f3_p1_execution import preflight
        pre=preflight()[0]
        write(OUT/'pre_registration_p1_preflight.json',pre)
        assert pre['pass'] is True, 'CANDIDATE_P1_PREFLIGHT_FAIL'
        from runtime_successor_chain import validate_runtime_chain, EXECUTOR
        successor=read(ROOT/'configs/b4_executor_compatibility_successor_v1.json')
        successor_check=validate_runtime_chain(ROOT,EXECUTOR,
            successor['parent_hash'],sha(ROOT/EXECUTOR))
        write(OUT/'authorized_successor_chain_verification.json',successor_check)
        assert successor_check['pass'], 'AUTHORIZED_SUCCESSOR_CHAIN_FAIL'
        acceptance={'status':'PRE_REGISTRATION_ACCEPTANCE_PASS',
            'focused_tests_pass':True,'full_regression_pass':True,
            'p1_preflight_pass':True,'focused':focused,'full_regression':full,
            'registered_P1_executed':False}
        write(OUT/'pre_registration_acceptance.json',acceptance)
        overlay=dict(candidate);overlay.pop('canonical_sha256')
        overlay['status']='PASS'
        overlay['successor_chain_verification']=successor_check
        overlay['full_regression_result']=full
        overlay['final_preflight_before_registration']={
            'pass':True,'report':str((OUT/'pre_registration_p1_preflight.json').relative_to(ROOT)),
            'report_sha256':sha(OUT/'pre_registration_p1_preflight.json')}
        overlay['acceptance_evidence']={
            'report':str((OUT/'pre_registration_acceptance.json').relative_to(ROOT)).replace('\\','/'),
            'report_sha256':sha(OUT/'pre_registration_acceptance.json')}
        overlay=freeze(overlay)
        overlay_name='configs/gate_f3_b4_production_multiprocessing_overlay_v1.json'
        registration_name='configs/gate_f3_b4_production_multiprocessing_registration_v1.json'
        if (ROOT/overlay_name).exists() or (ROOT/registration_name).exists():
            raise AssertionError('REFUSE_OVERWRITE_EXISTING_PRODUCTION_RUNTIME_REGISTRATION')
        write(ROOT/overlay_name,overlay)
        registration=freeze({'schema':'b4_production_runtime_registration_v1',
            'status':'FROZEN','parent_chain_canonical_sha256':chain['canonical_sha256'],
            'overlay':overlay_name,'overlay_sha256':sha(ROOT/overlay_name),
            'registered_P1_executed':False})
        write(ROOT/registration_name,registration)
        os.environ.pop('B4_ENGINEERING_RUNTIME_CANDIDATE',None)
        env.pop('B4_ENGINEERING_RUNTIME_CANDIDATE',None)
        seals=suite('registered_runtime_seal_tests.txt',['-v','tests.test_b4_runtime_seal'],env)
        final_pre=preflight()[0]
        write(OUT/'final_p1_preflight.json',final_pre)
        assert final_pre['pass'] is True, 'FINAL_P1_PREFLIGHT_FAIL'
        assert historical_before=={str(p.relative_to(ROOT)):tree(p) for p in history}
        final={
            'status':'B4_PRODUCTION_MULTIPROCESSING_INTEGRATION_PASS',
            'checkpoint_alignment':'PASS','multi_epoch_exact_equivalence':'PASS',
            'epochs_s':report['epochs_s'],'full_regression':full,'focused':focused,
            'registered_runtime_seal_tests':seals,'final_p1_preflight_pass':True,
            'previous_FAIL_attempt_preserved':True,'paused_attempt_preserved':True,
            'production_worker_count':8,'serial_reference_retained':True,
            'pool_created_once':True,'worker_shutdown_clean':True,
            'production_observe_speedup':report['production_observe_speedup'],
            'overlay':overlay_name,'overlay_canonical_sha256':overlay['canonical_sha256'],
            'registration_canonical_sha256':registration['canonical_sha256'],
            'registered_P1_executed':False,'P2_started':False,'RL_started':False}
        write(OUT/'acceptance_report.json',final)
        write(ROOT/'configs/gate_f3_b4_production_multiprocessing_status.json',final)
        epochs=read(OUT/'epoch_evidence.json')
        table=['| epoch / s | serial observe / s | 8-worker observe / s | speedup | exact |',
               '|---:|---:|---:|---:|---|']
        for row in epochs:
            s=row['serial_timing']['controller_observe_wall_s']
            p=row['parallel_timing']['controller_observe_wall_s']
            table.append(f'| {row["time_s"]:g} | {s:.3f} | {p:.3f} | {s/p:.2f}× | YES |')
        doc=f'''# Production B4 multiprocessing integration / checkpoint alignment

**B4_PRODUCTION_MULTIPROCESSING_INTEGRATION = PASS**。本次独立工程 attempt 为 `{OUT.relative_to(ROOT)}`，t=0/2/4/6/8/10 的完整 serial-vs-production-8-worker 验证全部精确通过。上一 FAIL 和暂停 attempt 原样保留，没有改判。

四种对应 checkpoint hashes 全部相等；每种模式内 H_decision_root = H_post_observe，分别匹配 controller 的 live-before/live-after。H_pre_call 只与另一模式的同名 checkpoint 比较。实际顺序见 `B4_PRODUCTION_MULTIPROCESSING_CHECKPOINT_AUDIT_CN.md`。

每 epoch 精确比较 raw/final IDs、order/hash、所有分支结果与证据、J_H、合法性及原因、Gate B、terminal/reservation/event versions、active/admit graph、Q/I/D、累积目标与诊断、action/proposal、tie metadata 和决策字典。POST_DECISION 到下一个 DECISION_ROOT 使用真实 network evolution；状态随时间变化，非重复初始快照。

生产官方 P1 runner 的 B4 构造参数为 8 workers；串行参考显式保留。persistent pool 在本 controller 生命周期内只创建一次，branch mutable scientific state 每 task 从当前根状态独立构造；退出后无遗留 worker。run 和 engineering-prefix 的 finally 路径关闭 pool。异常不会触发自动换候选或自动串行重试。

{chr(10).join(table)}

六个 epoch 总 observe 提速 **{report['production_observe_speedup']:.2f}×**。每 epoch candidate source、proposer、network advance、Gate B 和 epoch total 的原始 timing 见 `epoch_evidence.json`；此数值只针对本工程 prefix，不能当作整场 P1 的提速保证。

focused/multiprocessing/runtime tests **{focused['count']}/{focused['count']} PASS**；完整仓库回归 **{full['count']}/{full['count']} PASS**；正式 registration 路径 seal tests **{seals['count']}/{seals['count']} PASS**；最终 default P1 preflight **PASS**。测试阶段只使用 outputs 下的待验收候选 runtime 元数据，最终 preflight 使用正式的新 registration；旧 runtime chain 和旧 overlay 未修改。

新 overlay canonical SHA-256：`{overlay['canonical_sha256']}`。registered P1 executed=false，P2 started=false，RL started=false。到此停止，等待人工授权正式 P1。
'''
        (ROOT/'docs/B4_PRODUCTION_MULTIPROCESSING_INTEGRATION_RESULT_CN.md').write_text(doc,encoding='utf-8')
        print(json.dumps(final,ensure_ascii=False),flush=True)
    except BaseException as exc:
        write(OUT/'acceptance_report.json',{'status':'B4_PRODUCTION_MULTIPROCESSING_INTEGRATION_FAIL',
            'failure_type':type(exc).__name__,'failure':str(exc),'traceback':traceback.format_exc(),
            'registered_P1_executed':False,'P2_started':False,'RL_started':False})
        raise
    finally:
        if previous_env is None:os.environ.pop('B4_ENGINEERING_RUNTIME_CANDIDATE',None)
        else:os.environ['B4_ENGINEERING_RUNTIME_CANDIDATE']=previous_env


if __name__=='__main__':main()
