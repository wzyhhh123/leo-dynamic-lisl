"""Conditional registered entry; --preflight-only never constructs a runtime."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from dynamic_lisl.f3_v2.matrix_execution import validate_registered_request, run_matrix
from dynamic_lisl.f3_v2.evidence import write_new_json, file_sha256


def read_local(relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not (ROOT / path).resolve().is_relative_to(ROOT):
        raise ValueError('EXACT_LOCAL_AUTHORITY_INPUT_REQUIRED')
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('manifest', 'science-contract', 'k0-report', 'k1-report', 'engineering-report', 'runtime-budget', 'authorization'):
        p.add_argument('--' + key, required=True)
    p.add_argument('--preflight-only', action='store_true')
    args = p.parse_args()
    out = ROOT / 'outputs' / ('f3_v2_registered_entry_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(exist_ok=False)
    started = False
    try:
        documents = {('science_contract' if key == 'science_contract' else key): read_local(value)
            for key, value in vars(args).items() if key != 'preflight_only'}
        manifest = documents['manifest']
        if (manifest.get('execution_manifest_path') != args.manifest
            or manifest.get('science_contract_path') != args.science_contract
            or manifest.get('authorization_path') != args.authorization):
            raise ValueError('CLI_AUTHORITY_PATHS_NOT_BOUND_TO_MANIFEST')
        gate = validate_registered_request(ROOT, **documents)
        write_new_json(out / 'preflight.json', gate)
        if args.preflight_only:
            report = {'status': 'REGISTERED_PREFLIGHT_READY_NO_EXECUTION', 'registered_experiment_started': False}
            rc = 0
        else:
            from dynamic_lisl.f3_v2.registered_runtime import create_runtime
            started = True
            report = run_matrix(ROOT, out / 'matrix_attempt', runs=manifest['runs'],
                runtime_factory=lambda row: create_runtime(ROOT, manifest, row),
                engineering_only=False, manifest=manifest, admission_inputs=documents)
            rc = 0 if report['status'] == 'REGISTERED_MATRIX_EXECUTION_PASS' else 1
    except Exception as exc:
        report = {'status': 'REGISTERED_ENTRY_FAIL_STOP', 'exception_type': type(exc).__name__,
            'reason': str(exc), 'registered_experiment_started': started, 'P2_started': False, 'RL_started': False}
        write_new_json(out / 'failure_summary.json', report)
        rc = 1
    write_new_json(out / 'report.json', report)
    write_new_json(out / 'artifact_hashes.json', {path.relative_to(out).as_posix(): file_sha256(path)
        for path in out.rglob('*') if path.is_file()})
    print(json.dumps({'status': report['status'], 'output_dir': str(out), 'registered_experiment_started': started}))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
