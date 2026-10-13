# N4-P0 最小动态 K MPC 评分接缝：工程功能通过，成本 STOP

**本轮总体结论：STOP_COST_EXCESSIVE，尚不授予完整 N4-P0 Engineering PASS。** 新评分接缝的专项功能和冻结上游回归通过；完整决策 epoch 的成本验收未完成。没有启动六场景24次、敏感性矩阵、GNN、MADRL/MAPPO 或正式论文实验。正式科学七参数及正式周期/搜索预算继续 null。

## 新增实现与真实复用

新增 `runtime/n4_p0.py`：P0EvidenceBinding、CausalRootView/causal_view、ForecastInput ZERO/PERSIST、make_sanitized_root、SanitizedRoot clone/checkpoint/restore、PilotCost、score_action、retain_small_domain、score_candidates。接口详情见 [N4_P0_INTERFACE_CN.md](../../contracts/N4_P0_INTERFACE_CN.md)。不创建第二套物理执行器、流体调度器或 FIFO；旧 B4 不调用。生产 src、历史 Gate、原 N1a/N1b/N2/N3、0001–0009、旧预实验草案原文件均保持原字节。

完整真实历史注入前缀来自原 ObservedD2Engine 观察日志。复制时替换真 trace、外生未来边界和含旧源 hash 的缓存；预测率须严格等于当前 ZERO/PERSIST 定义。保留 Q/I/A/D、已发送传播、原始 cohort 时间、能耗/年龄游标以及已承诺 setup/TX/到期。N3 原观察不完备，新只读视图补充已承诺内部状态；隔离是可达数据/闭包意义的因果隔离，不是防恶意 Python 读取文件或进程内省的安全沙箱。

## 解析、隔离与回归

完整专项19项通过；随后仅加入4条当前率入口拒绝语句，其余 runtime AST 完全相同，针对性复验5项通过，覆盖20个唯一用例、24次通过执行。完整报告、入口变更证明、源码快照及首轮失败均保留。首轮16项中3个失败来自新测试对 LocalFIFO 的对象地址比较；改为完整值序列化比较，没有改业务、容差、FIFO 或历史测试。

已通过：不同真未来的因果双生同根/同分支得分、候选顺序反转、history/连续 FIFO 保持、ZERO 积压保留、PERSIST 不读未来、未来读取/复制 poison、外来 trace 和手工未来率拒绝、真实 ADD/DROP/BBM/MBB、TX DRAINING/传播/setup/到期、clone/checkpoint/replay、多跳与非网格连续注入、部分交付条件年龄恒等式、无交付均值 null。

HOLD/ADD/DROP/BBM/MBB 与独立从零使用预测 trace 的真实推进进行逐字段比较：D2 原业务状态、全部 cohort 分布和 FIFO 账本、能耗账本与测量字段均比较，不用宽容差代替值比较。外生边界游标的等价表示及审计初态 hash 单独解释。真实160星新评分集成仅完成一个 PERSIST HOLD 分支；不得声称完成新真实160星多动作决策 epoch。

解析例：h=6 全 IDLE E=9600 J；已有双端 ACTIVE E=10080 J；空闲双端 ADD，真实 t+1 ACTIVE 后保持到 t+6，DeltaE=470 J；已有 TX 导致两端 DRAINING 在 t=3–5 的六秒分支增量160 J。T=30 全 IDLE 48000 J 是公式验算，不假称本轮另执行了完整30秒评分运行。真实结果沿用 N1b 的条件 IEEE 调和界，不标为硬件或任意实数解析精确。

冻结回归实际结果：N1a 25/25、N1b 24/24、N2 27/27、N3 20/20；N3 本轮实际执行完整2742窗口诊断和既有160星多epoch重放。历史131/132，唯一旧F3 `test_known_witness_domain_discovers_every_registered_size_without_J` 的完整失败 traceback 与既有证据相同，新增失败0。版本保护32项通过。上述上游回归不冒充新 MPC 预实验。

## 实际成本与停止证据

测试环境使用现有 Conda pytorch。成本进程单 worker、真实160星、完整登记 catalog、T=30/TA=20/H=6、t=3 当前根、双端 .5 s retarget + .5 s acquisition、PERSIST；lambda_N=6 s、lambda_E=1000 bit·s/J。完成一个独立 HOLD 分支后启动一个完整 catalog epoch，随后因成本明显过高按用户 STOP 条款终止。没有裁减物理宇宙、关验证、加 worker 或追加测量。

