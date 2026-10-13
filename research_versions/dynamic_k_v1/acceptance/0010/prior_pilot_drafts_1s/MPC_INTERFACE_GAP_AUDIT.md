# MPC_INTERFACE_GAP_AUDIT

状态：PILOT_ONLY / READ_ONLY_AUDIT / STOP_SCORER_MISSING。日期：2026-10-12。结论：修订 0007 的 dynamic_k_v1 没有已绑定、已验收的动态 K 反事实 MPC 评分器。N1a/N1b/N2/N3 可以作为独立实现接缝的基础，但四臂预实验目前不可执行。本轮不编写该实现，不用旧 B4 的结果或接口冒充新评分器。

## 证据范围和版本验证

研究根目录 `D:/Document/leo_routing_attitude/dynamic_lisl_v2`，版本根目录 `research_versions/dynamic_k_v1`。已完整验证当前 0009 的起点/记录链/全部文件，并单独核对实施修订 0007 及其 attempt02 manifest；独立锚在 `PILOT_PARAMETER_MANIFEST_DRAFT.md`。0008/0009 是文档维护，不改变本审计的实施基线。

针对版本 runtime 和生产 src 检索 MPC/mpc/counterfactual/forecast/predict/B4，并逐文件读取 N1a、N1b observer/evaluator、N2 候选/执行/物理层、N3 观察/策略/runner、冻结 D2、Gate B、旧 forecast/rollout_evaluator。版本 runtime 包含 N1a、N1b、N2、N3，没有新版 forecast 或 rollout scorer。检索到的 MPC 位于旧生产 `rollout_controller.py/rollout_evaluator.py` 和 `f3_v2`，未绑定到新版四状态能耗/FIFO/动态 K 评价链。

本轮已定位并阅读此前完成的 `D:/Document/leo_routing_attitude/dynamic_k_system_model_review/01_SOURCE_TRACEABILITY_CN.md`、`02_SYSTEM_MODEL_FULL_CN.md` 及 `04_MODEL_GAPS_AND_DECISIONS_CN.md`。该审计针对当时实施修订 0007；本轮仍复用其实施绑定，另核对后续 0008/0009 文档记录。下述边界同时以该审计与当前绑定源码/合同为证据，不用旧 F0/F1 替代新版系统审计。此前审计自身属于仓库外审阅材料，不是冻结合同。

|前次审计文档|本轮读取的原始字节 SHA-256|
|---|---|
|01_SOURCE_TRACEABILITY_CN.md|`a6ce82dab7643f3ee591d560a76fd6e9d9e47df7d1cedf691be231c8ee450442`|
|02_SYSTEM_MODEL_FULL_CN.md|`f0e76a0715caf1fd5a3cbf3d7c63476a7a8203a6c455f383c958272c0b123f5d`|
|04_MODEL_GAPS_AND_DECISIONS_CN.md|`007cffe979e7e3ed740855ae196f114b6bc22688224f50d4cd0b821e9371462b`|

对应前次缺口：G01/G05 的代价量纲及在线未知 B_total、G02/G07 的评价与删失范围、G04 的预测 oracle 风险、G06 的 TX/I 分离、G09 的空业务初态、G13/G14/G16/G19 的容量/setup/候选域/工程预算，以及 G21/G22/G29/G30 的基线适用性、内存 checkpoint、观测完备性和数值误差。本草案只提供局部 PILOT_ONLY 处理，不宣称解决正式科学冻结清单。

完整校验命令，工作目录为 `D:/Document/leo_routing_attitude`：

```powershell
& D:/Program_Files/anaconda3/envs/pytorch/python.exe -B dynamic_lisl_v2/research_versions/dynamic_k_v1/tools/version_control_readme_v1.py verify --project-root D:/Document/leo_routing_attitude/dynamic_lisl_v2 --expected-version-sha256 ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691 --expected-revision-sha256 bd54f8efb78375acca995b8ed43f5ccbfb4be80228d46eb2ca2ab5e954d86342
```

