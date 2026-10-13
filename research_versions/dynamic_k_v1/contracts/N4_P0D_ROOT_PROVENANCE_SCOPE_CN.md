# N4-P0D 根指纹审计边界

人工授权仅回溯0011封存根及0012重构差异，执行一次新的只读t=3根构造并先存hash原文、实际SHA及绑定摘要，再做严格比较。旧期望根SHA保持 `ba301c6b0d92b96b8490fe28b24322e254377aea01adffd0c368653daa3f01f6`。

所有旧内核、合同、修订、输入、验收结果和容差保持封存原字节。新根必须标注NEW_DIAGNOSTIC_ATTEMPT，不是旧失败重放。不同指纹立即停止，不提交ADD，不运行预测，不自动再构造一个根。之后仅允许读取保存证据进行离线差异分析和报告。

本轮不改hash规范，不排序回写历史审计项，不更换锚，不开展catalog候选遍历、MPC epoch、24次预实验、840分支、GNN、MAPPO或业务守恒修复。正式科学参数保持null。审计/哈希检查PASS不授予N4-P0 Engineering PASS，也不解决业务守恒问题。缺乏完整native checkpoint时明确ORIGINAL_NATIVE_ROOT_NOT_RECOVERABLE，未保存历史字段标记UNVERIFIABLE。

采用0013连续追加封存，父锚为0012独立SHA，基线和版本起点不覆盖；完成后停止等待人工审核。
