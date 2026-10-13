"""300-second hard stop for enumeration, never truncating a legal universe."""
import json,subprocess,sys,time,os
from pathlib import Path
A=Path(__file__).resolve().parent
def write(name,data):
    with (A/name).open('x',encoding='utf-8') as f:json.dump(data,f,sort_keys=True,indent=2)
def main():
    assert json.loads((A/'SMALL_DOMAIN_ACCEPTANCE.json').read_text())['status']=='PASS'
    child=subprocess.Popen([sys.executable,'-B',str(A/'catalog_epoch.py')],env=dict(os.environ,PYTHONHASHSEED='1414'))
    start=None
    while child.poll() is None:
        marker=A/'CATALOG_STARTED.json'
        if start is None and marker.exists():
            try:start=json.loads(marker.read_text())['start_unix_s']
            except json.JSONDecodeError:pass
        if start is not None and time.time()-start>=300. and not (A/'CATALOG_DIAGNOSIS.json').exists():
            stopped=time.time();child.terminate();child.wait(timeout=10)
            rows=[]
            p=A/'CATALOG_VALIDATION_PREFIX.jsonl'
            if p.exists():
                for line in p.read_text().splitlines():
                    try:rows.append(json.loads(line))
                    except json.JSONDecodeError:break
            from collections import Counter
            write('CATALOG_HARD_STOP.json',dict(status='STOP_CATALOG_300S_HARD_LIMIT',pid=child.pid,
                started_unix_s=start,stopped_unix_s=stopped,elapsed_s=stopped-start,
                complete_legal_counts=None,completed_validation_count=len(rows),
                completed_prefix_by_kind=dict(Counter(x['action']['kind'] for x in rows)),
                legal_in_completed_prefix=dict(Counter(x['action']['kind'] for x in rows if x['accepted'])),
                reasons_in_completed_prefix=dict(Counter(x['reason'] or 'ACCEPTED' for x in rows)),
                full_epoch_executed=False,selected_action=None,indivisible_call_interrupted=True))
            print('STOP_CATALOG_300S_HARD_LIMIT',flush=True);return
        time.sleep(.1)
    write('CATALOG_WORKER_EXIT.json',dict(exit_code=child.returncode,pid=child.pid,
        epoch_completed=(A/'SINGLE_EPOCH_ACCEPTANCE.json').exists()))
    if child.returncode:raise SystemExit(child.returncode)
if __name__=='__main__':main()
