# STK 星历导出与 Python 读取

这个工具将通过 Gate A 的场景导出为独立几何数据集。它不转换 TLE，不修改原场景，不运行网络仿真。使用现有 Conda pytorch 环境。

## 导出

在 dynamic_lisl_v2 目录运行：

```powershell
python tools/export_ephemeris.py --check-only
python tools/export_ephemeris.py --gate-dir outputs/gate_a_720_20260918T124844_819817Z
```

默认导出全部 720 星、完整 86400 秒，网格间隔 30 秒，包含起点和终点。先核对 Gate A 状态、manifest 和原输出 hash，再启动独立隐藏 STK 实例、打开场景并读取。对加载后的传播器、单位和 epoch 进行回读检查；从 J2000 Position/Velocity 获取数据。源场景不会保存，结束后复核源文件 hash。

小规模接口检查可使用 `--duration-s 65 --sat-limit 12`；这是 manifest 前 12 星的诊断，不是新的星座。`--step-s` 调整采样间隔；若误差验收失败，导出报 FAIL，需减小步长重跑。需要可视窗口时显式加 `--visible`。

## 数据与离线查询

每次输出到新建的 `outputs/ephemeris_<时间戳>/`，包括：

- `ephemeris.npz`：time_s、sat_ids、position_km、velocity_km_s、metadata_json。
- `grid_audit.json`：每个 STK 网格样本对独立圆轨道 TwoBody 解析参考的检查。
- `interpolation_audit.json`：每颗卫星、每个区间内三个非网格点的误差检查。
- `stk_off_grid_audit.json`：最多 12 颗均匀选取卫星，每星三个固定随机种子的时刻，重新查询 STK 与插值比较。
- `geometry_boundary_examples.json`：三对示例卫星的球形地球 LOS 与距离边界细化。
- `status.json`、`provenance.json`：验收状态、来源和代码 hash；出错另存 failure.json。

数组形状为 `[时间, 卫星, xyz]`。位置单位 km，速度 km/s，时间为相对 metadata 中 UTC epoch 的秒数，坐标系 J2000。NPZ 不含 Python pickle。逻辑 ID 与 STK 对象名称映射保存在元数据中。

不启动 STK 的命令行查询：

```powershell
python tools/read_ephemeris.py outputs/ephemeris_<时间戳>/ephemeris.npz --time-s 17.3 --sat-id X0_1 --sat-id X1_1
```

Python 程序中将新项目的 src 配为 source root 后：

```python
from dynamic_lisl.ephemeris import Ephemeris

ep = Ephemeris.load("outputs/ephemeris_<时间戳>/ephemeris.npz")
r, v = ep.state(17.3, ["X0_1", "X1_1"])
# r 和 v 的形状均为 (1, 2, 3)
```

也可传入多个查询时刻。采用位置和速度的三次 Hermite 插值，返回速度是位置插值的时间导数，不独立插值两套不一致的状态。不允许查询覆盖范围之外的时间。

## 误差与边界的含义

STK 网格数据要求相对解析参考的位置误差不超过 1 m、速度误差不超过 1 mm/s。插值及非网格 STK 检查要求位置误差不超过 1 m、速度误差不超过 1 cm/s。阈值是当前几何工具的工程验收值，不代表链路边界误差自动达标。区间内三点检查属于采样验收，不冒充连续误差上界；测试中 120 秒粗网格会被拒绝。

边界示例不通过粗星历的可见/不可见标签直接推断，而是调用当前合同的解析圆轨道模型。对线段到地心的最短距离和星间距离构造有符号 margin，并使用 `|margin 变化率| <= |vi|+|vj|` 的保守界进行自适应区间细分：

- 能证明整个区间 margin 为正，标记 visible。
- 能证明整个区间 margin 为负，标记 invisible。
- 无法证明则继续细分；到 0.01 秒仍无法证明的叶区间保留为 unresolved_boundary。

不以“两端同号”断定中间没有短暂接触，相关反例有测试。未确定叶区间不能计入可用服务窗口，也可能对应切触而非真正可见性转换；多个相邻未确定叶区间的总宽度可能大于单叶 0.01 秒。

示例明确使用半径 6378.137 km 的不透明球和 5000 km 最大距离。5000 km 仅是诊断参数，尚未冻结成正式候选链路条件。该检查不含椭球遮挡、地球定向、FOV、姿态、双方终端指向或 acquisition，不输出完整 LISL lifetime，更不是 Gate B–G 的验收结果。将来采用非圆轨道或其他传播模型时必须替换解析参考和速度界，不能照搬。

## 采样间隔比较（2026-09-18）

当前圆轨道模型上，取 12 颗分布在不同轨道面/槽位的代表星，覆盖 24 小时，每区间检查三个非网格时刻。此表是解析参考比较，不是四次独立 STK 导出：

| 步长 | 最大位置插值误差 | 最大速度插值误差 | 1 m / 0.01 m/s 阈值 |
|---|---:|---:|---|
| 10 s | 0.000166 m | 0.00005098 m/s | 通过 |
| 30 s | 0.01341 m | 0.001376 m/s | 通过 |
| 60 s | 0.2145 m | 0.01101 m/s | 速度不通过 |
| 120 s | 3.432 m | 0.08807 m/s | 不通过 |

报告：`outputs/ephemeris_step_scan_20260918T140040Z/step_scan.json`。默认 30 秒的选择基于当前模型和阈值；正式全量 STK 导出仍单独验收，不能用代表星表替代。

## 全量实测结果（2026-09-18）

已生成 `outputs/ephemeris_20260918T135946_666110Z/ephemeris.npz`，状态为 PASS_EXPORTED_EPHEMERIS。

- 720 星，86400 秒，30 秒网格，共 2881 个时刻、2074320 个 STK 状态样本。
- 文件大小 69793306 bytes（约 66.6 MiB）。
- STK 网格对解析参考的最大位置差为 0.01063 m。
- 6220800 个非网格检查样本：最大位置差 0.01711 m、最大速度差 0.001386 m/s。
- 独立 STK 非网格查询检查通过；NPZ 保存后已用不启动 STK 的读取入口查询 17.3 秒状态。
- 新增 9 项测试与已有 Gate A 23 项测试共 32 项全部通过。
- 源场景及其 Gate A 输出 hash 在导出前后均一致，未修改旧生产执行器。

可直接复制的读取命令：

```powershell
python tools/read_ephemeris.py outputs/ephemeris_20260918T135946_666110Z/ephemeris.npz --time-s 17.3 --sat-id X0_1 --sat-id X1_1
```
