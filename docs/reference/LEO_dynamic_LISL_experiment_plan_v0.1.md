# 动态 LISL 实验规划 v0.1（给 Codex）

日期：2026-09-18  
状态：研究设计草案；用于冻结系统语义、物理模型、业务场景和实验顺序。**不要据此直接训练 RL；先完成几何、执行器、流量和机制 Gate。**

## 0. 当前研究问题

面对时变多 OD 聚合业务，在有限动态 LCT 和非零重构时间下，研究：

> 什么时候值得改变持久 LISL、应该替换哪条连接、建立哪条新连接，使动态拓扑带来的业务适应收益能够超过重构期间及共享网络中产生的服务损失？

第一阶段不把“算法必须是 RL”作为前提。先建立正确的物理/网络执行模型和强基线，再判断是否需要 RL。

---

## 1. 场景层：720 星母星座与子场景

### 1.1 母星座

采用理想化 Walker-Star 参考场景：

- 总卫星数：N = 720
- 轨道面：P = 18
- 每轨卫星：S = 40
- 高度：h = 1200 km
- 倾角：i = 85°
- Walker Star
- InterPlanePhaseIncrement：F = 1
- 初始轨内间隔：约 360/40 = 9°
- 相邻轨道 Walker 相位偏移目标：F·360/N = 0.5°

由 STK TwoBody + Walker Star 生成。该场景是“理想化文献参考星座”，不是当前真实 OneWeb TLE 星座。

使用 `generate_scenario_X720.py` 创建并审计母星座。必须生成并保存：

- constellation_manifest_720.csv
- constellation_config_720.json
- constellation_audit_720.json

Geometry Gate 未通过前，不得进入 traffic/topology-control 实验。

### 1.2 子场景

不要独立生成 4-plane 或 6-plane Walker-Star；必须从同一 18×40 母星座中抽取连续完整轨道面：

- 机制/调试：40 星左右，仅作 toy / regression，不宣称完整物理子星座；
- 中等主场景 A：连续 4 个完整 plane，4×40 = 160 星；
- 中等主场景 B：连续 6 个完整 plane，6×40 = 240 星；
- 最终扩展性：18×40 = 720 星。

160/240 场景必须继承母星座同一时刻的位置、速度、plane_id、sat_id，不重新缩放 RAAN 或轨道相位。

边界轨道必须单独标记，统计内部轨道与边界轨道的 candidate 数量、lifetime、可达性差异。

---

## 2. 每星终端架构：2 fixed intra + 2 dynamic inter

每颗卫星共有 4 个 full-duplex LCT（第一版建模假设）：

1. `FWD_INTRA`：固定连接同轨前方相邻卫星；
2. `BWD_INTRA`：固定连接同轨后方相邻卫星；
3. `DYN_1`：动态跨轨终端；
4. `DYN_2`：动态跨轨终端。

两个固定同轨 LCT 始终维持同轨 ring；两个动态 LCT 用于跨轨持久连接和重构。

**重要：**固定同轨链只保证每个 plane 内连通，不保证整个星座全局连通。跨轨全局可达性依赖动态 inter-plane LISL。

第一版不要假定 `DYN_1/DYN_2` 一定是 left/right，除非后续物理 FOV/安装方向文献已冻结；先把两者视为两个独立物理终端，每个都有自己的 current_peer / target_peer / orientation / phase。若后续有硬件依据，再增加 side-specific FOV 消融。

---

## 3. 图模型：候选、命令、活动必须分离

定义：

- `E_intra`：固定同轨边集；
- `E_cand(t)`：时刻 t 物理上可以尝试建立的跨轨候选边；
- `Z_cmd(t)`：控制器当前提交/希望维持的目标动态连接；
- `E_dyn_active(t)`：双方完成重构和 acquisition，真正可传输的动态边；
- `E_active(t) = E_intra ∪ E_dyn_active(t)`。

关键合同：

`Z_cmd(t) != E_dyn_active(t)` 一般成立，因为命令和真正 LINK_UP 之间存在非零 setup/reconfiguration 时间。

路由和传输只能使用 `E_active(t)`，不能使用 candidate 或 commanded-but-not-ready 边。

---

## 4. 动态 LCT 的终端级状态

每个动态终端 `(i,k)`，k∈{1,2}，至少维护：

