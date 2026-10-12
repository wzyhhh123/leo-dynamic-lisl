# Gate F3 Runtime Phase 2B-1 结果

正式状态：`GATE_F3_RUNTIME_PHASE2B1_PASS`

## 修改范围

`DeterministicShortestPropagationDelayRouter.routes_to_destinations()` 现在对每次调用构造一次 exact canonical adjacency，然后按原 commodity/node 循环顺序执行全部 path search。每个 search 仍使用原 positive-weight Dijkstra 和 lexicographic full-path tie-breaking。

Phase 1 exact live-state clone 与 Phase 2A exact local edge-delay memoization 保持启用且未改变。

## 小型严格等价

测试覆盖：基础 route、equal-cost tie、disconnected/None、directed asymmetric graph、source==destination、多个 commodity 同 destination、不同 destination、不同 topology、重复调用确定性和 canonical neighbor order。

legacy 与 optimized 的 route dict、dict insertion order、path tuple、None pattern、route cost 和 tie choice 完全一致。路径不使用 tolerance 比较。

## 160 星 ENGINEERING_PROFILE_ONLY 等价

固定条件：160 星、Z_MODERATE、rho=0.5、hotspot migration、production candidate source、top-K=16、真实 B1/B3、当前 Gate B/C、Phase 1 与 Phase 2A。

逐项 exact equality：

- 64 个 raw candidate IDs；
- final 16 proposal IDs/order/hash；
- proposal-set SHA-256 均为 `3791664971e36a1f0d9c48535e6b1e0b6cf90c4ace1cc9733723f9ddae0e46b6`；
- 全部 route tables、route costs、HOLD/candidate snapshot evaluations；
- 每个 commodity 的 N_f、C_prop、demand nodes、allocations、R_snap、Psi 和 invalid reason；
- B1/B3 selected action、decision metadata；
- terminal/graph event sequence、G_active/G_admit、Q/I/D 和 canonical live state。

B1 捕获状态 SHA-256 两边均为 `ec149387d750b70b2c84b0c8f3bfa712770c8622590a3a9c455ff45c20884531`。

## 性能

B1 首个 epoch：

| 指标 | Legacy | Optimized |
|---|---:|---:|
| `routes_to_destinations()` calls | 18 | 18 |
| path search count | 46,080 | 46,080 |
| adjacency build count | 45,792 | 18 |
| adjacency build wall time | 3.733 s | 0.00260 s |
| path search wall time | 5.783 s | 5.290 s |
| B1 observe wall time | 7.961 s | 4.118 s |
| total epoch wall time | 18.884 s | 14.286 s |

- adjacency build count 减少 45,774，即 99.961%；
- B1 observe speedup：1.933×；
- total epoch speedup：1.322×；
- path search count 完全不变。

## 剩余热点

46,080 次独立 Dijkstra path search 仍占约 5.29 s，是 snapshot routing 的主要剩余热点。destination-tree/reverse-Dijkstra 属于 Phase 2B-2 范围，本任务未实施。

## 完整性与停止状态

- registered P1 executed = false；
- Phase 2B-2 started = false；
- P2 started = false；
- RL started = false；
- frozen manifests 未修改；
- final pre-P1 runtime equivalence = `REQUIRED_NOT_EXECUTED`。

最终正式 P1 重新授权前，仍必须另行执行至少 `sim_end_s=4`、推荐 10 s 的多 epoch、无 cProfile、production optimized engineering equivalence gate。本任务没有执行该 Gate。

机器证据：`outputs/gate_f3_runtime_phase2b1_20260925T142155_002773Z/report.json`。
