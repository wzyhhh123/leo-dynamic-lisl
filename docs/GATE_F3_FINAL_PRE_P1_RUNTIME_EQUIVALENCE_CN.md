# Gate F3 Final Pre-P1 Runtime Equivalence

## 结论

**FINAL_PRE_P1_RUNTIME_EQUIVALENCE = PASS**。在 160 星、Z_MODERATE、rho=0.5、TRAFFIC_HOTSPOT_MIGRATION_V1 条件下，reference semantics 与 Phase 1 + Phase 2A + Phase 2B-1 + Phase 2B-2 production stack 在 `t={0,2,4,6,8,10}s` 的 6 个决策 epoch 全部逐项 exact equivalent。

本次运行是 `ENGINEERING_PROFILE_ONLY`，未使用 registered P1 run ID，未运行 P1/P2/RL，未启动 Phase 2B-3，也未启用 cProfile。

## 逐 epoch canonical state chain

| t (s) | before decision | after decision | after next advance | exact |
|---:|---|---|---|:---:|
| 0 | `8ff14d3ddbf1dc75edba13dbe48e11073f840647076e768d7c1076fd4e3fc569` | `8ff14d3ddbf1dc75edba13dbe48e11073f840647076e768d7c1076fd4e3fc569` | `62ae8c74bdf3e196cbf1ee770c148116c0089d551fe52ab50d164618a0f0f51e` | YES |
| 2 | `62ae8c74bdf3e196cbf1ee770c148116c0089d551fe52ab50d164618a0f0f51e` | `8e3d7180756049eff8d4a3d88cf5c8c0a46b43e70851a8c39a4c8f2f161f439a` | `e0ceae02c90f76f981ed7bf818e8e2de2805a7cdf14134dae3e7f8155d6af627` | YES |
| 4 | `e0ceae02c90f76f981ed7bf818e8e2de2805a7cdf14134dae3e7f8155d6af627` | `e0ceae02c90f76f981ed7bf818e8e2de2805a7cdf14134dae3e7f8155d6af627` | `144ad67f4b419f1e13d565ac2595da2ce6f01446fe3a92f8ac4060462b79e4ac` | YES |
| 6 | `144ad67f4b419f1e13d565ac2595da2ce6f01446fe3a92f8ac4060462b79e4ac` | `144ad67f4b419f1e13d565ac2595da2ce6f01446fe3a92f8ac4060462b79e4ac` | `cefe6dbd781602fb7cadc28d035384991d54c5d30afd79bcb5c68de4a77ce9a1` | YES |
| 8 | `cefe6dbd781602fb7cadc28d035384991d54c5d30afd79bcb5c68de4a77ce9a1` | `745ec98a7256904196dfbf5a08b59a92ec03e829a698c549052840bde1c029a8` | `f1b9572df54cfd36dc5138585efc7a863cc1a5bfb4c577362d2fcd0b49234cdc` | YES |
| 10 | `f1b9572df54cfd36dc5138585efc7a863cc1a5bfb4c577362d2fcd0b49234cdc` | `f1b9572df54cfd36dc5138585efc7a863cc1a5bfb4c577362d2fcd0b49234cdc` | `f1b9572df54cfd36dc5138585efc7a863cc1a5bfb4c577362d2fcd0b49234cdc` | YES |

`t=10 s` 是 prefix 终点，没有后续时间区间，因此 after-next-advance 与 after-decision 相同。其余相邻 epoch 的 after-next-advance 与下一 epoch 的 before-decision 连续一致。

## 自然状态演化

| t (s) | queue bits | in-flight bits | delivered bits | active links | reservations | action |
|---:|---:|---:|---:|---:|---:|---|
| 0 | 0.000000 | 0.000000 | 0.000000 | 4 | 0 | HOLD |
| 2 | 0.000000 | 1257393790.976810 | 25409272875.689850 | 4 | 1 | REPLACE / F3SRC-1ca9c38058121acc54630a0c |
| 4 | 0.000000 | 1257393790.976810 | 52075939542.356514 | 4 | 0 | HOLD |
| 6 | 0.000000 | 1125138693.593062 | 78874861306.428040 | 4 | 0 | HOLD |
| 8 | 0.000000 | 1125138693.593062 | 105541527973.094696 | 3 | 1 | REPLACE / F3SRC-edfb9767cd6e2f6a9aa5e8eb |
| 10 | 0.001231 | 1532613265.685078 | 131800720067.692688 | 4 | 0 | HOLD |

delivered work、in-flight work、terminal reservation、active-link count、动作和 proposal hash 随时间发生变化，因此该验收不是重复六次初始状态。

## Production runtime evidence

| t (s) | candidate source | proposer | controller observe | network advance | Gate B | epoch total |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.220 | 11.936 | 3.697 | 0.958 | 0.000 | 15.868 |
| 2 | 0.193 | 9.759 | 3.530 | 0.858 | 0.188 | 13.689 |
| 4 | 0.207 | 11.446 | 3.525 | 1.133 | 0.000 | 15.196 |
| 6 | 0.216 | 11.811 | 3.692 | 13.763 | 0.000 | 15.736 |
| 8 | 0.220 | 11.528 | 3.571 | 0.013 | 1.231 | 16.567 |
| 10 | 0.221 | 12.913 | 3.599 | 21.046 | 0.000 | 16.750 |

Production optimized 10 s prefix 总 wall time 为 **131.992 s**，epoch total 均值 **15.634 s**、最大值 **16.750 s**。Reference 总 wall time 为 **296.715 s**，production 相对 reference 为 **2.25x**。这些数字只属于 engineering runtime evidence，不参与 PASS/FAIL。

## 完整性检查

- Runtime Phase 1/2A/2B-1/2B-2 focused equivalence tests：15/15 PASS。
- Full repository regression：277/277 PASS。
- 当前 P1 runner 的只读 `preflight()`：PASS，全部 11 个检查为 true。
- F3 canonical manifest、execution manifest、F3-0.1 overlay、A–E2 frozen parents 与 runtime overlay chain：unchanged。
- 历史 blocked attempt 证据：unchanged。
- Registered P1：0/12 executed；仍需新的人工授权。

历史 `tools/check_gate_f3_p1.py` 仍用于验证 F3-0 当时的候选源 blocker，因此会保留并打印旧 blocker；本 Gate 使用当前执行器中的 `tools.run_gate_f3_p1_execution.preflight()` 作为 post-overlay preflight。

## 证据

- `outputs/gate_f3_final_pre_p1_runtime_equivalence_20260925T154049_934409Z/report.json`
- `outputs/gate_f3_final_pre_p1_runtime_equivalence_20260925T154049_934409Z/epoch_equivalence.json`
- `outputs/gate_f3_final_pre_p1_runtime_equivalence_20260925T154049_934409Z/runtime_summary.json`
- `configs/gate_f3_final_pre_p1_runtime_equivalence_status.json`

Gate 已停止。P1/P2/RL 均未启动。
