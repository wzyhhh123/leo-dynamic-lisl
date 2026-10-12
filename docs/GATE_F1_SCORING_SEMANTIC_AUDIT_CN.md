# Gate F1 评分语义审计：active-set / in-flight 边界

## 1. 范围与结论

本次工作只审计已冻结的 D1/D2 service semantics 与 Gate F1 scoring human freeze v1 的兼容性。未修改评分公式、B1/B2/B3、Gate F0/F1 合同、proposer、cadence、拓扑场景或 A–E2 资产，也未运行 controller performance。

唯一分类结论为：

> **C. `SCORING_ACTIVE_SET_DEFINITION_CONFLICTS_WITH_FROZEN_SERVICE_SEMANTICS`**

现有模拟器语义本身清楚且 D1/D2 一致；冲突发生在冻结评分 overlay 的全局 `F_active` 定义与模拟器实际的节点局部、边局部 service-demand 集合之间。B1/B2/B3 的科学评分实现暂时不能继续，必须先进行一次新的 human freeze，明确评分快照怎样处理 current downstream inputs 和“只有传播中 bit、此刻没有 service demand”的业务。

## 2. 模拟器实际怎样确定 service participant

D1 与 D2 使用相同规则：

1. 对每个 `(node, commodity)` 构造本地输入率。源节点输入为当前外生 `lambda_f(t)`；已经到达某条传播边末端的连续到达流，作为该边下游节点的输入。对应实现为 `network_service_engine.py:71-79` 和 `transition_service_orchestrator.py:219-227`。
2. 初始本地候选 key 为 `Q_i^f > 1e-12` **或**该节点当前 `input_i^f > 1e-15`。对应实现为 `network_service_engine.py:81-85` 和 `transition_service_orchestrator.py:229-234`。
3. 目的节点不再发送；无 route/next-hop 的 key 不参加任何边的 service sharing；D2 还要求 next hop 属于当前 `G_admit`。对应实现为 `transition_service_orchestrator.py:235-242`。
4. 若本地 queue 超过 `state_tol`，该 key 的 demand 取 `+infinity`；否则 demand 等于该节点的当前 input rate。只有正 demand 才进入相应 directed edge 的 demand map。对应实现为 `network_service_engine.py:91-97` 和 `transition_service_orchestrator.py:243-246`。
5. 每条 directed edge 独立调用 `equal_weight_fair_share`。该函数只接收正 demand；先等分容量，有限 demand 用不完的份额会重新分给仍有需求的 key。因此实际参与集合是“当前在该节点对该边有正 demand 的 commodity”，并非一个全网统一的 commodity 集合。对应实现为 `service_scheduler.py:5-27`，合同见 `GATE_D0_TRAFFIC_QUEUE_ROUTING_CONTRACT_CN.md:96`。

所以，精确答案不是简单的 `queue > 0`、`queue > 0 OR lambda > 0` 或 `queue > 0 OR in-flight > 0`。它是：

\[
\boxed{(i,f)\text{ 在边 }e\text{ 上参与分配}
\iff e=\operatorname{nextHop}(i,f),\ e\in G_{admit},\
[Q_i^f>\varepsilon_Q\ \lor\ u_i^f>\varepsilon_u],\ d_{i,f}>0}
\]

其中 `u_i^f` 是源端外生到达率与已传播到节点 `i` 的 in-flight arrival rate 之和；有 backlog 时 `d=+infinity`，否则 `d=u_i^f`。

仓库中没有可供评分器直接调用的“全局 active commodity helper”。D1/D2 分别在各自 engine 内联构造本地 key 和 per-edge demand map。可复用的公共函数只有 `equal_weight_fair_share(capacity, demands)`，它假定调用方已经按上述规则构造 demand。

## 3. `Q=0, lambda=0, I>0` 是否可达，以及是否获得 service

该状态可以自然出现，特别是在 arrival horizon 之后的 drain 和每一跳传播时延内。D1 已有证据在 `t=0.5 s` 出现 `A=2.5, I=2.5, Q=D=0`（`GATE_D1_NETWORK_SERVICE_RESULT_CN.md:31`）；守恒合同明确 `N_f=sum Q+sum I`（`GATE_D0_TRAFFIC_QUEUE_ROUTING_CONTRACT_CN.md:81,117`）。

本次又用未修改的 D2 执行器运行了一个三节点、两跳、0.5 s 到达、每跳 1 s 传播的 correctness fixture：

| 时刻 | Q | lambda | I | 当前节点输入 | 当前 service |
|---:|---:|---:|---:|---|---|
| 0.75 s | 0 | 0 | 0.5 | 无 | 无 |
| 1.25 s | 0 | 0 | 0.5 | `B|f = 1 bit/s` | `B->C|f = 1 bit/s` |

这说明仅凭聚合条件 `I_f>0` 不能判断当前是否参与 service：

