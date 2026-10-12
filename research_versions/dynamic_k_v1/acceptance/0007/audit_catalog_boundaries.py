"""Explain rejected sampled FoR window starts without weakening N2 legality."""
import hashlib,json,sys
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
sys.path[:0]=[str(V),str(P/'src')]
from runtime.n2_physical import ReplayableSgp4Model,Sgp4PhysicalGuard
from dynamic_lisl.gate_c_terminal_geometry import TerminalGeometryConfig

def main():
    path=A/'attempt01/catalog_coverage.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest()=='bd5685f14cdf013eb10057ee40e6f3792bb6eabadcac31ece6d78062e26b7507'
    coverage=json.loads(path.read_text(encoding='utf-8'))
    catalog=P/'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl'
    rows=[json.loads(line) for line in catalog.read_text().splitlines()]
    config=TerminalGeometryConfig.from_dict(json.loads((P/'configs/hardware_gate_c_simplified_v1.json').read_text()))
    guard=Sgp4PhysicalGuard(ReplayableSgp4Model.load(P/'data/raw/sgp4_x720'),config,earth_radius_km=6378.137)
    audit=[]
    for probe in coverage['record_probes_evidence']:
        if probe['accepted']:continue
        row=rows[probe['row_index']];a=(row['sat_a'],row['terminal_a']);b=(row['sat_b'],row['terminal_b'])
        current=guard.evaluate(a,b,row['start_s'])
        offset=min(.001,(row['end_s']-row['start_s'])/2.)
        inside=guard.evaluate(a,b,row['start_s']+offset)
        details=current['for_details']
        excess=max(details['local_angle_deg']-details['local_half_angle_deg'],
                   details['remote_angle_deg']-details['remote_half_angle_deg'])
        audit.append(dict(row_index=probe['row_index'],start_s=row['start_s'],
            originally_recorded_reason=probe['reason'],current_geometry=current,
            TEST_ONLY_inside_offset_s=offset,inside_geometry=inside,half_angle_excess_deg=excess))
    assert len(audit)==318
    assert all(r['current_geometry']['reason']==r['originally_recorded_reason'] and
               not r['current_geometry']['accepted'] and r['inside_geometry']['accepted'] for r in audit), 'UNEXPLAINED_CATALOG_REJECTION_STOP'
    result=dict(status='PASS_ALL_318_EXPLAINED_AS_NUMERICAL_FoR_LEFT_BOUNDARIES',
        original_coverage_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rejected_rows=len(audit),
        all_rejections_reproduced=True,all_inside_samples_feasible=True,
        maximum_sampled_half_angle_excess_deg=max(r['half_angle_excess_deg'] for r in audit),
        scope='ADDITIONAL_CONTROLLED_GEOMETRY_DIAGNOSTIC_ONLY',legal_masks_changed=False,
        numerical_tolerance_relaxed=False,continuous_window_coverage_claimed=False,
        scientific_gate_pass=False,formal_experiments_executed=False,records=audit)
    with (A/'catalog_boundary_audit.json').open('x',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
if __name__=='__main__':main()
