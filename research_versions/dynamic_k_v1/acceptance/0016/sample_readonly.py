"""Finite read-only stack sampling; no process memory/state modification."""
import subprocess,time,json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
A=Path(__file__).resolve().parent
def main():
    pid=int(sys.argv[1]);label=sys.argv[2]
    exe=A/'readonly_diagnostic_tool/py-spy.exe';start=time.perf_counter()
    args=[str(exe),'dump','--pid',str(pid),'--locals']
    r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',timeout=30)
    p=A/('BBM_STACK_'+label+'.json')
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(dict(
        captured_utc=datetime.now(timezone.utc).isoformat(),command=args,exit_code=r.returncode,
        actual_wall_s=time.perf_counter()-start,raw_output=r.stdout,
        sampler_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        method='External read-only CPython frame sampling, no code injected',
        interpretation_limit='A stack sample is not a complete native checkpoint or accepted score'),f,indent=2,sort_keys=True)
    print(r.stdout,flush=True)
if __name__=='__main__':main()
