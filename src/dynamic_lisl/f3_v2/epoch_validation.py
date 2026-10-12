"""Read-only v2 candidate-budget/resource evidence; never economic filtering."""
from .joint_action import canonical_sha256


def validate_epoch_inputs(engine, pool, source_audit, *, raw_budget, search_budget):
    """Validate existing outputs before observation, without choosing an action.

    Output caps are deliberately not claimed to bound uncapped source work.
    Failed observations are returned intact for persistence before STOP.
    """
    items = {}
    def check(name, observed, limit, passed):
        items[name] = {'observed': observed, 'frozen_limit': limit, 'pass': bool(passed)}
    raw_ids = pool.audit['raw_member_ids']
    static = source_audit.get('role') == 'STATIC_NO_CANDIDATE_SEARCH'
    counts = {'BBM': 0, 'MBB': 0} if static else source_audit.get('stratum_counts', {})
    ids = [] if static else source_audit.get('selected_member_ids', [])
    check('raw_source_identity', sorted(ids), raw_ids, sorted(ids) == raw_ids and len(set(ids)) == len(ids))
    for mode in ('BBM', 'MBB'):
        n = counts.get(mode)
        cap = getattr(raw_budget, mode + '_cap')
        check('raw_' + mode + '_cap', n, cap, type(n) is int and 0 <= n <= cap)
    check('raw_total_cap', len(raw_ids), raw_budget.total_cap,
        len(raw_ids) <= raw_budget.total_cap and set(counts) == {'BBM', 'MBB'}
        and all(type(v) is int for v in counts.values()) and sum(counts.values()) == len(raw_ids))
    check('singleton_cap', len(pool.audit['singleton_member_ids']), search_budget.singleton_cap,
        len(pool.audit['singleton_member_ids']) <= search_budget.singleton_cap)
    check('final_joint_pool_cap', len(pool.actions) - 1, search_budget.max_non_hold,
        0 <= len(pool.actions) - 1 <= search_budget.max_non_hold)
    check('rollout_pool_cap', len(pool.actions), search_budget.rollout_cap,
        1 <= len(pool.actions) <= search_budget.rollout_cap)
    for field, cap in (('joint_validation_calls', search_budget.validation_cap),
                       ('structural_expansions', search_budget.expansion_cap)):
        value = pool.audit[field]
        check(field, value, cap, type(value) is int and 0 <= value <= cap)
    roots = [action.decision_root_sha256 for action in pool.actions]
    root = engine.decision_root_sha256()
    check('same_decision_root', roots, root, pool.root_sha256 == root and all(v == root for v in roots))
    counts_by_action = [len(a.members) for a in pool.actions]
    check('HOLD_and_batch_permissions', counts_by_action, search_budget.max_members,
        bool(counts_by_action) and counts_by_action[0] == 0
        and all(1 <= n <= search_budget.max_members for n in counts_by_action[1:]))
    structural = []
    for action in pool.actions:
        footprints = [m.footprint for m in action.members]
        structural.append(action.decision_time_s == engine.now
            and action.absolute_time_frame_id == engine.absolute_time_frame_id
            and len({m.old_binding for m in action.members}) == len(action.members)
            and all(m.member_id in raw_ids for m in action.members)
            and all(not a & b for i, a in enumerate(footprints) for b in footprints[i + 1:]))
    check('resource_independence_and_current_time', structural, 'ALL_TRUE', all(structural))
    expected = canonical_sha256({'root_sha256': pool.root_sha256,
        'identities': [a.identity_document() for a in pool.actions], 'audit': pool.audit})
    check('proposal_identity_order_hash', pool.pool_sha256, expected,
        pool.pool_sha256 == expected and all(a.joint_proposal_set_sha256 == expected for a in pool.actions))
    return {'status': 'PASS' if all(x['pass'] for x in items.values()) else 'FAIL',
        'time_s': engine.now, 'items': items,
        'source_output_caps_do_not_bound_screening': True,
        'economic_scores_read': False}
