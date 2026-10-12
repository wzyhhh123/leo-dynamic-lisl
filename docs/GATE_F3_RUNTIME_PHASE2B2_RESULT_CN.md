# Gate F3 Runtime Phase 2B-2 结果

正式状态：`GATE_F3_RUNTIME_PHASE2B2_PASS`

## 实现

仅增加 exact same-destination route-table reuse。Phase 1 live-state clone、Phase 2A edge-delay memoization 和 Phase 2B-1 canonical adjacency reuse 保持不变。

`phase2b1_no_destination_reuse_reference()` 保留 Phase 2B-1 行为用于工程/测试对照。public `path()` 和 `_path_with_adjacency()` 的 Dijkstra 逻辑未改。

## 严格等价测试

focused tests 覆盖：

- 不同 source、相同 destination 的两个 commodities；
- 相同 destination 下全部 node routes；
- equal-cost full-path tie；
- disconnected/None；
- directed asymmetric graph；
- source==destination；
- mixed repeated/unique destinations；
- repeated deterministic calls；
- topology change；
- exact routes dict insertion order。

legacy 与 optimized 的 route keys/order、path tuples、None pattern、route costs 和 tie choice完全相同。

## 160 星 ENGINEERING_PROFILE_ONLY 等价

固定条件：160 星、Z_MODERATE、rho=0.5、hotspot migration、production candidate source、top-K=16、真实 B1/B3，以及 Phase 1/2A/2B-1 stack。

Phase 2B-1 reference 与 Phase 2B-2 candidate 逐项 exact equal：

- 64 raw candidates；
- final 16 proposals、顺序及 hash；
- proposal-set SHA-256：`3791664971e36a1f0d9c48535e6b1e0b6cf90c4ace1cc9733723f9ddae0e46b6`；
- route tables/costs、全部 snapshot evaluations；
- HOLD/candidate V_v2、N_f、C_prop、demand/allocation、R_snap、Psi、invalid reason；
- B1/B3 actions 与 metadata；
- terminal/graph events、G_active/G_admit、Q/I/D 和 canonical live state。

B1 state SHA-256 两边均为 `ec149387d750b70b2c84b0c8f3bfa712770c8622590a3a9c455ff45c20884531`。

## 性能

B1 首 epoch：

| 指标 | Phase 2B-1 reference | Phase 2B-2 |
|---|---:|---:|
| routing evaluations | 18 | 18 |
| unique destinations | 16 commodity queries | 14 destination tables |
| path searches | 46,080 | 40,320 |
| adjacency builds | 18 | 18 |
| path-search wall time | 5.900 s | 4.961 s |
| B1 observe wall time | 4.715 s | 3.790 s |
| total epoch wall time | 14.719 s | 14.253 s |

path searches 减少 5,760，即 12.5%，精确等于 `18 × 160 × (16−14)`；没有其他 path reduction。

- B1 observe speedup：1.244×；
- total epoch speedup：1.033×。

## 停止状态

Runtime optimization 在 Phase 2B-2 后停止：

- Phase 2B-3 started = false；
- registered P1 executed = false；
- P2/RL started = false；
- final pre-P1 runtime equivalence = `REQUIRED_NOT_EXECUTED`。

正式 P1 重新授权前，下一个独立任务仍必须执行推荐 `sim_end_s=10`、无 cProfile、ENGINEERING_PROFILE_ONLY 的多 epoch Final Pre-P1 Runtime Equivalence Gate。

机器证据：`outputs/gate_f3_runtime_phase2b2_20260925T145217_477550Z/report.json`。
