# dynamic_k_v1 修订 0005 — N1b FIFO 语义与工程实现结果

N1b 工程验收：PASS，最终生效以封存后的完整版本验证 PASS 为条件。仅实施已交付 fluid-bit 的端到端年龄统计；不是 packet 平均时延，不以 J_T/D 代替部分交付平均时延。本轮未开展 N2、MADRL、训练或主性能实验；所有正式科学参数仍为 null。

## 前置保护与实施顺序

开始前以独立版本起点 SHA-256 `ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691` 和人工指定修订 0004 SHA-256 `815352309856b9e8aa2c5ffbb4e233dd412b6bc7aa3fd2365ea03e17230411f9` 完整验证：PASS；5810 个基线旧文件、5859 个当时已登记文件、202 个排除文件，未登记新增/修改/删除/疑似重命名均为空。对应开始前命令输出登记在 pre_implementation_verification.json。

首先形成独立 FIFO 合同、配置和 Fraction 手算案例；20 项静态语义检查 PASS 后才创建实现。静态 PASS 不当作 N1b 工程验收或科学 Gate PASS。静态合同哈希 `fc5b0daf7562a3cae40c3328484adce2dea01fe6d42ea3ea81c4a67c4d3eafd4`，配置哈希 `a9f3d047acb00579a47e26f0562bc911edc96d536f53c507dcd0315b002c894e`；原文件此后未修改。

候选实现清单 SHA-256：`c27ac2866d4bfd12a8384bd91a990f841daad45a7079230301d1aaef4436031a`。清单绑定源代码、独立实现、合同/配置、测试、schema、版本起点、基线 seal 和父修订 0004；验收前后核对一致。工程结果绑定此具体候选清单，随后修订 0005 绑定完整运行证据，避免结果与尚未生成的修订互相引用。

## 新增文件及接口

本轮全部变更均为新版本命名空间内新增文件，修改与删除文件清单为空。未改任何生产源码、旧 Gate 合同、冻结 manifest、历史测试预期、历史实验输出、版本起点或修订 0001–0004；N1a 原合同/配置/runtime 也保持原始字节。完整逐文件原始字节 SHA-256 与大小见 revisions/0005/record.json 的 changes.added。

主要新增文件：

- contracts/N1B_NODE_LOCAL_FIFO_SEMANTICS_CN.md：人工冻结的本地 FIFO、同时到达比例混合、连续分布、边界与手算合同。
- contracts/N1B_NUMERICAL_PRECISION_CN.md：有理积分、浮点闭合误差界、适用条件和拒绝策略。
- configs/n1b_fifo_semantics_v1.json：独立语义配置；7 个科学数值、算法仍 null，正式实验与 N2 禁用。
- runtime/n1b_observer.py：ObservedD2Engine，新增只读服务、事件发射和闭合观察记录。
- runtime/n1b_fifo.py：LocalFIFO.advance_piece、DeliveredAgeLedger.consume/metrics/clone、AgeSemanticConflict。
- runtime/n1b_evaluator.py：DeliveredFluidEvaluator.advance_to/run/clone/checkpoint/restore、N1bEvidenceBinding.verify、validate_n1b。
- tests/test_n1b_fifo.py、schemas/n1b_engineering_result_v1.schema.json：解析与真实 D2 集成测试、独立结果结构。
- acceptance/0005/：静态检查、候选清单、验收/回归/示例/旧资产审计、封存工具及本报告。

ObservedD2Engine 是新版本内的独立 D2 子类；三个观察方法各调用冻结 super 方法一次，不插入业务事件，不重复调用 delay provider。全部旧引擎状态、传播 agenda、完整 Gate B 历史、服务量、容量分配、守恒、J 及真实闭合对照相等，包含所有七个 D2 机制案例；延迟函数调用列表也精确一致。少量历史 fixture 仅在测试内转换为观察子类，不改变生产 fixture 源码。

FIFO 排序依据每个节点每个 commodity 的本地进入队列时刻，原始注入时间只用于年龄，不参与后续节点的 FIFO 排序。同时连续到达按密度比例混合，同时数值闭合到达按 bit 比例混合；保留各仿射原始时间分布及权重，输入顺序翻转后结果相等。连续部分发送采用精确区间积分，未使用中点近似。

独立包装保留完整 n1a_result；其中所有数值、完成标志、trace/state 哈希、能耗、K、J_T、N(T)、R_del 与原 FixedHorizonEvaluator 对照逐字段精确一致。原 N1a 对象保留其历史的 N1b 未实现标志及 null 年龄占位，新增年龄字段位于外层 N1b 对象，避免改写旧结果 schema 的语义。

外层新增 delivered_bit_age_integral_bit_s、delivered_bits、mean_delivered_fluid_delay_s、mean_delay_absolute_error_bound_s 与 age_accounting。无交付时 M_D=0、平均值及其界限=null。只支持初始无历史业务，未知历史原始时间应拒绝；checkpoint 为内存深复制，保留全部 cohort/映射、在途段、混合、本地顺序、观察游标、年龄矩与 N1a 能耗。

