# Gate F0 Human Freeze v1

## 正式状态

本文件是已验收 parent F0 contract 的 immutable overlay。它不覆盖 parent JSON 中的 null 字段，也不改写 parent baseline registry、interface audit 或 human-decisions 文档。

- Parent F0：`PASS_WITH_HUMAN_FREEZE_ITEMS`
- Human Freeze v1：待 `tools/check_gate_f0_human_freeze.py` 验收
- F1/F2/F3/RL：均未启动
- Controller implementation/performance：未开始

Overlay 引用了三个 parent SHA，并对自身不含 `canonical_sha256` 字段的 canonical JSON 计算 SHA-256。

## 1. Decision epoch

统一冻结：

- `decision_cadence_s = 2.0`
- periodic decision enabled；
- topology event、LINK_UP、LINK_DOWN、natural expiry 不触发即时 controller decision；
- minimum controller reaction interval = 2.0 s；
- 同时发生 periodic 与 physical event 时，只产生一个 periodic epoch，且在已承诺 physical events 结算后执行。

[
t_k=t_0+2k {m s}.
]

两次 epoch 之间的物理事件立即更新 terminal、graph、routing 和 service，但 controller 等待下一 periodic epoch。该等待是注册的 reaction latency。

Microstep 继续为：

```
committed propagation events
→ Gate B terminal events
→ controller observes right-continuous state
→ at most one action
→ Gate C / safety / Gate B
→ graph → router → service
```

setup target 仍不可取消或改写。

## 2. Candidate proposal budget

主规模统一 `top-K=16`，不是通过 performance 调参所得。

Hard pruning 只允许移除：

- Gate C bilateral illegal；
- setup 无法在 window end 前完成；
- terminal/reservation conflict；
- 已失效 target；
- exact physical no-op；
- 违反 regime connectivity safety 的 candidate。

禁止 proposer 读取 J、delta-J、future realized traffic、reversal、controller identity 或 downstream performance。

Hard-legal candidates 分成：

- `MBB_STRUCTURALLY_FEASIBLE`：8 slots；
- `BBM_REQUIRED`：8 slots。

某类不足 8 时全部保留，剩余 slots 按确定性规则 spill over，总数不超过 16。类内排序为 usable lifetime 降序、plane gap 升序、old edge/terminals、new edge/terminals、proposal ID 字典序。

B1/B2/B3/B4 在相同 state、epoch、regime 下获得相同 proposal set。B0 记录 budget unused by design；B5 tiny exact oracle 不受 K=16 限制。

## 3. Forecast

冻结为：

- class：`SHORT_HORIZON_FORECAST`
- traffic：`CURRENT_RATE_PERSISTENCE`
- horizon：10 s
- update period：2 s

[
hatlambda_f(t+	au)=lambda_f(t),qquad 0le	aule10{m s}.
]

不得读取 immutable trace 中尚未实现的真实 future segment。SGP4/Gate C geometry、known window、natural expiry 与 Gate B deterministic transition 是可预测物理信息，可以在 rollout 中推进。

10 s 是预注册 development horizon，不声称最优；看到 performance 前不得更改。

## 4. Z_MODERATE construction

选择 `ZM_A_MINIMAL_PLANE_CYCLE_CLOSURE`，construction epoch = 0 s。

从 Z_SPARSE_REFERENCE 出发，只使用 (t=0) 的 Gate C legal、concrete terminal pair、terminal-conflict-free、setup-completable、traffic-agnostic、result-blind candidates。目标是以最少新增 binding 消除 plane-level bridge。

构造成功，冻结新增：

[
(X0_1,D2)leftrightarrow(X3_1,D1).
]

其 ready time 为 2 s，remaining lifetime 600 s，usable lifetime 598 s。新增 plane edge 0–3，使 plane graph 成为 0–1–2–3–0 环。

结构结果：

- dynamic links：4（新增 1）；
- used dynamic terminals：8/320；
- terminal occupancy：2.5%；
- terminal conflicts：0；
- plane bridge count：0；
- satellite graph connected：true；
- satellite bridge count：0；
- non-bridge dynamic edges：4；
- plane coverage：0、1、2、3；
- added binding Gate C legal；
- added-link setup transition 在 (G_{m admit}) 上 strict connected。

配置位于 `configs/z_moderate_v1.json`。其 deterministic canonical SHA 为 `442dc666bc745da6b9fa6316cda450587f4d5da3cf64208318e2d2a15cf9f24e`。

## 5. Regime-specific safety

### Z_SPARSE_REFERENCE

- `BOUNDED_TRANSITION_OUTAGE`
- (T_{max}=2.0) s
- 只约束 controller 主动 transition period；
- ( le 2.0 ) s 可进入 controller 评价，(>2.0) s safety reject；
- post-expiry no-route 不占 2 s budget，但正常进入 rollout、J 和报告；
- 2 s 仅对应 simplified setup fixture，不是商业硬件保证。

### Z_MODERATE

- `STRICT_CONNECTED`
- controller transition 全过程中 (G_{m admit}) 必须连通；
- safety 只拒绝，不可改 MBB、换 terminal 或替换成第二候选。

两个 regime 的角色分别是 bridge-dominated bounded-BBM-outage 与 redundant connected-reconfiguration。

## F3-only unresolved items

本 overlay 不冻结：

- B2 minimum-hold grid；
- B2 improvement-threshold grid；
- F3 evaluation cross-product；
- mixed complete/censored ranking；
- stochastic seed policy。

它们统一保持 `REQUIRES_HUMAN_FREEZE_BEFORE_F3`。B2 后续可以参数化实现，但不能根据 performance 选择最佳参数。

## Additive measurement requirement

F1 validation 前 runner 必须区分：

- `transition_period_outage_s`
- `transition_period_no_route_by_commodity_s`
- `post_expiry_no_route_s`
- `post_expiry_no_route_by_commodity_s`

旧 `forced_outage_duration` 只能保留为 diagnostic。该要求不授权本轮实现 controller。

## Readiness

五个 F1 blocker 已解决，Z_MODERATE 已构造并通过结构审计。Human Freeze checker PASS 后：

- Gate F1 readiness = READY
- Gate F1 started = false
- Gate F2 started = false
- Gate F3 started = false
- RL started = false

通过后立即停止，不自动进入 F1。
