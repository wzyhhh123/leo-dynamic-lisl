"""Fixed eight-node independent K0 review; no natural audit or controller."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from dynamic_lisl.f3_v2.evidence import file_sha256, write_new_json
from dynamic_lisl.f3_v2.k0_fixture import fixture
from dynamic_lisl.f3_v2.k0_snapshot import produce_snapshot, write_snapshot_bundle
from dynamic_lisl.f3_v2.k0_independent_review import IndependentReviewBudget, review_point


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    out = ROOT / 'outputs' / ('f3_v2_k0_independent_review_' + stamp)
    out.mkdir(exist_ok=False)
    print(str(out), flush=True)
    start = time.perf_counter()
    hashes = {'code': {p.relative_to(ROOT).as_posix(): file_sha256(p)
        for p in sorted((ROOT / 'src/dynamic_lisl/f3_v2').glob('*.py'))},
        'input': {'configs/gate_k0_contract_v1_1_DRAFT.json': file_sha256(ROOT / 'configs/gate_k0_contract_v1_1_DRAFT.json')}}
    write_new_json(out / 'input_code_hashes.json', hashes)
    rows = []
    try:
        args, scene = fixture()
        write_new_json(out / 'fixture.json', scene)
        for K, t in ((4, 0), (4, 30), (4, 570), (16, 0)):
            bundle = produce_snapshot(**args, K=K, time_s=t)
            ref = write_snapshot_bundle(out / ('point_K%d_t%d' % (K, t)), bundle, root=ROOT, replay_index=0)
            proof = review_point(bundle['snapshot'], {k: bundle[k] for k in ('solver', 'physical', 'inventory', 'lifetime')},
                **{k: args[k] for k in ('nodes', 'fixed_edges', 'plane_by_satellite', 'physical_layer', 'setup', 'input_hashes')},
                budget=IndependentReviewBudget(100, 1000, 10.))
            rows.append({'K': K, 'time_s': t, 'reference': ref, 'independent_proof': proof})
            write_new_json(out / ('proof_K%d_t%d.json' % (K, t)), rows[-1])
            if proof['status'] != 'INDEPENDENT_POINT_REVIEW_PASS':
                raise AssertionError('INDEPENDENT_EIGHT_NODE_PROOF_NOT_PASS')
        if any(file_sha256(ROOT / p) != h for values in hashes.values() for p, h in values.items()):
            raise AssertionError('INPUT_OR_SOURCE_CHANGED_DURING_REVIEW')
        report = {'status': 'ENGINEERING_K0_INDEPENDENT_REVIEW_PASS', 'scope': 'EIGHT_NODE_SYNTHETIC_ONLY',
            'records': rows, 'producer_solvers_not_called_by_independent_proof': True,
            'Gate_C_physical_catalogue_replay': True, 'uncapped_inventory_enumeration': True,
            'matching_and_lexicographic_oracle': True, 'asset_generation_verified': False,
            'batch_diagnostics_independently_verified': False, 'full_natural_K0_executed': False,
            'Gate_K0_PASS': False, 'K_star_selected': False, 'registered_experiment_started': False,
            'wall_s': time.perf_counter() - start}
        write_new_json(out / 'report.json', report)
        rc = 0
    except Exception as exc:
        report = {'status': 'ENGINEERING_K0_INDEPENDENT_REVIEW_FAIL_STOP', 'records': rows,
            'exception_type': type(exc).__name__, 'reason': str(exc), 'K_star_selected': False,
            'registered_experiment_started': False, 'wall_s': time.perf_counter() - start}
        write_new_json(out / 'failure_summary.json', report)
        write_new_json(out / 'report.json', report)
        rc = 1
    write_new_json(out / 'artifact_hashes.json', {p.relative_to(out).as_posix(): file_sha256(p)
        for p in out.rglob('*') if p.is_file()})
    print(json.dumps({'status': report['status'], 'output_dir': str(out)}))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
