"""K4/t0 natural structural source cost/coverage, no traffic or controllers.

The full unchanged source must finish before any raw/pool coverage conclusion.
Budgets only bound this isolated engineering observation; they are not F3
scientific caps. Prefix evidence survives UNKNOWN, exceptions and child timeout.
"""
import argparse
from datetime import datetime,timezone
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def run_audit(output_dir,max_evaluations,source_wall_s,legacy_physical):
    from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256
    from dynamic_lisl.f3_v2.source_diagnostics import observe_replacement_source
    from dynamic_lisl.f3_v2.candidate_source import RawCandidateBudget
    from dynamic_lisl.f3_v2.joint_action import BatchReplaceMember,JointAction,terminal_state_hash,canonical_sha256
    from dynamic_lisl.f3_v2.batch_executor import BatchPhysicalValidator,BatchSafetyValidator
    from dynamic_lisl.f3_v2.joint_proposer import BoundedJointProposer,JointSearchBudget
    from dynamic_lisl.terminal_executor import TerminalExecutor,Connect,pair
    from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
    from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
    from dynamic_lisl.operational_policy import OperationalPolicy
    out=Path(output_dir)
    inputs=['configs/z_moderate_v1.json','configs/hardware_gate_c_simplified_v1.json',
        'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl',
        'configs/F3_V2_RUNTIME_BUDGET_PLAN.json']
    input_hashes={p:file_sha256(ROOT/p) for p in inputs}
    write_new_json(out/'input_hashes.json',input_hashes)
    topology=json.loads((ROOT/inputs[0]).read_text(encoding='utf-8'))
    hardware=json.loads((ROOT/inputs[1]).read_text(encoding='utf-8'))
    fixed=tuple(map(tuple,topology['fixed_edges']));nodes=tuple(sorted({n for e in fixed for n in e}))
    planes={n:int(n.split('_')[0][1:]) for n in nodes}
    catalog=TerminalPairCatalog.from_records([json.loads(line) for line in
        (ROOT/inputs[2]).read_text(encoding='utf-8').splitlines()],planes)
    physical=TerminalPairPhysicalFeasibility(catalog);ex=TerminalExecutor(nodes)
    # Match the existing natural prefix initialization order/checkpoints exactly.
    for row in topology['bindings']:
        ex.submit((Connect(tuple(row['a']),tuple(row['b']),row['end_s'],0,0,0),))
    initial=terminal_state_hash(ex);setup=hardware['audit_setup_fixture'];frame='K4_NATURAL_SOURCE_ENGINEERING_ONLY'
    budget=JointSearchBudget(16,8,4,32,4,184,184,33)
    validator=BatchSafetyValidator(BatchPhysicalValidator(physical,max_batch_replace=4,
        observation_end_s=600,absolute_time_frame_id=frame,counterfactual_physical_clone=not legacy_physical),
        fixed,OperationalPolicy('STRICT_CONNECTED'))
    write_new_json(out/'root_terminal_state.json',ex.snapshot())
    started=time.perf_counter();stage='WITNESS';report=None
    try:
        # Predeclared structural witness: canonical-first genuine MBB preserving
        # each old plane pair, >10 s window, disjoint terminal footprints.
        witness=[];used=set();windows=catalog.terminal_pair_candidates(0,nodes);inspected=0
        for old in sorted(ex.links.values(),key=lambda link:link.endpoints):
            if used.intersection(old.endpoints):continue
            old_planes=tuple(sorted(planes[t[0]] for t in old.endpoints))
            for window in windows:
                new=pair(window.endpoint_a,window.endpoint_b)
                if tuple(sorted(planes[t[0]] for t in new))!=old_planes or window.end_s<=10:continue
                if new==old.endpoints or used.intersection(new):continue
                if any(ex.terminals[t].phase!='IDLE' or ex.terminals[t].reservation_id for t in new):continue
                member=BatchReplaceMember('V2-RAW-'+canonical_sha256({'time_s':ex.now,'old':old.endpoints,'new':new}),
                    len(witness),old.endpoints,new,setup['retarget_a_s'],setup['retarget_b_s'],setup['acquisition_s'])
                action=JointAction(0,frame,initial,canonical_sha256([]),(member,));inspected+=1
                plan=validator.evaluate(ex,action)
                if not plan.accepted:continue
                if plan.member_results[0]['transition_mode']!='MBB':raise AssertionError('WITNESS_NOT_GENUINE_MBB')
                witness.append(member);used.update(member.footprint);break
        witness_action=JointAction(0,frame,initial,canonical_sha256([]),tuple(witness))
        witness_plan=validator.evaluate(ex,witness_action)
        write_new_json(out/'structural_witness.json',{'action':witness_action.to_dict(),
            'validation':witness_plan.to_dict(),'candidate_evaluations':inspected,
            'wall_s':time.perf_counter()-started,'full_universe_maximum_claim':False})
        if not witness or not witness_plan.accepted:raise AssertionError('PREDECLARED_NATURAL_WITNESS_NOT_SAFE')
        stage='UNCHANGED_RAW_SOURCE'
        with (out/'row_observations.jsonl').open('x',encoding='utf-8') as row_file:
            def sink(row):
                row_file.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n')
                if row['index']%128==127:row_file.flush()
            observed=observe_replacement_source(ex,physical,max_evaluations=max_evaluations,
                wall_budget_s=source_wall_s,row_sink=sink,legacy_physical=legacy_physical,plane_by_satellite=planes,
                retarget_a_s=setup['retarget_a_s'],retarget_b_s=setup['retarget_b_s'],
                acquisition_s=setup['acquisition_s'],observation_end_s=600,
                raw_budget=RawCandidateBudget(32,32,64))
        write_new_json(out/'source_observation_summary.json',{k:v for k,v in observed.items() if k not in ('source_result','rows')})
        report={'status':observed['status'],'source_wall_s':observed['wall_s'],
            'source_validator_wall_s':observed['validator_wall_total_s'],
            'source_evaluations_completed':observed['evaluations_completed'],
            'root_unchanged':observed['live_unchanged'],'source_wrapper_restored':observed['wrapper_restored'],
            'terminal_pair_windows_at_t0':len(windows),'old_binding_count':len(ex.links),
            'full_raw_coverage_known':observed['complete_raw_coverage_known'],
            'uncapped_joint_safe_witness_size':len(witness),'pool_coverage_known':False}
        if observed['status']=='SOURCE_OBSERVATION_COMPLETE':
            stage='COMMON_PROPOSER';source=observed['source_result'];write_new_json(out/'raw_source_audit.json',source['audit'])
            pool_start=time.perf_counter();pool=BoundedJointProposer(validator,budget).propose(ex,source['members'])
            pool_wall=time.perf_counter()-pool_start
            write_new_json(out/'pool.json',pool.public_document())
            old_bindings=sorted(link.endpoints for link in ex.links.values())
            histogram=lambda members:[{'old_binding':old,'count':sum(m.old_binding==old for m in members)} for old in old_bindings]
            report.update(status='NATURAL_K4_SOURCE_COVERAGE_AUDIT_COMPLETE',
                uncapped_accepted_count=source['audit']['uncapped_physical_count'],
                raw_member_count=len(source['members']),raw_stratum_counts=source['audit']['stratum_counts'],
                raw_old_binding_histogram=histogram(source['members']),
                singleton_old_binding_histogram=histogram(pool.physical_singletons),
                final_pool_non_hold_count=len(pool.actions)-1,
                final_pool_max_batch_size=max(len(action.members) for action in pool.actions),
                final_pool_coverage_by_size=pool.audit['coverage_by_size'],
                pool_sha256=pool.pool_sha256,proposer_wall_s=pool_wall,pool_coverage_known=True,
                raw_witness_member_coverage=[m.member_id in source['audit']['selected_member_ids'] for m in witness],
                singleton_witness_member_coverage=[m.member_id in {x.member_id for x in pool.physical_singletons} for m in witness])
        elif observed['status']=='SOURCE_OBSERVATION_FAIL_STOP':raise AssertionError(observed['error'])
    except Exception as error:
        report={'status':'ENGINEERING_FAIL_STOP','stage':stage,'error_type':type(error).__name__,'error':str(error),
            'full_raw_coverage_known':False,'pool_coverage_known':False}
    report.update(total_wall_s=time.perf_counter()-started,
        inputs_unchanged=all(file_sha256(ROOT/p)==h for p,h in input_hashes.items()),
        final_root_sha256=terminal_state_hash(ex),live_unchanged=terminal_state_hash(ex)==initial,
        scope='160_STAR_T0_K4_OCCUPIED_TERMINALS_STRUCTURAL_ENGINEERING_ONLY',
        initial_binding_convention='historical K4 pre-established by original sequential submit order; not new K1',
        legacy_physical_reference=legacy_physical,
        science_policy_changed=False,traffic_read=False,Q_I_D_created=False,J_computed=False,
        K_star_selected=False,registered_P1_v2_executed=False,P2_started=False,RL_started=False)
    if not report['inputs_unchanged'] or not report['live_unchanged']:report['status']='ENGINEERING_FAIL_STOP'
    write_new_json(out/'final_terminal_state.json',ex.snapshot())
    write_new_json(out/'report.json',report)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-evaluations',type=int,required=True)
    parser.add_argument('--source-wall-s',type=float,required=True)
    parser.add_argument('--timeout-s',type=float,required=True)
    parser.add_argument('--legacy-physical',action='store_true')
    args=parser.parse_args()
    import math
    if args.max_evaluations<1 or any(not math.isfinite(t) or t<=0 for t in (args.source_wall_s,args.timeout_s)) or args.timeout_s<=args.source_wall_s:
        parser.error('EXPLICIT_POSITIVE_BUDGET_AND_LONGER_PARENT_TIMEOUT_REQUIRED')
    from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256
    out=ROOT/'outputs'/('f3_v2_natural_source_coverage_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir()
    write_new_json(out/'fixture_contract.json',{'status':'ENGINEERING_ONLY_DRAFT_NOT_FROZEN',
        'scene':'historical160_K4_t0','raw_caps':[32,32,64],'singleton_cap':16,'per_stratum':8,
        'beam_width':4,'pool_non_hold_cap':32,'expansion_cap':184,'validation_cap':184,'rollout_cap':33,
        'observation_budget':vars(args),'future_performance_read':False,
        'fixture_selection':'fixed historical K4, t0; no alternative selection after observing coverage',
        'witness_rule':'lexical first safe genuine MBB per old plane pair; disjoint footprints; >10s window',
        'cost_includes_passive_recording_overhead':True,'row_recording_fsync':False,
        'partial_inventory_cannot_define_raw_proposals':True,
        'tool_sha256':file_sha256(Path(__file__)),
        'code_hashes':{p.relative_to(ROOT).as_posix():file_sha256(p) for p in (ROOT/'src/dynamic_lisl/f3_v2').glob('*.py')}})
    print(str(out),flush=True)
    proc=mp.get_context('spawn').Process(target=run_audit,args=(str(out),args.max_evaluations,args.source_wall_s,args.legacy_physical))
    started=time.perf_counter();proc.start();proc.join(args.timeout_s)
    if proc.is_alive():
        proc.terminate();proc.join();status='ENGINEERING_CHILD_TIMEOUT_UNKNOWN'
    elif proc.exitcode!=0:status='ENGINEERING_CHILD_FAIL_STOP'
    else:status=json.loads((out/'report.json').read_text(encoding='utf-8'))['status']
    write_new_json(out/'parent_execution_report.json',{'status':status,'child_exitcode':proc.exitcode,
        'child_alive_after_shutdown':proc.is_alive(),'wall_s':time.perf_counter()-started,
        'registered_experiment_started':False,'K_star_selected':False})
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps({'status':status,'output_dir':str(out)},indent=2))
    return 1 if 'FAIL_STOP' in status else 0


if __name__=='__main__':raise SystemExit(main())
