"""Draft-only horizon alignment; no matching, topology builder or controllers.

Historical files are SHA-256 streamed in a separate preservation channel.
Only explicitly listed physical/contract inputs are parsed.
"""
from pathlib import Path
from fractions import Fraction
from copy import deepcopy
import argparse
import hashlib
import json
import math
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog

MARKER = 'DRAFT_NOT_FROZEN'
HORIZON = 600.0
OLD_TIMES = list(range(0, 601, 30))
NEW_TIMES = list(range(0, 571, 30))
C_ASSET = 'outputs/gate_c_simplified_20260922T064019_313843Z'
DOC = 'docs/GATE_K0_V1_1_HORIZON_ALIGNMENT_CN.md'
DRAFT = 'configs/gate_k0_contract_v1_1_DRAFT.json'
NEW_FILES = {DOC, DRAFT, 'tools/check_gate_k0_v1_1_revision.py',
             'tests/test_gate_k0_v1_1_revision.py'}
ALLOWLIST = {
    'configs/gate_k0_contract_v1.json': 'old structural contract',
    'configs/hardware_gate_c_simplified_v1.json': 'frozen setup and numerical epsilon',
    'outputs/geometry_20260921T053240_016088Z/metadata.json': 'epoch/frame/units/horizon/mapping',
    'outputs/visibility_20260921T055451_308214Z/subset_160/manifest.json': '160-satellite parent mapping',
    'outputs/visibility_20260921T055451_308214Z/subset_160/intervals.jsonl': 'continuous parent intervals',
    C_ASSET + '/terminal_pair_intervals.jsonl': 'bilateral terminal windows',
    C_ASSET + '/inputs.json': 'frozen physical input provenance',
    C_ASSET + '/hashes.json': 'frozen terminal-window hash',
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False), encoding='utf-8')


def bounded_lifetime(window, ready, horizon=HORIZON):
    """K0 draft metric only. Does not decide legality or change Gate C."""
    if not math.isfinite(ready) or not math.isfinite(horizon):
        raise ValueError('NONFINITE_TIME')
    end = window['end_s']
    if window['right_censored'] and end != horizon:
        raise ValueError('CENSOR_BOUNDARY_MISMATCH')
    return {
        't_ready_s': ready,
        't_physical_end_s': None if window['right_censored'] else end,
        'observed_interval_end_s': end,
        'L_usable_within_horizon_s': max(0.0, min(end, horizon) - ready),
        'censor_flag': ('RIGHT_CENSORED_AT_600' if window['right_censored']
                        else 'KNOWN_NATURAL_END'),
        'complete_physical_lifetime_claimed': False,
        'legality_must_be_checked_separately_by_Gate_B_C': True,
    }


def threshold_table():
    rows = []
    for label, old_n, new_n in (
        ('K0-A matching capacity', 21, 20),
        ('K0-B all-plane participation', 21, 20),
        ('K0-C connected and bridge_count < edge_count', 18, 18),
        ('K0-D uncapped legal REPLACE >= 16', 18, 18),
        ('K0-E raw MBB >= 8 AND raw BBM >= 8', 18, 18),
    ):
        old, new = Fraction(old_n, 21), Fraction(new_n, 20)
        rows.append({'condition': label, 'old_numerator': old_n,
                     'old_denominator': 21, 'old_fraction': float(old),
                     'proposed_numerator': new_n, 'proposed_denominator': 20,
                     'proposed_fraction': float(new),
                     'percentage_point_change': float(100 * (new - old)),
                     'strictness': 'STRICTER_PROPORTION' if new > old else 'SAME_PROPORTION',
                     'sampling_domain_changed': True,
                     'human_approval_required': True})
    rows.extend([
        {'condition': 'K0-E median MBB fraction', 'old_sample_count': 21,
         'proposed_sample_count': 20, 'old_band': [0.1, 0.9],
         'proposed_band': [0.1, 0.9], 'strictness': 'BAND_UNCHANGED_DOMAIN_CHANGED',
         'even_sample_median': 'mean of sorted middle two values',
         'recompute_from_full_20_point_inventory_only': True},
        {'condition': 'K0-F full audit deterministic replay', 'old_replays': 2,
         'proposed_replays': 2, 'strictness': 'UNCHANGED',
         'this_revision_check_is_not_a_full_K0_replay': True},
    ])
    return {'status': MARKER, 'rows': rows,
            'unchanged': ['K_candidates', 'primary occupancy 15%-50%',
                          'REPLACE >=16', 'MBB >=8', 'BBM >=8',
                          'median MBB band 0.10-0.90', 'min admissible K selection rule'],
            'qualification': 'Stricter fraction does not imply a nested feasible set: the t=600 sampling requirement is removed.'}


