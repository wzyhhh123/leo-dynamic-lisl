# N4-P0R 精确等价成本优化与受控复测结果

结论：**STOP_EXISTING_CONSERVATION_BOUNDARY。N4-P0R 完整 Engineering PASS 未获得，N4-P0 完整 Engineering PASS 仍未获得。暂不建议恢复完整单 epoch 验收。** 读取接缝本身的正确性与等价测试通过；真实小域 PERSIST/ADD 揭示原实现已有的严格守恒拒绝。未修改冻结内核、旧合同、修订 0001–0010、历史结果或旧测试预期；未放宽数值条件。

## 实现与实际调用链

新增 `runtime/n4_p0r_reader.py` 路径锁定原型与 `runtime/n4_p0r_handle_reader.py` 最终 HandleReaderLease；接口为上下文管理及 `lease.guard(original_binding)`，返回原类新对象。最小用法：取得完整依赖/路径句柄 → 原始完整校验 → 在原 N1a/N1b/N2/P0 对象上明确绑定新校验入口 → 直接调用原 make_sanitized_root/score_action/score_candidates → 关闭上下文失效。没有第二套物理状态机、网络服务、FIFO 或评分公式。

没有缓存正向验证、内容或 SHA。最终接缝每次从锁定句柄完整读取原字节，验证身份、前后元数据并重新 SHA-256；只减少重复路径遍历、重新打开文件、Path.stat 及验证器重复装载。Windows WRITE/DELETE 分享限制、非 reparse 祖先保护、关闭失效、已有 writer/本机 writable mapping 拒绝在独立测试副本验证。未实现任何 SGP4/LOS/FoR、事务或状态结果缓存。句柄只在同一上下文内复用，不提供跨进程序列化能力。

原真实 HOLD 分支实际调用 N1a/N1b/N2/P0 不可变依赖 verify 7/11/8/1 次，共 27 次；原始字节读取/哈希 **3114 次，156 个不同文件，40461106 字节**。优化后次数及字节量完全相同，与原生读取计数器闭合。root 另读取 475 次 / 7247700 字节。5 次 N2 动态 `_verify` 与 5 次物理输入摘要仍执行；状态/证据 SHA、资源和窗口校验也保留。调用链、逐文件次数/字节/SHA、各文件类别及原方法/适配 AST 见 actual_binding_callchain_*、immutable_dependency_actual_leaf_counts、paired_* 和 cost_callchain_findings。

原分支 JSON dumps/loads 为 25/54 次，分别序列化 15942322 / 解析 636060 字符。原仪器化 19556075 个 profiler callback，优化后仍有 17732403 个。原观测中 N1a 的委托 raw_info 返回曾被重复计数；原报告原样保留，paired_trace_native_counter_reconciliation 独立剔除该包装返回并与真正读取次数、字节量完全闭合，未改动任何时间数据。

## 串行配对成本（同一 160 星 t=3 PERSIST/HOLD）

| 测量 | 原净化 root / s | 新 root / s | 原 HOLD 分支 / s | 新分支 / s |
|---|---:|---:|---:|---:|
| 不带 profiler | 3.769700 | 0.432691 | 20.805871 | 1.510073 |
| 调用链 profiler | 8.713216 | 5.897828 | 35.596686 | 13.940364 |

两版及两种仪器化方式的结果逐字段完全相同，只排除 `timings`。原始根和分支不是新完整 epoch 的总耗时。读取上下文构建（原始全量校验及路径准备）6.032251s，锁获取和锁后原始全校验 3.898404s；新增实现绑定检查 0.140833s，全部冷启动单独计入，不隐藏为热分支成本。

仪器化原/新路径检查 11.701615/0.399270s，原始文件 I/O、元数据与 SHA 10.798076/0.914184s；动态检查 3.382951/3.474745s，FIFO 2.587844/2.367077s，网络 0.444345/0.479196s，能耗 0.400057/0.381984s。以上为含 callback 开销的互斥区段，不能当成不带 profiler 的分类耗时，更不能把原 binding/hash 全部归因于 SHA 运算。原 score_action 还保留 clone、真实提交、推进及能耗/代价证据的粗计时。

独立 HOLD 预测 h=6s：J_h=187306.60287934053 bit·s，N_end=31217.767146556987 bit，E_h=10080J，DeltaE_h=480J，代价 854613.2057586825 bit·s。手算：318×5×6 + 2×45×6=10080J；相对 320×5×6=9600J 的增量为480J。7 条服务观察、20 个结束 cohort、0 个新增终端事件。预测结束 t9 不等于全 T30 评价完成。

