"""Read-only evidence review and four explicitly authorized planning revisions.

Does not import simulator/controller code, time a workload, or authorize a run.
"""
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    'docs/F3_V2_OCTOBER_CRITICAL_PATH.md',
    'configs/F3_V2_PAPER_EXPERIMENT_MATRIX_DRAFT.json',
    'configs/F3_V2_RUNTIME_BUDGET_PLAN.json',
    'configs/F3_V2_OCTOBER_DELIVERABLES.json',
]
EVIDENCE = {
    'structural_cost': 'outputs/f3_v2_predeclared_cost_summary_20261008T155819_547812Z/report.json',
    'natural_source': 'outputs/f3_v2_natural_source_coverage_20261008T162145_156464Z/report.json',
    'physical_clone': 'outputs/f3_v2_natural_physical_trial_20261008T163118_750402Z/report.json',
    'historical_natural_rollout': 'outputs/f3_v2_natural_prefix_20261008T142126_443971Z/report.json',
    'historical_regression': 'outputs/f3_v2_engineering_check_20261008T155127_587459Z/report.json',
}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def canonical(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def read(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    attempt = ROOT / ('outputs/f3_v2_october_completion_plan_' + stamp)
    attempt.mkdir(parents=True, exist_ok=False)
    prior = attempt / 'prior_plan_bytes'
    prior.mkdir()
    old = {rel: sha(ROOT / rel) for rel in FILES}
    for rel in FILES:
        (prior / Path(rel).name).write_bytes((ROOT / rel).read_bytes())
    protected = sorted(p for p in ROOT.rglob('*') if p.is_file() and attempt not in p.parents
        and not {'.git', '__pycache__', '.pytest_cache'}.intersection(p.relative_to(ROOT).parts)
        and p.suffix != '.pyc' and p.relative_to(ROOT).as_posix() not in FILES)
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in protected}
    write(attempt / 'protected_hashes_before.json', before)
    evidence = {key: read(path) for key, path in EVIDENCE.items()}
    evidence_refs = {key: {'path': path, 'sha256': sha(ROOT / path)} for key, path in EVIDENCE.items()}
    source = evidence['natural_source']
    assert source['status'] == 'NATURAL_K4_SOURCE_COVERAGE_AUDIT_COMPLETE'
    assert source['final_pool_max_batch_size'] == 1 and source['uncapped_joint_safe_witness_size'] == 4
    matrix, budget, delivery = [read(rel) for rel in FILES[1:]]
    original_runs = json.loads(json.dumps(matrix['runs']))
    original_search = json.loads(json.dumps(budget['shared_search_budget_proposal']))
    # Read historical test seal; do not relabel an old PASS as a current one.
    seal_path = str(Path(EVIDENCE['historical_regression']).parent / 'input_code_hashes.json').replace('\\', '/')
    seal = read(seal_path)['code']
    changed_code = [p for p, h in seal.items() if not (ROOT / p).is_file() or sha(ROOT / p) != h]
    new_code = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / 'src/dynamic_lisl/f3_v2').glob('*.py')
        if p.relative_to(ROOT).as_posix() not in seal)
    snapshot = {
        'scope': 'READ_ONLY_EXISTING_EVIDENCE; no tests/benchmarks rerun by planning task',
        'evidence': evidence_refs,
        'historical_focused_tests': 110, 'historical_full_tests': 439,
        'current_code_differs_from_test_seal': changed_code,
        'new_code_not_in_test_seal': new_code,
        'current_full_stack_acceptance': 'PENDING_CURRENT_CODE_REGRESSION_AND_APPROVED_PRODUCTION_CONFIG',
        'historical_natural_scope': 'K4, restricted 9-branch fixture, six 2s epochs; not K*/5s/full production pool',
        'current_natural_B4_stack_acceptance': 'NOT_ESTABLISHED_BY_THIS_PLANNING_TASK',
        'K_star_selected': False, 'formal_K0_K1_complete': False,
        'B4_v2_engineering_PASS': False, 'formal_preflight_READY': False,
    }
    for rel, item in zip(FILES[1:], (matrix, budget, delivery)):
        item.pop('draft_canonical_sha256', None)
        item.update(status='DRAFT_NOT_FROZEN', frozen=False,
            formal_performance_authorized=False, implementation_authorized_by_this_plan=False,
            plan_revision='OCTOBER_FULL_NON_MARL_COMPLETION_REVIEW_3',
            reviewed_date_local='2026-10-09', revision_utc=stamp,
            prior_plan_sha256=old[rel], prior_plan_preserved_at=prior.relative_to(ROOT).as_posix(),
            current_engineering_snapshot=snapshot)

    blockers = [
        {'id': 'CP_FREEZE', 'status': 'OPEN', 'due': '2026-10-11',
         'reason': '科学合同、K0/K1、候选搜索政策、矩阵及资源需要集中审批。',
         'earliest_affected_milestone': 'M16', 'slip_model': '审批晚于Oct11后，按剩余依赖与资源重新排期，不能假定可追回。'},
        {'id': 'CP_POOL', 'status': 'OBSERVED_STRUCTURAL_BLOCKER', 'due': '2026-10-11',
         'reason': '真实K4/t0存在安全四链动作，但64 raw到16 singleton全部替换同一old，最终池仅size1。',
         'evidence': evidence_refs['natural_source'],
         'response': '审批result-blind old-binding/terminal-footprint覆盖与按size结构种子的具体规则；全控制器共用。未自动改变候选空间。'},
        {'id': 'CP_SOURCE_COST', 'status': 'OBSERVED_RUNTIME_BLOCKER', 'due': '2026-10-11',
         'reason': 'raw output cap64不限制此前7980次物理验证；K4/t0 source实测455.0807451s。',
         'evidence': evidence_refs['natural_source'],
         'response': '与CP_POOL一并审批runtime scouting/physical-evaluation budget；保留uncapped K0结构审计独立性。'},
        {'id': 'CP_K', 'status': 'PARTIAL_CERTIFICATES_ONLY', 'due': '2026-10-16',
         'reason': '三点matching/解析exact证书已有；全部获批K×20 snapshots、K*选择及K1初态尚未完成。',
         'evidence': evidence_refs['structural_cost'],
         'response': '按原K列表/lex合同逐点审计，UNKNOWN不是无合格K或最优证书；不得按J选K。'},
        {'id': 'CP_CURRENT_ACCEPTANCE', 'status': 'OPEN', 'due': '2026-10-23',
         'reason': '旧9-branch/K4/2s自然等价不能验收当前clone与最终K*/5s/完整pool/8worker。',
         'response': '最终新版本tiny oracle、自然多epoch exact、当前源码全回归及P1-v2 preflight。'},
        {'id': 'CP_EPISODE_BUDGET', 'status': 'OPEN', 'due': '2026-10-22',
         'reason': '完整42项逐run保守费用与可用机器时段仍未测齐；不能保证Oct31。',
         'response': '成本准入不过即提前提交预计延期与非核心减项/资源提案，禁止放松正确性。'},
    ]
    matrix['research_question_registry'] = {
        'Q1': 'B4-v2 vs B3-v2核心比较', 'Q2': 'B1-v2忽略setup', 'Q3': 'B0无主动重构',
        'Q4': 'K* vs K4结构敏感性', 'Q5': '2/5s × batch1/4消融',
        'Q6': '三种负载', 'Q7': '稳定业务/热点迁移', 'Q8': 'B2 minimum-hold',
        'Q9': 'common-router鲁棒性', 'Q10': '计算费用/候选遗漏/BBM-MBB机制',
    }
    matrix['runtime_readiness'] = {
        'status': 'PENDING_APPROVED_POOL_POLICY_AND_MEASURED_BUDGET',
        'candidate_source_output_caps_do_not_bound_screening': True,
        'natural_K4_t0_singleton_only_pool_observed': True,
        'each_run_provisional_resource_ceiling_table': 'configs/F3_V2_RUNTIME_BUDGET_PLAN.json#run_planning_budgets',
        'estimated_cost_fields_remain_null': True,
        'run_ids_order_config_unchanged': True,
    }
    budget['new_v2_cost_status'] = 'PARTIAL_ENGINEERING_MEASUREMENTS; FINAL_K_STAR_PRODUCTION_EPISODE_UNMEASURED'
    budget['measured_engineering_cost_evidence'] = {
        'structural_points': evidence['structural_cost']['rows'],
        'natural_source_K4_t0': {
            'evidence': evidence_refs['natural_source'],
            **{k: source[k] for k in ('source_wall_s','source_evaluations_completed','uncapped_accepted_count',
                'raw_member_count','final_pool_max_batch_size','proposer_wall_s')},
            'not_representative_of_K_star_or_episode_mean': True,
            'source_wall_includes_passive_recording': True,
        },
        'physical_clone_pool_equivalence': {
            'evidence': evidence_refs['physical_clone'],
            'legacy_proposer_wall_s': evidence['physical_clone']['legacy_proposer_wall_s'],
            'optimized_proposer_wall_s': evidence['physical_clone']['optimized_proposer_wall_s'],
            'scope': '64 raw, 16 singleton pool and size4 physical witness; not full B4/episode'},
        'historical_natural_rollout': {
            'evidence': evidence_refs['historical_natural_rollout'],
            'branch_count': 9, 'epochs': 6,
            'serial_observe_total_s': sum(r['serial_observe_wall_s'] for r in evidence['historical_natural_rollout']['records']),
            'parallel_observe_total_s': sum(r['parallel_observe_wall_s'] for r in evidence['historical_natural_rollout']['records']),
            'scope': snapshot['historical_natural_scope'],
            'use_as_final_budget_or_current_acceptance': False},
    }
    budget['cost_evidence_policy']['measured_natural_batch_cost_s'] = None
    budget['cost_evidence_policy']['partial_components_available'] = True
    budget['critical_path_blockers'] = blockers
    budget['shared_search_budget_proposal']['derivation'] = (
        'P=16,W=4,m=4: 16+4*(15+14+13)=184 joint expansions; outputs<=28<=M32; rollout cap33. '
        'Raw64 is an OUTPUT cap only: source screening count is NOT64 and currently unbounded by these caps.')
    budget['shared_search_budget_proposal'].update(
        runtime_scouting_budget=None, runtime_physical_evaluation_cap=None,
        diversity_policy='REQUIRES_HUMAN_FREEZE: old-binding and terminal-footprint coverage + structural size seeds',
        budget_numbers_preserved_not_approved=True,
        production_readiness='BLOCKED_BY_CP_POOL_AND_CP_SOURCE_COST')
    budget['measurement_plan'][0].update(
        status='PREDECLARED_THREE_POINTS_MEASURED_FULL_K0_PENDING',
        measured_evidence=evidence_refs['structural_cost'])
    budget['measurement_plan'][1].update(
        status='K4_T0_SOURCE_MEASURED_FINAL_K_STAR_AND_PHASES_PENDING',
        measured_evidence=evidence_refs['natural_source'])
    budget['measurement_plan'][2].update(
        status='HISTORICAL_RESTRICTED_K4_PREFIX_ONLY_FINAL_PRODUCTION_PENDING',
        measured_evidence=evidence_refs['historical_natural_rollout'])
    budget['run_planning_budgets'] = []
    for run in matrix['runs']:
        ceiling = 135.0 if run['controller'] == 'B4-v2' else 22.5
        budget['run_planning_budgets'].append({
            'run_id': run['run_id'], 'execution_order': run['execution_order'],
            'calibration_key': run['runtime_budget']['calibration_key'],
            'maximum_scheduled_epochs': run['runtime_budget']['maximum_scheduled_epochs'],
            'provisional_zero_overhead_epoch_resource_ceiling_s': ceiling,
            'provisional_zero_overhead_run_resource_ceiling_s': ceiling * run['runtime_budget']['maximum_scheduled_epochs'],
            'estimated_wall_clock_s': None, 'approved_operational_timeout_s': None,
            'status': 'RESOURCE_ALLOCATION_DRAFT_NOT_COST_PREDICTION',
            'overhead_must_be_subtracted_before_admission': True,
            'B0_note': 'no source/proposer/rollout required; scheduled epochs are bookkeeping ceilings' if run['controller']=='B0-v2' else None,
        })
    budget['block_resource_allocation_hours'] = {
        block: sum(r['provisional_zero_overhead_run_resource_ceiling_s'] for r in budget['run_planning_budgets']
                   if matrix['runs'][r['execution_order']-1]['block']==block)/3600
        for block in matrix['block_counts']}
    budget['risk_sensitivity_not_prediction'] = {
        'assumption': 'ONLY IF every candidate-evaluating epoch repeated the observed K4/t0 source cost; not an episode estimate',
        'candidate_evaluating_epoch_ceiling': sum(r['runtime_budget']['maximum_scheduled_epochs'] for r in matrix['runs'] if r['controller']!='B0-v2'),
        'source_only_hypothetical_hours': source['source_wall_s'] * sum(r['runtime_budget']['maximum_scheduled_epochs'] for r in matrix['runs'] if r['controller']!='B0-v2') / 3600,
        'rollout_service_IO_extra_not_included': True,
        'reported_to_demonstrate_budget_risk_not_to_select_parameters': True,
    }
    budget['conservative_estimate_protocol'] = {
        'per_run': 'measured fixed overhead + max scheduled epochs * phase-specific conservative component cost + real service/IO/shutdown cost',
        'avoid_double_count': 'use exclusive component walls; include source/proposer once, merge/HOLD rollout once, not each worker cumulative CPU as wall',
        'phase_inputs': 'predeclare root-state fixtures/time/traffic stages before timing; equal-J checks allowed, no economic ranking',
        'missing_representative_phase': 'UNKNOWN; do not assume cheaper epoch or early drain',
        'serial_parallel': 'same branches and state, cold and persistent-warm timings separately; exact gate precedes cost adoption',
        'admission': 'all42 per-run estimates and approved timeouts filled; total conservative wall <=confirmed available hours minus reserve; RAM/process liveness pass',
        'if_over_budget': 'publish critical path/date range and resource or scope proposal before formal runs; no auto pruning/correctness change',
    }

    tasks = [
        ('T01','2026-10-09','2026-10-11',[], '集中科学合同/搜索覆盖/资源审批包', 'PLAN_AND_READ_ONLY_READY', 'HF_SCIENCE/HF_K/HF_SEARCH/HF_MATRIX/HF_RESOURCE'),
        ('T02','2026-10-09','2026-10-15',[], '现有batch安全fixture和5s/drain/checkpoint测试准备', 'INDEPENDENT_ENGINEERING_PREPARATION', '执行测试须在已有工程授权范围内；最终生产验收依冻结'),
        ('T03','2026-10-12','2026-10-15',['T01'], '按获批规则完成所有K×20点K0和证书/结构报告', 'WAIT_HUMAN_FREEZE', 'HF_K'),
        ('T04','2026-10-12','2026-10-16',['T01','T02'], '修订共享source/pool，完成资源独立batch2/3/4的结构与成本验收', 'WAIT_HUMAN_FREEZE', 'HF_SEARCH；无J调参'),
        ('T05','2026-10-16','2026-10-16',['T02','T03','T04'], '结构选择K*并生成K1当前合法初态/年龄/hash', 'WAIT_HUMAN_FREEZE', 'HF_K；按结构规则，不按控制器性能'),
        ('T06','2026-10-17','2026-10-20',['T04','T05'], 'B1/B3/B4-v2最终共享pool接入、最小B2、真实joint rollout', 'WAIT_APPROVED_PRODUCTION_CONTRACT', 'HF_SCIENCE/HF_SEARCH/HF_BUILD'),
        ('T07','2026-10-09','2026-10-20',[], 'evidence writer/manifest/图表接口复用、失败与censor fixture准备', 'INDEPENDENT_ENGINEERING_PREPARATION', '不读取正式结果；绘图literal fixture不算论文图'),
        ('T08','2026-10-21','2026-10-23',['T05','T06'], '当前tiny oracle/serial8自然多epoch/全回归/P1-v2 preflight', 'WAIT_FINAL_PRODUCTION_CONFIG', '不得借用旧runtime PASS'),
        ('T09','2026-10-17','2026-10-22',['T04','T05','T06'], '冻结前成本-only实测，全部42项预算/机器准入', 'WAIT_COST_FIXTURE_APPROVAL', 'HF_RESOURCE；成本与结构，不按J调预算'),
        ('T10','2026-10-23','2026-10-23',['T07','T08','T09'], '42项最终manifest/hash封存及独立人工运行授权', 'WAIT_NEW_RUN_AUTHORIZATION', 'HF_RUN'),
        ('T11','2026-10-24','2026-10-29',['T10'], '按唯一冻结顺序执行42项、失败先持久化再STOP', 'NOT_AUTHORIZED', '禁止静默重跑/删项/额外run'),
        ('T12','2026-10-30','2026-10-31',['T11'], '数据验证、paired分析、论文图caption、11项证据封存', 'WAIT_REGISTERED_RESULTS', '不以engineering PASS证明科学优越性'),
    ]
    delivery['task_dependency_registry'] = [dict(id=x[0],start=x[1],due=x[2],dependencies=x[3],work=x[4],readiness=x[5],authorization=x[6]) for x in tasks]
    delivery['critical_path_blockers'] = blockers
    delivery['deadline_risk'] = 'HIGH; candidate coverage and screening cost are present blockers, not just missing estimates'
    delivery['slip_reporting_contract'] = {
        'when': 'each milestone breach or conservative cost admission failure, immediately; no unattended monitoring scheduled',
        'fields': ['blocker','affected_dependencies','earliest/upper completion date or UNKNOWN','difference vs Oct31','resource options','noncore scope proposal'],
        'date_formula': 'acceptance_finish + conservative approved matrix wall / confirmed effective daily hours + two seal days; pipeline overlap only if dependencies really satisfied',
        'if_unknown': 'report UNKNOWN and missing measurement/date; never promise Oct31',
        'scope': 'CORE12 and same-permission B4/B3 comparisons, safety/exact/invariants are mandatory; reducing robustness needs explicit amended preregistration before results',
    }
    updates = {
        'D01': ('PARAMETERIZED_CODE_PRESENT_SCIENTIFIC_FREEZE_AND_CURRENT_ACCEPTANCE_PENDING',[EVIDENCE['historical_regression']]),
        'D02': ('SYNTHETIC_AND_NATURAL_PHYSICAL_CHECKS_ONLY_FINAL_PRODUCTION_ACCEPTANCE_PENDING',[EVIDENCE['physical_clone']]),
        'D03': ('THREE_POINT_EXACT_CERTIFICATES_ONLY_FULL_K0_K1_PENDING',[EVIDENCE['structural_cost']]),
        'D04': ('IMPLEMENTATION_PRESENT_CP_POOL_AND_CP_SOURCE_COST_BLOCK_PRODUCTION',[EVIDENCE['natural_source']]),
        'D05': ('HISTORICAL_RESTRICTED_K4_PASS_CURRENT_K_STAR_FULL_POOL_NATURAL_GATE_PENDING',[EVIDENCE['historical_natural_rollout']]),
    }
    for item in delivery['items']:
        if item['id'] in updates:
            item['current_status'], item['evidence_paths'] = updates[item['id']]
            item['evidence_limit'] = '部分工程证据，未完成该论文交付项；需最终配置对应验收。'
    for item in delivery['consolidated_approval_checklist']:
        if item['id']=='HF_SEARCH':
            item['decision'] = ('集中审批raw64/singleton16/8+8/W4/M32/184/33草案，同时冻结old-binding/terminal-footprint多样性、'
                '按size结构种子、runtime scouting枚举/预算及遗漏记录；原cap数字不变更为自动批准。')
        elif item['id']=='HF_BUILD':
            item['decision'] = '确认复用现有工程实现和剩余验收范围；此次计划更新不新增实现/测试运行授权，不将已有代码视为生产PASS。'
    delivery['immediate_independent_preparation'] = [
        '只读核对已有代码与验收seal的版本关系，准备当前源码回归任务',
        '准备synthetic安全/整批冲突/自然expiry/5s边界/tiny-oracle测试fixture',
        '复用失败持久化、ledger、censor、图表/caption接口并准备literal数据QA',
        '准备预声明成本采样字段、冷/热池测量协议和机器资源准入检查',
        '以上工程准备不依赖K*；实际执行仍遵守当前已授工程权限，不授权正式实验',
    ]
    delivery['not_executed_by_this_task'] = ['implementation','tests/benchmark workloads','K* selection','controller performance','registered experiments']

    doc = '''# F3-v2：2026年10月31日非MARL论文实验完整交付计划

状态：**DRAFT_NOT_FROZEN / PLAN_READY_FOR_CONSOLIDATED_HUMAN_REVIEW**。修订日期：2026-10-09，Asia/Shanghai。本轮只读取已有证据并更新四份计划，不运行算法、benchmark或正式实验；未授权冻结合同或正式运行。历史F3-v1/K0/FAIL/旧8-worker证据全部保留。

## 目标、当前进度与关键路径

10月31日前争取完成全部获批预注册的非MARL论文实验、数据检查和主要图表。12月中下旬投稿；11月安排解释、写作和审阅，不把第一轮主实验留到11月。正式规模为160星，不新增240/720实验。MARL/PPO、ADD/DROP、可变K、事件触发控制、自适应预测时域和大规模全局联合搜索均不进入本轮。

仓库已有隔离的JointAction/BatchPhysicalValidator、服务adapter、B1/B2/B3、joint B4、tiny oracle、evidence/preflight和图表接口。它们是可复用工程资产；K*尚未选择，正式K0/K1、最终共享候选政策与生产配置验收仍未完成。历史110项focused/439项全回归PASS后源码已有变化，当前验收不能沿用这些数字。旧v1 multiprocessing PASS，以及v2的K4/9分支/2s受限自然fixture PASS，均不等于最终K*/5s/完整pool验收。

**关键路径：集中合同审批 → 共享候选覆盖与计算上限 + batch物理安全 → 完整K0/K1 → B1/B3/B4-v2最终接入 → 当前tiny oracle/serial8/全回归 → 逐run实测预算 + 最终manifest/preflight → 单独正式运行授权 → 42项实验 → 验证/图表/封存。** 工程测试准备、evidence和绘图接口可与结构工作交错，不能绕过依赖或另造模拟器。

## 已经出现的阻塞：必须在10月11日前解决政策

1. **CP_POOL：真实候选池退化。** 160星K4/t0，7596个物理合法REPLACE经raw64截断及singleton16后，16项全部替换同一条old link，共享池无size2/3/4；同时存在原Gate B/C验过的安全四链MBB witness。仅把batch上限设为4不足以形成联合控制。需集中审批result-blind的old-binding/terminal-footprint覆盖规则及按size结构种子；所有B1/B3/B4共用，不据最终J调参。该发现只说明固定K4/t0，不能推广为所有K*/epoch。
2. **CP_SOURCE_COST：输出cap不约束筛选成本。** 相同自然场景7980次物理验证，source约455.081 s，proposer约7.683 s。runtime仍是全扫描再截断，raw64不能称为64次物理计算上限。需与覆盖政策一起批准有限scouting/physical-evaluation budget、canonical枚举及未扫描空间报告。K0的uncapped结构审计另行保留。当前不擅自改变候选宇宙。
3. **CP_K：结构前提未闭合。** 预声明三点t0/K24、t270/K48、t570/K80的inventory约48–59 s、exact matching约0.46–0.71 s；解析exact证书约0.016–0.020 s并有独立验证，bounded reference仍UNKNOWN。三点只证明局部求解路线，不代替原K列表×20 snapshots、正式K*或K1。
4. **CP_CURRENT_ACCEPTANCE / CP_EPISODE_BUDGET：最终自然配置与全矩阵费用待验。** 旧9分支自然B4的parallel observe约49–72 s/epoch，不能据此线性推算完整33分支或K*费用；physical clone局部等价通过也不能代替新B4全链验收。

上述原始report路径与SHA均录入runtime JSON。当前风险为**HIGH**，10月31日是目标，尚无可信全episode/全矩阵费用可保证日期。审批或验收延迟须立即报告受影响节点、预计延期范围/UNKNOWN、缺测项和可批准资源/非核心减项，不等最后一周。

## 里程碑与依赖

|截止|必须完成|准入/停止条件|
|---|---|---|
|10月11日|科学合同、K0/K1方案、覆盖与scouting政策、资源预算及集中审批包|局部实测和NOT_MEASURED分开；CP_POOL/CP_SOURCE_COST有明确获批路线|
|10月16日|获批完整K0/K1、共享batch executor及5s调度安全验收|整批双端原子性、BBM/MBB/mixed、TX draining、expiry、全时间线STRICT_CONNECTED；无合格K或UNKNOWN按合同停止|
|10月20日|同一pool的B1/B3/B4-v2核心、最小B2、正式evidence接口|真实joint rollout；B3 full-graph snapshot；无未来realization/不同权限对比|
|10月23日|新serial/8worker自然多epoch、tiny oracle、当前全回归、逐run预算、P1-v2 preflight|全state-chain exact、隔离/无孤儿进程、全部hash、最终42项manifest；任何失败不得启动|
|10月24–29日|单独人工授权后，按冻结次序执行全部42项|逐项COMPLETE/CENSORED；invariant failure先持久化再STOP；不静默重跑、不删失败|
|10月30–31日|原始证据校验、paired统计、图表/caption、11项交付封存|正式结果与engineering PASS分开；阴性/tied/censor均保留|

更细的12项任务、开始/截止/依赖/权限在deliverables JSON。10月9–11准备合同和独立工程fixtures；12–16先处理共享pool/结构与安全；17–20接入；21–23集中验收。若节点失约，重新用剩余任务与实测费用估算日期，不沿用旧从零人日预测。

## 最小完整实验矩阵：42项，维持原ID和执行次序

|块|研究配置|新增runs|
|---|---|---:|
|CORE|K*、热点迁移、primary、5s/batch4；ρ=.5/.8/1 × B0/B1/B3/B4|12|
|STABLE|K*、稳定业务、ρ=.8、primary、5s/batch4；四控制器|4|
|SPARSE|历史K4、热点、primary；B3/B4 ×三负载，ρ=.8另加B0/B1|8|
|FACTORIAL|K*、热点、ρ=.8；B3/B4 ×(2s,1)/(2s,4)/(5s,1)，(5s,4)复用CORE|6|
|HOLD|K*、热点、primary、5s/batch4；B2-H4/H8 ×三负载|6|
|ROUTER|K*、热点、5s/batch4；load-aware B3/B4 ×三负载，primary复用CORE|6|
|总计|B4=13、B3=13、B1=5、B0=5、B2=6|42|

每项run_id、状态、配置、科学作用、对照引用及预算字段已在matrix JSON，42项仍PLANNED_NOT_AUTHORIZED。K* artifact/hash、最终搜索政策和费用尚待填齐，不能作为可执行manifest。本轮不新增或删除run。

主比较是同配置B4-B3；B1决策忽略setup而真实执行仍走Gate B/C，B0不主动重构，B2只加逐链LINK_UP H4/H8最小hold。无额外算法功能。动作权限、共享pool构造、Gate B/C、router、traffic、scheduler、forecast source与决策时点相同；两算法真实状态分歧后pool可以不同，不能强迫相同实际候选。2s/5s是决策周期，不是将物理或arrival事件量化为时隙。

复用16 OD、D0 reference alpha*与统一ρ，arrival0–240s，真实drain最多600s，600不发起新decision。nominal H10，末端min(10,600−t)是待审批边界裁剪，非自适应预测。K固定指名义/初始预算，自然expiry照常发生；不ADD/DROP补链。K4保留VERY_SPARSE_HISTORICAL_REFERENCE，不能混用三链Z_SPARSE。两个K regime拟用相同STRICT_CONNECTED政策，须验证初态及全过程可行。

## 运行预算与准入

机器已有只读库存：Intel Core Ultra 9 275HX、24核/逻辑CPU、总RAM约31.43 GiB，conda pytorch。瞬时空闲RAM不能当长期保证。建议一个B4 episode、persistent8workers+parent；并行episode和线程上限需用实测RAM/争用与exact gate批准，不按24核自动启动三组。无需实时监控；只在获批测量/启动时采样。

建议Oct24–29每日至多20h可用，6天120h，20%余量，净96h；暂分B4 72h、其他24h。按600s全部决策机会计，B4最多1920 epoch、其他最多3840，零额外开销平均资源上限135s/B4和22.5s/其他epoch。B0本身不需要source/proposer；该上限是保守资源划拨，不是假定B0也搜索。每run的暂定资源额度与校准键列在runtime JSON；**实测预测和获批timeout仍为null**，必须扣除source/advance/冷启动/传输/I/O/shutdown后才判断准入。

455s的K4单点已经超过这些均值上限，是提前风险证据，不等于全episode均值。费用须在最终K*、scouting/pool政策下，用预声明阶段/状态实测source、整batch safety、真实rollout、serial/8worker、cold/warm池、推进与evidence，再给逐run保守范围。不得用9分支速度外推33分支，不据J挑K、业务或beam。source cap、joint cap和rollout cap分别计数；费用分解不得把worker累计CPU当wall或重复计算共享source。

Oct11提交局部成本与缺口；Oct16确认结构/安全费用；Oct20–22完成新B4与阶段费用；Oct23前42项预算、机器时段、RAM、超时全部填写并获批。未测代表阶段为UNKNOWN，不能假定提前drain。保守费用超过96h即立即提出资源/工期/非核心范围修订；未经审批不采用减项，不改tolerance或截短科学horizon。

## 工程验收、分析与主要图表

新增最终配置必须重验serial/8worker分支J_H、合法性/原因、Gate B events、terminal/reservation/version、G_active/G_admit、Q/I/D、objective/diagnostics、proposal ID/order/hash、action/tie和四checkpoint；自然跨epoch状态链exact、live隔离、确定性、clean shutdown。tiny oracle分别验证B3 snapshot与B4 rollout的合法集、best-in-pool及遗漏，不要求两目标选择相同，不宣称大规模全局最优。

每个正式run验证immutable traffic、work conservation、queue非负、capacity、batch资源/原子性、candidate budgets、decision边界、drain及报告一致性。内部1bit返回不是F3 .01bit排空；无clamp/drop/virtual drain。超时为execution failure，先完整写出invariant/failure/finalstate/metrics/timelines/audit/hash再STOP；CENSORED为合法科学结果，保留residual/delivery，禁止truncated-J ranking。

主目标仍network-wide unfinished-work J，无人为switch/setup penalty。双方COMPLETE才计算完整J差值；其余报告censor、backlog、delivery和completion time。42项是deterministic场景比较，不当独立随机样本生成p-value/CI，不生成global ranking。B4不优于B3仍可形成有效、完整结果。

固定ρ=.8 opening case及原run引用，画N/Q/I、REPLACE与Gate B markers、60/120/180/240s phase boundaries；其余是三负载核心对照、完整2×2cadence/batch、K/stable/B2/router、费用/候选覆盖、BBM/MBB与transition outage/post-expiry分拆。曲线重合不得换case。图表接口可提前用literal fixture检查，论文图必须引用全部正式run证据与seal。11项交付全部逐项验收，不以文件存在或engineering PASS替代。

## 一次性审批清单与可立即准备的工程任务

|组|集中审批内容|
|---|---|
|HF_SCIENCE|terminal-level joint REPLACE、whole-transition safety、5s/batch4、B1/B3/B4评分及H10/persistence/末端裁剪|
|HF_K|K0-v1.1 20点/18-of20/600右删失截断寿命、batch结构诊断、原候选K与选择规则、K1初始化/age0|
|HF_SEARCH|原raw32/32/64、singleton16/8+8、W4/M32/184/33提案；同时批准具体结构覆盖、有限scouting预算及遗漏报告，不能只批输出caps|
|HF_MATRIX|42项ID/配置/次序、三负载、stable、K4、2×2、B2-H4/H8、router、固定图case与censor分析|
|HF_RESOURCE|确认机器20h/day建议、一B4/8worker、RAM准入、成本fixture范围；最终实测预算集中补齐|
|HF_BUILD|确认现有工程复用与剩余实施/验收范围；不增加算法、星座或无关runtime重构|
|HF_RUN|前述冻结、验收、预算、manifest/hash及preflight齐全后，单独授权正式运行；本计划不授予此权限|

不依赖科学数值、可立即准备的工程工作：核对源码与seal版本、设计冲突/expiry/drain/checkpoint/tiny fixtures、复用evidence/ledger/censor接口、绘图/caption数据QA、成本字段和资源准入协议。实际运行这些工程任务仍遵守既有工程授权；此次只更新计划。候选覆盖/scouting、K*、生产评分与正式manifest必须等集中审批，不能为每个小参数反复中断。

若资源缺口无法解决，首先保全CORE12、同权限B4-B3、完整正确性及关键2×2消融；只可在任何性能结果前，申请减少非核心B2/router/sparse/stable覆盖并明确结论损失、替代manifest及延期。当前没有采用任何减项。若依赖/费用未知，完工日期写UNKNOWN，不保证10月31日。

本轮完成计划和静态一致性校验后停止。未冻结合同、未执行正式K0/K1/K*选择、未运行P1-v2/P2/RL。下一步为集中人工审批。
'''
    counts = dict(collections.Counter(r['controller'] for r in matrix['runs']))
    by_id = {r['run_id']:r for r in matrix['runs']}
    primary = [c for c in matrix['contrasts'] if c['kind']=='PRIMARY_CONTROLLER']
    checks = {
        '42_unique_runs_original_order_and_configuration': len(by_id)==42 and matrix['runs']==original_runs,
        'controller_counts': counts==matrix['controller_counts'],
        'block_counts': dict(collections.Counter(r['block'] for r in matrix['runs']))==matrix['block_counts'],
        'ten_questions_covered': set(matrix['research_question_registry']) <= {q for r in matrix['runs'] for q in r['research_question_ids']},
        'all_13_primary_pairs_fair': len(primary)==13 and all(
            all(by_id[c['left_run_id']][k]==by_id[c['right_run_id']][k] for k in ('scale','rho','topology_regime','router','traffic','decision_cadence_s','max_batch_replace')) for c in primary),
        'input_parents_unchanged': all(sha(ROOT/p)==h for p,h in matrix['parent_artifact_sha256'].items()),
        'costs_and_timeouts_not_invented': all(r['runtime_budget']['estimated_wall_clock_s'] is None and r['runtime_budget']['approved_operational_timeout_s'] is None for r in matrix['runs']),
        'run_budget_ids_order_match': [r['run_id'] for r in budget['run_planning_budgets']]==list(by_id),
        'resource_allocations_sum_96_hours': sum(budget['block_resource_allocation_hours'].values())==96.0,
        'existing_search_numbers_not_changed': all(budget['shared_search_budget_proposal'][k]==v for k,v in original_search.items() if isinstance(v,(int,float,dict)) and not isinstance(v,bool)),
        'eleven_deliverables_not_accepted': len(delivery['items'])==11 and not any(x['accepted'] for x in delivery['items']),
        'all_draft_no_run_authorization': all(x['status']=='DRAFT_NOT_FROZEN' and x['frozen'] is False and x['formal_performance_authorized'] is False for x in (matrix,budget,delivery)),
        'dependency_graph_forward_and_acyclic': all(tasks.index(x)>next(i for i,t in enumerate(tasks) if t[0]==dep) for x in tasks for dep in x[3]),
    }
    if not all(checks.values()):
        write(attempt/'planning_revision_report.json',{'status':'FAIL_STOP','checks':checks})
        raise RuntimeError('Planning validation failed before publishing')
    (ROOT/FILES[0]).write_text(doc,encoding='utf-8')
    for rel, item in zip(FILES[1:], (matrix,budget,delivery)):
        item['draft_canonical_sha256']=canonical(item)
        write(ROOT/rel,item)
    after={p:sha(ROOT/p) if (ROOT/p).is_file() else None for p in before}
    unexpected=[p for p in before if after[p]!=before[p]]
    checks['all_other_existing_project_files_unchanged']=not unexpected
    checks['canonical_json_hashes_valid']=all(read(p)['draft_canonical_sha256']==canonical({k:v for k,v in read(p).items() if k!='draft_canonical_sha256'}) for p in FILES[1:])
    write(attempt/'protected_hashes_after.json',after)
    write(attempt/'historical_integrity_report.json',{'status':'PASS' if not unexpected else 'FAIL', 'protected_count':len(before), 'changed':unexpected,'authorized_planning_paths':FILES})
    write(attempt/'current_engineering_snapshot.json',snapshot)
    write(attempt/'artifact_hashes.json',{'before':old,'after':{p:sha(ROOT/p) for p in FILES}})
    report={'status':'PLAN_READY_FOR_CONSOLIDATED_HUMAN_REVIEW' if all(checks.values()) else 'FAIL_STOP',
        'checks':checks, 'attempt':attempt.relative_to(ROOT).as_posix(), 'run_count':42,
        'deadline_risk':'HIGH','forecast_completion_date':'UNKNOWN_PENDING_FINAL_PRODUCTION_COST',
        'formal_runs_executed_by_task':0,'benchmarks_executed_by_task':0,
        'implementation_changed_by_task':False,'K_star_selected':False,
        'prior_plan_and_historical_evidence_preserved':not unexpected,
        'next_step':'CONSOLIDATED_HUMAN_REVIEW; no automatic freeze or formal execution'}
    write(attempt/'planning_revision_report.json',report)
    write(attempt/'seal.json',{p.relative_to(attempt).as_posix():sha(p) for p in sorted(attempt.rglob('*')) if p.is_file()})
    print(json.dumps(report,ensure_ascii=True,indent=2))
    if not all(checks.values()): raise RuntimeError('Planning integrity failed; STOP')


if __name__=='__main__':
    main()
