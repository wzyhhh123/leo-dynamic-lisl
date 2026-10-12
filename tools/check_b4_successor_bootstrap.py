"""Independent engineering validation, explicit hash-only classification, then authorization."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import os
import subprocess
import sys
import re
import traceback
import seal_b4_production_multiprocessing as seal

ROOT=seal.ROOT
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]

def main():
    out=ROOT/'outputs'/('b4_successor_bootstrap_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir();seal.OUT=out
    print(out,flush=True)
    history=[p for p in (ROOT/'outputs').iterdir() if p.is_dir() and
             p!=out and p.name.startswith(('b4_production_multiprocessing_','b4_final_compatibility_','b4_successor_bootstrap_'))]
    before={str(p.relative_to(ROOT)):seal.tree(p) for p in history}
    seal.write(out/'history_before.json',before)
    try:
        name='src/dynamic_lisl/gate_f3_p1_execution.py'
        previous=ROOT/'outputs/b4_production_multiprocessing_20261002T124551_332297Z'
        old=seal.read(previous/'report.json')['source_hashes'][name.replace('/','\\')]
        new=seal.sha(ROOT/name)
        data=(ROOT/name).read_bytes()
        new_text=b'        sink = getattr(self, "_checkpoint_sink", None)\n        if sink is not None:\n            sink({'
        old_text=b'        if self._checkpoint_sink is not None:\n            self._checkpoint_sink({'
        if b'\r\n' in data:new_text=new_text.replace(b'\n',b'\r\n');old_text=old_text.replace(b'\n',b'\r\n')
        assert data.count(new_text)==1 and hashlib.sha256(data.replace(new_text,old_text)).hexdigest()==old
        candidate=seal.read(previous/'production_runtime_candidate.json')
        candidate['bookkeeping_code_hashes']={n:seal.sha(ROOT/n) for n in candidate['bookkeeping_code_hashes']}
        branch='outputs/b4_branch_multiprocessing_retry_20261002T114610_676786Z/report.json'
        candidate['branch_equivalence_evidence']={'report':branch,'report_sha256':seal.sha(ROOT/branch)}
        path=out/'pretest_candidate.json';seal.write(path,seal.freeze(candidate))
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT/'tools'),B4_ENGINEERING_RUNTIME_CANDIDATE=str(path))
        tests=[]
        for label,modules in (
            ('checkpoint',['tests.test_b4_checkpoint_alignment']),
            ('telemetry_exact',['tests.test_gate_f3_runtime_telemetry.GateF3PassiveProgressTests.test_progress_on_off_scientific_equivalence_and_call_counts']),
            ('multiprocessing',['tests.test_b4_branch_multiprocessing'])):
            tests.append(seal.suite(label+'.txt',['-v',*modules],env));print(label+' PASS',flush=True)
        subprocess.run([sys.executable,str(ROOT/'tools/check_b4_production_multiprocessing_integration.py'),'--output',str(out/'multi_epoch')],cwd=ROOT,env=env,check=True)
        os.environ['B4_ENGINEERING_RUNTIME_CANDIDATE']=str(path)
        command=[sys.executable,'-m','unittest','discover','-s','tests','-v']
        result=subprocess.run(command,cwd=ROOT,env=env,text=True,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        seal.write(out/'candidate_full_invocation.json',{
            'command':command,'cwd':str(ROOT),'stdout':result.stdout,
            'stderr':result.stderr,'returncode':result.returncode})
        combined=result.stdout+'\n'+result.stderr
        (out/'candidate_full_tests.txt').write_text(combined,encoding='utf-8')
        # Preserve the nonzero exit code. Only exact legacy assertion tracebacks
        # may continue under the explicitly authorized bootstrap exception.
        failures=[]
        blocks=re.findall(r'^={70}\n((?:FAIL|ERROR): .*?)(?=^={70}\n|^-{70}\nRan \d+ tests?)',combined,re.M|re.S)
        for block in blocks:
            test=block.splitlines()[0]
            tb=block.split('Traceback (most recent call last):',1)[-1].strip()
            legacy=('b4_runtime_seal.py' in tb and
                    'assert (report_sources[name]==expected==actual or' in tb and
                    tb.rstrip().endswith('AssertionError'))
            failures.append({'test':test,'classification':'LEGACY_HASH_EXPECTATION' if legacy else 'SCIENTIFIC_OR_OTHER_FAILURE','traceback':tb})
        count=re.search(r'^Ran (\d+) tests? in ',combined,re.M)
        summary=re.search(r'^FAILED \(([^\n]+)\)',combined,re.M)
        reported=sum(int(v) for v in re.findall(r'(?:failures|errors)=(\d+)',summary.group(1))) if summary else 0
        skipped=re.findall(r'^.*(?:\.\.\. skipped |skipped=\d+).*$',combined,re.M)
        legacy_only=(result.returncode==1 and summary is not None and
                     reported==len(failures)>0 and
                     all(x['classification']=='LEGACY_HASH_EXPECTATION' for x in failures))
        clean=(result.returncode==0 and not failures and re.search(r'^OK\s*$',combined,re.M) is not None)
        classified={'tests_run':int(count.group(1)) if count else 0,
                    'returncode':result.returncode,'failures':failures,'skipped':skipped,
                    'legacy_only_bootstrap_exception':legacy_only,
                    'scientific_tests_pass':bool(count and (clean or legacy_only) and not skipped and 'unexpected success' not in combined.lower())}
        seal.write(out/'candidate_test_classification.json',classified)
        assert classified['scientific_tests_pass'], 'CANONICAL_FULL_REGRESSION_FAILURE'
        assert before=={str(p.relative_to(ROOT)):seal.tree(p) for p in history}
        support=[out/'candidate_full_invocation.json',out/'candidate_full_tests.txt',out/'candidate_test_classification.json',out/'multi_epoch/report.json']+[out/x for x in ('checkpoint.txt','telemetry_exact.txt','multiprocessing.txt')]
        doc={'status':'CANDIDATE_SUCCESSOR_VALIDATED','file':name,'H_old':old,'H_new':new,
             'change_reason':'optional checkpoint compatibility only',
             'exact_code_diff_summary':{'old':old_text.decode(),'new':new_text.decode(),'inverse_patch_historical_hash_exact':True},
             'scientific_semantics_unchanged':True,'previous_FAIL_attempts_preserved':True,
             'supporting_test_results':tests,'telemetry_equivalence':'PASS',
             'multi_epoch_report':str((out/'multi_epoch/report.json').relative_to(ROOT)),
             'supporting_evidence':[{'report':str(p.relative_to(ROOT)),'report_sha256':seal.sha(p)} for p in support],
             'registered_P1_executed':False,'P2_started':False,'RL_started':False}
        evidence=out/'candidate_runtime_successor.json';seal.write(evidence,doc)
        registry=ROOT/'configs/b4_executor_compatibility_successor_v1.json'
        assert not registry.exists()
        seal.write(registry,seal.freeze({'status':'AUTHORIZED_RUNTIME_SUCCESSOR','file':name,
            'parent_hash':old,'successor_hash':new,'authorization_gate':'B4_RUNTIME_SUCCESSOR_BOOTSTRAP',
            'semantic_classification':'runtime/instrumentation compatibility successor',
            'evidence':{'report':str(evidence.relative_to(ROOT)),'report_sha256':seal.sha(evidence)}}))
        print('CANDIDATE_SUCCESSOR_VALIDATED; authorization registered',flush=True)
        subprocess.run([sys.executable,str(ROOT/'tools/check_b4_final_compatibility.py')],cwd=ROOT,check=True)
        seal.write(out/'report.json',{'status':'B4_RUNTIME_SUCCESSOR_BOOTSTRAP_PASS','registered_P1_executed':False})
    except BaseException as exc:
        seal.write(out/'report.json',{'status':'B4_RUNTIME_SUCCESSOR_BOOTSTRAP_FAIL','failure':str(exc),'traceback':traceback.format_exc(),'registered_P1_executed':False})
        raise

if __name__=='__main__':main()
