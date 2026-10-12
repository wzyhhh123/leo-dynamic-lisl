# -*- coding: utf-8 -*-
"""Eight-node structural evidence gate; never performs full K0 or K* selection."""
from datetime import datetime,timezone
import itertools
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.operational_policy import OperationalPolicy
from dynamic_lisl.f3_v2.k0_fixture import fixture
from dynamic_lisl.f3_v2.k0_snapshot import produce_snapshot,SnapshotBudget,BatchDiagnosticSpec,write_snapshot_bundle
from dynamic_lisl.f3_v2.k0_support import verify_snapshot_support
from dynamic_lisl.f3_v2.k0_ledger import review_ledger,load_review_records
from dynamic_lisl.f3_v2.structural import StructuralEdge,topology_objective
from dynamic_lisl.f3_v2.evidence import file_sha256,write_new_json
from dynamic_lisl.f3_v2.joint_action import canonical_sha256


def independent_tiny_oracle(bundle):
    edges=[StructuralEdge(tuple(tuple(t) for t in r['endpoints']),tuple(r['plane_pair']),
        r['ready_time_s'],r['observed_end_s'],r['censor_status']=='RIGHT_CENSORED_AT_600',
        r['observation_cutoff_s']) for r in bundle['lifetime']['idle_inventory']]
    K=bundle['snapshot']['K'];valid=[]
    for subset in itertools.combinations(edges,K):
        terminals=[t for e in subset for t in e.endpoints];pairs=[e.satellite_pair for e in subset]
        if len(set(terminals))==2*K and len(set(pairs))==K:
            valid.append(tuple(sorted(subset,key=lambda e:e.endpoints)))
    best=min(valid,key=lambda s:topology_objective(s,(0,1,2,3)))
    if canonical_sha256([e.endpoints for e in best])!=canonical_sha256(bundle['solver']['bindings']):
        raise AssertionError('INDEPENDENT_TINY_LEX_ORACLE_MISMATCH')
    # All eight fixture edges are terminal-disjoint, attaining the trivial
    # |terminals|/2 upper bound: an independent cardinality certificate here.
    matched=bundle['matching']['bindings']
    if len(matched)!=8 or len({t for b in matched for t in b})!=16:
        raise AssertionError('INDEPENDENT_FIXTURE_MATCHING_UPPER_BOUND_NOT_ATTAINED')
    return {'status':'PASS','enumerated_size_K_subsets':len(list(itertools.combinations(edges,K))),
        'legal_subsets':len(valid),'optimal_binding_sha256':canonical_sha256([e.endpoints for e in best]),
        'matching_cardinality_upper_bound_attained':8,'scope':'EIGHT_NODE_FIXTURE_ONLY'}


