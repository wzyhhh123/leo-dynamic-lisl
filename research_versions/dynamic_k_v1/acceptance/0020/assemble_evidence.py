"""Offline evidence accounting only; no simulation or performance runs."""
import hashlib,json,statistics
from pathlib import Path
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,d):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def bind(p):
    b=p.read_bytes();return dict(path=p.relative_to(P).as_posix(),byte_count=len(b),sha256=hashlib.sha256(b).hexdigest())
def main():
    perf=read(A/'FIXTURE_PERFORMANCE.json');costs=[]
    for row in perf['cases']:
        averages={}
        for mode in ('reference','sweep'):
            averages[mode]={key:statistics.mean(x[mode][key] for x in row['paired_plain_samples'])
                for key in ('total_fixture_s','interval_including_index_cold_build_s')}
        stats=row['sweep_light_measurements']
        costs.append(dict(layout=row['layout'],m=row['n'],paired_plain_means=averages,
            coverage_predicate_reference_count_source_derived=sum(x['legacy_coverage_predicate_iterations'] for x in stats),
            sweep_runtime_coverage_predicate_count=sum(x['optimized_coverage_predicate_iterations'] for x in stats),
            actual_clip_calls=sum(x['clips'] for x in stats),coverage_created_Stream_objects=sum(x['temporary_clip_Stream_objects'] for x in stats),
            active_peak=max(x['active_peak'] for x in stats),parts_peak=max(x['parts_peak'] for x in stats),
            peak_active_bitset_bits=max(x['peak_active_bitset_bits'] for x in stats),
            index_endpoint_references=sum(x['endpoint_references'] for x in stats),
            light_stage_s={key:sum(x[key] for x in stats) for key in ('build_s','maintenance_s','enumeration_and_clip_s')},
            memory=row['memory'],
            interval_ratio=averages['reference']['interval_including_index_cold_build_s']/averages['sweep']['interval_including_index_cold_build_s']))
    real=read(A/'REAL_PREFIX_COMPARISON.json');light=read(A/'REAL_PREFIX_LIGHT.json')['rows']
    real_cost=dict(comparison=real,
        prefix_source_derived_legacy_predicate_iterations=sum(x['legacy_coverage_predicate_iterations'] for x in light),
        replay_measured_optimized_predicate_iterations=sum(x['optimized_coverage_predicate_iterations'] for x in light),
        replay_actual_clip_calls=sum(x['clips'] for x in light),coverage_created_Stream_objects=sum(x['temporary_clip_Stream_objects'] for x in light),
        active_peak=max(x['active_peak'] for x in light),parts_peak=max(x['parts_peak'] for x in light),
        incoming_peak=max(x['input_streams'] for x in light),index_build_calls=len(light),
        index_endpoint_references=sum(x['endpoint_references'] for x in light),
        light_stage_s={key:sum(x[key] for x in light) for key in ('build_s','maintenance_s','enumeration_and_clip_s')},
        complete_process_peak_memory_bytes=None,complete_cohort_allocation_count=None,
        scope='COVERAGE_COUNTERS_ONLY_FROM_READ_ONLY_REPLAY_OF_REAL_PREFIX; TOTAL_COHORT_PEAK_NOT_MEASURED')
    regs={}
    for p in (A/'regressions').glob('*.json'):regs[p.stem]=read(p)
    assert all(x['status'] in ('PASS','PASS_NO_NEW_FAILURES') for x in regs.values())
    for stage in ('N3','P0'):
        rows=[x for k,x in regs.items() if k.startswith('sweep_'+stage+'_')]
        ids=[i for row in rows for i in row['selected_test_ids']]
        assert len(ids)==len(set(ids))==20 and all(x['full_suite_count']==20 for x in rows)
    summary=dict(status='PASS_NO_NEW_COMPLETED_REGRESSION_FAILURES',
        upstream=dict(N1a=regs['original_N1a']['tests_run'],N1b=regs['sweep_N1b']['tests_run'],
            N2=regs['sweep_N2']['tests_run'],N3=20,P0=20),
        original_control_additional=dict(N1b=regs['original_N1b']['tests_run'],N2=regs['original_N2']['tests_run']),
        event_clock_and_1bit_loss=regs['events']['tests_run'],
        historical_tests=sum(x['tests_run'] for k,x in regs.items() if k.startswith('history_')),
        retained_historical_failures=[f for k,x in regs.items() if k.startswith('history_') for f in x['failures']],
        early_N3_UTF8_entry_failure='KEPT; NO_TEST_CASE_STARTED',
        early_N3_60s_whole_group_timeout='KEPT; NO_PASS_INFERRED_FROM_PARTIAL_LOG; ALL_CASES_COMPLETED_IN_BOUNDED_GROUPS',
        test_sources_or_expected_results_modified=False)
    assert sum(summary['upstream'].values())==116
    assert summary['historical_tests']==132 and len(summary['retained_historical_failures'])==1
    write(A/'REGRESSION_ACCEPTANCE.json',summary)
    write(A/'COST_SUMMARY.json',dict(status='STOP_NO_DEMONSTRATED_NET_GAIN',fixture_costs=costs,real_short_prefix=real_cost,
        conclusion='SYNTHETIC_DISJOINT_GAIN_MEASURED; ONE_REAL_PREFIX_END_TO_END_GAIN_NOT_DEMONSTRATED',
        further_performance_attempts_after_real_pair=0,full_BBM_speedup=None,full_N4_P0_engineering_pass=False,
        counters_labels='REFERENCE_PREDICATE_COUNT_STRUCTURALLY_DERIVED_FROM_MEASURED_m_c; SWEEP_CLIP_COUNTS_MEASURED',
        memory_labels='SEPARATE_TRACEMALLOC_RUNS_SYNTHETIC_ONLY; NOT_PRODUCTION_WALL_OR_PROCESS_RSS'))
    paths=[V/'runtime'/x for x in ('n1b_fifo.py','n1b_evaluator.py','n1a.py','n2_controller.py','n4_p0.py','n4_p0f_events.py','n4_p0r_handle_reader.py')]
    paths += list((V/'tests').glob('test_n*.py'))
    paths += [V/'acceptance/0019'/x for x in ('DIAGNOSTIC_PROGRESS.jsonl','COST_EVIDENCE.json','diagnostic_child.py','SOURCE_CALL_SITES.json')]
    paths += [V/'acceptance/0015'/x for x in ('ROOT_BASELINE/root_binding.json','variant_dependencies.json','VARIANT_BINDING.json','replay_recipe.json','test_event_clock.py')]
    paths += [V/'acceptance/0011/workflow.py',V/'acceptance/0011/historical_regression.json',V/'acceptance/0010/workflow.py',V/'acceptance/0007/attempt01/catalog_coverage.json']
    paths += [P/'src/dynamic_lisl/transition_service_orchestrator.py',P/'configs/hardware_gate_c_simplified_v1.json']
    paths += [P/'outputs/gate_c_simplified_20260922T064019_313843Z'/x for x in ('z_ref.json','terminal_pair_intervals.jsonl')]
    paths += [P/'data/raw/sgp4_x720'/x for x in ('manifest.json','hashes.json','constellation.tle')]
    paths += [V/'revisions'/('%04d'%i)/'record.json' for i in range(1,20)]+[V/'version_record.json']
    write(A/'AUDIT_INPUT_MANIFEST.json',dict(schema='dynamic_k_0020_exact_FIFO_sweep_inputs_v1',files=[bind(p) for p in sorted(set(paths))]))
    for p in A.glob('*.py'):compile(p.read_bytes(),str(p),'exec')
    write(A/'VALIDATION.json',dict(status='PASS_EXACT_EQUIVALENCE_COST_STOP',correctness_cases=29,
        reference_and_seam_existing_state_hashes_equal=True,parts_order_and_exact_Fractions_equal=True,
        native_code_class_provenance_differs=True,full_native_class_graph_SHA_equivalence_claimed=False,
        single_real_prefix_pair=.125,performance_case_count=8,regression=summary,
        optimization_scope='INCOMING_COVERAGE_LOOKUP_ONLY_NO_FLIGHT_KEY_INDEX',
        FIFO_semantics_changed=False,conservation_tolerance_changed=False,global_monkeypatch=False,
        science_frozen=False,full_catalog_enumerated=False,full_epoch_executed=False,
        STOP='STOP_NO_DEMONSTRATED_NET_GAIN',full_N4_P0_engineering_pass=False))
    old=read(V/'configs/n4_p0i_fifo_diagnostic_v1.json')
    write(V/'configs/n4_p0j_fifo_sweep_v1.json',dict(schema='dynamic_k_0020_exact_fifo_sweep_v1',
        scientific_parameters=old['scientific_parameters'],formal_control_parameters=old['formal_control_parameters'],
        historical_PILOT_ONLY_background=old['historical_PILOT_ONLY_background'],hard_diagnostic_limit_s=60,
        stage='P0J_INCOMING_COVERAGE_SWEEP_ONLY',source_module='runtime/n4_p0j_fifo_sweep.py',
        integration_into_complete_MPC=False,full_N4_P0_engineering_pass=False,full_pilot_execution_authorized=False,
        status='STOP_NO_DEMONSTRATED_NET_GAIN',retain_catalog_status='STOP_CATALOG_300S_HARD_LIMIT'))
    print(json.dumps(dict(status='EVIDENCE_ASSEMBLED_COST_STOP',regression=summary),sort_keys=True),flush=True)
if __name__=='__main__':main()
