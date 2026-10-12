# v0.3 SGP4 geometry pilot 结果

轨道合同：synthetic-TLE + SGP4/WGS72 + TEMEOfDate；共同 epoch 为 2026-01-01 00:00:00 UTC。目标仍为 Walker-Star 720/18/40、1200 km、85°、F=1。无需 TwoBody/J2000 交叉验收。

## 资产与验收状态

原 pilot `outputs/geometry_20260921T053240_016088Z` 未修改。新结果位于 `outputs/visibility_20260921T055451_308214Z`。

- 搜索全部 258840 个无向卫星对，包含从未出现在快照中的卫星对。
- 0–600 s 窗口，30 s 粗扫描，根细化容差 0.001 s；15 s 复核，无边界数量/状态模式不一致，无超过 0.01 s 的根位移，无 unresolved grazing。
- 21 个快照候选集合与细化区间一致；单位、epoch、frame、ID/plane mapping 检查通过；重复 SGP4 传播逐元素一致。此重复性是冻结 TLE 的重复传播，不是重新拟合 TLE 的重复性。
- 两个子集的星历和区间均与母资产精确一致，保留母 ID，不重新传播或重编号。hashes.json 记录输出哈希。
- **严格目标几何 Gate A 未通过**：共同 epoch 的 RAAN 最大偏差 0.345723°、倾角 0.145399°、相位 0.145986°，超过 0.001°；半径偏差约 0.379 m，小于 25 m。当前 TLE 来自旧坐标目标的拟合，不能换一个 frame 标签就认为满足新的 TEME 目标。保留诊断资产，不放宽阈值、不覆盖原 TLE。后续正式资产需在 TEME 目标下生成并重新验收。

## 区间与子场景统计

| 项目 | 母场景 720 星 | 4-plane / 160 星 | 6-plane / 240 星 |
|---|---:|---:|---:|
| plane IDs | 0–17 | 0–3 | 0–5 |
| 可见区间数 | 46246 | 2704 | 5822 |
| 未被窗口截断的区间数 | 780 | 4 | 8 |
| 完整区间寿命中位数 (s) | 324.090 | 540.571 | 540.746 |
| 区间采样平均距离的中位数 (km) | 3723.159 | 3113.492 | 3375.674 |
| boundary 时间平均候选度 | 95.796 | 32.038 | 41.390 |
| interior 时间平均候选度 | 96.674 | 33.728 | 47.559 |
| 非环绕 plane-gap 范围 | 0–17 | 0–3 | 0–5 |

boundary 定义为所选轨道面序列的首、末面；其余为 interior。这是截取位置分类，不代表物理空间边缘。候选度仅计子集内部边，子集会丢失指向外部卫星的边，不能视为与母场景网络性能等价。plane-gap 使用绝对面编号差，不将 Star 的首末轨道面当作周期邻居。各 gap 的区间数和 visible-pair-seconds 见 statistics.json。

距离表格统计的是每个区间内端点、中点及原快照时刻的距离均值，再跨区间取中位数；不是连续距离极值，也不是按时间加权的总体距离分布。逐区间采样最小、最大和平均距离均保存在 intervals.jsonl。

绝大多数区间被 600 s 窗口截断，因此不能把 observed duration=600 s 解释为真实 lifetime；完整寿命样本也有窗口选择偏差，不代表全体链路的寿命分布。当前母场景完整区间寿命范围为 66.879–586.546 s。更长窗口的正式寿命统计尚未执行。

## 模型边界

5000 km 始终是 diagnostic cutoff，不是冻结 LCT hardware range。遮挡采用 6378.137 km 不透明球，切触阻断；没有 FOV、姿态、终端占用、setup 或 active-link 语义。30/15 s 一致性是数值分辨率检查，不是任意短接触均不会遗漏的数学证明。此次不进入 traffic、queue、routing、matching、MPC 或 RL。


## Common-mode audit update

See [COMMON_MODE_AUDIT_CN.md](COMMON_MODE_AUDIT_CN.md). Absolute element errors are dominated by a common rigid rotation; exceeding 0.001 deg alone does not establish structural distortion or require rebuilding TLEs. Existing thresholds and historical results remain unchanged.
