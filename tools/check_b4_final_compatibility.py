"""Ordered engineering-only compatibility acceptance; never launches P1."""
from pathlib import Path
from datetime import datetime, timezone
import os
import subprocess
import sys
import traceback
import seal_b4_production_multiprocessing as seal

ROOT=seal.ROOT

def main():
    out=ROOT/'outputs'/('b4_final_compatibility_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir()
    seal.OUT=out
    history=[p for p in (ROOT/'outputs').iterdir() if p.is_dir() and p!=out and
             p.name.startswith(('b4_production_multiprocessing_','b4_final_compatibility_','b4_successor_bootstrap_'))]
    before={str(p.relative_to(ROOT)):seal.tree(p) for p in history}
    seal.write(out/'historical_hashes_before.json',before)
    print(str(out),flush=True)
    try:
        # Per-file controller evidence is already PASS; this is NOT final registration.
        candidate=seal.read(ROOT/'outputs/b4_production_multiprocessing_20261002T124551_332297Z/production_runtime_candidate.json')
        candidate['bookkeeping_code_hashes']={n:seal.sha(ROOT/n) for n in candidate['bookkeeping_code_hashes']}
        branch='outputs/b4_branch_multiprocessing_retry_20261002T114610_676786Z/report.json'
        candidate['branch_equivalence_evidence']={'report':branch,'report_sha256':seal.sha(ROOT/branch)}
        candidate=seal.freeze(candidate)
        path=out/'controller_only_pretest_candidate.json'
        seal.write(path,candidate)
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT/'tools'),
                 B4_ENGINEERING_RUNTIME_CANDIDATE=str(path))
        results=[]
        for name,module in (
            ('runtime_chain','tests.test_runtime_successor_chain'),
            ('checkpoint','tests.test_b4_checkpoint_alignment'),
            ('telemetry','tests.test_gate_f3_runtime_telemetry'),
            ('evidence_persistence','tests.test_gate_f3_p1_evidence_persistence'),
            ('multiprocessing','tests.test_b4_branch_multiprocessing')):
            result=seal.suite(name+'.txt',['-v',module],env)
            results.append({'stage':name,**result})
            seal.write(out/'pretests.json',results)
            print(name+' PASS',flush=True)
        # New state-chain run, no reuse of historical metrics.
        for script in ('check_b4_production_multiprocessing_integration.py',
                       'seal_b4_production_multiprocessing.py'):
            subprocess.run([sys.executable,str(ROOT/'tools'/script),
                '--output',str(out/'multi_epoch')],cwd=ROOT,check=True)
        assert before=={str(p.relative_to(ROOT)):seal.tree(p) for p in history}
        from runtime_successor_chain import validate_runtime_chain,EXECUTOR
        verified=validate_runtime_chain(ROOT,EXECUTOR,
            'f879ea45dd006769108c32205ed111c53f5f2a3c83e7098bdbf0220415b73a44',seal.sha(ROOT/EXECUTOR))
        assert verified['pass'],verified
        seal.write(out/'authorized_successor_chain_verification.json',verified)
        seal.write(out/'report.json',{'status':'B4_FINAL_ACCEPTANCE_COMPATIBILITY_PASS',
            'historical_evidence_unchanged':True,'registered_P1_executed':False,
            'P2_started':False,'RL_started':False})
    except BaseException as exc:
        seal.write(out/'report.json',{'status':'B4_FINAL_ACCEPTANCE_COMPATIBILITY_FAIL',
            'failure':str(exc),'traceback':traceback.format_exc(),
            'historical_evidence_unchanged':before=={str(p.relative_to(ROOT)):seal.tree(p) for p in history},
            'registered_P1_executed':False,'P2_started':False,'RL_started':False})
        raise

if __name__=='__main__':main()
