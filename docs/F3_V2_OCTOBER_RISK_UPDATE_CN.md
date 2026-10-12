# F3-v2 10月关键路径风险更新

状态：ENGINEERING_EVIDENCE_UPDATE；科学合同和42-run矩阵仍为DRAFT_NOT_FROZEN。此文件补充既有October四份计划，不改其内容、矩阵或预算，不读取正式控制器性能作参数选择。

## 已有证据与适用边界

160星、原SGP4/WGS72/TEME、16 OD、K4工程fixture完成t=0/2/4/6/8/10的serial与persistent 8-worker逐分支/逐checkpoint/自然状态链精确对照；共6 epoch、每epoch9个分支。使用受限结构fixture候选和2 s测试步长，属于兼容性工程检查，**不是正式K*、主5 s周期、完整production pool的验收或性能证据**。原始记录见 [natural prefix](../outputs/f3_v2_natural_prefix_20261008T142126_443971Z/report.json)。

该检查总墙钟2004.986 s，包括两个模式和两次proposer/commit/advance及精确审计开销。8-worker observe单epoch49.471–72.032 s；serial176.853–245.485 s。必须按各mode总observe时间求相应speedup，不能把整次equivalence检查墙钟当一个正式episode的费用。冻结前预算仍缺K* candidate source、main-size safety、不同业务阶段、最大候选池、推进及证据开销，不据9分支线性外推33分支或42-run总量。

一次只读内存快照显示parent+8workers共9进程，group RSS约1.327 GiB；可用RAM约9.954 GiB。各进程历史峰值之和不是同时峰值，此测量也不是正式主规模峰值保证。证据见 [memory snapshot](../outputs/f3_v2_natural_memory_probe_20261008T142759_950053Z/memory_report.json)。前次匹配包含PowerShell而重复计算的快照保留并明确不可用，不择优报告。

## Critical-path blockers

|对象|实测/结构发现|对里程碑的影响|处置边界|
|---|---|---|---|
|CP_K_COST|t0/K24、t270/K48、t570/K80三个预声明probe完成：inventory 48–59 s，matching 0.46–0.71 s；先前60 s超时证据保留|实际K* occupied-state source、全部20点及整episode费用仍未知；Oct11须报告|三点费用不代替完整预算，不填未测项、不把timeout UNKNOWN当无合格K|
|CP_K_CERT|三点新增解析界exact证书0.016–0.020 s，独立验收PASS；原bounded reference仍UNKNOWN|推进了求解路线，但全部K×20与正式K0/K1尚未完成|解析界不可达/预算耗尽仍UNKNOWN；不以成本点选择K*|
|CP_POOL_COVERAGE|Oct9真实K4/t0：7596→64→16，singleton全替换同一old，最终无size2/3/4；同时存在真实安全四链witness|已确认一个自然场景的联合搜索覆盖退化；不能宣布joint-v2整体ready|HF_SEARCH明确old/terminal-footprint多样性和coverage；不按J选规则、不自动改变K硬门槛|
|CP_RUNTIME_SOURCE|history-free exact physical trial前缀2.619×后，全K4 source仍455.081 s，proposer7.683 s|单点source已超过零开销平均规划上限，Oct11前必须解决runtime有界scouting及预算；月底风险HIGH|新计算/覆盖规则需科学审批；无全episode预测，不以prefix提速宣布42-run可行|
|CP_PRODUCTION_ACCEPTANCE|自然K4、小池6epoch已exact；K*、正式搜索预算和全部周期/业务状态未验|不能把该工程PASS提升为B4-v2总体PASS|获批K1与共享pool后做真实生产配置的新验收|
|CP_RESOURCE|42项预算未实测齐，机器可用窗口未人工确认|当前无法可靠给出最早/保守实验完成日期；10月31日风险HIGH|每项预算填齐后准入；超出窗口立即申请资源/日程或性能运行前预注册范围调整|

## 里程碑保持，完成标准不降低

10月11日：集中科学审批包、结构solver/coverage风险与成本分层；10月16日：获批K0/K1和batch安全；10月20日：主算法核心；10月23日：生产equivalence、tiny oracle、全回归、完整预算/preflight；10月24–29日：单独人工授权后全部42项；10月30–31日：审计、图表和证据封存。

若Oct16的K0/K1或candidate-policy前提未完成，应当即报告依赖如何推迟Oct20/23/24；现阶段无可靠剩余工期实测，不编造某日一定完成。旧18–29人日从零估计不是现有实现之后的剩余工期。最先保护核心B4-B3公平对比和所有正确性验收；原计划中的非核心减项仍仅为人工审批备选，未实施。CENSORED/无优势/失败结果不得删掉或用截断J排名。

当前可连续实施：隔离fixture测试、共享runner/evidence工具、结构/费用诊断与报告。正式冻结、K*选择、生产性能矩阵启动均未授权。集中审阅入口：[审批清单](F3_V2_HUMAN_FREEZE_CHECKLIST_CN.md)。

新增审批输入：[结构证书、真实tiny B3评分和图表接口结果](F3_V2_ENGINEERING_SOLVER_AND_SCORING_RESULT_CN.md)。评分检查确实出现短寿命成员压低整个batch评分；不按该结果修改公式。42-run审阅manifest已生成，K*与预算留空，正式实验条件仍不足。无法给出可靠延期天数；当测得完整费用超出已确认机器窗口时必须立即报告，而非到10月底再解释。

Oct9：[自然source完整结构与成本结果](F3_V2_NATURAL_SOURCE_COVERAGE_RESULT_CN.md)。原300 s UNKNOWN保留，未把partial raw当source；新完整7980验证不读traffic/Q/J，live与资产hash不变。source prefix与physical clone/capped-pool工程等价不能替代K*正式多epoch B4验收。核心风险从“仅怀疑raw退化”升级为“自然K4实证退化”，但不外推到所有K或按该结论选更好K。
