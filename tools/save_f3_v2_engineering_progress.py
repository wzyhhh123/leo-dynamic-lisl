# -*- coding: utf-8 -*-
"""Save a new evidence-linked progress checkpoint, never freezes or runs science."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.evidence import file_sha256,write_new_json
from dynamic_lisl.f3_v2.joint_action import canonical_sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acceptance-report',required=True)
    parser.add_argument('--k0-snapshot-report')
    parser.add_argument('--k0-orchestration-report')
    parser.add_argument('--k0-independent-review-report')
    parser.add_argument('--runtime-entry-report')
    args=parser.parse_args()
    acceptance=ROOT/args.acceptance_report
    report=json.loads(acceptance.read_text(encoding='utf-8'))
    sealed=json.loads((acceptance.parent/'input_code_hashes.json').read_text(encoding='utf-8'))
    if report.get('status')!='ENGINEERING_PASS' or not report.get('full_regression_executed') or not report.get('historical_integrity_pass'):
        raise ValueError('CURRENT_COMPLETE_ENGINEERING_REPORT_REQUIRED')
    if any(file_sha256(ROOT/p)!=h for group in ('inputs','code') for p,h in sealed[group].items()):
        raise ValueError('TESTED_SOURCE_CHANGED_SINCE_ACCEPTANCE')
    seals=json.loads((acceptance.parent/'artifact_hashes.json').read_text(encoding='utf-8'))
    if any(file_sha256(acceptance.parent/p)!=h for p,h in seals.items()):raise ValueError('ACCEPTANCE_SEAL_MISMATCH')
    focused,full=report['test_reports']
    natural_rel='outputs/f3_v2_natural_prefix_20261008T142126_443971Z/report.json'
    natural=json.loads((ROOT/natural_rel).read_text(encoding='utf-8'))
    if natural['status']!='NATURAL_K4_FIXTURE_EXACT_EQUIVALENCE_PASS':raise ValueError('NATURAL_FIXTURE_NOT_PASS')
    linked={
        'structural_cost':'outputs/f3_v2_structural_cost_probe_20261008T152937_945871Z/probe_report.json',
        'certificate':'outputs/f3_v2_certificate_verification_20261008T154931_292950Z/report.json',
        'tiny_eta':'outputs/f3_v2_tiny_eta_20261008T152205_955774Z/report.json',
        'manifest_review':'outputs/f3_v2_execution_review_20261008T165332_900421Z/report.json',
        'figure_layout':'outputs/f3_v2_figure_layout_20261008T153624_134185Z/report.json',
        'three_point_cost':'outputs/f3_v2_predeclared_cost_summary_20261008T155819_547812Z/report.json',
        'natural_source_coverage':'outputs/f3_v2_natural_source_coverage_20261008T162145_156464Z/report.json',
        'natural_source_prefix_exact':'outputs/f3_v2_source_prefix_equivalence_20261008T162135_588471Z/report.json',
        'natural_physical_trial_pool_exact':'outputs/f3_v2_natural_physical_trial_20261008T163118_750402Z/report.json'}
    if args.k0_snapshot_report:
        rel=Path(args.k0_snapshot_report)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('EXACT_LOCAL_K0_REPORT_REQUIRED')
        k0=json.loads((ROOT/rel).read_text(encoding='utf-8'))
        if (k0.get('status')!='ENGINEERING_K0_SNAPSHOT_EVIDENCE_PASS'
            or k0.get('scope')!='EIGHT_NODE_SYNTHETIC_ONLY'
            or k0.get('Gate_K0_PASS') is not False or k0.get('K_star_selected') is not False
            or k0.get('registered_experiment_started') is not False):
            raise ValueError('EXACT_K0_ENGINEERING_SCOPE_REQUIRED')
        k0_hashes=json.loads((ROOT/rel).parent.joinpath('input_code_hashes.json').read_text(encoding='utf-8'))
        if any(file_sha256(ROOT/p)!=h for group in ('input','code') for p,h in k0_hashes[group].items()):
            raise ValueError('K0_EVIDENCE_SOURCE_CHANGED')
        linked['k0_snapshot']=rel.as_posix()
    if args.k0_orchestration_report:
        rel=Path(args.k0_orchestration_report)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('EXACT_LOCAL_K0_ORCHESTRATION_REPORT_REQUIRED')
        k0_run=json.loads((ROOT/rel).read_text(encoding='utf-8'))
        if (k0_run.get('status')!='ENGINEERING_K0_ORCHESTRATION_PASS'
            or k0_run.get('full_natural_K0_executed') is not False
            or k0_run.get('Gate_K0_PASS') is not False or k0_run.get('K_star_selected') is not False
            or k0_run.get('registered_experiment_started') is not False
            or k0_run.get('all_spawned_children_joined') is not True):
            raise ValueError('EXACT_K0_ORCHESTRATION_ENGINEERING_SCOPE_REQUIRED')
        k0_seal=json.loads((ROOT/rel).parent.joinpath('input_code_hashes_before.json').read_text(encoding='utf-8'))
        if any(file_sha256(ROOT/p)!=h for group in ('input','code') for p,h in k0_seal[group].items()):
            raise ValueError('K0_ORCHESTRATION_EVIDENCE_SOURCE_CHANGED')
        linked['k0_orchestration']=rel.as_posix()
    if args.k0_independent_review_report:
        rel=Path(args.k0_independent_review_report)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('EXACT_LOCAL_K0_INDEPENDENT_REPORT_REQUIRED')
        proof=json.loads((ROOT/rel).read_text(encoding='utf-8'))
        if (proof.get('status')!='ENGINEERING_K0_INDEPENDENT_REVIEW_PASS'
            or proof.get('scope')!='EIGHT_NODE_SYNTHETIC_ONLY'
            or proof.get('full_natural_K0_executed') is not False
            or proof.get('Gate_K0_PASS') is not False or proof.get('K_star_selected') is not False
            or proof.get('registered_experiment_started') is not False):
            raise ValueError('EXACT_K0_INDEPENDENT_ENGINEERING_SCOPE_REQUIRED')
        proof_hashes=json.loads((ROOT/rel).parent.joinpath('input_code_hashes.json').read_text(encoding='utf-8'))
        if any(file_sha256(ROOT/p)!=h for values in proof_hashes.values() for p,h in values.items()):
            raise ValueError('K0_INDEPENDENT_REVIEW_SOURCE_CHANGED')
        linked['k0_independent_review']=rel.as_posix()
    if args.runtime_entry_report:
        rel=Path(args.runtime_entry_report)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('EXACT_LOCAL_RUNTIME_ENTRY_REPORT_REQUIRED')
        entry=json.loads((ROOT/rel).read_text(encoding='utf-8'))
        if (entry.get('status')!='ENGINEERING_RUNTIME_ENTRY_PASS'
            or entry.get('scope')!='TINY_EPISODES_PLUS_NATURAL_T0_CONSTRUCTION_ONLY'
            or entry.get('natural_controller_multi_epoch_acceptance') is not False
            or entry.get('new_K_star_full_pool_acceptance') is not False
            or entry.get('formal_P1_started') is not False or entry.get('K_star_selected') is not False
            or entry.get('DRAFT_registered_entry_denied') is not True
            or entry.get('all_runtime_cleanup_PASS') is not True):
            raise ValueError('EXACT_RUNTIME_ENTRY_ENGINEERING_SCOPE_REQUIRED')
        entry_hashes=json.loads((ROOT/rel).parent.joinpath('input_code_hashes.json').read_text(encoding='utf-8'))
        if any(file_sha256(ROOT/p)!=h for values in entry_hashes.values() for p,h in values.items()):
            raise ValueError('RUNTIME_ENTRY_EVIDENCE_SOURCE_CHANGED')
        linked['runtime_entry']=rel.as_posix()
    for rel in linked.values():
        p=ROOT/rel
        seal=json.loads((p.parent/'artifact_hashes.json').read_text(encoding='utf-8'))
        if any(file_sha256(p.parent/name)!=h for name,h in seal.items()):
            raise ValueError('LINKED_ENGINEERING_EVIDENCE_SEAL_MISMATCH:'+rel)
    structural=json.loads((ROOT/linked['structural_cost']).read_text(encoding='utf-8'))
    certificate=json.loads((ROOT/linked['certificate']).read_text(encoding='utf-8'))
    if certificate['status']!='ONE_POINT_CERTIFICATE_VERIFICATION_PASS':raise ValueError('ONE_POINT_CERTIFICATE_REQUIRED')
    natural_contract=json.loads((ROOT/natural_rel).parent.joinpath('fixture_contract.json').read_text(encoding='utf-8'))
    natural_current_mismatches=[p for p,h in natural_contract['code_hashes'].items()
        if not (ROOT/p).is_file() or file_sha256(ROOT/p)!=h]
    source=json.loads((ROOT/linked['natural_source_coverage']).read_text(encoding='utf-8'))
    physical_trial=json.loads((ROOT/linked['natural_physical_trial_pool_exact']).read_text(encoding='utf-8'))
    if source['status']!='NATURAL_K4_SOURCE_COVERAGE_AUDIT_COMPLETE' or physical_trial['status']!='NATURAL_PHYSICAL_TRIAL_POOL_EXACT_PASS':
        raise ValueError('NATURAL_SOURCE_AND_PHYSICAL_EVIDENCE_REQUIRED')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    out=ROOT/'outputs'/('f3_v2_engineering_checkpoint_'+stamp);out.mkdir()
    progress_rel='docs/F3_V2_IMPLEMENTATION_PROGRESS.md';status_rel='configs/f3_v2_implementation_status.json'
    prior={}
    for rel in (progress_rel,status_rel):
        p=ROOT/rel
        if p.exists():
            target=out/'prior_progress_bytes'/p.name;target.parent.mkdir(exist_ok=True)
            shutil.copyfile(p,target);prior[rel]=file_sha256(p)
    rows=natural['records']
    serial=sum(r['serial_observe_wall_s'] for r in rows)
    parallel=sum(r['parallel_observe_wall_s'] for r in rows)
    cost={'status':'ENGINEERING_FIXTURE_COST_ONLY_NOT_APPROVED_MATRIX_BUDGET',
        'natural_prefix_report':natural_rel,'report_sha256':file_sha256(ROOT/natural_rel),
        'scope':'HISTORICAL_160_STAR_K4_SMALL_STRUCTURAL_FIXTURE; not current production or K* acceptance',
        'historical_natural_code_changed':natural_current_mismatches,
        'epochs_s':[r['time_s'] for r in rows],'branches_per_epoch':[r['branch_count'] for r in rows],
        'serial_observe_total_s':serial,'parallel_observe_total_s':parallel,
        'observe_speedup_from_summed_times':serial/parallel,
        'parallel_observe_range_s':[min(r['parallel_observe_wall_s'] for r in rows),max(r['parallel_observe_wall_s'] for r in rows)],
        'equivalence_attempt_wall_s':natural['total_wall_s'],
        'equivalence_attempt_wall_is_not_episode_cost':True,
        'production_K_star_inventory_cost_s':None,'production_pool_epoch_cost_s':None,
        'one_point_t0_K24_inventory_wall_s':structural['inventory_wall_s'],
        'one_point_t0_matching_wall_s':structural['matching_wall_s'],
        'one_point_t0_K24_analytic_certificate_wall_s':structural['analytic_certificate_wall_s'],
        'full_K0_all_points_cost_s':None,'full_K0_all_points_certified':False,
        'complete_episode_cost_s':None,'matrix_42_run_cost_s':None,
        'natural_K4_t0_source_wall_s':source['source_wall_s'],
        'natural_K4_t0_source_physical_evaluations':source['source_evaluations_completed'],
        'natural_K4_t0_raw_old_histogram':source['raw_old_binding_histogram'],
        'natural_K4_t0_singleton_old_histogram':source['singleton_old_binding_histogram'],
        'natural_K4_t0_pool_max_size':source['final_pool_max_batch_size'],
        'natural_uncapped_joint_safe_witness_size':source['uncapped_joint_safe_witness_size'],
        'natural_capped_physical_clone_proposer_speedup':physical_trial['proposer_speedup'],
        'clone_proposer_speedup_not_B4_speedup':True,
        'scientific_performance_read_for_budget':False,'approved_runtime_budget':False}
    write_new_json(out/'runtime_observations.json',cost)
    status={'status':'ENGINEERING_PROGRESS_SCIENTIFIC_FREEZE_PENDING','created_utc':stamp,
        'latest_acceptance_report':args.acceptance_report,'current_tested_v2_source_matches_test_seal':True,
        'focused_tests':focused['tests'],'focused_result':'PASS','full_repository_tests':full['tests'],
        'full_result':'PASS','focused_wall_s':focused['wall_s'],'full_wall_s':full['wall_s'],
        'historical_integrity':'PASS_WITH_EXPLICIT_PLANNING_ONLY_REVISION; scientific/runtime files unchanged',
        'gate_states':{'V2_A_B_C':'SYNTHETIC_ENGINEERING_PASS',
            'K0':('BOUNDED_ORCHESTRATION_FIXTURE_PASS_AUTHORIZED_NATURAL_FULL_AUDIT_PENDING' if args.k0_orchestration_report else
                'TINY_PRODUCER_CONTENT_CHAIN_ORACLE_PASS_FULL_AUDIT_PENDING' if args.k0_snapshot_report else
                'TINY_EXACT_AND_LEDGER_PASS_THREE_POINT_CERTIFICATES_ONLY_FULL_AUDIT_PENDING'),
            'K1':'TINY_CANDIDATE_PASS_FORMAL_K1_PENDING',
            'V2_D':'FIXTURES_PASS_NATURAL_SINGLETON_DEGENERACY_OBSERVED_SOURCE_POLICY_FREEZE_PENDING',
            'V2_E':'CURRENT_SYNTHETIC_PASS_HISTORICAL_NATURAL_K4_PASS_CURRENT_K_STAR_PRODUCTION_PENDING',
            'V2_F':'B0_B1_B2_B3_B4_EPISODE_FIXTURES_PASS_SCIENTIFIC_FREEZE_PENDING',
            'V2_G':'FAILURE_FIRST_EVIDENCE_ANALYSIS_REVIEW_MANIFEST_FIGURE_INTERFACE_TESTED_FORMAL_PREFLIGHT_NOT_READY'},
        'natural_multi_epoch_evidence':natural_rel,'historical_natural_K4_exact_equivalence':True,
        'current_natural_B4_stack_exact_equivalence':not natural_current_mismatches,
        'natural_evidence_current_code_mismatches':natural_current_mismatches,
        'worker_failure_tests':'PASS_WITH_COMPLETED_PREFIX_EVIDENCE_AND_CLEAN_SHUTDOWN',
        'raw_coverage_counterexample':'outputs/f3_v2_raw_batch_coverage_20261008T144825_051246Z/report.json',
        'raw_policy_changed':False,'B4_v2_engineering_PASS':False,'formal_performance_ready':False,
        'K_star_selected':False,'registered_P1_v2_executed':False,'P2_started':False,'RL_started':False,
        'deadline_risk':'HIGH; full K0, natural K*/production pool/episode costs and coverage policy pending',
        'linked_new_engineering_evidence':linked,
        'tiny_eta_short_member_limitation_observed':True,
        'execution_review_run_count':42,'paper_figure_pipeline_implemented':True,
        'paper_figure_layout_QA_scope':'literal engineering data only; no formal result figure',
        'runtime_observations':out.relative_to(ROOT).as_posix()+'/runtime_observations.json',
        'remaining_authorized_engineering':[
            'complete natural K0 asset provenance/certificate acceptance under approved contract; tiny independent proofs do not replace full audit',
            'conditional matrix/runtime entry implemented; final production adoption requires approved scientific contract and resource limits',
            'production configuration acceptance after consolidated freeze',
            'final evidence package after approved manifest and separate run authorization'],
        'awaiting_scientific_freeze':[
            'K0-v1.1, independent pre-established snapshot initialization, and K1 initial age',
            '5s/batch4 safety/scoring/forecast/late-horizon semantics',
            'shared search budgets AND old-binding/terminal-footprint diversity AND runtime scouting budget',
            'B2 per-binding LINK_UP H4/H8 / age0',
            '42-run manifest and measured operational resources/budgets'],
        'consolidated_approval_document':'docs/F3_V2_HUMAN_FREEZE_CHECKLIST_CN.md',
        'risk_update_document':'docs/F3_V2_OCTOBER_RISK_UPDATE_CN.md',
        'goal_complete':False,'continues_authorized_engineering':True,
        'current_progress_checkpoint':out.relative_to(ROOT).as_posix(),
        'tested_input_code_sha256':sealed,'progress_writer_sha256':file_sha256(Path(__file__))}
    status['conditional_runtime_entry_engineering_checked']=bool(args.runtime_entry_report)
    status['natural_factory_initial_state_only_verified']=bool(args.runtime_entry_report)
    status['production_source_policy_approved']=False
    status['progress_canonical_sha256']=canonical_sha256(status)
    (ROOT/status_rel).write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    text=f'''# F3-v2 实施进度

状态：ENGINEERING_PROGRESS；科学合同DRAFT_NOT_FROZEN。目标未完成，正式P1-v2/P2/RL未启动。

## 当前验收

{focused['tests']}项v2测试PASS（{focused['wall_s']:.3f} s），{full['tests']}项全仓库回归PASS（{full['wall_s']:.3f} s）。测试命令、退出码、stdout/stderr及源文件hash见 [{args.acceptance_report}](../{args.acceptance_report})。保存进度前已逐项确认该验收封存与当前被测试代码/输入相同。3164项既有保护基线通过；仅明确授权的4份October计划修订经精确parent/replacement hash链接受，不新增科学runtime successor，不修改历史FAIL/PASS。

|阶段|状态|关键代码（src/dynamic_lisl/f3_v2）|范围与缺项|
|---|---|---|---|
|V2-A/B/C|synthetic engineering PASS|joint_action.py / batch_executor.py / service_adapter.py|2/3/4 BBM/MBB/mixed、冲突、原子性、全timeline、expiry、守恒、singleton兼容；不是正式K*验收|
|K0|tiny exact/ledger PASS；三个cost点证书PASS|structural.py / certified_topology.py / k0_ledger.py|三点inventory约48–59 s；matching约0.46–0.71 s；解析证书约0.016–0.020 s；20点×原K列表完整审计及正式选择未完成|
|K1|tiny candidate PASS；formal PENDING|k1.py|精确K/双端物理/连通初态模板；正式K1依赖获批K0和初始化约定|
|V2-D/E|current fixtures PASS；historical natural K4 exact PASS|joint_proposer.py / snapshot_controllers.py / batch_rollout.py|旧t=0/2/4/6/8/10自然state-chain证据保留；当前源码已变化，最终K*/5s/production pool须重新验收|
|V2-F/G|短episode/证据/分析/图表接口PASS；formal NOT_READY|engineering_episode.py / evidence.py / preflight.py / result_analysis.py / paper_figures.py / manifest_review.py|42-run审阅版保留原ID/配置/顺序；图表先验全结果与seal；正式冻结manifest、实际论文图表与主实验未完成|

## 自然场景精确等价与成本

[{natural_rel}](../{natural_rel})历史封存6个epoch、每epoch9分支，four checkpoint和完整自然状态链exact，persistent pool复用、live隔离、无孤儿进程。当前代码与该证据有{len(natural_current_mismatches)}处hash差异（逐项在status JSON）；不能据它声明当前B4自然验收PASS，更不能冒充K*/5s/full pool验收。

该等价检查总墙钟{natural['total_wall_s']:.3f} s；serial observe合计{serial:.3f} s、8-worker合计{parallel:.3f} s，observe speedup={serial/parallel:.3f}x。总墙钟包含两模式/审计，不是正式episode耗时。正式K* source/pool、最大分支池、不同阶段及整episode成本仍null。一次RSS约1.327 GiB只是瞬时parent+8worker快照，非主规模峰值保证。原始内存错误快照保留，不采用。

## 新结构风险与集中审批

K0新单点证据和真实tiny B3评分见 [工程结果](F3_V2_ENGINEERING_SOLVER_AND_SCORING_RESULT_CN.md)。t0/K24达到四项全局数学界并按canonical枚举得到证书，不能外推为全部K×20通过。旧60 s timeout与int.bit_count环境兼容FAIL均原样保留。B3 min eta在真实8节点fixture中确实会让短寿命成员主导整个batch评分；公式未据此调整。

raw覆盖构造例144个物理候选→32截断候选（全部同一old binding）→16个singleton；另有真实whole-transition safe四成员witness。因此原排序可能在beam之前丢失batch覆盖，不能靠batch4权限宣称联合控制已实现有效搜索。证据见 [raw coverage](../outputs/f3_v2_raw_batch_coverage_20261008T144825_051246Z/report.json)。不证明实际K*已发生，也未按结果修改科学policy。

集中审批见 [F3_V2_HUMAN_FREEZE_CHECKLIST_CN.md](F3_V2_HUMAN_FREEZE_CHECKLIST_CN.md)，风险和里程碑见 [F3_V2_OCTOBER_RISK_UPDATE_CN.md](F3_V2_OCTOBER_RISK_UPDATE_CN.md)。10月31日风险HIGH；Oct11需解决成本/求解证书与候选多样性审批，不能缺测填0或省失败。42项矩阵、固定ID和配置未变，仍DRAFT。

## 当前自然候选覆盖与新K0汇总入口

真实K4/t0完整source验证7980次，7596个物理合法候选→raw64（old分布49/9/6/0）→singleton16（16/0/0/0），最终pool最大size1；与此同时存在真实整批安全size4 MBB witness。source耗时{source['source_wall_s']:.3f} s，原始证据在 [{linked['natural_source_coverage']}](../{linked['natural_source_coverage']})。该结果只涵盖这一K4/t0，不据此选K或修改原排序。64-row physical clone/proposer和size4 witness严格等价PASS，局部proposer提速{physical_trial['proposer_speedup']:.3f}x，不是B4或整episode提速。

新的k0_ledger.py / prepare_f3_v2_k0_ledger_review.py只汇总明确文件/hash引用的结构证据：原12个K×20点×2replay共480条应有记录；缺失、UNKNOWN、replay mismatch逐项保留，不伪称空admissible set。支持18/20、median中间两项均值、uncapped库存约束、右删失截断寿命和按K完整性。磁盘loader已增加内容关联校验、重算matching/图/截断寿命、原Gate B预建立状态重构；不以支持文件hash本身证明全局最优、Gate C窗口生成或uncapped库存完整性，也不选择K*。

逐点producer为k0_snapshot.py，复用真实Gate B/C、原exact solver及uncapped source。{'当前8星t=0/30/570双replay、独立tiny matching/lex oracle、磁盘支持链、t0真实四链MBB安全witness均PASS，见 '+linked['k0_snapshot'] if args.k0_snapshot_report else '逐点producer验收证据未传入本次checkpoint'}。其独立预建立快照只是一项显式工程假设，未冻结；setup资格与snapshot时预建链状态分别存证，不能解释为免费执行真实重构。完整160星K×20执行/成本/独立证书与人工冻结仍未完成。

{'新增k0_audit_runner.py已通过固定8星六点隔离编排、库存预算/solver UNKNOWN区分、timeout与子进程清理、DRAFT拒绝检查；证据 '+linked['k0_orchestration'] if args.k0_orchestration_report else '完整结构编排当前验收证据未传入本次checkpoint'}。自然full-domain入口必须绑定新FROZEN合同、480点原序列、独立人工结构授权、源码/scene/window/setup/backbone哈希；审批文件在manifest之后独立签署，避免循环hash。编排器不选择K*，完整自然审计未执行，独立全部证书与provenance验收仍未完成。

{'新增独立复核器k0_independent_review.py在当前8星t0/30/570以及K16上界不可行点PASS，见 '+linked['k0_independent_review'] if args.k0_independent_review_report else '独立复核器当前证据未传入本次checkpoint'}。复核器重新枚举Gate C原catalogue、uncapped REPLACE，独立穷举terminal matching及lex最优与canonical tie；不调用producer/source/solver来证明其自身结果。预算耗尽为UNKNOWN。该tiny结论不验证自然窗口生成，不代替全部480自然记录/批量diagnostic独立验收，不选择K*。

## 证据与执行管线

worker result/submission失败均保留完成prefix、root/forecast/action哈希，拒绝重试并安全shutdown；错误fixture及全部FAIL attempt均保留。engineering episode只接受ENGINEERING- fixture ID；共用真实D2 cadence/drain，结束COMPLETE/CENSORED或失败完整存证后STOP。新的条件正式入口必须先验证真实FROZEN合同、K0/K1、当前验收、实测资源与独立人工授权；现有DRAFT在建runtime前拒绝。

{'共同episode/矩阵顺序、失败先存证、cleanup、真实160星t0构造器exact与DRAFT拒绝已验，见 '+linked['runtime_entry'] if args.runtime_entry_report else '当前条件入口独立验收证据未传入本checkpoint'}。160星测试没有advance/source/observe/rollout，不能当作K*/5s/full pool或新版多epoch验收。原source仍uncapped scan后截断；新diversity/scouting未获批、未被悄悄实现。详细边界见 [运行入口工程说明](F3_V2_RUNTIME_ENTRY_ENGINEERING_CN.md)。

结果loader先检查FROZEN canonical manifest，再校验原始seal、注册input/code哈希和run配置绑定；自重封存的错误输入/配置仍拒绝。全部registered COMPLETE/CENSORED之前不生成paired analysis；删失不以truncated J排名，不造global ranking或随机重复显著性。正式evidence必须显式绑定manifest/run SHA，不能拿工程结果冒充。

load-aware scoring在私有router按原E2 current-state公式补当前epoch上下文，不改live fast routes或时间；full canonical包含queue/transition/propagation诊断。原Gate B/C/D、旧controller与frozen manifests未改。

## 下步与当前封存

可继续独立工程：自然K0输入provenance/证书验收准备与条件执行入口的最终生产验收准备。三个预声明成本点、真实自然raw覆盖、tiny eta、42-run审阅manifest和固定case绘图接口已有证据。HF_SEARCH须同时决定old/terminal-footprint多样性与runtime scouting计算预算；否则正式pool与episode成本仍阻塞。科学参数集中审批后才可正式K*、K1及生产验收；完整preflight和另一次人工运行授权前不启动正式论文实验。

当前checkpoint：{out.relative_to(ROOT).as_posix()}。逐文件SHA、各Gate、耗时、依赖和未决项见progress_snapshot.json及runtime_observations.json；之前进度bytes已保存，不覆盖历史attempt。

工程总体B4-v2 PASS=false；正式ready=false；goal_complete=false。
'''
    (ROOT/progress_rel).write_text(text,encoding='utf-8')
    write_new_json(out/'progress_snapshot.json',status)
    rels=[progress_rel,status_rel,'docs/F3_V2_HUMAN_FREEZE_CHECKLIST_CN.md','docs/F3_V2_OCTOBER_RISK_UPDATE_CN.md',
          args.acceptance_report,natural_rel,'outputs/f3_v2_raw_batch_coverage_20261008T144825_051246Z/report.json',
          'docs/F3_V2_ENGINEERING_SOLVER_AND_SCORING_RESULT_CN.md',
          'docs/F3_V2_NATURAL_SOURCE_COVERAGE_RESULT_CN.md',
          'docs/F3_V2_PHYSICAL_TRIAL_CLONE_AUDIT_CN.md',
          'docs/F3_V2_K0_LEDGER_ENGINEERING_CN.md']+list(linked.values())
    if args.k0_orchestration_report:rels.append('docs/F3_V2_K0_ORCHESTRATION_ENGINEERING_CN.md')
    if args.k0_independent_review_report:rels.append('docs/F3_V2_K0_INDEPENDENT_REVIEW_ENGINEERING_CN.md')
    if args.runtime_entry_report:rels.append('docs/F3_V2_RUNTIME_ENTRY_ENGINEERING_CN.md')
    write_new_json(out/'artifact_hashes.json',{'prior_progress_hashes':prior,
        'current_linked_files':{p:file_sha256(ROOT/p) for p in rels},
        'checkpoint_files':{p.relative_to(out).as_posix():file_sha256(p) for p in out.rglob('*') if p.is_file()}})
    print(json.dumps({'status':'ENGINEERING_PROGRESS_SAVED','checkpoint':str(out),
        'focused_tests':focused['tests'],'full_tests':full['tests'],'B4_v2_engineering_PASS':False,
        'formal_ready':False,'goal_complete':False},indent=2))


if __name__=='__main__':main()
