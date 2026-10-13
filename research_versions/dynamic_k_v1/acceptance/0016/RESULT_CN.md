# 0016：MPC单决策epoch恢复验收结果

结论：**STOP_CATALOG_300S_HARD_LIMIT**。指定小候选域Engineering PASS；完整合法目录枚举未结束，单epoch未运行，完整N4-P0 Engineering PASS仍未获得。正式科学参数保持null，未运行24次预实验、840分支矩阵、敏感性实验或学习算法。

0015独立父锚为a5c427c4225bbd4850c3979079b18d68afa92d64cdffe1f90025904537ac7318。开始前完整原始字节验证通过：6355个登记文件、5810个旧基线研究文件，202个排除项；版本起点、完整父链和冻结依赖通过。新t=3根与0015的LIVE_PRE_ACTION、SANITIZED_PRE_ACTION、ROOT完整类型状态逐字段相同；ROOT图哈希d28a8160b748e31b5f924bbbf74f7de0c0e1de1c3f9938a4362920d3822f1764。这里复用的是0015隔离修复语义的新场景，未声称恢复0011原始根。

## 真实小域评分

PERSIST和ZERO各5个动作全部先经N2合法性检查，再提交真实HOLD/ADD/DROP/BBM/MBB执行并推进t=3→9。未跳过经济上不利的动作。评分直接调用冻结n4_p0.score_action，网络、FIFO、能耗直接复用N1a/N1b/N2，所有分支使用P0F_EXACT_NOMINAL_V1。0011 HandleReaderLease保持不可变输入绑定，动态合法性及最终提交检查照常执行。

完整数值、实际回执/释放集合、状态检查、误差界及事件账本见small目录和FINAL_DIAGNOSTIC_EVIDENCE.json；汇总表见SMALL_DOMAIN_RESULTS_CN.md。代价为J_h+6N_end+1000DeltaE_h，HOLD=854613.2057586825、ADD=995518.0708517093 bit·s，与0015原始字段和公式严格一致。指定小域PERSIST排序MBB→HOLD→ADD→BBM→DROP，ZERO排序DROP→HOLD→BBM→MBB→ADD；这不是完整目录的最终epoch选择。

PERSIST/BBM完成评分耗时1100.5151s，未达到人工追加的1800s分支上限，监控未终止该分支。五个PERSIST评分总耗时1159.0092148s。只读采样显示时间主要消耗在精确FIFO连续流片段处理，且记录区间持续前进；没有证实事件时钟停滞。该成本边界及后续仅供审核的优化方向见FIFO_COST_BOUNDARY_CN.md。

## 完整物理目录诊断与STOP

加载完整已登记2742行物理目录，t=3、160星筛选后的当前窗口1996个。原始行数和窗口数均不是合法动作数量。调用冻结CandidateSource.generate时retention_budgets=None，没有提前裁剪合法集合。

实际墙钟300.0830555s时外部监控终止枚举进程；300s是授权上限，0.083s为监控轮询延迟。正在进行的不可分调用被中断，其未完成结果没有计入。完成2598次合法性检查，部分统计如下：

|种类|完成检查|其中合法|
|---|---:|---:|
|HOLD|1|1|
|ADD|1996|1965|
|DROP|1|1|
|REPLACE|600|599|
|合计|2598|2566|

部分拒绝：ADD_WOULD_IMPLICITLY_RELEASE 31次、DUPLICATE_LINK 1次。REPLACE路径未完成，完整合法集合、完整合法数、最终保留/截断数均为null。上述2566仅为已完成前缀的合法动作数。未创建EPOCH_SUBSET，未运行最终ZERO/PERSIST epoch，未生成最终所选动作。

最后完整阶段快照为第2500次检查、墙钟288.544831s：物理窗口/双端验证独占192.1205672s，LOS/FoR独占2.7652716s，SGP4原生独占0.8373567s，绑定/根物理核对0.1124807s，目录窗口查询0.0030412s。阶段值为轻量实例计时、含包装开销；生成/事务及尚在栈上的调用没有完整结算，不能据此补出300秒的完整分解或估算完整目录总耗时。全部前缀逐动作原始记录保存在CATALOG_VALIDATION_PREFIX.jsonl，最终硬停止证据在CATALOG_HARD_STOP.json。

目录进程只读内存快照：峰值工作集352481280 bytes，峰值页内存341590016 bytes；小域进程峰值工作集353099776 bytes。它们是进程生命周期高水位，含根构造，非独立分支重置峰值。没有伪造终止瞬间峰值或完整目录事件数。

## 仪器化与回归

不修改对象字段的只读CPython profiler配对HOLD：非仪器化1.7483777s、仪器化27.0437250s，差25.2953473s，7287604个回调。所有相同序列化层次的非timings输出、最终状态哈希及状态检查严格相同。该profiler开销不能代替目录轻量包装的开销；没有重复执行完整无仪器化目录来推算成本。

新辅助代码产生的绑定路径错误、冻结对象包装错误、辅助方法字段进入哈希及native tuple/JSON list比较错误都保留原证据；修正只涉及0016未封存验收辅助器。没有改动测试预期、评分公式或数值容差。ENV_AND_HELPER_AUDIT.json与SMALL_DOMAIN_RESULTS_CN.md解释各次失败及最终有效证据。

N1a/N1b/N2/N3/P0：旧语义116、新时钟变体116、额外内联构造1项均通过；事件时序和1bit真实丢失负向测试7项通过。历史132项中131通过，旧F3候选覆盖失败1项保留，未出现新增失败。旧F3为test_known_witness_domain_discovers_every_registered_size_without_J的coverage_by_size断言失败。全部原始测试输出在regressions目录。

## 保护、接口与下一步

新增接口均在acceptance/0016：epoch_workflow负责根重建和真实评分，profile_timing_check/complete_saved_timing负责只读计时及严格持久证据比较，catalog_epoch/catalog_supervisor负责完整枚举与300秒停止，assemble_diagnosis负责离线汇总。新增范围合同和PILOT_ONLY配置；生产运行时、0015及以前源码、合同、证据、修订记录不改。seal_stop.py为未使用的BBM超时封存入口，BBM按时完成后没有调用它。

封存前完整原始字节扫描检查所有旧登记资产；若有修改、删除、重命名或新增越界即拒绝封存。扫描记录preseal_change_audit.json与连续修订0016记录分别保存，manifest绑定全部新增文件和冻结依赖；修订记录不自引用。封存后使用独立计算的0016 SHA及原版本起点再次运行完整验证，最终结果由工具输出和交付摘要报告。

不建议直接启动24次配对预实验。若继续，需要另行授权完整候选枚举成本审计/精确优化（重点查看Gate C双端窗口及事务预演重复成本），以及BBM精确FIFO流片段成本审计。保持全部目录、拒绝原因、释放集合、连续年龄分布和原容差；本轮未实施这些优化，也未延长300s上限。3s仿真决策周期不代表墙钟实时能力。

当前停止等待人工审核；不自动恢复epoch或预实验。
