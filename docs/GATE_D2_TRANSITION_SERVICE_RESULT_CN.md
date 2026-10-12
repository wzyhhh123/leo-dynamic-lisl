# Gate D2 动态重构—网络服务耦合集成结果

## 结论

`Gate D2 transition-aware network-service integration = PASS`。

正式证据目录为 `outputs/gate_d2_20260922T162211_364524Z`，验收入口为：

```powershell
python tools/check_gate_d2.py
```

本 Gate 只证明预注册的 terminal transition 已真实作用于 routing、service、queue、in-flight 和 delivery。它没有实现或比较 topology controller，也没有按最终 J 选择 fixture。Gate E/F/G 均未启动。

## 实现结果

新增 `TransitionAwareNetworkServiceEngine` 作为 Gate B/C 与 D1 之间的 event-driven 编排适配层。适配层直接复用冻结的 `TerminalExecutor`、`graph_state`、`CommonRouter`、`QueueState`、`InFlightState` 和 equal-weight scheduler。

真实因果链已经闭合：

\[
\text{scripted proposal}\rightarrow\text{Gate C legality/policy}
\rightarrow\text{Gate B transition events}
\rightarrow G_{active}(t),G_{admit}(t)
\rightarrow\text{CommonRouter}\rightarrow\text{service}\rightarrow Q/I/D.
\]

执行器没有固定数值更新步长。每次只推进到 traffic boundary、传播 rate-change、queue-empty、Gate B event、scripted proposal、visibility expiry 或 geometry refresh 中的最近真实事件。

## 小型解析 fixture

| Fixture | 覆盖机制 | 主要观测 | 结果 |
|---|---|---:|---|
| D2-A | occupied-terminal BBM | outage 2 s；新增/峰值积压 16,000,000,000.008 bit；恢复后 8 s 清空 | PASS |
| D2-B | genuine idle-terminal MBB | forced outage 0 s；transition peak queue 0 bit；全程有路 | PASS |
| D2-C | false MBB | Gate C 返回 `FOR_FAIL_BILATERAL`，未创建 link | PASS |
| D2-D | DRAINING split | 旧 B–C 在 `G_active` 中、从 `G_admit` 移除；既有 TX 与 network in-flight work 完成 | PASS |
| D2-E | temporary partition | affected flow 进入 `NO_ROUTE_TEMPORARY`；unaffected E→F 继续服务；恢复后清空 | PASS |
| D2-F | alternate path | A–C–D → A–B–D → A–E–D；B→D 同时承载 third-party flow | PASS |
| D2-G | natural expiry | `LINK_EXPIRE → LINK_DOWN` 触发同一 graph/reroute 路径 | PASS |
| D2-H | same-state clone | 分支前状态 hash 相同，future traffic hash 相同，HOLD/SWITCH 计数为 0/1 | PASS |

D2-A 的解析误差为 0.008001 bit，相对于 16 Gbit 为约 \(5.0\times10^{-13}\)。该微小差值来自正传播时延下 action boundary 附近仍在传播的连续流体，低于冻结的 1 bit 绝对容差。D2-B 的数值队列最大值为 0.006 bit，低于相同容差，没有形成 forced zero-service interval。

## 160 星 scripted integration pilot

两个 case 使用相同的 160 星、16 OD、\(\rho=0.2\) 冻结 trace 和当前 Z_ref。proposal 来自冻结的 terminal-pair feasible windows，选择理由仅为覆盖 bridge BBM 与 spare-terminal MBB，不使用 J 做筛选。

| 指标 | Bridge / temporary partition | Connected MBB / reroute |
|---|---:|---:|
| transition | BBM 1 | MBB 1 |
| route change（OD source） | 24 | 12 |
| no-route / partition duration | 2.0 s | 0 s |
| partition node-time | 160 node·s | 0 |
| transition 新增积压 | 8.2130299337 Gbit | 0 |
| peak queue | 8.2130299337 Gbit | 0.0979 bit |
| backlog clearance | 0.5866315 s | 0 s |
| delivered | 64 Gbit | 64 Gbit |
| residual Q+I | 0.556 bit | 0.0605 bit |
| 最大守恒误差 | 0.0731 bit | 0.0534 bit |
| 最大容量数值越界 | \(1.91\times10^{-6}\) bit/s | 0 |

Bridge case 在 1–3 s 形成临时分区，12 条受影响 OD 进入 `NO_ROUTE_TEMPORARY`，外生到达继续并形成积压；3 s LINK_UP 后这些 OD 恢复路由并清空 backlog。Connected MBB case 先用真实空闲 terminal 建立 X1_1.D2–X2_1.D1，再释放旧 bridge，全程 connected，发生确定性 route change，没有 forced outage。

表中的 J 和 mean delay 只作为执行器输出与守恒核对，不构成 BBM/MBB 策略性能结论。

## 验收证据

- Gate D2 小型单元测试：10/10 PASS。
- Gate A–D 全回归：102/102 PASS。
- deterministic replay：除 runtime 外 canonical identical；事件、图、路由、Q/I/D、J 和 transition metrics 全部一致。
- 所有 7 个小 fixture 和 2 个 160 星 case 均无负队列，容量越界低于 0.01 bit/s，work conservation PASS。
- Gate A/B/C/D0/D1 共 26 个冻结文件 hash 全部 unchanged。
- `configs/current.json` 已更新到 `GATE_D2_TRANSITION_AWARE_NETWORK_SERVICE_INTEGRATION_PASS`；`gate_e_started=false`、`gate_f_started=false`、`gate_g_started=false`。

## 合同要求的 A–J 回答

**A. Gate B/C transition 是否已经真实作用于 D1 queue/service？**

是。DRAINING、LINK_DOWN、LINK_UP 和 natural expiry 均改变 `G_admit`，随后触发 CommonRouter 与 service allocation，最终改变 Q/I/D。

**B. DRAINING 的 active/admit 差异是否正确？**

是。D2-D 明确观察到旧边仍属于 `G_active`，但已从 `G_admit` 移除；新 work 和新 route 都不能再使用它。

**C. BBM outage 是否产生了可解析验证的 backlog？**

是。8 Gbit/s × 2 s 的解析值为 16 Gbit，仿真观测为 16,000,000,000.008 bit，误差低于 1 bit。

**D. MBB 是否能够避免对应的 forced outage？**

是。小型 D2-B 和 160 星 connected-MBB case 的 no-route/outage duration 都是 0。

**E. temporary partition 是否让业务等待，而不是丢失？**

是。受影响 commodity 进入 `NO_ROUTE_TEMPORARY`，arrival 继续进入 queue，没有 drop、teleport 或 topology event 产生的 delivery credit。

**F. recovery 后 backlog 是否正确继续发送？**

是。D2-A、D2-E 和 160 bridge case 均在 LINK_UP 后恢复 route/service 并在 drain limit 前清空到冻结数值容差内。

**G. alternate path 是否触发 deterministic rerouting？**

是。D2-F 记录了 A–C–D → A–B–D → A–E–D；160 connected-MBB 记录 12 次 OD-source route change。

**H. 所有 topology events 是否保持 work conservation？**

是。所有 case 的最大误差均低于 `1 bit + 1e-12 × arrived bits`，且没有负队列或实质容量越界。

**I. 160-star integration 是否通过？**

是。bridge/temporary-partition 与 connected-MBB/reroute 两个确定性 case 均 PASS。

**J. 是否存在 blocker 阻止进入 Gate E？**

当前 D2 correctness 范围内没有发现 blocker。进入 Gate E 仍需人工审查；本轮已按 stop rule 停止，没有实现 controller、matching、MPC 或 RL。
