# PILOT_ACCEPTANCE_CRITERIA

状态：PILOT_ONLY / PROPOSED_ACCEPTANCE / NOT_EXECUTED。日期：2026-10-12。本文件预定义后续工程接缝与探索运行的通过条件，不宣称本轮执行了测试。当前结论为 `DOCUMENT_AUDIT_COMPLETE / SCORER_IMPLEMENTATION_MISSING / PILOT_EXECUTION_STOP`。

## 授权分层与停止条件

本轮只有仓库外四份审阅文档、源码/版本只读检查和静态物理输入审计。没有新增修订、生产改动、仿真、预测分支、训练或参数搜索。正式科学参数保持 null。

后续先另行授权最小独立评分接缝及其工程验收；只有净化、解析、同动作等价和版本保护均通过，才申请六场景四臂短预实验。敏感性按预定单因素范围，不能演变为寻找最优阈值的大规模搜索。任何生产 frozen kernel 修改需求、无法解释的 Q/I/A/D 或 FIFO 冲突、真未来信息泄漏、绑定不匹配或超数值包络均立即 STOP，并保留原始失败和具体最小接缝证据。

## A. 版本与可执行性闸门

|检查|验收要求|
|---|---|
|版本起点/0007/当前完整链|使用独立锚逐项验证；不得只检查最新文件的自报哈希|
|N1a/b/N2/N3 绑定|原 manifest/冻结源与历史合同不变；0007 使用 attempt02 实施 manifest|
|新评分器身份|独立新版模块/测试/证据，连续新修订登记；不是旧 B4 或 f3_v2 更名|
|因果预测状态接缝|只读当前 setup/TX/已承诺传播/cohort，补足既有系统审计 G29；原 N3 observation 不宣称是精确 Markov 状态|
|正式科学配置|T_A/T/tau_res/R_min/alpha/D_ref/E_ref、正式周期/并行预算/搜索预算均 null|
|初态|160 星/320 终端、资源不变量、物理合法；U/C 分别验证，初始 Q/I 为 0，无未知年龄|
|物理输入|完整已登记 2742 窗口、160 固定环边、相同 TLE/hardware；候选合法性动态重新验证|
|时间设置|所有真实运行 T=30，TA=20，H≤6，epoch=0..29，setup 双端 .5 + acq .5；禁止暗调|
|工程成本|报告单 branch 和完整 epoch 计时/内存，区分模拟 1 s 周期与实际实时能力|

当前完成的是完整文件/版本绑定 PASS 和静态指定两对几何抽查。上述新评分器、初始 checkpoint 构造、全 30 s 闭环及成本测试均未完成，不能给 PILOT Engineering PASS。

## B. 最小评分接缝工程验收

1. **历史前缀正确性**：t>0、多个率段和不同注入年龄时，预测源 cumulative A(t) 与原 A 一致；Q/I/D、服务量、FIFO 历史和累计 J/E 不变。不能用当前率覆盖历史，不能把历史积压在 t 重新注入。
2. **因果双生与对象隔离**：两个 live 根在 t 以前历史和当前状态相同、t 以后真实率/边界完全不同。净化 root、预测输入、逐候选成本、排序、动作必须相同；未来 trace 对象、future hash、未来 exogenous boundaries 和 metadata 不得出现在评分器可访问对象图中。故意注入一个“未来读取即报错”的源用于工程负例；仅声称 select 没调用 rate_at(future) 不足够。
3. **同预测/同根**：同 epoch 同预测模式的所有候选，history root/forecast hash 相同；分支顺序反转后评分与选择不变。评分完 live 的业务字段、executor、ledger、物理输入和源不变；私有 live 完整 hash 只供隔离审计。
4. **ZERO/PERSIST 边界**：ZERO 不抹 Q/I，仍收到已发送业务；PERSIST 只用当前率，不读取 burst 结束或 TA 下一边界。t=0、t=20、t=29 的 h=1、无当前注入、同刻真实率跳变均明确检查。
5. **已承诺事件**：t 前发送、t 后到达、多跳/cohort 混合仍保留原年龄；当前预约和自然失效按物理模型发生。未来政策命令为空；不能删除 committed arrival 来“净化”未来。
6. **解析能耗**：全 IDLE T=30→48,000 J；已有双端 ACTIVE→50,400 J；空闲 ADD 的 6 s 分支→DeltaE_h=470 J。每终端驻留为对应累计时间，320 总量闭合；DRAINING 45 W 且不计 K。最后无事件尾段计费。
7. **解析成本**：选取显式 J_h/N_end/DeltaE_h 的 fixture，按 bit·s 手算，包含 lambda_N 或 lambda_E=0、h 截短和只在末端 ready 的动作。J_h 是增量，不重复计入根以前的 J；能耗只计真实 320 终端，不按 K 快照近似。
8. **真实动作**：K=0 ADD、setup 后 LINK_UP 才增 K；DROP 不误删其他 link，保留真实 drain；合法 BBM/MBB、资源冲突/预约/窗口不足/自然失效均由 N2 判断。非法分支保存拒绝原因、不生成伪成功结果、不参与有效最小值；HOLD 若不能推进，整 epoch STOP。
9. **同动作等价**：将一段明确的新预测 trace 当成独立参考的真实后续输入，用相同 N2 动作与推进切点逐字段对照 service/queues/I/A/D/routes/events/J/energy/FIFO；新接缝不得改变冻结服务规则。比较所有字段，不能只比较最终标量。N1b Fraction 解析案例按有理值精确；binary64 原字段应在相同编码/事件序列下逐字段一致，差异须解释并记录，不能泛用宽容差。
10. **预测切点不扰动**：为 1 s 误差输出而记录子段、HOLD 的未来 epoch 以及 h 末端，不改变参考服务推进、数量闭合或年龄结果；全时域 T 与预测正常结束的两个完成标志不得混用。
11. **FIFO/数值关闭**：连续注入部分服务、同刻多入边比例合流、断连恢复、多跳队列、数值闭合均沿用 N1b；记录 exact_rational/roundoff_audit/metric_status/误差界。未知正闭合或初始未知年龄必须拒绝，不能虚构 cohort。
12. **checkpoint 和重放**：live 和净化 branch 的 clone/checkpoint/restore/replay 完全一致，包括分支成本、动作、原始 FIFO 分布、状态 hash 和错误信息。墙钟计时另列，不要求计时数值重放相同。
13. **不泄漏控制器结果**：STATIC/REACTIVE 不访问 MPC 评分或真未来；两个 MPC 的候选小域选择只用公共当前数据/OD/物理合法性，不能按未来完成结果过滤候选。
14. **全合法数与子集**：对两个初态和资源受限 fixture 验证 HOLD/ADD/DROP/REPLACE 分类；全部唯一合法数与仅进入预测的数分开。执行顺序/字典顺序不能改变 cohort 年龄或候选排序。REPLACE 的已登记生成范围须明确，不宣称任意释放组合都覆盖。

