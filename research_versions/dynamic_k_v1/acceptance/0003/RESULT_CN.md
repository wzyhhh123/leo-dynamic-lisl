# N0c 科学合同语义补充结果（仅静态验证）

本轮完成新版本科学合同语义补充。25 项文档/schema 静态检查 PASS；不代表 N1a、N1b 或任何科学 Gate PASS。
未修改生产代码和历史 Gate 资产，未运行仿真、训练或主实验。合同、配置和 schema 均仍为草案。

## 连续修订编号

用户请求中的 0002 已被此前重复 PNG 清理记录使用。本轮按连续、追加且不覆盖封存记录的机制使用 0003，父记录为 0002。
版本起点、修订 0001/0002 和原基线 seal 保持原字节；本轮不重编号或改写既有记录。

## 五项语义补充

1. 主 K 只统计真实 ACTIVE 且可接纳新业务的动态连接实例，每条双端连接计一次；不要求当时有待发业务。DRAINING 不进入主 K，其连接数及 SETUP 状态/预约资源分别计量。
2. 全部 320 个动态终端按真实状态在共同 [0,T] 内计费；初始状态与剩余阶段时间沿实际输入继续，不虚构 t=0 建链。窗口外预建立能耗不并入本窗口，四能耗态 ACTIVE 驻留包含执行态 DRAINING，保留五执行态驻留以便核对。
3. 结果 schema/未执行模板预留 K 与 SETUP 时间序列、四/五态驻留、能耗、评价完成、业务全部交付、终止原因和后续 fluid 年龄字段。未知结果为 null；评价正常完成和全部交付是独立结果。
4. N1a 仅计划实现固定时域/能耗核算；N1b 才计划实现已交付 fluid bit 年龄追踪。两阶段均尚未实现或授权，未选择年龄搬运数据结构。
5. T_A、T、tau_res、R_min、alpha、D_ref、E_ref 和新增数值容差均保持 null；控制数值及算法选择保持未决。功率数值沿用已确定表，没有新增科学数值冻结。

## 修改文件与原始字节哈希

| 项目相对路径 | 修改前 SHA-256 | 修改后 SHA-256 |
|---|---|---|
| research_versions/dynamic_k_v1/configs/research_v1_DRAFT.json | b8b86d1abc3db1765ee23123bfafaa99c419731cb046984458baa962980e8102 | 71ab1ddfb38cbd9d2804c01a67c131a2e937fc2290293170922d0ef60b7c5742 |
| research_versions/dynamic_k_v1/contracts/research_contract_v1_DRAFT_CN.md | 7aca0acd0e28164898582ebfa1e12e83e1b84d5a7e8372c5dbc7309987da8bcc | 2dc51c9f844ef28f6a2dede0e1ce253c89bbf2fdd4bb845c57e18907af0a52f5 |

原始修改前快照保存在 before/contract_before.md 和 before/configuration_before.json，不转换编码或换行。
新增结果 schema：research_versions/dynamic_k_v1/schemas/research_result_v1_DRAFT.schema.json。
新增未执行模板：research_versions/dynamic_k_v1/schemas/research_result_v1_DRAFT.template.json。
所有新增证据及修改的 before/after 大小、哈希由修订 0003 逐项登记，修订自身由交付时的独立哈希固定。

## 静态验收与旧资产保护

static_validation_report.json 保存 25 项检查、检查器/合同/配置/schema/模板哈希、命令及 UTC/北京时间。
包含模板 schema 验证、两种完成状态组合的结构检查、错误 DRAINING/窗口计费/驻留状态等输入的拒绝检查。内存中的结构 fixture 不是仿真或测量结果。
schema 仅验证字段形状与类型，不能证明时域覆盖、终端状态守恒、业务守恒或计费数值正确。
preseal_change_audit.json 对完整文件集合与原始字节进行了全量核对：5,810 个历史文件、15,219,456,380 字节完全未变；除两份获授权草案外的现有版本资产未改写。
封存后再次运行版本完整性验证，只有其 PASS 才交付新的修订哈希；最终验证输出与外部哈希见本轮交付消息，不将清单或记录自哈希递归写入自身。

后续阶段均不在本轮执行范围内。完成 N0c 后停止，等待用户审核。

报告生成 UTC：2026-10-10T04:03:17.076821+00:00；北京时间：2026-10-10T12:03:17.076821+08:00.
