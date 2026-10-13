"""Each diagnostic/test child has an independent 60-second hard deadline."""
import json,os,subprocess,sys,time
from pathlib import Path
A=Path(__file__).resolve().parent
def main():
    label,script,*args=sys.argv[1:]
    flag=A/(label+'_STARTED.json');result=A/(label+'_PROCESS.json')
    with flag.open('x',encoding='utf-8') as f:json.dump(dict(limit_s=60,script=script,args=args),f)
    start=time.monotonic();deadline=start+60
    env=dict(os.environ,PYTHONHASHSEED='1414')
    with (A/(label+'_stdout.log')).open('x',encoding='utf-8') as out,(A/(label+'_stderr.log')).open('x',encoding='utf-8') as err:
        p=subprocess.Popen([sys.executable,'-B',str(A/script),*args],stdout=out,stderr=err,cwd=str(A.parents[3]),env=env)
        timeout=False
        try:p.wait(timeout=max(0,deadline-time.monotonic()))
        except subprocess.TimeoutExpired:timeout=True;p.kill();p.wait()
    record=dict(status='STOP_60S_HARD_LIMIT' if timeout else ('COMPLETED' if p.returncode==0 else 'STOP_CHILD_ERROR'),
        pid=p.pid,exit_code=p.returncode,wall_s=time.monotonic()-start,hard_limit_s=60,child_launches=1,
        process_scope='INCLUDES_IMPORT_SETUP_VALIDATION_AND_OUTPUT',kill_at_deadline=True)
    with result.open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
    print(json.dumps(record),flush=True)
    raise SystemExit(0 if p.returncode==0 else 2)
if __name__=='__main__':main()
