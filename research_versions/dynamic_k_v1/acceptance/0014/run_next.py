"""Sequential clean replay gate, then at most one HOLD and one ADD branch."""
import os,sys,json,hashlib,subprocess,time
from pathlib import Path
A=Path(__file__).resolve().parent
def info(p):return dict(path=str(p),byte_count=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,value):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
def main():
    anchor=A/'independent_root_evidence_anchor.json'
    files=[p for p in (A/'ROOT_BASELINE').rglob('*') if p.is_file()]+[A/'replay_recipe.json']
    rows=[info(p) for p in sorted(files)];write(anchor,dict(schema='p0e_independent_root_artifact_anchor_v1',files=rows,
        scope='New scenario root, original 0011 anchor not used or replaced'))
    anchor_bytes=anchor.read_bytes()
    receipts=[]
    for command in ('rebuild','HOLD','ADD'):
        assert anchor.read_bytes()==anchor_bytes,'NEW_ROOT_ANCHOR_MODIFIED'
        assert all(info(Path(r['path']))==r for r in rows),'NEW_ROOT_EVIDENCE_MODIFIED'
        args=[sys.executable,'-B',str(A/'replay_worker.py'),command]
        start=time.perf_counter();r=subprocess.run(args,env=dict(os.environ,PYTHONHASHSEED='1414'),
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        receipt=dict(command=args,exit_code=r.returncode,output=r.stdout,wall_s=time.perf_counter()-start,
            isolated_new_process=True,hash_seed='1414',anchor_sha256=hashlib.sha256(anchor_bytes).hexdigest())
        write(A/('PROCESS_'+command+'.json'),receipt);receipts.append(receipt)
        print(command+' '+r.stdout,flush=True)
        if r.returncode:
            write(A/'CONTROL_STOP.json',dict(status='STOP_WORKER_FAILURE',command=command,
                receipt=receipt,completed_commands=[x['command'][-1] for x in receipts],reruns=0));return 1
        assert all(info(Path(x['path']))==x for x in rows),'ROOT_EVIDENCE_CHANGED_DURING_REPLAY'
        if command=='rebuild':
            v=json.loads((A/'CLEAN_REBUILD/reconstruction_validation.json').read_text())
            assert v['status']=='ROOT_RECONSTRUCTION_PASS'
        else:
            result=json.loads((A/command/'branch_result.json').read_text())
            if result['error']:
                write(A/'CONTROL_STOP.json',dict(status=result['status'],command=command,
                    completed_commands=[x['command'][-1] for x in receipts],reruns=0,
                    original_assertions_preserved=True));return 0
    write(A/'CONTROL_STOP.json',dict(status='TWO_AUTHORIZED_BRANCHES_COMPLETED',reruns=0,
        completed_commands=['rebuild','HOLD','ADD'],full_epoch_executed=False))
    return 0
if __name__=='__main__':sys.exit(main())
