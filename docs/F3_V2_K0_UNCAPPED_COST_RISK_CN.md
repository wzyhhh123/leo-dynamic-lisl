# 完整K0的uncapped验证成本风险

状态：**STRUCTURAL_OPERATION_COUNT_DIAGNOSTIC_NOT_RUNTIME_FORECAST**。本轮只读原窗口采样计数、K列表、当前source/snapshot循环及旧费用记录；没有matching、topology构造、全量inventory、控制器或正式实验。

结果：[操作数报告](../outputs/f3_v2_k0_work_count_diagnostic_20261008T191943_532953Z/report.json)。条件是某个K/t点得到EXACT可行拓扑，并按当前未冻结的独立预建立约定构成K个eligible ACTIVE binding，无draining/reservation，而且每个old binding对应一个当前terminal-pair窗口。当前uncapped source遍历每old×全部当前跨轨终端窗口，exact old==new跳过一次，其余调用真实physical validator，因此该点调用数为 `K*(W(t)-1)`。

这个关系在已存自然K4/t0费用证据上得到校验：`4*(1996-1)=7980`，与真实验证次数完全一致。它不把setup不合格候选免费删掉：其不合格本身由原物理验证得到，仍有成本。

原12个K为4/8/16/24/32/40/48/64/80/96/120/160，20个采样点、两次replay不变。**若这些点全部为EXACT可行并进行完整uncapped库存验证，条件总调用数为55,077,664。** 实际上高K可能不可行、某些solver可能UNKNOWN，不能把这个假设当作已知可行域或实际运行数量。UNKNOWN/超时停止更不能视为完整审计完成。

将旧K4 validator的历史平均0.05691699s机械乘上该数量，得到870.793小时的计数缩放。这既不是新状态实测，也不是runtime上界或完整K0预计工期；高occupancy可能改变reject路径和单次费用。该诊断只表明需要尽早测量有代表性的occupied-root uncapped验证，而不是只测idle inventory/matching/builder。额外的idle库存、matching/lex构造、joint diagnostics、独立证明/库存复核与I/O还未计入。

新风险编号：**CP_K_UNCAPPED_COST**。建议在10月11日前集中审批结构成本探测范围和单次工程预算；预先指定K/t、访问identity和停止规则，只测原validator费用、reject原因与结构计数，不读J或traffic收益。完整480记录是否可完成须在实测后重新准入，不能把部分prefix当完整inventory或通过删K/删snapshot满足日期。

可以审阅语义严格保持的工程方案，如验证已知不可能条件是否能以完全相同的reject reason提前检查、重用确实与K无关的idle库存计算，以及等价的结构验证调度；这些仍需单独证明状态/时间/事件/结果与原路径完全一致。本轮没有实现任何方案，不能用future optimization假设填入预算。

runtime控制器的bounded scouting和K0的uncapped结构审计是不同合同。[HF_SEARCH草案](F3_V2_SEARCH_POLICY_APPROVAL_DRAFT_CN.md)的256 visit建议只用于runtime，不能复制到K0、删去真实候选或声称全域无合法动作。原K0阈值、K列表、历史证据和F3-v1均未修改。此诊断没有选择K*，也没有改变10月31日目标或正确性标准。
