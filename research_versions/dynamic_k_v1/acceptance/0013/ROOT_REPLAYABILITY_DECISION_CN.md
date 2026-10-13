# N4-P0D：可重放性决定

选择**方案二：无法忠实恢复原0011完整native根**，状态 `ORIGINAL_NATIVE_ROOT_NOT_RECOVERABLE`。保留原期望指纹、0011守恒失败、0012绑定STOP及本轮新诊断不匹配，不替换任何历史锚。

检查0011所有登记新增文件及acceptance下JSON字段，没有完整native checkpoint、完整t=3 root_view.state_json或可恢复对象图。运行时checkpoint方法是deepcopy并返回内存对象；方法存在与单进程重放测试PASS，不代表该失败根已经持久保存。失败记录的网络/能耗位于t=6，年龄位于ADD后同时间结算的t=3，不能把这些不同阶段状态拼成原始根。

唯一新诊断严格停止于t=3。实际SHA `06f3803e0c74ca9ba4a45a04ac5efada773ad988e044f7323083cc3421fc2adb` 不等于原期望 `ba301c6b0d92b96b8490fe28b24322e254377aea01adffd0c368653daa3f01f6`。因此它**不是0011失败的成功重放**。本轮完整记录hash原文和摘要，仍不把这些JSON称为native checkpoint。

已定位的审计顺序差异、部分业务字段一致以及同时间结算的解释，不能弥补整个原始状态缺失。原0012未保存实际hash/原文，故其差异的完整归因UNVERIFIABLE。本轮不采取方案一，不申请在现有不匹配根上直接继续旧失败诊断。

## 建议的下一次最小授权

另行授权“新独立可重放根封存及有限守恒诊断”，建立新的场景ID，明确不是0011锚的替代。

1. 固定已验收源码与原始几何/trace输入，记录Python/依赖版本、环境、进程hashseed/探针、构造器、初始化参数及全部源文件SHA；每个工程条件保持PILOT_ONLY，正式参数仍null。
2. 在任何动作前同时保存完整live与净化根的**可恢复native checkpoint**、原始hash preimage、原trace及其字节、observed_prefix、forecast/action参数、所有绑定；只保存视图JSON不达标。
3. 明确持久化格式及版本，保留float的原始位表示、Fraction分子/分母、dict插入顺序、列表/heap顺序、所有补偿累加器、传播与终端agenda、预约/links/事件计数器、N1a驻留/游标/历史、FIFO/cohort/年龄/误差envelope和审计日志。SGP4 native对象必须采用经验证的重构或支持的持久化方案；模型TLE/config/SHA全部绑定。不能用当前JSON解析后随意推测原类型。
4. 文件读取租约/路径/handle需显式重新绑定和逐字节验证，不持久化不可用的OS handle。恢复协议须证明不会重置状态、结算游标或未来已承诺事件。
5. 在独立进程从checkpoint恢复，要求严格原hash、全部状态和重放结果一致；固定seed只是新场景的可重放条件，不用于搜索原0011未知seed。若需要冻结内核改动或重新规范hash，先停止提交最小方案，不能擅自实施。
6. 恢复验收通过后，才按新授权限额提交一个指定ADD并追踪至t=6或首次失败；先记录同一时刻的动作前、提交后、结算后阶段。保持原守恒公式与容差，禁止跳过断言。原读取路径与HandleReaderLease可做有限配对，使用同一封存新根。

若新独立根不能复现相同守恒失败，结论必须是“新场景未复现”，原0011失败继续保留，不宣称其已消除。此次未实施持久化接缝、根重建协议或上述未来诊断；本轮没有预测、控制动作或容差修改。

## 审核边界

0013仅为原始根证据审计和一次NEW_DIAGNOSTIC_ATTEMPT。后续阶段需要另行人工授权。保留 `STOP_ROOT_BINDING_MISMATCH`、`UNRESOLVED` 和无N4-P0 Engineering PASS；不自动恢复完整epoch、catalog、24次/840分支、GNN或MAPPO。
