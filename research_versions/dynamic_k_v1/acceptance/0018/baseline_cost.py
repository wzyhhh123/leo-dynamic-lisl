"""Seven specified checks only; never enumerates catalog or scores forecasts."""
import time
import support18 as s
from stage_timer import Timer
def main():
    c=s.root('BASELINE');lease,c,g,startup=s.w.open_lease(c)
    try:
        ex=c.engine.executor;before=s.digest(dict(snapshot=ex.snapshot(),log=ex.log));rows=[]
        for name,action in s.actions(c):
            start=time.perf_counter();plain=c.validator.validate(ex,action);plain_s=time.perf_counter()-start
            timer=Timer(ex);instrumented,timings=timer.run(lambda:c.validator.validate(ex,action))
            assert s.verdict(plain)==s.verdict(instrumented),'BASELINE_TIMER_CHANGED_RESULT'
            assert before==s.digest(dict(snapshot=ex.snapshot(),log=ex.log))
            rows.append(dict(name=name,action=s.asdict(action),accepted=plain['accepted'],reason=plain['reason'],
                plain_wall_s=plain_s,instrumented=timings,exact_equal=True,
                root_scale=dict(dynamic_terminals=len(ex.terminals),history_records=len(ex.log),
                    historical_terminal_rows=sum(len(r['terminals']) for r in ex.log),
                    history_JSON_bytes=len(__import__('json').dumps(ex.log,sort_keys=True).encode()),
                    links=len(ex.links),reservations=len(ex.reservations),agenda=len(ex.events))))
        s.write('BASELINE_COST.json',dict(status='PASS_FINITE_BASELINE_DIAGNOSIS',rows=rows,
            specified_actions=7,validate_calls=14,full_catalog_enumerated=False,forecast_branches=0,reader_startup_s=startup))
        print('BASELINE_DIAGNOSIS_PASS',flush=True)
    finally:lease.__exit__(None,None,None)
if __name__=='__main__':main()
