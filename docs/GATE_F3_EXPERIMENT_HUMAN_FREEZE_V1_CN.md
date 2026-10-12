# Gate F3-0 实验 Human Freeze v1

## 冻结目的

本 Gate 在任何 controller performance 结果产生前，预注册完整 F3-v1 实验。科学问题是：显式预测真实 transition → routing → service → queue 演化的 B4，是否相对于 setup/lifetime-aware、CURRENT_STATE_ONLY 的 B3 提供额外价值。

主对比为 B4 vs B3；次级对比为 B4 vs B1、B3 vs B1、B1 vs B0。禁止生成全局控制器排行榜。

## 系统、OD 与负载

F3-v1 只使用冻结 160 星场景和 16 个冻结 OD。OD manifest SHA-256 为 `b8e46dd988e4f5136eeb5b8adea4272ad93b3fafc5ed7fc4fb537eff167173de`。冻结归一化来自 `outputs/gate_d1_20260922T133909_838853Z/load_normalization_report.json`，`alpha_star_bit_s=26666666666.666664`，不按 phase、topology、controller、router 或 B4 branch 重算。

primary rho 为 0.5/0.8/1.0；robustness rho 为 0.2/1.2。rho 只缩放交通强度。

## 交通

`g0` 是 Gate D1 冻结的 16-OD 均匀 reference shape。H0=['f00', 'f02', 'f06', 'f12', 'f14']，H2=['f03', 'f08', 'f11', 'f15']。

`TRAFFIC_HOTSPOT_MIGRATION_V1` 在 0/60/120/180/240 s 分为 stable、X0 hotspot、迁移到 X2 hotspot、recovery。hotspot 倍率为 2，并在每个阶段重新归一化 shape，使 `sum_f g_f(t)=G_total=1`。`alpha_star` 不重算。`TRAFFIC_STABLE_V1` 在 0–240 s 保持 `g0`。240 s 后全部 arrival 为 0。

所有 run 最多 drain 到绝对 600 s。低于冻结 D0 0.01 bit 零阈值则 COMPLETE；600 s 仍有 unfinished work 则 CENSORED。混合 censor pair 不比较截断 J，不添加虚拟 penalty。

## 控制器、拓扑与路由

主控制器为 B0/B1/B3/B4。B2 只在 R4 中以 B2_H4、B2_H8 两个配置做工程 robustness，threshold 均为 0，不选“最佳 B2”。拓扑分别报告 Z_MODERATE 与 Z_SPARSE_REFERENCE；主 router 为 shortest propagation，R3 使用冻结 current-state load-aware router。

## 执行清单

- P1：12 runs，Z_MODERATE，primary rho，B0/B1/B3/B4。
- P2：12 runs，Z_SPARSE_REFERENCE，primary rho，B0/B1/B3/B4。
- R1：16 runs，两 topology、rho 0.2/1.2。
- R2：8 runs，两 topology、stable traffic、rho 0.8。
- R3：8 runs，两 topology、load-aware router、rho 0.8。
- R4：4 runs，两 topology、B2_H4/B2_H8、rho 0.8。

总计 60 个确定性 run_id，执行顺序固定为 P1→P2→R1→R2→R3→R4。每个 unique run_id 只执行一次，无随机 seed。

## 图与报告边界

开场图固定为 Z_MODERATE/rho0.8 与 Z_SPARSE_REFERENCE/rho0.8 两个 case，均显示 B0/B1/B3/B4 的 N(t)、Q(t)、REPLACE、Gate B transition 与 60/120/180/240 s 边界。1 s reporting grid 只用于可视化，不进入状态演化。

本 Gate 不运行 P1，不执行 controller performance，不生成 performance plot，不修改任何科学控制器、Gate B/C/D 或拓扑资产。
