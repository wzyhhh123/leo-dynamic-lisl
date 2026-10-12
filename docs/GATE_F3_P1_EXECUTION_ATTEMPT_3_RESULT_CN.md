# Gate F3-1 P1 完整执行：第三次 attempt 结果

## 正式状态

`Gate F3 P1 execution = BLOCKED`

`GATE_F3_P1_EXECUTION_BLOCKED_BY_COMPLETE_OR_CENSORED_SEMANTICS`

本次使用新的目录，从冻结 manifest 第一行 `rho=0.5/B0` 重新计算。该项完成模拟后有且仅有 `complete_or_censored_semantics` 失败，其余 traffic identity、work conservation、capacity、queue nonnegative、drain upper bound、candidate caps、top-K、reporting consistency 和 600 s decision boundary 全部通过。按照 stop rule，失败项没有重跑，后续 11 项没有启动。

## 原始证据

- 最终模拟时间：`240.16470503331377 s`；
- 最终未完成工作：`0.03552987114996607 bit`；
- F3 COMPLETE 零阈值：`0.01 bit`；
- 分类器得到：`CENSORED`；
- CENSORED 合法条件要求：在 `600 s` 仍有大于 `0.01 bit` 的未完成工作。

因此该状态既不满足 COMPLETE（0.03553 > 0.01 bit），也不满足 CENSORED（240.1647 != 600 s）。

进一步只读定位表明，D2 `engine.run()` 的提前排空条件使用：

`residual <= max(state_tolerance_bits, conservation_abs_tolerance_bits)`

当前冻结值分别为 `0.01 bit` 和 `1.0 bit`，所以 D2 内部提前停止阈值实际为 `1.0 bit`。残余 `0.03553 bit` 小于 1.0 bit，执行器因而在 240.1647 s 提前返回；但它仍大于 F3 的 0.01 bit COMPLETE 阈值。该跨层阈值不一致造成了非法的“600 s 前 CENSORED”状态。

这不是队列负值、守恒错误或容量超限，也不是 B0 性能结论。修复需要单独冻结如何让 F3 drain adapter 遵循 0.01 bit 判据，同时不修改 D2 的既有科学 tolerance；本次 attempt 内不得修复并继续。

## 证据完整性

失败前已经写出 invariant report、failure summary、final-state evidence、metrics、action/transition/candidate/timeseries 和 artifact hashes。冻结科学文件运行前后哈希一致；前两次 blocked attempt 的证据树没有变化。

本次有效科学结果仍为 `0/12`，`FAILED=1`，result seal 为 `NO`。P2、R1--R4、B2 和 RL/PPO 均未启动。
