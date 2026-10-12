# F3-v2 一次性科学合同审批包

状态：**DRAFT_NOT_FROZEN / HUMAN_DECISION_PENDING**。本包是现有建议的汇总，没有新增实验、自动批准参数或授权正式运行。此前集中审批问题仍待回复，不重新逐项提问。

## 一次审阅的六组决定

|组|建议冻结的完整内容|替代方案及影响|
|---|---|---|
|HF_SCIENCE|160星；固定名义K；HOLD或每epoch最多4条资源独立REPLACE；主周期5秒；整批全transition STRICT_CONNECTED；B3 whole-graph snapshot×min(member eta)；B4真实joint rollout、H10、current-rate persistence、H_eff=min(10,600−t)；不递归控制|不同评分或预测规则需独立科学revision；不能拿旧单链工程PASS证明新规则。min eta的短寿命成员偏置已披露。K4对照也建议采用相同STRICT_CONNECTED，不沿用另一个三链Z_SPARSE的outage权限。|
|HF_K|原12个K、20点0:30:570、原occupancy band及结构门槛、18/20、min admissible K、600秒截断可用寿命；snapshot独立预建立，但所选每链须有原Gate C向前setup证书；batch兼容只作diagnostic|继承t=0拓扑并真实演化会改变审计问题，不能默默替代。原K0-v1.1仍保留DRAFT，正式冻结须新增合同。未知证书不能算满足门槛。|
|HF_SEARCH|具体政策RR_STRUCTURAL_SCOUT256_RAW64_SINGLE16_SEED4_V1：source visits/physical calls分别≤256；old/window轮转、footprint覆盖与结构种子；raw32/32/64；singleton16、8+8；W4；M32；seed与beam共享184 expansion/validation；HOLD在内最多33 rollout；batch1最多17|scout128/512为已提出替代；必须在正式结果前选定。原字典截断可保留作reference，但自然K4有单链退化。详尽规则必须连同其normative document和canonical hash审批，不能只批准数字256。|
|HF_B2|最小B1+minimum-hold；实际秒数、逐binding LINK_UP计龄；初始age0；H4/H8；threshold0|不同初始化或hold须先改草案；不按结果挑最佳值。不增加防抖之外的策略。|
|HF_MATRIX|已有42项完整ID及顺序；CORE/STABLE/SPARSE/FACTORIAL/HOLD/ROUTER；同权限B4−B3为主比较；固定opening figure；完整COMPLETE/CENSORED规则|不新增或删除实验。不用截断J排删失run，不作global ranking；任何缩减均需另行审批并说明科学覆盖损失。|
|HF_RESOURCE|一个B4 episode、persistent8 workers；机器时间提案6天×20h、20%余量、净96h；B4/其他暂分72h/24h|资源划拨不是实测耗时批准。最终K*/政策下的RAM、epoch、episode及逐run费用、超时仍待测并签认；24核不自动授权并行三个B4。|

上述为建议，当前approval状态均为PENDING。批准科学草案后才能实现并验收所选新搜索政策；冻结不等于工程PASS，不等于K*已选，也不等于正式运行授权。

## 审阅材料与已验证边界

- [具体候选政策](F3_V2_SEARCH_POLICY_APPROVAL_DRAFT_CN.md)：未实现；新科学输入政策，不能称为保持旧候选语义的runtime优化。
- [自然输入provenance](F3_V2_NATURAL_INPUT_PROVENANCE_CN.md)：77项静态检查通过，原0–600秒资产可用于20个结构采样点。该项已完成，不再列为缺失；occupied readiness仍必须执行原Gate B/C。
- [占用状态成本前缀](F3_V2_OCCUPIED_STRUCTURAL_COST_PREFIX_CN.md)：三个预声明点共192次真实验证，只涉及各点第一条old；不得外推完整K0或42项费用。
- [完整K0成本风险](F3_V2_K0_UNCAPPED_COST_RISK_CN.md)：全部K/t均可构造时，两replay条件调用数55,077,664。它是工作量诊断，不是实测费用预测。runtime256预算不适用于K0 uncapped审计。
- [现有工程进度](F3_V2_IMPLEMENTATION_PROGRESS.md)：当前代码194项focused、523项全仓回归通过；最终K*/5s/full pool自然serial8 gate仍未完成。
- [42项矩阵](../configs/F3_V2_PAPER_EXPERIMENT_MATRIX_DRAFT.json)与[月底关键路径](F3_V2_OCTOBER_CRITICAL_PATH.md)：原文件哈希与run次序不变。

机器可读汇总为 `configs/f3_v2_consolidated_human_review_DRAFT.json`，绑定全部源合同、政策、矩阵、当前代码封存及证据哈希。本包的静态一致性检查不运行控制器、matching或正式实验。

## 审批后的顺序与授权范围

1. 人工确认六组科学建议与所选scout预算；记录新合同canonical hash，不改历史文件。未选预算保持PENDING。
2. 按已批准政策继续隔离工程实现、tiny覆盖、共享pool公平性及成本测试。旧source/reference保持可审计。
3. 完整自然K0需另一个明确结构执行授权及计算预算；原12K×20点×2replay不删点、不因UNKNOWN或费用高自动取K。K*选择与K1按获批合同完成。
4. 最终自然serial/8-worker完整state chain、oracle、全回归、测量预算及42项manifest/preflight全部通过。
5. 人工对正式manifest hash及run ID序列另行授权后，才执行论文实验。不能把审批本包当作这一步的授权。

10月11日前的主要决定是HF_SEARCH/HF_K与资源路线。当前月底交付风险HIGH；最终episode费用UNKNOWN，没有可验证的延期天数估计。若计算上限仍无法闭合，须提交资源、工期或非核心范围修订，保留正确性标准与全部失败证据。
