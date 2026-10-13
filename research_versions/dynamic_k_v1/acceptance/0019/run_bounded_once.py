"""Independent process hard watchdog: ONLY one child launch, 60s total budget."""
import json
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime,timezone

A=Path(__file__).resolve().parent
def write(name,value):
    with (A/name).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')

def main():
    assert not (A/'WATCHDOG_STARTED.json').exists(),'NO_SECOND_DIAGNOSTIC_ATTEMPT_ALLOWED'
    start=time.monotonic();deadline=start+60
    write('WATCHDOG_STARTED.json',dict(kind='NEW_SYNTHETIC_READ_ONLY_DIAGNOSTIC_NOT_BBM_REPLAY',
        created_utc=datetime.now(timezone.utc).isoformat(),hard_limit_s=60,maximum_child_launches=1,
        executable=sys.executable,profiler_used=False))
    with (A/'child_stdout.log').open('x',encoding='utf-8') as out, (A/'child_stderr.log').open('x',encoding='utf-8') as err:
        child=subprocess.Popen([sys.executable,'-B',str(A/'diagnostic_child.py')],stdout=out,stderr=err,
                               cwd=str(A.parents[3]))
        timeout=False
        try: child.wait(timeout=max(0,deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            timeout=True;child.kill();child.wait()
    evidence=dict(status='STOP_60S_HARD_LIMIT' if timeout else ('COMPLETED' if child.returncode==0 else 'STOP_CHILD_ERROR'),
        child_pid=child.pid,child_exit_code=child.returncode,elapsed_wall_s=time.monotonic()-start,
        hard_deadline_relative_s=60,terminate_on_deadline=True,child_launch_count=1,
        measured_scope='WHOLE_CHILD_INCLUDING_IMPORT_AND_CONTROL_AND_COUNTER_CASES',
        no_full_BBM_or_MPC_execution=True)
    write('WATCHDOG_RESULT.json',evidence);print(json.dumps(evidence),flush=True)
    if child.returncode:raise SystemExit(2)

if __name__=='__main__':main()
