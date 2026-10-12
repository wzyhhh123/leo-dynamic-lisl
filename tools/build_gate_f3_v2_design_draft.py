# -*- coding: utf-8 -*-
"""Generate F3-v2-0 design documents and static audit only; no simulator imports."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
STATUS = 'DRAFT_NOT_FROZEN'
DOC1 = 'docs/GATE_F3_V2_JOINT_RECONFIGURATION_DESIGN_CN.md'
DOC2 = 'docs/GATE_F3_V2_BASELINE_REDESIGN_CN.md'
CONFIGS = ['configs/gate_f3_v2_joint_action_contract_DRAFT.json',
           'configs/gate_f3_v2_baseline_registry_DRAFT.json',
           'configs/gate_f3_v2_execution_contract_DRAFT.json',
           'configs/gate_k0_v1_2_batch_audit_proposal_DRAFT.json']
NEW_FILES = set(CONFIGS + [DOC1, DOC2, 'tools/build_gate_f3_v2_design_draft.py'])


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def draft(schema, **fields):
    value = {'schema': schema, 'status': STATUS, 'frozen': False,
             'implementation_authorized': False, **fields}
    value['draft_canonical_sha256'] = hashlib.sha256(canonical(value).encode()).hexdigest()
    return value


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt-dir', required=True)
    args = parser.parse_args()
    out = Path(args.attempt_dir).resolve()
    assert out.parent == (ROOT / 'outputs').resolve() and out.name.startswith('gate_f3_v2_design_')
    assert not (out / 'f3_v2_design_review_report.json').exists(), 'REFUSE_OVERWRITE_ATTEMPT'
    assert not any((ROOT / p).exists() for p in CONFIGS + [DOC1, DOC2]), 'REFUSE_OVERWRITE_DRAFT'
    before = json.loads((out / 'historical_integrity_before.json').read_text(encoding='utf-8'))['files']
    read_log = []
    def read_json(name):
        p = ROOT / name
        read_log.append({'path': name, 'channel': 'CONTRACT_OR_RUNTIME_PROVENANCE', 'sha256': sha(p)})
        return json.loads(p.read_text(encoding='utf-8-sig'))
    contracts = {name: read_json(name) for name in (
        'configs/gate_f0_controller_contract.json', 'configs/gate_f0_baseline_registry.json',
        'configs/gate_f0_human_freeze_v1.json', 'configs/gate_f1_scoring_human_freeze_v2.json',
        'configs/gate_f2_rollout_human_freeze_v1.json', 'configs/gate_f3_b2_grid_v1.json',
        'configs/gate_f3_experiment_human_freeze_v1.json',
        'configs/gate_f3_execution_manifest_v1.json',
        'configs/gate_f3_candidate_source_drain_human_freeze_v1.json',
        'configs/gate_k0_contract_v1_1_DRAFT.json',
        'configs/gate_f3_b4_production_multiprocessing_registration_v1.json',
        'configs/gate_f3_b4_production_multiprocessing_overlay_v1.json',
        'configs/b4_executor_compatibility_successor_v1.json',
        'configs/gate_f3_b4_runtime_chain_v1.json')}
    source_names = [
        'terminal_executor.py', 'terminal_pair_intervals.py', 'gate_c_simplified_feasibility.py',
        'transition_profiler.py', 'operational_policy.py', 'production_candidate_source.py',
        'candidate_proposer.py', 'baseline_controllers.py', 'scientific_controllers.py',
        'scientific_snapshot.py', 'common_router.py', 'service_scheduler.py',
        'queue_state.py', 'in_flight.py', 'network_service_engine.py',
        'transition_service_orchestrator.py', 'gate_e2_experiments.py',
        'controller_runner.py', 'gate_f3_p1_execution.py', 'f3_drain_continuation.py',
        'forecast.py', 'rollout_controller.py', 'rollout_evaluator.py',
        'b4_branch_multiprocessing.py', 'rollout_clone.py', 'b4_runtime_seal.py']
    # The in-flight module name is resolved exactly from the real orchestrator import.
    if not (ROOT / 'src/dynamic_lisl/in_flight.py').exists():
        source_names[source_names.index('in_flight.py')] = 'inflight_state.py'
    sources = {}
    for name in source_names:
        path = ROOT / 'src/dynamic_lisl' / name
        body = path.read_text(encoding='utf-8-sig')
        read_log.append({'path': path.relative_to(ROOT).as_posix(), 'channel': 'CODE_READ_ONLY', 'sha256': sha(path)})
        tree = ast.parse(body)
        symbols = {}
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                symbols[node.name] = node.lineno
                if isinstance(node, ast.ClassDef):
                    for child in node.body:
                        if isinstance(child, ast.FunctionDef):
                            symbols[node.name + '.' + child.name] = child.lineno
        sources[name] = {'body': body, 'symbols': symbols}
    def ref(name, symbol):
        return {'path': 'src/dynamic_lisl/' + name,
                'symbol': symbol, 'line': sources[name]['symbols'][symbol]}

    impact_rows = [
        ('terminal_executor.py', 'TerminalExecutor.submit', '可直接复用',
         '真实多个 reservations/events；trial 顺序验证全体命令，全部成功后才替换 live __dict__。异常不提交。',
         '不改内核；新增 v2 资源独立 batch adapter，不能把 submit 多命令能力当作网络级 batch safety 已完成。'),
        ('terminal_pair_intervals.py', 'TerminalPairCatalog.connect_command', '可直接复用',
         '半开窗口、Gate B trial predicted_ready、严格 ready<end 和原 epsilon。',
         '在同一 DECISION_ROOT 取各条 Connect，完整集合再 trial.submit；不是独立合法即联合合法。'),
        ('gate_c_simplified_feasibility.py', 'TerminalPairPhysicalFeasibility.evaluate', '需要新增接口',
         '公开 evaluate 只接受一组 a/b/release_after，hardware hook 也是单 pair。',
         '新增 BatchPhysicalValidator；保留每条 Gate C，并对整组 Gate B trial 校验。未建模卫星公共电源/热约束不额外声称硬件并发保证。'),
        ('transition_profiler.py', 'profile_transition', '可直接复用',
         'commands 本来是序列；在 clone 上 submit 后按真实事件组生成 active/admit graphs。',
         '新 adapter 提供整个 batch 完成边界，包含 MBB release/旧 TX drain，不只用最大 new ready。'),
        ('operational_policy.py', 'OperationalPolicy.apply', '不应修改',
         'STRICT_CONNECTED 拒绝 partition_occurs；profile 的 partition 同时检查 active/admit。BOUNDED_OUTAGE 仍使用现有 2s 界。',
         '原 policy reject-only，不根据经济分数补救或替换。新 Z_K* 继承 moderate policy 的选择单独待批准。'),
        ('production_candidate_source.py', 'ProductionCandidateSource.materialize', '必须升级',
         'old_rows×terminal windows 的一换一 raw universe；拒绝 MULTI_OLD_BINDING_CONFLICT；32/32/64 caps。',
         '独立 v2 source 可复用物理枚举规则/排序，输出 singleton resource footprint；不得沿用 v1 source identity 假称 batch identity。'),
        ('candidate_proposer.py', 'FrozenTerminalPairProposer.propose', '必须升级',
         '逐条 physical/safety pruning，然后 top16/8+8。',
         '新增 shared structural joint proposer；single unsafe 作为 diagnostic，不自动证明联合 unsafe；所有可执行最终 batch 整体 safety 通过。'),
        ('baseline_controllers.py', 'ControllerAction', '必须升级',
         'kind 仅 HOLD/REPLACE；只容纳一个 proposal_id。',
         '新增 v2 HOLD/BATCH_REPLACE schema，ordered member IDs、batch ID、root hash；旧 dataclass 不改。'),
        ('baseline_controllers.py', 'StaticHoldController.observe', '可直接复用',
         '恒 HOLD，自然 expiry 仍执行；无需消费候选。',
         '轻量 v2 类型 adapter，保留相同物理时间线，controller 权限不同于根本不执行物理。'),
        ('baseline_controllers.py', 'HysteresisMinimumHoldController.observe', '必须升级',
         '当前 last_accepted_switch_time 为全局时钟；无 per-link hold。',
         '新增逐 old-binding elapsed-seconds eligibility；B2 基于 B1-v2，不混用 B3；H4/H8 历史不改。'),
        ('scientific_controllers.py', 'IgnoreSetupDynamicController.observe', '必须升级',
         'B1 在理想单目标图上 argmin V_v2；B3 用单条 DeltaV×eta。',
         '新增 B1/B3-v2 对共同 batch pool 的完整目标图重新算 snapshot；B3 定义 batch eta。'),
        ('scientific_snapshot.py', 'ScientificSnapshotEvaluator.evaluate_edges', '可直接复用',
         '路由重算、current local demands、equal_weight_fair_share 和 in-flight-only Psi=0，未 advance。',
         '只新增 batch target_edges 构造/完整批次调用；保留 V_v2 数学与浮点规则。'),
        ('transition_service_orchestrator.py', 'TransitionAwareNetworkServiceEngine._apply_due_actions', '需要新增接口',
         'ScriptedProposal 单 proposal；逐条 evaluate/profile/submit，不能保证 batch 外层原子性。',
         '新 v2 subclass 的 ScriptedBatchProposal/_apply_due_actions hook 一次 commit，外层 microstep 一次刷新图/路由/服务；旧 D2 内核源码不改。'),
        ('transition_service_orchestrator.py', 'TransitionAwareNetworkServiceEngine._microstep', '不应修改',
         'propagation settlement→executor events→due action→graphs/router→service；事件推进独立于控制。',
         '通过 polymorphic due-action hook 接入；不连续 schedule 多个单动作伪造原子 batch。'),
        ('common_router.py', 'DeterministicShortestPropagationDelayRouter._path_with_adjacency', '不应修改',
         'distance/full_path/node heap 和 candidate<current deterministic tie。',
         'primary/robustness 条件内所有 controller 同 router；保留已有缓存生命周期。'),
        ('network_service_engine.py', 'NetworkServiceEngine', '不应修改',
         '既有静态 service reference；production 使用 transition-aware/E2 subclass。',
         '不创建平行 simulator，不动 link capacity、allocator、Q/I/D 或 in-flight closure。'),
        ('controller_runner.py', 'MultiEpochControllerRunner.__init__', '必须升级',
         '显式拒绝 cadence!=2；每 epoch 消费单 proposal。',
         '新增 v2 runner，5s nominal/兼容2s模式由不同合同驱动，旧 guard 不改。'),
        ('gate_f3_p1_execution.py', 'P1RunExecutor._decision', '必须升级',
         '单 selected_proposal_id/action record；固定 Z_MODERATE 和 v1 hashes/manifest。',
         '新增 v2 execution adapter/manifests/evidence writer，读取未来 K* 初态；不改旧 P1 或其 preflight。'),
        ('production_candidate_source.py', 'DrainDecisionPolicy', '必须升级',
         '2s/240/600 guard 硬编码；600 无 decision。',
         '新增 v2 5s policy：0..595；240 后真实 drain；COMPLETE 0.01bit 不变。'),
        ('forecast.py', 'CurrentRatePersistenceForecast.__post_init__', '需要新增接口',
         '强制 horizon=10；clone 替换 future trace；不读取真实 future phases。',
         '新增 v2 effective-horizon forecast以支持595→600的5s截断；当前 lambda persistence 原理保留。'),
        ('rollout_controller.py', 'RootActionRolloutMPCController.evaluate_root_actions', '必须升级',
         '最多16 singleton；order/state/forecast hash共享；一次root REPLACE，未来不递归controller。',
         '新 B4-v2 shared batch pool argmin真实 J_H；每个 branch root提交完整batch，仍 root-action-only。'),
        ('rollout_evaluator.py', 'ExactRootActionRolloutEvaluator.evaluate_candidate', '必须升级',
         '单 ScriptedProposal，固定 advance t+10；单 action_result。',
         '新 batch evaluator/result schema，多成员结果与整体 validity；H_eff边界相同，无terminal penalty。'),
        ('b4_branch_multiprocessing.py', 'BranchTask', '必须升级',
         '调度pool可并行任意task数，但task/evaluator分派依赖一个record/spec。',
         '新 v2 BatchBranchTask/payload dispatch；8-worker持久pool机制可继承但必须重新验收，不改旧runtime overlay。'),
        ('rollout_clone.py', 'clone_rollout_engine', '需要新增接口',
         '仅已审计append-only历史record浅共享；其余及未知字段使用同一个memo deepcopy保持alias。TerminalExecutor另有字段白名单。',
         '为新 subclass 的 batch queues、ledger/hold-age/readiness maps 单独 field audit；严禁跨branch/epoch共享 mutable state。'),
        ('f3_drain_continuation.py', 'F3DrainContinuationAdapter', '可直接复用',
         'D2 early return 1bit不等于F3 COMPLETE 0.01；真实 continuation直到边界。',
         '换外层cadence，内层阈值/推进/守恒完全保留。'),
        ('b4_runtime_seal.py', 'validate_runtime', '不应修改',
         '旧 source hashes 和明确授权 successor/overlay 链。',
         'v2 是新科学合同，另建新code/evidence registry；不能借runtime successor许可改变科学动作。'),
    ]
    impact = draft('f3_v2_repository_impact_matrix', rows=[{
        'module': name, 'classification': category, 'observed': observed,
        'proposed_change': change, 'evidence': ref(name, symbol)}
        for name, symbol, category, observed, change in impact_rows],
        hardcoded_locations={'2s': ['controller_runner.MultiEpochControllerRunner.__init__',
            'production_candidate_source.DrainDecisionPolicy.__post_init__',
            'gate_f3_p1_execution.P1RunExecutor uses that policy',
            'configs/gate_f0_human_freeze_v1.json', 'configs/gate_f2_rollout_human_freeze_v1.json',
            'configs/gate_f3_experiment_human_freeze_v1.json'],
            '10s': ['forecast.CurrentRatePersistenceForecast.__post_init__',
            'rollout_controller.RootActionRolloutMPCController.horizon_s',
            'rollout_evaluator.ExactRootActionRolloutEvaluator.horizon_s',
            'rollout_evaluator._finish exact horizon assertion',
            'configs/gate_f2_rollout_human_freeze_v1.json']},
        actual_implementation_vs_old_registry='F0 implemented=false is a historical F0 timestamp, not current implementation state; real scientific modules are audited.',
        no_new_simulator=True)

    order = ['settle committed propagation arrivals/rate events',
             'settle due Gate B events in existing priority/sequence order',
             'use right-continuous external rate and refresh current graph/routes/service under old kernel',
             'DECISION_ROOT checkpoint', 'shared single + joint proposal/validation',
             'controller observes/evaluates clones only', 'POST_OBSERVE checkpoint',
             'validate selected exact batch from unchanged root',
             'atomic Gate B multi-command commit, including due zero-time events',
             'one graph/routes/service refresh after batch group', 'POST_DECISION checkpoint']
    safety_rules = [
        '0<=m<=min(4,K_star); HOLD iff m=0; no ADD/DROP; old bindings exact and distinct',
        'each old link active, not draining, not release-owned; target terminals known D1/D2',
        'for each r, footprint=endpoints(old_r) UNION endpoints(new_r)',
        'distinct replacements have disjoint footprints (satellites may share distinct D1/D2)',
        'new/current/pending satellite pairs cannot create forbidden parallel bindings',
        'all target endpoints unreserved; no old release lock or same old claimed twice',
        'MBB target both genuinely IDLE at DECISION_ROOT; release_after names only own old binding',
        'BBM target occupied endpoints belong only to own old binding; Gate B performs actual drain/free/setup',
        'no cross-action terminal reuse, release chains, cyclic exchange or instantaneous freed-port assumption',
        'one immutable decision root; each Gate C window current, actual ready strictly before observed end with original epsilon',
        'validate full commands by Gate B trial.submit in canonical member order; all invariants required',
        'dry-run full batch with existing pending events; apply original regime safety on whole graph evolution',
        'safety coverage through new setup and all selected old release/drain completion, bounded by600',
        'if required physical continuation cannot be certified within asset, reject with horizon-limited reason, never infer natural expiry at600',
        'live commit is one submit(commands); validation failures reject entire batch, no partial repair/substitution',
        'unexpected commit mismatch is execution failure: preserve evidence and STOP; no replay or clamp',
        'after commit visibility abort remains per reservation; other independent reservations continue; no retroactive rollback of physical time',
    ]
    batch = draft('gate_f3_v2_joint_action_contract', gate='F3-v2-0',
        decision_cadence_s={'proposed': 5.0, 'approval': 'REQUIRES_HUMAN_FREEZE'},
        max_batch_replace={'proposed': 4, 'approval': 'REQUIRES_HUMAN_FREEZE'},
        K_star=None, K_star_status='NOT_SELECTED',
        action_schema={'HOLD': {'members': []}, 'BATCH_REPLACE': {
            'fields': ['decision_time_s', 'absolute_time_frame_id', 'decision_root_sha256',
                       'joint_proposal_set_sha256', 'batch_id', 'ordered_member_ids', 'members'],
            'member_fields': ['member_id', 'old_physical_binding', 'new_terminal_pair'],
            'transition_mode_controller_supplied': False,
            'member_canonical_order': 'same shared singleton proposal index; members strictly increasing',
            'batch_canonical_order': 'cardinality then tuple of shared singleton indices; HOLD first',
            'identity': 'schema+absolute time/frame+root hash+canonical exact old/new terminal pairs; no runtime completion order'}},
        safety_rules=safety_rules,
        interfaces=['validate_batch(root,members)->PASS/FAIL+exact reason+commands+per-member readiness+joint profile',
                    'commit_batch(live,validated_plan)->atomic accepted/rejected batch result+member map',
                    'schedule_batch(engine,ScriptedBatchProposal)->one due-action entry, not m independent singleton entries'],
        validation_pure=True, reservation_atomicity='Bilateral and entire command transaction',
        transaction_failure='Validation or trial failure leaves live terminal/Q/I/D/event/counters unchanged; audit-only rejection record allowed.',
        future_abort_semantics='Atomic admission does not guarantee all future links survive; actual later expiry abort is independent physical evolution.',
        target_budget_semantics='One-for-one intended topology budget K_star. Active counts may be below K during BBM/expiry and above K during genuine MBB. Natural expiry does not trigger ADD or fake auto-restoration.',
        strict_constant_active_K_claim=False,
        regime_safety={'Z_MODERATE': 'inherit actual STRICT_CONNECTED active/admit profile behavior',
                       'Z_SPARSE_REFERENCE': 'inherit BOUNDED_OUTAGE Tmax=2s',
                       'Z_K_STAR': 'propose inherit moderate STRICT_CONNECTED; REQUIRES_HUMAN_FREEZE'},
        newly_added_connectivity_constraint=False,
        new_semantic_restrictions=['resource-independent footprints', 'batch atomicity at network adapter',
                                   'joint safety rather than singleton safety equivalence'],
        observed_gate_B_capability='Multi-reservation concurrent lifecycles and atomic list submit exist; shared network batch adapter not implemented.')

    search = draft('f3_v2_joint_candidate_search_plan',
        recommended_primary='SHARED_STRUCTURAL_BOUNDED_BEAM_POOL',
        shared_across=['B1-v2', 'B2-v2', 'B3-v2', 'B4-v2'],
        permission_m=4,
        pending_budgets={'raw_BBM_cap': {'suggested': 32, 'source': 'v1 inheritance only, pending approval'},
            'raw_MBB_cap': {'suggested': 32, 'source': 'v1 inheritance only, pending approval'},
            'raw_total_cap': {'suggested': 64, 'source': 'v1 inheritance only, pending approval'},
            'single_proposal_limit': {'suggested': 16, 'source': 'v1 inheritance only, pending approval'},
            'single_strata_slots': {'suggested': {'BBM': 8, 'MBB': 8}, 'status': 'REQUIRES_HUMAN_FREEZE'},
            'beam_width': None, 'max_non_hold_batch_candidates': None,
            'max_joint_validation_calls': None, 'max_structural_expansions': None,
            'max_rollout_evaluations_including_HOLD': None, 'operational_wall_timeout_s': None},
        single_proposal_rule='Reuse terminal/window/resource predicates; physically illegal singles excluded. Network single-safety result diagnostic: unsafe prefix may stay expandable. Joint safety decides complete executable batches.',
        structural_ranking='ascending (-min bounded usable lifetime, -sum bounded usable lifetime, canonical member-index tuple); no traffic/Q/J/controller identity. Affects search coverage; not optimality.',
        algorithm=[
            'Form identical capped physical singleton universe from DECISION_ROOT and preregistered deterministic order.',
            'Build conflict metadata using exact old/new footprints, binding identity and forbidden parallel pairs.',
            'Depth1=singleton prefixes; expand only increasing member indices, cardinality<=min(4,K_star).',
            'Prune proven resource/terminal conflicts before Gate C/B; do not prune only because a prefix fails network connectivity.',
            'Whole batch physical trial and timeline safety, retain diagnostic reason; resource/physical-valid safety-rejected prefixes may grow within expansion budget.',
            'At each depth keep at most W expandable prefixes by structural ranking; each level process fixed canonical order.',
            'Executable output contains all individually joint-safe singletons plus preregistered per-depth retained legal batches, up to M non-HOLD; include smaller sizes, not only size4.',
            'Reserve all executable singletons and one retained safe batch per available size2/3/4; then fill remaining slots round-robin by size and within-size structural rank. Require M>=P+(max_batch_replace-1); pool truncation independent of controller score.',
            'Dedup exact member sets only; graph-equivalent but physically different batches remain different (ready/releases matter).',
            'Freeze/hash full common joint pool before any controller economics/rollout. B3/B4 receive identical records on the same root.',
        ],
        complete_16_singleton_subsets_through_size4=sum(math.comb(16, k) for k in range(5)),
        full_enumeration_main_scale=False,
        structural_expansion_bound='P + sum_depth2to4 W*(P-depth+1), additionally bounded by frozen expansion/validation caps',
        budget_consistency='W>=1; M>=P+3 for max_batch4; validation/expansion budgets must at least validate all P singletons; E_rollout>=1+M. Incompatible human budgets fail static preflight, never silently lower m or omit a required score.',
        rollout_budget_relation='B4 evaluates HOLD plus every legal common non-HOLD batch: calls=1+pool_size<=1+M. Require registered E_rollout>=1+M.',
        no_multi_step_action_tree=True,
        ties='Scores exact; HOLD wins tie; batch-vs-batch uses canonical pool order, independent of worker finish order.',
        budget_exhaustion='Deterministic count cap truncates structural search before scoring; report SEARCH_BUDGET_EXHAUSTED and keep common completed validated pool. No score-driven hidden enlargement.',
        operational_timeout='Not a score/algorithm budget. Any incomplete required rollout/worker fault: return explicit operational HOLD if physically allowable, persist exception/unfinished tasks and mark run EXECUTION_BLOCKED, never report scientific COMPLETE/CENSORED. No choose-first-finished.',
        speculative_score_adaptive_beam='Not primary. If later authorized B4 uses J-driven beam, register B3-SEARCH_MATCHED with the exact same J-selected batch pool and report search-cost/forecast contamination; cannot claim pure prediction contrast.',
        primary_search_matched_by_design=True)

    snapshot = {
        'version': 'frozen scheduler-consistent V_v2',
        'G_batch_ideal': '(current admitted edges minus all selected old satellite edges) union all selected new satellite edges',
        'unchanged_other_pending_transitions': 'Remain current-state edges for snapshot; idealize only this selected batch.',
        'route_recompute': 'Selected frozen common router on entire ideal topology, same root node/commodity state',
        'N_f': 'sum_i Q_i^f + sum_e I_e^f',
        'demand': 'Frozen evaluator: Q>state_tol => infinite local demand; else positive current source/inflight input => finite demand; in-flight-only without local demand has Psi=0.',
        'R_snap': 'Minimum actual equal_weight_fair_share allocation over current positive local demand nodes, not equal division by all route-using commodities',
        'V': 'sum_{f:N_f>0} [N_f*C_prop_f + Psi_f]; Psi=N_f^2/(2R_snap) if demands exist, otherwise0',
        'invalid': 'Frozen source-route/no-next-hop/nonpositive-allocation invalid reasons => +infinity',
        'no_time_advance': True, 'no_rollout': True,
        'infinity_rule': 'Both HOLD/candidate infinity => not positive improvement; finite candidate vs infinity HOLD => +infinity improvement; never calculate NaN infinity-infinity.'}
    b3 = {'candidate_set': 'exact common joint pool',
          'deltaV': 'V(HOLD)-V(G_batch_ideal)',
          'eta_member': 'actual Gate C usable_lifetime_s / remaining_lifetime_s (both current observed-window quantities; retain censor flags)',
          'eta_batch_proposal': 'min_r eta_r',
          'score_proposal': 'S_batch=deltaV_batch*min_r eta_r for deltaV>0 and every remaining/usable>0',
          'selection': 'maximum positive S_batch, otherwise HOLD; exact ties common order',
          'interpretation': 'Myopic setup-aware choice over jointly constructed batches, not independent top-four or sequential summed benefits',
          'single_mode': 'min of one eta recovers old B3 formula when pool/root/router same',
          'min_eta_status': 'NEW_AGGREGATION_REQUIRES_HUMAN_FREEZE; conservative proxy, not exact queue-area/service loss theorem',
          'evaluate_new_prefix': 'Each extended retained prefix recomputes full graph and current service snapshot; never sum individual DeltaV.',
          'explicit_network_rollout': False}
    b2 = {'base': 'B1-v2 exactly', 'threshold_signal': 'deltaV of whole batch',
          'hold_eligibility': 'For each member: now-old_link.active_link_start >= minimum_hold_s, all members eligible.',
          'timer_reset': 'new link actual LINK_UP timestamp, not accepted-command time; initial links use explicit supplied ages (propose active_link_start=0 for same constructed initial state).',
          'initial_age_status': 'REQUIRES_HUMAN_FREEZE',
          'history': {'B2_H4': {'minimum_hold_s': 4, 'threshold': 0},
                      'B2_H8': {'minimum_hold_s': 8, 'threshold': 0},
                      'old_clock': 'global last_accepted_switch_time; first switch has no hold block'},
          '5s_sampling': 'If link_up=0, H4 first eligible t=5, H8 t=10. General elapsed eligibility H<=actual_hold<H+5 absent other blockage; never convert H to epoch counts.',
          'threshold_boundary': 'B1 chooses positive deltaV; threshold equality accepted; exact HOLD tie still HOLD.',
          'shared_pool': 'Read same pool; apply own per-link eligibility to its members without regenerating advantaged proposals.',
          'final_robustness_inclusion': 'Proposed include B2-v2-H4/H8 as engineering robustness after core B3/B4; numerical reuse and new clock need approval, not best-config selection.',
          'blocks_B3_B4_core': False,
          'compatibility_mode': 'Explicit LEGACY_GLOBAL_ACCEPT_CLOCK adapter for old B2 regression only; default per-link clock cannot claim legacy B2 equality.'}
    registry = draft('gate_f3_v2_baseline_registry', primary_contrast='B4-v2_vs_B3-v2',
        shared_action_contract=CONFIGS[0], shared_search_plan=(out / 'joint_candidate_search_plan.json').relative_to(ROOT).as_posix(),
        scientific_snapshot=snapshot,
        baselines=[
            {'id': 'B0-v2', 'name': 'STATIC/HOLD', 'information': 'CURRENT_STATE_ONLY',
             'core': True, 'rule': 'Always HOLD, same geometry/events/traffic/drain; natural expiry applies.'},
            {'id': 'B1-v2', 'name': 'Batch Ignore-Setup', 'information': 'CURRENT_STATE_ONLY',
             'core': True, 'rule': 'argmin V_v2 over HOLD and every shared executable ideal batch topology',
             'decision_setup_consequence': 'ignored in V; physical legality still real',
             'economic_safety_substitution': False},
            {'id': 'B2-v2', 'name': 'Batch Hysteresis/Minimum-Hold',
             'information': 'CURRENT_STATE_ONLY', 'core_blocker': False, 'definition': b2},
            {'id': 'B3-v2', 'name': 'Batch Setup-Aware Greedy', 'information': 'CURRENT_STATE_ONLY',
             'core': True, 'definition': b3},
            {'id': 'B4-v2', 'name': 'Bounded Joint Root-Action Rollout',
             'information': 'SHORT_HORIZON_FORECAST', 'core': True,
             'rule': 'argmin J_H over HOLD and every exact shared legal batch',
             'forecast': 'current-rate persistence, common source per epoch, no actual future realization',
             'root_action_only': True, 'future_voluntary_actions_inside_branch': False,
             'terminal_penalty': False, 'real_batch_Gate_B_C_D': True,
             'nominal_horizon_s': 10, 'production_worker_count_proposal': 8,
             'v1_multiprocessing_PASS_implies_v2_PASS': False},
            {'id': 'B5-v2', 'name': 'Tiny exact batch oracle', 'information': 'ORACLE_SMALL_FIXTURE_ONLY',
             'main_scale': False, 'role': 'Exhaustive legal root batches, not a future-traffic oracle in core contrasts'},
        ], forbidden=['MARL', 'PPO', 'ADD', 'DROP', 'variable_K', 'adaptive_cadence',
                       'event_triggered_decisions', '720_star_main_experiment'])

    execution = draft('gate_f3_v2_execution_contract', gate='F3-v2-0',
        proposed_decision_cadence_s=5, proposed_rollout_horizon_s=10,
        proposed_max_batch_replace=4, epochs={'start_s': 0, 'step_s': 5,
            'last_possible_decision_s': 595, 'end_exclusive_s': 600,
            'maximum_scheduled_epochs': 120, 'event_extra_decision': False},
        microstep_order=order,
        same_timestamp_tie={'terminal': 'original (time,priority,sequence); expiry0/TX_DONE1/LINK_DOWN2/retarget3/LINK_READY4',
            'new_commands': 'canonical batch member order assigns deterministic reservations and event sequence',
            'observation': 'right-continuous after prior physical/propagation events; no transient graph between commands of one atomic batch',
            'economic': 'HOLD exact tie first; canonical joint proposal order otherwise'},
        traffic={'immutable_external_trace': True, 'arrival_s': [0, 240],
            'at_and_after_240_rate': 0, 'phase_boundaries': [60, 120, 180, 240],
            'normalization': 'inherit D0 reference alpha_star/rho, no renormalization on K* or controller topology',
            'scale': 160},
        drain={'max_s': 600, 'COMPLETE_threshold_bits': 0.01,
            'D2_internal_early_return_bits': 1.0, 'D2_return_is_COMPLETE': False,
            'after240': 'Continue real physical/service drain, controller only at240,245,...,595 while unfinished>0.01; early completion ends run; no600 decision.',
            'at600': 'Settle real events at600, then COMPLETE if threshold met else CENSORED; no artificial clearing.',
            'ranking': 'Full-J contrast only if both COMPLETE; censored residual/delivery/time reported, no truncated-J ranking'},
        horizon={'nominal_s': 10, 'effective_formula': 'H_eff=min(10,600-t)',
            'last_epoch_example': {'t': 595, 'effective_horizon_s': 5, 'end_s': 600},
            'cutoff_rule_status': 'REQUIRES_HUMAN_FREEZE; new v2 boundary rule, not inherited v1 equivalence',
            'same_for_all_batch_branches': True, 'physics_asset_extension': False,
            'setup_completion': 'Actual ready<own window_end (<=600); required transition safety completion must be covered, otherwise horizon-limited rejection.',
            'forecast': 'lambda_hat(t+s)=lambda(t), 0<=s<=H_eff; no actual next traffic phase read.',
            'cross240': 'Retain simple persistence forecast even across a future arrival cutoff before t=240; at240 current observed lambda=0. Real trace always has zero input after240.',
            'post_horizon_drain': False, 'terminal_penalty': False,
            'later_natural_expiry_after_transition_complete': 'Not batch invalidity; real rollout/service sees consequences, reported separately.'},
        network_state_updates='LINK_UP/DOWN/EXPIRE and service/propagation events occur at true timestamps, never delayed to5s controller epochs.',
        geometry_refresh='Inherit E2/P1 physical-event-driven route/delay refresh convention; changing controller cadence does not add periodic geometry refresh.',
        common_router={'primary': 'DeterministicShortestPropagationDelayRouter',
            'robustness': 'DeterministicLoadAwareRouter (current-state-only implementation)',
            'same_scenario_and_parameters_only_router_replaced': True},
        objective='J=sum_f integral (A_f-D_f) dt = sum_f integral (Q_f+I_f)dt; no switch/setup/outage hand penalty',
        future_policy={'B1_B2_B3': 'current Q/I/current lambda/service/routes plus deterministic Gate C metadata; no forecast/actual future traffic',
            'B4': 'same physics plus root-local current-rate-persistence forecast; no future controller actions or actual future realization'},
        fairness='same K*/initial states/geometry/trace/rho/capacity/scheduler/router/cadence/raw singles/joint pool/batch safety/drain and tolerances; branch identity per epoch and entire initial state across runs',
        K_star=None, experiment_grid_status='REQUIRES_SEPARATE_HUMAN_FREEZE',
        formal_performance_runs_authorized=False,
        provisional_policy='No global controller ranking; core contrast B4-v2 vs B3-v2, router-matched replay.')

    k0 = draft('gate_k0_v1_2_batch_audit_proposal', parent='configs/gate_k0_contract_v1_1_DRAFT.json',
        parent_draft_sha256=sha(ROOT/'configs/gate_k0_contract_v1_1_DRAFT.json'),
        parent_frozen=False, existing_thresholds_changed=False, K_star_selected=False,
        finding='16 legal singleton REPLACE is not a certificate of four mutually compatible joint replacements.',
        retain={'times': list(range(0, 571, 30)), 'candidate_K': contracts['configs/gate_k0_contract_v1_1_DRAFT.json']['K_candidates'],
                'occupancy_band': [0.15, 0.5], 'draft_18_over_20_conditions': 'untouched pending approval',
                'lifetime': 'L_usable_within_horizon, right-censor flag, actual readiness',
                'K4_ROLE': 'VERY_SPARSE_HISTORICAL_REFERENCE'},
        proposed_metrics=[
            {'name': 'M_resource(t,K)', 'meaning': 'Maximum resource-independent subset of uncapped physically legal singleton inventory, with old/new footprint and parallel-pair conflicts; exact conflict-graph independent-set solver, not matching.', 'role': 'DIAGNOSTIC'},
            {'name': 'M_joint(t,K)', 'meaning': 'Maximum cardinality among resource-independent batches additionally passing whole Gate B/C/time-line safety; report exact/certified-bound status. Pairwise compatibility alone is insufficient.', 'role': 'DIAGNOSTIC'},
            {'name': 'exists_safe_size_2_3_4', 'meaning': 'Separate certified booleans with witnesses or exact infeasibility. Exhaustion of bounded search => UNKNOWN, never FALSE.', 'role': 'DIAGNOSTIC_AND_POSSIBLE_FUTURE_GATE'},
            {'name': 'mode_composition', 'meaning': 'For each feasible size: all BBM/all MBB/mixed composition witnesses/counts if exact; whole transition safety and completion bounds.', 'role': 'DIAGNOSTIC'},
            {'name': 'conflict_reasons', 'meaning': 'Repeated old, old/new terminal footprint, existing reservation/owner, parallel pair, physical-window and joint connectivity conflict.', 'role': 'DIAGNOSTIC'},
            {'name': 'operational_cap_loss', 'meaning': 'Compare full structural witnesses with proposed capped runtime pool coverage; no traffic or economic score.', 'role': 'DIAGNOSTIC'},
        ],
        possible_new_hard_gate={'proposal': 'exists_safe_size4 over a human-preregistered minimum fraction of20 samples',
            'fraction': None, 'numerator': None, 'denominator': 20,
            'status': 'REQUIRES_HUMAN_FREEZE_NOT_APPLIED',
            'recommendation': 'First record diagnostics; m<=4 permission does not require m=4 always. Do not automatically change K-selection.',
            'bias': 'Could push K upward, penalize terminal/lifetime bottlenecks, prefer spare-terminal MBB structures and exclude useful networks controllable with m1-3. Initial static snapshots also do not prove runtime reservation availability.'},
        solver_boundary='No maximum matching, independent-set solving, Z_K building, uncapped replacement enumeration or structural mode scan executed in this design gate.',
        implementation_dependency='Define/approve batch physical/safety predicate before K0-v1.2 audit; implement validator correctness before selecting K*. Use same predicate in K0 and F3-v2, not economic controller evaluator.',
        audit_performance_firewall=['no traffic rates', 'no Q/I/D outcomes', 'no J', 'no delivery', 'no controller actions/results'])

    fairness_rows = []
    for controller, info, evaluate, eligibility in (
        ('B0-v2', 'CURRENT_STATE_ONLY', 'HOLD only', 'none; physical timeline identical'),
        ('B1-v2', 'CURRENT_STATE_ONLY', 'whole ideal batch V_v2', 'common physical/safety pool'),
        ('B2-v2', 'CURRENT_STATE_ONLY', 'B1-v2 deltaV + per-binding hold', 'common pool + own hold filter'),
        ('B3-v2', 'CURRENT_STATE_ONLY', 'whole batch deltaV*min_eta', 'common physical/safety pool'),
        ('B4-v2', 'SHORT_HORIZON_FORECAST', 'actual cloned joint-root J_H', 'exact same pool as B3'),
    ):
        fairness_rows.append({'controller': controller, 'cadence_s': 5,
            'max_batch': 4, 'K_star': None, 'initial_state': 'same',
            'single_universe': 'same', 'joint_pool': 'same except B0 unused',
            'router_service_traffic': 'same', 'information': info,
            'evaluation': evaluate, 'eligibility': eligibility})
    fairness = draft('f3_v2_baseline_fairness_matrix', rows=fairness_rows,
        comparison_claim='Same bounded search opportunity isolates current snapshot proxy vs explicit predictive dynamics; it does not prove 10s globally optimal control.',
        same_state_audit='Given identical root, pool IDs/order/hash must match across controller types. At later epochs controllers may have diverged live states; no requirement their actual proposal hashes remain equal.',
        search_mismatch_ablation_required=False,
        future_search_change='Any J-guided B4-specific beam requires additional B3-SEARCH_MATCHED and separate approval before a prediction-only claim.',
        information_asymmetry='B4 extrapolates common current lambda; B3 uses same observed lambda without forward integration. Different access to actual future realization is forbidden for both.')

    gates = [
        ('V2-A', '新控制调度与物理事件解耦',
         ['epochs0,5,...,595; no600; physical events at1.3/7.25等非epoch及时执行',
          '240 current lambda=0; real drain to next5s boundary; early COMPLETE threshold0.01',
          'simultaneous propagation/terminal/decision priority; shifted synthetic absolute-time fixtures',
          '595 horizon cap common to HOLD/all batches; stale horizon fail closed']),
        ('V2-B', '联合 batch safety 与 atomicity',
         ['duplicate old/new/terminal, reservation ownership, parallel pairs, cross-release chains rejected',
          'two singles individually legal but joint partition rejected; safety-rejected prefix not automatically pruned as proof',
          'validation no live mutation; late last member failure rolls back entire transaction',
          'Gate C ready==end and original epsilon; unknown end after600 not fabricated']),
        ('V2-C', '并发 BBM/MBB 资源和状态守恒',
         ['size2/3/4 allBBM/allMBB/mixed synthetic fixture, unequal TX free times and setup readiness',
          'one satellite D1/D2 independent, fixed ports untouched; no terminal double occupancy',
          'visibility abort/stale event per reservation; remaining independent members continue',
          'Q/I/D conservation, nonnegative queues, capacity, in-flight closure; batches and per-link counts consistent']),
        ('V2-D', 'B1/B2/B3-v2 与 information boundary',
         ['m1/cadence2 same singleton pool compare old B1/B3 score/action/tie and state chain',
          'whole graph batch V_v2 recomputed, nonadditive congestion example; zero unfinished and in-flight-only Psi0',
          'B1 economics ignores setup but execution real; B3 min_eta deterministic; no future trace access',
          'B2 per-link LINK_UP ages, H4/H8 seconds, threshold0 exact ties; separate legacy-global-clock compatibility']),
        ('V2-E', 'B4 joint rollout/determinism/tiny oracle',
         ['6-10node tiny fixtures U<=8 enumerate0..4 all subsets, no production-scale enumeration',
          'complete physical/safety oracle vs pairwise conflicts; exact branch objective/event/state comparison',
          'common beam recall by size, certified legal batch count, omitted objective-best action diagnostic',
          'B3/B4 agree only zero setup & constructed proxy-exact toy conditions; generally not required to choose same action',
          'serial-vs8 worker full batch payload/every branch and multi-epoch checkpoints/state chain; no orphan/leak']),
        ('V2-F', '控制器动作权限与搜索公平性',
         ['same root identical pool IDs/order/hash, raw budgets/strata/validation caps',
          'same initial state/traffic geometry K* cadence router/capacity; no result-based proposal selection',
          'shared pool economics starts only after pool frozen; full candidate evaluation or operational failure',
          'adaptive-beam if authorized requires search-matched ablation; no cross-router ranking']),
        ('V2-G', '成本/扩展性与最终preflight',
         ['engineering-only short evolving160 prefix; no registered performance experiment until independent authorization',
          'count expansions/validation/snapshot/rollouts, walltime/RSS/worker lifecycle; deterministic count budget',
          'fault/timeout evidence; stop rather than scientific ranking of incomplete evaluations',
          'full repository regressions after implementation, v2 preflight/frozen hash chain; old overlays unchanged',
          'K0-v1.2/K1 approved K*+topology, all human budgets frozen, new execution manifests ready']),
    ]
    plan = draft('f3_v2_implementation_and_test_plan', gates=[{
        'gate': name, 'purpose': purpose, 'requirements': reqs,
        'PASS': 'All listed deterministic tests and invariants pass; evidence/seals present.',
        'FAIL_STOP': 'Any semantic mismatch, missing evidence, leakage, capacity/conservation failure or frozen mutation; persist evidence then stop, no tolerance changes.'}
        for name, purpose, reqs in gates],
        tiny_oracle={'nodes': '6-10', 'single_candidates_max_for_fixture': 8,
            'subsets_through_size4_max': sum(math.comb(8, k) for k in range(5)),
            'exact_oracle_information': 'same frozen forecast for B4 comparison, not actual future traffic',
            'quality_outputs': ['legal/action cardinality counts', 'joint safety outcomes', 'set recall by size',
                                'B3 best-in-pool vs exact snapshot best', 'B4 best-in-pool vs exact J_H best',
                                'deterministic exact ties/None routes'],
            'now_executed': False},
        compatibility={'mode': 'batch_max1/cadence2/full10s',
            'checks': 'Same singleton universe/policy/forecast/geometry/root; score/action/event/state trajectory comparison for B1/B3/B4; B2 old global timer explicit separate mode.',
            'hash_identity_claim': False, 'historical_binary_equivalence_claim': False},
        dependency_order=[
            {'step': 1, 'work': '人工批准 action/time/horizon/safety/score/search contracts；冻结pending budgets', 'estimate_person_days': '1-2'},
            {'step': 2, 'work': 'shared batch executor + scheduler/type/ledger/validation；V2-A/B/C', 'estimate_person_days': '4-6'},
            {'step': 3, 'work': 'shared structural joint proposer + whole-graph snapshot + B3-v2；V2-D核心', 'estimate_person_days': '3-5'},
            {'step': 4, 'work': 'B4-v2 joint evaluator/forecast cutoff/8worker payload＋tiny oracle；V2-E', 'estimate_person_days': '4-6'},
            {'step': 5, 'work': 'B1-v2接相同pool/真实batch；V2-D与V2-F公平性', 'estimate_person_days': '1-2'},
            {'step': 6, 'work': 'B2-v2逐链hold＋H4/H8鲁棒性，非核心阻塞', 'estimate_person_days': '1-2'},
            {'step': 'parallel structural dependency after validator PASS', 'work': '经授权实施K0-v1.2 exact batch兼容审计/选K*/K1新初态', 'estimate_person_days': '3-5'},
            {'step': 7, 'work': 'V2-G engineering成本、完整回归、新preflight、独立实验预注册', 'estimate_person_days': '2-3'},
        ],
        total_estimate='Core engineering and structural prerequisites roughly18-29 person-days, uncertain; test/runtime delays excluded, not promised wall-clock completion.',
        schedule={'target_submission': '2026-12 mid-to-late',
            'October': 'freeze + shared batch/A-C + B3/B4 implementation',
            'early_November': 'finish oracle/fairness/K0-K1/preflight',
            'November': 'separately authorized160 core results and writing in parallel; B2 robustness last',
            'early_December': 'robustness/interpretation/manuscript close; reserve review buffer',
            'defer': ['MARL/PPO', 'ADD/DROP', 'variableK', 'adaptive/event cadence', '720main']},
        no_automatic_next_gate=True)

    write(out / 'repository_impact_matrix.json', impact)
    write(out / 'batch_action_semantics_review.json', batch)
    write(out / 'baseline_fairness_matrix.json', fairness)
    write(out / 'joint_candidate_search_plan.json', search)
    write(out / 'k0_dependency_review.json', k0)
    write(out / 'implementation_and_test_plan.json', plan)
    for name, value in zip(CONFIGS, (batch, registry, execution, k0)):
        write(ROOT / name, value)

    overlay = contracts['configs/gate_f3_b4_production_multiprocessing_overlay_v1.json']
    registration = contracts['configs/gate_f3_b4_production_multiprocessing_registration_v1.json']
    successor = contracts['configs/b4_executor_compatibility_successor_v1.json']
    def canon_check(doc):
        body = dict(doc); expected = body.pop('canonical_sha256')
        return hashlib.sha256(canonical(body).encode()).hexdigest() == expected
    runtime_checks = {
        'overlay_PASS': overlay['status'] == 'PASS',
        'registration_canonical': canon_check(registration), 'overlay_canonical': canon_check(overlay),
        'registration_overlay_file_hash': sha(ROOT / registration['overlay']) == registration['overlay_sha256'],
        'production_workers8': overlay['production_worker_count'] == 8,
        'overlay_current_code_hashes': all(sha(ROOT / name) == value for name, value in overlay['optimized_code_hashes'].items()),
        'successor_canonical': canon_check(successor),
        'successor_authorized': successor['status'] == 'AUTHORIZED_RUNTIME_SUCCESSOR',
        'successor_actual_source': sha(ROOT / successor['file']) == successor['successor_hash'],
        'successor_evidence_hash': sha(ROOT / successor['evidence']['report']) == successor['evidence']['report_sha256'],
        'overlay_registry_hash': sha(ROOT / overlay['authorized_executor_successor']['registry']) == overlay['authorized_executor_successor']['registry_sha256'],
        'parent_runtime_chain_file_hash': sha(ROOT / 'configs/gate_f3_b4_runtime_chain_v1.json') == overlay['parent_chain_file_sha256'],
        'chain_entry_contiguous': overlay['successor_chain_verification']['validated_chain'] == [successor['parent_hash'], successor['successor_hash']],
    }
    write(out / 'runtime_provenance_audit.json', draft('f3_v2_v1_runtime_provenance', checks=runtime_checks,
        pass_all=all(runtime_checks.values()), validation_scope='Static registration/parent/current/evidence SHA checks, not re-running v1 preflight or any branch.',
        v2_runtime_acceptance=False))

    impact_table = '\n'.join(f"| {r['module']} | {r['classification']} | {r['observed']} | {r['proposed_change']} |"
                              for r in impact['rows'])
    parent_hashes = {name: sha(ROOT / name) for name in contracts}
    unresolved = [
        '5s cadence、max batch4的科学设计值（本轮只有草案）',
        'raw32/32/64、singleton16/8+8是否继承及结构排序规则',
        'beam width W、非HOLD batch budget M、结构expansion/validation caps、rollout预算 E>=1+M、operational timeout',
        'B3 batch eta=min(member eta) 聚合定义；不能由旧singleton合同自动推出',
        '595决策的H_eff=min(10,600-t)统一截断；不延长资产',
        'Z_K* safety regime继承STRICT_CONNECTED的批准；现有active/admit实际判定不扩成新物理约束',
        'B2逐链接LINK_UP计时、初态age及H4/H8是否纳入最后鲁棒性',
        'K0-v1.1冻结／v1.2新增batch audit诊断与可选hard gate；K*与K1初态仍未知',
        'F3-v2实验grid/manifest/result seal需要另行预注册；旧F3-v1不授权v2性能运行',
    ]
    doc1 = f'''# Gate F3-v2-0 联合拓扑重构设计与仓库审计

**DRAFT_NOT_FROZEN；仅设计与静态审计，无生产实现、结构扫描或性能实验。**

本次 attempt：`{out.relative_to(ROOT).as_posix()}`。5 s cadence 与每epoch最多4条REPLACE是待审批设计，不是最优参数。保留10 s名义horizon、真实事件驱动物理层、160星、外生0–240 s业务和600 s最大drain。目标为B4核心期刊论文，暂不MARL/PPO。历史F3-v1/K4、K0-v1 FAIL、K0-v1.1 DRAFT、A–E资产和8-worker overlay全部保护。

## 1. 实际代码能力与缺口

Gate B已有多个Reservation并发推进，`submit(commands)`先在transaction clone上逐条执行，任何失败不更新live，全部成功后执行同时间事件并一次更新live。Gate C公开接口仍是单terminal-pair，D2 `_apply_due_actions`也是逐条proposal。**不能将多个单动作依次schedule当成原子batch**：后一个拒绝时，前一个可能已经改变live状态。B1/B3和B4都使用同一single proposal set；旧F0 registry的implemented=false只是历史登记，不能用它判断现在代码未实现。

REPLACE流程为：物理evaluate中trial Gate B验证ready→transition profiler→regime policy→真实submit。Gate B `_connect`先检查terminal/old-release owner/parallel pair和ready，再创建bilateral reservation、target peer、版本，标记旧链DRAINING或MBB release_owner；MBB的旧链在新LINK_UP后drain。批次后面的命令能看到trial里前面的reservation，所以会拒绝冲突。事件可以并发，物理先后关系并未被并行计算取消。

旧B2是global accepted-command timer，首次没有hold阻塞，并非每条链LINK_UP计时。旧B4是root-action-only rollout，不是枚举未来多epoch action树。旧8-worker pool调度可继承，但任务只有一个record/spec、结果只有一个proposal_id；v2 batch payload/validator/clone都要重新验收，旧PASS不能代替新PASS。已登记overlay/registry/current代码与supporting evidence的hash关系仅做静态核对，详见runtime_provenance_audit.json。

| 模块 | 分类 | 当前真实实现 | v2影响 |
|---|---|---|---|
{impact_table}

具体函数与一基行号在repository_impact_matrix.json。2s guard位于controller_runner和DrainDecisionPolicy，P1 runner消费该policy；10s在forecast、rollout controller/evaluator、_finish断言和冻结合同。不得在旧文件原地替换这些常量。

## 2. 调度合同草案

周期点为0,5,…,595 s；最多120个可能点。每次先推进到实际时间并settle既有propagation与Gate B events，再得到右连续DECISION_ROOT，生成同一候选集，controller只读评价，记录POST_OBSERVE，原子提交选择的batch，再刷新graph/router/service得到POST_DECISION。要求DECISION_ROOT=POST_OBSERVE证明假设分支不改live；不要求PRE_CALL=DECISION_ROOT。

同时间戳保留Gate B `(time,priority,sequence)`：expiry0、TX_DONE1、LINK_DOWN2、retarget3、LINK_READY4。命令按共享singleton索引canonical顺序提交，编号/事件sequence确定；worker完成顺序不参与决策。原D2 microstep先结算已承诺传播，后terminal/action，最后router/service，不能把5s变成服务时隙。1.3s建链完成、7.25s失效等都在真实时间执行。

240 s时先观察新业务rate=0；240,245,…,595 s仅在unfinished>0.01bit时继续决策。真实drain可提前完成，D2 1bit early return不能当F3 COMPLETE。600 s结算物理事件后分类COMPLETE/CENSORED，不产生新decision；不clamp/drop/virtual drain。初始归一化alpha*、rho和traffic bytes沿用，不能按K*或当前拓扑重新算load。

**截止边界待批准：H_eff=min(10,600-t)。** 595 s统一预测5s至600，HOLD与所有batch同长度，不外推到605、不补terminal penalty、不延长Gate C资产。该规则需要新v2 forecast/evaluator adapter，因为旧实现硬拒绝非10s。名义10s不是已证明最优；最大horizon附近不代表完整physical lifetime。若不批准截断，须另选晚期决策规则并单独冻结，不能静默在两个规则间切换。

forecast仍current-rate persistence，root内部不产生未来主动控制。235 s的简单预测可能把当前rate延续到245 s，保持其非oracle性质；真实trace仍在240 s归零，240时的新预测为0。物理可知window/expiry可读，未来真实traffic/最终J不可读。当前几何刷新沿用E2/P1在起点和物理拓扑事件触发的惯例，不因5s controller cadence擅加刷新。

## 3. 资源独立批量动作

`A_t={{REPLACE_r}}`，0<=m<=min(4,K*)，m=0是HOLD。每条含具体old binding/new terminal pair与member ID；batch含decision time/frame、root hash、joint pool hash、成员序列和batch ID。BBM/MBB来自实际Gate B/C状态，不能controller自报。

对每条r定义footprint=old endpoints∪new endpoints，批次中不同footprint必须互不相交；可以共用卫星的不同终端，不允许共用同一terminal、old binding、reservation、release owner或非法satellite pair。MBB新端口在root时真实IDLE；BBM占用端口只属于自己的old binding，释放和ready由旧TX/retarget/acquisition实际决定。不支持借另一动作将释放的端口、终端交换链、同peer非法并行链或fixed port借用。

validate_batch只读同一个root，逐条Gate C取得窗口/command，整组Gate B trial.submit验证原子性，再profile整个组的真实event timeline与当前已有pending events，并应用原regime policy。必须看全过程而非最终图，也不能把两条独立合法误当联合合法。profile应覆盖所有new ready和选中old release/drain结束；MBB old TX可能晚于new ready，不能只取max(new ready)+epsilon。验证覆盖超出600时报告观察窗口不足，不把600称为自然失效。

验证失败拒绝整个batch；不会由safety删掉经济性差的成员或换更好候选。真实commit一次submit(commands)，失败无部分terminal/Q/I/D改变；commit不一致则证据持久化后STOP。原子的是“验证和接纳”，不是未来物理成功承诺：之后某个reservation因可见性abort，按原Gate B释放、版本检查处理，独立其他成员继续，不回滚已经发生的时间。

原moderate STRICT_CONNECTED判定来自profile的active/admit partition，sparse BOUNDED_OUTAGE仍为2s，不能随cadence改为5s。v2 K*主regime建议继承moderate policy，但该映射待人工批准；没有新增必须全天候连通或k-edge-connectivity硬约束。批量原子化和资源独立限制是新动作合同，需要批准。

固定K指一换一目标预算，无ADD/DROP；并非每一时刻active link count恒等K。BBM暂时减少、MBB暂时增加，自然expiry也可减少。现有内核不会把已自然消失的old link自动补回K。若论文要求真实active始终K，则与BBM和自然失效不相容，必须另立maintenance合同，不能本轮暗中实现。

## 4. shared joint search与B4范围

建议采用同一结构bounded beam：先共同singleton physical universe，再footprint/conflict剪枝，按递增singleton索引扩展至size4；按最小/总截断usable lifetime及canonical order做结构beam保留，完全不读traffic/Q/J/controller结果。单条network safety失败不自动证明组合失败；resource/physical有效但safety失败的prefix可在budget内扩展，最终可执行pool必须整体safety通过。

所有可执行singletons保留，然后按预注册的depth/结构顺序填充合法size2/3/4。pool预算必须至少容纳single预算，并给部分batch留位；不强制四条。exact member集合去重；只有satellite target graph相同但terminal/ready/release不同不得合并。pool在任何经济评价前固定canonical hash，B1/B2/B3/B4同root获得相同pool。

raw32/32/64、singleton16/8+8只是建议继承，全部待批准；beam width W、最大非HOLD batch M、validation/expansion caps、rollout E和operational timeout均留null，不能偷偷写死。16 singletons全部0..4组合有2517个，主规模禁止全部做10s rollout。B4只评价共同pool的HOLD+M，E必须>=1+M，并按pool order归并8-worker结果。

确定性count budget耗尽截断结构搜索并明确记录，不依据J拓展或缩小候选。真正wall timeout/worker错误不作为科学策略：只能明确operational HOLD并封存异常、STOP该性能attempt，不把未评价完整pool的run当科学COMPLETE/CENSORED。不能取先完成的branch，不因机器速度改变science。

## 5. K0依赖

K0-v1.1仍DRAFT，20snapshot/18-20等未被本任务改动。16个single legal replacements不能证明4个资源独立且joint-safe。建议K0-v1.2额外记录M_resource（conflict graph最大independent set）与M_joint（再加整体Gate B/C/safety）；它们不是terminal maximum matching同一问题。size2/3/4必须有certified witness或exact不可行证明，bounded搜索找不到仅为UNKNOWN。

记录BBM-only/MBB-only/mixed的联合兼容性、reservation/terminal/parallel/joint-connectivity冲突、capped runtime pool相对uncapped结构空间的损失。初态snapshot空reservation不证明运行中也可用4条。所有内容只读物理结构，不读J/Q/delivery/traffic。

建议先作为诊断；可选hard gate为某预注册snapshot比例存在safe size4，具体分子留null。它会偏向更密集K/更多spare-MBB资源并排除虽能m1-3控制的场景，不能自动把18/20或原K-selection标准替换掉。人工批准batch predicate后先验收validator，再执行获授权的K0-v1.2/K1；本轮未完整K0、未K* selection。

## 6. 验收、工作量与阻塞项

后续按V2-A调度→V2-B joint atomicity→V2-C并发资源/守恒→V2-D当前状态baselines→V2-E真实batch rollout/oracle/8workers→V2-F公平性→V2-G成本与新preflight。每Gate具体断言及FAIL/STOP在implementation_and_test_plan.json；任何真实mismatch、泄漏、历史修改或守恒失败先持久化再停止，不改tolerance。

tiny oracle仅6–10星、U<=8，最多163个size0..4组合；穷举验证完整joint legality、cardinality、conflicts、ties，量化beam遗漏和B3/B4各自best action。不能要求B3/B4通常选同动作，只在proxy确实精确的专门toy中要求一致。兼容模式m1/cadence2从同root/pool比较旧B1/B3/B4，但不预先承诺历史binary/hash相等；B2需专门legacy global timer模式。

最小代码路径：新v2 action/batch physical validator+service due-action hook+5s runner；shared structural joint proposer；whole-graph snapshot adapter/B3；batch rollout evaluator/forecast cap/B4；8worker batch task与精确clone审计；B1同pool；B2最后。旧Gate B/C/D源码、service allocator/router、v1controllers/runner/overlay保留，不再建第二套仿真。

估计core与结构前置18–29人日（不含长跑和返工保证）：shared executor4–6、shared pool+B3 3–5、B4+oracle4–6、B1 1–2、B2 1–2、K0/K1 3–5、最终engineering验收2–3；部分文档和K0准备可并行，validator必须先验收。以2026年12月中下旬投稿为目标：10月冻结/核心实现，11月初闭合正确性/K0-K1/preflight，11月单独授权结果与写作并行，12月初留复查修改。B2不阻塞核心B3/B4实验，但最终是否纳入鲁棒性要预注册。

待人工冻结清单：

''' + '\n'.join('- ' + item for item in unresolved) + '''

本轮只证明设计与静态审计交付完整，不证明batch implementation PASS或正式performance readiness。完成后STOP，等待人工审核和实施授权。
'''
    (ROOT / DOC1).write_text(doc1, encoding='utf-8')
    fairness_table = '\n'.join(f"| {r['controller']} | {r['information']} | {r['evaluation']} | {r['eligibility']} |"
                              for r in fairness_rows)
    doc2 = f'''# Gate F3-v2 baseline重新设计草案

**DRAFT_NOT_FROZEN；没有实现或运行新控制器。** 公共动作/时间/搜索预算详见联合重构设计与四份DRAFT JSON。核心contrast=B4-v2 vs B3-v2，先共享搜索机会，再比较当前状态proxy和显式网络预测；暂不MARL。

| baseline | 信息边界 | 决策评价 | eligibility |
|---|---|---|---|
{fairness_table}

## 公共数学与动作

公共pool由物理/结构信息确定，含HOLD和合法size1..4 batch；snapshot目标图为 `G_A=(G_admit−all old edges)∪all new edges`，只将本次选择的batch理想瞬时执行，其余pending transition仍以root现状表示。每个batch重新调用selected frozen common router和V_v2 evaluate_edges，不加单动作分数。

V_v2继承scheduler-consistent定义：N_f=Q_f+I_f，C_prop为source路线传播时间和。当前local demand由queue>state_tol或current source/inflight input决定，按原equal_weight_fair_share计算实际allocation；有需求时R_snap为这些local需求节点allocation最小值，Psi=N_f²/(2R_snap)，没有local需求时Psi=0。V=sum[N_f*C_prop+Psi]。这不是path上所有commodity等分capacity的旧v1公式，也不是推进Q/I/D得到的真实J。保留无route/非正allocation等invalid理由和exact ties。

## B1-v2

在HOLD与共同pool的完整理想目标图中选最小V_v2，忽略setup导致的服务中断/延迟收益。真实physical readiness只用于共同合法性，不用eta或真实transition经济性给B1改选候选。执行选中的完整batch必须真实Gate B/C。总unfinished=0沿用HOLD；双方V=Infinity不构造NaN改善值。安全层拒绝，不经济修复。

## B2-v2

明确base=B1-v2，不混用B3。对每个将被替换的old binding检查actual elapsed seconds；建议time origin是该binding实际LINK_UP，new link只有LINK_UP后重置。initial links age需明确，建议constructed initial active_start=0；这会使H4初次可用t=5、H8为t=10，而旧B2首次无hold限制，属于科学语义变更。

旧B2_H4/H8配置均threshold=0，role=ENGINEERING_ROBUSTNESS_ONLY，代码是全局last accepted command timer，保持历史原样。一般5s采样使实际等待在[H,H+5)附近（其余eligibility可再延长），不能把4s/8s机械换成2/4个旧epoch。v2先读取共同pool，再要求每条member eligible，按B1全batch deltaV及threshold选择；threshold equality允许，但经济exact tie仍HOLD。H4/H8是否继续使用、initial-age规则与per-link timer等待人工批准，不按性能调参。建议最终鲁棒性纳入两配置，不让B2开发阻塞B3/B4。

## B3-v2

不是取单链前三/四名。共同结构beam对新增member形成的整个batch生成目标图；B3对每个保留batch重算V。建议 `deltaV_A=V_H−V_A`，`eta_r=L_usable,r/L_remaining,r`，`eta_A=min_r eta_r`，`S_A=deltaV_A*eta_A`。选择最大正S，否则HOLD。m可为1/2/3/4，不强制填满；所有时间来自actual Gate C/Gate B，并保留window右删失标记。

min_eta是新的待批准保守聚合，不是精确network service loss定理；one-member时恢复旧eta公式。不能用独立deltaV求和替代共享拥塞作用，也不执行10s service rollout。B3可使用current lambda、Q/I、current router/service和known windows，但不读forecast对象/真实未来trace。

## B4-v2

评价同一pool每个完整batch的 `J_H(A;t)=sum_f integral_t^(t+H_eff) N_f^A(s) ds`，HOLD同时评估。branches从同canonical root和current-rate-persistence forecast构造，真实joint Gate B/C→graph→common router→service→Q/I/D。root后不再调用controller，没有未来action tree，无terminal/switch/setup/outage penalty，所有effects自然进入J。nominal H=10，late截止统一H_eff=min(10,600-t)待批准。

持久8workers只是调度，不产生额外candidate；parent依次HOLD及canonical pool order归并，不按future完成顺序或机器速度选动作。live root不得被clone修改，branch之间/epoch之间mutable state不共享。v2 task是batch，旧单动作8-worker PASS只提供机制参考，必须重新通过多epoch exact/state-chain/orphan检查。

## 搜索公平性与解释边界

B3/B4对同一个root拥有完全相同的raw universe、singleton预算、joint beam/pool、整体safety和m<=4权限。共同pool在评分前hash；不同controller造成后续状态分叉后，不要求其实际proposal hashes仍相同。主路由条件内同primary router；robustness重放同initial topology/trace/params，仅换common router。

这一设计不需要额外search-matched controller，B3本身就是search-matched对照。若以后B4改用J-guided adaptive beam而B3使用不同beam，则必须新增B3-SEARCH_MATCHED：在同一由B4选出的pool内做snapshot选择，承认proposal generation含预测信息，分开报告搜索贡献与评价贡献；不能仍声称纯rollout收益。本轮不采用这种变体。

tiny B5仅穷举小fixture完整root batches，报告bounded pool recall、遗漏size及最佳动作是否遗漏，并分别比较B3的snapshot oracle和B4的same-forecast J oracle。两者通常不同不能当FAIL；只有专门proxy-exact条件才检验一致性。主实验双方COMPLETE时报告完整J contrast；任一CENSORED报告残余work/delivery/time，不截断J排名。

设计就绪不等于baseline已实现，所有预算/数值仍需人工冻结。STOP，不运行controller性能。
'''
    (ROOT / DOC2).write_text(doc2, encoding='utf-8')

    checks = {
        'all_requested_artifacts_exist': all((ROOT / p).is_file() for p in CONFIGS + [DOC1, DOC2]),
        'all_contracts_marked_DRAFT': all(v['status'] == STATUS and not v['frozen'] and not v['implementation_authorized'] for v in (batch, registry, execution, k0)),
        'proposed_5s_4batch_10h': execution['proposed_decision_cadence_s'] == 5 and execution['proposed_max_batch_replace'] == 4 and execution['proposed_rollout_horizon_s'] == 10,
        'epochs_exclude_600': len(range(0, 600, 5)) == 120 and list(range(0, 600, 5))[-1] == 595,
        'K_star_unselected': batch['K_star'] is None and execution['K_star'] is None and not k0['K_star_selected'],
        'A_to_G_test_gates_defined': [x['gate'] for x in plan['gates']] == ['V2-A','V2-B','V2-C','V2-D','V2-E','V2-F','V2-G'],
        'B0_to_B5_registered': [x['id'] for x in registry['baselines']] == ['B0-v2','B1-v2','B2-v2','B3-v2','B4-v2','B5-v2'],
        'B3_B4_primary_shared_pool': search['primary_search_matched_by_design'] and not fairness['search_mismatch_ablation_required'],
        'no_numerical_search_budgets_silently_frozen': all(search['pending_budgets'][x] is None for x in ('beam_width','max_non_hold_batch_candidates','max_joint_validation_calls','max_structural_expansions','max_rollout_evaluations_including_HOLD','operational_wall_timeout_s')),
        'snapshot_v2_not_v1_equal_path_share': 'equal_weight_fair_share' in snapshot['R_snap'] and 'otherwise0' in snapshot['V'],
        'K0_existing_thresholds_untouched': k0['existing_thresholds_changed'] is False,
        'v1_runtime_static_provenance': all(runtime_checks.values()),
        'no_implementation_or_performance_imports': not any(isinstance(n, (ast.Import,ast.ImportFrom)) and any(x in ast.unparse(n) for x in ('dynamic_lisl','subprocess','multiprocessing')) for n in ast.walk(ast.parse(Path(__file__).read_text(encoding='utf-8')))),
        'generator_static_syntax': True,
    }
    write(out / 'static_contract_validation.json', draft('f3_v2_static_contract_validation', checks=checks,
        pass_all=all(checks.values()), scope='Static schema/logic/AST/hash checks only; no simulator, controller, fixture or performance run.'))
    after = {name: sha(ROOT / name) if (ROOT / name).is_file() else None for name in before}
    changed = [p for p in before if before[p] != after[p]]
    unexpected = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
        if p.is_file() and out not in p.parents
        and not any(x in p.parts for x in ('__pycache__','.git','.pytest_cache'))
        and p.suffix not in ('.pyc','.pyo') and p.relative_to(ROOT).as_posix() not in before
        and p.relative_to(ROOT).as_posix() not in NEW_FILES)
    integrity_ok = not changed and not unexpected
    write(out / 'historical_integrity_report.json', draft('f3_v2_historical_integrity',
        protected_file_count=len(before), before_sha256=before, after_sha256=after,
        changed_or_missing=changed, unexpected_new_files=unexpected,
        all_historical_files_unchanged=integrity_ok,
        scope='Whole pre-existing project except cache/VCS internals. Historical results hashed only, never parsed for design.'))
    write(out / 'input_read_log.json', draft('f3_v2_input_read_log', reads=read_log,
         parent_contract_hashes=parent_hashes, historical_result_content_read=False,
         scope='Static source/contracts and exact runtime registry evidence hash only.'))
    outcome = 'F3_V2_JOINT_RECONFIGURATION_DESIGN_READY_FOR_HUMAN_REVIEW' if all(checks.values()) and integrity_ok else 'F3_V2_DESIGN_BLOCKED'
    report = draft('f3_v2_design_review_report', formal_outcome=outcome,
        static_validation_pass=all(checks.values()), historical_integrity_pass=integrity_ok,
        protected_file_count=len(before), unresolved_human_freeze_items=unresolved,
        design_blockers=[] if outcome.endswith('READY_FOR_HUMAN_REVIEW') else ['See static_contract_validation/historical_integrity_report'],
        implementation_and_performance_blockers=['No approved joint/search/horizon budgets', 'K0 draft not frozen/K* unselected/K1 topology absent', 'Batch adapters and v2 controllers not implemented or accepted'],
        final_answers={
            '1_Gate_B': 'Physical concurrency/list transaction sufficient for conservative independent batches; network-level joint Gate C/safety/service adapter still required.',
            '2_modules': 'New v2 types, batch physical/safety adapter, due-action hook, source/joint proposer, B1-B4/hold-age, cadence/drain runner, forecast cutoff, batch rollout/clone/task/evidence/preflight interfaces. Frozen modules remain unchanged.',
            '3_shared_action': 'Same canonical HOLD/BATCH_REPLACE, common pool and actual Gate B/C executor; B0 alwaysHOLD.',
            '4_fairness': 'Shared structural bounded beam + exact same batch pool before scoring. B3 whole-graph current snapshot vs B4 full actual rollout; if later adaptive search diverges require search-matched ablation.',
            '5_complexity_risks': 'Moderate-to-high; combined connectivity, transaction boundaries, late horizon, B2 age change, branch transport/clone isolation, structural search omissions and natural expiry.',
            '6_K0': 'Need separate batch compatibility diagnostics; any new hard gate needs human approval; single legal>=16 not size4 certificate.',
            '7_minimum_B4': 'Accepted shared validator/service hook/cadence+pool, batch forecast/evaluator/controller, serial reference and8worker payload, clone field audit, full chain/evidence/preflight.',
            '8_plan': 'shared executor→B3/shared pool→B4/oracle→B1→B2; K0/K1 after validator in structural track; V2-G final. Rough18-29 person-days plus separately authorized experiment time.'},
        production_modified=False, new_controller_implemented=False, exact_matching_executed=False,
        full_K0_executed=False, K_star_selected=False, K1_started=False,
        new_registered_P1_executed=False, P2_started=False, RL_started=False,
        compatibility_equivalence_claim=False, v2_runtime_PASS_claim=False,
        stop='STOP_WAITING_FOR_HUMAN_REVIEW_AND_IMPLEMENTATION_AUTHORIZATION')
    write(out / 'f3_v2_design_review_report.json', report)
    write(out / 'artifact_hashes.json', draft('f3_v2_design_artifact_hashes',
        attempt_files={p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()},
        deliverables={name: sha(ROOT / name) for name in CONFIGS + [DOC1, DOC2]},
        design_generator_sha256=sha(Path(__file__))))
    print(json.dumps({'formal_outcome': outcome, 'output_directory': str(out),
                      'static_checks': checks, 'protected_files': len(before),
                      'historical_unchanged': integrity_ok}, ensure_ascii=False, indent=2))
    return 0 if outcome.endswith('READY_FOR_HUMAN_REVIEW') else 1


if __name__ == '__main__':
    raise SystemExit(main())
