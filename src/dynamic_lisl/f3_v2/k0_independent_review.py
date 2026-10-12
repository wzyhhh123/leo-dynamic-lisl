"""Bounded, independently enumerated K0 evidence checks; never selects K*.

Uses the original Gate B/C as the physical authority. It does not call the K0
producer, candidate source, matching solver or topology builder. Exhaustive
subset proofs are suitable for tiny fixtures; budget exhaustion is UNKNOWN.
The caller must separately bind the catalogue to approved physical asset hashes.
"""
from dataclasses import dataclass, replace
from fractions import Fraction
import itertools
import math
import time
from ..terminal_executor import TerminalExecutor, Connect, pair
from .batch_executor import BatchPhysicalValidator
from .joint_action import BatchReplaceMember, JointAction, canonical_sha256, terminal_state_hash
from .k0_support import verify_snapshot_support


@dataclass(frozen=True)
class IndependentReviewBudget:
    physical_evaluations: int
    subset_evaluations: int
    wall_s: float

    def __post_init__(self):
        if any(type(v) is not int or v < 1 for v in
               (self.physical_evaluations, self.subset_evaluations)):
            raise ValueError('EXPLICIT_INDEPENDENT_REVIEW_COUNT_BUDGET_REQUIRED')
        if type(self.wall_s) not in (int, float) or not math.isfinite(self.wall_s) or self.wall_s <= 0:
            raise ValueError('EXPLICIT_INDEPENDENT_REVIEW_WALL_BUDGET_REQUIRED')


class _Unknown(Exception):
    pass


def _equal(left, right, reason):
    if canonical_sha256(left) != canonical_sha256(right):
        raise ValueError(reason)


def _independent_objective(selected, planes):
    counts = {p: 0 for p in planes}
    for row in selected:
        for p in row['plane_pair']:
            counts[p] += 1
    lives = [Fraction.from_float(row['L_usable_within_horizon_s']) for row in selected]
    return (max(counts.values()) - min(counts.values()),
            -len({tuple(r['plane_pair']) for r in selected}),
            -sum(lives, Fraction()), -min(lives, default=Fraction()),
            tuple(pair(*r['endpoints']) for r in selected))


