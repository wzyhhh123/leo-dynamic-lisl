# C0 Geometry ↔ Gate B 接口报告

状态：**PASS**。

连续区间通过 `VisibilityCatalog` 读取，按卫星对索引。可用语义为半开窗口 `[start_s,end_s)`，并保留 `left_censored/right_censored`。候选池只过滤为 inter-plane，不限制相邻轨道面；terminal candidate 显式展开为 D1/D2 对。

CONNECT 前先检查当前窗口，再由 Gate B clone 计算包含已有 TX drain 的 ready time。只有 `ready < end` 才返回真实 `Connect` 对象。提交后 Gate B 自己调度 setup expiry / active link expiry，没有第二套链路生命周期。

600 s pilot 的 right-censored end 在接口中标作 `prediction_horizon`。这意味着“当前资产只能保证到这里”，不意味着真实 LOS 在 600 s 结束。

确定性测试覆盖窗口起止边界、跨面过滤、ready=end、ready>end、硬件 hook、setup 中 expiry abort 和 replay。机器证据见当前 Gate C 输出的 `report.json`、`representative_transition_traces.json` 与 hashes。

当前接口不计算 FOV、姿态或 slew；这些参数保留为 C5 hook，hardware calibration 为 PENDING。
