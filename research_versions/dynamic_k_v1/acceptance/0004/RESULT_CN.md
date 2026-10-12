# Stage N1a 工程结果报告 — 修订 0004

N1a 工程验收 PASS：固定时域、真实终端状态积分、四能耗态/五执行态驻留时间和所需业务/拓扑指标已实现。新增测试 25/25 PASS；历史回归实现前后均为 96/97 PASS，同一项旧 F3 失败，没有新增回归。本结论不是 N1b、N2、科学 Gate 或性能结果 PASS。

## 前置验证与文件边界

开始实现前，完整验证独立保存的版本起点 `ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691` 和用户指定父修订 0003 `7c9fa913a72ab740dfff233513c766ded57326fad2906c259d8ba56a3998baeb`，结果 PASS：基线 5810 文件、版本验证 5837 文件、排除 202，无未登记变更。

旧 Gate 合同、源码、测试预期、历史输出和 manifest 均不修改。正式 T_A/T、tau_res、R_min、alpha、D_ref、E_ref、算法选择及正式容差仍为 null；正式实验禁用，生产 runner 未接入。

全部新增文件都位于 `research_versions/dynamic_k_v1/`：

- `runtime/__init__.py`、`runtime/n1a.py`、`runtime/bindings.py`、`runtime/README_CN.md`：独立接口与使用说明。
- `tests/test_n1a.py`：解析、实际 Gate B/D2 集成、重放、数值与错误输入验证。
- `schemas/n1a_engineering_result_v1.schema.json`：专用工程测量 schema，保留旧研究 schema 和未执行模板。
- `acceptance/0004/prepare_candidate.py`、`run_n1a_acceptance.py`、`run_regression.py`、`finalize_revision.py`：候选绑定、测试、历史回归和追加封存工具。
- `acceptance/0004/before/contract_before.md`、`configuration_before.json`：修改前原始字节副本。
- `acceptance/0004/implementation_manifest.json`、`n1a_test_report.json`、`engineering_examples.json`：测试前固定清单、测试报告和解析案例。
- `acceptance/0004/regression_before.json`、`regression_after.json`、`regression_comparison.json`：旧失败的前后比较。
- `acceptance/0004/pre_implementation_verification.json`、`version_protection_tests.json`、`preseal_change_audit.json`、本报告：保护与验收证据。
- `revisions/0004/record.json`：连续追加的修订记录，登记全部新增文件和两份草案的前后字节数/SHA-256。

修改文件仅两项：`contracts/research_contract_v1_DRAFT_CN.md`、`configs/research_v1_DRAFT.json`。更新 N1a 授权/实现状态和接口说明；配置仍为 DRAFT_NOT_FROZEN，工程验收以独立证据为准。不存在生产代码或旧路径修改、删除、重命名。

## 实际接口与核算方法

`TerminalEnergyLedger(executor).capture/metrics` 从 t=0 真实状态出发，消费 Gate B 每条完整状态日志，以事件时间差累加全部 320 个动态终端。相同时间戳的中间变化驻留时间为零；最后无事件区间照常积分。已有 ACTIVE/SETUP/DRAINING 按剩余真实状态计费，不生成初始建链动作。日志截断/改写、终端遗漏和未记录的直接状态改动会被拒绝。

功率 IDLE=5、RETARGETING=40、ACQUIRING=40、ACTIVE=45、DRAINING=45 W。四能耗态 ACTIVE 包含五执行态 ACTIVE+DRAINING；五态单独保留。DeltaE 按各态 `(P-5)*驻留时间` 求和，与 `E-320*T*5` 交叉校验，避免纯待机浮点相消产生伪负值。保持 Gate B DRAINING 的传输、传播和释放语义。

`FixedHorizonEvaluator(engine, T_s, time_tolerance_s, energy_tolerance_J, business_tolerance_bits, evidence_binding)` 使用原 D2 `advance_to`，所有评价均推进到显式 T，不因业务排空停止。`advance_to(t)` 支持检查点；`run()` 到 T；`clone/checkpoint/restore` 同时保留业务引擎、事件游标和累计能耗，不在恢复点重启计费窗口。恢复接口为内存状态，不提供磁盘 pickle 装载。

`EngineeringBinding.verify` 在测试前及评价推进/测量前核对候选清单与原始文件哈希。清单绑定版本起点、基线 seal、父修订 0003、候选 0004 的实现和合同/配置；运行结果再由修订 0004 绑定。清单 SHA-256：`227043a6bcf318846bbc2e854130613b49082ef6a7e17f3913160f24f40456ad`。

`validate_measurement` 核对数值有限性与范围、320 个终端逐项时长、总驻留、四态/五态映射、能耗/增量公式、业务守恒、R_del、完成标志、拓扑计数以及 K/SETUP 时间积分与驻留的一致性。示例另外通过 JSON Schema 校验。

