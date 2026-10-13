"""Consecutive append-only 0020 seal; full raw-byte asset protection."""
import importlib.util,json
from pathlib import Path
from datetime import datetime,timezone,timedelta
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='d057cc197f7d5733d9523c7ce31c993b9ac722747ba7ee941b718432d128b605'
spec=importlib.util.spec_from_file_location('0020_vc',V/'tools/version_control_readme_v1.py')
vc=importlib.util.module_from_spec(spec);spec.loader.exec_module(vc)
def write(p,d):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def bind(p):return vc.binding(P,Path(p).relative_to(P).as_posix())
def main():
    version,base,expected,latest,parent,reserved=vc.load_expected(P,ORIGIN,PARENT)
    assert latest['revision_id']=='0019'
    for row in vc.read_json(A/'AUDIT_INPUT_MANIFEST.json')['files']:
        assert bind(P/row['path'])==row
        if row['path'] not in reserved:assert expected[row['path']]=={k:row[k] for k in ('byte_count','sha256')}
    provenance=vc.read_json(A/'SOURCE_PROVENANCE.json')
    runtime=V/'runtime/n4_p0j_fifo_sweep.py'
    assert vc.file_info(runtime)['sha256']==provenance['seam_sha256']
    assert vc.file_info(V/'runtime/n1b_fifo.py')['sha256']==provenance['frozen_source_sha256']
    assert vc.read_json(A/'CORRECTNESS.json')['case_count']==29
    assert vc.read_json(A/'REGRESSION_ACCEPTANCE.json')['status']=='PASS_NO_NEW_COMPLETED_REGRESSION_FAILURES'
    assert vc.read_json(A/'COST_SUMMARY.json')['status']=='STOP_NO_DEMONSTRATED_NET_GAIN'
    assert vc.read_json(A/'REAL_PREFIX_COMPARISON.json')['outputs_exact']
    config=V/'configs/n4_p0j_fifo_sweep_v1.json';cfg=vc.read_json(config)
    assert all(v is None for v in cfg['scientific_parameters'].values())
    assert all(v is None for v in cfg['formal_control_parameters'].values())
    assert cfg['historical_PILOT_ONLY_background']['decision_cadence_s']==3
    for p in A.glob('*.py'):compile(p.read_bytes(),str(p),'exec')
    compile(runtime.read_bytes(),str(runtime),'exec')
    contract=V/'contracts/N4_P0J_0020_FIFO_SWEEP_SCOPE_CN.md'
    write(A/'pre_implementation_verification.json',dict(status='PASS',revision_id='0019',
        version_record_sha256=ORIGIN,revision_record_sha256=PARENT,verified_file_count=6578,
        excluded_file_count=202,baseline_file_count=5810,
        undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[]),
        source='Complete version verifier session68705 exit0 before0020 writes'))
    write(A/'manifest_final.json',dict(schema='dynamic_k_0020_FIFO_sweep_acceptance_manifest_v1',
        revision_id='0020',parent_revision=parent,version_origin=bind(V/'version_record.json'),
        files=[bind(p) for p in sorted(p for p in A.rglob('*') if p.is_file())]+[bind(runtime),bind(config),bind(contract)],
        status='STOP_NO_DEMONSTRATED_NET_GAIN',correctness='PASS_EXACT_EQUIVALENCE_SCOPE_ONLY',
        single_real_prefix_seconds=.125,full_N4_P0_engineering_pass=False,
        production_frozen_kernel_changed=False,optimization_scope='INCOMING_COVERAGE_ONLY_NO_FLIGHT_KEY_INDEX'))
    actual,excluded=vc.inventory(P,progress=lambda p:print(p,flush=True))
    for p in reserved:actual.pop(p,None)
    diff=vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],diff
    assert all(r['path'].startswith('research_versions/dynamic_k_v1/') for r in diff['added'])
    audit=A/'preseal_change_audit.json'
    write(audit,dict(status='PASS_COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',changes_before_audit_creation=diff,
        excluded=excluded,excluded_count=len(excluded),old_assets_modified=[],old_assets_deleted=[],old_assets_renamed=[]))
    actual[audit.relative_to(P).as_posix()]=vc.file_info(audit);diff=vc.differences(expected,actual)
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0020',
        parent_record=parent,created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='Bounded exact incoming-coverage sweep isolated seam; unchanged original cuts/order/clip/continuous FIFO/mass/moment/audits/tolerances;29 exact tests,116 upstream cases plus51 original controls,7 clock negative cases,132 historical with knownF3 preserved; synthetic gains but one160star PERSIST BBM 3->3.125 prefix shows no net gain; preserve helper UTF8 entry failure and60s partial N3 before bounded completion; STOP no fullBBM/epoch/pilot or automatic0021',
        authorization=dict(actor='human_user',source='current_conversation_user_request',scope='0020_BOUNDED_EXACT_FIFO_INCOMING_COVERAGE_SWEEP_ONLY',
            request='Verify0019 fullchain/frozeninputs; new independent seam no globalpatch; exactFraction activecoverage originalcuts incomingorder clipcalls massmomentFIFO/audits conserved; broad exactfields/order/hash tests incl1bit loss; correctness before finitepairedtimings and controlled realprefix;60s per diagnostic child; no1100sBBM/catalog/epoch;no flightkeystage or sciencealgorithm change; seal0020 and STOPreview'),
        changes={k:diff[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=version['baseline_seal'],contract=bind(contract),configuration=bind(config),
            implementation_manifest=bind(A/'manifest_final.json'),implementation=bind(runtime),
            result_report=bind(A/'RESULT_CN.md'),cost_evidence=bind(A/'COST_SUMMARY.json'),
            source_provenance=bind(A/'SOURCE_PROVENANCE.json'),minimal_diff=bind(A/'MINIMAL_INTERVAL_DIFF.patch'),
            correctness=bind(A/'CORRECTNESS.json'),regressions=bind(A/'REGRESSION_ACCEPTANCE.json'),
            real_prefix=bind(A/'REAL_PREFIX_COMPARISON.json'),inputs=bind(A/'AUDIT_INPUT_MANIFEST.json'),
            validation=bind(A/'VALIDATION.json'),old_asset_audit=bind(audit)),
        status='STOP_NO_DEMONSTRATED_NET_GAIN',correctness_status='PASS_EXACT_EQUIVALENCE_SCOPE_ONLY',
        limited_cost_engineering_pass=False,full_N4_P0_engineering_pass=False,scientific_gate_pass=False,
        retained_prior_status='STOP_CATALOG_300S_HARD_LIMIT',formal_experiments_executed=False,
        frozen_production_kernel_modified=False,history_modified=False,full_BBM_reruns=0,full_catalog_runs=0,
        full_epoch_runs=0,real_short_prefix_pair_count=1,further_performance_runs_after_real_pair=0,
        recommend_full_BBM_validation=False,recommendation='PAUSE_FURTHER_FIFO_OPTIMIZATION_REVIEW_BEFORE_ANY_NEW_WORK')
    p=V/'revisions/0020/record.json';p.parent.mkdir(exist_ok=False);write(p,record)
    print(json.dumps(dict(revision=bind(p),added=len(diff['added']),modified=0,deleted=0,renamed=0)),flush=True)
if __name__=='__main__':main()
