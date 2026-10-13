"""Read-only static evidence accounting. No simulator/runtime imports."""
import ast,hashlib,json,math,statistics
from collections import Counter,defaultdict
from pathlib import Path
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1];OLD=V/'acceptance/0016'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(name,data):
    with (A/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(data,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def binding(p):
    p=Path(p);data=p.read_bytes();return dict(path=p.relative_to(P).as_posix(),byte_count=len(data),sha256=hashlib.sha256(data).hexdigest())
def source_functions(p):
    data=Path(p).read_bytes();tree=ast.parse(data);return dict(binding=binding(p),
        functions=[dict(name=n.name,line=n.lineno,end_line=n.end_lineno) for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))])
def summary(values):
    return dict(count=len(values),sum_s=math.fsum(values),min_s=min(values),max_s=max(values),
        median_s=statistics.median(values)) if values else dict(count=0,sum_s=0.)
def main():
    inputs=set();branches=[]
    for mode in ('PERSIST','ZERO'):
        for p in sorted((OLD/'small'/mode).glob('*.json')):
            inputs.add(p);d=read(p);r=d['result'];age=r['n2_result']['n1b_result']['age_accounting']
            audits=age['roundoff_audit']
            branches.append(dict(evidence=binding(p),mode=mode,action=r['action'],wall_s=d['actual_wall_s'],
                measured_timings=r['timings'],terminal_log_delta=r['terminal_event_count'],
                age_observation_record_delta=r['service_observation_count'],final_resident_cohort_and_stream_count=r['cohort_count'],
                closure_audit_entries=len(age['closure_audit']),roundoff_audit_entries=len(audits),
                roundoff_by_state=dict(Counter(x.get('state','ABSENT') for x in audits)),
                roundoff_by_boundary=dict(Counter(x.get('boundary','ABSENT') for x in audits)),
                unique_times_in_nonzero_roundoff_audit=len({x['time'] for x in audits if 'time' in x}),
                state_checks=d['state_checks'],memory=d['memory'],
                unrecorded=dict(actual_microstep_count=None,actual_INTERVAL_count=None,
                    total_Stream_created=None,total_Cohort_created=None,peak_resident_cohorts=None,
                    split_count=None,consume_count=None,sort_count=None,queue_update_count=None,FIFO_exclusive_wall_s=None)))
    p=OLD/'CATALOG_VALIDATION_PREFIX.jsonl';inputs.add(p)
    rows=[json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()]
    assert len(rows)==2598 and [x['index'] for x in rows]==list(range(1,2599))
    groups=defaultdict(list);pairs=Counter()
    for x in rows:
        groups[(x['action']['kind'],str(x['mode']),str(x['reason']))].append(x['wall_s'])
        if 'a' in x['action']:pairs[(tuple(x['action']['a']),tuple(x['action']['b']))]+=1
    stop=read(OLD/'CATALOG_HARD_STOP.json');inputs.add(OLD/'CATALOG_HARD_STOP.json')
    assert len(rows)==stop['completed_validation_count']
    prefix=dict(evidence=binding(p),completed_count=len(rows),accepted_count=sum(x['accepted'] for x in rows),
        by_kind=dict(Counter(x['action']['kind'] for x in rows)),
        accepted_by_kind=dict(Counter(x['action']['kind'] for x in rows if x['accepted'])),
        reasons=dict(Counter(x['reason'] or 'ACCEPTED' for x in rows)),
        groups=[dict(kind=k[0],mode=k[1],reason=k[2],timing=summary(v)) for k,v in sorted(groups.items())],
        total_finished_validate_wall_s=math.fsum(x['wall_s'] for x in rows),
        repeated_endpoint_pairs_in_prefix=sum(v>1 for v in pairs.values()),
        endpoint_pair_multiplicity_histogram=dict(Counter(pairs.values())),
        distinct_endpoint_pairs=len(pairs),complete_legal_count=None,full_coverage=False,
        candidate_trial_clone_actual_calls=None,candidate_deepcopy_actual_calls=None,
        candidate_snapshot_actual_calls=None,missing_result_for_interrupted_call=True)
    snapshots=[]
    for p in sorted(OLD.glob('CATALOG_PROGRESS_*.json'),key=lambda p:int(p.stem.split('_')[-1])):
        inputs.add(p);snapshots.append(dict(evidence=binding(p),data=read(p)))
    root=V/'acceptance/0015/ROOT_BASELINE/ROOT_FULL_STATE.json';inputs.add(root)
    root_types=Counter(x['type'] for x in read(root)['objects'] if x['type'].startswith('runtime.n1b_fifo.'))
    source_names=['runtime/n1b_fifo.py','runtime/n1b_evaluator.py','runtime/n1b_observer.py',
        'runtime/n2_actions.py','runtime/n2_candidates.py','runtime/n2_controller.py','runtime/n2_physical.py',
        'runtime/n4_p0.py','runtime/n4_p0f_events.py','runtime/n1a.py',
        'acceptance/0016/catalog_epoch.py','acceptance/0016/profile_timing_check.py',
        'acceptance/0016/epoch_workflow.py']
    source_paths=[V/x for x in source_names]+[P/'src/dynamic_lisl'/x for x in
        ['terminal_executor.py','terminal_pair_intervals.py','gate_c_simplified_feasibility.py',
         'gate_c_terminal_geometry.py','transition_service_orchestrator.py','sgp4_model.py']]
    for p in source_paths:inputs.add(p)
    for name in ['OBSERVER_PROFILE_TIMING_PAIR.json','SMALL_DOMAIN_ACCEPTANCE.json','ENV_AND_HELPER_AUDIT.json',
        'CATALOG_UNIVERSE.json','CATALOG_MEMORY_SNAPSHOT_01.json','REGRESSION_ACCEPTANCE.json',
        'BBM_STACK_02.json','BBM_STACK_03.json','manifest_final.json']:
        inputs.add(OLD/name)
    profile=read(OLD/'OBSERVER_PROFILE_TIMING_PAIR.json')
    frozen_sources=[source_functions(p) for p in source_paths]
    write('COST_EVIDENCE.json',dict(schema='dynamic_k_0017_static_cost_evidence_v1',
        status='STATIC_EVIDENCE_ACCOUNTING_ONLY',parent_sha256='8cb85f868c5177663b89222d9da7db66b48e10bec6a38a35b2f83701925ffea6',
        simulation_runs=0,branch_runs=0,catalog_validation_calls=0,branches=branches,catalog_prefix=prefix,
        catalog_progress=snapshots,initial_t3_FIFO_graph_type_counts=dict(root_types),
        profiler_scope='PERSIST HOLD only, FIFO category combines Cohort.consume, DeliveredAgeLedger.consume and metrics; not BBM profiler',
        HOLD_profiled_wall_s=profile['instrumented']['actual_wall_s'],HOLD_plain_wall_s=profile['plain']['actual_wall_s'],
        HOLD_profiler_callbacks=profile['profiler_callbacks'],HOLD_profiled_stage_calls=profile['stage_calls'],
        HOLD_profiled_stage_exclusive_s=profile['stage_exclusive_s'],
        precision='Recorded Python float timings; sums use math.fsum only for offline descriptive analysis, not simulator state',
        observation_limits='No BBM call counters or peak stream counts were sealed; resident final count is not lifetime allocation count; aggregate observation count is not microstep count; no full legal universe inferred'))
    write('SOURCE_CALL_SITES.json',dict(schema='dynamic_k_0017_static_source_sites_v1',sources=frozen_sources))
    write('AUDIT_INPUT_MANIFEST.json',dict(schema='dynamic_k_0017_static_audit_inputs_v1',files=[binding(p) for p in sorted(inputs)],
        no_runtime_modules_imported=True,no_scoring_or_candidate_enumeration_executed=True))
    print(json.dumps(dict(status='PASS_STATIC_ACCOUNTING',branches=len(branches),prefix=prefix,root_FIFO_types=dict(root_types)),indent=2))
if __name__=='__main__':main()