def main():
    out=ROOT/'outputs'/('f3_v2_k0_snapshot_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(exist_ok=False);print(str(out),flush=True)
    contract=ROOT/'configs/gate_k0_contract_v1_1_DRAFT.json';before=file_sha256(contract)
    code=list((ROOT/'src/dynamic_lisl/f3_v2').glob('*.py'))+[Path(__file__)]+[
        ROOT/'src/dynamic_lisl'/name for name in ('terminal_executor.py','gate_c_simplified_feasibility.py',
            'terminal_pair_intervals.py','transition_profiler.py','operational_policy.py')]
    code_hashes={p.relative_to(ROOT).as_posix():file_sha256(p) for p in code}
    write_new_json(out/'code_hashes_before.json',code_hashes)
    start=time.perf_counter();refs=[];point_evidence=[];current=None
    try:
        args,description=fixture();write_new_json(out/'fixture_contract.json',description)
        for t in (0,30,570):
            for replay in (0,1):
                current={'K':4,'time_s':t,'replay_index':replay}
                kwargs=dict(args)
                if t==0:kwargs['batch_diagnostic']=BatchDiagnosticSpec(2516,OperationalPolicy('STRICT_CONNECTED'))
                bundle=produce_snapshot(**kwargs,K=4,time_s=t)
                oracle=independent_tiny_oracle(bundle)
                verify=verify_snapshot_support(bundle['snapshot'],{k:bundle[k] for k in ('solver','physical','inventory','lifetime')})
                ref=write_snapshot_bundle(out/('K4_t%d_replay%d'%(t,replay)),bundle,root=ROOT,replay_index=replay)
                refs.append(ref)
                point_evidence.append({**current,'solver_status':bundle['solver']['status'],
                    'replay_sha256':bundle['snapshot']['relative_structural_replay_sha256'],
                    'support_verification':verify,'tiny_oracle':oracle,
                    'component_wall_s':bundle['component_wall_s'],
                    'selected_link_lifetime':bundle['lifetime']['selected_links'],
                    'batch_diagnostics':bundle['snapshot']['batch_diagnostics']})
                write_new_json(out/('point_%d_checkpoint.json'%len(refs)),{'point':current,'evidence_reference':ref,'oracle':oracle})
        manifest={'schema':'f3_v2_k0_review_inputs_v1','records':refs}
        write_new_json(out/'review_input_manifest.json',manifest)
        records=load_review_records(ROOT,manifest)
        ledger=review_ledger(json.loads(contract.read_text(encoding='utf-8')),records)
        write_new_json(out/'ledger_review.json',ledger)
        if any(point_evidence[i]['replay_sha256']!=point_evidence[i+1]['replay_sha256'] for i in (0,2,4)):
            raise AssertionError('POINT_REPLAY_MISMATCH')
        controls=[]
        for name,K,budget in (('solver_unknown',4,SnapshotBudget(1,5.,1,5.)),('matching_infeasible',16,args['budget'])):
            kwargs=dict(args);kwargs['budget']=budget;bundle=produce_snapshot(**kwargs,K=K,time_s=0)
            verify_snapshot_support(bundle['snapshot'],{k:bundle[k] for k in ('solver','physical','inventory','lifetime')})
            expected='UNKNOWN' if name=='solver_unknown' else 'EXACT_INFEASIBLE'
            if bundle['solver']['status']!=expected or bundle['snapshot']['metrics'] is not None:
                raise AssertionError('NEGATIVE_CONTROL_STATUS_MISMATCH')
            ref=write_snapshot_bundle(out/name,bundle,root=ROOT,replay_index=0)
            controls.append({'name':name,'status':expected,'metrics':None,'evidence_reference':ref})
        if file_sha256(contract)!=before:raise AssertionError('PROTECTED_K0_DRAFT_CHANGED')
        if any(file_sha256(ROOT/p)!=h for p,h in code_hashes.items()):raise AssertionError('SOURCE_CHANGED_DURING_GATE')
        report={'status':'ENGINEERING_K0_SNAPSHOT_EVIDENCE_PASS','scope':'EIGHT_NODE_SYNTHETIC_ONLY',
            'point_records':point_evidence,'negative_controls':controls,'paired_replay_PASS':True,
            'disk_support_content_verification_PASS':True,'tiny_matching_and_lex_oracle_PASS':True,
            'batch_safe_four_witness_at_t0':point_evidence[0]['batch_diagnostics']['max_joint_safe_witness_size']==4,
            't30_t570_batch_diagnostics':'NOT_EXECUTED','observation_cutoff_is_not_natural_expiry':True,
            'protected_contract_sha256_before':before,'protected_contract_sha256_after':file_sha256(contract),
            'ledger_status':ledger['status'],'Gate_K0_PASS':False,'full_natural_K0_audit_executed':False,
            'snapshot_initialization_human_frozen':False,'K_star_selected':False,
            'controller_or_traffic_invoked':False,'registered_experiment_started':False,
            'wall_s':time.perf_counter()-start}
        if not report['batch_safe_four_witness_at_t0']:raise AssertionError('FOUR_MEMBER_FIXTURE_WITNESS_MISSING')
        write_new_json(out/'report.json',report)
        write_new_json(out/'input_code_hashes.json',{'input':{'configs/gate_k0_contract_v1_1_DRAFT.json':before},
            'code':code_hashes,
            'fixture_canonical_sha256':canonical_sha256(description)})
        status=report['status'];rc=0
    except Exception as exc:
        status='ENGINEERING_K0_SNAPSHOT_FAIL_STOP';rc=1
        write_new_json(out/'failure_summary.json',{'status':status,'exception_type':type(exc).__name__,
            'message':str(exc),'last_point':current,'completed_references':refs,
            'wall_s':time.perf_counter()-start,'K_star_selected':False,'registered_experiment_started':False})
    write_new_json(out/'artifact_hashes.json',{p.relative_to(out).as_posix():file_sha256(p)
        for p in out.rglob('*') if p.is_file()})
    print(json.dumps({'status':status,'output_dir':str(out),'registered_experiment_started':False},indent=2))
    return rc


if __name__=='__main__':raise SystemExit(main())