- `phase ∈ {IDLE, DRAINING, RETARGETING, ACQUIRING, ACTIVE}`
- `current_peer`
- `target_peer`
- `reservation_id/version`
- `orientation`
- `terminal_free_time`
- `retarget_start/end`
- `acquisition_start/end`
- `active_link_start`
- `visibility_end`

每个动态 LCT 同一时刻最多占用一个 peer；一颗卫星因此最多有 2 条动态 active/reserved inter-plane links。

一条动态物理边必须占用双方各一个动态 LCT；状态必须双边一致。

---

## 5. 重构语义：Break-Before-Make（BBM）

当某动态终端从旧 peer `j` 切换到新 peer `m`：

1. 控制命令到达；
2. 旧连接停止接纳新的 TX；
3. 已开始的非抢占发送允许完成；
4. `LINK_DOWN`，旧 peer 双方释放；
5. 两端独立 retarget；
6. 双端均到位后开始 acquisition；
7. acquisition 完成后 `LINK_UP`；
8. 新边加入 `E_dyn_active`。

若 i 和 j 两端的 free/retarget 时刻分别为：

- `t_i_free + tau_i`
- `t_j_free + tau_j`

则：

`t_ready = max(t_i_free + tau_i, t_j_free + tau_j) + tau_acq`

第一阶段：

- setup 中途不允许换目标；
- acquisition 成功率设为 1；
- 控制信令延迟先设为 0 或显式并入 free_time；
- 不建模故障、抖动、thermal、battery。

重构某一个动态 LCT 时，同星另一个动态 LCT 和两个固定同轨 LCT 均继续正常工作。

---

## 6. 物理候选边 `E_cand(t)`

一条跨轨边 `(i,j)` 进入候选集，至少需要：

1. i、j 不同轨；
2. 不是固定同轨边；
3. 距离 `d_ij(t) <= d_max`；
4. Earth LOS 成立（整条线段不穿地球/安全净空）；
5. 双端目标方向在各自动态终端可指向 FOV 内；
6. tracking angular rate / acceleration 不超过终端能力；
7. 从当前 orientation 到目标方向的 retarget 轨迹可行；
8. acquisition 完成前整个链路仍物理可行；
9. `t_ready < t_visibility_end`。

定义：

`L_usable = t_visibility_end - t_ready`

候选边必须记录：

- range
- propagation delay
- plane gap
- reference-topology hop saving
- visibility_start/end
- remaining_lifetime
- estimated retarget time
- acquisition time
- usable lifetime

**当前硬件 FOV、slew/acceleration、acquisition 参数尚未冻结时，不得把宽 FOV 简化结果称为硬件可行性证书。**先做参数化接口和文献标定表。

---

## 7. 链路容量与双工

第一版采用等容量设计，用来隔离“拓扑/重构”机制：

- 固定 intra-plane LISL 与动态 inter-plane LISL 使用同一名义容量 `C`；
- full-duplex：每个方向各自有 `C bit/s`；
- `i->j` 和 `j->i` 容量分别约束，不共享同一个 C；
- 不额外设置“整星只能发一条”的旧执行器限制；
- 若要建模 switch fabric/processing bottleneck，必须作为新的独立约束明确加入。

`C` 必须配置化，不硬编码。若复现 TCOM 风格场景，可把 10 Gbps 作为首个参考值，但最终参数表需要文献来源和 sensitivity。

仿真 packet/chunk 大小与物理链路容量分离；不要为了 10 Gbps 强行模拟真实 1500-byte packet 导致事件爆炸。使用 aggregate chunk 后必须做粒度敏感性测试，保证关键时间尺度 `B/C`、setup、traffic load 的关系没有被破坏。

---

## 8. 业务场景：时变多 OD 聚合业务

第一篇不模拟 TCP/视频/VoIP 等具体应用协议。每条业务 commodity 表示“一个区域/网关到另一个区域/网关的聚合业务”。

### 8.1 第一阶段端点

为隔离 LISL 重构机制，先使用固定 satellite-to-satellite commodity：

`f = (source_sat, destination_sat)`

避免一开始同时引入 ground access handover。

核心机制和算法稳定后，再增加 ground-region -> nearest/assigned access satellite 映射作为扩展实验。