输出 E_LCT/DeltaE、逐终端及全网五态/四态驻留、K_active_admissible(t)、K_draining(t)、setup_connection_count、setup_terminal_count、retargeting/acquiring 数、setup_reserved_terminal_count、J_T、N_T、R_del、正常到 T 标志、全部业务交付标志及数值容差。

主 K 按真实双端 ACTIVE 连接实例计数，排除 DRAINING。SETUP 连接数表示有 RETARGETING/ACQUIRING 终端的预约连接；等待旧链释放的预约仍计入预约终端数，状态数和预约数允许重叠。J_T 为未加权 N=A-D 的事件分段积分，独立于旧 commodity.weight 加权目标。N_T 包含 queue 和 in-flight。

N1b 年龄累计和已交付 fluid 平均时延均为 null，绝不以 J_T/已交付量替代。空输入 R_del=1，不生成时延样本。正常到 T 与全部交付独立；未正常到 T 的工程检查点不报告完整窗口已覆盖。

## 解析测试及验算

25 项新增测试通过。覆盖用户要求的 12 类最低验收，包括全部待机、单终端手算、DRAINING、逐终端时长、提前排空、初始 ACTIVE、真实 ADD/DROP/BBM/MBB/abort/expiry、同时间戳、未排空、clone/恢复/重放、非负增量及数值/跨字段检查。额外覆盖未加权 J、初始 SETUP/DRAINING、绑定摘要错误、输入修改、日志丢失、拒绝动作和真实传播交付。

| 工程案例 | T | E_LCT | DeltaE | 业务结果 |
|---|---:|---:|---:|---|
| 全部 320 终端 IDLE | 7.5 s | 12000 J | 0 J | 无业务，正常到 T |
| 两端已知序列，各 IDLE1/RETARGET4/ACQUIRE3/ACTIVE2 s | 10 s | 16650 J | 650 J | 单端 375 J，其余 318 端各 50 J |
| 初始 ACTIVE 链在 6 s 自然失效，业务 2 s 排空 | 10 s | 16480 J | 480 J | J_T=10 bit·s，N_T=0，R_del=1，仍评价到 10 s |
| 无路由，10 bit 在前 1 s 注入 | 4 s | 6400 J | 0 J | J_T=35 bit·s，N_T=10 bit，R_del=0；正常到 T，业务未全交付 |
| D2 实际 DRAINING 与传播，0.5 s 停止接纳，1.5 s 释放 | 4 s | 6520 J | 120 J | 交付5/剩余5 bit，R_del=0.5，J_T=21.25 bit·s |

所有测试 T 和容差仅为工程输入；没有冻结正式科学值。业务提前排空案例中，318 个 IDLE 终端与两个终端的后续自然失效和剩余待机区间均计费到 T。

## 历史回归与版本保护

适用回归覆盖 Gate B、D1、D2、in-flight 闭合、轻量 clone、checkpoint 对齐、drain continuation、联合快照和旧搜索策略。实现前后各 97 项，96 PASS、1 FAIL、0 ERROR、0 SKIP。既有失败为 `StructuralPolicyProbeTests.test_known_witness_domain_discovers_every_registered_size_without_J`，位于旧 `tests/test_f3_v2_search_policy_probe.py:50`，断言 `coverage_by_size > 0` 得到 0。前后失败名称与 traceback 完全一致。未修改或删除历史测试，也未修复超出授权范围的旧 F3 搜索策略。

版本保护原有 22 项测试 PASS，覆盖原始字节/换行、内容修改、删除、新增、重命名、清单/seal/父链/起点篡改、尾修订删除、读取失败、采集期间变化、遗漏及禁止的旧资产修改；草案不能授权正式实验。

封存工具先执行完整原始字节资产扫描，要求 5810 个旧资产无差异；修订登记严格限定新版本命名空间，只修改上述两份草案。修订起点、基线和 0001–0003 不覆盖。随后必须用独立起点与新修订 SHA 执行完整 `version_control.py verify`，失败即停止并不得把本报告作为最终保护 PASS。最终验证结果与新修订摘要由完成回复独立提交；本报告受该修订绑定，避免自引用。

## 后续工程条件与停止点

N1a 能耗/固定 T 基础接口具备供 N2 使用的工程条件；N2 控制器本身未实现、未验收。依据已登记阶段顺序，N1b 仍须另行授权与验收，再决定 N2；不能将基础接口可用解读为整个 N1 或 N2 PASS。旧 F3 失败不被偷偷修复，也不作为新方案完整 K* 前置条件。

本轮未开展主性能实验、训练、MADRL、N1b 年龄追踪或 N2 控制器。完成封存和最终完整验证后停止，等待下一次授权。
