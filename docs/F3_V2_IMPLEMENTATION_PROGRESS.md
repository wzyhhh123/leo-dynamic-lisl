# F3-v2 实施进度

状态：ENGINEERING_PROGRESS；科学合同DRAFT_NOT_FROZEN。目标未完成，正式P1-v2/P2/RL未启动。

## 当前验收

194项v2测试PASS（76.718 s），523项全仓库回归PASS（132.329 s）。测试命令、退出码、stdout/stderr及源文件hash见 [outputs/f3_v2_engineering_check_20261008T190136_458031Z/report.json](../outputs/f3_v2_engineering_check_20261008T190136_458031Z/report.json)。保存进度前已逐项确认该验收封存与当前被测试代码/输入相同。3164项既有保护基线通过；仅明确授权的4份October计划修订经精确parent/replacement hash链接受，不新增科学runtime successor，不修改历史FAIL/PASS。

|阶段|状态|关键代码（src/dynamic_lisl/f3_v2）|范围与缺项|
|---|---|---|---|
|V2-A/B/C|synthetic engineering PASS|joint_action.py / batch_executor.py / service_adapter.py|2/3/4 BBM/MBB/mixed、冲突、原子性、全timeline、expiry、守恒、singleton兼容；不是正式K*验收|
|K0|tiny exact/ledger PASS；三个cost点证书PASS|structural.py / certified_topology.py / k0_ledger.py|三点inventory约48–59 s；matching约0.46–0.71 s；解析证书约0.016–0.020 s；20点×原K列表完整审计及正式选择未完成|
|K1|tiny candidate PASS；formal PENDING|k1.py|精确K/双端物理/连通初态模板；正式K1依赖获批K0和初始化约定|
|V2-D/E|current fixtures PASS；historical natural K4 exact PASS|joint_proposer.py / snapshot_controllers.py / batch_rollout.py|旧t=0/2/4/6/8/10自然state-chain证据保留；当前源码已变化，最终K*/5s/production pool须重新验收|
|V2-F/G|短episode/证据/分析/图表接口PASS；formal NOT_READY|engineering_episode.py / evidence.py / preflight.py / result_analysis.py / paper_figures.py / manifest_review.py|42-run审阅版保留原ID/配置/顺序；图表先验全结果与seal；正式冻结manifest、实际论文图表与主实验未完成|

## 自然场景精确等价与成本

[outputs/f3_v2_natural_prefix_20261008T142126_443971Z/report.json](../outputs/f3_v2_natural_prefix_20261008T142126_443971Z/report.json)历史封存6个epoch、每epoch9分支，four checkpoint和完整自然状态链exact，persistent pool复用、live隔离、无孤儿进程。当前代码与该证据有4处hash差异（逐项在status JSON）；不能据它声明当前B4自然验收PASS，更不能冒充K*/5s/full pool验收。

该等价检查总墙钟2004.986 s；serial observe合计1189.818 s、8-worker合计351.768 s，observe speedup=3.382x。总墙钟包含两模式/审计，不是正式episode耗时。正式K* source/pool、最大分支池、不同阶段及整episode成本仍null。一次RSS约1.327 GiB只是瞬时parent+8worker快照，非主规模峰值保证。原始内存错误快照保留，不采用。

## 新结构风险与集中审批

K0新单点证据和真实tiny B3评分见 [工程结果](F3_V2_ENGINEERING_SOLVER_AND_SCORING_RESULT_CN.md)。t0/K24达到四项全局数学界并按canonical枚举得到证书，不能外推为全部K×20通过。旧60 s timeout与int.bit_count环境兼容FAIL均原样保留。B3 min eta在真实8节点fixture中确实会让短寿命成员主导整个batch评分；公式未据此调整。

raw覆盖构造例144个物理候选→32截断候选（全部同一old binding）→16个singleton；另有真实whole-transition safe四成员witness。因此原排序可能在beam之前丢失batch覆盖，不能靠batch4权限宣称联合控制已实现有效搜索。证据见 [raw coverage](../outputs/f3_v2_raw_batch_coverage_20261008T144825_051246Z/report.json)。不证明实际K*已发生，也未按结果修改科学policy。

集中审批见 [F3_V2_HUMAN_FREEZE_CHECKLIST_CN.md](F3_V2_HUMAN_FREEZE_CHECKLIST_CN.md)，风险和里程碑见 [F3_V2_OCTOBER_RISK_UPDATE_CN.md](F3_V2_OCTOBER_RISK_UPDATE_CN.md)。10月31日风险HIGH；Oct11需解决成本/求解证书与候选多样性审批，不能缺测填0或省失败。42项矩阵、固定ID和配置未变，仍DRAFT。

## 当前自然候选覆盖与新K0汇总入口