### 8.2 Traffic profiles

至少三类：

1. **Stable**：业务空间分布基本稳定；算法不应频繁换链。
2. **Localized Hotspot**：某组 OD 在一段时间内显著增强。
3. **Hotspot Migration**：热点从一组 OD 转移到另一组 OD，用来测试“什么时候撤旧链、什么时候建新链”。

建议 phase：

`normal -> hotspot -> migration/recovery`

### 8.3 连续到达

正式业务 trace 使用连续异步到达；slot-batched 只作消融。

第一版建议：分段常速 Poisson / 可复现 aggregate arrival process；所有策略共享同一外生 trace 和 RNG seed。

控制器不能读取尚未发生的随机 arrival；MPC 只能使用公开的 intensity/forecast；oracle 才允许看完整 future trace，并明确标注信息优势。

---

## 9. Traffic 归一化：新的 2+2 场景不能再只用 fixed intra ring 当“backbone capacity”

由于 `E_intra` 只连接各自轨道，单独它不是全局连通网络，因此不能把旧的“固定骨干最大承载能力”直接拿来定义 rho。

必须先冻结一个 **reference inter-plane topology `Z_ref`**，例如：

- 两个动态 LCT 被固定成一个可复现、物理合法的常规邻轨跨轨配置；
- 或使用经典 nearest-left / nearest-right inter-plane reference；
- `Z_ref` 只用于 traffic normalization 和静态 baseline，不参与动态算法的在线优化。

定义参考图：

`E_ref(t) = E_intra ∪ Z_ref(t)`

若 reference links 随几何发生必要 handover，需要把 reference 规则写清楚；若实验窗口内可以保持静态，则优先选静态窗口。

给定未归一化 OD 模板 `G(t)`，在参考图上求多商品流最小拥塞：

`U_ref(G,t) = min_x max_e load_e/C`

令：

`g* = max_t U_ref(G,t)`

`F0(t) = G(t)/g*`

`F_rho(t) = rho * F0(t)`

于是 reference peak congestion 约等于 rho。

第一轮 rho：

`{0.2, 0.5, 0.8, 1.0, 1.2}`

rho 只缩放 demand，不改 C、packet size、hotspot duration、setup time。

---

## 10. Queue 与传输模型

按节点、commodity 建立独立队列：

`Q_i^f(t)`，单位 bit 或 aggregate work unit。

每个 packet/chunk 至少包含：

- packet_id
- flow_id
- bit_size
- arrival_time
- current_node
- in_flight state

同一 commodity 内 FIFO；不同 commodity 由明确 scheduler 调度，不能用一个 aggregate deque 暗中引入 HOL blocking。

路由只能使用 `E_active(t)`。

setup 期间被拆掉的动态边 capacity = 0；traffic 可以：

- 走其他 active inter-plane links；
- 沿同轨 ring 绕行寻找其他跨轨出口；
- 或留在 queue 等待。

必须保持 packet/bit conservation：

`created = queued + serializing + propagating + delivered + dropped`

第一阶段设置无限/足够大 buffer，drop=0；先把 service/queue 机制验证干净。

---

## 11. Routing：固定快层，Topology Control 是主研究对象

第一篇不要同时让 RL 学 topology + routing。

所有 topology-control 方法共享同一个 fast routing/scheduling baseline，例如：

- queue-aware shortest path；或
- backpressure / fixed multicommodity scheduler。

选择一个后冻结，不同 topology-control 算法不能各自配不同 routing。

两时间尺度：

- 快层：packet arrival、TX completion、LINK_UP/DOWN 后执行 routing/service；
- 慢层：每隔 `Delta_c` 秒，允许 topology controller 决定动态连接目标。

控制 epoch：

`t_n = n * Delta_c`

---

## 12. Topology Control 状态、动作和目标

### 12.1 状态 `s_n`

第 n 次拓扑决策时，至少包括：

- 当前各 commodity queue/backlog；
- 当前 `E_dyn_active`；
- 每个 dynamic LCT 的 phase/current_peer/target_peer/remaining setup；
- 当前 `E_cand(t_n)`；
- candidate remaining lifetime / usable lifetime；
- 当前已知 traffic intensity/hotspot phase；
- 必要的 reference routing/load summary。

