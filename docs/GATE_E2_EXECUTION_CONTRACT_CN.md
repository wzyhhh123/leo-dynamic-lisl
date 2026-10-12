# Gate E2：160 星自然几何机制验证执行合同

## 1. 当前阶段

Pre-E2 绝对时间专项回归已经 PASS，因此允许启动 Gate E2 的结果盲候选枚举。本合同直接消费冻结的 E0 sweep/selector、160 星 Gate C terminal-pair windows、D0/D1 traffic/commodity 语义、D1/D2 service kernel 和 E0 paired harness。

当前只完成候选枚举与 selected-scenario 冻结。HOLD / IDEAL-SWITCH / REAL-SWITCH 尚未执行，Gate E2 尚未 PASS，Gate F 未启动。

## 2. 自然候选枚举

- 场景：冻结的 4-plane / 160-satellite reference topology。
- terminal-pair windows：Gate C 已冻结的 2,742 个自然窗口；不修改 interval end、visibility end 或 FoR。
- setup：候选分层采用 Gate C 已冻结的 audit fixture，即双端 1 s 并行 retarget + 1 s acquisition，`tau_setup=2 s`。
- decision time：`t0=max(1 s, natural interval start)`。1 s 与既有 160 星 D2 scripted integration 的 warm start 一致；不根据 J 或 reversal 调整 t0。
- 合法性：先检查 terminal-pair window、双端占用、重复链、setup 可完成、最终图连通和 transition graph；冻结选择后，每个 selected case 再实际通过 Gate C physical adapter、Gate B executor 和 transition profiler。
- MBB：目标两端均为真实 IDLE，先建新链，再释放指定旧 binding。
- BBM：目标至少一端占用同一旧 binding，先 LINK_DOWN，再 setup；不允许两个不同旧 binding 被一个命令隐式合并。
- `kappa2=tau_setup/L_remain`，其中 `L_remain=natural interval end-t0`。

候选只包含 E0 selector 允许的结构字段。枚举和选择禁止读取 J、delay、delivery、reversal 或任何 performance score。

## 3. 四类结构定义

- E-A：BBM，旧 edge 在 setup 期间移除后全网断开，LINK_UP 后恢复；使用已注册 bounded-outage legality。
- E-B：BBM，旧 edge 移除后全网仍连通且 OD path 发生变化。
- E-C：两端 IDLE 的 genuine MBB，transition 全程连通且 OD path 发生变化。
- E-D：transition 全程连通；至少一条 focus OD 的 hop path 改善，且其新路径与至少一条 third-party OD 共享 capacity-constrained edge。这里只证明存在产生 congestion externality 的结构条件，不读取或声称实际性能外部性。

每个 class / natural-kappa2 bin 按冻结字典序选择一个；空分层保留 `NO_ELIGIBLE_CASE`。

## 4. 已冻结的 paired execution points

人工已正式冻结：

- `rho = {0.2, 0.5, 0.8, 1.0, 1.2}`；
- `setup = 2.0 s`，本轮不做 setup sensitivity；
- router：`shortest_propagation` 与 `current_state_load_aware`；
- branch：`HOLD / IDEAL_SWITCH / REAL_SWITCH`。

规范文件为 `configs/gate_e2_execution_points.json`。它在任何 E2 paired branch 之前完成 canonical JSON 与 SHA-256 冻结。自然 κ₂ 继续使用 2 s setup，不重新选择 candidate、不重新分层。

8 个 selected logical entries × 5 个 rho × 2 个 router，共 80 个 logical paired points。E-C 与 E-D 中相同物理动作按 `(t0, old edge, new edge, terminal IDs, transition type, rho, router)` 合并后为 50 个 unique physical execution points；相同物理点只执行一次并映射回两个逻辑类别。

当前 8 个 `NO_ELIGIBLE_CASE` 分层原样保留。E-B 四个分层正式解释为 `NOT_NATURALLY_AVAILABLE_UNDER_CURRENT_SPARSE_ZREF`，只适用于当前三 bridge 的稀疏 Z_ref。

## 5. 验收与解释边界

每个物理点从完全相同 canonical state 分出三条 branch，共享 future traffic。任一 branch 到 common drain limit 仍有 backlog，则整个 paired point 的 reversal 为 `NOT_EVALUABLE_CENSORED`，不使用截断 J 判定 reversal。

每个 branch 检查 paired identity、work conservation、非负队列和容量约束。正式结果完整重放第二遍，去除 runtime metadata 后的 canonical results 必须一致。

selected cases 是结构化、结果盲机制案例，reversal 数量不是现实概率。2 s 是 simplified parametric fixture，不是真实商业硬件测量值。Gate E2 完成后停止，Gate F 保持未启动。
