# Gate A 操作说明

范围仅为 Walker-Star 母星座几何与稀疏星历验收，不执行 B–G、网络业务仿真或 RL。旧参考脚本保留原样，不再作为正式入口。

在 dynamic_lisl_v2 目录及 Conda pytorch 环境中运行：

```powershell
python tools/generate_scenario_X720.py --mode preflight
python tools/generate_scenario_X720.py --mode smoke
python tools/generate_scenario_X720.py --mode 720
```

默认模式为 preflight，不启动 STK。smoke 先运行离线测试，再生成 3×4 星、600 秒场景。720 自动顺序执行离线测试、smoke、18×40 星母场景；任一步失败即退出。不要并发运行。默认隐藏自建 STK 窗口；需要查看时显式加 --visible。不会关闭已有非空场景。

## 验收内容

- 18 个轨道面，RAAN = 10p 度；每面 40 星、面内间隔 9 度。
- 同一个全局正相位方向：u(p,k) = 0.5p + 9k 度；不接受逐面对正负号取绝对值。
- 显式 TwoBody、J2000、km/deg/sec、UTCG，epoch 为 2026-01-01 00:00:00 UTC。
- STK 实际状态与独立圆轨道解析状态交叉检查；不能只核对生成参数。
- 使用本机 Earth.cb 的 GM，并记录文件 hash；不混用不同引力常数。
- 核对初始轨道以及 0、17.3、60、600 秒和窗口末端的状态，检查能量与角动量。
- 720 场景通过后提取前 4 面的 160 星、前 6 面的 240 星严格子集，保留母场景 ID 与边界标记、父文件 hash。子集不等于周期拼接的新星座。

## 输出与限制

每次 STK 运行创建 outputs 下新的时间戳目录，不覆盖旧输出。包括 gate_status.json、constellation_config.json、manifest、几何验收、稀疏星历验收、STK 场景及 provenance。失败保存 failure.json。

PASS_SAMPLED_GEOMETRY 只代表上述采样几何范围通过，不代表连续 LOS/FOV、完整链路寿命、固定骨干可维持性或网络连通性已通过。子集外部节点被移除，也不保证子集可直接用于后续网络实验。

离线测试覆盖正确星座、错误 20°/1° RAAN、交替相位、全局错误符号、缺星/重号、单位或 epoch 错误、非法数值、星历扰动和子集篡改。离线测试通过不能替代本机 STK 实测。

## 本机验证记录（2026-09-18）

- Conda pytorch / Python 3.9：23 项离线测试全部通过。
- STK 12 星 smoke 实测通过，目录：outputs/gate_a_smoke_20260918T105101_938414Z。
- 48 个位置/速度样本通过；最大位置误差约 8.10e-8 km，最大速度误差约 7.75e-11 km/s。
- 已修复本机 STK COM 空指针判断、传播区间初始化和版本查询接口；起止时间、单位、传播器均回读核验。
- 本轮没有运行完整 720 星生成。720 母星座与 160/240 子集的 STK 实测仍待 --mode 720 完成；不要把 smoke 的 PASS 当作 720 已通过。
- 历次失败目录保留用于追溯；判断当前状态应使用上面明确列出的成功目录。

版本查询使用官方 [GetSTKVersion](https://help.agi.com/stk/12.10.0/Subsystems/connectCmds/Content/cmd_GetSTKVersion.htm) 命令。
