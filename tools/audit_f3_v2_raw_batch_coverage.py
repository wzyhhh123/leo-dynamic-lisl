"""Synthetic structural counterexample: no traffic/J/controller results."""
from datetime import datetime,timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog,TerminalPairWindow
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.operational_policy import OperationalPolicy
from dynamic_lisl.f3_v2.candidate_source import replacement_inventory,RawCandidateBudget
from dynamic_lisl.f3_v2.batch_executor import BatchPhysicalValidator,BatchSafetyValidator
from dynamic_lisl.f3_v2.joint_action import JointAction,canonical_sha256,terminal_state_hash
from dynamic_lisl.f3_v2.joint_proposer import JointSearchBudget,BoundedJointProposer
from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256


def main():
    out=ROOT/'outputs'/('f3_v2_raw_batch_coverage_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir()
    nodes=tuple(sorted(c+str(i) for c,count in [('A',4),('B',4),('C',6),('D',6)] for i in range(count)))
    planes={n:int(n[0] in ('B','D')) for n in nodes}
    old=tuple((("A"+str(i),'D1'),("B"+str(i),'D1')) for i in range(4))
    windows=tuple(TerminalPairWindow('C'+str(i),'D1','D'+str(j),'D1',0,30) for i in range(6) for j in range(6))
    fixed=tuple(zip(nodes[:-1],nodes[1:]));frame='RAW_COVERAGE_SYNTHETIC'
    budget=JointSearchBudget(16,8,4,32,4,184,184,33)
    write_new_json(out/'fixture_contract.json',{'scope':'ENGINEERING_STRUCTURAL_ONLY','nodes':nodes,'old_bindings':old,
        'windows':[w.to_dict() for w in windows],'fixed_edges':fixed,'raw_caps':[32,32,64],'budget':budget.__dict__,
        'setup':[1,1,1],'traffic_present':False,'queue_present':False,'J_present':False,
        'rule_changes_by_this_task':False,'K_star_selection':False})
    ex=TerminalExecutor(nodes);ex.submit(tuple(Connect(*ends,30,0,0,0) for ends in old))
    physical=TerminalPairPhysicalFeasibility(TerminalPairCatalog(windows,planes))
    kwargs=dict(plane_by_satellite=planes,retarget_a_s=1,retarget_b_s=1,acquisition_s=1,observation_end_s=30)
    full=replacement_inventory(ex,physical,**kwargs)
    capped=replacement_inventory(ex,physical,**kwargs,raw_budget=RawCandidateBudget(32,32,64))
    validator=BatchSafetyValidator(BatchPhysicalValidator(physical,max_batch_replace=4,observation_end_s=30,
        absolute_time_frame_id=frame),fixed,OperationalPolicy('STRICT_CONNECTED'))
    proposer=BoundedJointProposer(validator,budget)
    pool=proposer.propose(ex,capped['members'])
    witness=tuple(next(m for m in full['members'] if m.old_binding==old[i] and
        m.new_terminal_pair==(('C'+str(i),'D1'),('D'+str(i),'D1'))) for i in range(4))
    action=JointAction(0,frame,terminal_state_hash(ex),canonical_sha256([]),witness)
    proof=validator.evaluate(ex,action)
    if not proof.accepted:raise AssertionError('FOUR_MEMBER_WITNESS_NOT_JOINT_SAFE:'+str(proof.reason))
    histogram=lambda members:{repr(ends):sum(m.old_binding==ends for m in members) for ends in old}
    report={'status':'STRUCTURAL_COVERAGE_COUNTEREXAMPLE_CONFIRMED' if len({m.old_binding for m in capped['members']})==1 and
        max(len(a.members) for a in pool.actions)==1 else 'COUNTEREXAMPLE_NOT_OBSERVED',
        'uncapped_physical_count':len(full['members']),'capped_count':len(capped['members']),
        'uncapped_old_binding_histogram':histogram(full['members']),'capped_old_binding_histogram':histogram(capped['members']),
        'final_pool_non_hold_count':len(pool.actions)-1,'final_pool_max_batch_size':max(len(a.members) for a in pool.actions),
        'uncapped_joint_safe_size4_witness':action.to_dict(),'witness_validation_sha256':proof.seal_sha256,
        'uncapped_available_maximum_under_action_size4':4,
        'result_interpretation':'canonical raw cutoff can exclude diversity before beam; witness is structural, not proof of the actual K* scene',
        'needs_human_freeze':'raw/singleton structural diversity policy and coverage standard before production adoption',
        'alternatives':['keep legacy lexical selection and disclose observed structural omissions',
            'predeclare old-binding/terminal-conflict diversity seed or round-robin while retaining same budgets; engineer and verify before freeze'],
        'recommended_next_step':'engineering-only result-blind diversity audit on approved natural scene; no J tuning and no automatic K hard-gate',
        'controller_performance_read':False,'scientific_rules_modified':False,'registered_P1_v2_started':False}
    write_new_json(out/'uncapped_source_audit.json',full['audit'])
    write_new_json(out/'capped_source_audit.json',capped['audit'])
    write_new_json(out/'pool.json',pool.public_document())
    write_new_json(out/'witness_validation.json',proof.to_dict())
    write_new_json(out/'report.json',report)
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    print({'status':report['status'],'output_dir':str(out),'registered_P1_v2_started':False})


if __name__=='__main__':main()
