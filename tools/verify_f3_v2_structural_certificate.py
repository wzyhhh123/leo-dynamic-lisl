"""Independently check a sealed one-point engineering certificate; no K selection."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.evidence import file_sha256,write_new_json
from dynamic_lisl.f3_v2.structural import StructuralEdge
from dynamic_lisl.f3_v2.certified_topology import certified_bound_topology
from dynamic_lisl.f3_v2.joint_action import canonical_sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-attempt',required=True)
    args=parser.parse_args()
    source=(ROOT/args.source_attempt).resolve()
    if not source.is_relative_to(ROOT/'outputs'):raise ValueError('ENGINEERING_OUTPUT_SOURCE_REQUIRED')
    out=ROOT/'outputs'/('f3_v2_certificate_verification_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir()
    try:
        seal=json.loads((source/'artifact_hashes.json').read_text(encoding='utf-8'))
        if any(file_sha256(source/p)!=h for p,h in seal.items()):raise ValueError('SOURCE_SEAL_MISMATCH')
        rows=json.loads((source/'structural_edges.json').read_text(encoding='utf-8'))
        edges=[StructuralEdge(tuple(map(tuple,r['endpoints'])),tuple(r['plane_pair']),r['ready_time_s'],
            r['observed_end_s'],r['censor_status'].startswith('RIGHT_CENSORED'),r['observation_cutoff_s']) for r in rows]
        fixture=json.loads((source/'loaded_fixture.json').read_text(encoding='utf-8'))
        cert=json.loads((source/'analytic_certificate_cost.json').read_text(encoding='utf-8'))
        inputs=json.loads((source/'input_hashes.json').read_text(encoding='utf-8'))
        if any(file_sha256(ROOT/p)!=h for p,h in inputs.items()):raise ValueError('PHYSICAL_SOURCE_CHANGED')
        config=json.loads((ROOT/'configs/z_moderate_v1.json').read_text(encoding='utf-8'))
        nodes={n for e in config['fixed_edges'] for n in e}
        mapping={n:int(n.split('_')[0][1:]) for n in nodes};planes=sorted(set(mapping.values()))
        lookup={e.endpoints:e for e in edges}
        bindings=tuple(tuple(map(tuple,b)) for b in cert['bindings'])
        selected=[lookup[b] for b in bindings];terminals=[t for b in bindings for t in b]
        satellite_pairs=[tuple(t[0] for t in b) for b in bindings]
        counts=Counter(p for e in selected for p in e.plane_pair)
        life=[Fraction.from_float(e.usable_within_horizon_s) for e in selected]
        maximum=max(Fraction.from_float(e.usable_within_horizon_s) for e in edges)
        k=fixture['nominal_probe_K']
        range_lower=int((2*k)%len(planes)!=0)
        coverage_upper=min(k,len({e.plane_pair for e in edges}))
        checks={'exact_K':len(selected)==k,'all_edges_in_original_inventory':True,
            'canonical_sorted_bindings':bindings==tuple(sorted(bindings)),
            'terminal_degree_one':len(terminals)==len(set(terminals)),
            'no_parallel_satellite_links':len(satellite_pairs)==len(set(satellite_pairs)),
            'actual_plane_mapping':all(tuple(sorted(mapping[t[0]] for t in e.endpoints))==e.plane_pair for e in edges),
            'strict_ready_before_window_end':all(e.ready_time_s<e.observed_end_s<=600 for e in selected),
            'plane_range_global_lower_attained':max(counts[p] for p in planes)-min(counts[p] for p in planes)==range_lower,
            'plane_pair_global_upper_attained':len({e.plane_pair for e in selected})==coverage_upper,
            'total_lifetime_global_upper_attained':sum(life,Fraction())==k*maximum,
            'minimum_lifetime_global_upper_attained':min(life)==maximum,
            'source_exact':cert['status']=='EXACT' and cert['optimality_certified']}
        replay=certified_bound_topology(edges,k,planes,plane_by_satellite=mapping,
            max_search_nodes=100000,wall_timeout_s=10)
        checks['canonical_search_replay_exact']=replay['structural_sha256']==cert['structural_sha256']
        report={'status':'ONE_POINT_CERTIFICATE_VERIFICATION_PASS' if all(checks.values()) else 'FAIL_STOP',
            'checks':checks,'snapshot_s':fixture['snapshot_s'],'K':k,'inventory_count':len(edges),
            'plane_endpoint_counts':dict(counts),'usable_lifetime_total_exact_s':str(sum(life,Fraction())),
            'usable_lifetime_minimum_exact_s':str(min(life)),
            'canonical_minimum_basis':'include-first ordered subset enumeration; independently tested against tiny exhaustive oracle',
            'source_attempt':source.relative_to(ROOT).as_posix(),'source_seal_sha256':file_sha256(source/'artifact_hashes.json'),
            'inventory_sha256':canonical_sha256(rows),'solver_sha256':file_sha256(ROOT/'src/dynamic_lisl/f3_v2/certified_topology.py'),
            'tool_sha256':file_sha256(Path(__file__)),'K_star_selected':False,'full_K0_executed':False,
            'formal_main_scale_builder_ready':False,'controller_performance_read':False,'registered_experiment_started':False}
    except Exception as error:
        report={'status':'FAIL_STOP','error_type':type(error).__name__,'error':str(error),
            'K_star_selected':False,'registered_experiment_started':False}
    write_new_json(out/'report.json',report)
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps({'status':report['status'],'output_dir':str(out)},indent=2))
    return 0 if report['status']=='ONE_POINT_CERTIFICATE_VERIFICATION_PASS' else 1


if __name__=='__main__':raise SystemExit(main())