`s_n` 的含义：**当前控制器能看到的网络状态。**

### 12.2 动作 `Z_n`

`Z_n` 是下一目标动态跨轨连接集合。

例如当前：

`{A-D, B-E, C-F}`

决策后：

`{A-G, B-E, C-F}`

表示保留 B-E、C-F，替换 A-D -> A-G。

动作必须满足：

- 每个 dynamic LCT 最多一个 peer；
- 双边 reservation 一致；
- 物理 candidate 合法；
- 不产生非法 duplicate/terminal conflict。

### 12.3 安全连通约束

第一阶段为避免“谁少把网络切断谁就赢”，建议设置：

在重构 transition 期间，对所有存在 backlog/arrival 的关键 commodity，source 到 destination 仍保持可达。

即：核心机制实验研究 capacity reduction / detour / queue，而不是 network partition。

Temporary disconnection 可作为后续扩展。

---

## 13. 主目标与指标

主目标：相同外生 trace 下最小化加权未完成业务面积：

`J = E[ integral_0^H sum_f w_f N_f(t) dt ]`

`N_f(t)` 包含该 flow 已产生但尚未最终交付的业务，包括：

- queued
- serializing
- in-flight / propagating

不要只用纯 queue-area 当主目标，因为 topology 改变 hop 数后，queue-area 和 end-to-end delay 可能排序不同。

第一阶段不再额外把 `C * setup_time` 加进 J；真实 LINK_DOWN、rerouting 和 queue 已经自然反映 service loss，避免 double-counting。

辅助指标：

- mean / P95 end-to-end delay
- delivery-by-deadline
- final residual backlog
- pure queue-area
- per-OD delay/backlog
- non-target OD degradation（外部性）
- reconfiguration count
- setup terminal-seconds
- usable-lifetime utilization
- link active lifetime
- path stretch / hop count
- max / percentile link utilization
- connectivity violations（应为 0）
- algorithm runtime / decision latency

---

## 14. 算法路线：先不用 RL

所有算法解决同一件事：

`state s_n -> target dynamic topology Z_n`

### Baselines

1. **Static/Fixed Reference**：始终使用 `Z_ref`；
2. **Ignore-Setup Greedy**：只看新 topology 的即时网络收益，不计真实 setup，但实际执行仍经历真实 setup；
3. **Hysteresis / Minimum-Hold**：收益超过阈值才切换；
4. **Adaptive-MaxWeight-style baseline**：queue pressure + reconfiguration hysteresis；
5. **Short-Horizon MPC**：对少量候选 action rollout 未来 `[t_n, t_n+H_p]`；
6. **Small-graph oracle**：小规模枚举连接序列，用于判断算法离最优有多远。

### 拟重点开发的结构化算法

优先研究：

**Setup-Aware Queue/Lifetime-Weighted Dynamic b-Matching**

思路：给候选动态边 `(i,j)` 一个权重：

`W_ij = traffic/service gain - setup/transient loss - replacement externality`

可进一步包含：

- queue pressure relief
- predicted path/service improvement
- usable lifetime
- remaining lifetime
- setup time
- old-link opportunity cost
- impact on other OD

然后在所有 candidate edges 上求 degree/terminal-constrained maximum-weight b-matching（每星 b=2，但实现必须保留 terminal-level identity）。

RL 暂不实现。只有当：

- 长期非局部影响难以由结构化权重/MPC处理；或
- MPC 很强但在线计算太慢；

再考虑用 RL 近似 `s_n -> Z_n`。

若未来做 RL：

- 小图可先做 centralized policy；
- 720 星更适合 shared-policy MARL + explicit matching/arbitration；
- 不能让 agent 单边宣布 link 成立，双边 terminal matching 必须由环境/协调层保证。

---

## 15. 实验分阶段 Gate

### Gate A：720 母星座几何

- 720/18/40 数量正确；
- RAAN plane grouping 正确；
- 轨内相位约 9°；
- 相邻 plane Walker phase 约 0.5°；
- 160/240 子图从母星座真实抽取；
- 不人工闭合不存在的子图边。

### Gate B：2+2 网络骨架

- 同轨 fixed ring 正确；
- 两个 dynamic LCT 独立；
- bilateral reservation / terminal uniqueness；
- BBM 状态机；
- stale LINK_READY 不得复活旧连接；
- 另一个 dynamic LCT 在单终端 setup 时仍能工作。