def coverage_preflight(hardware, metadata, subset, records, parents):
    errors = []
    ids = subset['satellite_ids']
    indices = subset['parent_indices']
    planes = {sid: metadata['plane_ids'][idx] for sid, idx in zip(ids, indices)}
    if len(ids) != 160 or len(set(ids)) != 160 or len(indices) != 160:
        errors.append('INVALID_160_MAPPING')
    if [metadata['sat_ids'][idx] for idx in indices] != ids:
        errors.append('PARENT_ID_MAPPING_MISMATCH')
    if sorted(set(planes.values())) != [0, 1, 2, 3]:
        errors.append('INVALID_FOUR_PLANE_SUBSET')
    if any(sum(p == q for p in planes.values()) != 40 for q in range(4)):
        errors.append('INVALID_PLANE_SIZE')
    if (metadata['start_s'], metadata['stop_s']) != (0.0, HORIZON):
        errors.append('OBSERVATION_HORIZON_MISMATCH')
    if metadata['time_unit'] != 's' or metadata['position_unit'] != 'km':
        errors.append('UNITS_MISMATCH')
    if metadata['frame'] != subset['frame'] or metadata['epoch_utc'] != subset['epoch_utc']:
        errors.append('FRAME_EPOCH_MISMATCH')
    parent_lookup = {(ids[p['i']], ids[p['j']], p['start_s'], p['end_s'])
                     for p in parents}
    for index, r in enumerate(records):
        start, end = r['start_s'], r['end_s']
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= HORIZON):
            errors.append(f'WINDOW_BOUNDS:{index}')
        if r['sat_a'] not in planes or r['sat_b'] not in planes:
            errors.append(f'WINDOW_ID:{index}')
            continue
        if planes[r['sat_a']] == planes[r['sat_b']]:
            errors.append(f'INTRA_PLANE_DYNAMIC:{index}')
        if r['terminal_a'] not in ('D1', 'D2') or r['terminal_b'] not in ('D1', 'D2'):
            errors.append(f'TERMINAL_ID:{index}')
        parent_key = (r['sat_a'], r['sat_b'], r['parent_start_s'], r['parent_end_s'])
        if parent_key not in parent_lookup:
            errors.append(f'PARENT_INTERVAL_MISMATCH:{index}')
        if not r['parent_start_s'] <= start < end <= r['parent_end_s']:
            errors.append(f'PARENT_CONTAINMENT:{index}')
        if r['right_censored'] and end != HORIZON:
            errors.append(f'RIGHT_CENSOR_NOT_AT_HORIZON:{index}')
    try:
        TerminalPairCatalog.from_records(records, planes)
    except ValueError as error:
        errors.append('CATALOG_VALIDATION:' + str(error))
    setup = hardware['audit_setup_fixture']
    tau = max(setup['retarget_a_s'], setup['retarget_b_s']) + setup['acquisition_s']
    eps = hardware['lifetime_numerical_epsilon_s']
    times = []
    for t in NEW_TIMES:
        current = [r for r in records if r['start_s'] <= t < r['end_s']]
        qualified = [r for r in current if r['end_s'] - (t + tau) > eps]
        natural_rejected = sum(not r['right_censored'] and r not in qualified for r in current)
        capped_rejected = sum(r['right_censored'] and r not in qualified for r in current)
        covered = metadata['start_s'] <= t < t + tau < metadata['stop_s']
        times.append({'t_s': t, 'snapshot_and_idle_setup_lookahead_covered': covered,
                      'idle_fixture_ready_s': t + tau,
                      'current_terminal_windows': len(current),
                      'idle_setup_qualified_count': len(qualified),
                      'natural_end_insufficient_setup_count': natural_rejected,
                      'right_censored_not_certifiable_within_horizon_count': capped_rejected,
                      'current_right_censored_count': sum(r['right_censored'] for r in current),
                      'all_current_candidates_accounted': len(qualified) + natural_rejected + capped_rejected == len(current),
                      'is_matching_or_replace_inventory': False})
    if tau != 2.0:
        errors.append('FROZEN_SETUP_NOT_TWO_SECONDS')
    return {'status': MARKER, 'pass': not errors and all(
                x['snapshot_and_idle_setup_lookahead_covered'] and x['all_current_candidates_accounted']
                for x in times), 'errors': errors, 'observed_horizon_s': [0.0, HORIZON],
            'interval_count': len(records),
            'right_censored_interval_count': sum(r['right_censored'] for r in records),
            'known_natural_end_interval_count': sum(not r['right_censored'] for r in records),
            'snapshot_count': len(NEW_TIMES), 'setup_fixture_s': tau,
            'frozen_lifetime_epsilon_s': eps, 'times': times,
            'dynamic_readiness': 'Reuse Gate C connect_command trial of current Gate B state; longer draining readiness beyond the observed end is rejected for this bounded audit, not asserted physically impossible.',
            'coverage_interpretation': 'Coverage of the frozen accepted interval asset, not a new continuous-geometry completeness proof.',
            'no_new_physical_windows_computed': True}


