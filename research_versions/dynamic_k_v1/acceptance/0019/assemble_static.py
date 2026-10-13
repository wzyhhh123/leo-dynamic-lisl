"""Read sealed evidence only. No simulator/runtime imports or re-execution."""
import ast
import hashlib
import json
from pathlib import Path

A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(name,value):
    with (A/name).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def binding(p):
    b=p.read_bytes();return dict(path=p.relative_to(P).as_posix(),byte_count=len(b),sha256=hashlib.sha256(b).hexdigest())
def main():
    names=[V/'runtime'/x for x in ('n1b_fifo.py','n1b_evaluator.py','n1a.py','n2_controller.py','n4_p0.py','n4_p0f_events.py')]
    names += [V/'acceptance/0017'/x for x in ('COST_EVIDENCE.json','STRUCTURAL_EVENT_COUNTS.json','SOURCE_CALL_SITES.json','AUDIT_INPUT_MANIFEST.json','SUPPLEMENTAL_INPUT_MANIFEST.json','FIFO_COST_ATTRIBUTION_CN.md','OPTION_1_EXACT_OPTIMIZATION_DESIGN_CN.md')]
    names += [V/'acceptance/0016'/x for x in ('BBM_STACK_02.json','BBM_STACK_03.json','OBSERVER_PROFILE_TIMING_PAIR.json','SMALL_DOMAIN_ACCEPTANCE.json','SMALL_PERSIST_SUMMARY.json','SMALL_ZERO_SUMMARY.json','epoch_workflow.py','profile_timing_check.py','BBM_WATCHDOG_COMPLETED.json')]
    names += sorted((V/'acceptance/0016/small').rglob('*.json'))
    names += [V/'acceptance/0015/ROOT_BASELINE/ROOT_FULL_STATE.json',V/'acceptance/0015/ROOT_BASELINE/root_binding.json']
    names += [V/'acceptance/0018'/x for x in ('manifest_final.json','RESULT_CN.md','acceptance_summary.json')]
    names += [V/'configs/n4_p0h_structural_seam_v1.json',V/'version_record.json']
    names += [V/'revisions'/('%04d'%i)/'record.json' for i in range(1,19)]
    names=sorted(set(names))
    write('AUDIT_INPUT_MANIFEST.json',dict(schema='dynamic_k_0019_static_diagnostic_inputs_v1',files=[binding(p) for p in names]))
    old=read(V/'acceptance/0017/COST_EVIDENCE.json');derived=read(V/'acceptance/0017/STRUCTURAL_EVENT_COUNTS.json')
    branches=[]
    for b in old['branches']:
        d=next(x for x in derived['rows'] if x['mode']==b['mode'] and x['action']==b['action'])
        branches.append(dict(mode=b['mode'],action=b['action'],measured_timings=b['measured_timings'],
            final_resident_count=b['final_resident_cohort_and_stream_count'],observation_records=b['age_observation_record_delta'],
            closure_records=b['closure_audit_entries'],roundoff_audit_entries=b['roundoff_audit_entries'],
            source_structurally_derived_counts=d,raw_evidence=b['evidence'],
            fifo_exclusive_wall_s=None,peak_active_streams=None,cumulative_cohort_allocations=None,cumulative_splits=None))
    progress=[json.loads(line) for line in (A/'DIAGNOSTIC_PROGRESS.jsonl').read_text(encoding='utf-8').splitlines()]
    completed=progress[-1];assert completed['status']=='PASS_DIAGNOSTIC_FIXTURES_ONLY'
    assert len(completed['rows'])==13 and read(A/'WATCHDOG_RESULT.json')['child_exit_code']==0
    functions=[]
    for p in names:
        if p.suffix!='.py':continue
        tree=ast.parse(p.read_bytes())
        for node in ast.walk(tree):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                functions.append(dict(source=p.relative_to(P).as_posix(),name=node.name,line=node.lineno,end=node.end_lineno))
    write('SOURCE_CALL_SITES.json',dict(functions=functions))
    write('COST_EVIDENCE.json',dict(schema='dynamic_k_0019_fifo_cost_diagnosis_v1',historical_branches=branches,
        historical_HOLD_profiler=dict(plain_s=old['HOLD_plain_wall_s'],instrumented_s=old['HOLD_profiled_wall_s'],
            callbacks=old['HOLD_profiler_callbacks'],fifo_category_instrumented_s=old['HOLD_profiled_stage_exclusive_s']['FIFO'],
            scope='HOLD_ONLY_MIXED_Cohort.consume_LEDGER.consume_metrics_NOT_BBM'),
        controlled_diagnostic=completed,watchdog=read(A/'WATCHDOG_RESULT.json'),
        preverification=dict(status='PASS',parent_revision='0018',verified_files=6557,excluded_files=202,
            parent_sha256='c5c293b54f0eaf7b74c45effce6a8eafe6d39a4246f4c4b3e79b60b98f2eba4f'),
        bounds=dict(full_BBM_reruns=0,physical_root_runs=0,full_catalog_runs=0,epoch_runs=0,
                    diagnostic_child_launches=1,diagnostic_limit_s=60,optimization_implemented=False),
        decision='WORTH_BOUNDED_EXACT_SWEEP_INDEX_PROOF_NOT_PROVEN_FULL_BBM_SPEEDUP',
        complete_BBM_cost_attribution='UNRESOLVED_NO_PEAK_LIFETIME_COUNTERS',
        full_N4_P0_engineering_pass=False))
    write('DIAGNOSTIC_VALIDATION.json',dict(status='PASS_DIAGNOSTIC_SCOPE_ONLY',
        short_fixture_cases=13,plain_vs_counter_exact_state_or_result_equal=True,
        original_observation_records_mutated=False,profiler_or_trace_callbacks=0,
        global_monkeypatch=False,counters_scope='SYNTHETIC_ONLY_INTEGER_OPERATIONS_IN_ISOLATED_AST_COPY',
        timing_scope='ONE_SAMPLE_PER_LAYOUT_NOT_STATISTICAL_BENCHMARK',
        fixture_conservation_and_original_moments='EXACT_RATIONAL_PASS',
        runtime_or_scientific_acceptance=False,new_regression_runs=0,
        inherited_regression_evidence='0018_ONLY_NOT_RERUN',production_or_frozen_source_modified=False))
    old_cfg=read(V/'configs/n4_p0h_structural_seam_v1.json')
    config=dict(schema='dynamic_k_0019_fifo_cost_diagnostic_v1',stage='N4_P0I_DIAGNOSTIC_ONLY',
        scientific_parameters=old_cfg['scientific_parameters'],formal_control_parameters=old_cfg['formal_control_parameters'],
        historical_PILOT_ONLY_background=old_cfg['historical_PILOT_ONLY_background'],
        maximum_independent_diagnostic_runs=1,hard_stop_s=60,optimization_implemented=False,
        full_N4_P0_engineering_pass=False,full_pilot_execution_authorized=False,
        retained_prior_status='STOP_CATALOG_300S_HARD_LIMIT',Gate_C_0018_integrated_into_MPC=False)
    with (V/'configs/n4_p0i_fifo_diagnostic_v1.json').open('x',encoding='utf-8',newline='\n') as f:
        json.dump(config,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(dict(status='STATIC_EVIDENCE_ASSEMBLED',input_count=len(names),cases=13)),flush=True)

if __name__=='__main__':main()
