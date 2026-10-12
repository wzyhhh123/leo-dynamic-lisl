# Gate D0：Traffic–Queue–Routing–Objective 合同

日期：2026-09-22  
状态：**PASS**  
适用范围：Gate D1 固定参考拓扑服务内核，以及未来共用快层接口。本文覆盖 D0，不授权或实现 Gate D2、拓扑控制、matching、MPC、RL 或性能比较。

本合同取代 v0.3 中关于随机 work/chunk 的第一版设想。D0 主表示已冻结为外生、确定性、分段常速的 fluid workload；单位为 bit。算法输出不能影响 traffic trace。

## 1. Commodity 与 traffic

有限有向 OD 集合为

\[
f=(s_f,d_f),\qquad f\in\mathcal F.
\]

commodity 表示卫星级聚合 OD workload，不表示单用户、TCP 连接或真实 packet。v1 没有 ground user、gateway handover 或地面接入。当前 correctness pilot 使用预注册的 16 OD manifest；OD 不因未来控制算法结果而改变。

每个 commodity 的外生到达率和累计到达为

\[
\lambda_f(t)\ [{\rm bit/s}],\qquad
A_f(t)=\int_0^t\lambda_f(\tau)d\tau .
\]

`PiecewiseConstantTrafficTrace` 在仿真开始前完整生成并以 canonical JSON 保存、hash。仿真循环内不调用 RNG。相同 trace 在不同控制分支、重放和观测分辨率下保持同一 hash；simulator 的观察或积分设置不能改变 \(A_f(t)\)。

主空间机制为 `stable → localized_hotspot → hotspot_migration → recovery`。每段使用

\[
g_f(t)\ge0,\qquad \sum_f g_f(t)=1,
\]

且各阶段总 offered rate 不变，只移动空间权重。改变总负载和 burst 过程属于后续 robustness，不属于 D1 correctness。

## 2. 负载归一化

参考图固定为

\[
G_{ref}=(V,E^{intra}\cup Z_{ref}),
\]

其中 `Z_ref` 直接读取 Gate C 冻结资产。固定和动态物理链均为 full-duplex；两个方向各有独立 \(C=10\) Gbit/s，反向不共享总额。

对预注册 reference shape \(g_f^{ref}\) 只求解一次 maximum-concurrent-flow：

\[
\max\ \alpha
\]

subject to 每个 commodity 的多商品流守恒、非负流和每条有向边容量约束。正式注入率为

\[
\lambda_f(t)=\rho\alpha^*g_f(t).
\]

hotspot 和 migration 后不得重算 \(\alpha^*\)。\(\rho\) 是 reference splittable-flow capacity 标尺，不等于实际 shortest-path 链路利用率，也不保证任意 routing 在 \(\rho<1\) 时无瞬态队列。D1 只冻结 correctness pilot 的 \(\rho=0.2\)；主实验网格仍为 deferred，不得从 D1 性能反选。

## 3. Queue、in-flight 与可靠性

对每个非目的节点和 commodity 保存

\[
Q_i^f(t)
\]

等待继续发送的 bit。对每条有向服务边保存

\[
I_e^f(t)
\]

已经离开发送端 queue、尚未抵达下游节点的 bit。目的节点不保留普通转发队列，抵达后计入 \(D_f(t)\)。传播完成前不得提前记作 downstream queue 或 delivery。

v1 假设评估窗内 buffer 足够、无 overflow drop、可用链可靠服务，并显式建模拓扑中断。BER、随机光衰落、ARQ、有限 buffer drop 和 packet loss 均在范围外；这只是 v1 scope assumption，不代表真实硬件没有这些现象。

每个真实事件边界执行硬不变量：

\[
A_f(t)=D_f(t)+\sum_{i\ne d_f}Q_i^f(t)+\sum_e I_e^f(t).
\]

外生到达、发送和传播到达以守恒事务搬运同一数值的 bit。浮点验收阈值在正式运行前冻结为：绝对 1 bit 或相对 \(10^{-12}\)。1 bit 是当前 64 Gbit pilot 总工作的约 \(1.6\times10^{-11}\)。低于阈值的残余仍原样报告，不转成 delivery，也不 drop。

## 4. Capacity 与 service discipline

有向边满足

\[
\sum_f\mu_e^f(t)\le C_e(t).
\]

只有 \(e\in G_{admit}(t)\) 才能接纳新工作。D1 中 `G_admit=G_ref` 且不切换。未来 D2 的 DRAINING edge 仍可完成已开始的 non-preemptive transmission，但不得接纳新工作；此接口语义不在 D1 执行。

D1 service discipline 固定为 equal-weight work-conserving max-min sharing。某 commodity 用不完平均份额时，剩余容量迭代分给仍有需求的 commodity。每条反向边独立调度。

## 5. CommonRouter

`CommonRouter` 与 topology controller 解耦。所有未来 topology baseline 必须调用同一接口；router 只能看到当前 `G_admit`，不能读取未来 action、controller identity 或未来 traffic。相同图、相同状态得到相同 route，正权路径必须 loop-free，平局按完整节点序列字典序确定。

D1 唯一实现为 `DeterministicShortestPropagationDelayRouter`。边权为传播时延。它只用于 service-kernel correctness validation，不自动成为 Gate E/F 唯一主 routing；进入 Gate E 前仍须增加一个共用 load-aware router 做 robustness。

当前 SGP4 pilot 在每个真实 service-rate segment 启动时，用共同 TEME 时刻的位置计算

\[
\tau_e^{prop}(t)=\frac{\|r_j^{TEME}(t)-r_i^{TEME}(t)\|}{299792.458\ {\rm km/s}}.
\]

内核在业务边界、传播速率到达、queue 清空等真实事件之间做分段仿射精确积分，没有 numerical integration step。输出 observation grid 只插值记录，不进入状态推进。

## 6. 目标与评估时域

定义网络中尚未交付的工作

\[
N_f(t)=A_f(t)-D_f(t)
\]

及主目标

\[
J=\sum_fw_f\int_0^{T_D}N_f(t)dt,
\qquad w_f=1.
\]

不额外加入 setup penalty。未来 setup/outage 的成本必须通过 service reduction、queue/backlog 增长和 \(J\) 增长自然产生，避免双重计数。完全排空时报告

\[
\bar D_{bit}=J/\sum_fA_f(T_A).
\]

仅在 \(0\le t<T_A\) 产生业务；\(t\ge T_A\) 强制 \(\lambda_f=0\)。随后运行到 \(Q+I\) 达到预注册数值零阈值，或到 safety drain limit。超限时不 drop，必须报告真实 residual backlog 和 censored evaluation。

## 7. Metrics 与冻结资产

机器 schema 至少包含：`mean_bit_delay_s`、`delivered_bits`、`delivery_ratio`、`residual_backlog_bits`、`mean_queue_bits`、`max_queue_bits`、`link_utilization`、`traffic_weighted_hop_count`、`route_change_count`、`active_dynamic_link_count`、`switch_count`、`BBM_count`、`MBB_count`、`outage_duration`、`partition_node_time`、`runtime`。D1 没有 topology transition，因此对应计数为零。

合同入口：

- `configs/gate_d0_traffic_contract.json`
- `configs/gate_d0_od_manifest_16.json`
- `configs/gate_d0_traffic_trace_schema.json`
- `configs/gate_d0_metrics_schema.json`
- `configs/gate_d1_fixture_manifest.json`

Gate D0 的 symbols、traffic、queue/in-flight、capacity、routing、objective、normalization 和 evaluation horizon 已无歧义，故 **Gate D0 = PASS**。
