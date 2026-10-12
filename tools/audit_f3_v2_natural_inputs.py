"""Read-only natural K0 asset audit; no matching, topology or controller run."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from dynamic_lisl.terminal_executor import TerminalExecutor
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from check_f3_v2_engineering import authorized_planning_revision

GEOMETRY = 'outputs/geometry_20260921T053240_016088Z'
VISIBILITY = 'outputs/visibility_20260921T055451_308214Z'
GATE_C = 'outputs/gate_c_simplified_20260922T064019_313843Z'
BASELINE = 'outputs/f3_v2_engineering_20261008T125056_858471Z/historical_integrity_before.json'
OVERLAY = 'configs/gate_f3_runtime_phase1_overlay_v1.json'
OVERLAY_CANONICAL = '605220d3437a1580da9f87b68d71fbe607d9646c75a16e715281bed39bae73f4'
EPOCH = '01 Jan 2026 00:00:00.00'
TIMES = tuple(range(0, 600, 30))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def canonical(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def local_path(root, relative):
    """Accept historical Windows separators, never an absolute or escaping path."""
    if not isinstance(relative, str):
        raise ValueError('EXACT_LOCAL_PATH_REQUIRED')
    relative = relative.replace('\\', '/')
    p = Path(relative)
    if p.is_absolute() or ':' in relative or '..' in p.parts:
        raise ValueError('PATH_OUTSIDE_PROJECT')
    resolved = (root / p).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise ValueError('PATH_OUTSIDE_PROJECT')
    return resolved


def verify_hashes(root, mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError('NONEMPTY_HASH_MAP_REQUIRED')
    for rel, expected in mapping.items():
        p = local_path(root, rel)
        if not p.is_file() or digest(p) != expected:
            raise ValueError('EXACT_HASH_MISMATCH:' + rel)
    return len(mapping)


def validate_metadata(meta, subset):
    required = {'frame': 'TEMEOfDate', 'propagator': 'SGP4', 'gravity': 'WGS72',
        'epoch_utc': EPOCH, 'position_unit': 'km', 'velocity_unit': 'km/s',
        'distance_unit': 'km', 'time_unit': 's', 'satellite_count': 720,
        'start_s': 0., 'stop_s': 600., 'step_s': 30, 'synthetic_tle': True,
        'max_range_km': 5000}
    if any(meta.get(k) != v for k, v in required.items()):
        raise ValueError('GEOMETRY_CONTRACT_MISMATCH')
    expected = ['X%d_%d' % (p, s) for p in range(18) for s in range(1, 41)]
    if meta.get('sat_ids') != expected or meta.get('plane_ids') != [p for p in range(18) for _ in range(40)]:
        raise ValueError('PARENT_ID_PLANE_MAPPING_MISMATCH')
    if (subset.get('parent_indices') != list(range(160))
        or subset.get('satellite_ids') != expected[:160]
        or subset.get('plane_ids') != [0, 1, 2, 3]
        or subset.get('frame') != meta['frame'] or subset.get('epoch_utc') != EPOCH):
        raise ValueError('SUBSET_ID_FRAME_MAPPING_MISMATCH')
    return expected[:160]


def validate_windows(records, parent_records, parent_ids, nodes, epsilon):
    mapping = {n: int(n.split('_')[0][1:]) for n in nodes}
    parents = {(parent_ids[r['i']], parent_ids[r['j']], r['start_s'], r['end_s']): r
               for r in parent_records}
    right = natural = 0
    for r in records:
        a, b = r['sat_a'], r['sat_b']
        start, end = r['start_s'], r['end_s']
        if (a not in mapping or b not in mapping or a == b or mapping[a] == mapping[b]
            or r['terminal_a'] not in ('D1', 'D2') or r['terminal_b'] not in ('D1', 'D2')
            or not all(math.isfinite(v) for v in (start, end)) or not 0 <= start < end <= 600):
            raise ValueError('INVALID_TERMINAL_WINDOW')
        key = (a, b, r['parent_start_s'], r['parent_end_s'])
        parent = parents.get(key)
        if parent is None or not parent['start_s'] <= start < end <= parent['end_s']:
            raise ValueError('TERMINAL_WINDOW_PARENT_MISMATCH')
        if r['plane_gap'] != abs(mapping[a] - mapping[b]) or parent['plane_gap'] != r['plane_gap']:
            raise ValueError('WINDOW_PLANE_GAP_MISMATCH')
        if r['right_censored']:
            if not parent['right_censored'] or abs(end - 600.) > epsilon:
                raise ValueError('RIGHT_CENSOR_HORIZON_MISMATCH')
            right += 1
        else:
            natural += 1
        if r['left_censored'] and (not parent['left_censored'] or abs(start) > epsilon):
            raise ValueError('LEFT_CENSOR_HORIZON_MISMATCH')
    # Original catalogue enforces bilateral pair identity and non-overlap.
    catalog = TerminalPairCatalog.from_records(records, mapping)
    return catalog, {'terminal_window_count': len(records), 'right_censored_windows': right,
        'known_terminal_pair_expiry_windows': natural,
        'censor_boundary_tolerance_s': epsilon}


def verify_executor_overlay(root, baseline, protected):
    path = 'src/dynamic_lisl/terminal_executor.py'
    parent = baseline[path]
    current = digest(root / path)
    if current == parent:
        return {'classification': 'EXACT_FROZEN_EXECUTOR', 'parent_hash': parent, 'current_hash': current}
    verify_hashes(root, {OVERLAY: protected[OVERLAY]})
    overlay = json.loads((root / OVERLAY).read_text(encoding='utf-8'))
    if (overlay.get('canonical_sha256') != OVERLAY_CANONICAL
        or canonical({k: v for k, v in overlay.items() if k != 'canonical_sha256'}) != OVERLAY_CANONICAL
        or overlay.get('status') != 'PASS'
        or overlay.get('frozen_scientific_semantics_changed') is not False
        or overlay.get('parent_code_hashes', {}).get(path) != parent
        or overlay.get('optimized_code_hashes', {}).get(path) != current):
        raise ValueError('UNAUTHORIZED_EXECUTOR_SUCCESSOR')
    evidence = overlay['equivalence_evidence']
    verify_hashes(root, {evidence['report']: evidence['report_sha256']})
    if protected.get(evidence['report']) != evidence['report_sha256']:
        raise ValueError('EXECUTOR_EVIDENCE_NOT_IN_HISTORICAL_BASELINE')
    report = json.loads(local_path(root, evidence['report']).read_text(encoding='utf-8'))
    if (report.get('pass') is not True or report.get('proposal_equivalence') is not True
        or report.get('frozen_inputs_unchanged') is not True
        or report.get('status') != 'GATE_F3_RUNTIME_PHASE1_PASS'):
        raise ValueError('EXECUTOR_SUPPORTING_EQUIVALENCE_NOT_PASS')
    return {'classification': 'EXPLICIT_HISTORICAL_PHASE1_RUNTIME_OVERLAY',
        'parent_hash': parent, 'current_hash': current, 'overlay': OVERLAY,
        'overlay_sha256': digest(root / OVERLAY), 'supporting_evidence': evidence}


def run_audit(root):
    root = Path(root).resolve()
    read = lambda rel: json.loads((root / rel).read_text(encoding='utf-8'))
    records = lambda rel: [json.loads(line) for line in (root / rel).read_text(encoding='utf-8').splitlines() if line]
    protected = read(BASELINE)['files']
    before = {rel: digest(root / rel) for rel in protected}
    differences = [rel for rel, old in protected.items() if before[rel] != old
        and not authorized_planning_revision(root, rel, old, before[rel])]
    if differences:
        raise ValueError('HISTORICAL_ASSETS_CHANGED:' + ','.join(differences))
    checks = {}
    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            raise ValueError(name)
    check('Gate_C_historical_artifact_hashes', verify_hashes(root,
        {GATE_C + '/' + p: h for p, h in read(GATE_C + '/hashes.json').items()}) == 14)
    check('visibility_historical_artifact_hashes', verify_hashes(root,
        {VISIBILITY + '/' + p: h for p, h in read(VISIBILITY + '/hashes.json').items()}) == 13)
    acceptance = read('configs/gate_a_acceptance_v0.3.json')
    verify_hashes(root, acceptance['asset_hashes'])
    check('explicit_Gate_A_common_mode_acceptance', acceptance['status'] == 'ACCEPTED_FOR_GATE_B'
        and acceptance['absolute_teme_orientation'] == 'DOCUMENTED_COMMON_MODE_OFFSET_NON_BLOCKING')
    inputs = read(GATE_C + '/inputs.json')
    verify_hashes(root, inputs['code_hashes']); verify_hashes(root, inputs['input_hashes'])
    checks['Gate_C_generation_inputs_and_sources_exact'] = True
    base = read('configs/gate_c_frozen_baseline_hashes.json')['files']
    executor_chain = verify_executor_overlay(root, base, protected)
    verify_hashes(root, {p: h for p, h in base.items() if p != 'src/dynamic_lisl/terminal_executor.py'})
    checks['Gate_B_baseline_or_explicit_executor_overlay'] = True
    meta = read(GEOMETRY + '/metadata.json'); subset = read(VISIBILITY + '/subset_160/manifest.json')
    nodes = validate_metadata(meta, subset)
    check('subset_exact_parent_asset', Path(subset['parent_asset']).resolve() == (root / GEOMETRY).resolve())
    verify_hashes(root, {GEOMETRY + '/positions.npz': subset['parent_positions_sha256'],
        VISIBILITY + '/intervals.jsonl': subset['parent_intervals_sha256'],
        'data/raw/sgp4_x720/constellation.tle': meta['tle_sha256'],
        'data/raw/sgp4_x720/manifest.json': meta['manifest_sha256']})
    with np.load(root / GEOMETRY / 'positions.npz', allow_pickle=False) as parent, \
         np.load(root / VISIBILITY / 'subset_160/positions.npz', allow_pickle=False) as child:
        for key in ('position_km', 'velocity_km_s'):
            check('exact_parent_' + key, np.array_equal(parent[key][:, subset['parent_indices'], :], child[key])
                and np.isfinite(child[key]).all())
        check('exact_time_grid', np.array_equal(parent['time_s'], child['time_s'])
            and np.array_equal(child['time_s'], np.arange(0., 601., 30.)))
        check('exact_subset_ids', child['sat_ids'].tolist() == nodes
            and parent['sat_ids'].tolist() == meta['sat_ids'])
    mother = records(VISIBILITY + '/intervals.jsonl')
    child = records(VISIBILITY + '/subset_160/intervals.jsonl')
    allowed = set(subset['parent_indices'])
    check('exact_induced_visibility_records', child == [r for r in mother if r['i'] in allowed and r['j'] in allowed])
    original = read(GATE_C + '/report.json')
    resolution = read(GATE_C + '/terminal_pair_interval_resolution_audit.json')
    consistency = read(VISIBILITY + '/snapshot_consistency.json')
    check('original_Gate_C_all_acceptance_items', all(original['pass_items'].values()))
    check('original_interval_resolution_evidence', resolution['passed'] is True
        and resolution['max_boundary_shift_s'] <= resolution['allowed_boundary_shift_s'])
    check('original_snapshot_visibility_consistency', consistency['passed'] is True)
    hardware = read('configs/hardware_gate_c_simplified_v1.json')
    windows = records(GATE_C + '/terminal_pair_intervals.jsonl')
    catalog, statistics = validate_windows(windows, child, meta['sat_ids'], nodes,
        hardware['terminal_interval_boundary_tolerance_s'])
    checks['terminal_window_mapping_parent_censor_nonoverlap'] = True
    physical = TerminalPairPhysicalFeasibility(catalog)
    setup = hardware['audit_setup_fixture']; idle_tau = max(setup['retarget_a_s'], setup['retarget_b_s']) + setup['acquisition_s']
    rows = []
    for t in TIMES:
        observed = catalog.terminal_pair_candidates(t)
        qualified = [w for w in observed if w.end_s - (t + idle_tau) > hardware['lifetime_numerical_epsilon_s']]
        check('snapshot_%d_has_idle_setup_qualified_window' % t, bool(qualified))
        window = qualified[0]
        executor = TerminalExecutor(nodes); executor.advance(float(t))
        result = physical.evaluate(executor, window.endpoint_a, window.endpoint_b,
            retarget_a=setup['retarget_a_s'], retarget_b=setup['retarget_b_s'], acquisition=setup['acquisition_s'])
        check('snapshot_%d_original_Gate_C_representative' % t, result['accepted'])
        ready = result['geometry']['ready_time']
        check('snapshot_%d_idle_readiness_exact' % t, ready == t + idle_tau and ready < window.end_s)
        rows.append({'time_s': t, 'observed_terminal_pairs': len(observed),
            'idle_assumption_setup_qualified_pairs': len(qualified),
            'count_scope': 'UNRESERVED_IDLE_ENDPOINTS_ONLY_NOT_OCCUPIED_REPLACE_INVENTORY',
            'representative': window.to_dict(), 'ready_time_s': ready,
            'L_usable_within_horizon_s': max(0., min(window.end_s, 600.) - ready),
            'end_semantics': 'RIGHT_CENSORED_AT_600' if window.right_censored else 'NATURAL_TERMINAL_PAIR_FOR_EXPIRY',
            'full_physical_lifetime_known': not window.right_censored})
    checks['all_20_structural_sampling_points_covered'] = len(rows) == 20
    after = {rel: digest(root / rel) for rel in protected}
    check('all_3164_existing_baseline_files_unchanged_during_audit', before == after)
    tracked = set(before) | set(inputs['code_hashes']) | set(inputs['input_hashes'])
    hashes = {rel.replace('\\', '/'): digest(local_path(root, rel)) for rel in tracked}
    return {'status': 'NATURAL_K0_INPUT_PROVENANCE_AUDIT_PASS', 'scope': 'READ_ONLY_INPUTS_AND_20_IDLE_GATE_C_REPRESENTATIVES',
        'checks': checks, 'executor_runtime_chain': executor_chain, 'window_statistics': statistics,
        'snapshots': rows, 'input_hashes': hashes,
        'historical_integrity': {'baseline_file_count': len(before), 'changed_during_audit': [],
            'authorized_planning_only_differences': [p for p in before if before[p] != protected[p]]},
        'limitations': ['5000 km is diagnostic, FoR90 is parametric, no hardware calibration claim',
            'original resolution consistency is not a mathematical no-missed-tangency proof',
            '20 structural samples do not cover every controller epoch',
            'nominal idle setup 2 s does not determine occupied BBM drain or MBB readiness',
            'right-censored end is an observation horizon, not a natural expiry',
            'asset provenance does not prove matching, lexicographic optimum, inventory completeness or batch safety'],
        'Gate_K0_PASS': False, 'full_natural_K0_executed': False, 'K_star_selected': False,
        'controller_performance_executed': False, 'registered_experiments_started': False}


def main():
    start = time.perf_counter()
    out = ROOT / 'outputs' / ('f3_v2_natural_input_audit_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(exist_ok=False)
    print(str(out), flush=True)
    try:
        report = run_audit(ROOT)
        hashes = report.pop('input_hashes')
        (out / 'input_hashes.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
        rc = 0
    except Exception as exc:
        report = {'status': 'NATURAL_K0_INPUT_PROVENANCE_AUDIT_FAIL_STOP',
            'reason': str(exc), 'exception_type': type(exc).__name__, 'Gate_K0_PASS': False,
            'K_star_selected': False, 'registered_experiments_started': False}
        rc = 1
    report['wall_s'] = time.perf_counter() - start
    report['audit_code_sha256'] = digest(Path(__file__))
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (out / 'artifact_hashes.json').write_text(json.dumps({p.name: digest(p) for p in out.iterdir() if p.is_file()}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json'), 'wall_s': report['wall_s']}))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
