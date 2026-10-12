"""Experimental structural policy only; never imported by registered runtime.

The closure authorization permits engineering tests, not scientific freezing.
Clarifications: shortage backfill continues the same per-group queues/cover;
safe seeds are unioned with the original top-W safe beam rows at each size.
All physical, joint and safety decisions still use the original validators.
"""
from dataclasses import replace
import time

from ..terminal_executor import pair
from .batch_executor import BatchPhysicalValidator
from .joint_action import BatchReplaceMember, JointAction, canonical_sha256, terminal_state_hash
from .joint_proposer import JointProposalPool

POLICY_ID = 'RR_STRUCTURAL_SCOUT256_RAW64_SINGLE16_SEED4_V1'


def physical_key(item):
    m, r = item
    return (-r['usable_lifetime_s'], int(r['window'].get('plane_gap') or 0),
            m.old_binding, m.new_terminal_pair, m.member_id)


def old_order(executor, epoch_index):
    if type(epoch_index) is not int or epoch_index < 0:
        raise ValueError('EXPLICIT_COMMON_NONNEGATIVE_EPOCH_INDEX_REQUIRED')
    old = tuple(sorted(l.endpoints for l in executor.links.values() if not l.draining and not l.release_owner))
    offset = epoch_index % len(old) if old else 0
    return old, old[offset:] + old[:offset]


def take_round_robin(buckets, order, count, cover=None):
    chosen = []
    while len(chosen) < count:
        any_taken = False
        for old in order:
            bucket = buckets.get(old, [])
            if not bucket:
                continue
            index = 0
            if cover is not None and old not in cover['old']:
                index = next((i for i, (m, _) in enumerate(bucket)
                              if not m.footprint & cover['terminals']), 0)
            item = bucket.pop(index)
            m, _ = item
            if cover is not None and old not in cover['old'] and not m.footprint & cover['terminals']:
                cover['old'].add(old)
                cover['terminals'].update(m.footprint)
            chosen.append(item)
            any_taken = True
            if len(chosen) == count:
                break
        if not any_taken:
            break
    return chosen


def group_buckets(entries, mode):
    buckets = {}
    for item in sorted(entries, key=physical_key):
        if item[1]['transition_mode'] == mode:
            buckets.setdefault(item[0].old_binding, []).append(item)
    return buckets