真实K4/t0完整source验证7980次，7596个物理合法候选→raw64（old分布49/9/6/0）→singleton16（16/0/0/0），最终pool最大size1；与此同时存在真实整批安全size4 MBB witness。source耗时455.081 s，原始证据在 [outputs/f3_v2_natural_source_coverage_20261008T162145_156464Z/report.json](../outputs/f3_v2_natural_source_coverage_20261008T162145_156464Z/report.json)。该结果只涵盖这一K4/t0，不据此选K或修改原排序。64-row physical clone/proposer和size4 witness严格等价PASS，局部proposer提速2.169x，不是B4或整episode提速。

新的k0_ledger.py / prepare_f3_v2_k0_ledger_review.py只汇总明确文件/hash引用的结构证据：原12个K×20点×2replay共480条应有记录；缺失、UNKNOWN、replay mismatch逐项保留，不伪称空admissible set。支持18/20、median中间两项均值、uncapped库存约束、右删失截断寿命和按K完整性。磁盘loader已增加内容关联校验、重算matching/图/截断寿命、原Gate B预建立状态重构；不以支持文件hash本身证明全局最优、Gate C窗口生成或uncapped库存完整性，也不选择K*。

逐点producer为k0_snapshot.py，复用真实Gate B/C、原exact solver及uncapped source。当前8星t=0/30/570双replay、独立tiny matching/lex oracle、磁盘支持链、t0真实四链MBB安全witness均PASS，见 outputs/f3_v2_k0_snapshot_20261008T184247_039493Z/report.json。其独立预建立快照只是一项显式工程假设，未冻结；setup资格与snapshot时预建链状态分别存证，不能解释为免费执行真实重构。完整160星K×20执行/成本/独立证书与人工冻结仍未完成。

新增k0_audit_runner.py已通过固定8星六点隔离编排、库存预算/solver UNKNOWN区分、timeout与子进程清理、DRAFT拒绝检查；证据 outputs/f3_v2_k0_orchestration_20261008T184307_122277Z/report.json。自然full-domain入口必须绑定新FROZEN合同、480点原序列、独立人工结构授权、源码/scene/window/setup/backbone哈希；审批文件在manifest之后独立签署，避免循环hash。编排器不选择K*，完整自然审计未执行，独立全部证书与provenance验收仍未完成。

新增独立复核器k0_independent_review.py在当前8星t0/30/570以及K16上界不可行点PASS，见 outputs/f3_v2_k0_independent_review_20261008T184247_090488Z/report.json。复核器重新枚举Gate C原catalogue、uncapped REPLACE，独立穷举terminal matching及lex最优与canonical tie；不调用producer/source/solver来证明其自身结果。预算耗尽为UNKNOWN。该tiny结论不验证自然窗口生成，不代替全部480自然记录/批量diagnostic独立验收，不选择K*。

## 证据与执行管线

worker result/submission失败均保留完成prefix、root/forecast/action哈希，拒绝重试并安全shutdown；错误fixture及全部FAIL attempt均保留。engineering episode只接受ENGINEERING- fixture ID；共用真实D2 cadence/drain，结束COMPLETE/CENSORED或失败完整存证后STOP。新的条件正式入口必须先验证真实FROZEN合同、K0/K1、当前验收、实测资源与独立人工授权；现有DRAFT在建runtime前拒绝。

共同episode/矩阵顺序、失败先存证、cleanup、真实160星t0构造器exact与DRAFT拒绝已验，见 outputs/f3_v2_runtime_entry_20261008T184246_505918Z/report.json。160星测试没有advance/source/observe/rollout，不能当作K*/5s/full pool或新版多epoch验收。原source仍uncapped scan后截断；新diversity/scouting未获批、未被悄悄实现。详细边界见 [运行入口工程说明](F3_V2_RUNTIME_ENTRY_ENGINEERING_CN.md)。

结果loader先检查FROZEN canonical manifest，再校验原始seal、注册input/code哈希和run配置绑定；自重封存的错误输入/配置仍拒绝。全部registered COMPLETE/CENSORED之前不生成paired analysis；删失不以truncated J排名，不造global ranking或随机重复显著性。正式evidence必须显式绑定manifest/run SHA，不能拿工程结果冒充。

load-aware scoring在私有router按原E2 current-state公式补当前epoch上下文，不改live fast routes或时间；full canonical包含queue/transition/propagation诊断。原Gate B/C/D、旧controller与frozen manifests未改。

## 下步与当前封存

