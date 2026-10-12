# F3-v2 真实K4候选覆盖与运行成本结果

状态：ENGINEERING_ONLY；未运行controller/traffic/service/Q/I/D/J，未选择K*，不修改原K4、Gate B/C/D、F3-v1和任何历史FAIL/PASS。

## 完整自然输入审计

固定160星、t=0、历史K4 binding、原Gate C 0–600 s bilateral terminal-pair资产；预建链按现有natural-prefix的原sequential submit顺序初始化。原样candidate_source.replacement_inventory遍历全部old binding×当前terminal-pair window，再执行原rank与raw32/32/64截断。使用已有草案singleton16/8+8、beam4、pool32、validation/expansion184、rollout cap33；仅审计，不冻结这些值。

|项目|实测|
|---|---|
|t0 terminal-pair windows|1996|
|old bindings|4|
|全部候选验证|7980（4×1996，扣除4个exact physical noop）|
|物理合法REPLACE|7596|
|截断raw|64：MBB32、BBM32|
|raw分布，按old lexical顺序|49、9、6、0|
|final singleton分布|16、0、0、0|
|非HOLD共享池|16个，全为size1；size2/3/4均0|
|整批安全四链genuine MBB witness|存在；原Gate B/C和whole-transition STRICT_CONNECTED PASS|
|witness成员是否进入raw/singleton|四个均未进入|

因此，**真实K4自然输入下，当前raw/singleton排序确实可能在联合搜索之前丢失批量覆盖**。这不是因为物理网络不存在四链动作，也不是beam搜索已经证明所有组合不可行。不能将“权限最多4”表述为当前实际pool支持了联合四链控制。

结论范围仅该固定K4/t0；不证明每个epoch、K*或其他初态均退化。不根据结果换case、增大K、修改预算/排序，不自动将batch覆盖加入K0硬门槛。

原始完整证据：[自然审计](../outputs/f3_v2_natural_source_coverage_20261008T162145_156464Z/report.json)、[完整raw审计](../outputs/f3_v2_natural_source_coverage_20261008T162145_156464Z/raw_source_audit.json)、[shared pool](../outputs/f3_v2_natural_source_coverage_20261008T162145_156464Z/pool.json)、[四链安全证据](../outputs/f3_v2_natural_source_coverage_20261008T162145_156464Z/structural_witness.json)。source/proposer只读root，文件hash未变，child已正常退出，无controller性能泄漏。

## 成本及exact clone的适用范围

初次工程观察在300 s预算只完成2221次验证，状态为SOURCE_OBSERVATION_BUDGET_UNKNOWN，没有输出截断生产source/pool；证据保留。该次将四条初态Connect放入一个transaction，initial event/checkpoint与现有sequential初始化不同；只用于成本定位，不能拿其root作为后续exact对照reference。随后建立相同sequential root的两个独立128-row attempt。

针对原Gate C deepcopy历史日志的开销，仅在新v2验证器给已经审计的原类型传入已有history-free exact clone。原Gate B/C不修改。全部terminal/link/reservation/event/free/setup/orientation/version/sequence复制；仅旧log省略，原catalog仍从当前trial新增RESERVE_BOTH读取ready。hardware/custom扩展保留legacy路径；未知字段fail closed。逐字段审计：[clone依赖审计](F3_V2_PHYSICAL_TRIAL_CLONE_AUDIT_CN.md)。

相同自然128-row对照：legacy source 19.159908 s，optimized 7.316285 s，约2.619×。全部row IDs/order/accepted/reason/geometry，root隔离与四链完整validation exact，见 [prefix exact report](../outputs/f3_v2_source_prefix_equivalence_20261008T162135_588471Z/report.json)。这不是全7980行legacy执行对照，不能称full-source empirical equivalence或主episode提速。

优化路径完成全部7980次验证：source 455.080745 s，其中validator 454.197608 s；proposer 7.683084 s；整次含初始化/witness/写证据463.973936 s。被动记录无fsync，source wall包含记录开销。原候选排序、配额、root/proposal/hash定义、setup、event order和service均未调整。

**仅t0/K4的source已约7.6分钟，显著超过当前预算草案22.5 s/非B4 epoch和135 s/B4 epoch的零开销平均规划上限。** 单点不是全episode平均或保守总预算，不能据此给出精确42-run日期，但已是必须现在处理的critical-path blocker；不以2.619×前缀提速宣布月底运行可行。

## 集中审批所需的candidate-source决策

当前raw output cap不限制此前7980次昂贵Gate C验证。formal runtime采用uncapped全扫描再截断，和bounded shared search的运行成本目标存在矛盾。需要同时明确**计算scouting预算**与**候选结构覆盖政策**，不能只增加beam或batch上限。

以下均为未实施、未冻结提案，不用J选参数：

1. 保持现有原排序/全扫描：输出semantics最易解释，但须接受实际低batch覆盖与成本；不能冒充已完成核心joint-v2实验设计。
2. 冻结result-blind的old-binding及terminal-footprint多样性规则，并为size2/3/4保留有证书的结构种子。单纯old-binding round-robin仍可能让不同old争用同一target，因此需要terminal冲突覆盖检查；全部B1/B3/B4共用。
3. 冻结有限runtime scouting/physical-evaluation budget和明确canonical枚举顺序，记录未扫描空间、UNKNOWN与截断遗漏。K0 uncapped结构审计继续单独保留，不将其全扫描当runtime controller候选预算。具体budget不得凭最终性能决定，需新的成本/结构验收。

建议在HF_SEARCH中一起审阅2和3；它们改变candidate universe/覆盖规则，须独立科学overlay、tiny oracle coverage、deterministic及natural验收，**本轮没有自动实现**。不借审批删掉失败结果或用更有利的K。

共享批量执行器和控制器参数化实现继续保留；由于上述科学未决项，B4-v2总体工程PASS=false，正式preflight仍NOT_READY。等待集中冻结后才能进行完整K0/K1和正式生产配置验收；不启动P1-v2/P2/RL。
