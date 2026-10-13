"""Conditional complete physical catalog diagnosis, bounded at 300 seconds."""
import time,json,sys,traceback,os
from collections import Counter,defaultdict
from dataclasses import asdict
from contextlib import ExitStack
from unittest.mock import patch
import epoch_workflow as w
class CatalogDeadline(RuntimeError):pass
class Enumerate:
    def __init__(self,c):
        self.c=c;self.rows=[];self.parts=defaultdict(float);self.calls=Counter();self.stack=[]
        self.start=None;self.original=c.validator.validate;self.outputs=[]
    def wrap(self,category,fn):
        def invoke(*args,**kwargs):
            start=time.perf_counter();frame=[category,0.];self.stack.append(frame);self.calls[category]+=1
            try:return fn(*args,**kwargs)
            finally:
                elapsed=time.perf_counter()-start;self.stack.pop();self.parts[category]+=elapsed-frame[1]
                if self.stack:self.stack[-1][1]+=elapsed
        return invoke
    def validate(self,ex,action):
        if time.perf_counter()-self.start>=300.:raise CatalogDeadline('CATALOG_300S_SAFETY_LIMIT')
        start=time.perf_counter();verdict=self.original(ex,action)
        row=dict(index=len(self.rows)+1,action=asdict(action),action_key=w.action_key(action),
            accepted=verdict['accepted'],reason=verdict['reason'],mode=verdict.get('mode'),
            actual_immediate_release_ids=verdict.get('actual_immediate_release_ids'),
            release_refs=[asdict(x) for x in verdict.get('release_refs',())],wall_s=time.perf_counter()-start)
        self.rows.append(row);self.log.write(json.dumps(row,sort_keys=True)+'\n');self.log.flush()
        if len(self.rows)%100==0:
            print('CATALOG_VALIDATIONS '+str(len(self.rows)),flush=True)
            w.write(w.A/('CATALOG_PROGRESS_'+str(len(self.rows))+'.json'),dict(
                completed_validation_count=len(self.rows),wall_s=time.perf_counter()-self.start,
                completed_stage_exclusive_s=dict(self.parts),stage_calls=dict(self.calls),
                complete_legal_counts=None,coverage='PREFIX_ONLY'))
        if time.perf_counter()-self.start>=300.:raise CatalogDeadline('CATALOG_300S_SAFETY_LIMIT')
        return verdict
    def run(self):
        source=None;failure=None;before=w.causal_view(self.c);guard=self.c.validator.physical.guard
        with (w.A/'CATALOG_VALIDATION_PREFIX.jsonl').open('x',encoding='utf-8',newline='\n') as stream,ExitStack() as ctx:
            self.log=stream
            for obj,name,category in [(self.c.validator.physical.catalog,'terminal_pair_candidates','catalog_window_lookup'),
                (guard.model,'state','SGP4_native'),(guard,'evaluate','LOS_FOR'),
                (self.c.validator.physical,'evaluate','physical_window_bilateral'),
                (self.c,'_verify','binding_and_root_physical'),(self.c.source,'generate','proposal_and_validation_union')]:
                ctx.enter_context(patch.object(obj,name,self.wrap(category,getattr(obj,name))))
            ctx.enter_context(patch.object(self.c.validator,'validate',self.validate))
            self.start=time.perf_counter();w.write(w.A/'CATALOG_STARTED.json',dict(start_perf_counter=self.start,start_unix_s=time.time(),pid=os.getpid(),deadline_s=300.))
            try:source=self.c.candidates(w.SETUP,retention_budgets=None)
            except CatalogDeadline as exc:failure=str(exc)
            except Exception as exc:failure=dict(message=str(exc),traceback=traceback.format_exc())
            elapsed=time.perf_counter()-self.start
        assert before==w.causal_view(self.c),'ENUMERATION_ROOT_CHANGED'
        prefix_legal=Counter(r['action']['kind'] for r in self.rows if r['accepted'])
        considered=Counter(r['action']['kind'] for r in self.rows);reasons=Counter(r['reason'] or 'ACCEPTED' for r in self.rows)
        report=dict(status='COMPLETE_LEGAL_ENUMERATION' if source is not None else 'STOP_CATALOG_INCOMPLETE',
            wall_s=elapsed,safety_limit_s=300.,completed_validation_count=len(self.rows),
            completed_counts_by_kind=dict(considered),legal_in_completed_prefix=dict(prefix_legal),
            rejection_and_acceptance_reasons_in_prefix=dict(reasons),stage_exclusive_instrumented_s=dict(self.parts),
            stage_calls=dict(self.calls),instrumentation='instance-local timers, overhead included',
            full_legal_counts=source['diagnostics'] if source is not None else None,
            legal_set_precropped=False,retention_budget=None,candidate_sort='frozen action_key',
            root_unchanged=True,error=failure,global_epoch_executed=False,global_selected_action=None,memory=w.memory())
        w.write(w.A/'CATALOG_DIAGNOSIS.json',report)
        if source is not None:
            w.write(w.A/'CATALOG_COMPLETE_SOURCE.json',dict(candidates=[asdict(a) for a in source['candidates']],
                masks=[dict(action=asdict(x['action']),legal=x['legal'],reason=x['reason']) for x in source['masks']],
                diagnostics=source['diagnostics'],replacement_coverage=source['replacement_coverage']))
        return source
