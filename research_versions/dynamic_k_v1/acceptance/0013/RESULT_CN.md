# 0013 N4-P0D 中文结果

结论：`STOP_ROOT_BINDING_MISMATCH`，选方案二 `ORIGINAL_NATIVE_ROOT_NOT_RECOVERABLE`。完成授权内的根溯源、一次新诊断和离线差异审计；未获得ROOT_RECONSTRUCTION_PASS或N4-P0 Engineering PASS，业务守恒根因仍为UNRESOLVED。

本轮实际根SHA：`06f3803e0c74ca9ba4a45a04ac5efada773ad988e044f7323083cc3421fc2adb`。原锚 `ba301c6b0d92b96b8490fe28b24322e254377aea01adffd0c368653daa3f01f6` 保持原样。hash原文和输入/状态摘要已在严格比较前持久保存。只构造一次live根，推进0→3；净化克隆未进行预测，控制动作提交数0。

明确差异：315条同阶段FIFO舍入审计项的精确多重集相同、追加顺序不同，首差异索引4、t≈0.004430762292133393。原代码采用未排序set遍历并将列表原序纳入hash。本轮未改排序、未拼接或重试根hash、未搜seed。原完整preimage缺失，不能宣称顺序是整个指纹不匹配的唯一原因；0012未保存actual，不能声称完整解释其历史字段。

另一个容易误判的边界：原失败年龄快照虽仍为t=3，却是ADD后的同时间结算阶段，cursor44/338条；新根为动作前cursor43/315条。尾部22条FINAL及1条REPORTED_DELIVERY解释额外的误差envelope；离线精确减法吻合，未写回状态。原与新0→3观察前缀、已保存各键A/Q/I/D和13个FIFO年龄字段一致；原t=3完整native根、能耗账本和agenda不可验证。

已交付独立文件：

- ROOT_HASH_PROVENANCE_CN.md：真实构造链、输入、序列化、阶段与A–F分类。
- ROOT_RECONSTRUCTION_DIFF.json：逐字段差异、首差异、同时间结算校正与UNVERIFIABLE项。
- ROOT_REPLAYABILITY_DECISION_CN.md：方案二及另行封存独立可重放根的最小授权建议。
- NEW_DIAGNOSTIC_ATTEMPT.json、actual_root_hash_preimage.json、actual_root_summary.json、root_comparison_stop.json及离线明细：原始新诊断/STOP证据。

此次没有修改实现内核，仅新增审计工具、文档、诊断证据和独立范围配置。准备阶段两个辅助脚本错误（语法括号、保留修订记录不在文件清单）均在任何根构造前修正，没有借此重试根。未运行历史仿真测试或新增场景：本轮授权仅一个根；历史源码/测试期望/证据的原字节由完整版本审计核对。旧F3失败及0011守恒失败保持原样。

版本保护：开始前0012/起点/完整父链及6105文件PASS；封存前对所有旧资产重新原字节清点，要求0修改、0删除、0重命名，只允许新版本命名空间新增。清单见preseal_change_audit.json；0013连续记录封存所有新增文件，记录SHA由独立命令输出。封存后完整独立验证使用该新SHA；最终校验结果以工具输出为准，不将文件保护PASS解释为科学或工程Gate PASS。

不恢复epoch、不运行守恒分支、不实施建议修复。完成后停止等待人工审核。
