"""Static-only consecutive seal; never imports simulator/runtime code."""
import ast,importlib.util,json,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='8cb85f868c5177663b89222d9da7db66b48e10bec6a38a35b2f83701925ffea6'
spec=importlib.util.spec_from_file_location('static_0017_vc',V/'tools/version_control_readme_v1.py')
vc=importlib.util.module_from_spec(spec);spec.loader.exec_module(vc)
def write(p,d):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def bind(p):return vc.binding(P,Path(p).relative_to(P).as_posix())
def main():
    version,base,expected,latest,parent,reserved=vc.load_expected(P,ORIGIN,PARENT)
    assert latest['revision_id']=='0016'
    for r in vc.read_json(A/'AUDIT_INPUT_MANIFEST.json')['files']:
        assert bind(P/r['path'])==r
        assert expected[r['path']]=={k:r[k] for k in ('byte_count','sha256')}
    supplemental=[V/'tests/test_n3_baselines.py',V/'configs/n4_p0g_single_epoch_engineering_v1.json',
        V/'acceptance/0016/SMALL_PERSIST_SUMMARY.json',V/'acceptance/0016/SMALL_ZERO_SUMMARY.json',
        V/'acceptance/0016/SCORING_RULE_0015_CHECK.json',V/'acceptance/0016/complete_saved_timing.py']
    for p in supplemental:assert vc.file_info(p)==expected[p.relative_to(P).as_posix()]
    write(A/'SUPPLEMENTAL_INPUT_MANIFEST.json',dict(schema='dynamic_k_0017_supplemental_audit_inputs_v1',files=[bind(p) for p in supplemental]))
    evidence=vc.read_json(A/'COST_EVIDENCE.json');deriv=vc.read_json(A/'STRUCTURAL_EVENT_COUNTS.json')
    assert evidence['simulation_runs']==evidence['branch_runs']==evidence['catalog_validation_calls']==0
    assert len(evidence['branches'])==10 and evidence['catalog_prefix']['completed_count']==2598
    assert evidence['catalog_prefix']['accepted_count']==2566 and evidence['catalog_prefix']['complete_legal_count'] is None
    bbm=next(x for x in deriv['rows'] if x['mode']=='PERSIST' and x['action'].get('mode')=='BBM')
    assert bbm['derived_positive_time_steps']==233 and bbm['derived_microstep_and_SCHEDULE_calls']==236
    assert bbm['age_record_delta']==479 and bbm['closure_record_delta']==10
    for p in A.glob('*.py'):compile(p.read_bytes(),str(p),'exec')
    imports={}
    for name in ('audit_static.py','derive_event_counts.py'):
        tree=ast.parse((A/name).read_bytes());names=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):names.extend(x.name for x in node.names)
            if isinstance(node,ast.ImportFrom):names.append(node.module)
        assert not any(x.startswith(('runtime','dynamic_lisl')) for x in names)
        imports[name]=names
    old=vc.read_json(P/latest['bindings']['configuration']['path'])
    assert all(x is None for x in old['scientific_parameters'].values())
    assert all(x is None for x in old['formal_control_parameters'].values())
    cp=V/'configs/n4_p0g_0017_static_cost_design_v1.json'
    contract=V/'contracts/N4_P0G_0017_STATIC_COST_DESIGN_SCOPE_CN.md'
    write(cp,dict(schema='dynamic_k_n4_p0g_0017_static_cost_design_v1',stage='N4_P0G_COST_ATTRIBUTION_DESIGN_ONLY',
        scientific_parameters=old['scientific_parameters'],formal_control_parameters=old['formal_control_parameters'],
        historical_PILOT_ONLY_background=old['PILOT_ONLY'],MPC_weights_modified=False,
        prospective_scheme_2_budgets=dict(lookup=None,ADD=None,DROP=None,REPLACE=None,refill=None),
        selected_implementation_scheme=None,optimization_implemented=False,simulation_runs=0,
        scoring_runs=0,catalog_validation_calls=0,full_N4_P0_engineering_pass=False,
        formal_experiments_authorized=False,full_pilot_execution_authorized=False,
        retained_prior_status='STOP_CATALOG_300S_HARD_LIMIT',status='PASS_STATIC_COST_AUDIT_DESIGN_ONLY'))
    write(A/'pre_implementation_verification.json',dict(status='PASS',revision_id='0016',revision_sha256=PARENT,
        version_record_sha256=ORIGIN,verified_file_count=6459,baseline_file_count=5810,excluded_file_count=202,
        undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[]),
        source='Complete read-only verifier session 64422 exit0 before 0017 writes'))
    write(A/'STATIC_VALIDATION.json',dict(status='PASS_STATIC_EVIDENCE_AND_DESIGN_SCOPE_ONLY',
        input_raw_byte_bindings='PASS',parent_chain='PASS',branch_evidence_count=10,
        prefix_sequential_indices_and_counts='PASS',structural_count_equations='PASS',
        derived_BBM_steps=233,derived_BBM_microsteps=236,new_helper_syntax='PASS',
        audit_script_imports=imports,no_simulator_imports_in_audit_scripts=True,
        formal_science_and_control_null='PASS',source_or_test_expectations_modified=False,
        simulation_runs=0,new_regression_runs=0,full_catalog_or_epoch_runs=0,
        runtime_or_performance_acceptance_claimed=False))
    files=sorted(p for p in A.rglob('*') if p.is_file())+[cp,contract]
    write(A/'manifest_final.json',dict(schema='dynamic_k_0017_static_cost_design_manifest_v1',
        revision_id='0017',parent_revision=parent,version_origin=bind(V/'version_record.json'),
        files=[bind(p) for p in files],status='PASS_STATIC_COST_AUDIT_DESIGN_ONLY',
        source_binding_manifests=[bind(A/'AUDIT_INPUT_MANIFEST.json'),bind(A/'SUPPLEMENTAL_INPUT_MANIFEST.json')],
        runtime_changed=False,simulation_runs=0,full_N4_P0_engineering_pass=False))
    actual,excluded=vc.inventory(P,progress=lambda p:print(p,flush=True))
    for p in reserved:actual.pop(p,None)
    diff=vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],diff
    assert all(x['path'].startswith('research_versions/dynamic_k_v1/') for x in diff['added'])
    audit=A/'preseal_change_audit.json'
    write(audit,dict(status='PASS_COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',changes_before_audit_creation=diff,
        excluded=excluded,excluded_count=len(excluded),old_assets_modified=[],old_assets_deleted=[],old_assets_renamed=[]))
    actual[audit.relative_to(P).as_posix()]=vc.file_info(audit);diff=vc.differences(expected,actual)
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0017',
        parent_record=parent,created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N4-P0G static-only dual cost attribution over 0016 sealed branch/profiler/catalog prefix evidence; measured vs structural/source inference explicitly separated; exact optimization and newly preregistered hierarchical candidate alternatives designed but not adopted or implemented; preserve catalog STOP and all frozen assets',
        authorization=dict(actor='human_user',source='current_conversation_user_request',
            scope='N4_P0G_STATIC_DUAL_BOTTLENECK_ATTRIBUTION_AND_DESIGN_ONLY',
            request='Verify 0016 anchor and chain; statically audit sealed FIFO and candidate costs; no 1100s BBM or 300s catalog rerun; propose exact equivalent optimization and separately preregistered hierarchical candidates; no frozen implementation/weights/tolerance changes, simulations or experiments; seal consecutive 0017 and stop'),
        changes={k:diff[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=version['baseline_seal'],contract=bind(contract),configuration=bind(cp),
            implementation_manifest=bind(A/'manifest_final.json'),result_report=bind(A/'RESULT_CN.md'),
            cost_evidence=bind(A/'COST_EVIDENCE.json'),structural_counts=bind(A/'STRUCTURAL_EVENT_COUNTS.json'),
            inputs=bind(A/'AUDIT_INPUT_MANIFEST.json'),supplemental_inputs=bind(A/'SUPPLEMENTAL_INPUT_MANIFEST.json'),
            static_validation=bind(A/'STATIC_VALIDATION.json'),old_asset_audit=bind(audit),
            option_1=bind(A/'OPTION_1_EXACT_OPTIMIZATION_DESIGN_CN.md'),option_2=bind(A/'OPTION_2_HIERARCHICAL_CANDIDATES_DESIGN_CN.md')),
        status='PASS_STATIC_COST_AUDIT_DESIGN_ONLY',retained_prior_status='STOP_CATALOG_300S_HARD_LIMIT',
        full_N4_P0_engineering_pass=False,scientific_gate_pass=False,formal_experiments_executed=False,
        optimization_implemented=False,simulation_runs=0,new_regression_runs=0,production_code_modified=False,
        history_modified=False,selected_implementation_scheme=None)
    path=V/'revisions/0017/record.json';path.parent.mkdir(exist_ok=False);write(path,record)
    print(json.dumps(dict(revision=bind(path),added=len(diff['added']),modified=0,deleted=0,renamed=0)),flush=True)
if __name__=='__main__':main()
