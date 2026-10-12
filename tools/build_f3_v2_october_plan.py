# -*- coding: utf-8 -*-
"""Planning artifacts only: no simulator/controller import or execution."""
import collections
import datetime as dt
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
ATTEMPT = ROOT / "outputs/f3_v2_october_plan_20261008T122321_890739Z"
STATUS = "DRAFT_NOT_FROZEN"
OUTPUTS = [
    "docs/F3_V2_OCTOBER_CRITICAL_PATH.md",
    "configs/F3_V2_PAPER_EXPERIMENT_MATRIX_DRAFT.json",
    "configs/F3_V2_RUNTIME_BUDGET_PLAN.json",
    "configs/F3_V2_OCTOBER_DELIVERABLES.json",
]


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def write_json(path, value):
    if path.exists():
        raise RuntimeError("Refuse to overwrite: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def draft(schema):
    return {"schema": schema, "status": STATUS, "frozen": False,
            "created_date_local": "2026-10-08", "timezone": "Asia/Shanghai",
            "implementation_authorized_by_this_plan": False,
            "formal_performance_authorized": False,
            "target_evidence_date": "2026-10-31", "MARL_PPO_in_scope": False}


def main():
    for rel in OUTPUTS:
        if (ROOT / rel).exists():
            raise RuntimeError("Existing output: " + rel)
    before = json.loads((ATTEMPT / "historical_integrity_before.json").read_text(encoding="utf-8"))["files"]
    parents = [
        "docs/GATE_F3_V2_JOINT_RECONFIGURATION_DESIGN_CN.md",
        "docs/GATE_F3_V2_BASELINE_REDESIGN_CN.md",
        "configs/gate_f3_v2_joint_action_contract_DRAFT.json",
        "configs/gate_f3_v2_baseline_registry_DRAFT.json",
        "configs/gate_f3_v2_execution_contract_DRAFT.json",
        "configs/gate_k0_contract_v1_1_DRAFT.json",
        "configs/gate_k0_v1_2_batch_audit_proposal_DRAFT.json",
        "outputs/gate_f3_v2_design_20261008T112538_143340Z/implementation_and_test_plan.json",
        "outputs/gate_f3_v2_design_20261008T112538_143340Z/joint_candidate_search_plan.json",
        "configs/gate_f3_traffic_stable_v1.json",
        "configs/gate_f3_traffic_hotspot_migration_v1.json",
        "configs/gate_d0_od_manifest_16.json",
        "configs/z_moderate_v1.json",
    ]
    parent_hashes = {rel: sha(ROOT / rel) for rel in parents}
    prior_plan = json.loads((ROOT / parents[7]).read_text(encoding="utf-8"))
    milestones = [
        {"id": "M11", "due": "2026-10-11", "work": "科学合同、K0/K1审批包；结构与计算资源预算初估；一次性审批清单",
         "acceptance": "所有科学未决项集中列出；早期成本可复现，未实现项明确NOT_MEASURED；不能伪称新B4实测",
         "dependencies": [], "risk": "审批未完成则后续日期不可保证"},
        {"id": "M16", "due": "2026-10-16", "work": "获批K0/K1审计与初态、共享JointAction/BatchPhysicalValidator、5s调度与batch安全验收",
         "acceptance": "K*按结构规则选定；全部旧证据不变；联合原子性/全时间线安全/BBM-MBB/守恒通过",
         "dependencies": ["M11", "human_contract_freeze", "implementation_authorization"], "risk": "K0/K1与安全验证相互依赖，先完成validator再完成K1联合证据"},
        {"id": "M20", "due": "2026-10-20", "work": "同一结构batch pool、B1/B3/B4-v2核心、最小B2、evidence writer",
         "acceptance": "同一root/pool/hash；B3全图snapshot；B4真实joint rollout；信息边界及失败持久化通过",
         "dependencies": ["M16"], "risk": "不能以独立单链得分相加替代联合执行"},
        {"id": "M23", "due": "2026-10-23", "work": "serial/8-worker多epoch精确等价、tiny oracle、完整回归、成本终估、P1-v2 preflight",
         "acceptance": "新版本每分支/四checkpoint/自然state-chain exact；全回归100%；42项最终manifest、预算和hash齐全",
         "dependencies": ["M20"], "risk": "旧multiprocessing PASS不能替代新验收；任一失败禁止正式启动"},
        {"id": "M24_29", "start": "2026-10-24", "due": "2026-10-29", "work": "独立人工运行授权后，按冻结顺序执行全部42项非MARL实验",
         "acceptance": "每项COMPLETE/CENSORED或完整失败证据；无删项；invariant失败持久化后STOP",
         "dependencies": ["M23", "formal_run_authorization"], "risk": "不可用截断J排名或加快失败重试来赶工"},
        {"id": "M30_31", "start": "2026-10-30", "due": "2026-10-31", "work": "验证原始数据、paired统计、主要图表/caption、证据封存与局限清单",
         "acceptance": "11项交付逐项核验；正式结果/工程验收分开；42项ledger全保留；canonical manifest与artifact seal可复现",
         "dependencies": ["M24_29"], "risk": "阴性/重合/无法排空结果仍报告；封存不等于必须证明B4更好"},
    ]

    rows = []

    def add(block, controller, rho, topology="K_STAR", traffic="HOTSPOT_MIGRATION",
            cadence=5, batch=4, router="SHORTEST_PROPAGATION_DELAY", hold=None, purpose="", questions=None):
        rid = "OCT26-" + block + "-%02d" % (sum(r["block"] == block for r in rows) + 1)
        epochs = len(range(0, 600, cadence))
        max_pool = 16 if batch == 1 else 32
        rows.append({"run_id": rid, "execution_order": len(rows) + 1, "block": block,
                     "status": "PLANNED_NOT_AUTHORIZED", "scale": 160, "controller": controller + "-v2",
                     "rho": rho, "topology_regime": topology,
                     "nominal_K": 4 if topology == "K4_HISTORICAL_REFERENCE" else None,
                     "topology_artifact": "configs/z_moderate_v1.json" if topology == "K4_HISTORICAL_REFERENCE" else "PENDING_K1_K_STAR_ARTIFACT",
                     "router": router, "traffic": traffic,
                     "traffic_asset": "configs/gate_f3_traffic_stable_v1.json" if traffic == "STABLE" else "configs/gate_f3_traffic_hotspot_migration_v1.json",
                     "decision_cadence_s": cadence, "max_batch_replace": batch,
                     "rollout_horizon_nominal_s": 10, "minimum_hold_s": hold,
                     "hysteresis_threshold": 0 if controller == "B2" else None,
                     "scientific_role": purpose, "research_question_ids": questions or [],
                     "runtime_budget": {"status": "PENDING_RESULT_BLIND_MEASUREMENT", "maximum_scheduled_epochs": epochs,
                                        "maximum_rollout_evaluations_per_epoch": 1 + max_pool if controller == "B4" else 0,
                                        "max_non_hold_pool_proposed": max_pool,
                                        "estimated_wall_clock_s": None, "approved_operational_timeout_s": None,
                                        "calibration_key": controller + ":%s:%d:%d:%s" % (topology, cadence, batch, router),
                                        "formula": "fixed episode overhead + epoch_count * measured conservative per-epoch cost + non-epoch service/evidence overhead"},
                     "requires": ["scientific_contract_freeze", "K0_K1_or_exact_K4_binding", "new_v2_acceptance",
                                  "runtime_budget_filled", "final_manifest_hash", "human_formal_run_authorization"]})

    # Primary contrasts first, all ordering is proposed now, never result driven.
    for rho in [0.5, 0.8, 1.0]:
        for c in ["B3", "B4", "B0", "B1"]:
            add("CORE", c, rho, purpose="三负载主对比及STATIC/Ignore-Setup对照", questions=["Q1", "Q2", "Q3", "Q6", "Q10"])
    for c in ["B3", "B4", "B0", "B1"]:
        add("STABLE", c, 0.8, traffic="STABLE", purpose="同平均负载下稳定业务vs热点迁移", questions=["Q7", "Q10"])
    for rho in [0.5, 0.8, 1.0]:
        for c in ["B3", "B4"]:
            add("SPARSE", c, rho, topology="K4_HISTORICAL_REFERENCE", purpose="固定K* vs历史稀疏K=4结构敏感性", questions=["Q4", "Q10"])
    for c in ["B0", "B1"]:
        add("SPARSE", c, 0.8, topology="K4_HISTORICAL_REFERENCE", purpose="K=4锚点的STATIC/Ignore-Setup上下文", questions=["Q2", "Q3", "Q4"])
    for cadence, batch in [(2, 1), (2, 4), (5, 1)]:
        for c in ["B3", "B4"]:
            add("FACTORIAL", c, 0.8, cadence=cadence, batch=batch,
                purpose="2x2 cadence/batch消融；(5,4)复用CORE rho=.8", questions=["Q5", "Q10"])
    for rho in [0.5, 0.8, 1.0]:
        for hold in [4, 8]:
            add("HOLD", "B2", rho, hold=hold, purpose="B1基础上最小逐链hold H4/H8对照，禁止择优只报一种", questions=["Q8"])
    for rho in [0.5, 0.8, 1.0]:
        for c in ["B3", "B4"]:
            add("ROUTER", c, rho, router="CURRENT_STATE_LOAD_AWARE",
                purpose="same scenario/traffic/parameters仅替换common router", questions=["Q9", "Q10"])

    def find(**conditions):
        matches = [r for r in rows if all(r[k] == v for k, v in conditions.items())]
        if len(matches) != 1:
            raise RuntimeError("Not unique anchor: " + repr(conditions))
        return matches[0]["run_id"]

    contrasts = []

    def contrast(kind, left, right, axis, role):
        contrasts.append({"contrast_id": "%s-%02d" % (kind, sum(x["kind"] == kind for x in contrasts) + 1),
                          "kind": kind, "left_run_id": left, "right_run_id": right,
                          "changed_axis": axis, "role": role,
                          "full_J_rule": "both COMPLETE only; otherwise censor/residual/delivery/completion evidence, no truncated-J ranking"})

    for block in ["CORE", "STABLE", "SPARSE", "FACTORIAL", "ROUTER"]:
        b4s = [r for r in rows if r["block"] == block and r["controller"] == "B4-v2"]
        for b4 in b4s:
            keys = ["block", "rho", "decision_cadence_s", "max_batch_replace", "router", "traffic", "topology_regime"]
            b3id = find(controller="B3-v2", **{k: b4[k] for k in keys})
            contrast("PRIMARY_CONTROLLER", b4["run_id"], b3id, "controller", "同动作权限、pool规则与common fast layer的B4-B3")
    for block in ["CORE", "STABLE"]:
        for rho in sorted({r["rho"] for r in rows if r["block"] == block}):
            for left, right in [("B4", "B1"), ("B3", "B1"), ("B1", "B0")]:
                contrast("BASELINE", find(block=block, rho=rho, controller=left + "-v2"),
                         find(block=block, rho=rho, controller=right + "-v2"), "controller", "预注册secondary对照，无global ranking")
    anchor = {c: find(block="CORE", rho=0.8, controller=c + "-v2") for c in ["B0", "B1", "B3", "B4"]}
    for r in rows:
        c = r["controller"]
        if r["block"] == "SPARSE":
            contrast("K_SENSITIVITY", r["run_id"], find(block="CORE", rho=r["rho"], controller=c),
                     "initial_topology_K", "仅初始固定K/绑定改变，保持同安全政策；不据此挑最佳K")
        elif r["block"] == "STABLE":
            contrast("TRAFFIC", r["run_id"], anchor[c[:-3]], "traffic", "same rho/normalizer；不将stable优势外推到迁移")
        elif r["block"] == "FACTORIAL":
            contrast("CADENCE_BATCH", r["run_id"], anchor[c[:-3]], "cadence_and_or_batch", "锚点之外3配置；另报告完整2x2因素效应")
        elif r["block"] == "HOLD":
            contrast("MINIMUM_HOLD", r["run_id"], find(block="CORE", rho=r["rho"], controller="B1-v2"),
                     "minimum_hold", "同一B1基础；H4/H8均保留")
        elif r["block"] == "ROUTER":
            contrast("ROUTER_ROBUSTNESS", r["run_id"], find(block="CORE", rho=r["rho"], controller=c),
                     "common_router", "跨router只作结论敏感性，不混合排名")

    counts = dict(collections.Counter(r["controller"] for r in rows))
    blocks = dict(collections.Counter(r["block"] for r in rows))
    b4epochs = sum(r["runtime_budget"]["maximum_scheduled_epochs"] for r in rows if r["controller"] == "B4-v2")
    other_epochs = sum(r["runtime_budget"]["maximum_scheduled_epochs"] for r in rows if r["controller"] != "B4-v2")
    matrix = draft("f3_v2_october_paper_experiment_matrix")
    matrix.update({"parent_artifact_sha256": parent_hashes, "target_run_count": 42,
                   "controller_counts": counts, "block_counts": blocks,
                   "primary_contrast": "B4-v2_minus_B3-v2; complete pairs only",
                   "new_K_star_selected": False, "K_star": None,
                   "preregistration_state": "DRAFT_ONLY_NOT_AN_EXECUTABLE_FROZEN_MANIFEST",
                   "common_contract": {
                       "scale": 160, "commodities": 16, "OD_manifest": "configs/gate_d0_od_manifest_16.json",
                       "arrival_horizon_s": [0, 240], "drain_limit_s": 600, "decision_at_600": False,
                       "COMPLETE_threshold_bits": 0.01, "D2_early_return_bits": 1.0,
                       "alpha_star_bit_s": 26666666666.666664, "rho_normalization": "existing D0 reference, never recalibrate by K/controller/router",
                       "setup": "unchanged Gate C base hardware and real state-dependent Gate B/C transitions, no setup sweep in this matrix",
                       "physical_inputs": "existing160-star SGP4/WGS72/TEME plus Gate C0-600 windows; preserve natural expiry/censor",
                       "safety_proposal": "STRICT_CONNECTED for both K_STAR and K4; same policy, requires freeze and feasibility verification",
                       "initial_link_age_proposal_s": 0, "current_rate_forecast": "B4 persistence only, no realized future traffic",
                       "late_horizon_proposal": "min(10,600-t); fixed nominal10, boundary clipping only; approval required",
                       "shared_search": "structure-only common pool on same root; no J-based selection/tuning; no across-epoch pool cache",
                       "fairness": "paired controllers may evolve different states; same pool construction contract/budgets, not identical pool after divergent live states",
                       "deterministic": True, "seed_policy": "fixed immutable traces, no new stochastic seeds/replicates",
                       "statistical_scope": "single deterministic trace family; paired descriptive effects, no independent-replicate CI/p-value claim"},
                   "runs": rows, "contrasts": contrasts,
                   "factorial_anchor_reuse": {"cadence_batch": [[2, 1], [2, 4], [5, 1], [5, 4]],
                                               "anchor_5s_batch4": {"B3": anchor["B3"], "B4": anchor["B4"]}},
                   "registered_opening_figure_proposal": {"rho": 0.8, "run_ids": anchor,
                       "series": ["N(t)", "Q(t)", "I(t)", "REPLACE batch/per-link", "Gate B BBM/MBB transitions"],
                       "phase_boundaries_s": [60, 120, 180, 240], "no_post_result_case_replacement": True},
                   "mechanism_and_search_analysis": {
                       "source": "same42 raw evidence plus separate tiny engineering oracle, no additional formal runs",
                       "metrics": ["BBM/MBB by binding and batch, mixed batches", "transition outage vs post-expiry no-route separately",
                                   "focus/third-party backlog", "candidate raw/prune/reject/pool coverage counts",
                                   "beam omissions by cardinality on tiny exact oracle", "controller wall/RSS/workers/evaluation counts"],
                       "limits": "Main-scale missing optimum cannot be inferred from capped pool; report budget/certificates, tiny recall does not prove160-star optimality",
                       "no_causal_overclaim": "Runtime/mechanism correlations are not new paired setup-ablation evidence; router/cadence/batch effects reported separately"},
                   "execution_stop_policy": "scientific/execution invariant failure: persist all evidence then STOP; do not silently retry/drop. CENSORED is retained valid scientific outcome",
                   "finalization_before_formal_run": ["human freeze all science/search parameters", "result-blind K0/K1 select and bind K* artifacts",
                       "all v2 gates PASS and scientific source hashes recorded", "fill measured per-run costs/limits",
                       "emit new frozen executable manifest with all42 IDs and this draft parent hash",
                       "obtain separate human performance authorization"]})

    mem = psutil.virtual_memory()
    runtime = draft("f3_v2_october_runtime_budget_plan")
    runtime.update({"hardware_read_only_snapshot": {
        "captured_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "CPU_model": "Intel Core Ultra 9 275HX (prior read-only CIM inventory)",
        "physical_cores": psutil.cpu_count(logical=False), "logical_cpus": psutil.cpu_count(logical=True),
        "process_affinity_cpu_count": len(psutil.Process().cpu_affinity()),
        "memory_total_GiB": mem.total / 2**30, "memory_available_GiB": mem.available / 2**30,
        "python_executable": sys.executable, "python_version": platform.python_version(),
        "sampling": "one read-only inventory, no continuous monitor or active run profiling"},
        "new_v2_cost_status": "NOT_MEASURED; no matching/builder/batch-controller benchmark executed by this plan",
        "historical_timing_use": "old single-REPLACE/8-worker timings are context only, never certify new K/batch-v2 cost or equivalence",
        "resource_proposals": {"status": "REQUIRES_HUMAN_FREEZE_AND_MEASUREMENT",
            "production_workers": 8, "B4_concurrent_episodes": 1, "default_other_episode_concurrency": 1,
            "available_machine_hours_per_day": 20, "formal_days": 6, "reserve_fraction": 0.2,
            "allocated_machine_hours": 120, "net_compute_hours_after_reserve": 96,
            "B4_planning_allocation_hours": 72, "other_controller_allocation_hours": 24,
            "RAM_fraction_of_launch_available_max": 0.75,
            "memory_admission_formula": "parent peak RSS + 8*worker peak RSS + shared/transport/pool overhead <=0.75*available RAM measured at launch",
            "thread_policy": "audit BLAS/OpenMP oversubscription; worker single-thread environment is proposal only, must record/validate exact equivalence before freeze",
            "parallel_admission": "24 reported cores do not authorize 3 B4 episodes; RSS, heterogeneous cores, contention and liveness measured first",
            "wall_timeout_s": None, "timeout_semantics": "operational failure with complete persistence; never CENSORED, never select incomplete/first-finished branch"},
        "shared_search_budget_proposal": {"status": "REQUIRES_HUMAN_FREEZE; COMPUTE/STRUCTURAL_BASIS_ONLY",
            "raw_BBM_cap": 32, "raw_MBB_cap": 32, "raw_total_cap": 64,
            "single_proposal_cap": 16, "single_strata_slots": {"BBM": 8, "MBB": 8},
            "beam_width": 4, "max_non_hold_batch_candidates": 32,
            "structural_expansion_cap": 184, "joint_validation_cap": 184,
            "maximum_rollout_evaluations_including_HOLD": 33,
            "derivation": "P=16,W=4,m=4: P+W*(15+14+13)=184 expansion upper bound; retained legal outputs<=P+3W=28<=M32; 33 rollout cap>=1+M. Physical raw screening64 separately counted. No score to enlarge budgets.",
            "batch1_rule": "same capped16 singleton universe, no joint expansion; HOLD+up to16 branches; quotas unchanged",
            "structural_acceptance": "fixture suite includes certified legal size2/3/4 and BBM/MBB/mixed actions, reports pool recall/omissions by size; no unearned main-scale optimality guarantee",
            "diagnostic_budget_adjustment": "only result-blind resource/structural evidence before final freeze; human-approved revision required; never final-J tuning"},
        "measurement_plan": [
            {"id": "RT_K", "due": "2026-10-11", "scope": "Gate K0 exact matching/topology builder cost-only after structural contract authorization",
             "fixture_rule": "predeclare t=0/270/570 and candidateK=24/48/80 for preliminary cost; full K0 still follows approved original candidate list and20 snapshots",
             "measure": ["wall time", "candidate graph size", "solver certificate", "memory", "builder phases"],
             "cost_s": None, "dependency": "human K0 authorization + solver/builder availability", "if_unavailable": "NOT_MEASURED + critical-path blocker byOct11, no fabricated cost"},
            {"id": "RT_BATCH", "due": "2026-10-16", "scope": "newK source and full-batch safety validation",
             "fixture_rule": "approved K* plus K4; predeclared20 structural snapshots; no controller performance",
             "measure": ["source wall", "singleton count", "resource-independent pool", "full batch validation count/wall", "available batch-size distribution"],
             "cost_s": None, "dependency": "shared validator PASS and approved K0/K1"},
            {"id": "RT_B4", "due": "2026-10-22", "scope": "one real joint B4 rollout and serial/8-worker epoch/short prefix engineering equivalence",
             "fixture_rule": "register current-state cost fixtures at0/120/240/480/595 andrho .5/.8/1 before timing; synthetic timeline fixtures if late live states not yet available must be labelled nonrepresentative",
             "measure": ["branch wall by cardinality", "cold/warm pool wall", "serialization/clone", "serial/8-worker exact and speed", "parent/worker peak RSS", "epoch components"],
             "cost_s": None, "dependency": "new B4-v2 implementation, K* and acceptance fixtures",
             "information_boundary": "do not compare controller J/delay/delivery for selecting fixtures or budgets; exact equality checks allowed"},
            {"id": "RT_EPISODE", "due": "2026-10-23", "scope": "conservative full episode and42-run extrapolation",
             "measure": ["phase/epoch conservative costs", "service between epochs", "IO/figure/seal overhead", "available machine hours"],
             "estimated_total_s": None, "dependency": "RT_K/RT_BATCH/RT_B4 measured", "status": "PENDING_COST_MEASUREMENTS"}],
        "matrix_cost_model": {"B4_runs": counts["B4-v2"], "other_runs": 42-counts["B4-v2"],
            "B4_max_decision_epochs": b4epochs, "other_max_decision_epochs": other_epochs,
            "maximum_epoch_counts": "B4:2*300+11*120=1920; others:2*300+27*120=3840. Early completion never assumed for conservative planning.",
            "upper_bound_B4_epoch_mean_s_if_zero_overhead": 72*3600/b4epochs,
            "upper_bound_other_epoch_mean_s_if_zero_overhead": 24*3600/other_epochs,
            "interpretation": "135s/B4 epoch and22.5s/other epoch are planning ceilings, not measured predictions; subtract fixed/service/IO overhead before admission",
            "formula": "sum_runs[frozen measured fixed costs + max_epoch_count*conservative observed epoch cost + extra service/IO costs]",
            "estimated_matrix_wall_s": None, "ready_to_launch": False},
        "early_risk_rules": [
            "Oct11: no K0/K1 approval, missing solver cost or engineering capacity gap => immediate blocker report",
            "Oct16: K*/batch validator not PASS or structure lacks desired independent batches => immediate redesign request, no cherry-picked K",
            "Oct20-22: measured total exceeds available96h net budget or RSS admission fails => notify immediately, not last week",
            "Oct23: any exact/regression/preflight fail => prohibit Oct24 start and publish projected slip",
            "formal invariant failure => preserve failure and stop; dates never relax semantics/tolerance"],
        "prohibited_measurement_use": ["rank controllers by J", "select better traffic/K/rho", "tune beam to achieved J", "replace inconvenient fixtures", "run registered experiment without authorization"]})

    approval = [
        {"id": "HF_SCIENCE", "decision": "批准现有v2 action/BBM-MBB/资源独立/原子执行/全时间线STRICT安全，5s主周期、batch4、B1 whole-graph、B3 min_eta、B4 H10 persistence、末端min(10,600-t)", "status": "REQUIRES_HUMAN_FREEZE"},
        {"id": "HF_K", "decision": "批准K0-v1.1 20snapshot/18-of20/截断寿命及K0-v1.2联合诊断；K*依结构规则选定，K1初态/age0；无合格K则STOP，不按J挑K", "status": "REQUIRES_HUMAN_FREEZE"},
        {"id": "HF_SEARCH", "decision": "一次审批共享结构beam建议W4/M32/184expansion/184joint validation/33rollouts，raw32+32/64与singleton16/8+8；允许仅结构/成本证据提出冻结前修订，不能自动调整", "status": "REQUIRES_HUMAN_FREEZE"},
        {"id": "HF_MATRIX", "decision": "批准42项六块矩阵、全部固定ID与次序、三负载、stable模板、K4同安全政策、2x2消融、B2逐链LINK_UP H4/H8 threshold0、两router；无额外seed/grid", "status": "REQUIRES_HUMAN_FREEZE"},
        {"id": "HF_RESOURCE", "decision": "确认Oct24-29机器可用时间；建议20h/day、一B4 episode/8workers、RAM上限；授权成本-only测量范围并在Oct23前填齐实测超时/预算", "status": "REQUIRES_HUMAN_RESOURCE_CONFIRMATION"},
        {"id": "HF_BUILD", "decision": "批准分阶段实施K0/K1、batch adapter/B1-B4/tiny oracle/evidence writer/preflight；复用原模拟器，无额外算法/星座/runtime重构", "status": "IMPLEMENTATION_NOT_AUTHORIZED_BY_PLAN"},
        {"id": "HF_RUN", "decision": "仅在前述冻结、新版本验收、完整预算/manifest/hash齐全后，另行人工授权全部42项正式执行；本次计划或合同审批均不自动授权运行", "status": "SEPARATE_FORMAL_RUN_AUTHORIZATION_REQUIRED"},
    ]
    deliverables = draft("f3_v2_october_deliverables")
    definitions = [
        ("D01", "F3-v2完整算法设计、代码和冻结配置", "2026-10-23", "signed contracts/schema/code hashes; no pending executable parameters", "DESIGN_DRAFT_ONLY"),
        ("D02", "共享batch executor安全验收", "2026-10-16", "atomic rollback, independent resources, simultaneous mixed transitions, full timeline safety, conservation PASS", "NOT_IMPLEMENTED"),
        ("D03", "K0/K1结构审计与初始拓扑证据", "2026-10-16", "result-blind20snapshot audit, exact/bound certificates, K* rule, parent/GateC hashes, K1 bindings/ages/connectivity", "K_STAR_NOT_SELECTED"),
        ("D04", "B1/B2/B3/B4-v2实现与验收", "2026-10-23", "same pool/info boundary/score exact/tie/hold semantics and deterministic fixtures PASS", "NOT_IMPLEMENTED"),
        ("D05", "B4 serial/8-worker精确等价", "2026-10-23", "new joint branches and multi-epoch four checkpoints/state-chain exact; no orphan; old PASS not substituted", "NOT_EXECUTED_FOR_V2"),
        ("D06", "全部预注册非MARL正式实验", "2026-10-29", "42/42 registered IDs with valid COMPLETE/CENSORED; zero unresolved execution failures; all raw evidence retained", "NOT_AUTHORIZED"),
        ("D07", "全部run状态和统计", "2026-10-31", "ledger/metrics/evidence agree; censored residual/delivery and no truncated-J rank; failures explicitly retained", "NOT_AVAILABLE"),
        ("D08", "核心B4-v2 vs B3-v2比较表", "2026-10-31", "three-load same-config paired contrasts; full J only complete pairs; negative/tied cases preserved", "NOT_AVAILABLE"),
        ("D09", "控制周期、batch上限和鲁棒性", "2026-10-31", "complete2x2 anchor reuse; K/stable/B2/router registered contrasts; permissions vs forecast effects separated", "NOT_AVAILABLE"),
        ("D10", "主要论文图表/caption/可复现manifest", "2026-10-31", "opening rho.8 immutable case; main contrasts/regime/ablation/runtime/mechanism plots; scripts/source hashes/seal", "NOT_AVAILABLE"),
        ("D11", "论文结论与局限性", "2026-10-31", "positive/negative/censor all explained; deterministic trace coverage, capped search, no proven large-scale optimum or MARL claim", "NOT_AVAILABLE"),
    ]
    deliverables.update({"milestones": milestones,
        "items": [{"id": i, "name": n, "due": d, "acceptance": a, "current_status": s,
                   "evidence_paths": [], "accepted": False} for i,n,d,a,s in definitions],
        "consolidated_approval_checklist": approval,
        "immediate_independent_preparation": ["schema/type/CLI/evidence layout and test-fixture specification without freezing pending science",
             "read-only compatibility inventory and artifact integrity hashes", "parameterized plotting/ledger validation skeletons", "record machine availability and result-blind measurement protocols"],
        "not_executed_by_this_task": ["implementation", "benchmark", "K selection", "controller evaluation", "registered experiment"],
        "blocked_until_scientific_freeze": ["K0/K1 executable selection", "batch safety/score semantics implementation", "beam/pruning/count-budget choices", "B2 timer semantics", "final registered manifest"],
        "final_acceptance": "eachD01-D11 accepted separately; engineering PASS never implies scientific superiority or experiment completion",
        "completion_deadline_not_guaranteed": True,
        "submission_target": "2026-12 mid-to-late; November writing/interpretation/review, not postponed first main experiments"})

    # Internal consistency checks only. No scientific tests or kernels are invoked.
    checks = {
        "exactly_42_unique_registered_draft_ids": len(rows) == 42 and len({r["run_id"] for r in rows}) == 42,
        "blocks_minimal_and_complete": blocks == {"CORE":12,"STABLE":4,"SPARSE":8,"FACTORIAL":6,"HOLD":6,"ROUTER":6},
        "controller_counts": counts == {"B3-v2":13,"B4-v2":13,"B0-v2":5,"B1-v2":5,"B2-v2":6},
        "no_duplicate_physical_run_configuration": len({tuple(r[k] for k in ["controller","rho","topology_regime","traffic","router","decision_cadence_s","max_batch_replace","minimum_hold_s"]) for r in rows}) == 42,
        "all_ten_research_questions_covered": {q for r in rows for q in r["research_question_ids"]} == {"Q%d" % i for i in range(1,11)},
        "two_by_two_uses_exact_core_anchor": all(find(block="CORE",rho=.8,controller=c+"-v2") == matrix["factorial_anchor_reuse"]["anchor_5s_batch4"][c] for c in ["B3","B4"]),
        "chronological_execution_order_complete": [r["execution_order"] for r in rows] == list(range(1,43)),
        "all_costs_explicitly_unmeasured": all(r["runtime_budget"]["estimated_wall_clock_s"] is None for r in rows),
        "all_rows_not_authorized": all(r["status"] == "PLANNED_NOT_AUTHORIZED" for r in rows),
        "maximum_epoch_budget": b4epochs == 1920 and other_epochs == 3840,
        "beam_count_consistency": 16+4*(15+14+13) == 184 and 16+3*4 <=32 and 33>=1+32,
        "eleven_unaccepted_deliverables": len(deliverables["items"]) == 11 and not any(x["accepted"] for x in deliverables["items"]),
        "all_drafts_not_frozen": all(x["status"] == STATUS and not x["formal_performance_authorized"] for x in [matrix,runtime,deliverables]),
        "new_K_not_falsely_selected": matrix["K_star"] is None and not matrix["new_K_star_selected"],
        "input_paths_exist": all((ROOT/p).is_file() for p in parents),
        "no_600_decision": all(r["runtime_budget"]["maximum_scheduled_epochs"] == 600//r["decision_cadence_s"] for r in rows),
    }
    index = {r["run_id"]: r for r in rows}
    checks["primary_pairs_match_all_noncontroller_config"] = all(
        all(index[x["left_run_id"]][k] == index[x["right_run_id"]][k] for k in ["scale","rho","topology_regime","traffic","router","decision_cadence_s","max_batch_replace"])
        for x in contrasts if x["kind"] == "PRIMARY_CONTROLLER")
    if not all(checks.values()):
        raise RuntimeError("Plan consistency failed: " + repr(checks))

    for obj, rel in zip([matrix,runtime,deliverables], OUTPUTS[1:]):
        obj["draft_canonical_sha256"] = canonical(obj)
        write_json(ROOT / rel, obj)

    table = "\n".join("|%s|%s|%s|%s|" % (m["id"],m.get("start",m["due"])+( "—"+m["due"] if "start" in m else ""),m["work"],m["acceptance"]) for m in milestones)
    approval_md = "\n\n".join("%d. **%s**：%s。状态：`%s`。" % (i,a["id"],a["decision"],a["status"]) for i,a in enumerate(approval,1))
    end_low = dt.date(2026,10,12)+dt.timedelta(days=17)
    end_high = dt.date(2026,10,12)+dt.timedelta(days=28)
    doc = """# F3-v2：10月31日非MARL论文实验证据包关键路径

状态：**DRAFT_NOT_FROZEN**。规划日期2026-10-08（Asia/Shanghai）。本轮仅审计和生成计划；没有运行matching、builder、controller、benchmark或注册实验，没有冻结科学参数。

## 目标与旧计划的关系

2026-10-31前争取完成全部获批、预注册的非MARL实验和可审查证据包；12月中下旬投稿。11月用于解释、论文写作和审阅，不能作为第一轮主实验的默认启动月。此次计划作为新的日程覆盖层，取代旧草案“10月工程、11月首轮实验”的排期，**不覆盖或修改旧文档、合同、FAIL attempt、K4证据或runtime overlay**。算法语义仍以先前v2草案为审批输入，并非因日期要求自动冻结。

## 当前可行性与必须提前报出的风险

当前v2只有设计草案；K*未选择，K1未构造，共享batch executor和B4-v2尚未实现，新版本运行成本未测量。旧单REPLACE的8-worker通过不能证明joint-v2正确或更快。

前次计划估计核心工程与结构前提约18–29人日，不确定且不含运行延期。若10月11日批准、10月12日开工，10月23日封闭验收仅有12个日历日；单人顺序实施的已有估计超出窗口。**当前总体风险HIGH，10月31日是目标而非保证。** 若顺序工作估计不下降，工程完成约%s至%s，另需6天运行+2天封存，证据约%s至%s，比目标晚约6–17天。这是容量情景，不能当作实测工期。

压缩方式限于复用已有Gate B/C/D执行器、已验收克隆/序列化/8worker基础，以及交错准备K0结构审计、测试fixtures、evidence writer和绘图脚本；不另造模拟器，不省安全检查。K0成本初估可在合同批准后开始；K1联合可行证据依赖新validator，不能假装独立完成。没有安排或创建任何子agent/额外人员；能否提供并行开发支持须人工确认。

10月11日必须明确审批与人力缺口；10月16日检查K*/executor关键前提；10月20–22日根据真实成本更新全矩阵预算；10月23日未通过不得启动正式实验。每个风险报告包含阻塞对象、依赖、预计延期范围和需审批的减项方案。不得等最后一周再报告。

## 唯一关键路径与里程碑

合同/资源审批 → batch物理与时间线validator → K0/K1结构证据+共享pool → B1/B3/B4-v2 → 新serial/8worker+tiny oracle+完整回归 → 实测预算/最终manifest/preflight → 单独正式运行授权 → 全矩阵 → 数据/图表/封存。

|节点|日期|工作|验收|
|---|---|---|---|
%s

Oct11的成本包区分“已有实测、结构推算、NOT_MEASURED”。新B4尚未实现，完整episode预测只能是初估；Oct20–22必须替换为新版本实测并在Oct23最终预算准入。缺项应标blocker，不能填0秒或借用旧版数字。

## 最小完整实验矩阵：42项deterministic runs

|块|配置/研究作用|新增run数|
|---|---|---:|
|CORE|K*、热点迁移、primary router、5s/batch4；rho=.5/.8/1 × B0/B1/B3/B4|12|
|STABLE|K*、稳定业务、rho=.8、primary、5s/batch4；四控制器|4|
|SPARSE|K4、热点、primary；B3/B4 × 三负载；rho=.8另加B0/B1|8|
|FACTORIAL|K*、热点、rho=.8；B3/B4 × (2s,1)/(2s,4)/(5s,1)，(5s,4)复用CORE|6|
|HOLD|K*、热点、primary、5s/batch4；B2-H4/H8 × 三负载|6|
|ROUTER|K*、热点、5s/batch4；load-aware B3/B4 × 三负载，primary复用CORE|6|
|总计|B4=13，B3=13，B1=5，B0=5，B2=6|42|

每项固定ID、草案执行次序、配置、科学作用、对照引用和预算字段在JSON中。K*与物理artifact/hash明确待K0/K1，不以未决符号冒充可运行manifest。K4绑定历史z_moderate_v1的4条链，仅作VERY_SPARSE_HISTORICAL_REFERENCE；不能混用三链Z_SPARSE。K*和K4拟用同一STRICT_CONNECTED安全政策，初始可行性必须验收。固定K指固定初始/名义预算，不人为阻止自然链路到期，不引入ADD/DROP自动补链。

主对比B4-B3动作权限、cadence、候选构造/预算和common router相同，避免把batch4对batch1的权限优势称为预测收益。共享pool是“同一root的相同构造”，两控制器状态分歧后不要求实际pool相同。B1决策忽略setup后果但执行真实setup；B2只增加逐链LINK_UP时钟H4/H8，threshold0，不事后选最优hold。

业务沿用16 OD、原immutable stable/migration模板、D0参考alpha*=26.6666666667Gbps与rho，不按K/全网容量重归一化。正式只做160星；无新240/720/MARL实验。2s/5s是controller cadence，物理、service、arrival与LINK_UP/DOWN事件仍在真实时间发生。主H=10s，截止600的截短为边界规则，须审批而非引入自适应预测时域。

## 计算预算：先测成本，不能据性能挑参数

机器只读库存记录在runtime JSON：CPU24 reported physical/logical cores；RAM约31.4GiB，当前空闲量是瞬时快照。建议先按**一个B4 episode、persistent8workers+parent**规划；24核不等于可无风险并跑3组。启动前重新测可用RAM，parent+8worker峰值+传输开销不得超过可用RAM的75%%草案上限。

建议共享结构beam W4、非HOLD池M32、单候选P16（8BBM+8MBB）、raw32/32/64；展开上界16+4×(15+14+13)=184，joint-validation预算184，HOLD+至多32批为33rollout上限。保留按size的覆盖，实际最多16+3×4=28 retained batches。以上是**待审批计算与结构预算建议**，并未冻结、实现或通过新物理审计；若新的具体算法不能满足此计数模型须在正式实验前明确修订。batch1仅16 singleton，不借消融增加搜索优势。

候选遗漏在tiny fixture（6–10node，single<=8）用精确枚举报告按size的legal-set recall/遗漏及代理/rollout best-in-pool差异；160星只报告预算与结构证据，不能声称知道全局遗漏最优解。tiny oracle可检查客观函数，但不能反过来据最终性能调主预算。主scale禁止全局精确联合动作搜索。

成本测量包括K0 matching/builder、newK source、整batch safety、B4分支/整epoch、serial/8worker cold/warm wall与RSS、代表时刻pool size，以及网络推进/evidence I/O。不比较控制器性能来挑测量状态。尚未实测的项全部null/NOT_MEASURED。

Oct24–29有144日历小时；建议待确认机器每天20h，6天120h，留20%%故障/验收余量，净96h计算。暂分B4 72h、其他24h。最大调度：B4为2×300+11×120=1920epoch；其他3840epoch。忽略所有固定开销时分别要求平均不高于135s/epoch、22.5s/epoch；真实准入必须扣除推进、冷启动、传输和I/O。**这是工期上限，不是速度预测。当前没有足够数据宣称42项能在6天跑完。**

若Oct20–22保守预测超96h/RAM不足，应当立即报告并要求资源/日程/预注册范围调整；不能调tolerance、提前截断rollout或按先完成分支决策。每run实测预算和操作超时未填齐之前preflight不READY。超时是执行失败，持久化后STOP，不是科学CENSORED。

## 科学验收、输出与解释

arrival0–240s，真实drain最多600s，600不新decision；D2 1bit内部返回不等于F3 .01bit COMPLETE。无clamp/drop/virtual drain。每run检查traffic identity、work conservation、queue非负、capacity、batch资源/原子性、checkpoint隔离、candidate budget、decision边界和evidence一致性。失败先完整持久化再停止，不隐藏或擅自重跑。CENSORED为合法结果，保留residual/delivery，不能用截断J排名。

主目标仍J=integral unfinished work，无人为switch penalty。仅双方COMPLETE计算B4-B3绝对/相对DeltaJ，secondary contrasts预先固定，无global ranking。42项是deterministic场景比较而非42独立随机样本，不生成虚假显著性/置信区间。协议验收与科学结论独立：B4不优于B3、曲线重合或censor仍完整报告。

主要图：固定rho=.8 opening N/Q/I+batch和terminal transition markers+60/120/180/240边界；三负载主对比表/图；完整2×2cadence/batch；K/stable/router/B2敏感性；cost分解/搜索覆盖；BBM/MBB、transition outage与post-expiry no-route拆分。图case不因好看更换，censored标注且不画成完整J优劣。

11项交付和逐项acceptance详见deliverables JSON。设计/代码/配置、batch安全、K0/K1、B1-B4、serial8、42项结果、状态统计、主对比、消融鲁棒性、图表/caption/复现和局限清单均必须单独审核。旧engineering PASS或文件存在不等于新实验完成。

## 可立即准备与必须等待审批

立即可独立准备：参数化schema/evidence目录及ledger校验设计、fixture清单、绘图数据接口、已有接口只读盘点、资源可用时间与成本测量协议。此轮**没有实施**这些工程模块。科学算法、可运行K0/K1、联合safety、评分、beam排序/预算、hold时钟与正式manifest必须在一次性合同审批后实施；新正式实验需另一次人工运行授权。

## 一次性审批清单

%s

审批包同时包含科学合同、K0/K1策略、搜索预算、矩阵、资源窗口和后续实施范围。需要测量后才能确定的运行成本/超时集中补齐，不逐个小参数打断。合同冻结与正式运行授权是不同关口，禁止将此次计划审批解释为自动启动。

## 超时风险下的非核心缩减备选（仅提案）

优先保全CORE12和B4-B3公平对比、完整2×2消融与全部正确性验收。若成本资源缺口确实无法解决，可在任何性能运行前，集中申请将B2六项改为rho=.8两项、router六项改为rho=.8两项、sparse八项改为rho=.8四项、stable四项改为B3/B4两项；合计最多减14项但减少结论覆盖。每一减项须人工批准新的manifest、保存42项原草案和明确延期/未执行状态；**本计划没有采用这些减项，也不授权删掉已注册run**。正式运行开始后不能因J不佳或censor择项缩减。

完成本计划后STOP。下一步是人工集中审阅/冻结与工程实施授权；不自动执行K0/K1、controller或P1/P2/RL。
""" % (end_low.isoformat(),end_high.isoformat(),(end_low+dt.timedelta(days=8)).isoformat(),(end_high+dt.timedelta(days=8)).isoformat(),table,approval_md)
    (ROOT / OUTPUTS[0]).write_text(doc, encoding="utf-8")

    changed = []
    after = {}
    for rel, old_hash in before.items():
        p = ROOT / rel
        actual = sha(p) if p.is_file() else None
        after[rel] = actual
        if actual != old_hash:
            changed.append({"path":rel,"before":old_hash,"after":actual})
    protected = {"status":"PASS" if not changed else "FAIL", "protected_file_count":len(before),
                 "all_historical_files_unchanged":not changed,"changes":changed,"files_after":after}
    write_json(ATTEMPT / "historical_integrity_report.json", protected)
    checks["all_historical_hashes_unchanged"] = not changed
    report = {"status":"PLANNING_ARTIFACTS_READY_FOR_HUMAN_REVIEW" if all(checks.values()) else "FAIL_STOP",
              "draft_not_frozen":True, "checks":checks,"run_count":42,"milestone_risk":"HIGH",
              "new_v2_cost_measured":False,"formal_run_started":False,"K_star_selected":False,
              "implementation_started_by_this_task":False,"previous_plans_preserved":True,
              "scope":"static planning consistency and read-only historical integrity only; no scientific regression/benchmark executed"}
    write_json(ATTEMPT / "static_plan_validation.json", report)
    write_json(ATTEMPT / "parent_inputs.json", parent_hashes)
    seals = {r:sha(ROOT/r) for r in OUTPUTS+["tools/build_f3_v2_october_plan.py"]}
    write_json(ATTEMPT / "artifact_hashes.json", {"sha256":seals,
                "canonical_json_sha256": {r:json.loads((ROOT/r).read_text(encoding="utf-8"))["draft_canonical_sha256"] for r in OUTPUTS[1:]}})
    write_json(ATTEMPT / "planning_report.json", {**report,"outputs":OUTPUTS,"evidence_directory":str(ATTEMPT),
               "schedule_supersedes_only":parents[7],"old_schedule":prior_plan["schedule"],"new_target":"2026-10-31"})
    if changed:
        raise RuntimeError("Historical files changed; STOP")
    print(json.dumps({"status":report["status"],"draft_runs":len(rows),"block_counts":blocks,
                      "static_checks_passed":sum(checks.values()),"historical_files_unchanged":len(before),
                      "runtime_cost_status":"NOT_MEASURED","output_dir":str(ATTEMPT)},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