def scout(executor, physical_layer, *, plane_by_satellite, epoch_index,
          retarget_a_s, retarget_b_s, acquisition_s, observation_end_s):
    started = time.perf_counter()
    before = terminal_state_hash(executor)
    canonical_old, visit_old = old_order(executor, epoch_index)
    windows = tuple(sorted(physical_layer.catalog.terminal_pair_candidates(executor.now, executor.satellite_ids),
        key=lambda w: (-w.end_s, abs(plane_by_satellite[w.endpoint_a[0]] - plane_by_satellite[w.endpoint_b[0]]),
                       pair(w.endpoint_a, w.endpoint_b))))
    if len({pair(w.endpoint_a, w.endpoint_b) for w in windows}) != len(windows):
        raise ValueError('MULTIPLE_CURRENT_WINDOWS_PER_PAIR_SPECIFICATION_REQUIRED')
    frame = 'ENGINEERING_SCOUT_POLICY'
    validator = BatchPhysicalValidator(physical_layer, max_batch_replace=1,
        observation_end_s=observation_end_s, absolute_time_frame_id=frame)
    rows, accepted = [], []
    physical_calls = 0
    physical_wall = 0.
    offsets = {old: q * len(windows) // len(canonical_old) for q, old in enumerate(canonical_old)}
    if canonical_old and windows:
        for round_index in range(len(windows)):
            for old in visit_old:
                if len(rows) == 256:
                    break
                window = windows[(offsets[old] + round_index) % len(windows)]
                new = pair(window.endpoint_a, window.endpoint_b)
                identity = {'time_s': executor.now, 'old': old, 'new': new}
                member = BatchReplaceMember('V2-RAW-' + canonical_sha256(identity), 0, old, new,
                    retarget_a_s, retarget_b_s, acquisition_s)
                row = {'member_id': member.member_id, 'old': old, 'new': new,
                       'visit_index': len(rows), 'physical_called': False}
                if new == old:
                    row.update(accepted=False, reason='EXACT_PHYSICAL_NOOP')
                elif plane_by_satellite[new[0][0]] == plane_by_satellite[new[1][0]]:
                    row.update(accepted=False, reason='INTRA_PLANE_EXCLUDED')
                else:
                    action = JointAction(executor.now, frame, before, canonical_sha256([]), (member,))
                    start = time.perf_counter()
                    plan = validator.evaluate(executor, action)
                    physical_wall += time.perf_counter() - start
                    physical_calls += 1
                    row.update(physical_called=True, accepted=plan.accepted, reason=plan.reason)
                    if plan.accepted:
                        metadata = plan.member_results[0]
                        accepted.append((member, metadata))
                        row.update(transition_mode=metadata['transition_mode'], ready_time_s=metadata['ready_time_s'])
                rows.append(row)
            if len(rows) == 256:
                break
    selected = []
    for mode in ('MBB', 'BBM'):
        selected += take_round_robin(group_buckets(accepted, mode), visit_old, 32)
    members = tuple(replace(m, canonical_index=i) for i, (m, _) in enumerate(selected))
    if terminal_state_hash(executor) != before:
        raise AssertionError('ENGINEERING_SCOUT_MUTATED_LIVE_ROOT')
    domain_size = len(canonical_old) * len(windows)
    audit = {'policy_id': POLICY_ID, 'scope': 'ENGINEERING_ONLY_NOT_FROZEN', 'epoch_index': epoch_index,
        'root_terminal_sha256': before, 'old_visit_order': visit_old,
        'current_window_metadata_sha256': canonical_sha256([w.to_dict() for w in windows]),
        'metadata_domain_size': domain_size, 'scout_visits': len(rows), 'source_physical_calls': physical_calls,
        'unvisited_identity_count': domain_size - len(rows), 'full_metadata_domain_visited': len(rows) == domain_size,
        'outside_domain_status': 'UNKNOWN_OUTSIDE_SCOUTED_DOMAIN' if len(rows) < domain_size else 'DOMAIN_EXHAUSTED',
        'visited_rows': rows, 'selected_member_ids': [m.member_id for m in members],
        'stratum_counts': {s: sum(r['transition_mode'] == s for _, r in selected) for s in ('MBB', 'BBM')},
        'accepted_scouted_count': len(accepted), 'old_binding_visited_count': len({tuple(tuple(e) for e in r['old']) for r in rows}),
        'raw_output_cap_is_compute_cap': False, 'performance_input_read': False}
    return {'members': members, 'audit': audit, 'raw_source_sha256': canonical_sha256(audit),
            'timing': {'source_wall_s': time.perf_counter() - started, 'source_physical_validation_wall_s': physical_wall}}


class StructuralPolicyProbeProposer:
    """Independent bounded probe, leaving the registered proposer untouched."""
    def __init__(self, validator, budget, *, epoch_index):
        self.validator, self.budget, self.epoch_index = validator, budget, epoch_index
        if (budget.singleton_cap, budget.per_stratum_slots, budget.beam_width) != (16, 8, 4):
            raise ValueError('EXACT_SCOUT_POLICY_BUDGET_REQUIRED')
        if budget.max_members not in (1, 4):
            raise ValueError('ONLY_REGISTERED_BATCH1_OR_BATCH4_PERMISSION')

    def propose(self, executor, members, *, decision_root_sha256=None):
        before = terminal_state_hash(executor)
        root = before if decision_root_sha256 is None else decision_root_sha256
        _, order = old_order(executor, self.epoch_index)
        members = tuple(members)
        if len({m.member_id for m in members}) != len(members) or len(members) > 64:
            raise ValueError('UNIQUE_RAW_MEMBERS_WITHIN_64_REQUIRED')
        frame = self.validator.physical_validator.absolute_time_frame_id
        action = lambda ms: JointAction(executor.now, frame, root, canonical_sha256([]), tuple(ms))
        screened, pruned = [], []
        for m in sorted(members, key=lambda m: m.member_id):
            p = self.validator.physical_validator.evaluate(executor, action((m,)), decision_root_sha256=root)
            if p.accepted:
                screened.append((m, p.member_results[0]))
            else:
                pruned.append({'member_ids': [m.member_id], 'reason': p.reason, 'stage': 'PHYSICAL'})
        buckets = {s: group_buckets(screened, s) for s in ('MBB', 'BBM')}
        cover = {'old': set(), 'terminals': set()}
        chosen_by_mode = {s: take_round_robin(buckets[s], order, 8, cover) for s in ('MBB', 'BBM')}
        for mode in ('MBB', 'BBM'):
            missing = 16 - sum(len(v) for v in chosen_by_mode.values())
            chosen_by_mode[mode] += take_round_robin(buckets[mode], order, missing, cover)
        chosen = [item for s in ('MBB', 'BBM') for item in chosen_by_mode[s]]
        chosen = [(replace(m, canonical_index=i), r) for i, (m, r) in enumerate(chosen)]
        selected = tuple(m for m, _ in chosen)
        lifetime = {m.canonical_index: r['usable_lifetime_s'] for m, r in chosen}
        key = lambda ms: (-min(lifetime[m.canonical_index] for m in ms),
                          -sum(lifetime[m.canonical_index] for m in ms), tuple(m.canonical_index for m in ms))
        evaluated, seed_ids = {}, set()
        validation_count, expansions, cache_hits = 0, 0, 0
        exhausted = False
        def evaluate(ms):
            nonlocal validation_count, expansions, cache_hits, exhausted
            ids = tuple(m.canonical_index for m in ms)
            if ids in evaluated:
                cache_hits += 1
                return evaluated[ids]
            if validation_count >= self.budget.validation_cap or expansions >= self.budget.expansion_cap:
                exhausted = True
                return None
            validation_count += 1
            expansions += 1
            p = self.validator.evaluate(executor, action(ms), decision_root_sha256=root)
            evaluated[ids] = p
            if not p.accepted:
                pruned.append({'member_ids': [m.member_id for m in ms], 'reason': p.reason, 'stage': 'JOINT'})
            return p
        singleton_plans = []
        for m in selected:
            p = evaluate((m,))
            if p is not None and p.accepted:
                singleton_plans.append(p)
        if self.budget.max_members == 4:
            anchors, olds = [], set()
            for m in selected:
                if m.old_binding not in olds:
                    anchors.append(m)
                    olds.add(m.old_binding)
                    if len(anchors) == 4:
                        break
            for anchor in anchors:
                prefix = [anchor]
                for m in selected:
                    if m.old_binding in {x.old_binding for x in prefix} or any(m.footprint & x.footprint for x in prefix):
                        continue
                    prefix.append(m)
                    seed_ids.add(tuple(sorted(x.canonical_index for x in prefix)))
                    if len(prefix) == 4:
                        break
            for size in (4, 3, 2):
                for ids in sorted(i for i in seed_ids if len(i) == size)[:4]:
                    evaluate(tuple(selected[i] for i in ids))
        safe_by_size = {}
        for ids, p in evaluated.items():
            if len(ids) > 1 and p.accepted:
                safe_by_size.setdefault(len(ids), {})[ids] = p
        prefixes = sorted(((m,) for m in selected), key=key)[:self.budget.beam_width]
        for size in range(2, self.budget.max_members + 1):
            next_prefixes, safe = [], {}
            for prefix in prefixes:
                for m in selected:
                    if m.canonical_index <= prefix[-1].canonical_index:
                        continue
                    ms = prefix + (m,)
                    if any(m.footprint & x.footprint for x in prefix):
                        pruned.append({'member_ids': [x.member_id for x in ms], 'reason': 'TERMINAL_FOOTPRINT_CONFLICT', 'stage': 'RESOURCE_PROOF'})
                        continue
                    p = evaluate(ms)
                    if p is None:
                        break
                    if p.commands:
                        next_prefixes.append(ms)
                    if p.accepted:
                        safe[tuple(x.canonical_index for x in ms)] = p
                if exhausted:
                    break
            for p in sorted(safe.values(), key=lambda p: key(p.action.members))[:self.budget.beam_width]:
                safe_by_size.setdefault(size, {})[tuple(x.canonical_index for x in p.action.members)] = p
            prefixes = sorted(next_prefixes, key=key)[:self.budget.beam_width]
            if not prefixes or exhausted:
                break
        queues = {s: sorted(v.values(), key=lambda p: key(p.action.members)) for s, v in sorted(safe_by_size.items())}
        output = list(singleton_plans)
        while any(queues.values()) and len(output) < self.budget.max_non_hold:
            for size in queues:
                if queues[size] and len(output) < self.budget.max_non_hold:
                    output.append(queues[size].pop(0))
        output.sort(key=lambda p: (len(p.action.members), tuple(m.canonical_index for m in p.action.members)))
        hold = action(())
        identities = [hold.identity_document()] + [p.action.identity_document() for p in output]
        audit = {'policy_id': POLICY_ID, 'scope': 'ENGINEERING_ONLY_NOT_FROZEN',
            'raw_member_ids': sorted(m.member_id for m in members), 'physical_screened_count': len(screened),
            'singleton_member_ids': [m.member_id for m in selected], 'pruned': pruned,
            'singleton_safety_rejections_are_expandable': True, 'joint_validation_calls': validation_count,
            'structural_expansions': expansions, 'cache_hits_same_index_tuple': cache_hits,
            'evaluated_index_tuples': list(evaluated), 'structural_seed_index_tuples': sorted(seed_ids, key=lambda i: (-len(i), i)),
            'budget_exhausted': exhausted, 'beam_width': 4,
            'coverage_by_size': {str(s): sum(len(p.action.members) == s for p in output) for s in range(1, self.budget.max_members + 1)},
            'performance_inputs_read': False, 'maximum_optimality_claim': False}
        digest = canonical_sha256({'root_sha256': root, 'identities': identities, 'audit': audit})
        actions = (replace(hold, joint_proposal_set_sha256=digest),) + tuple(replace(p.action, joint_proposal_set_sha256=digest) for p in output)
        plans = tuple(replace(p, action=a) for p, a in zip(output, actions[1:]))
        if terminal_state_hash(executor) != before:
            raise AssertionError('ENGINEERING_PROPOSER_MUTATED_LIVE_ROOT')
        return JointProposalPool(root, digest, actions, plans, audit, selected)
