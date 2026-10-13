"""Observer profiler leaves object graphs and frozen methods unchanged."""
import sys,time
from collections import Counter,defaultdict
import epoch_workflow as w
class Observer:
    def __init__(self):self.stack=[];self.parts=defaultdict(float);self.calls=Counter();self.callbacks=0
    def category(self,f):
        name=f.f_code.co_name;file=w.Path(f.f_code.co_filename).name
        if name=='verify':return 'binding_validation'
        if file=='n1b_fifo.py' and name in ('consume','metrics'):return 'FIFO'
        if file=='n1a.py' and name in ('capture','metrics','measure'):return 'energy_and_measurement'
        if file=='n2_controller.py' and name=='submit':return 'N2_action_submission'
        if name=='advance_to' and file in ('n4_p0f_events.py','transition_service_orchestrator.py'):return 'network_event_clock'
        if name=='clone' and file=='n2_controller.py':return 'branch_clone'
        return None
    def hook(self,frame,event,arg):
        if event not in ('call','return'):return
        self.callbacks+=1
        if event=='call':
            category=self.category(frame)
            if category:self.stack.append([frame,category,time.perf_counter(),0.]);self.calls[category]+=1
        elif self.stack and self.stack[-1][0] is frame:
            _,category,start,child=self.stack.pop();elapsed=time.perf_counter()-start
            self.parts[category]+=elapsed-child
            if self.stack:self.stack[-1][3]+=elapsed
def main():
    results={m:w.vc.read_json(w.A/('SMALL_'+m+'_SUMMARY.json')) for m in ('PERSIST','ZERO')}
    for d in results.values():assert len(d['rows'])==5 and d['decision']==w.select_success(d['rows'])
    assert results['PERSIST']['root_sha256']==results['ZERO']['root_sha256']
    assert results['PERSIST']['prefix_sha256']==results['ZERO']['prefix_sha256']
    live,built=w.load_live('PROFILE');lease,live,g,startup=w.open_lease(live)
    try:
        fc=w.ForecastInput.from_current(w.causal_view(live).observation,T_s=30.,H_s=6.,mode='PERSIST')
        root=w.make_sanitized_root(live,fc,binding=g);before=w.causal_view(root.atomic)
        plain=w.score(root,w.Hold());observer=Observer();previous=sys.getprofile()
        try:
            sys.setprofile(observer.hook);profiled=w.score(root,w.Hold())
        finally:sys.setprofile(previous)
        old=next(r for r in results['PERSIST']['rows'] if r['result']['action']['kind']=='HOLD')
        exact=w.stable(plain['result'])==w.stable(profiled['result'])==w.stable(old['result'])
        w.write(w.A/'OBSERVER_PROFILE_TIMING_PAIR.json',dict(plain=plain,instrumented=profiled,
            exact_result_including_state_hash_equal=exact,stage_exclusive_s=dict(observer.parts),
            stage_calls=dict(observer.calls),profiler_callbacks=observer.callbacks,
            instrumentation='CPython thread profile observer; no object field or runtime method replacement'))
        assert plain['error'] is None and profiled['error'] is None and exact
        assert before==w.causal_view(root.atomic)
        w.write(w.A/'SMALL_DOMAIN_ACCEPTANCE.json',dict(status='PASS',per_mode_branches=5,modes=['ZERO','PERSIST'],
            same_root_view=True,same_history_prefix=True,all_costs_from_real_fixed_horizon_execution=True,
            full_catalog_domain_claimed=False,instrumentation_result_exact_equal=True,
            plain_HOLD_wall_s=plain['actual_wall_s'],instrumented_HOLD_wall_s=profiled['actual_wall_s'],
            observed_timer_overhead_s=profiled['actual_wall_s']-plain['actual_wall_s'],startup_s=startup,root_build_s=built,
            helper_errors_retained=['FrozenInstanceError','wrapper_state_hash_difference'],
            extra_successful_timing_branches=4,extra_failed_instrumentation_attempts=1,main_pilot_runs=0))
        print('SMALL_DOMAIN_PASS',flush=True)
    finally:lease.__exit__(None,None,None)
if __name__=='__main__':main()