LIFETIME_CHANGES = [
    {'item': 'physical end interpretation', 'change': 'Natural end known => retain actual end. Right-censored at 600 => physical end null, observation cap 600, RIGHT_CENSORED_AT_600.'},
    {'item': 'candidate legality / matching input', 'change': 'Use current half-open terminal-pair window and actual Gate B/C readiness; retain ready < observed window end and frozen lifetime epsilon. Do not replace legality by max(0,...) > 0 or declare a censored boundary natural expiry.'},
    {'item': 'lexicographic priority 3', 'old': 'max_total_usable_lifetime', 'proposed': 'max_total_L_usable_within_horizon'},
    {'item': 'lexicographic priority 4', 'old': 'max_min_usable_lifetime', 'proposed': 'max_min_L_usable_within_horizon'},
    {'item': 'lexicographic priorities 1/2/5', 'change': 'Plane imbalance / plane-pair coverage / canonical lexical tie-break unchanged; horizon ties use the same lexical rule, not unknown physical ends.'},
    {'item': 'selected Z_K links', 'change': 'For independent structural construction, use actual Gate B/C construction-hypothesis readiness; do not silently charge a KEEP a new setup. No prior controller state is used.'},
    {'item': 'legal REPLACE target statistics', 'change': 'Use each actual terminal-level BBM/MBB replacement readiness, including drain/resource/release dependencies; never substitute t+2 universally.'},
    {'item': 'lifetime summaries', 'change': 'min/P10/median/P90/max and fractions <=setup, <=10s, <=20s now explicitly refer to L_usable_within_horizon. Cutoffs unchanged; report censored counts and distinguish bounded-audit rejection from known natural expiry.'},
    {'item': 'series and aggregations', 'change': 'All 21-point series/denominators become proposed 20-point series. Median over 20 uses the middle-two mean; recompute full inventories only after authorization.'},
]


