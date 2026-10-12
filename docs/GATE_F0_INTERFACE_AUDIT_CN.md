# Gate F0：A–E2 接口审计

## 结论

现有 Gate A–E2 执行链可以作为 Gate F 的唯一 simulator 内核继续使用，**不需要也不允许创建第二套 parallel simulator**。未发现必须修改冻结物理语义的 blocker。

进入多 epoch controller 前仍需新增薄控制适配层、可扩展 proposal 接口和分离 outage 指标；这些是后续接口工作，不构成重写仿真器的理由。

## 逐接口审计

| 对象 | 当前证据 | F0 结论 | 后续边界 |
|---|---|---|---|
| State cloning | `TransitionAwareNetworkServiceEngine.clone()` 使用 deepcopy；canonical state 包含 terminal、Q、I、A/D、traffic cursor、trace hash、routes、propagation agenda 和 future action IDs | 可复用 | SGP4 delay provider 必须提供 clone-safe deepcopy；E2 的 `E2Sgp4EdgeDelayProvider` 已验证 |
| Gate B executor | concrete D1/D2、bilateral atomic reservation、BBM/MBB、stale event、visibility expiry、batch atomicity | 可直接复用 | controller 不可直接改 executor state 或 setup target |
| Gate C windows | half-open terminal-pair interval；`evaluate()` 返回 legality、ready、remaining/usable lifetime 与具体 `Connect` | 可直接复用 | current catalog enumeration 是全集接口，不等于 scalable proposal algorithm |
| (G_{m active}/G_{m admit}) | `graph_state()` 将 DRAINING link 保留在 active、从 admit 中移除，并给出 components | 可直接复用 | controller safety 应检查整个 profiled transition，不只看最终图 |
| CommonRouter | `CommonRouter.path()`；deterministic propagation router；current-state load-aware router 拒绝 stale/future snapshot | 可直接复用 | 合同中的 robustness 名称与当前 Python 类名不同，采用 registry alias，不修改语义 |
| D1/D2 service | event-driven fluid Q/I/D、full-duplex per-direction capacity、exact affine integration、work conservation | 可直接复用 | 只能扩展 controller callback/metrics，不另写 queue/service kernel |
| E0 paired harness | clone same state、same trace hash、same target、HOLD/IDEAL/REAL | 用于 tiny validation 与 controller 单步反事实验证 | 不是 multi-epoch closed-loop controller runner |
| Traffic cursor | immutable trace、current `rate_at(t)`、boundary cursor、trace SHA | 可直接复用 | controller 默认只看当前 rate，不能偷读 future segments |
| Topology representation | exact physical bindings in Gate B；satellite-level active/admit edges in D2 | 可直接复用 | action 必须保留 terminal identity，不能只提交 satellite edge |

## 关键代码位置

- Gate B terminal/resource semantics：`src/dynamic_lisl/terminal_executor.py:24`、`:92`、`:146`、`:344`。
- Gate C bilateral legality：`src/dynamic_lisl/gate_c_simplified_feasibility.py:9`。
- terminal-pair candidates 与 lifetime：`src/dynamic_lisl/terminal_pair_intervals.py:141`、`:173`、`:199`。
- active/admit graph 与 transition profiling：`src/dynamic_lisl/transition_profiler.py:35`、`:48`。
- D2 microstep order、action、clone 与 canonical state：`src/dynamic_lisl/transition_service_orchestrator.py:43`、`:307`、`:360`、`:568`、`:571`。
- primary/common router：`src/dynamic_lisl/common_router.py:9`、`:15`。
- load-aware router：`src/dynamic_lisl/load_aware_router.py:19`、`:37`。
- immutable traffic：`src/dynamic_lisl/traffic_trace.py:18`、`:70`、`:73`。
- persistent per-node/per-commodity queue：`src/dynamic_lisl/queue_state.py:6`。
- paired counterfactual：`src/dynamic_lisl/mechanism_validation.py:92`、`:108`、`:139`。

## 时间与同时事件语义

D2 已冻结的 microstep 是：已承诺 propagation event → Gate B terminal event → scripted physical evaluation/action → active/admit graph → route/service。Gate B 同时刻内部 priority 是 visibility expiry、TX completion、LINK_DOWN、retarget、LINK_READY。

Gate F 的 controller callback 尚未存在。F1 应把 controller decision 作为上述同一 microstep 中的薄层插入，不能通过外部 simulator 循环复制 Q/I/D。周期值和 event trigger 仍需人工冻结。

## Clone 与 absolute time

Pre-E2 absolute-time regression 已 PASS。现有 canonical state 能用于 exact replay。一般 `Sgp4EdgeDelayProvider` 的 Satrec 不能直接 deepcopy；E2 已用只共享 immutable Satrec、复制 cache 的 adapter 解决。Gate F 的 natural-geometry runner必须沿用 clone-safe provider，不得退回 TwoBody 或重新实现 geometry。

## Candidate proposal gap

`TerminalPairCatalog.terminal_pair_candidates(t)` 能给出当前所有可见 concrete terminal pairs，Gate C 能逐个判合法，但当前没有 scalable top-K proposer。F0 只冻结 proposer interface；K、ranking 和 pruning 需人工决定。这个 gap 不影响合同 PASS，但会阻止直接进行 F1 公平实现。

## Outage metric gap

D2 当前 `no_route_duration_s` / `outage_duration_s` 会把 transition outage 和 later natural-expiry outage 累加。E2 已显示该合并会混淆解释。

Gate F 要求新增或从 route/terminal event timeline严格派生：

- transition-period no-route；
- post-expiry no-route；
- 两者的 per-commodity 版本。

这是 additive measurement work，不改变 Gate A–E2 dynamics。完成前不得运行 F3 performance。

## Z_ref 静态结构审计

当前 160-star Z_ref：

- 160 条 fixed intra-plane edges；
- 3 条 dynamic cross-plane edges；
- dynamic terminal occupancy 为 6/320 = 1.875%；
- 只占用 5 颗卫星的 dynamic terminals；
- 三条 dynamic edges 都是 bridge；
- plane 0–3 均被覆盖。

因此 E-B connected-BBM 缺失是 reference structure 的结果。Gate F 必须保留 sparse regime，同时另建 result-blind Z_MODERATE。

## 冻结资产审计

F0 开始前把 A–E2 的 148 个文件/hash 记录到 `configs/gate_f0_frozen_a_to_e2_hashes.json`。F0 checker 只读复核这些 hash。合同编写没有修改 Gate A–E2 manifests、candidate selection、execution points、执行代码或 evidence。

## Blocker 结论

没有 simulator blocker。进入 F1 的阻塞来自未完成的人工 contract freeze，而不是代码不可用：

- decision cadence/event trigger；
- candidate K/ranking/pruning；
- forecast source/horizon；
- Z_MODERATE design/density；
- safety connectivity policy；
- hysteresis/min-hold grid；
- mixed-censor ranking。
