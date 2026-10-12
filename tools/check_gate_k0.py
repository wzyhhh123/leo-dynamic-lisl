"""K0 structural preflight: fail closed on missing physical look-ahead.

No controllers, traffic modules, production candidate caps, or performance inputs.
Integrity bytes are hashed in a separate channel, never parsed for design.
"""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.sgp4_model import Sgp4Model
from dynamic_lisl.gate_c_terminal_geometry import TerminalGeometryConfig, bilateral_for_margin

KS=[4,8,16,24,32,40,48,64,80,96,120,160]
TIMES=list(range(0,601,30))
SEMANTIC_FILES={
    'configs/hardware_gate_c_simplified_v1.json':'Gate C terminal mounting/FoR/setup',
    'configs/z_moderate_v1.json':'historical structural anchor only',
    'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl':'frozen bilateral physical intervals',
    'outputs/geometry_20260921T053240_016088Z/metadata.json':'geometry frame/units and satellite mapping',
    'data/raw/sgp4_x720/manifest.json':'frozen SGP4 model and time horizon',
    'data/raw/sgp4_x720/hashes.json':'frozen raw-bundle hashes',
    'data/raw/sgp4_x720/constellation.tle':'frozen synthetic TLE',
}

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

def write(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def freeze(value):
    return {**value,'canonical_sha256':hashlib.sha256(canonical(value).encode()).hexdigest()}

def protected_files():
    # Content is processed exclusively by SHA-256; values never enter preflight.
    roots=[ROOT/'src']
    roots.extend(p for p in (ROOT/'outputs').iterdir() if p.is_dir() and
                 (p.name.startswith(('gate_f3_','b4_')) or
                  p.name in ('gate_c_simplified_20260922T064019_313843Z',)))
    files={p for folder in roots for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    files.update(p for p in (ROOT/'configs').glob('*.json') if not p.name.startswith('gate_k0_'))
    files.update(p for p in (ROOT/'docs').glob('*.md') if not p.name.startswith('GATE_K0_'))
    return sorted(files)

def integrity(paths):
    return {str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in paths}

def preflight(hardware,manifest,metadata,records):
    setup=hardware['audit_setup_fixture']
    tau=max(setup['retarget_a_s'],setup['retarget_b_s'])+setup['acquisition_s']
    end=max(row['end_s'] for row in records)
    coverage=[]
    for t in TIMES:
        current=[r for r in records if r['start_s']<=t<r['end_s']]
        current_legal=[r for r in current if t+tau<r['end_s']]
        coverage.append({'t_s':t,'idle_setup_s':tau,'earliest_ready_s':t+tau,
            'terminal_pair_windows_at_t':len(current),'setup_completable_in_asset_count':len(current_legal),
            'model_covers_ready':t+tau<=manifest['duration_s'],
            'strict_interval_end_after_ready':t+tau<end,
            'capacity_status':'NOT_COMPUTED' if t+tau<end else 'NOT_EVALUABLE_ASSET_HORIZON'})
    return {'model_duration_s':manifest['duration_s'],'snapshot_stop_s':metadata['stop_s'],
            'maximum_terminal_interval_end_s':end,'terminal_window_count':len(records),
            'right_censored_window_count':sum(bool(r['right_censored']) for r in records),
            'setup_s':tau,'times':coverage,
            'blocker':'FROZEN_PHYSICAL_ASSET_HAS_NO_LOOKAHEAD_AT_T600',
            'pass':all(r['model_covers_ready'] and r['strict_interval_end_after_ready'] for r in coverage)}

def main():
    out=ROOT/'outputs'/('gate_k0_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir();print(out,flush=True)
    protected=protected_files();before=integrity(protected)
    write(out/'historical_integrity_before.json',before)
    # The only semantic data reads. TLE loader below uses the same explicit allowlist.
    reads=[]
    def read(name,lines=False):
        assert name in SEMANTIC_FILES,'PROHIBITED_SEMANTIC_INPUT'
        p=ROOT/name;reads.append({'path':name,'purpose':'STRUCTURAL_SEMANTIC_INPUT','sha256':sha(p)})
        body=p.read_text(encoding='utf-8-sig')
        return [json.loads(x) for x in body.splitlines()] if lines else json.loads(body)
    hardware=read('configs/hardware_gate_c_simplified_v1.json')
    anchor=read('configs/z_moderate_v1.json')
    assert len(anchor['bindings'])==4
    meta=read('outputs/geometry_20260921T053240_016088Z/metadata.json')
    manifest=read('data/raw/sgp4_x720/manifest.json')
    records=read('outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl',True)
    write(out/'input_read_log.json',reads)
    contract=freeze({'gate':'K0','scope':'STRUCTURAL_DESIGN_ONLY','satellites':160,'planes':4,
        'satellites_per_plane':40,'terminals_per_satellite':2,'terminal_endpoints':320,
        'integrity_statement':'DESIGN_REVISION_AFTER_LIMITED_K4_OBSERVATION',
        'K_candidates':KS,'snapshot_times_s':TIMES,'primary_band':[0.15,0.50],
        'K4_ROLE':'VERY_SPARSE_HISTORICAL_REFERENCE','primary_excludes_K4':True,
        'lexicographic_objectives':['min_plane_endpoint_range','max_represented_plane_pairs',
                                   'max_total_usable_lifetime','max_min_usable_lifetime','canonical_lexical'],
        'hard_constraints':['exact_K','terminal_degree_le_1','bilateral_Gate_C','inter_plane_only',
                            'no_parallel_satellite_pair','no_reservation_conflict','exact_replay'],
        'admissibility':{'capacity_snapshots':21,'all_planes_snapshots':21,
            'connected_and_bridges_lt_edges_snapshots':18,'replace_ge_16_snapshots':18,
            'MBB_ge_8_and_BBM_ge_8_snapshots':18,'median_MBB_fraction_band':[0.1,0.9],
            'full_audit_replays':2},'selection_rule':'min_admissible_K',
        'empty_set_rule':'PASS_AUDIT_AND_STOP_NO_ADMISSIBLE_K_ONLY_IF_FULL_AUDIT_COMPLETED',
        'forbidden':['controller_performance','traffic','queues','J','delivery','caps_32_32','topK_pruning',
                     'P1','P2','RL','production_changes'],
        'setup_source':'configs/hardware_gate_c_simplified_v1.json',
        'request_source':'user Gate K0 authorization; no result-driven changes'})
    for name,doc in (
        ('gate_k0_contract_v1.json',contract),
        ('gate_k0_candidate_k_v1.json',freeze({'K_candidates':KS,'primary_eligible_band_K':[24,32,40,48,64,80],
            'occupancy':[{'K':k,'u_terminal':k/160} for k in KS]})),
        ('gate_k0_allowed_inputs.json',freeze({'semantic_allowlist':SEMANTIC_FILES,
            'source_dependencies':['src/dynamic_lisl/sgp4_model.py','src/dynamic_lisl/gate_c_terminal_geometry.py','src/dynamic_lisl/common.py'],
            'prohibited_semantic_input_categories':['controller_results','traffic','queue','J','delay','delivery','action_trace'],
            'integrity_only':'historical files may be SHA-256 streamed by protection routine; never parsed or passed to selection',
            'actual_semantic_read_log':str((out/'input_read_log.json').relative_to(ROOT)),
            'actual_integrity_only_read_log':str((out/'historical_integrity_before.json').relative_to(ROOT))}))):
        path=ROOT/'configs'/name
        if path.exists():raise AssertionError('REFUSE_OVERWRITE_K0_CONTRACT')
        write(path,doc)
    first=preflight(hardware,manifest,meta,records);second=preflight(hardware,manifest,meta,records)
    assert canonical(first)==canonical(second)
    write(out/'physical_coverage_preflight.json',first)
    # Demonstrate that the right boundary is not an observed disappearance.
    model=Sgp4Model.load(ROOT/'data/raw/sgp4_x720')
    for name in ('data/raw/sgp4_x720/manifest.json','data/raw/sgp4_x720/hashes.json','data/raw/sgp4_x720/constellation.tle'):
        reads.append({'path':name,'purpose':'STRUCTURAL_MODEL_LOAD','sha256':sha(ROOT/name)})
    ids=tuple(meta['sat_ids'][:160]);planes=np.asarray(meta['plane_ids'][:160])
    pos,vel=model.state([600.0],ids);r=pos[0];v=vel[0]
    i,j=np.triu_indices(160,1);delta=r[j]-r[i];norm2=np.einsum('ij,ij->i',delta,delta)
    fraction=np.clip(-np.einsum('ij,ij->i',r[i],delta)/norm2,0,1)
    closest=r[i]+fraction[:,None]*delta
    los=np.linalg.norm(closest,axis=1)>meta['earth_radius_km']+meta['clearance_km']
    eligible=los&(np.sqrt(norm2)<=meta['max_range_km'])&(planes[i]!=planes[j])
    a=i[eligible];b=j[eligible];config=TerminalGeometryConfig.from_dict(hardware)
    instant={}
    for da in ('D1','D2'):
        for db in ('D1','D2'):
            margin=bilateral_for_margin(r[a],v[a],da,r[b],v[b],db,config)
            instant[da+'-'+db]=int(np.count_nonzero(margin>=-config.numerical_epsilon_deg))
    write(out/'t600_instantaneous_geometry_diagnostic.json',{
        't_s':600,'inter_plane_distance_LOS_satellite_pairs':len(a),'instant_FoR_pair_counts':instant,
        'instant_terminal_pairs':sum(instant.values()),'setup_or_lifetime_feasibility_proved':False,
        'diagnostic_cutoff_km':meta['max_range_km'],'is_hardware_range':False})
    write(out/'input_read_log.json',reads)
    # Preflight STOP: output unknowns explicitly, never fabricate matching or topology metrics.
    matching=[{'t_s':t,'M_max':None,'status':row['capacity_status']} for t,row in zip(TIMES,first['times'])]
    write(out/'matching_capacity_by_time.json',{'status':'NOT_EXECUTED_PRECHECK_STOP','series':matching,
        'min':None,'median':None,'max':None,'no_greedy_substitute_used':True})
    rows=[{'K':k,'t_s':t,'status':'NOT_EXECUTED_PRECHECK_STOP','capacity_margin':None,
           'represented_planes':None,'connected':None,'bridge_count':None,
           'raw_legal_replace_count':None,'raw_MBB_count':None,'raw_BBM_count':None} for k in KS for t in TIMES]
    for base in ('topology_metrics_by_k_time','replace_inventory_by_k_time'):
        write(out/(base+'.json'),{'status':'NOT_EXECUTED_PRECHECK_STOP','rows':rows})
    for base,data in (('matching_capacity_by_time',matching),('topology_metrics_by_k_time',rows),('replace_inventory_by_k_time',rows)):
        with (out/(base+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    write(out/'terminal_occupancy_by_k.json',[{'K':k,'occupied_endpoints':2*k,'idle_endpoints':320-2*k,
        'u_terminal':k/160,'satellites_with_0_1_2_occupied':None} for k in KS])
    for name in ('mbb_bbm_structural_summary.json','usable_lifetime_summary.json'):
        write(out/name,{'status':'NOT_EXECUTED_PRECHECK_STOP','reason':first['blocker']})
    write(out/'deterministic_replay_report.json',{'preflight_canonical_equal':True,
        'full_audit_replayed_twice':False,'K0_F_satisfied':False,'status':'FULL_AUDIT_NOT_EXECUTED'})
    write(out/'primary_k_admissible_set.json',{'PRIMARY_K_ADMISSIBLE_SET':None,'SELECTED_PRIMARY_K':None,
        'PRIMARY_K_SELECTION':'STOP_MISSING_PHYSICAL_LOOKAHEAD','not_equivalent_to_empty_admissible_set':True})
    after=integrity(protected);unchanged=before==after
    write(out/'historical_integrity_after.json',after)
    assert unchanged,'HISTORICAL_EVIDENCE_CHANGED'
    input_before={r['path']:r['sha256'] for r in reads}
    input_after={name:sha(ROOT/name) for name in input_before}
    write(out/'input_hashes_before_after.json',{'before':input_before,'after':input_after,
          'equal':input_before==input_after})
    assert input_before==input_after,'STRUCTURAL_INPUT_CHANGED'
    assert set(input_before)<=set(SEMANTIC_FILES),'PERFORMANCE_INPUT_LEAKAGE'
    report={'gate_k0':'FAIL','status':'K0_FAIL_STOP_MISSING_PHYSICAL_LOOKAHEAD',
        'blocker':first['blocker'],'full_structural_audit_executed':False,
        'exact_M_max_executed':False,'lexicographic_builder_executed':False,'SELECTED_PRIMARY_K':None,
        'performance_semantic_inputs_read':False,'controller_invocations':0,
        'historical_frozen_files_unchanged':True,'B4_production_overlay_unchanged':True,
        'input_hashes_before_after_equal':True,'K4_ROLE':'VERY_SPARSE_HISTORICAL_REFERENCE',
        'integrity_statement':'DESIGN_REVISION_AFTER_LIMITED_K4_OBSERVATION',
        'new_registered_P1_executed':False,'P2_started':False,'RL_started':False,'K1_started':False,
        'required_input_resolution':'separately authorized physical look-ahead asset beyond 602 s; do not alter historical Gate C',
        'no_thresholds_relaxed':True}
    write(out/'gate_k0_report.json',report)
    table=['| K | terminal occupancy | min M_max margin | all-plane | connected fraction | bridge summary | median MBB fraction | median BBM fraction | legal replace median | admissible |',
           '|---|---:|---|---|---|---|---|---|---|---|']
    table.extend(f'| {k} | {k/160:.1%} | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |' for k in KS)
    doc=f'''# Gate K0 动态链路预算结构审计

**Gate K0 = FAIL + STOP：冻结物理资产没有 t=600 的 setup look-ahead。** 本轮目录为 `{out.relative_to(ROOT)}`。未完成完整结构扫描，未选 K*，不能将此结果写为 PASS 或 STOP_NO_ADMISSIBLE_K。

诚信记录为 DESIGN_REVISION_AFTER_LIMITED_K4_OBSERVATION：结构复审发生在有限 K=4 结果已被观察之后；本工具未读取性能数值，未调用 controller，未使用 J、queue、delay、delivery 或动作 trace。K=4 保留为 VERY_SPARSE_HISTORICAL_REFERENCE，占用 8/320=2.5%。

输入诊断：冻结 SGP4 bundle duration={manifest['duration_s']} s；geometry stop={meta['stop_s']} s；所有 {len(records)} 个 Gate C terminal-pair 窗口的最大 end={first['maximum_terminal_interval_end_s']} s，其中 {first['right_censored_window_count']} 个是右删失窗口。`contains(t)` 使用 start<=t<end。当前 retarget_a=1、retarget_b=1、acquisition=1 s，因此 t=600 的最早 ready=602 s，无法通过冻结窗口的 ready<end 合法性，SGP4 model 也拒绝超出 bundle duration 的调用。

在 t=600 单点重新计算的 distance+LOS+bilateral FoR 仍有 **{sum(instant.values())} 个 terminal pairs**，仅是瞬时几何诊断；它不能证明这些链能在 602 s 建成，更不能提供 usable lifetime。因此窗口缺失不是实证的物理容量为零，不能借此判定所有 K 不可行。5000 km 保持 diagnostic cutoff，未改称硬件范围。

在 coverage preflight STOP 后，exact maximum-cardinality matching、完整 lexicographic Z_K builder 和 uncapped REPLACE inventory 均未执行；输出以 null / NOT_EXECUTED 明确表示未知，没有用 greedy 冒充 maximum。现有 scipy.optimize.milp 与 NetworkX 可用，但可用求解器不解决缺失物理时间窗问题。

{chr(10).join(table)}

PRIMARY_K_ADMISSIBLE_SET = 未评估；SELECTED_PRIMARY_K = null。候选集合、15%–50% band、18/21 和 MBB比例阈值原样记录，无放宽。最小 admissible K 的规则只在完整审计通过后适用，目标是最小满足结构要求的资源预算，不是性能最优 K。

`gate_k0_allowed_inputs.json` 列明 semantic allowlist；`input_read_log.json` 记录实际输入。历史文件只通过独立保护例程逐字节 SHA-256，不解析其性能内容、不进入选择算法，完整 hash-only 路径日志在 historical_integrity_before/after。保护校验相等；生产 Z_MODERATE/F3-v1/B4 overlay/历史 FAIL 均未修改。预检查两次 canonical 一致不等于完整 K0-F replay PASS。

解除 blocker 需要人工明确独立 K0 geometry/terminal-pair look-ahead 的覆盖终点和右删失 lifetime 处理；至少必须覆盖 602 s 之后以满足严格 ready<end。应由原 synthetic TLE + SGP4/WGS72/TEME 和同一 Gate C FoR 规则生成独立资产，不能把历史 end=600 直接改大，也不能删除 t=600 或替换为 599 来通过审计。本轮不创建生产 K* topology，不进入 K1/P1/P2/RL。
'''
    (ROOT/'docs/GATE_K0_DYNAMIC_LINK_BUDGET_STRUCTURAL_AUDIT_CN.md').write_text(doc,encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