可继续独立工程：自然K0输入provenance/证书验收准备与条件执行入口的最终生产验收准备。三个预声明成本点、真实自然raw覆盖、tiny eta、42-run审阅manifest和固定case绘图接口已有证据。HF_SEARCH须同时决定old/terminal-footprint多样性与runtime scouting计算预算；否则正式pool与episode成本仍阻塞。科学参数集中审批后才可正式K*、K1及生产验收；完整preflight和另一次人工运行授权前不启动正式论文实验。

当前checkpoint：outputs/f3_v2_engineering_checkpoint_20261008T190531_630836Z。逐文件SHA、各Gate、耗时、依赖和未决项见progress_snapshot.json及runtime_observations.json；之前进度bytes已保存，不覆盖历史attempt。

工程总体B4-v2 PASS=false；正式ready=false；goal_complete=false。

## Natural K0 input provenance checkpoint

Input provenance PASS: 77 checks, 20 structural samples, 2742 terminal-pair windows (1992 right-censored, 750 known terminal-pair expiry). At t=570 the idle representative is ready at 572, with 28 seconds usable within the observation horizon. Counts assume unreserved IDLE endpoints; occupied BBM/MBB readiness must still use real Gate B/C. See [input audit](F3_V2_NATURAL_INPUT_PROVENANCE_CN.md).

Current focused regression: 194/194 PASS; full repository: 523/523 PASS. No scientific/runtime implementation changed in this checkpoint; only a read-only auditor, its nine control tests, and documentation were added. The protected 3164-file baseline is unchanged apart from the four previously authorized planning revisions.

Formal preflight remains NOT_READY. K0/K1 full natural evidence, K*, final production candidate policy/8-worker acceptance, measured run budgets, science freeze and independent run authorization are still missing. Gate K0 PASS=false; B4-v2 overall engineering PASS=false; formal P1-v2/P2/RL=false. This input check is not a narrower substitute for the complete objective.

Checkpoint: outputs/f3_v2_natural_input_progress_20261008T190632_088993Z. Previous progress bytes preserved in prior_progress_bytes.

## Concrete HF_SEARCH proposal and K0 operation-count risk

Added [candidate-policy approval draft](F3_V2_SEARCH_POLICY_APPROVAL_DRAFT_CN.md) and configs/f3_v2_search_policy_human_review_DRAFT.json. The recommendation specifies256 visits, round-robin old/window coverage, raw64/singleton16, structural size seeds, and shared184/33 limits.21 static completeness checks PASS; this is not algorithm execution or equivalence. Policy is NOT_IMPLEMENTED/NOT_FROZEN; current source and current194/523 test seal unchanged. Prior draft byte/hash records and the LF/CRLF archival-validation failure were preserved.

New [K0 uncapped cost risk](F3_V2_K0_UNCAPPED_COST_RISK_CN.md): if every registeredK/t yields an exact pre-established topology, current two-replay source loop entails55,077,664 validations. This conditional count is not an observed feasible domain or a runtime forecast. Runtime scouting cap must never truncate K0. Actual full K0 cost remains unmeasured.

Consolidated human-freeze question is pending; do not treat automatic goal continuation as approval. No new scientific controller/code/candidate policy implemented, no tests or profiles rerun this checkpoint, no formal K0/K*/P1-v2/P2/RL. Existing full objective remains incomplete. Checkpoint: outputs/f3_v2_approval_dependency_checkpoint_20261008T192825_021130Z.


## 已占用根状态的短前缀成本观察

t=0/K24、t=270/K48、t=570/K80各64次物理验证，source前缀耗时3.609、2.034、2.132秒。仅涉及各点第一条旧链路，不代表全域成本。完整inventory未执行；局部结果禁止作为生产候选源。

Evidence: outputs/f3_v2_occupied_cost_probe_20261008T193613_387045Z/report.json

未改生产源码；先前194/523测试封存仍匹配当前源码，本次未重跑全回归。集中人工审批仍待回复；未冻结新政策，未启动正式实验。


## 集中审批包已完整汇总

[One consolidated review packet](F3_V2_CONSOLIDATED_APPROVAL_PACKET_CN.md) + configs/f3_v2_consolidated_human_review_DRAFT.json.22 static review checks PASS; pending groups HF_SCIENCE/HF_K/HF_SEARCH/HF_B2/HF_MATRIX/HF_RESOURCE. Current77-check input provenance and192-call cost-prefix evidence linked; complete K0/K1, final natural production acceptance and42-run costs still missing.

Existing scientific/runtime/tested code seal unchanged; no new regression, source-policy implementation, frozen contract, K* or formal run. Original checklist bytes and failed independent JSON-canonicalization validation preserved. Review evidence: outputs/f3_v2_consolidated_review_20261008T195035_935391Z/report.json.

下一步需要集中人工冻结回复。已发问题仍待处理，不重复逐参数提问，不把自动goal续行当作批准。完整原始目标未完成。