## 验收与验算

| 验证 | 结果 |
|---|---|
| 独立 FIFO 静态语义及 Fraction 手算 | 20 项 PASS，实施前完成 |
| N1b 单元与真实 D2 集成 | 24 项 PASS，0 FAIL/ERROR |
| 原 N1a 工程回归 | 25 项 PASS，原测试未修改 |
| 新结果 schema 与候选清单前后校验 | PASS |
| 原版本保护测试 | 22 项 PASS |
| 适用历史回归 | 97 项：96 PASS、1 既有 FAIL、0 ERROR/SKIP |

24 项覆盖：两批连续注入 MD24/J39、本地 FIFO 区别于全网注入次序、同刻多入边比例混合及逆序不变、连续部分交付和积压、两跳传播、有中间积压的多 commodity equal-weight 服务、无路由/恢复、未知闭合拒绝、实际 BBM/MBB/拒绝/DRaining/分区/替代路由/自然失效等七个旧 D2 案例、observer 全字段与延迟函数无额外调用、clone/检查点/恢复/重放、固定 T 与 N1a 全字段不变、无交付 null、数值范围与跨字段拒绝、非二进制浮点误差状态。

| 工程案例 | D bit | M_D bit·s | 平均 s | W(T) bit·s | J_T bit·s |
|---|---:|---:|---:|---:|---:|
| 两批各6 bit，[0,1]/[2,3]；只交付第一批，T=5 | 6 | 24 | 4 | 15 | 39 |
| 两入边2:6同比混合，取前半并传播1 s | 4 | 23 | 5.75 | 不用于此局部队列案例的全网恒等式 | 不使用 |
| 单跳10 bit，传播1 s，T=4 | 10 | 10 | 1 | 0 | 10 |
| 两跳10 bit，各传播1 s | 10 | 20 | 2 | 0 | 20 |
| 无路由至2 s，恢复20 bit/s并传播1 s | 10 | 27.5 | 2.75 | 0 | 27.5 |
| 连续10 bit，容量4 bit/s，T=2 | 4 | 5.2 | 1.3 | 7.8 | 13 |
| 无路由至T=4 | 0 | 0 | null | 35 | 35 |

MD24 与 J39 同时在纯 Fraction 案例和真实 D2 服务案例验证；部分交付不使用 J/D。固定 T=4 的全部待机 E=6400 J、初始动态 ACTIVE 两端 E=6720 J，均与原 N1a 完全一致。测试有限 T 不是正式科学冻结值。

0.3 bit/s、容量0.2 bit/s、传播0.1 s 的工程浮点示例：旧 N1a D=0.30000000000000004 bit、J=0.10500000000000002 bit·s；M_D=0.10499999999999998 bit·s、mean=0.34999999999999987 s、W=0。记录数量调和包络 6.139533326177116e-16 bit，年龄积分界 4.918565554845601e-15 bit·s；明确标为 IEEE_RECONCILIATION_BOUNDED_NOT_ANALYTIC_EXACT。界限仅适用于已登记数量调和与输出舍入、初始无历史业务、年龄位于 [0,T] 等合同条件，不是通用物理/科学精度证明。

每个区间有理 cohort 守恒严格检查，原 D2 数量逐项对照；任何未归属正闭合、超包络差额、未知初始年龄或不可解释服务均拒绝。数值残余不生成虚构注入时间。详见数值说明与示例中的 exact_rational、roundoff_audit、closure_audit。

## 历史失败、完整保护与停止

唯一历史失败为 StructuralPolicyProbeTests.test_known_witness_domain_discovers_every_registered_size_without_J，旧 tests/test_f3_v2_search_policy_probe.py:50，coverage_by_size 得到0。与修订 0004 保存的失败名称及 traceback 完全一致，新回归0。没有修改测试制造 PASS，也没有将旧 F3 完整 K* 作为新方向前置条件。

封存工具重新读取全部原始字节，覆盖未纳入 Git 的原始数据、outputs、归档、工具与 tmp 证据，不按 .gitignore 排除；必须要求全部 5810 旧文件及0004时已有新资产无修改/删除，只有已登记的新版本新增文件。preseal_change_audit.json 保存这一完整审计。修订0005只新增，不覆盖0001–0004；parent_record 精确绑定0004哈希。

封存后必须使用独立起点及新修订哈希运行完整 version_control.py verify，失败即 STOP，本报告不能替代最终验证。最终验证状态、全部文件计数与修订 SHA-256 在完成回复独立提交，避免报告/修订/最终验证记录自引用。

N1a+N1b 已具备交付年龄、固定时域、能耗及拓扑的工程计量基础，可在下一次独立授权后进入 N2 接口工作。N2 尚未实现或验收，科学数值未冻结；本轮无科学 Gate PASS 声明。完成封存和最终验证后停止，等待审核。