起始和文档生成后的完整复核均 PASS，均为 5966 文件，未登记新增/删除/修改/疑似重命名四类为空。未执行任何网络 `advance_to/run`、候选事务探测、预测评分或测试套件；SGP4 点位和静态最短路计算仅用于输入可执行性审计。所有本轮写入均在仓库外审阅目录。

## 现有可复用接口与缺口

以下路径相对于版本根目录；冻结内核路径相对于研究根目录。

|接口|当前实际能力|本轮缺口|
|---|---|---|
|`runtime/n1a.py:TerminalEnergyLedger/FixedHorizonEvaluator`|320 终端事件积分、固定真实 T、不提前终止、J_T/N/Rdel、clone/checkpoint|无预测分支源替换；累计 A 与当前 trace 的历史累计量强校验|
|`runtime/n1b_observer.py:ObservedD2Engine`|原 D2 方法执行一次，观察服务、传播及闭合|不能丢弃观察游标、已发送 cohort 或已承诺传播事件|
|`runtime/n1b_evaluator.py:DeliveredFluidEvaluator`|真实 Node-Local FIFO、原始注入年龄及数值误差报告|历史必须与预测未来拼接；不能从 t>0 重新建立空年龄统计器|
|`runtime/n2_controller.py:AtomicTopologyController`|HOLD/ADD/DROP/REPLACE 的真实物理校验和双端事务，clone/checkpoint|可作为分支唯一动作执行器；没有成本评分与预测接口|
|`runtime/n2_candidates.py:CandidateSource`|全供应 catalog 当前合法候选、显式截断诊断|新增小域 selector，但不能修改原生成器或隐瞒全枚举成本|
|`runtime/n3_baselines.py:CurrentObservation/StaticHold/ReactiveDynamicK`|当前信息；两条冻结基线及审计|原 Reactive 不做可达业务的拥塞扩容，不得静默改规则|
|`runtime/n3_baselines.py:ClosedLoopBaseline/paired_runs/validate_n3`|固定接受 StaticHold/Reactive 两种 policy，只配对两臂|不能把 MPC 类塞入原 runner 后宣称原 N3 已支持四臂；需独立组合 runner|
|`src/dynamic_lisl/transition_service_orchestrator.py`|真实服务、事件推进、克隆和守恒|clone 会复制完整真实 trace/boundaries；canonical state 含 future_trace_sha256；必须独立净化|

旧 `forecast.py` 强制 horizon=10.0，其 persistence trace 从 0 开始，attach 只替换 `engine.trace/boundaries/boundary_index`。旧 `ExactRootActionRolloutEvaluator` 同样 H=10，仅 HOLD/REPLACE，使用旧 weighted objective 与 RegimeSafetyAdapter；没有新版 DeltaE/FIFO 动态 ADD/DROP 的封存绑定。旧 `f3_v2` 是另一套批次动作语义，也没有新 N1a/b 评分验收。它们只能作为阅读参考，不调用其 scoring/forecast/runner，不继承旧安全连通硬约束或 B4 的固定 worker 数。

## 最小独立实现方案，尚未授权实施

仅新增版本内独立模块与测试，冻结 `src`、现有 N1a/b/N2/N3 runtime、历史合同和测试全部保持字节不变。未来新增资产须登记连续修订；本轮不建立修订或配置文件。拟议接口如下，名字是设计而非已存在文件：