以上均通过后才可称为“新版单动作滚动评分接缝 Engineering PASS”，不构成 MPC 科学性能 PASS 或主预实验已完成。若只能数值近似，必须先提交误差界及指标状态并等待授权，不自行降低要求。

## C. 四臂预实验运行与输出

六个主场景共 24 次配对短运行；所有运行每个 epoch 至多一个原子动作，直达同一 T，业务排空后能耗仍继续。各场景四臂的 initial checkpoint/真实 traffic/OD/容量/几何/catalog/T/setup/服务/评价版本 hash 完全一致。不同场景负载或 U/C 初态不同，不跨场景宣称同初态配对。

每次运行至少输出下列原始量及单位：

|输出|定义与约束|
|---|---|
|J_T_bit_s|原 N1a 从 0 到 T 的 ∫(A−D)dt，不用旧 weighted objective 替代|
|N_T_bits、queued_bits、in_flight_bits|N=Q+I，残余不丢弃|
|offered_bits、delivered_bits、R_del_T|A/D/交付率；空输入按已有语义 1，必须标明不是零时延|
|delivered_bit_age_integral_bit_s|原始注入到最终交付的 bit 加权年龄积分 M_D|
|mean_delivered_fluid_delay_s|M_D/D；D=0→null，禁止 J_T/D|
|mean_delay_absolute_error_bound_s、age_accounting|每个真实结果的精度状态、原始分数、B/C、年龄/守恒差额|
|remaining_bit_age_integral_bit_s|未交付业务截止 T 已等待年龄；与 J/M_D 的条件恒等式核对|
|E_LCT_J、DeltaE_LCT_J|真实终端事件计费及 320×5×T 基线差额|
|K_time_series|K_admit、DRAINING、SETUP connection/terminal、预约占用、全部终端状态|
|四能耗态/五执行态驻留|逐终端及总和；每终端 30 s，总 9600 terminal·s|
|evaluation_completed_normally|是否真实到 T，与全部业务交付分开|
|all_offered_business_delivered|是否无剩余并完成所有已定义真实业务；不作为提前停止条件|
|动作/候选日志|当前 Q/I/率/K、全合法/保留/评分数、排序键、拒绝原因、实际释放集合、前后状态 hash|
|真实终端事件|RETARGET/ACQUIRE/LINK_UP/DRAINING/LINK_DOWN/ABORT/自然到期及对应时间|
|预测分支日志|因果 root/forecast hash、action、h、J_h/N_end/DeltaE_h/cost、接受/拒绝、末端与 1 s 检查点|
|计算量|每 epoch/full run 的候选枚举数、评分数/失败数、advance/event 数、cohort 数、branch-s、clone 数及峰值内存|
|墙钟时间|perf_counter 单调计时，候选枚举/净化 clone/绑定/推进/年龄/评分/全部决策分项，median/max/p95；单位 s|

运行结果 scope=PILOT_ONLY，formal_experiment=false，scientific_gate_pass=false。嵌套 N1a/b/N2 原对象仍保留其 ENGINEERING_TEST_ONLY 标记，不通过伪造 N3 schema 把 MPC 标成原 N3 控制器。

### 预测误差的因果报告