|已完成阶段|实测墙钟 s|
|---|---:|
|历史前缀净化及完整根克隆|6.729693|
|一个六秒 HOLD 分支的克隆、提交、推进和评分|31.356397|

分支互斥分类时间，含 Python profile 开销；避免与外层粗计时重复相加：

```json
{
  "binding_and_hash": 26.37400460000051,
  "fifo_age": 1.2064480000000088,
  "network_service": 0.2736349000000118,
  "other_stage_work": 3.222078699999969,
  "terminal_energy": 0.2802298999999948
}
```

原 `standalone_branch_cost.json` 另有 branch_clone、explicit_binding_hash、n2_submit、advance_network_fifo_energy、energy_cost_evidence 的粗阶段时间。粗阶段包含嵌套调用，不能和互斥分类再相加。已完成分支指标及计算量：

```json
{
  "J_h_bit_s": 187306.60287934053,
  "N_end_bits": 31217.767146556987,
  "DeltaE_h_J": 480.0,
  "cost_bit_s": 854613.2057586825,
  "cohort_count": 20,
  "service_observation_count": 7,
  "terminal_event_count": 0
}
```

真实已交付年龄状态为 `IEEE_RECONCILIATION_BOUNDED_NOT_ANALYTIC_EXACT`，具体分数、误差界、驻留、K(t)、320终端及实际动作回执随嵌套结果保存。没有真实控制器配对性能结论。

中止时：进程累计 CPU **2208.984375 s**，进程从启动到中止墙钟 **2281.763567 s**，峰值工作集 **105111552 byte**。该进程时间包含 fixture 构造与已完成分支，不能冒充完整 epoch 或精确候选阶段耗时；内存为 Windows 进程高水位，不能声称单个 clone 的独立峰值。中止命令先核验 PID 的实际 command_line 指向本次 cost/独立 manifest hash，再终止，证据在 `cost_stop_process_evidence.json`。

**完整 epoch 的候选合法计数、阶段分解、所选动作、评分子集和分支数未获得，记录为 null/未完成。** 不根据理论预算或旧 N3/B4 填充。完整成本验收因此未通过；本轮不再尝试补测。三秒为模拟决策周期，本次仪器化单分支已远超三秒，不证明无采样开销的速度；也不声称实时性满足。

## 优化与下一步建议，仅设计

已完成分支中绑定/hash 是主要实测开销；未完成完整枚举不能臆造其净时间分布。源码另显示 Gate B snapshot/_log 对全部320终端反复 asdict。事务克隆本来就共享只读历史，不能错误归因为递归复制全部日志。优化建议见 [N4_P0_EXACT_COST_OPTIMIZATION_PROPOSAL_CN.md](../../contracts/N4_P0_EXACT_COST_OPTIMIZATION_PROPOSAL_CN.md)：明确不可变依赖验证接缝、同根纯几何/事务复用、逐字段等价的只读快照记录。仅 mtime/size 或前后相同 hash 不足以证明期间未变化。若需要改冻结内核，先 STOP，不实施。

Current-State Greedy 建议已提交、未实现：共享当前候选域，依据当前队列/率、路由瓶颈容量压力和即时路径改善作确定性排序，不做 H 秒多步 rollout，与原 N3 可达性规则分开命名。参数和代理须另授权，不冻结新科学阈值。

**不建议现在授权24次配对预实验。** 建议先审核成本 STOP、授权最小等价优化/低开销采样设计，再完成缺失的完整 epoch 成本验收；不自动开展新测量或新基线。

## 三秒人工修订与版本封存

四份新审阅副本位于 `pilot_review_3s/`，原一秒草案完整快照与各自 SHA 在 `prior_pilot_drafts_1s/`、`prior_pilot_draft_hashes.json`，原文件未覆盖。三秒 epoch=0,3,6,9,12,15,18,21,24,27；所有控制器同时间表；真实业务 t8/t10/t20 与传播/终端事件不对齐决策网格。t0–24 有效h=6，t27有效h=3，预测不越T。主理论840分支/4788 branch-s；额外单因素敏感性理论1680分支/9576 branch-s，均未授权执行。

本轮只新增独立版本资产，连续修订0010记录功能通过与成本STOP，不覆盖任何历史。完整原字节封存前审计见 `preseal_change_audit.json`；完整修订独立SHA及封存后全文件验证在本轮工具输出和最终交付中提供。版本完整性PASS不等于本轮成本或科学Gate PASS。完成封存后停止等待审核。
