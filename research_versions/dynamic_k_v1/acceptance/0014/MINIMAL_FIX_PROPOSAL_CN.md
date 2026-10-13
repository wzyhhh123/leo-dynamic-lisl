# 新场景最小修复建议：本轮不实施

首要建议是另行授权冻结D2的**传播事件有效时刻与微步选择**专项修复。已有精确账本证明，只改聚合求和不足以消除本场景的1.0902878102569957e-6 bit残差；放宽1e-6容差不是本轮方案。

最小候选差异，**仅为审阅草案，未应用、未验收**：

```diff
 # transition_service_orchestrator.py: _settle_propagation_rate_events
- and self.propagation_agenda[0].time_s <= self.now+1e-12):
+ and self.propagation_agenda[0].time_s <= self.now):

 # _next_time: retain genuinely positive short intervals
- future = [value for value in candidates if value > self.now+1e-13]
+ future = [value for value in candidates if value > self.now]
```

必须配套审计advance_to的终止过滤、微步及重复同时间事件处理，确保这些极短正区间不会被跳过或无限循环。只删除第一处epsilon而保留前向过滤，可能把略晚事件漏过或迟处理，不能宣布两行差异天然足够。Gate B真实状态机、TX与D2在途语义不得连带改变；无需改物理catalog、拓扑动作或FIFO服务次序。

目标是事件在真实nominal浮点时刻生效，保持同一commodity服务量分配与原连续注入率，消除提前生效造成的额外尾流。若需要其他事件合并策略，必须证明脉冲积分及cohort原始注入时间保持正确，不能把未来事件提前而无体积补偿。

候选验收应包含：本独立封存根的原失败对照；相差不足1e-12的正/负到达率事件；多边合流；极短正区间；多跳切换尾流；原HOLD及N1a/N1b/N2/P0相关回归。修复后的服务数值变化必须完整披露为数值语义修复，不能声称状态逐字段等同于原错误推进。全部原冻结资产保持原文件，实施须按新授权指定的版本/接缝保护方式另建，不能在本轮偷偷改内核。

次要建议是独立观测层同时保存A−(D+Q+I)、有符号fsum及精确IEEE参考，便于解释消去误差；这只改善报告，不是本失败的修复，也不能替换原断言。本轮已经记录这些参考但没有替换生产状态。

不建议简单限制arrival amount为available再继续交付：这会改变实际服务量，必须同步修订传播/FIFO及守恒语义。也不建议隐藏负值、清除cohort或增加容差。

若未来确需讨论容差，应先给出可推导的事件偏移×率误差界及跨commodity/edge累积界，并用明确真实1bit丢失负向测试证明仍拒绝；本轮测得的逐调用绝对误差界只适用于当前已保存有限轨迹，不足以冻结通用容差。

本轮未实施任何上述差异，不自动恢复epoch或主预实验。需要另外人工授权内核/数值接缝修复。
