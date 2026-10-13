"""Exactly one standalone branch + one full-catalog decision epoch, serial."""
import sys,time,ctypes,json
from dataclasses import asdict
from pathlib import Path
from runtime.n4_p0 import (ForecastInput,PilotCost,make_sanitized_root,score_action,
    score_candidates,retain_small_domain,causal_view)
from runtime.n2_actions import Hold,Setup
from dynamic_lisl.commodity import Commodity
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace,TrafficSegment
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect
from runtime.n1b_observer import ObservedD2Engine


def memory():
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(x,ctypes.c_size_t) for x in
            ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
             'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]
    k=ctypes.windll.kernel32;k.GetCurrentProcess.restype=ctypes.c_void_p
    f=ctypes.windll.psapi.GetProcessMemoryInfo;f.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
    c=Counters();c.cb=ctypes.sizeof(c);assert f(k.GetCurrentProcess(),ctypes.byref(c),c.cb)
    return dict(process_peak_working_set_bytes=c.PeakWorkingSetSize,working_set_bytes=c.WorkingSetSize,
                process_peak_commit_bytes=c.PeakPagefileUsage,private_bytes=c.PrivateUsage,
                scope='WINDOWS_PROCESS_LIFETIME_HIGH_WATER_INCLUDES_FIXTURE_BUILD_NO_RESET')


class TimedPhase:
    """Exclusive union of classified Python calls; timing includes profiling cost."""
    def __init__(self):self.parts={};self.stack=[];self.last=0.;self.calls={}
    def category(self,frame):
        file=frame.f_code.co_filename.replace('\\','/');name=frame.f_code.co_name
        if (name=='verify' and type(frame.f_locals.get('self')).__name__.endswith('Binding')) or name in ('_verify','_physical_digest','digest','data_hash','canonical_state_sha256','sha256','file_info','binding','raw_info'):
            return 'binding_and_hash'
        if file.endswith('/n1b_fifo.py'):return 'fifo_age'
        if file.endswith('/n1a.py') and type(frame.f_locals.get('self')).__name__=='TerminalEnergyLedger':return 'terminal_energy'
        if file.endswith('/transition_service_orchestrator.py'):return 'network_service'
        return None
    def add(self):
        now=time.perf_counter();key=self.stack[-1][1] if self.stack else 'other_stage_work'
        self.parts[key]=self.parts.get(key,0.)+now-self.last;self.last=now
    def callback(self,frame,event,arg):
        if event=='call':
            c=self.category(frame)
            if c:self.add();self.stack.append((frame,c));self.calls[c]=self.calls.get(c,0)+1
        elif event=='return' and self.stack and self.stack[-1][0] is frame:
            self.add();self.stack.pop()
    def run(self,operation):
        self.last=time.perf_counter();start=self.last;sys.setprofile(self.callback)
        try:value=operation()
        finally:sys.setprofile(None);self.add()
        return value,dict(wallclock_s=time.perf_counter()-start,exclusive_classified_s=self.parts,
                          classified_calls=self.calls,instrumentation='sys.setprofile_serial_inclusive_overhead',memory=memory())


