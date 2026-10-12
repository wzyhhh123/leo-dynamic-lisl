"""Planning revision only. Never imports a simulator or runs an experiment."""
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["docs/F3_V2_OCTOBER_CRITICAL_PATH.md", "configs/F3_V2_PAPER_EXPERIMENT_MATRIX_DRAFT.json",
         "configs/F3_V2_RUNTIME_BUDGET_PLAN.json", "configs/F3_V2_OCTOBER_DELIVERABLES.json"]


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def canonical(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    attempt = ROOT / ("outputs/f3_v2_october_plan_revision_" + stamp)
    attempt.mkdir(parents=True, exist_ok=False)
    prior = attempt / "prior_plan_bytes"
    prior.mkdir()
    old_hashes = {}
    for rel in FILES:
        old_hashes[rel] = sha(ROOT / rel)
        (prior / Path(rel).name).write_bytes((ROOT / rel).read_bytes())
    # Exact protection of all existing project files except the four explicitly
    # requested mutable planning artifacts. Historical evidence is included.
    paths = [p for p in ROOT.rglob("*") if p.is_file() and attempt not in p.parents
             and not {"__pycache__", ".git", ".pytest_cache"}.intersection(p.relative_to(ROOT).parts)
             and p.suffix != ".pyc" and p.relative_to(ROOT).as_posix() not in FILES]
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    write(attempt / "protected_hashes_before.json", before)
    latest = "outputs/f3_v2_engineering_check_20261008T133202_075331Z"
    earlier = "outputs/f3_v2_engineering_check_20261008T130350_414494Z"
    evidence = read(latest + "/report.json")
    code_seal = read(latest + "/input_code_hashes.json")["code"]
    differences = [rel for rel, digest in code_seal.items() if sha(ROOT / rel) != digest]
    newly_added = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "src/dynamic_lisl/f3_v2").glob("*.py")
                         if p.relative_to(ROOT).as_posix() not in code_seal)
    snapshot = {"scope": "read-only inventory; historical tests not rerun", "source_report": latest + "/report.json",
                "source_report_sha256": sha(ROOT / latest / "report.json"),
                "historical_focused_tests": evidence["test_reports"][0]["tests"],
                "historical_focused_returncode": evidence["test_reports"][0]["returncode"],
                "historical_synthetic_batch_gate": evidence["V2_A_B_C_synthetic_engineering"],
                "current_code_differs_from_test_seal": differences, "new_code_not_in_test_seal": newly_added,
                "current_full_stack_acceptance": "NOT_ESTABLISHED_BY_THIS_PLANNING_TASK",
                "historical_full_regression_report": earlier + "/report.json",
                "historical_full_regression_tests": read(earlier + "/report.json")["test_reports"][1]["tests"],
                "natural_160_star_v2_acceptance": "PENDING", "K_star_selected": False,
                "B4_v2_engineering_PASS": False, "formal_preflight_READY": False}
    matrix, budget, deliverables = [read(rel) for rel in FILES[1:]]
    for rel, item in zip(FILES[1:], [matrix, budget, deliverables]):
        item.pop("draft_canonical_sha256", None)
        item.update({"plan_revision": "OCTOBER_COMPLETION_PLAN_REVIEW_2", "revision_utc": stamp,
                     "prior_plan_sha256": old_hashes[rel], "prior_plan_preserved_at": str(prior.relative_to(ROOT)).replace("\\", "/"),
                     "current_engineering_snapshot": snapshot, "status": "DRAFT_NOT_FROZEN", "frozen": False,
                     "formal_performance_authorized": False, "implementation_authorized_by_this_plan": False})
    budget["cost_evidence_policy"] = {
        "synthetic_test_wall_is_not_natural_epoch_cost": True,
        "prior_5_74x_or_6_06x_not_v2_batch_cost": True,
        "measured_natural_batch_cost_s": None,
        "forecast_source": "predeclared states, structural counts and measured component wall/RSS only",
        "estimate_range": "record conservative lower/upper scenario; no early drain assumed; no extrapolation from one cheap epoch alone",
        "first_cost_gate": "2026-10-11; missing measurement reported as blocker, not zero",
        "final_admission": "by2026-10-23: sum per-run conservative upper estimates plus operational reserve <= confirmed available hours",
        "formal_budget_timeout": "must be approved after measurement; timeout is execution failure, not scientific censor"}
    budget["critical_path_blockers"] = [
        {"id": "CP_K", "due": "2026-10-11", "status": "OPEN",
         "reason": "K0/K1 contract not frozen and exact bounded reference builder has no main-scale cost/certificate",
         "response": "measure result-blind cost after authorization; UNKNOWN is not certified optimum nor permission to select K*"},
        {"id": "CP_NATURAL", "due": "2026-10-23", "status": "OPEN",
         "reason": "synthetic serial/8-worker evidence does not certify approved K* /160-star joint stack",
         "response": "new natural multi-epoch state-chain exact gate plus current full regression"},
        {"id": "CP_COST", "due": "2026-10-22", "status": "OPEN",
         "reason": "new K, joint pool and complete42-run wall/RSS costs unmeasured",
         "response": "report budget gap and forecast date immediately; keep all correctness requirements"}]
    statuses = {"D01": "PARAMETERIZED_CODE_PRESENT_CONTRACT_NOT_FROZEN",
                "D02": "HISTORICAL_SYNTHETIC_PASS_CURRENT_FULL_ACCEPTANCE_PENDING",
                "D03": "TINY_SOLVER_K1_INFRASTRUCTURE_PRESENT_K_STAR_NOT_SELECTED",
                "D04": "CODE_PRESENT_CURRENT_SCIENTIFIC_ACCEPTANCE_PENDING",
                "D05": "SYNTHETIC_MULTI_EPOCH_EVIDENCE_NATURAL_K_STAR_GATE_PENDING"}
    for item in deliverables["items"]:
        if item["id"] in statuses:
            item["current_status"] = statuses[item["id"]]
            item["evidence_paths"] = [latest + "/report.json"]
            item["evidence_limit"] = "historical engineering only; does not accept this paper deliverable"
    deliverables["immediate_independent_preparation"] += [
        "audit existing parameterized v2 modules and test-seal freshness without changing science",
        "prepare result-blind timing fixtures, evidence schema and figure/caption specifications",
        "plan focused coverage for evidence/preflight and current-source regression; execute only under engineering authorization"]
    deliverables["blocked_until_scientific_freeze"] = [
        "formal K0 thresholds/K* selection and K1 research initial state",
        "production adoption of batch safety, scoring and forecast contract",
        "beam/pruning budgets, B2 clock/hold grid and initialization convention",
        "final executable registered manifest and measured runtime limits"]
    for item in deliverables["consolidated_approval_checklist"]:
        if item["id"] == "HF_BUILD":
            item["decision"] = "审批剩余实施/验收范围；已有参数化工程代码不等于科学冻结或正式上线，复用原执行器且不扩展算法"
    matrix["execution_policy"] = {
        "core_priority": "CORE12 first, original proposed order retained; complete matched B4/B3 contrasts first",
        "registered_runs_may_be_removed_without_approval": False,
        "pre_run_change_policy": "only human-approved new manifest before any performance result; preserve this42-run draft",
        "post_result_selection": "FORBIDDEN", "global_controller_ranking": "FORBIDDEN"}
    doc = (ROOT / FILES[0]).read_text(encoding="utf-8")
    doc = doc.replace("当前v2只有设计草案；K*未选择，K1未构造，共享batch executor和B4-v2尚未实现，新版本运行成本未测量。",
                      "当前v2科学合同仍为草案；已有隔离的参数化batch executor、结构求解、候选池、B1/B2/B3和joint B4工程代码。K*未选择、正式K1初态未构造，160星新版本科学验收和运行成本尚未完成。")
    doc = doc.replace("以上是**待审批计算与结构预算建议**，并未冻结、实现或通过新物理审计；",
                      "以上是**待审批计算与结构预算建议**；参数化实现已存在，但尚未冻结或通过正式160星物理/成本审计；")
    doc = doc.replace("科学算法、可运行K0/K1、联合safety、评分、beam排序/预算、hold时钟与正式manifest必须在一次性合同审批后实施；",
                      "现有参数化工程实现应审计后复用；K*选择、正式K1初态、production联合safety/评分/beam/hold语义和正式manifest必须经过集中科学审批与验收后采用；")
    doc = doc.replace("下一步是人工集中审阅/冻结与工程实施授权；", "下一步是人工集中审阅/冻结与剩余工程验收范围确认；")
    doc += """

## 本轮只读进度复核与关键路径修订

历史最新短验收记录为53项测试通过、synthetic batch A/B/C通过；更早记录有363项全仓库回归通过。二者均不是当前全部源码的重新验收，也不是160星K*主场景的科学上线证明。源文件与测试封存hash的差异、新增未覆盖文件见本轮current_engineering_snapshot。已有代码可以减少重复搭建工作；不能从文件存在推定交付完成，也不把旧版8-worker速度当作joint-v2预算。

当前最早阻塞是K0/K1：exact matching只是terminal-degree容量界，不能代替满足无并行卫星对及lexicographic规则的Z_K构造。现有bounded exact reference builder到预算会返回UNKNOWN；主规模可解性尚未测得，UNKNOWN不能当最优证书。10月11日必须提出结构成本/证书和获批求解路线；10月16日未完成K0/K1则立即公布对10月20、23、24的影响。

余下路径按依赖推进：先复用并补验共享batch安全 → 获批结构K0/K1 → 同root joint pool与B1/B3/B4 → 160星真实状态链serial/8-worker、tiny oracle与当前全回归 → 逐run实测预算与冻结manifest → 独立运行授权 → 42项正式实验。工程准备可交错进行；未经审批不将参数草案提升为生产语义。本轮不执行这些模块或任何benchmark。

截至目前没有新的完工预测依据，保留HIGH风险。前述18–29人日及11月6–17日延期是旧的从零顺序容量情景，已有代码后不能直接当剩余工期；10月11日重新按剩余任务清单估计，输出最早/保守完工日期和关键依赖。若成本缺测，就同时报告“日期无法可靠估算”，而不是保证10月31日。风险缓解只限获批资源、工程复用和性能运行前审批的非核心范围调整，不减少正确性标准、不隐藏失败，不自动删除42项。

一次性审批仍分科学冻结、结构规则、共享预算、42项矩阵、计算资源、剩余工程验收范围六组；待10月23日实际成本补齐和preflight通过，再提交独立正式运行授权。提交物中所有run预算仍为null/PENDING，不能直接启动。完成本轮计划修订后立即停止。
"""
    checks = {
        "exactly42_unique_ids": len(matrix["runs"]) == 42 == len({r["run_id"] for r in matrix["runs"]}),
        "all_questions_covered": {"Q" + str(i) for i in range(1,11)} <= {q for r in matrix["runs"] for q in r["research_question_ids"]},
        "original_run_ids_order_and_config_unchanged": matrix["runs"] == read(FILES[1])["runs"],
        "eleven_deliverables_not_falsely_accepted": len(deliverables["items"]) == 11 and not any(x["accepted"] for x in deliverables["items"]),
        "all_costs_pending_not_zero": all(r["runtime_budget"]["estimated_wall_clock_s"] is None for r in matrix["runs"]),
        "same_authorization_boundary": all(not x["frozen"] and not x["formal_performance_authorized"] for x in [matrix,budget,deliverables]),
        "input_hashes_match": all(sha(ROOT / rel) == digest for rel,digest in matrix["parent_artifact_sha256"].items()),
        "controller_counts_match": dict(collections.Counter(r["controller"] for r in matrix["runs"])) == matrix["controller_counts"],
        "six_block_counts_match": dict(collections.Counter(r["block"] for r in matrix["runs"])) == matrix["block_counts"]}
    if not all(checks.values()):
        write(attempt / "validation.json", {"status": "FAIL_STOP", "checks": checks})
        raise RuntimeError("Static plan check failed before publishing")
    (ROOT / FILES[0]).write_text(doc, encoding="utf-8")
    for rel, data in zip(FILES[1:], [matrix,budget,deliverables]):
        data["draft_canonical_sha256"] = canonical(data)
        write(ROOT / rel, data)
    changed = [rel for rel,digest in before.items() if not (ROOT / rel).is_file() or sha(ROOT / rel) != digest]
    checks["all_other_existing_files_unchanged"] = not changed
    write(attempt / "historical_integrity_report.json", {"status": "PASS" if not changed else "FAIL", "protected_files":len(before),
                                                        "changed": changed, "authorized_planning_paths": FILES})
    write(attempt / "current_engineering_snapshot.json", snapshot)
    write(attempt / "artifact_hashes.json", {"before": old_hashes, "after": {rel:sha(ROOT / rel) for rel in FILES}})
    report = {"status": "PLAN_READY_FOR_CONSOLIDATED_HUMAN_REVIEW" if all(checks.values()) else "FAIL_STOP",
              "checks": checks, "run_count": 42, "formal_runs_executed_by_task": 0, "benchmarks_executed_by_task": 0,
              "new_engineering_implementation_by_task": False, "deadline_risk": "HIGH", "K_star_selected": False,
              "all_drafts_not_frozen": True, "attempt":str(attempt), "previous_plan_preserved":True}
    write(attempt / "planning_revision_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if changed:
        raise RuntimeError("Historical integrity failed; STOP")


if __name__ == "__main__":
    main()
