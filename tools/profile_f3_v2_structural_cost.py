"""Bounded engineering cost probe; no traffic, controller, or K* selection."""
import argparse
from datetime import datetime,timezone
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def run_probe(out_dir,t0_s,target_K,max_search_nodes,builder_wall_s,certificate_nodes=None,certificate_wall_s=None):
    from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256
    from dynamic_lisl.f3_v2.structural import legal_edge_inventory,exact_terminal_maximum_matching,deterministic_lexicographic_topology
    from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
    from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
    from dynamic_lisl.terminal_executor import TerminalExecutor
    import psutil
    out=Path(out_dir)
    inputs=['configs/z_moderate_v1.json','configs/hardware_gate_c_simplified_v1.json',
            'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl',
            'configs/gate_k0_contract_v1_1_DRAFT.json']
    data=json.loads((ROOT/inputs[0]).read_text(encoding='utf-8'))
    nodes=tuple(sorted({n for e in data['fixed_edges'] for n in e}))
    planes={n:int(n.split('_')[0][1:]) for n in nodes}
    records=[json.loads(line) for line in (ROOT/inputs[2]).read_text(encoding='utf-8').splitlines()]
    catalog=TerminalPairCatalog.from_records(records,planes)
    physical=TerminalPairPhysicalFeasibility(catalog)
    executor=TerminalExecutor(nodes);executor.advance(t0_s)
    setup=json.loads((ROOT/inputs[1]).read_text(encoding='utf-8'))['audit_setup_fixture']
    write_new_json(out/'input_hashes.json',{p:file_sha256(ROOT/p) for p in inputs})
    write_new_json(out/'loaded_fixture.json',{'nodes':len(nodes),'planes':len(set(planes.values())),
        'interval_records':len(records),'snapshot_s':t0_s,'nominal_probe_K':target_K,
        'setup_source':inputs[1],'setup_status':setup['status'],'traffic_state_exists':False,
        'executor_initialization':'ALL_DYNAMIC_TERMINALS_IDLE; no K1 research initial state'})
    write_new_json(out/'inventory_started.json',{'status':'RUNNING','time_s':t0_s})
    # Passive engineering observation only. Return the exact Gate C result;
    # the structural inventory and candidate semantics are not replaced.
    from dynamic_lisl.f3_v2.structural import ObservedPhysicalLayer
    physical=ObservedPhysicalLayer(physical)
    start=time.perf_counter()
    inventory=legal_edge_inventory(executor,physical,planes,retarget_a_s=setup['retarget_a_s'],
        retarget_b_s=setup['retarget_b_s'],acquisition_s=setup['acquisition_s'],observation_end_s=600)
    inventory_wall=time.perf_counter()-start
    write_new_json(out/'gate_c_row_costs.json',physical.observations)
    write_new_json(out/'inventory_cost.json',{'status':'COMPLETE','wall_s':inventory_wall,
        'physical_candidate_count':len(inventory['edges']),'rejection_count':len(inventory['rejected']),
        'inventory_sha256':inventory['candidate_inventory_sha256'],'uncapped':True,
        'right_censored_count':sum(e.right_censored for e in inventory['edges'])})
    write_new_json(out/'structural_edges.json',[e.to_dict() for e in inventory['edges']])
    write_new_json(out/'matching_started.json',{'status':'RUNNING'})
    start=time.perf_counter();matching=exact_terminal_maximum_matching(inventory['edges'])
    matching_wall=time.perf_counter()-start
    write_new_json(out/'matching_cost.json',{'wall_s':matching_wall,**matching})
    write_new_json(out/'builder_started.json',{'status':'RUNNING','target_K':target_K})
    solved=deterministic_lexicographic_topology(inventory['edges'],target_K,tuple(sorted(set(planes.values()))),
        max_search_nodes=max_search_nodes,wall_timeout_s=builder_wall_s)
    write_new_json(out/'builder_cost.json',solved)
    certified=None
    if certificate_nodes is not None:
        from dynamic_lisl.f3_v2.certified_topology import certified_bound_topology
        certified=certified_bound_topology(inventory['edges'],target_K,tuple(sorted(set(planes.values()))),
            plane_by_satellite=planes,max_search_nodes=certificate_nodes,wall_timeout_s=certificate_wall_s)
        write_new_json(out/'analytic_certificate_cost.json',certified)
    memory=psutil.Process().memory_info()
    write_new_json(out/'probe_report.json',{'status':'ENGINEERING_COST_PROBE_COMPLETE',
        'inventory_wall_s':inventory_wall,'matching_wall_s':matching_wall,'builder_wall_s':solved['wall_s'],
        'builder_certificate_status':solved['status'],
        'analytic_certificate_status':None if certified is None else certified['status'],
        'analytic_certificate_wall_s':None if certified is None else certified['wall_s'],
        'this_cost_point_certified':solved['optimality_certified'] or (certified is not None and certified['optimality_certified']),
        'formal_main_scale_builder_ready':False,
        'certificate_scope':'this one engineering cost point only; not all K x20 audit',
        'process_peak_working_set_bytes':getattr(memory,'peak_wset',None),'process_final_RSS_bytes':memory.rss,
        'full_K0_executed':False,'K_star_selected':False,'controller_performance_read':False,
        'traffic_read':False,'registered_experiment_started':False,
        'interpretation':'one predeclared cost point; exact matching is capacity relaxation; UNKNOWN is not a K1 solution'})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--t0-s',type=float,required=True)
    parser.add_argument('--K',type=int,required=True)
    parser.add_argument('--max-search-nodes',type=int,required=True)
    parser.add_argument('--builder-wall-s',type=float,required=True)
    parser.add_argument('--timeout-s',type=float,required=True)
    parser.add_argument('--certificate-max-search-nodes',type=int)
    parser.add_argument('--certificate-wall-s',type=float)
    args=parser.parse_args()
    # Cost points were proposed before any outcome. This is not a full K0 audit.
    if args.t0_s not in (0,270,570) or args.K not in (24,48,80):parser.error('PREDECLARED_COST_POINTS_ONLY')
    import math
    if args.max_search_nodes<1 or any(not math.isfinite(v) or v<=0 for v in (args.builder_wall_s,args.timeout_s)):
        parser.error('EXPLICIT_POSITIVE_RESOURCE_LIMITS_REQUIRED')
    if (args.certificate_max_search_nodes is None)!=(args.certificate_wall_s is None):parser.error('EXPLICIT_CERTIFICATE_LIMIT_PAIR_REQUIRED')
    if args.certificate_max_search_nodes is not None and (args.certificate_max_search_nodes<1 or
        not math.isfinite(args.certificate_wall_s) or args.certificate_wall_s<=0):parser.error('EXPLICIT_POSITIVE_CERTIFICATE_LIMITS_REQUIRED')
    from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256
    out=ROOT/'outputs'/('f3_v2_structural_cost_probe_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir()
    write_new_json(out/'probe_contract.json',{'scope':'ENGINEERING_COST_ONLY_NOT_K_SELECTION','config':vars(args),
        'DRAFT_NOT_FROZEN':True,'parameter_basis':'predeclared October runtime-budget cost fixtures',
        'no_performance_leakage':True,'parent_budget_sha256':file_sha256(ROOT/'configs/F3_V2_RUNTIME_BUDGET_PLAN.json'),
        'code_hashes':{p.relative_to(ROOT).as_posix():file_sha256(p) for p in
            (ROOT/'src/dynamic_lisl/f3_v2').glob('*.py')},'command':sys.argv,'tool_sha256':file_sha256(Path(__file__))})
    print(str(out),flush=True)
    proc=mp.get_context('spawn').Process(target=run_probe,args=(str(out),args.t0_s,args.K,args.max_search_nodes,args.builder_wall_s,
        args.certificate_max_search_nodes,args.certificate_wall_s))
    start=time.perf_counter();proc.start();proc.join(args.timeout_s)
    if proc.is_alive():
        # Own isolated cost process only; never touches an existing experiment.
        proc.terminate();proc.join()
        status='ENGINEERING_COST_PROBE_TIMEOUT_UNKNOWN'
    elif proc.exitcode!=0:status='ENGINEERING_COST_PROBE_FAIL_STOP'
    else:status='ENGINEERING_COST_PROBE_COMPLETE'
    write_new_json(out/'parent_execution_report.json',{'status':status,'wall_s':time.perf_counter()-start,
        'child_exitcode':proc.exitcode,'child_alive_after_shutdown':proc.is_alive(),
        'K_star_selected':False,'registered_experiment_started':False})
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps({'status':status,'output_dir':str(out)},indent=2))
    return 0 if status=='ENGINEERING_COST_PROBE_COMPLETE' else 1


if __name__=='__main__':raise SystemExit(main())