已保存测量期间进程峰值工作集 **137199616 字节**，峰值提交 125673472 字节。Windows 数值为进程生命周期高水位，含 fixture、前序配对/profiler及 ZERO 五分支；不是各分支可重置的独立峰值。诊断复现和最终 20MB 状态证据序列化不属于这次成本计时。3 秒仿真 cadence 不代表 3 秒墙钟实时性保证。

## 小域、停止证据与 catalog 边界

完整输入 catalog 为2742行，五个显式候选 HOLD/ADD/DROP/BBM/MBB 逐个经过原 N2物理检查。ZERO 五分支完成，共30 branch-s，墙钟 15.778782s；仅该五动作域的选择为 DROP，未把它提交到真实 live。PERSIST 按原排序首先评估 ADD，在 t6 首个预测检查点被拒绝，剩余四项未继续评估，整个 PERSIST 小域选择为 null。

拒绝输入：A=3600000.0bit，D=3598758.711573384bit，Q+I=1241.2884277067496bit。顺序 A-D-N 的残差为 -1.0905205272138119e-06bit；验收函数实际浮点表达式 A-(D+N) 的残差为 -1.0905787348747253e-06bit，均超过固定1e-6bit。原版和新读取器的拒绝测量、可序列化状态、FIFO观察及能耗状态完全相同。原 D2实际 abs_tol=0.001、rel_tol=1e-12、state_tol=1e-6；目前仅确认层间容差边界不同，尚未锁定具体哪次舍入/闭合产生残差。失败前能耗记录不被当作通过验收的完整预测结果。

原初诊断正确捕获相同拒绝输入，但额外日志不能直接序列化 native Satrec，产生二次观察器错误；两份尝试原样保留。attempt02 只排除 delay/native model 和 router 实现对象，保留物理输入 SHA及全部业务/观察/能耗数据，再次得到相同 BUSINESS_CONSERVATION_MISMATCH，未改变服务与容差。

成本执行到此 STOP。**新的完整 catalog 枚举/SGP4/事务/320终端快照成本诊断没有启动**；完整合法数、全域选择和完整 epoch 成本均 null，完整 epoch 数为0。不能用历史2742行证据或五个合法动作冒称本轮全 catalog 覆盖。后续可能的重复计算调用链已在原代码中可读，但本轮没有新的枚举耗时和重复几何测量，不能据函数名推定瓶颈。

## 测试、保护及后续条件

最终20项 N4-P0专项全跑PASS，包含入口拒绝、未来源隔离、ZERO/PERSIST、HOLD/ADD/DROP/BBM/MBB、连续FIFO、部分服务、状态/能耗、候选顺序、clone/checkpoint/restore/replay。原评分器最终20项也完整PASS；最终reader8项PASS；6类动作原/新全部字段精确等价。N1a/N1b/N2/N3为25/24/27/20 PASS。N3 catalog回归执行冻结测试自带的独立历史证据复核分支，并验证全部记录映射及源码/输入绑定，不是新的完整物理扫描。历史132项131PASS，原旧F3失败及traceback完全相同，未改测试。版本保护32项PASS。

真实新增PERSIST/ADD不是通过项，已作为两版都复现的原有模型边界登记；不能把“已知套件无新回归”换成完整N4-P0 PASS。最小后续方案见 MINIMAL_NEXT_STEP_CN.md；先解释数值闭合，任何必要内核改动另行授权，不能增加容差、清除cohort或伪造业务。

前置用独立起点 ce3fe1df…及0010 fa9564ca…核验6023受保护文件、5810旧基线文件及完整父链PASS。封存前将再次全量核对原始字节，所有新增/修改/删除都进入0011；本轮预期仅新增，旧资产和旧版本文件修改/删除均0。封存记录不自引用，最终独立0011 SHA及封存后完整校验结果由交付工具输出确认，不能以哈希PASS替代科学或工程Gate。

PILOT_ONLY T30/TA20/H6/cadence3/setup1/单原子动作及lambda6/1000保持；正式T_A、T、tau_res、R_min、alpha、D_ref、E_ref及正式周期/搜索预算均null。未运行24次主预实验、840分支矩阵、敏感性、GNN或MAPPO。Gate B TX与D2在途业务分离、右删失窗口、分段传播/FIFO及数值误差界仍是原模型解释边界，本轮不改写。完成后停止等待审核。
