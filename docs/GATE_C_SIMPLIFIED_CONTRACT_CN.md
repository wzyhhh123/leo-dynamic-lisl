# Gate C 最小物理模型合同

版本：`gate_c_simplified_terminal_model_v1`

## 1. 研究边界

Gate C 只回答三个问题：

1. 哪一个具体动态终端对在几何上能够连接；
2. 结合两端终端占用和 setup 后，当前是否还来得及完成建链；
3. 执行切换时会发生 BBM、真实空闲第二终端 MBB、链路中断或网络分区中的哪一种后果。

Gate C 不评价一次切换是否能改善业务性能。流量、队列、路由、matching、MPC、RL 和网络收益判断均不属于本 Gate。

## 2. 冻结输入

- 轨道：synthetic TLE + SGP4/WGS72；原生状态为 TEME-of-date。
- 卫星级父候选：5000 km diagnostic cutoff 与球形地球遮挡 LOS。
- 父可见区间：半开区间 `[start_s, end_s)`，保留 left/right-censored 语义。
- 执行器：已有 `TerminalExecutor`，包括双边原子预约、terminal-level BBM、空闲第二终端 MBB、DRAINING、LINK_DOWN/RETARGETING/ACQUIRING/LINK_UP、自然失效、stale-event 防护和原子命令批次。
- 网络策略接口：`STRICT_CONNECTED` 与 `BOUNDED_OUTAGE(T_max)`。

5000 km 不是 LCT 硬件量程；right-censored 的 600 s 端点是预测资产边界，不是自然失效时刻。

## 3. 理想 RTN 姿态

对同一 TEME 时刻下的卫星位置、速度：

\[
\hat{R}_i=\frac{\mathbf r_i}{\|\mathbf r_i\|},\qquad
\hat{N}_i=\frac{\mathbf r_i\times\mathbf v_i}
{\|\mathbf r_i\times\mathbf v_i\|},\qquad
\hat{T}_i=\hat{N}_i\times\hat{R}_i.
\]

必须验证三轴单位化、两两正交且满足

\[
\hat R_i\times\hat T_i=\hat N_i.
\]

这里采用 deterministic ideal RTN / nadir-pointing attitude。这是网络层研究假设，不代表 OneWeb、Starlink 或其他商业卫星的真实姿态控制规律。

## 4. 终端安装

安装方向用 RTN 分量写入版本化配置：

\[
FWD\_INTRA=+T,\quad BWD\_INTRA=-T,\quad D1=+N,\quad D2=-N.
\]

动态终端数量仍为每星 D1/D2 两个。固定同轨终端不进入动态终端占用。D1/D2 不按轨道面编号硬编码邻居；能否连接只由实时状态和 FoR 判断。

`D1=+N、D2=-N` 是为了让两个端口具有不同空间能力而采用的简化安装假设，不是已校准的商业终端安装数据。

## 5. 双端圆锥 Field of Regard

目标视线单位向量为

\[
\mathbf u_{ij}(t)=\frac{\mathbf r_j(t)-\mathbf r_i(t)}
{\|\mathbf r_j(t)-\mathbf r_i(t)\|}.
\]

对 terminal pair `((i,k),(j,l))`，必须同时满足

\[
\angle(\mathbf b^{TEME}_{i,k},\mathbf u_{ij})\le \rho_k,
\]

\[
\angle(\mathbf b^{TEME}_{j,l},\mathbf u_{ji})\le \rho_l.
\]

实现使用等价的点积/夹角判据，并区分：

- `FOR_FAIL_LOCAL`：本端失败、对端通过；
- `FOR_FAIL_REMOTE`：本端通过、对端失败；
- `FOR_FAIL_BILATERAL`：两端都失败。

FoR 半角必须配置化。v1 默认 `90°`，状态为 `sensitivity_only_not_hardware_calibrated`；同时支持 `60°/75°/90°` sensitivity 配置。该数值不得用于宣称某型终端的真实扫描范围。

## 6. terminal-pair 候选与连续区间

Gate A 每个卫星级父候选 `(i,j)` 在 Gate C 展开为：

\[
(D1,D1),(D1,D2),(D2,D1),(D2,D2).
\]

每一种组合分别计算

\[
\mathcal F_{ik,jl}(t)=F_{satellite}(t)\land F_{FoR,i,k}(t)\land F_{FoR,j,l}(t).
\]

只输出 `F=1` 的 maximal half-open intervals。边界搜索使用 2 s 扫描和 Brent root refinement，并用 1 s 扫描做分辨率一致性审计。该审计证明当前资产在两种分辨率下结果稳定，但不是对任意亚采样相切事件的数学完备证明。

## 7. setup 与寿命

Gate B 继续负责 drain-aware ready time。两端可并行重指向、捕获在两端重指向都结束后开始时：

\[
t_{ready}=\max(t^{free}_i+\tau_i,t^{free}_j+\tau_j)+\tau^{acq}_{ij}.
\]

对当前 terminal-pair 区间末端 `t_end`，必须返回：

\[
L_{remain}=t_{end}-t_{now},\qquad
L_{usable}=t_{end}-t_{ready}.
\]

物理合法性只要求：

\[
t_{ready}<t_{end}
\]

并使用 `1e-9 s` 数值裕量。不得增加 10 s、30 s 等经济意义上的最短可用时间；是否值得为短窗口支付 setup 代价留给 Gate E/F。

## 8. tracking 与 PAT

v1 明确假设：满足 FoR 的候选在该 terminal-pair 区间内能够持续跟踪。配置必须记录：

- `tracking_rate_limit = not_explicitly_modeled_v1`；
- `tracking_acceleration = not_modeled_v1`。

不填写无来源的角速度或角加速度上限。

## 9. 切换后果

合法 CONNECT 交给已有 `TerminalExecutor` 执行：

\[
ACTIVE\rightarrow DRAINING\rightarrow LINK\_DOWN\rightarrow
RETARGETING\rightarrow ACQUIRING\rightarrow ACTIVE.
\]

Gate C 的统一结果至少包含：`transition_mode`、`ready_time`、`link_up_time`、`old_link_down_time`、`outage_occurs`、`outage_start/end/duration`、`partition_occurs`、`recovery_time`、active/admit graph 最大 component count。

Gate C 只报告真实后果；`STRICT_CONNECTED` 或 `BOUNDED_OUTAGE(T_max)` 决定操作层是否接受。v1 不冻结正式 `T_max`。

## 10. Z_ref

只构造一个 deterministic、traffic-agnostic、adjacent-plane-oriented 的连通参考拓扑：

- 固定同轨 ring 作为 plane 内连接；
- 在每一对连续轨道面之间选择一个当前 bilateral FoR 可行的明确 terminal pair；
- 不允许端口双占或同一卫星对并行动态链；
- 不要求占满动态终端。

输出动态链数、占用率、空闲率、桥数、连通性、remaining/usable lifetime 分布。若区间 right-censored，寿命只解释到预测窗口末端。

## 11. Gate C 关闭条件

RTN、distinct D1/D2、双端 FoR、terminal-pair 连续区间、remaining/usable lifetime、BBM/MBB、切换连通性报告、连通 Z_ref、两轮确定性回放、Gate A/B 冻结哈希和全部回归测试均通过后，允许记录：

`Gate C = PASS under simplified parametric terminal model`

同时必须保留：`detailed PAT / tracking / optical link budget are outside Gate C v1 scope`。通过后停止，不自动进入 Gate D。
