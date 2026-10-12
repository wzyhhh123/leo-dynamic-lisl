# Gate K0 动态链路预算结构审计

**Gate K0 = FAIL + STOP：冻结物理资产没有 t=600 的 setup look-ahead。** 本轮目录为 `outputs\gate_k0_20261004T115537_251895Z`。未完成完整结构扫描，未选 K*，不能将此结果写为 PASS 或 STOP_NO_ADMISSIBLE_K。

诚信记录为 DESIGN_REVISION_AFTER_LIMITED_K4_OBSERVATION：结构复审发生在有限 K=4 结果已被观察之后；本工具未读取性能数值，未调用 controller，未使用 J、queue、delay、delivery 或动作 trace。K=4 保留为 VERY_SPARSE_HISTORICAL_REFERENCE，占用 8/320=2.5%。

输入诊断：冻结 SGP4 bundle duration=86400.0 s；geometry stop=600.0 s；所有 2742 个 Gate C terminal-pair 窗口的最大 end=600.0 s，其中 1992 个是右删失窗口。`contains(t)` 使用 start<=t<end。当前 retarget_a=1、retarget_b=1、acquisition=1 s，因此 t=600 的最早 ready=602 s，无法通过冻结窗口的 ready<end 合法性，SGP4 model 也拒绝超出 bundle duration 的调用。

在 t=600 单点重新计算的 distance+LOS+bilateral FoR 仍有 **1992 个 terminal pairs**，仅是瞬时几何诊断；它不能证明这些链能在 602 s 建成，更不能提供 usable lifetime。因此窗口缺失不是实证的物理容量为零，不能借此判定所有 K 不可行。5000 km 保持 diagnostic cutoff，未改称硬件范围。

在 coverage preflight STOP 后，exact maximum-cardinality matching、完整 lexicographic Z_K builder 和 uncapped REPLACE inventory 均未执行；输出以 null / NOT_EXECUTED 明确表示未知，没有用 greedy 冒充 maximum。现有 scipy.optimize.milp 与 NetworkX 可用，但可用求解器不解决缺失物理时间窗问题。

| K | terminal occupancy | min M_max margin | all-plane | connected fraction | bridge summary | median MBB fraction | median BBM fraction | legal replace median | admissible |
|---|---:|---|---|---|---|---|---|---|---|
| 4 | 2.5% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |
| 8 | 5.0% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |
| 16 | 10.0% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |
| 24 | 15.0% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |
| 32 | 20.0% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |
| 40 | 25.0% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |
| 48 | 30.0% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |
| 64 | 40.0% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |
| 80 | 50.0% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |
| 96 | 60.0% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |
| 120 | 75.0% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |
| 160 | 100.0% | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未评估 |

PRIMARY_K_ADMISSIBLE_SET = 未评估；SELECTED_PRIMARY_K = null。候选集合、15%–50% band、18/21 和 MBB比例阈值原样记录，无放宽。最小 admissible K 的规则只在完整审计通过后适用，目标是最小满足结构要求的资源预算，不是性能最优 K。

`gate_k0_allowed_inputs.json` 列明 semantic allowlist；`input_read_log.json` 记录实际输入。历史文件只通过独立保护例程逐字节 SHA-256，不解析其性能内容、不进入选择算法，完整 hash-only 路径日志在 historical_integrity_before/after。保护校验相等；生产 Z_MODERATE/F3-v1/B4 overlay/历史 FAIL 均未修改。预检查两次 canonical 一致不等于完整 K0-F replay PASS。

解除 blocker 需要人工明确独立 K0 geometry/terminal-pair look-ahead 的覆盖终点和右删失 lifetime 处理；至少必须覆盖 602 s 之后以满足严格 ready<end。应由原 synthetic TLE + SGP4/WGS72/TEME 和同一 Gate C FoR 规则生成独立资产，不能把历史 end=600 直接改大，也不能删除 t=600 或替换为 599 来通过审计。本轮不创建生产 K* topology，不进入 K1/P1/P2/RL。
