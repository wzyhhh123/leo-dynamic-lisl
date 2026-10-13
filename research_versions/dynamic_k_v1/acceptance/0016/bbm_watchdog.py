"""User-authorized wall-clock stop for this BBM branch only."""
import ctypes,datetime,json,subprocess,time
from pathlib import Path
A=Path(__file__).resolve().parent
PID=10368
previous=A/'small/PERSIST/03_HOLD_.json'
completed=A/'small/PERSIST/04_REPLACE_BBM.json'
start=previous.stat().st_mtime
deadline=start+1800.
def write(name,data):
    with (A/name).open('x',encoding='utf-8') as f:json.dump(data,f,indent=2,sort_keys=True)
def utc(t):return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat()
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
kernel.OpenProcess.restype=ctypes.c_void_p
kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
kernel.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint]
kernel.CloseHandle.argtypes=[ctypes.c_void_p]
handle=kernel.OpenProcess(0x100000|0x0001,False,PID)
if not handle:raise ctypes.WinError(ctypes.get_last_error())
write('BBM_WALL_LIMIT_AUTHORIZATION.json',dict(pid=PID,user_limit_s=1800,
    start_boundary_utc=utc(start),deadline_utc=utc(deadline),basis=str(previous),
    boundary_description='previous HOLD evidence write completed immediately before BBM; conservative lower bound, not exact branch-start timestamp',
    user_authorization='This branch cumulative 30 minutes unfinished then STOP and seal partial evidence',
    catalog_limit_s=300,catalog_not_started=True))
try:
    while time.time()<deadline:
        if completed.exists() or kernel.WaitForSingleObject(handle,0)==0:
            write('BBM_WATCHDOG_COMPLETED.json',dict(completed_file_exists=completed.exists(),utc=utc(time.time()),terminated=False));break
        print('BBM_WATCH remaining_s='+str(round(deadline-time.time(),1)),flush=True)
        time.sleep(min(30.,max(0.,deadline-time.time())))
    else:
        if completed.exists() or kernel.WaitForSingleObject(handle,0)==0:
            write('BBM_WATCHDOG_COMPLETED.json',dict(completed_file_exists=completed.exists(),utc=utc(time.time()),terminated=False))
        else:
            at=time.time();ok=bool(kernel.TerminateProcess(handle,124))
            if not ok:raise ctypes.WinError(ctypes.get_last_error())
            kernel.WaitForSingleObject(handle,10000)
            write('BBM_WALL_LIMIT_STOP.json',dict(status='STOP_BBM_WALL_CLOCK_LIMIT',pid=PID,
                limit_s=1800,elapsed_from_conservative_boundary_s=at-start,stop_utc=utc(at),
                terminated=True,bbm_complete_score=False,catalog_executed=False,epoch_executed=False,
                score=None,native_checkpoint_captured=False,previous_completed=['PERSIST/ADD','PERSIST/DROP','PERSIST/HOLD']))
            print('STOP_BBM_WALL_CLOCK_LIMIT',flush=True)
finally:kernel.CloseHandle(handle)