def main():
    assert w.vc.read_json(w.A/'SMALL_DOMAIN_ACCEPTANCE.json')['status']=='PASS'
    assert w.vc.read_json(w.A/'REGRESSION_ACCEPTANCE.json')['status']=='PASS_NO_NEW_FAILURES'
    live,built=w.load_live('CATALOG');lease,live,g,startup=w.open_lease(live)
    try:
        # Full catalog remains intact; only this clone receives timing wrappers.
        diagnostic=Enumerate(live.clone())
        original_windows=live.validator.physical.catalog.terminal_pair_candidates(3.,live.engine.executor.satellite_ids)
        w.write(w.A/'CATALOG_UNIVERSE.json',dict(registered_catalog_rows=2742,current_window_count=len(original_windows),
            original_rows_are_not_legal_action_count=True,live_root_build_s=built,reader_startup_s=startup))
        source=diagnostic.run()
        if source is None:print('STOP_CATALOG_INCOMPLETE',flush=True);return
        subset,domain=w.retain_small_domain(source)
        assert len(subset)<=7 and any(a.kind!='HOLD' for a in subset)
        w.write(w.A/'EPOCH_SUBSET.json',dict(actions=[asdict(a) for a in subset],coverage=domain,
            global_optimum_search_claimed=False,sorted_by='frozen retain_small_domain + action_key'))
        start=time.perf_counter();epochs={}
        for mode in ('ZERO','PERSIST'):
            mode_start=time.perf_counter();fc=w.ForecastInput.from_current(w.causal_view(live).observation,T_s=30.,H_s=6.,mode=mode)
            root=w.make_sanitized_root(live,fc,binding=g);root.verify_isolation();rows=[]
            for index,a in enumerate(subset):
                print('EPOCH '+mode+' '+a.kind+' '+getattr(a,'mode',''),flush=True)
                result=w.score(root,a);w.write(w.A/'epoch'/mode/(str(index+1).zfill(2)+'.json'),result);rows.append(result)
                if result['error']:raise RuntimeError('EPOCH_BRANCH_FAILED:'+str(result['error']))
            epochs[mode]=dict(decision=w.select_success(rows),branch_count=len(rows),branches=rows,
                scoring_and_sanitization_wall_s=time.perf_counter()-mode_start,forecast_sha256=fc.sha256,
                root_sha256=root.view.state_sha256)
        w.write(w.A/'SINGLE_EPOCH_ACCEPTANCE.json',dict(status='PASS_SINGLE_T3_EPOCH_ZERO_PERSIST',modes=epochs,
            enumeration_wall_s=w.vc.read_json(w.A/'CATALOG_DIAGNOSIS.json')['wall_s'],
            scoring_wall_s=time.perf_counter()-start,reader_startup_s=startup,root_build_s=built,
            safety_limit_is_not_scientific_controller_deadline=True,three_second_realtime_guaranteed=False,
            memory=w.memory(),full_pilot_executed=False,scientific_gate_pass=False))
        print('SINGLE_EPOCH_PASS',flush=True)
    finally:lease.__exit__(None,None,None)
if __name__=='__main__':main()