def build_draft(parent):
    old = deepcopy(parent)
    old.pop('canonical_sha256', None)
    old.update({'version': '1.1', 'status': MARKER,
                'scope': 'STRUCTURAL_CONTRACT_REVISION_ONLY',
                'parent_canonical_sha256': parent['canonical_sha256'],
                'snapshot_times_s': NEW_TIMES,
                'observation_horizon_s': [0.0, HORIZON],
                'snapshot_scope': '20 structural samples; not all 2s controller epochs',
                'human_approval_required': True, 'frozen': False,
                'full_K0_executed': False, 'K_star_selected': False,
                'K_star': None, 'K1_started': False,
                'lifetime_contract': {'metric': 'L_usable_within_horizon',
                    'formula': 'max(0, min(t_physical_end, 600) - t_ready)',
                    'right_censored_branch': 't_physical_end unknown; substitute observation cap 600 only in bounded metric; retain RIGHT_CENSORED_AT_600',
                    'ready_source': 'actual Gate B/C trial of concrete terminal pair and current physical state',
                    'legality': 'unchanged half-open window, strict ready<end and frozen epsilon',
                    'applies_only_to_K0_structural_audit': True,
                    'Gate_C_data_and_B4_horizon_unchanged': True},
                'implementation_change_list': LIFETIME_CHANGES,
                'revision_execution_forbidden': ['maximum_matching', 'Z_K_builder',
                    'uncapped_REPLACE_inventory', 'full_MBB_BBM_scan', 'K_star_selection',
                    'controller_evaluation', 'J_queue_delay_delivery_performance',
                    'registered_P1', 'P2', 'RL', 'K1'],
                'full_K0_next_step': 'Requires human approval/freeze of this draft and separate authorization; exact/controlled solver infrastructure still requires implementation and acceptance.'})
    old['admissibility']['capacity_snapshots'] = 20
    old['admissibility']['all_planes_snapshots'] = 20
    old['admissibility']['snapshot_denominator'] = 20
    old['admissibility']['median_MBB_sample_count'] = 20
    old['lexicographic_objectives'][2:4] = [
        'max_total_L_usable_within_horizon', 'max_min_L_usable_within_horizon']
    old['request_source'] = 'user Gate K0-v1.1 horizon-alignment draft authorization; no result-driven changes'
    old['draft_canonical_sha256'] = digest(old)
    return old


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt-dir', required=True)
    args = parser.parse_args()
    out = Path(args.attempt_dir).resolve()
    if out.parent != (ROOT / 'outputs').resolve() or not out.name.startswith('gate_k0_v1_1_revision_'):
        raise ValueError('ATTEMPT_MUST_BE_NEW_ISOLATED_OUTPUT')
    if (out / 'gate_k0_v1_1_revision_report.json').exists():
        raise ValueError('REFUSE_OVERWRITE_ATTEMPT')
    if any((ROOT / name).exists() for name in (DOC, DRAFT)):
        raise ValueError('REFUSE_OVERWRITE_DRAFT')
    before = json.loads((out / 'historical_integrity_before.json').read_text(encoding='utf-8'))['files']
    reads = []
    def read(name):
        if name not in ALLOWLIST:
            raise ValueError('PROHIBITED_SEMANTIC_INPUT')
        p = ROOT / name
        reads.append({'path': name, 'sha256': sha(p), 'purpose': ALLOWLIST[name]})
        body = p.read_text(encoding='utf-8-sig')
        return ([json.loads(line) for line in body.splitlines()] if name.endswith('.jsonl')
                else json.loads(body))
    parent = read('configs/gate_k0_contract_v1.json')
    assert digest({k: v for k, v in parent.items() if k != 'canonical_sha256'}) == parent['canonical_sha256']
    assert parent['snapshot_times_s'] == OLD_TIMES
    hardware = read('configs/hardware_gate_c_simplified_v1.json')
    metadata = read('outputs/geometry_20260921T053240_016088Z/metadata.json')
    subset = read('outputs/visibility_20260921T055451_308214Z/subset_160/manifest.json')
    parents = read('outputs/visibility_20260921T055451_308214Z/subset_160/intervals.jsonl')
    records = read(C_ASSET + '/terminal_pair_intervals.jsonl')
    inputs = read(C_ASSET + '/inputs.json')
    c_hashes = read(C_ASSET + '/hashes.json')
    coverage = coverage_preflight(hardware, metadata, subset, records, parents)
    provenance = {name: sha(ROOT / name) == expected
                  for name, expected in inputs['input_hashes'].items()}
    provenance['terminal_pair_intervals.jsonl'] = sha(ROOT / C_ASSET / 'terminal_pair_intervals.jsonl') == c_hashes['terminal_pair_intervals.jsonl']
    coverage['frozen_physical_input_hash_checks'] = provenance
    coverage['pass'] = coverage['pass'] and all(provenance.values())
    write(out / 'coverage_preflight.json', coverage)
    write(out / 'input_read_log.json', {'status': MARKER, 'semantic_reads': reads,
         'integrity_channel': 'Whole-project historical bytes are hashed only; no performance JSON is parsed.'})
    comparison = {'status': MARKER, 'old_times_s': OLD_TIMES, 'proposed_times_s': NEW_TIMES,
                  'old_count': 21, 'proposed_count': 20, 'removed_audit_sample_s': [600],
                  'physical_assets_not_shortened_or_extended': True,
                  'last_idle_ready_s': 572, 'controller_epochs_covered_claim': False,
                  'P1_arrival_drain_deadline_cadence_rollout_unchanged': True}
    write(out / 'snapshot_schedule_comparison.json', comparison)
    migration = threshold_table()
    write(out / 'threshold_migration_table.json', migration)
    write(out / 'lifetime_contract_comparison.json', {'status': MARKER,
         'old': 'attempted complete physical remaining/usable lifetime',
         'proposed': 'finite-horizon usable lifetime with explicit right censoring',
         'formula': 'max(0,min(t_physical_end,600)-t_ready)',
         'right_censored_physical_end': None, 'changes': LIFETIME_CHANGES,
         'builder_executed': False, 'replacement_inventory_executed': False})
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s',
         'tests', '-p', 'test_gate_k0_v1_1_revision.py', '-v'], cwd=ROOT,
         capture_output=True, text=True, encoding='utf-8', errors='replace')
    write(out / 'contract_consistency_tests.json', {'status': MARKER,
          'command': [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p',
                      'test_gate_k0_v1_1_revision.py', '-v'], 'cwd': str(ROOT),
          'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
          'pass': result.returncode == 0})
    draft = build_draft(parent)
    write(ROOT / DRAFT, draft)
    threshold_lines = '\n'.join(
        f"| {r['condition']} | {r['old_numerator']}/{r['old_denominator']} | {r['old_fraction']:.6%} | {r['proposed_numerator']}/{r['proposed_denominator']} | {r['proposed_fraction']:.6%} | {r['strictness']} |"
        for r in migration['rows'] if 'old_numerator' in r)
    doc = f'''# Gate K0-v1.1 时间窗口对齐与合同修订草案

**DRAFT_NOT_FROZEN。仅完成合同修订和输入覆盖检查，等待人工批准。**

原 K0-v1 合同及 FAIL attempt 原样保留。原合同 canonical SHA-256：`{parent['canonical_sha256']}`。本次目录：`{out.relative_to(ROOT).as_posix()}`。本次草案指纹：`{draft['draft_canonical_sha256']}`；指纹只用于识别草案，不表示冻结。

## 时间与物理输入

建议审计点改为 0,30,…,570 s，共 20 点。删除的是新版本审计 schedule 的 t=600 采样要求，未删除任何历史物理记录。20 点是结构采样，不覆盖全部 2 s controller epochs，也不能证明采样间全部拓扑持续可行。

原 Gate C 终端对窗口仍为 0–600 s，包含 {coverage['interval_count']} 条记录，其中 {coverage['right_censored_interval_count']} 条右删失。160 星的 ID/plane mapping、parent visibility interval、单位/frame/epoch 和冻结输入 hash 均纳入覆盖检查。最后审计点 570 s：双端空闲的冻结 fixture retarget=(1,1) s、acquisition=1 s，因此 ready=572 s，小于观察截止 600 s。各点候选及自然短窗口拒绝数见 coverage_preflight.json；保留所有自然不可行窗口，没有人为删除它们。

Gate C 使用 `start <= t < end`，Gate B 检查 `ready < end`，Gate C 进一步使用原 `1e-9 s` lifetime epsilon。覆盖检查只证明这些判断可以依据已有资产实施，不保证每个候选合法，也不保证任何 K 有足够 matching capacity。沿用原资产的数值扫描/边界精度，不新增连续完整性或硬件能力证明；5000 km 仍是 diagnostic cutoff。

## 截断 usable lifetime

`L_usable_within_horizon = max(0, min(t_physical_end,600) - t_ready)`。

自然窗口结束已知时，t_physical_end 使用原记录的真实 end。窗口右删失时，t_physical_end 保持未知/null，指标仅用 600 s 观察上限计算，并保留 RIGHT_CENSORED_AT_600。数字 end=600 本身不决定删失，必须读取 right_censored 标志。此指标不是完整 physical lifetime；不同未知自然寿命可能在截断后相同。

ready 必须取现有 Gate C `connect_command` 对实际 Gate B 状态试执行输出的 predicted_ready。其物理关系为 `max(free_i+ret_i,free_j+ret_j)+acq`；occupied-terminal BBM 会考虑旧 TX/draining，genuine MBB 使用真实空闲端口及 release-after plan。同 peer 换终端等依赖继续由 Gate B 判定，KEEP 不产生新 setup。不能把全部 REPLACE 都简化为 t+2。

若 drain 导致 ready 达到/超出右删失 end=600，原 Gate C 拒绝其在已观察窗口内建成；报告为 bounded audit 内不可认证，不声称其在真实 600 s 之后物理不可能。合法性先独立检查；max(0,…) 的指标截断不能掩盖 ready>=end 的非法动作。

Builder 修改清单见 lifetime_contract_comparison.json：第三、第四优先级分别改为最大化总/最小 L_usable_within_horizon；第一、第二和第五优先级保持不变。matching 输入和 REPLACE legality 保持 Gate B/C 判定；selected Z_K 与 replacement targets 的 min/P10/median/P90/max、<=setup/10/20 s 比例改为明确的截断指标，阈值值不变，并附 censor counts。20 点汇总中 median 取排序后中间两值均值。本轮没有执行 builder 或 inventory。

## 阈值迁移（等待批准）

| 条件 | 原分子/分母 | 原比例 | 建议分子/分母 | 建议比例 | 严格程度 |
|---|---:|---:|---:|---:|---|
{threshold_lines}

18/21=85.714286%，18/20=90%，提高 4.285714 个百分点，比例门槛更严格；可失败点从 3 减为 2。采样域同时移除了原先无法认证的 t=600，因此不声称新旧 admissible sets 存在包含关系。21/21→20/20 仍要求全部采样点通过，比例均为 100%，时间覆盖域改变。

K0-E 的 median MBB fraction band 仍为 [0.10,0.90]，仅样本数从 21→20；K0-F 完整审计重放仍为 2 次，本次草案检查不是完整重放。K 候选、15%–50% occupancy band、raw legal REPLACE>=16、MBB/BBM>=8、最小 admissible K 选择规则全部继承。K=4 保留 VERY_SPARSE_HISTORICAL_REFERENCE，不参与 primary selection。

## 保护、范围与下一步

所有既有项目文件在独立 hash-only 通道记录前后 SHA-256，涵盖 A–E、Gate C 物理窗口、K0-v1/FAIL、F3-v1、历史 Z_MODERATE/Z_SPARSE/K4、B4 production overlay 和生产源码。性能内容不解析、不进入草案。仅运行新合同一致性测试（含少量 synthetic Gate B/C readiness 检查）；未运行完整 matching、Z_K construction、uncapped inventory、MBB/BBM 全量扫描、K* selection、controller 或性能实验。

若覆盖、合同测试、历史 hash 均通过，只记录 K0_V1_1_CONTRACT_REVISION_READY_FOR_HUMAN_REVIEW。它不等于 Gate K0 PASS 或 K* SELECTED。

现有物理资产足以支持这个有限窗口定义，无需重算或延长窗口；不改变原 traffic 0–240 s、最大 drain 600 s、2 s cadence、10 s rollout、600 s 不决策规则。下一步必须先人工冻结 v1.1 并授权完整 K0；exact matching 与 deterministic exact/controlled lexicographic solver 仍需实现和验收，不能把输入覆盖通过当成整个 K0 已可直接完成。完成本草案后 STOP，不进入 K1/P1/P2/RL。
'''
    (ROOT / DOC).write_text(doc, encoding='utf-8')
    after = {name: sha(ROOT / name) if (ROOT / name).is_file() else None for name in before}
    changed = [name for name in before if before[name] != after[name]]
    unexpected = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
          if p.is_file() and out not in p.parents
          and not any(x in p.parts for x in ('__pycache__', '.git', '.pytest_cache'))
          and p.suffix not in ('.pyc', '.pyo')
          and p.relative_to(ROOT).as_posix() not in before
          and p.relative_to(ROOT).as_posix() not in NEW_FILES)
    integrity = {'status': MARKER, 'protected_file_count': len(before),
                 'all_historical_files_unchanged': not changed and not unexpected,
                 'changed_or_missing': changed, 'unexpected_new_files': unexpected,
                 'before_sha256': before, 'after_sha256': after,
                 'historical_FAIL_attempt_preserved': True if not changed else None,
                 'scope': 'All pre-existing project files except Python caches and VCS internals; no protected category excluded.'}
    write(out / 'historical_integrity_report.json', integrity)
    passed = coverage['pass'] and result.returncode == 0 and integrity['all_historical_files_unchanged']
    report = {'status': MARKER, 'formal_outcome': (
              'K0_V1_1_CONTRACT_REVISION_READY_FOR_HUMAN_REVIEW' if passed
              else 'K0_V1_1_CONTRACT_REVISION_BLOCKED'),
              'engineering_only': True, 'coverage_pass': coverage['pass'],
              'contract_consistency_tests_pass': result.returncode == 0,
              'historical_integrity_pass': integrity['all_historical_files_unchanged'],
              'threshold_migration_complete': True,
              'no_controller_performance_leakage': True,
              'Gate_K0_PASS': False, 'K_star_selected': False,
              'matching_executed': False, 'topology_builder_executed': False,
              'replacement_inventory_executed': False, 'K_selection_executed': False,
              'new_registered_P1_executed': False, 'P2_started': False,
              'RL_started': False, 'K1_started': False,
              'draft_canonical_sha256': draft['draft_canonical_sha256'],
              'input_read_log': 'input_read_log.json',
              'code_sha256': {name: sha(ROOT / name) for name in NEW_FILES if name.endswith('.py')},
              'next_action': 'STOP; await human review/freeze and separate full-K0 authorization.'}
    write(out / 'gate_k0_v1_1_revision_report.json', report)
    write(out / 'artifact_hashes.json', {'status': MARKER,
          'files': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()},
          'draft_file_sha256': sha(ROOT / DRAFT), 'doc_sha256': sha(ROOT / DOC)})
    print(json.dumps({**report, 'output_directory': str(out)}, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
