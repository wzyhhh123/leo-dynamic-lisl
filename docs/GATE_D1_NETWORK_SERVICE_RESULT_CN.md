# Gate D1：固定拓扑 network-service kernel 验收结果

日期：2026-09-22  
状态：**Gate D1 fixed-topology network-service kernel = PASS**  
正式证据：`outputs/gate_d1_20260922T133909_838853Z`

本 Gate 只验证

\[
traffic\rightarrow routing\rightarrow capacity/service\rightarrow queue
\rightarrow propagation\rightarrow delivery.
\]

没有调用 topology controller，没有创建 CONNECT/DISCONNECT，没有执行 dynamic reconfiguration，也没有比较任何 topology algorithm。Gate D2 未启动。

## 1. 实现

新增职责分离模块：commodity、piecewise-constant traffic trace、per-node/per-commodity queue、per-edge/per-commodity in-flight、CommonRouter、fair service scheduler、event-driven network service engine、MCF load normalization 和 metrics schema。

状态推进只发生在真实事件处；观测网格通过仿射插值记录，不改变轨迹。外生到达、发送和传播到达使用守恒事务移动同一份 bit。传播中的工作留在 \(I_e^f\)，serialization/service 完成不会被瞬时算作 downstream delivery。

## 2. 解析 fixtures

| Fixture | 手算验收量 | 结果 |
|---|---:|---|
| Single link | 10 bit；\(J=5\) bit·s；mean delay 0.5 s | PASS |
| Two hop | `Q_A → I_AB → Q_B → I_BC → D`；\(J=4\) bit·s | PASS |
| Shared bottleneck | 两流各 8 bit；公平各得 5 bit/s；max queue 6 bit；\(J=8\) bit·s | PASS |
| Overload then drain | max queue 10 bit；停止到达后 1 s 清空；\(J=18\) bit·s | PASS |
| Disconnected path | 10 bit 留在 queue；0 delivery；censored | PASS |
| Propagation/in-flight | t=0.5 s 时 A=2.5、I=2.5、Q=D=0 | PASS |
| Deterministic tie | 两条等长路稳定选择 `A-B-D` | PASS |

D1 专项测试重复两次均为 10/10；包含 Gate A/B/C 的完整回归为 92/92。

## 3. MCF normalization 与 160 星 pilot

冻结 `G_ref` 有 160 个节点、163 条无向物理边和 326 条有向服务边。16 OD 的 uniform reference shape 得到

\[
\alpha^*=26.6666666667\ {\rm Gbit/s}.
\]

correctness pilot 使用 \(\rho=0.2\)，故各阶段总 offered rate 恒为 5.3333333333 Gbit/s；hotspot 和 migration 只改变空间分布，未重新计算 \(\alpha^*\)。LP 标尺的 peak utilization 为 0.2。

所有 16 个 OD 都有路径。shortest-propagation-delay 路径为 21–55 hop，均值 30.25 hop；出现 9 种 hop count。110 条有向路由边被多个 OD 共用，单边最多重叠 7 个 OD，说明场景确实包含 shared bottleneck 结构。实际最高链路利用率为 0.21725。该负载是 correctness pilot，不是主性能负载或算法收益证据。

## 4. Queue、delivery 与目标

12 s 到达窗共注入约 64 Gbit，12.21344 s 达到数值排空条件：

- \(J=7.3144340947\times10^9\) bit·s；
- mean bit delay = 0.114288 s；
- delivery ratio = 0.999999999999746；
- 原样保留的数值 residual = 0.01809 bit，其中 queue 0.01662 bit、in-flight 0.00147 bit；
- max aggregate queue = 0.24409 bit；
- traffic-weighted hop count = 30.0667。

残余小于冻结的 1 bit 数值零阈值，未被转成 delivery 或 drop。结果没有 queue overflow、丢包或 capacity credit。

## 5. 守恒、容量与分辨率

逐真实事件检查 \(A_f=D_f+\sum_iQ_i^f+\sum_eI_e^f\)。7420 个样本中：

- max absolute conservation error = 0.00112142 bit；
- max relative conservation error = \(2.0514\times10^{-13}\)；
- negative queue count = 0；
- max capacity numerical excess = \(1.9074\times10^{-6}\) bit/s，小于冻结的 0.01 bit/s 容量数值阈值。

相同 initial state、trace、routing config 和 0.5 s passive observation grid 重跑，终态、route 和除 runtime 外的 metrics canonical JSON 完全一致。0.5 s 与 0.3 s observation grid 的 arrived、delivered、J、mean delay 和 max queue 全部完全一致；trace hash 也一致。内核没有 numerical integration step。

SGP4/TEME 传播检查在 0、3、6、9、12 s 采样全部 326 条有向边：传播时延范围 0.606–3.967 ms，pilot 窗内最大相对变化 1.618%。service-rate segment 启动时使用当时的 `distance/c`。

## 6. 冻结性、运行成本与结论

Gate A/B/C 的 19 项冻结文件/资产全部与既有 hash 一致。固定拓扑 pilot 单次内核运行约 22.3 s；稠密状态条目上界 7776，当前实现实际使用稀疏状态。

Gate D1 acceptance checks 全部通过：解析 fixtures、nonnegative queue、capacity、逐事件 conservation、deterministic replay、drain-down、resolution audit、OD path、完整回归和冻结 hash 均为 PASS。因此：

**Gate D1 fixed-topology network-service kernel = PASS。**

当前停止。D2 的 Gate B/C transition coupling、BBM/MBB traffic fixtures、HOLD/SWITCH sanity check 及所有 topology transition 仍未实现，需人工批准后另行开始。
