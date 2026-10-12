# Gate F3 Runtime Semantic-Preserving Optimization Phase 1 Result

正式状态：GATE_F3_RUNTIME_PHASE1_PASS

## 实现

- TerminalExecutor.clone_for_transaction()：复制全部 live state，保留独立日志列表并共享追加后只读的历史记录。
- TerminalExecutor.clone_for_counterfactual()：复制全部 live state，清空旧日志前缀，只记录 dry-run 新事件。
- TerminalExecutor.submit()：使用 exact structural transaction clone，原子提交和失败不修改 live state 的语义不变。
- profile_transition()：使用 counterfactual clone。
- submit_legacy_reference() 与 profile_transition_legacy_reference()：只供测试/工程对照使用。
- proposer 仅新增 profiler dependency injection；默认仍调用正式优化路径，排序、quota、record 和 hash 定义未改。

## 等价验收

5 项小型确定性测试覆盖：顶层字段白名单与 history boundary；optimized/legacy atomic submit 及未来事件；optimized/legacy transition profile；合法、NOOP、非法候选的剪枝 ID/原因、proposal 顺序与 hash；genuine MBB profile、submit、LINK_UP 后状态。

160 星 engineering-only 初始 epoch 对照：

- raw candidates：64，对照一致；
- final proposals：16，对照一致；
- proposal order：一致；
- proposal_set_sha256：两边均为 3791664971e36a1f0d9c48535e6b1e0b6cf90c4ace1cc9733723f9ddae0e46b6；
- ready/remaining/usable lifetime、BBM/MBB stratum、safety policy/classification：逐项一致；
- B1 action：两边均 HOLD（初始时刻 unfinished work 为零）；
- terminal transition type：两边均为 null；
- prefix 后 canonical live state：两边均为 47f31920229132020b1fff64a9ef9c46c2ead86cac9055d609a0d5263d6497f8。

## 性能

只运行 sim_end_s=0 的一个 decision epoch，没有运行 4 s 或 20 s：

| 指标 | Legacy | Optimized |
|---|---:|---:|
| proposer wall time | 102.299 s | 38.015 s |
| 全 prefix wall time | 162.749 s | 97.941 s |
| cProfile deepcopy total calls | 103,872,269 | 30,140,045 |

proposer speedup 为 2.691×。deepcopy total calls 减少 73,732,224，即 70.98%。

剩余主要耗时仍包含 B1/current router path evaluation。按照 Phase 1 stop rule，本轮不优化 router。

## 完整性

- frozen manifests 未修改；
- f3_progress.py 未修改；
- registered P1 executed = false；
- P2 started = false；
- RL started = false；
- router optimization started = false。

机器证据：outputs/gate_f3_runtime_phase1_20260925T123855_238623Z/report.json。

## 回归封存

- Phase 1 focused equivalence：5/5 PASS；
- repository full regression：267/267 PASS；
- P1 preflight（仅检查、不执行）：PASS。