def review_point(row, supports, *, nodes, fixed_edges, plane_by_satellite,
                 physical_layer, setup, input_hashes, budget):
    """Recreate physical inputs and uncapped enumeration before tiny exact proof.

    PASS certifies this supplied point, not all K/time strata, asset generation,
    batch compatibility diagnostics, a human freeze or formal K0/K1 acceptance.
    """
    if not isinstance(budget, IndependentReviewBudget):
        raise TypeError('EXPLICIT_INDEPENDENT_REVIEW_BUDGET_REQUIRED')
    started = time.perf_counter()
    progress = {'physical_evaluations': 0, 'subset_evaluations': 0,
                'content_consistency': False, 'idle_inventory_replayed': False,
                'uncapped_replacements_replayed': False, 'matching_independently_proved': False,
                'topology_independently_proved': False}
    stage = 'INPUT_BINDING'
    def tick(kind):
        if time.perf_counter() - started >= budget.wall_s:
            raise _Unknown('INDEPENDENT_REVIEW_WALL_BUDGET')
        name = kind + '_evaluations'
        if progress[name] >= getattr(budget, name):
            raise _Unknown('INDEPENDENT_REVIEW_' + kind.upper() + '_BUDGET')
        progress[name] += 1
    result = {'Gate_K0_PASS': False, 'K_star_selected': False,
              'formal_P1_started': False, 'controller_or_traffic_invoked': False,
              'asset_generation_verified': False,
              'physical_asset_hash_authorization_required_separately': True}
    try:
        verify_snapshot_support(row, supports)
        progress['content_consistency'] = True
        state = row['canonical_structural_state']
        for value, recorded, name in ((sorted(nodes), state['nodes'], 'NODES'),
                (fixed_edges, state['fixed_edges'], 'FIXED_EDGES'),
                (plane_by_satellite, state['plane_by_satellite'], 'PLANE_MAPPING'),
                (setup, state['setup'], 'SETUP'), (input_hashes, row['input_hashes'], 'INPUT_HASHES')):
            _equal(value, recorded, 'INDEPENDENT_REVIEW_CONTEXT_MISMATCH:' + name)
        ex = TerminalExecutor(nodes)
        ex.advance(row['time_s'])
        idle_before = terminal_state_hash(ex)
        windows = physical_layer.catalog.terminal_pair_candidates(ex.now, ex.satellite_ids)
        idle = []
        stage = 'IDLE_CATALOGUE_REPLAY'
        for w in windows:
            endpoints = pair(w.endpoint_a, w.endpoint_b)
            planes = tuple(sorted(plane_by_satellite[t[0]] for t in endpoints))
            if planes[0] == planes[1]:
                continue
            tick('physical')
            p = physical_layer.evaluate(ex, *endpoints, retarget_a=setup['retarget_a_s'],
                retarget_b=setup['retarget_b_s'], acquisition=setup['acquisition_s'])
            if p['accepted']:
                ready = p['geometry']['ready_time']
                idle.append({'endpoints': endpoints, 'plane_pair': planes, 'ready_time_s': ready,
                    'observed_end_s': w.end_s, 'physical_end_s': None if w.right_censored else w.end_s,
                    'observation_cutoff_s': 600,
                    'censor_status': 'RIGHT_CENSORED_AT_600' if w.right_censored else 'NATURAL_END_KNOWN',
                    'L_usable_within_horizon_s': max(0.0, min(w.end_s, 600) - ready)})
        idle.sort(key=lambda e: e['endpoints'])
        _equal(idle, supports['lifetime']['idle_inventory'], 'INDEPENDENT_IDLE_CATALOGUE_MISMATCH')
        _equal(terminal_state_hash(ex), idle_before, 'INDEPENDENT_IDLE_REPLAY_MUTATED_ROOT')
        progress['idle_inventory_replayed'] = True
        solver = supports['solver']
        if solver['status'] == 'UNKNOWN':
            raise _Unknown('SUPPLIED_SOLVER_UNKNOWN')
        if solver['status'] == 'EXACT':
            edge_map = {e['endpoints']: e for e in idle}
            bindings = tuple(pair(*b) for b in solver['bindings'])
            ex.submit([Connect(*b, edge_map[b]['observed_end_s'], 0., 0., 0.) for b in bindings])
            _equal(ex.snapshot(), supports['physical']['terminal_state'], 'INDEPENDENT_PREESTABLISHED_STATE_MISMATCH')
            root_hash = terminal_state_hash(ex)
            stage = 'UNCAPPED_REPLACE_REPLAY'
            frame = 'STRUCTURAL_RAW_SOURCE'
            validator = BatchPhysicalValidator(physical_layer, max_batch_replace=1,
                observation_end_s=600, absolute_time_frame_id=frame)
            entries = []
            rejected = []
            for old in sorted(ex.links.values(), key=lambda link: link.endpoints):
                if old.draining or old.release_owner:
                    continue
                for w in windows:
                    new = pair(w.endpoint_a, w.endpoint_b)
                    if plane_by_satellite[new[0][0]] == plane_by_satellite[new[1][0]] or new == old.endpoints:
                        continue
                    tick('physical')
                    identity = {'time_s': ex.now, 'old': old.endpoints, 'new': new}
                    m = BatchReplaceMember('V2-RAW-' + canonical_sha256(identity), 0, old.endpoints, new,
                        setup['retarget_a_s'], setup['retarget_b_s'], setup['acquisition_s'])
                    p = validator.evaluate(ex, JointAction(ex.now, frame, root_hash, canonical_sha256([]), (m,)))
                    if p.accepted:
                        entries.append((m, p.member_results[0]))
                    else:
                        rejected.append({'member_id': m.member_id, 'reason': p.reason})
            def rank(entry):
                m, r = entry
                return (-r['usable_lifetime_s'], int(r['window'].get('plane_gap') or 0),
                        m.old_binding, m.new_terminal_pair, m.member_id)
            ordered = []
            for mode in ('MBB', 'BBM'):
                ordered.extend(sorted((entry for entry in entries if entry[1]['transition_mode'] == mode), key=rank))
            members = [replace(m, canonical_index=i).to_dict() for i, (m, _) in enumerate(ordered)]
            expected = {'schema': 'f3_v2_raw_source_v1', 'root_terminal_sha256': root_hash, 'time_s': ex.now,
                'uncapped': True, 'uncapped_physical_count': len(entries),
                'selected_member_ids': [m['member_id'] for m in members], 'members': members,
                'stratum_counts': {mode: sum(r['transition_mode'] == mode for _, r in ordered) for mode in ('MBB', 'BBM')},
                'physical_rejections': rejected, 'performance_input_read': False}
            _equal(expected, supports['inventory'], 'INDEPENDENT_UNCAPPED_REPLACE_MISMATCH')
            _equal(terminal_state_hash(ex), root_hash, 'INDEPENDENT_REPLACE_REPLAY_MUTATED_ROOT')
            progress['uncapped_replacements_replayed'] = True
        stage = 'EXHAUSTIVE_MATCHING_PROOF'
        matching_best = ()
        terminal_upper = len({t for e in idle for t in e['endpoints']}) // 2
        for size in range(1, min(len(idle), terminal_upper) + 1):
            for subset in itertools.combinations(idle, size):
                tick('subset')
                terminals = [t for e in subset for t in e['endpoints']]
                if len(set(terminals)) == 2 * size:
                    candidate = tuple(e['endpoints'] for e in subset)
                    if size > len(matching_best) or size == len(matching_best) and candidate < matching_best:
                        matching_best = candidate
        _equal(matching_best, state['matching']['bindings'], 'INDEPENDENT_MATCHING_CERTIFICATE_MISMATCH')
        progress['matching_independently_proved'] = True
        if solver['status'] == 'EXACT_INFEASIBLE' and solver['solver_role'] == 'EXACT_TERMINAL_MATCHING_UPPER_BOUND':
            if len(matching_best) >= row['K']:
                raise ValueError('INDEPENDENT_INFEASIBILITY_BOUND_INVALID')
            progress['topology_independently_proved'] = True
        else:
            stage = 'EXHAUSTIVE_TOPOLOGY_PROOF'
            best = None
            for subset in itertools.combinations(idle, row['K']):
                tick('subset')
                terminals = [t for e in subset for t in e['endpoints']]
                satellite_pairs = [tuple(t[0] for t in e['endpoints']) for e in subset]
                if len(set(terminals)) != 2 * row['K'] or len(set(satellite_pairs)) != row['K']:
                    continue
                key = _independent_objective(subset, sorted(set(plane_by_satellite.values())))
                if best is None or key < best:
                    best = key
            if solver['status'] == 'EXACT_INFEASIBLE':
                if best is not None:
                    raise ValueError('INDEPENDENT_TOPOLOGY_NOT_INFEASIBLE')
            elif best is None:
                raise ValueError('INDEPENDENT_TOPOLOGY_NO_FEASIBLE_SOLUTION')
            else:
                recorded = [best[0], best[1], str(best[2]), str(best[3]), best[4]]
                _equal(recorded, solver['lexicographic_objective'], 'INDEPENDENT_LEXICOGRAPHIC_OPTIMUM_MISMATCH')
                _equal(best[4], solver['bindings'], 'INDEPENDENT_CANONICAL_OPTIMUM_MISMATCH')
            progress['topology_independently_proved'] = True
        result.update(status='INDEPENDENT_POINT_REVIEW_PASS', reason=None)
    except _Unknown as exc:
        result.update(status='INDEPENDENT_POINT_REVIEW_UNKNOWN', reason=str(exc))
    except Exception as exc:
        result.update(status='INDEPENDENT_POINT_REVIEW_FAIL_STOP', reason=str(exc), exception_type=type(exc).__name__)
    result.update(stage=stage, progress=progress, wall_s=time.perf_counter() - started)
    return result