|拟议模块|最小接口|边界|
|---|---|---|
|`pilot_forecast.py`|`ForecastInput.from_current(observation,h,mode)`、规范化字节/哈希|ZERO/PERSIST 只读当前率；不接收真 trace、scenario 标签或 burst 时间|
|`pilot_root_view.py`，可与工厂合并|`CausalRootView`：当前剩余 setup、TX 日程、已承诺传播脉冲及已知 cohort|只读状态接缝；补足前次审计 G29，不把含真未来的完整 canonical state 当成观测|
|`pilot_branch_factory.py`|`make_sanitized_branch(live_atomic,observed_prefix,forecast)`|同一当前业务/终端/FIFO 克隆；在交给评分器之前切断所有未来真实源的引用|
|`pilot_score.py`|`score_root_action(branch,action,h,cost)`|调用原 N2 submit/advance_to；输出 J_h、N_end、DeltaE_h、cost、日志和计时|
|`pilot_controllers.py`|共享小域 selector；`select_mpc(current_root,forecast,candidates)`|每候选同预测；首个动作之后 HOLD；字典序平分；无未来策略 oracle|
|`pilot_runner.py`|四臂 matched-origin runner、配对检查、预测误差延迟审计|组合原 StaticHold/Reactive.select；真实服务全由 N2 和 N1a/b 完成；不改 N3 类型校验|
|独立 fixture/checkpoint 和 tests|初始 ACTIVE checkpoint；预测净化/解析/同动作等价/资源测试|不得用改邻接矩阵构造动作成功；初态与控制动作分开|

### 最关键的预测净化契约

1. 工厂是可信隔离边界，评分器只拿净化后的预测 clone。工厂读取当前状态及 `age_observations` 已完成 INTERVAL 的 external 历史，生成 [0,t] 的连续历史前缀，拼接 (t,t+h) 的预测。不得先拷入完整真 trace 再把它暴露给控制器；可采用 deepcopy 替换 memo/明确状态白名单，具体方法须通过对象引用与因果双生测试。
2. 新 trace 必须包含每个 commodity 的历史注入分布和正确 cumulative A(t)。不能以当前率填满 [0,t]，不能在 t 将积压重新注入，不能把 cohort 原始时钟改为 t。连续历史来自已观察服务时间段，不从未来真 trace 推导；t=0 历史前缀为空。
3. `trace`、未来 exogenous `boundaries` 和 `boundary_index` 一起替换；移除真未来 trace/率缓存、future policy/actions、scenario/burst 标签以及会暴露未来的源哈希元数据。N2 原 live scripted_actions 本就必须为空。用于私有 live 未变证明的真源哈希只留在实验管理器，不进入分支、排序或缓存键。
4. 保留 Gate B 已有预约/setup/真实可见失效事件；保留 D2 已发送 bit 的 propagation_agenda、arrival_rates、原服务段延迟和所有 in-flight 年龄。它们在未来发生但由过去真实动作产生，不是未来业务 oracle。不能把所有 future event 一律清掉。
5. Q/I/A/D、路由/服务状态、能耗历史、FIFO 分布、已消费游标、观察日志及数值闭合审计保持一致，新的 source 只影响 t 之后。按原 D2 微步重算未来服务，不手改 service_rates 假装新预测生效。
6. N1a 的 `input_trace_sha256` 等分支元数据应绑定历史前缀+预测源，而不是未来真源；不得更改 live 元数据。分支因果 state hash 与 live 完整证据 hash 分开。历史起点、实际 origin 身份在管理器保留，预测身份明确标记，不混充真实实验结果。
7. 整个 evaluator/ledger/controller 克隆，不只克隆 engine；禁止在 t>0 用 fresh evaluator 或空 FIFO 重新计量。branch 保留真实评价 T=30，显式只 `advance_to(t+h)`，不调用默认 `.run()` 到 30。t+h<30 的核心结果是工程 checkpoint，不把 `evaluation_completed_normally=False` 误判为预测失败；预测另检查确实到 t+h。
8. J_h/E_h 用同一根历史累计量相减；末端 N 是 Q+I。N1b 的 J=M_D+W 校验仍针对从 0 起的已知完整历史，不把整个历史 M_D/J 当成未来成本。保留正式评价指标原定义。
9. 在预测推进中使用真实 runner 的 1 s 时间格及真实内部事件（未来控制一律 HOLD），末尾截到 t+h。如为报告 1 s 预测误差而额外切段，须证明不改变服务量与数量闭合；不能插入新的物理/年龄事件或掩盖段划分差异。