def run(guard):
    from workflow import A,fixtures,write
    # All correctness regressions must precede measurement. Known old F3 is separate.
    reports=[A/p for p in ('regression_N1a.json','regression_N1b.json','regression_N2.json','regression_N3.json')]
    assert all(json.loads(p.read_text(encoding='utf-8'))['status']=='PASS' for p in reports)
    assert any(json.loads(p.read_text(encoding='utf-8'))['status']=='PASS' for p in A.glob('attempt*/p0_tests.json'))
    f=fixtures();template,rows=f.real_fixture(full_catalog=True)
    nodes=template.engine.nodes;ex=TerminalExecutor(nodes)
    # Initial-condition constructor used by existing engineering fixtures; actual
    # ACTIVE at t0 is captured before accounting, no prehistory/setup energy.
    ex.submit([Connect(('X0_1','D2'),('X1_1','D1'),600.,0.,0.,0.)])
    trace=PiecewiseConstantTrafficTrace(('f_bg','f_hot'),[
        TrafficSegment(0.,8.,{'f_bg':200000.,'f_hot':400000.},'CURRENT'),
        TrafficSegment(8.,20.,{'f_bg':200000.,'f_hot':1200000.},'REAL_FUTURE_NOT_EXPOSED')])
    engine=ObservedD2Engine(nodes,template.engine.fixed_edges,1e6,
        [Commodity('f_bg','X0_1','X1_1'),Commodity('f_hot','X0_10','X1_10')],trace,template.engine.delay,ex)
    live=f.wrap(engine,template.validator.physical,30.);live.advance_to(3.)
    setup=Setup(.5,.5,.5);cost=PilotCost(6.,1000.);before=causal_view(live);baseline_memory=memory()
    forecast=ForecastInput.from_current(before.observation,T_s=30.,H_s=6.,mode='PERSIST')
    print('COST_STANDALONE_BRANCH_START',flush=True)
    r,clone_time=TimedPhase().run(lambda:make_sanitized_root(live,forecast,binding=guard))
    single,branch_time=TimedPhase().run(lambda:score_action(r,Hold(),cost,cadence_s=3.))
    write(A/'standalone_branch_cost.json',dict(scope='PILOT_ONLY_N4_P0_COST',clone=clone_time,branch=branch_time,
        baseline_memory=baseline_memory,result=single,scientific_gate_pass=False))
    print('COST_COMPLETE_CATALOG_EPOCH_START',flush=True);total_start=time.perf_counter()
    source,candidate_time=TimedPhase().run(lambda:live.candidates(setup))
    subset,domain_audit=retain_small_domain(source)
    require_nonhold=any(a.kind!='HOLD' for a in subset);assert require_nonhold
    epoch_root,sanitize_time=TimedPhase().run(lambda:make_sanitized_root(live,forecast,binding=guard))
    decision,score_time=TimedPhase().run(lambda:score_candidates(epoch_root,subset,cost,cadence_s=3.))
    elapsed=time.perf_counter()-total_start
    assert before==causal_view(live),'COST_MUTATED_REAL_ROOT'
    report=dict(scope='PILOT_ONLY_N4_P0_ONE_EPOCH_COST',time_s=3.,decision_cadence_s=3.,
        registered_catalog_rows=len(rows),candidate_enumeration=candidate_time,sanitized_root=sanitize_time,
        scoring=score_time,total_decision_wallclock_s=elapsed,peak_memory=memory(),baseline_memory=baseline_memory,
        n2_full_diagnostics=source['diagnostics'],replacement_coverage=source['replacement_coverage'],
        unique_proposed_count=len(source['masks']),domain_audit=domain_audit,
        all_masks=[dict(action=asdict(x['action']),legal=x['legal'],reason=x['reason']) for x in source['masks']],
        selected_subset=[asdict(a) for a in subset],decision=decision,
        branch_count=len(decision['branches']),branch_seconds=sum(x['effective_horizon_s'] for x in decision['branches'] if x['accepted']),
        event_count=sum(x.get('terminal_event_count',0) for x in decision['branches']),
        service_observation_count=sum(x.get('service_observation_count',0) for x in decision['branches']),
        ending_cohort_count_sum=sum(x.get('cohort_count',0) for x in decision['branches']),
        meets_three_second_decision_budget=elapsed<=3.,frozen_verification_disabled=False,simulation_workers=1,
        full_pilot_runs_executed=0,sensitivity_runs_executed=0,scientific_gate_pass=False)
    write(A/'one_epoch_cost.json',report)
    print(json.dumps({k:v for k,v in report.items() if k in ('total_decision_wallclock_s','branch_count','branch_seconds','peak_memory','meets_three_second_decision_budget')}),flush=True)
    return 0
