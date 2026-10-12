"""Read-only tiny scoring diagnostics; no parameter tuning or rollout."""
from .snapshot_controllers import SnapshotBatchController


def audit_tiny_eta(engine,pool):
    if not 4<=len(engine.nodes)<=16 or len(pool.physical_singletons)>8:
        raise ValueError('TINY_SCORING_DIAGNOSTIC_ONLY')
    before=engine.canonical_state_sha256()
    decision=SnapshotBatchController('B3-v2',eta_aggregation='min').observe(engine,pool)
    members={a.batch_id:a for a in pool.actions}
    plans={a.batch_id:p for a,p in zip(pool.actions[1:],pool.plans)}
    records=[]
    for row in decision.metadata['candidates']:
        plan=plans[row['batch_id']];action=members[row['batch_id']]
        records.append({**row,'batch_size':len(action.members),
            'member_ids':[m.member_id for m in action.members],
            'member_eta':[r['usable_lifetime_s']/r['remaining_lifetime_s'] for r in plan.member_results],
            'member_readiness_and_lifetime':plan.member_results})
    if before!=engine.canonical_state_sha256():raise AssertionError('DIAGNOSTIC_CHANGED_LIVE_STATE')
    return {'scope':'TINY_ENGINEERING_CURRENT_SNAPSHOT_ONLY',
        'hold':decision.metadata['hold'],'candidates':records,'selected_batch_id':decision.action.batch_id,
        'selected_batch_size':len(decision.action.members),'root_before':before,'root_after':before,
        'advance_simulation_time':False,'multi_step_rollout':False,'future_realization_read':False,
        'eta_aggregation':'min; draft not frozen','coefficients_tuned':False,
        'interpretation':[
            'one short-lived member can reduce the whole batch score despite a larger ideal-topology benefit',
            'no explicit cardinality penalty; with equal eta the comparison is solely whole-graph deltaV',
            'proxy ordering is not an assertion about realized J or exact setup service loss']}