### Gate C：物理 candidate/lifetime

- LOS/range/FOV/tracking/lifetime；
- candidate vs active vs commanded 三层不混；
- `ready < visibility_end`；
- 输出 candidate count、lifetime、usable-lifetime 分布；
- 参数未文献标定前标记为 provisional。

### Gate D：Traffic/queue

- 连续异步 trace；
- per-commodity queue；
- bit/packet conservation；
- `rho` 基于 reference topology 归一化；
- stable/hotspot/migration trace 可复现。

### Gate E：机制

在小图/40星受控场景证明：

- Ignore-Setup 可做出错误 switch；
- target flow 受益但 non-target OD 受损；
- setup service loss 由真实 service/queue 演化产生，不人工重复加罚项；
- arrival timing 会改变结论。

### Gate F：算法主实验

160 / 240 星：

- Static
- Ignore-Setup
- Hysteresis
- Setup-aware matching
- MPC（top-K actions）

比较 stable / hotspot / hotspot-migration，多个 rho 与 setup/lifetime regime。

### Gate G：720 星扩展性

只跑：

- Static reference
- strongest simple baseline
- proposed structured algorithm
- （如后续需要）RL/MARL

目标是 scalability，不在 720 上穷举全部参数组合。

---

## 16. 第一轮实验自变量

### 业务负载

`rho ∈ {0.2, 0.5, 0.8, 1.0, 1.2}`

### 时间尺度

不要只报告绝对 setup seconds；同时报告：

`kappa_1 = tau_setup / T_demand_change`

`kappa_2 = tau_setup / T_remaining_link_life`

每条实际 reconfiguration 还记录真实：

`kappa_2,event = (t_ready - t_command) / remaining_visibility`

最终论文重点应形成 regime map：

- light load / slow demand -> static sufficient
- moderate setup + persistent hotspot -> dynamic beneficial
- fast-moving demand / short lifetime -> tracking too slow
- high load -> setup transient/externality becomes important

### setup / hardware 参数

先参数化，不把 toy 数值当现实：

- link capacity C
- slew speed/acceleration
- acquisition time
- FOV
- max range
- tracking angular-rate limit

需要后续“物理参数文献表”冻结后再确定正式 sweep。

---

## 17. Paired experiment / counterfactual 设计

对关键机制实验，必须使用相同：

- initial topology
- queue state
- arrival trace
- geometry trace
- RNG seed

只改变 topology-control action/policy。

保存 action 前 state digest 和 future trace hash。

重点保存：

- HOLD branch
- SWITCH branch
- Ignore-Setup decision vs real execution

从而明确区分：

- 新连接对目标流的收益；
- 被拆旧链的机会成本；
- 对其他 OD 的共享网络外部性；
- setup transient。

---

## 18. 当前明确不做

第一阶段不要加入：

- battery / solar charging
- fault model
- stochastic acquisition failure
- thermal constraint
- RL/PPO training
- application-specific TCP/VoIP/video model
- ground access handover（核心机制稳定前）
- topology + routing 同时学习

这些会破坏问题隔离。

---

## 19. Codex 当前执行顺序

1. **不要修改旧生产执行器。**先在新分支/新模块实现。
2. 验证 `generate_scenario_X720.py` 在本机 STK11 实际可运行，并输出 manifest/audit。
3. 实现从 720 manifest 提取连续 4×40 / 6×40 子图的只读工具。
4. 实现 2-fixed-intra + 2-dynamic-inter 的纯数据结构与状态机，不接 traffic。
5. 加 candidate/lifetime geometry；输出统计，不做算法。
6. 加 continuous traffic + per-commodity queue + conservation tests。
7. 固定 fast routing baseline。
8. 先实现 Static / Ignore-Setup / Hysteresis。
9. 复现小规模机制反例到新执行器。
10. 再实现 setup-aware weighted b-matching。
11. 最后才做 MPC；RL 暂停。

每个 Gate 都要有：

- deterministic seed
- manifest/config
- machine-checkable assertions
- hash / reproducibility entry
- 明确 PASS/FAIL

若任何 Gate 失败，不得继续把后续性能结果解释为论文证据。

