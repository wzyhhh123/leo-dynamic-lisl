# Gate C 最小物理模型验收结果

结论：**Gate C = PASS under simplified parametric terminal model**。

验收资产：`outputs/gate_c_simplified_20260922T064019_313843Z`。

Gate D 在接口上已经具备启动条件，但本轮按合同停止，没有实现或运行 traffic、queue、routing、matching、MPC、RL 或主性能实验。

## 1. PASS 项

- RTN：160 星在 `t=0/300/600 s` 的 R/T/N 全部单位化、正交、右手且确定性一致。
- 安装：D1=`+N`、D2=`-N` 从配置加载，两个端口不再是等价资源槽。
- FoR：双端判据生效，并能分别返回 local、remote、bilateral failure。
- 区间：卫星级父窗口已细化为 terminal-pair maximal intervals。
- lifetime：明确输出 `remaining_lifetime_s` 与 `usable_lifetime_s`；`ready < end` 接受，等于或超过 end 拒绝。
- 切换：已有 Gate B 的 terminal-level BBM 与 genuine idle-terminal MBB 保持正确；FoR 不可行的空闲第二端口不能形成假 MBB。
- 连通性：切换后果继续通过 active/admit graph trajectory 报告，并保留两种 operational policy。
- Z_ref：生成了一个明确 terminal-pair、相邻轨道面导向、traffic-agnostic 的连通初始拓扑。
- 回归：两轮各 82 项测试全部通过；Gate A/B 冻结文件哈希全部未变。
- 确定性：terminal-pair interval 资产重复生成逐字节一致。

## 2. 候选空间审计

范围为冻结的 4-plane/160-satellite 子场景，主统计时刻 `t=0 s`。

| 指标 | 结果 |
|---|---:|
| satellite-pair candidates | 1996 |
| 展开后的 4× terminal-pair candidates | 7984 |
| bilateral FoR feasible terminal pairs | 1996 |
| FoR pass ratio | 25% |
| adjacent plane-gap terminal pairs | 1062 |
| non-adjacent plane-gap terminal pairs | 934 |
| 全窗口 terminal-pair intervals | 2742 |
| interval duration minimum | 3.581 s |
| interval duration median | 600 s |
| interval duration mean | 435.584 s |
| t=0 usable lifetime minimum | 4.932 s |
| t=0 usable lifetime median | 598 s |

D1 与 D2 的候选 incidence 均为 1996，比例为 1.0；两者没有出现全局方向偏置。每颗卫星把 D1/D2 合计后至少有 22 个、最多 27 个候选，因此动作空间没有整体塌缩。部分具体卫星在当前时刻只有 `+N` 或 `-N` 一侧端口有候选，这是两端半空间安装产生的预期空间区分。

当前 1996 个可行 terminal pair 恰为每个 satellite pair 的四种组合中有一种通过，因此 25% 只描述 `±N + 90°` sensitivity 配置的结构结果，不能解释为真实终端成功率。

## 3. terminal-pair interval 数值一致性

- 2 s coarse scan：2742 个区间；
- 1 s fine scan：2742 个区间；
- 分组区间数不一致：0；
- 最大边界偏移：`0.000341 s`；
- 验收上限：`0.01 s`。

因此当前资产通过分辨率一致性检查。该结果不是对任意短暂相切事件的形式化无遗漏证明。

## 4. Z_ref

Z_ref 使用 160 条固定同轨 ring 边和 3 条动态跨轨链连接四个轨道面：

1. `(X0_27,D1) — (X1_27,D2)`；
2. `(X1_11,D1) — (X2_11,D2)`；
3. `(X2_11,D1) — (X3_11,D2)`。

动态终端占用率为 `1.875%`，空闲率为 `98.125%`，初始图连通。三条动态跨面链同时也是三条 bridge，因此这个最小 Z_ref 很稀疏，适合作为共同初始拓扑，但不应被解释为鲁棒拓扑或性能最优拓扑。

三条选中链都 right-censored 于 600 s。报告中的 `remaining=600 s`、`usable=598 s` 只表示它们覆盖完整预测窗口，不能声称自然链路寿命就是 600 s。

在该 Z_ref 下，排除已存在的三个卫星对后，有 1993 个当前 terminal-pair 候选；其中 1913 个具体端口对在两端都真实空闲，projected MBB-feasible fraction 为 `95.986%`。这只是端口和 FoR 层面的投影，不包含未来业务收益或释放旧链的网络代价。

## 5. 切换后果样例

BBM fixture：旧链在 `t=0` LINK_DOWN，新链在 `t=2 s` LINK_UP；出现 2 s 可恢复分区，active/admit graph 最大 component count 均为 2。

MBB fixture：新链在 `t=2 s` LINK_UP 后旧链才 LINK_DOWN；无分区，active/admit graph component count 始终为 1。

这些结果验证执行语义和报告接口，不是业务性能实验。

## 6. 假设

- deterministic ideal RTN / nadir-pointing attitude；
- D1=`+N`、D2=`-N` 为简化安装；
- `90°` conic FoR 为 sensitivity-only；
- FoR 内 tracking capability 在 v1 中视为充足；
- 两端 retarget 并行，acquisition 等两端完成后开始；
- audit 使用 1 s retarget + 1 s acquisition synthetic fixture；
- 5000 km 仍是 diagnostic cutoff。

## 7. 有意延期与已知限制

延期：detailed acquisition FoV、PAT controller、gimbal dynamics、tracking angular rate/acceleration、pointing jitter、Sun keep-out、detailed body blockage、optical link budget、variable optical rate。

已知限制：FoR 与 setup 数值尚未硬件校准；600 s 预测窗口导致大量 right-censoring；Z_ref 是最小连通树式跨面结构，存在三条 bridge；当前 Gate 只解决物理可行性与执行后果，没有回答切换是否值得。

## 8. Gate D 状态

`Gate D technically ready = true`。

这表示 traffic/queue/routing 可以在明确的 terminal-pair 几何和执行接口上设计；本轮没有启动 Gate D。
