# Gate E0 机制验证合同与 Harness 验收结果

正式状态：`Gate E0 mechanism-validation contract = PASS`。

正式证据目录：`outputs/gate_e0_20260923T014228_143231Z`。

## 完成内容

- 预注册合同已冻结：HOLD、REAL-SWITCH、IDEAL-SWITCH、DELAYED-SWITCH 与 genuine MBB 的语义均已明确。
- paired-counterfactual harness 从同一 `t0` canonical state 深拷贝，各分支共享 geometry、terminal state、`Q/I/D`、future traffic hash、routing 和 service semantics。
- 已实现 `Delta J_real`、`Delta J_ideal`、relative effect、deadbanded reversal classifier、第三方 OD 分解。
- setup grid、非单调 break-even bracket 检测和 `<=0.01 s` refinement framework 已实现；E0 只做 synthetic correctness validation。
- sweep 与 scenario-selection manifest 已在 E1/E2 前独立 hash 冻结。
- scenario selector 只接受结构字段，按注册字典序选择；禁止读取 branch 的 `J` 或性能结果。
- independent deterministic load-aware CommonRouter 已实现并做 current-state-only correctness 验证。

## 验收证据

- Gate E0 单元测试连续两次运行：`13/13 PASS`、`13/13 PASS`。
- Gate A–E0 全回归：`115/115 PASS`。
- zero-setup REAL/IDEAL：`J` 一致、target 一致、network signature 一致。
- same-state clone、future trace identity、双 HOLD canonical replay：全部通过。
- DELAYED 执行时不可行、setup 超出 visibility window、optional MBB alias：均有确定性测试。
- Gate A–D 冻结基线共 49 个文件，正式验收复算后全部 unchanged。
- 两个 E0 manifest 的冻结 SHA-256 在正式验收中复算一致。

## 范围声明

本 Gate 没有执行 `rho × kappa1 × kappa2` 科学扫描，没有搜索或声称观察到 decision reversal，没有根据结果选择 scenario，也没有进入 matching、MPC、RL、160/240/720 星性能实验。

当前状态为：

```text
Gate E0 mechanism-validation contract = PASS
Gate E1 started = false
Gate E2 started = false
Gate F started = false
```

下一步必须先人工审查冻结的 sweep 与 scenario-selection manifest；本轮到此停止。