- bit 仍在一跳的纯传播区间内、尚未形成下游 arrival rate 时，没有当前 service allocation；
- in-flight arrival stream 已到达下游节点时，即使全网 queue 为零且源端 `lambda_f=0`，该业务仍可立即参与下游边的 service allocation。

## 4. 与冻结评分 active set 的冲突

冻结 overlay 定义：

\[
\mathcal F_{active}(t)=\{f:\sum_iQ_i^f(t)>0\ \lor\ \lambda_f(t)>0\},
\]

但 `V` 对全部 `N_f>0` 的业务求和，而 `N_f=A_f-D_f=sum Q+sum I`。于是上述两个自然状态都会满足 `N_f>0` 且 `f` 不属于冻结的 `F_active`。

后果是：

- 如果该 path 的某条边没有其他 `F_active` flow，`n_e=0`，冻结式 `r_{e,f}=C_e/n_e` 发生除零，`R_f` 在进入已有的 `R_f<=0` edge rule 之前就已无法定义；
- 如果同一路径上碰巧有其他 active flow，`n_e>0` 虽避免除零，但被评分的 in-flight-only flow 没有进入 denominator，仍与冻结式声称的 sharing population 不一致；
- 在下游 arrival stream 已经产生时，实际调度器会给该 flow 分配 service，而冻结 `F_active` 仍排除它；
- 在纯传播区间，实际调度器不会给该 flow 分配 service，但 `V` 又要求为其计算 `R_f`。

因此现有 edge rule `R_f<=0 -> +infinity` 不足以使公式闭合。问题不是 tolerance，也不是实现时加一条防除零即可解决；必须先冻结“评分快照的 service participant 到底采用模拟器的节点局部 demand，还是采用一个明确声明的近似集合”，以及无当前 demand 的 `N_f>0` 项怎样定义 service-rate term。

另外，实际 `equal_weight_fair_share` 会在有限 input demand 小于平均份额时重新分配剩余容量，而冻结的 `C_e/n_e` 是等分快照近似。它可以继续作为 analytic proxy，但文档不能把它描述成模拟器在所有状态下的精确 allocation。

## 5. `N_f` 在 `V` 中的解释

现有模拟器支持把 `V` 解释为：

> 将 aggregate unfinished work `N_f` 视为一份 source-to-destination current-state snapshot workload proxy。

该解释需要在新 freeze 中显式写清楚：

- `N_f` 包含 queue 和 in-flight bits；
- in-flight bits 可能已经走完部分路径；
- 所以 `N_f * C_f_prop(G,t)` 是以完整重算路径衡量 aggregate unfinished work 的快照代理，不是精确的剩余传播 work；
- `N_f^2/(2R_f)` 是恒定当前 service 假设下的 queue-area proxy，不是精确的多跳 residual-work area 或未来 queue evolution。

这个近似本身不导致公式被否决。当前 blocker 是 active-set/service-rate 边界尚未闭合。

## 6. 仅供下一次 human freeze 选择的最小方案

本次不选择、不应用以下任何方案：

1. **复用精确 scheduler demand construction。** 评分器按候选拓扑重新路由后，以当前每节点 queue、源端外生率和 in-flight arrival rates 构造 per-edge demand，再调用现有 `equal_weight_fair_share`；同时单独冻结 `N_f>0` 但当前无任何 demand 时的 `R_f` 规则。
2. **冻结一个明确的 backlogged/current-input 快照集合。** 只让当前具有本地 backlog 或正 current input 的 `(node,f)` 进入 rate sharing，并明确 in-flight-only、无 current input 的 unfinished work 是否不计 service-rate term，或采用其他显式特殊值。
3. **保留 commodity-level 近似但补齐集合与 edge rule。** 重新冻结 `F_active` 与 `N_f>0` 的关系，并明确 `n_e=0` 时 `r/R/V` 的定义；这仍需声明它与节点局部、工作守恒调度器的差异。

不能由现有冻结合同唯一选出其中一项，因此需要新的 human freeze，而不是直接做 implementation patch。

## 7. 完整性与停止状态

- A–E2 冻结清单：148/148 hash 一致。
- F1 parent 清单（含 A–E2 与 F0/Human Freeze）：159/159 hash 一致。
- scoring overlay 记录的 F0、F0 Human Freeze、F1 infrastructure 与 F1 implementation：21/21 hash 一致。
- scoring overlay canonical SHA-256 仍为 `afb031e5da8e988aadd081c83b2d2910a01bf87226c07f2938d2e6d541ca3955`；文件 SHA-256 仍为 `22a4c621d20643bf05d1578f9d567b9477a75cfcd0f0ed13c165449d86d9df2c`。
- 未修改 B1/B2/B3 scientific implementation，未生成 controller performance output。
- `F2 started = false`，`F3 started = false`，`RL started = false`。

最终状态：**Gate F1 scoring semantic audit = C / BLOCKED_PENDING_NEW_HUMAN_FREEZE**。
