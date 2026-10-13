# 0018：N4-P0H Gate C结构复制接缝限定工程结果

结论：**PASS_LIMITED_P0H_GATE_C_ENGINEERING_ONLY**。本次有限根接缝的精确等价、共享/回滚/拒绝、生命周期/能耗、受控成本和冻结上游回归通过。小样本热检查观察到约1.16倍改善；冷安装后此批样本无净收益。**完整N4-P0 Engineering PASS仍未获得**，不预测完整catalog能否进入300秒，不宣称3秒实时性，不继续FIFO优化或预实验。

## 保护与实现

开始前用独立版本起点ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691、0017锚e9554ecfd9a256dc766ac65ea1757e07d4eab00d6addb4b9a896d09154b5b22c核验完整父链与6478登记文件PASS。5810个旧基线文件、202排除项，无未登记漂移。全部Gate C、N1a/N1b/N2/N3、P0、0015时钟、历史合同与预期原始字节保持不变。

最终入口为runtime/n4_p0h_gate_c_final.py：SourceBinding绑定源文件；SealedHistory冻结原日志的native tuple/scalar数据树；StructuralCatalog.connect_command保留原窗口、Connect、trial.submit、ready提取、epsilon及返回语义，只改变复制策略并加入历史/源完整性保护；install(controller,binding)显式选择接缝。source binding可由冻结0011 HandleReaderLease适配，仍每次完整fresh SHA，无正向验证缓存。

Gate C试事务的当前320终端、links/tx_end、预约、agenda列表及日志列表独立。仅原始不可变值树共享，**视图对象不跨预演共享**。原日志不改写；预演前后重新核对其精确规范编码。普通容器写入拒绝，dict/list基类修改接口不能写入该Mapping/Sequence值视图；封存描述符也禁止普通属性替换。Python恶意进程内存任意改写不构成安全沙箱承诺。

N2原ActionValidator、外层试事务与Atomic.submit动态验证、trial/live快照及实际释放集合核对全部继续执行；没有连接结果、几何结果或候选缓存。FIFO、能耗、事件时序及MPC公式未改。内部只读值视图身份与旧类型不同，不宣称内部typed graph类型完全相同；对外输出、完整原日志内容、终端状态及状态哈希逐字段相同。

lease仅限一个明确根：源历史变化会拒绝，下一epoch需显式重新绑定。没有自动接入冻结N3多epoch控制器。这是本轮限定接缝验收边界，不能直接作为全部MPC闭环已集成的证据。

## 正确性、拒绝与共享审计

最终22个合成case与7个实际160星case，原/优化逐字段及SHA一致。HOLD/ADD/DROP/BBM/MBB、两个终端对和重复对、有/无合法候选、占用、未来预约、DRAINING、stale引用、MBB资源不足、setup非法、窗口失效、ready==end、剩余寿命≤1e-9及略大于阈值、未登记clone字段均覆盖。

另7个拒绝case覆盖未声明第三方释放、重复释放引用、未知REPLACE模式与LOS/双端FoR失败；该部分固定物理拒绝为明确合成fixture，实际160星用真实SGP4和登记目录。

5种真实原子动作原/优化各在t=3提交，回执、last_result、canonical状态、终端日志及SHA相同，没有推进真实6秒预测。当前mutable state、link.tx_end、未来Reservation对象、agenda与log列表独立；4种普通历史修改被拒绝，源历史篡改被检测。故意构造第一条Disconnect成功、第二条Connect失败的批事务，原/优化均按原原因拒绝且snapshot/log精确回滚。原N1a历史指纹拒绝仍生效。自有TEST_ONLY输入和manifest SHA篡改也拒绝，未动冻结源文件。

ADD/BBM/MBB的成功与setup abort六个案例在隔离Gate B执行器推进至4.25s，终端事件/日志及原N1a能耗逐字段相同；没有推进网络预测分支。依据文件：CORRECTNESS_ACCEPTANCE_TUPLE、SYNTHETIC_EQUIVALENCE_TUPLE、REAL160_EQUIVALENCE_TUPLE、REJECTION_COVERAGE_TUPLE、ROLLBACK_AND_TAMPER_FINAL、TERMINAL_LIFECYCLE_ENERGY_TUPLE。

## 成本与最小差异

原有限诊断证实重复工作：一个合法ADD原Gate C递归复制约1MB历史（8日志、2560历史终端行），再执行内层事务；N2再作独立事务。原/最终均有8次320终端新日志快照和2564次dataclass asdict，未减少拒绝/日志证据或实体状态规模。

最终7类动作各3次的无profiler检查总时长1.0886212→0.9397696s（约13.68%缩短）。0.2540131s冷克隆/安装加入后1.1937827s，超过原检查总时长；源句柄获取未独立单列，不能声称完整冷启动净收益。各动作分布和独立分项/对象计数见COST_BREAKDOWN_CN.md与PAIRED_COST_TUPLE、DISJOINT_STAGE_PROFILE。

仪器化开销很大：独立ADD分项观察总1.11979→0.62881s只是profiler下的数据，不能当生产加速。两次较慢尝试（2.135s、1.138s优化组）原样保留，最终只采纳tuple实现；没有修改旧结果来制造PASS。早期CLONE标签混合Gate C/N2的分类在另一次仅两条检查中纠正，原数据未覆盖。补充脚本一次缩进SyntaxError发生在执行前，原错误记录保留，仅修正新未封存辅助代码。

MINIMAL_CONNECT_DIFF.patch展示原/最终connect_command差异；SHARING_AUDIT.json描述共享边界。旧尝试源码由gate_c_attempt01.py.snapshot和ATTEMPT01_SOURCE_PROVENANCE保存，第一份源manifest指向当时的源码SHA；其旧运行时路径在本轮未封存开发中调整，最终有效绑定是SEAM_SOURCE_MANIFEST_TUPLE和SEAM_BINDING_TUPLE，旧manifest只作为历史尝试证据，不作为当前入口。

## 回归与封存

冻结原实现116、0015时钟变体116项全部通过，额外内联1、事件/1bit真实丢失负向7项通过。历史132项中131通过，原F3覆盖失败1项保留；无新增失败。原测试源和预期未改。新接缝以单根限定案例独立验证，未暗中替换冻结N3的多epoch执行器。原P0小fixture预测属于回归，不是本轮真实160星MPC成本分支或主实验。

所有正式科学/控制参数继续null，1e-6 bit阈值不变。完整目录只加载/绑定，没有重新执行2742行物理合法性枚举；没有真实6秒预测分支、完整epoch、24次预实验、敏感性、GNN或MAPPO。阶段测量为固定7类/3次代表性样本，单轮120s工程上限未触发，不是论文时限或动作预算。

封存前全文件raw-byte核对拒绝旧资产修改、删除、重命名和新增越界；追加0018后以独立SHA及起点再次完整验证。完整性结果不等于科学验收。完成后停止等待人工审核，后续整epoch、完整候选诊断与FIFO工作均需另行授权。