核心未解验收不是数学公式，而是这个净化接缝与旧强校验能否在不改 frozen kernel 的情况下完全一致。现有独立 observer/subclass 和可变分支状态提供有条件可行路径，尚未证明。若精确历史拼接、已承诺传播或 FIFO 状态无法保持，或需要修改冻结内核，立即 STOP 并给出最小改动证据；不得落回中点近似或悄悄借用旧 B4。

前次审计 G29 指出原 N3 CurrentObservation 不是完整预测状态。新评分器须通过独立只读 CausalRootView 取得当前预约剩余时间、已有 Gate B TX 接收完成时刻、过去发射形成的传播脉冲、完整已知 cohort 和计量游标；这些是当前内部状态/既有承诺，不是未来外生业务。原 Reactive 仍只收到原 CurrentObservation。该扩展是本轮待审核的最小接口方案，不宣称已实现实际卫星遥测能力，也不能称四种算法的内部访问字段完全相同；四臂真实物理/业务输入相同，精确模型评分所需已承诺状态单独披露。

## 模型边界对解释的影响

|已核实边界|直接证据|本轮解释约束|
|---|---|---|
|Gate B TX 与 D2 in-flight 分离|Gate B `start_tx` 记录含最后 bit 接收的非抢占 TX；D2 aggregate service 没有调用它|DROP 可在 D2 仍有 I 时立即 LINK_DOWN；已发 bit 按传播 agenda 继续到达。能耗/重建结果属于这个模型，不能声称真实激光 TX drain 与 fluid 数据已逐 bit 同步|
|DRAINING 按真实 TX 延长，而非按 I 推断|Gate B `_drain` 的 free=max(now,tx_end)|主场景无预置 TX 时 DRAINING 可零驻留；独立 TX fixture 可以验证非零 drain，但不得向主场景添加人为 TX 以制造收益|
|窗口右删失|catalog 600 s end 带 right_censored；executor 收到有限 visibility_end|600 是观测边界不是自然失效，本轮 t+h≤30 不触及；不得将 600 处 LINK_EXPIRE 解读为自然失败|
|FoR 窗口根边界误差|0007 318 个左边界拒绝；推进≤1 ms 后实时 FoR 通过|ready/live 严格 guard 保留；不放宽 90°；全 catalog 记录不等于每个数值左边界都可立即执行|
|连续注入与局部 FIFO|N1b 使用原注入 affine 分布、局部入队顺序，同刻合流按 bit 比例|不改为全网原注入 FIFO，不按段中点，不重置多跳年龄；不称 packet 平均|
|binary64 服务和数值闭合|N1b precision 合同：Fraction 对已编码事件精确，64 ULP×记录数包络、2tB+C 年龄界|真实 SGP4 结果可能为 IEEE_RECONCILIATION_BOUNDED_NOT_ANALYTIC_EXACT；逐结果给界，未知正闭合即使很小也拒绝|
|固定时域和末端剩余|N1a 到 T；N1b 只统计已交付业务|正常到 T 不保证交付完；部分交付均值有完成样本偏差。结合 Rdel/N/remaining age 报告，不用 J/D 替代真实 delay|
|路由和传播离散更新|D2 拓扑变化重路由；delay 在服务段起点采样，非连续光行时积分|不宣称每秒几何路由优化或真正端到端光行时求解；候选物理检查与服务延迟采样区分|
|Reactive 的信息与规则|0007 当前不可达改善规则|其拥塞下 HOLD 只说明此特定基线能力，不证明所有非预测控制器不足|
|原观察非完备预测状态|前次审计 G29；N3 只给阶段/预约 ID、Q/I 数量|精确分支需新只读因果状态接缝；不能声称只用原 N3 observation 已能精确预测|

N1b 的误差界是对已登记数值调和的条件上界，不覆盖未观测内核缺陷或真实物理模型误差。对未知来源的年龄量、守恒冲突、超包络误差必须拒绝，不能扩大容差制造 PASS。

## 预估计算量与墙钟风险

