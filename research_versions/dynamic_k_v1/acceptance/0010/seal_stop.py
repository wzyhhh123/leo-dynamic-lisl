"""Seal P0 functionality and explicit excessive-cost STOP without a PASS claim."""
import argparse,json
from datetime import datetime,timezone,timedelta
from workflow import A,V,P,vc,ORIGIN,PARENT,NS,write,bind,dependencies
from runtime.n4_p0 import P0EvidenceBinding

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--expected-manifest-sha256',required=True);args=parser.parse_args()
    guard=P0EvidenceBinding(P,NS+'acceptance/0010/manifest_final.json',args.expected_manifest_sha256)
    guard.verify();dependencies()
    full=vc.read_json(A/'attempt02/p0_tests.json');targeted=vc.read_json(A/'attempt03/p0_tests.json')
    assert full['status']==targeted['status']=='PASS' and full['tests_run']==19 and targeted['tests_run']==5
    entry=vc.read_json(A/'entry_guard_change_audit.json');assert entry['status']=='PASS' and entry['unique_test_cases_passed']==20
    regress={k:vc.read_json(A/('regression_'+k+'.json')) for k in ('N1a','N1b','N2','N3')}
    assert {k:r['tests_run'] for k,r in regress.items()}==dict(N1a=25,N1b=24,N2=27,N3=20)
    assert all(r['status']=='PASS' and not r['failures'] and not r['errors'] and not r['skipped'] for r in regress.values())
    historical=vc.read_json(A/'historical_regression.json');prior=vc.read_json(V/'acceptance/0007/historical_regression.json')
    assert historical['base']['tests_run']==97 and historical['physical_gate_c']['tests_run']==35
    assert historical['base']['failures']==prior['base']['failures'] and len(historical['base']['failures'])==1
    assert not historical['base']['errors'] and not historical['physical_gate_c']['failures'] and not historical['physical_gate_c']['errors']
    controls=vc.read_json(A/'version_protection_tests.json');assert controls['status']=='PASS' and controls['tests_run']==32
    stop=vc.read_json(A/'cost_stop_process_evidence.json');assert stop['status']=='STOP_COST_EXCESSIVE' and not stop['full_epoch_completed']
    assert not (A/'one_epoch_cost.json').exists(),'COMPLETE_EPOCH_EXISTS_REVIEW_STOP_STATUS'
    measured=vc.read_json(A/'standalone_branch_cost.json');assert measured['result']['prediction_completed']
    write(A/'causal_isolation_test_report.json',dict(status='PASS_TESTED_DATA_CAUSAL_ISOLATION',
        object_graph_scope='DATA_REFERENCES_AND_FUNCTION_CLOSURES_NOT_MALICIOUS_PYTHON_SECURITY_SANDBOX',
        full_suite=bind(A/'attempt02/p0_tests.json'),current_rate_entry_retests=bind(A/'attempt03/p0_tests.json'),
        exact_entry_guard_change_audit=bind(A/'entry_guard_change_audit.json'),
        tested_cases=['historical_prefix_mass_and_origin_age','twin_roots_different_future_trace',
            'candidate_order_and_checkpoint','ZERO_retains_backlog','committed_TX_setup_propagation_expiry',
            'foreign_trace_alias_rejected','future_read_and_deepcopy_poisoned','manual_future_rate_rejected'],
        source=bind(V/'runtime/n4_p0.py'),science_pass=False))
    write(A/'analytic_and_equivalence_report.json',dict(status='PASS_TARGETED_ENGINEERING_CASES',
        unique_case_count=20,full_suite_cases=19,targeted_reexecutions=5,total_passed_executions=24,
        failed_initial_attempt=bind(A/'attempt01/p0_tests.json'),initial_failure_cause='LocalFIFO identity comparison; full value encoding repaired, no tolerances changed',
        analytic_cases=dict(idle_h6_energy_J=9600,existing_active_pair_h6_energy_J=10080,
            free_pair_ADD_h6_increment_J=470,TX_draining_3_to_5_h6_increment_J=160,no_delivery_mean=None),
        same_action_reference=['HOLD','ADD','DROP','REPLACE_BBM','REPLACE_MBB'],
        compared_fields=['entire_D2_business_state_except_equivalent_exogenous_cursor_and_audit_initial_hash',
            'all_Fifo_cohort_distributions_and_state','all_energy_ledger_state','all_original_measurement_fields'],
        numerical_tolerances_changed=False,midpoint_approximation_used=False,
        real160_new_scoring_integration='ONE_COMPLETED_PERSIST_HOLD_BRANCH_ONLY',
        complete_real160_epoch_accepted=False))
    write(A/'regression_comparison.json',dict(status='PASS_NO_NEW_REGRESSIONS',
        upstream_counts={k:r['tests_run'] for k,r in regress.items()},historical_tests=132,historical_passed=131,
        existing_F3_failure=historical['base']['failures'],new_regressions=0,version_protection_tests=32))
    write(A/'cost_acceptance_report.json',dict(status='STOP_COST_EXCESSIVE',
        completed_standalone_branches=1,completed_full_decision_epochs=0,
        standalone_measurement=bind(A/'standalone_branch_cost.json'),process_stop_evidence=bind(A/'cost_stop_process_evidence.json'),
        sanitation_wallclock_s=measured['clone']['wallclock_s'],branch_wallclock_s=measured['branch']['wallclock_s'],
        process_cpu_s=stop['process_cpu_s'],process_elapsed_wall_s=stop['process_elapsed_wall_s'],
        process_peak_working_set_bytes=stop['process_peak_working_set_bytes'],
        full_epoch_wallclock_s=None,full_catalog_candidate_counts=None,full_epoch_action_selection=None,
        benchmark_instrumentation='sys.setprofile_cost_included_no_uninstrumented_speed_claim',
        branch_seconds_completed=6,branch_service_observations=measured['result']['service_observation_count'],
        branch_terminal_events=measured['result']['terminal_event_count'],branch_ending_cohorts=measured['result']['cohort_count'],
        partial_epoch_branch_compute_count=None,reason='STOP rule requested by human user; no incomplete phase reported as a completed epoch',
        further_optimization_runs=0,workers=1,full_pilot_runs=0,sensitivity_runs=0,scientific_gate_pass=False))
    write(A/'acceptance_summary.json',dict(status='STOP_COST_EXCESSIVE',N4_P0_engineering_pass=False,
        engineering_functionality_tests_pass=True,unique_functionality_cases=20,
        complete_cost_acceptance=False,full_epoch_completed=False,full_pilot_authorized=False,
        current_candidate_manifest=bind(A/'manifest_final.json'),frozen_upstream_regressions_pass=True,
        new_historical_regressions=0,formal_parameters_remain_null=True,decision_cadence_s=3,
        scientific_gate_pass=False))
    # Report template is UTF-8 Markdown; no interpreter locale dependency.
    template=(A/'RESULT_TEMPLATE_CN.md').read_text(encoding='utf-8')
    replacements={'CLONE_SECONDS':f"{measured['clone']['wallclock_s']:.6f}",
        'BRANCH_SECONDS':f"{measured['branch']['wallclock_s']:.6f}",
        'CPU_SECONDS':f"{stop['process_cpu_s']:.6f}",'PROCESS_ELAPSED_SECONDS':f"{stop['process_elapsed_wall_s']:.6f}",
        'PEAK_BYTES':str(stop['process_peak_working_set_bytes']),
        'BRANCH_METRICS':json.dumps({k:measured['result'][k] for k in
            ('J_h_bit_s','N_end_bits','DeltaE_h_J','cost_bit_s','cohort_count','service_observation_count','terminal_event_count')},indent=2),
        'PARTS':json.dumps(measured['branch']['exclusive_classified_s'],indent=2)}
    for k,v in replacements.items():template=template.replace('{{'+k+'}}',v)
    write(A/'RESULT_CN.md',template)
    loaded=vc.load_expected(P,ORIGIN,PARENT);version,baseline,expected,latest,parent,reserved=loaded
    actual,excluded=vc.inventory(P,progress=lambda x:print(json.dumps(dict(progress=x)),flush=True))
    for r in reserved:actual.pop(r,None)
    diff=vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],diff
    assert all(r['path'].startswith(NS) for r in diff['added']),diff
    assert vc.load_expected(P,ORIGIN,PARENT)==loaded;guard.verify();dependencies()
    write(A/'preseal_change_audit.json',dict(status='PASS',scope='COMPLETE_RAW_BYTE_AUDIT',
        old_assets_changed=[],existing_sealed_version_assets_changed=[],changes_before_audit_file=diff,
        includes_gitignored_research_assets=True,tmp_evidence_included=True,excluded=excluded,
        excluded_file_count=len(excluded),scientific_gate_pass=False))
    audit_rel=(A/'preseal_change_audit.json').relative_to(P).as_posix();actual[audit_rel]=vc.file_info(A/'preseal_change_audit.json')
    final=vc.differences(expected,actual);assert not final['modified'] and not final['deleted']
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0010',parent_record=parent,
        created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N4-P0 causal root-action scorer engineering implementation; three-second PILOT_ONLY amendment; functionality passed, cost STOP, no completed full epoch or paired pilot.',
        authorization=dict(actor='human_user',scope='N4_P0_MINIMUM_ENGINEERING_THREE_SECOND_AMENDMENT_AND_COST_STOP',
            source='current_conversation_user_request',request='Implement independent causal ZERO/PERSIST root scoring using unchanged N1a/N1b/N2/N3. Validate historical prefix/FIFO/events/energy and causal isolation. Measure only one branch and one epoch; STOP if cost is clearly excessive. Amend decision cadence from 1 to 3 seconds, keep old draft bytes/hashes, main pilot budget 840. No complete pilot/sensitivity/GNN/formal experiments; formal parameters remain null.'),
        changes={k:final[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=version['baseline_seal'],
            contract=bind(V/'contracts/N4_P0_CAUSAL_ROOT_SCORING_CN.md'),
            configuration=bind(V/'configs/n4_p0_pilot_semantics_v1.json'),implementation_manifest=bind(A/'manifest_final.json'),
            summary=bind(A/'acceptance_summary.json'),report=bind(A/'RESULT_CN.md'),cost=bind(A/'cost_acceptance_report.json'),
            old_asset_audit=bind(A/'preseal_change_audit.json'),seal_tool=bind(A/'seal_stop.py')),
        N4_P0_engineering_pass=False,engineering_functionality_tests_pass=True,cost_status='STOP_COST_EXCESSIVE',
        full_epoch_completed=False,full_pilot_executed=False,scientific_gate_pass=False,formal_experiments_executed=False)
    path=V/'revisions/0010/record.json';write(path,record);print(json.dumps(bind(path)),flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