每个 epoch 先保存预测输入及分支输出，未来到达后由隔离的事后审计器计算误差，审计器不得回传给当时决策：

- 每 commodity 的预测注入量误差 `A_hat(t,t+h)−A_true(t,t+h)`，单位 bit；同时报告 1 s 误差。ZERO 与 PERSIST 均给出有符号/绝对误差，所有候选同一预测输入只统计一次。
- 选择动作的预测分支保存 t+min(1,h) 的 J 增量/N/D 增量/E 增量；与真实运行在下一 epoch 提交新动作之前的状态比较，给出 bit·s/bit/bit/J 的有符号误差。保证动作及推进切点相同，才称为单步模型/负载预测误差。
- h=6 的状态预测与真实闭环 6 s 后之差可能包含后续五次重决策的影响，只标“闭环路径差异”，不宣称纯预测误差。若要另做同动作 6 s 真后续反事实重放，需单列授权和额外分支成本，不计入当前默认方案。
- 预测率仅是外生注入预测，不能用未来到达的 in-flight 业务率作为“预测失败”；已有 I 的到达本就必须在两分支保存。

## D. 回归、守恒与模型边界检查

后续接缝工程验收运行 N1a 25、N1b 24、N2 27、N3 20 的适用原测试，以及 Gate C/D 和现有历史回归；保留所有旧测试预期。上述数量是修订 0007 记录的已有证据，本轮没有重新运行。原历史 132 项中 131 PASS，唯一既有旧 F3 失败为 `StructuralPolicyProbeTests.test_known_witness_domain_discovers_every_registered_size_without_J`；不得删除、更改或以新 FAIL 冒充同一个旧失败。若实际套件范围变化，列精确清单/总数与前后差异，不能照搬历史计数当新执行结果。

实时运行逐阶段检查 A≈Q+I+D、容量不超限、已知 cohort 守恒、N1b 条件 J=M_D+remaining_age、全部 320 终端驻留、DeltaE≥0、动作实际释放集合。守恒容差沿用原工程值与年龄包络，不使用一律“误差很小”通过；平均时延误差界仅在 N1b 条件满足时引用。

Gate B TX/D2 I 分离、零驻留 DRAINING、右删失 600 s、不连续刷新路由/传播、合成几何、末端未交付均在结果报告披露。某个控制器较低已交付平均时延可能来自只交付较快的 subset，不能忽略其 Rdel/N；禁止将 bit 加权值叫 packet 均值。实现及运行前后再次完整版本校验，所有新增/必要修改通过明确连续修订登记；冻结内核修改需求必须先 STOP。

## E. 预定义探索判读，不是科学显著性检验

主比较按场景固定报告四臂的 J/N/Rdel/M_D/mean/E/DeltaE/K 和全部动作，不选最漂亮的场景。ZERO/PERSIST 与同场景原 REACTIVE 的对比为主要信息；STATIC 是共同机制参考。附加报告草案工程汇总代价 `C_T=J_T+6 s×N(T)+1000 bit·s/J×DeltaE_T`，但各原始指标为必报项；该代价不是正式 alpha 目标，也不能把能耗换取业务或反之隐藏为全面优越。

可支持“值得继续研究”的证据：评分接缝全部通过，实际 MPC 出现合法非 HOLD，至少一个预定 C 热点场景显示与 REACTIVE 不同的真实动作/容量/业务-能耗取舍，且变化超过已报告数值不确定性；预定系数敏感性揭示结论稳定性或明确代价边界。单一任意系数下的较低工程代价只支持该设置的探索价值，不证明最优或必要。

可支持“本设置暂未显示额外价值”的证据：评分与候选机制有效、确实有合法且进入评分的改变动作，配对结果仍没有观察到有用差异，或计算成本远超可承受范围。结论限于本模型、六场景、小候选域、单动作保持和两种当前信息预测。

必须标“不可判定”的情况：所有 MPC 只 HOLD 且改变候选未进入预测；真实合法域被截断漏掉目标；预测泄漏、评价未到 T、数值/守恒失败、只有 U-STATIC 的零交付产生差距、或尚未实现评分器。不能据此宣布 MPC 不必要。原 REACTIVE 在 C 拥塞下 HOLD 是其特定规则的局限，不是所有非学习/非预测控制器的下界。

不做统计显著性、最优性或 GNN 性能声明；这是确定性工程探索，没有独立随机样本来支持论文显著性。未观察到的突发无法被 ZERO/PERSIST 提前预知；若未来要检验真正的突发预报收益，须另注册因果可用的外部预测信息及误差模型，不使用真实未来 oracle。

## 本轮实际交付与 STOP

已形成四份独立草案，已对照此前 dynamic_k_system_model_review 审计并核对版本完整性、现有接口与模型边界，已完成指定两对 31 个时刻的静态几何抽查及 t=0 静态路由分析。开始和文档生成后的完整文件复核均 PASS，无未登记差异。未创建评分器、fixture、真实 trace 文件、新配置或版本修订；没有本轮 MPC/PILOT Engineering PASS。当前阻塞为缺少新版精确评分接缝及其因果/等价验收，完成文档后停止等待审核。