以下是静态上界，不是实测性能。每个 MPC 主运行 30 epoch，每 epoch 至多 7 分支，最多 210 分支；6 场景×2 MPC=12 运行，最多 **2520 分支**。单动作对应预测时间长度之和为 `25×6+5+4+3+2+1=165 s`，总预测推进量最多 `12×7×165=13,860 branch-s`。主四臂真实推进量 24×30=720 simulation-s。branch-s 是仿真时间长度，不能作为墙钟时间。

预定敏感性额外 24 次 MPC 运行，最多 5040 分支、27,720 branch-s。全部上界为 **48 次真实短运行、7560 分支、41,580 branch-s**；真实推进 1440 simulation-s。合法域缺少某种动作时实际分支更少；失败分支仍计入计算量。

仅作为条件换算：若单分支平均墙钟为 0.01/0.1/1/10 s，主分支部分为 25.2 s/4.2 min/42 min/7 h；全部含敏感性分支部分为 75.6 s/12.6 min/2.1 h/21 h。均未包含候选枚举、原始绑定校验、克隆、日志 I/O 或真实推进开销，不是速度承诺，没有执行 benchmark。

每 epoch 的全 catalog 合法性检查可能更昂贵。W 个当前窗口、L 个旧连接时，原生成路径需检查的动作数不超过 `1+W+L+2WL`；例如 W=1996、L=1 时约 5989 次验证，而进入预测最多 7 个。这些验证包含 Gate B 事务 clone 和物理点位检查。实际 K 不设人工上限，验证规模随真实 L 增加，不能假定所有 epoch 恒定为该数。

现有 Atomic/Evaluator 还频繁执行原始文件绑定和物理摘要检查，FIFO 使用 Fraction，clone 携带逐渐增长的历史，SGP4 C 对象需 replayable 重建。首版保持这些保护和串行结果，不擅自修改内核、关闭校验或复用旧 B4 轻量克隆。后续授权工程验收时先测一个净化分支和一个完整 epoch，拆分 candidate/clone/binding/advance/FIFO/I/O 时间，报告峰值内存与 cohort/事件数，再决定是否允许 24 次主预实验。1 s 是模拟决策周期，不保证控制器能在现实 1 s 内算完；实时性不足也属于探索结论。

## 源码复核指纹

|相对于研究根目录的文件|本轮原始字节 SHA-256|
|---|---|
|`research_versions/dynamic_k_v1/runtime/n3_baselines.py`|`513dc16be7a6d84817f4001eb6cefe01c54011892c923718f5ad35351a3c420b`|
|`research_versions/dynamic_k_v1/runtime/n1a.py`|`06287787a8cf7045e7e810a46e0c45781635fad98e02dcba3ef5d90c48d5456f`|
|`research_versions/dynamic_k_v1/runtime/n1b_evaluator.py`|`1fd0e7d8eef20c6936b4f14c586e08f7cd72dfb92d7d71a92d287b3173acf487`|
|`research_versions/dynamic_k_v1/runtime/n1b_observer.py`|`7bccef3b17b90ef395b616bfb92ef9e18ebfe5829f0855c2dcab277d0dff0ec6`|
|`src/dynamic_lisl/transition_service_orchestrator.py`|`9ed1ecf9b8c5cde21fd5a71113fdd45e2d69a20bb808689ccf40a9392ce172e7`|
|`src/dynamic_lisl/terminal_executor.py`|`80634fd278655ca6c50a758afe5344f025154879ac71ba5b7dc455a210782583`|
|`src/dynamic_lisl/forecast.py`|`fd9c2c56a6abc789cbb1e5d2fa5e2d8dec12a3b7be9bc568d4518602dea77a27`|
|`src/dynamic_lisl/rollout_evaluator.py`|`424e91dcf5e6e05cf0dfb9079ced72138e33dfd3581e218ee3b2c8d04b06dc71`|

独立新评分器、输入净化、四臂 runner 和工程成本校准是继续所需最小授权范围；正式预实验执行仍需在工程接缝验收后另行确认。当前 STOP 由用户本轮明确要求触发，不是把旧 B4 结果迁名后继续运行。
