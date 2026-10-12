# dynamic_k_v1 修订 0006：N2 动态 K 动作与真实物理执行

N2 Engineering PASS，最终生效以封存后完整版本验证 PASS 为条件。本轮只完成原子 HOLD/ADD/DROP/REPLACE 及物理/业务/能耗/FIFO 集成，没有正式控制器性能比较、MADRL、MAPPO、GNN、训练或 N3 实施。不是科学 Gate PASS。

## 独立信任锚与版本保护

开始前使用独立起点 SHA-256 `ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691` 与用户指定修订0005 SHA-256 `c2567b66fe880035853aba2b81463ece42443973d5b5178ae0b28e77a6c44769` 完整验证：PASS。5810 个旧基线文件、5882 个已登记文件、202 个排除文件；未登记新增/修改/删除/疑似重命名均为空。

N2 候选清单 SHA-256 `34e3412da99a96c58fe603af5de69777d69e0e2bc292fba4cbd3cfca8acb0b4a`，绑定全部旧生产 Python 源码、原N1a/N1b实现、独立N2实现/合同/配置/测试、结果schema、SGP4原始TLE、Gate C几何输入以及起点、父修订0005和baseline seal。每次动作提交/推进均复核绑定；验收前后绑定相等，证据随后由修订0006绑定，避免循环哈希。

本轮只新增文件，修改/删除为空。未修改冻结生产内核、旧Gate合同、current.json、旧manifest、历史测试预期/实验输出、N1a/N1b代码及版本起点/0001–0005。完整原始字节新增清单、大小及SHA-256在 revisions/0006/record.json；全部旧资产的全量扫描证据在 preseal_change_audit.json。

## 文件与实际接口

新增 contracts/N2_ATOMIC_TOPOLOGY_ACTIONS_CN.md、configs/n2_action_semantics_v1.json、runtime/n2_actions.py、runtime/n2_candidates.py、runtime/n2_physical.py、runtime/n2_binding.py、runtime/n2_controller.py、tests/test_n2_actions.py、schemas/n2_engineering_result_v1.schema.json，以及 acceptance/0006 内候选、运行器、报告、示例与封存证据。

- Setup、LinkRef、Hold、Add、Drop、Replace：显式setup时间、精确link_id及双端引用、BBM/MBB模式；不提供科学默认值。
- ActionValidator.validate：真实Gate C物理验证及Gate B事务预演；拒绝返回明确原因，不改变live终端。
- CandidateSource.generate：独立ADD/DROP/REPLACE路径和始终保留的HOLD，规范排序、掩码及逐类预算诊断。
- N2PhysicalLayer.evaluate：当前及预测ready的几何guard、Gate C窗口和真实资源检查。
- Sgp4PhysicalGuard：共同TEME状态的球形LOS与理想RTN双端FoR；ReplayableSgp4Model：仅在新版本提供同TLE重建的clone适配，不修改旧模型。
- AtomicTopologyController.candidates/submit/advance_to/run/clone/checkpoint/restore：提交真实终端命令并直接消费原DeliveredFluidEvaluator；submit_batch只保留未来接口，返回JOINT_ACTION_EXECUTION_DEFERRED，没有冻结并发数。
- release_audit、validate_n2、N2EvidenceBinding.verify：释放集合、终端/K/SETUP跨字段一致性与文件绑定校验。

## 动作、候选与分区语义

ADD要求双端真正空闲、无预约、没有占用端或同卫星对旧绑定；即使K=0也可发现并提交。候选接受不等于ACTIVE，真实retarget/acquisition完成后K才增加。非法ADD不会借Connect隐式释放旧连接。

DROP使用精确旧引用，调用原Disconnect。已登记非抢占TX使连接保持真实DRAINING至最后信号接收完成；无待结束TX时原Gate B可以同刻完成释放，控制器不虚构固定释放时长或提前假定所有终端空闲。D2在途业务沿原传播模型继续保留。DRAINING计45 W，不计主K。

BBM核对Connect隐式释放集合包含于声明集合，额外声明旧连接显式Disconnect；事务预演和live即时释放集合必须严格相等。MBB只接受真正空闲的新双端，release_after精确对应声明旧引用，真实LINK_UP后才释放。旧链setup期间自然失效及setup abort分别审计，不声称无中断。没有邻接矩阵编辑或直接业务量修改。

没有默认STRICT_CONNECTED/BOUNDED_OUTAGE拒绝，没有最低交付率、固定K或额外Kmax掩码。无路由业务等待，恢复后按原Node-Local Per-Commodity FIFO继续；Q/I/A/D和原数量闭合不变。

ADD全枚举当前提供的Gate C catalog窗口，DROP全枚举现有连接；REPLACE生成最小资源冲突释放集合及空闲双端对单旧连接的BBM/MBB，不枚举所有任意释放超集。验证器没有声明释放数量上限。默认不截断，显式工程预算按动作种类独立应用，报告considered/legal/retained/truncated和NO_LEGAL_PHYSICAL_ACTION或LEGAL_BUT_BUDGET_TRUNCATED。物理无候选结论仅限已提供catalog及当前资源，不是对未登记几何空间的全局不存在证明。

真实几何闭环故意使用一个明确登记的终端对作为受控场景，未宣称覆盖所有160星合法双端；通用候选源支持提供完整catalog。该场景不冻结正式搜索预算或控制算法。

## 验收结果

| 验证 | 结果 |
|---|---|
| N2 专项 | 27/27 PASS，0 FAIL/ERROR |
| 原N1a全部工程测试 | 25/25 PASS，代码与测试未改 |
| 原N1b全部工程测试 | 24/24 PASS，代码与FIFO未改 |
| 新结果schema、前后候选/上游绑定 | PASS |
| 原B/D1/D2/传播闭合/clone/checkpoint/F3适用回归 | 97项：96 PASS、1既有FAIL |
| 增加的Gate C三组回归 | 35/35 PASS |
| 版本保护测试 | 22/22 PASS |

专项覆盖用户15类要求，包括K=0 ADD、setup前不增加K、真实DROP/DRAINING/资源复用、实际BBM/MBB释放集合、双端/预约/同卫星对冲突、第三方释放拒绝、球形LOS与双端FoR各拒绝原因、ready时几何复核、窗口不足/自然失效/MBB abort、临时分区及FIFO恢复、驻留/能耗手算、部分交付时延、clone/checkpoint/restore及真实160星SGP4克隆重放。候选倒序输入结果相同；预算将ADD/REPLACE保留量设0的显式测试仍保留HOLD/DROP，并标记真实合法但被截断。

唯一既有失败是 StructuralPolicyProbeTests.test_known_witness_domain_discovers_every_registered_size_without_J，旧 tests/test_f3_v2_search_policy_probe.py:50，coverage_by_size为0。名称与traceback同修订0005证据完全一致；新增回归0，未改测试期望制造PASS。额外35项Gate C全部通过，合计历史回归132项为131 PASS、1旧FAIL。

## 工程验算与160星几何闭环

| 解析场景（全部T=4 s） | 结果 |
|---|---|
| K=0，t=0 ADD，retarget两端各0.5 s/acquire0.5 s | t<1时K=0，t=1后K=1；E=6710 J；10bit的M_D=17.5 bit·s、mean=1.75 s |
| 初始ACTIVE，t=0.5 DROP，真实TX完成1.5 s | 0.5–1.5 DRAINING、K=0；E=6520 J；交付5/剩余5 bit，M_D=5、mean=1、J=21.25 |
| 上例t=1.5资源IDLE后重新ADD | t=2.5恢复；全部10bit交付，M_D=J=19.375 bit·s，E=6710 J，cohort不重置 |
| BBM复用旧占用端，旧TX完成1 s，retarget/acquire各1 s | 真实ready=3 s，之前K=0；即时释放集合与声明精确相等 |
| MBB新端空闲，retarget/acquire各1 s，旧TX完成3 s | 新链2 s LINK_UP后才释放旧链；2–3 s旧链DRAINING，不计主K |

直接对照相同真实命令下原DeliveredFluidEvaluator，嵌套n1b_result精确相等，包含N1a的全部能耗/K/J/N/R/完成状态、FIFO年龄统计和数值界。旧层保留自己的历史作用域标志，当前N2实施状态由外层schema及修订记录表述。

真实短时案例使用冻结SGP4合成TLE，以真实SGP4位置/速度计算160节点（320动态终端）的路由传播及LOS/FoR。受控双端 X0_1/D2 ↔ X1_1/D1，输入catalog窗口[0,600]右删失；600是旧几何预测资产有效期，不是本轮评价T或正式T冻结，也不称真实遮挡时刻。

测试参数显式为T=4 s、注入[0,1]的1 bit/s、链容量10 bit/s、retarget两端0.2 s/acquire0.2 s。基于当前候选/状态执行ADD(0)、HOLD(0.1)、DROP(1.25，已确认交付1bit)、重新ADD(2)。真实LINK_UP在0.4及2.4 s；最终K=1、E=6652 J、DeltaE=252 J、交付1bit、M_D=mean=0.09331964311338135、J=0.09331964311338137。原数值调和界1.783517853902352e-15 bit·s，状态IEEE_RECONCILIATION_BOUNDED_NOT_ANALYTIC_EXACT；不把浮点结果宣传为解析精确。完整原始示例与参数在 engineering_examples.json。克隆分支执行同动作/事件后完整结果相等。

物理条件沿用Gate C理想RTN、参数化setup及数值窗口，未新增PAT/gimbal/硬件标定。LOS/FoR当前及ready检查和窗口条件严格执行；数值窗口保留已有分辨率/右删失限制，不宣称任意连续时间无漏事件数学证明。

## 封存、N3条件及停止

封存工具对所有原始字节重新扫描，包含被.gitignore忽略的raw data、历史outputs、归档、工具及tmp证据；要求5810个旧基线文件及0005时所有已有版本资产无改动。只接受新版本内新增文件，保存逐项排除路径/原因及变更审计，再新增连续修订0006，父记录精确绑定指定0005。

最终必须以独立起点和生成的0006 SHA-256运行完整 version_control.py verify；失败即STOP。最终保护结果与修订SHA-256在完成回复独立提交，避免报告/修订自引用。本报告受修订绑定，不能单独代替完整保护验证。

具备进入N3的工程基础：真实动态动作、允许分区、业务守恒及统一固定T/能耗/FIFO计量接口均可用。N3须下一次授权开展分区业务回归和非学习基线，复用相同物理合法性、动作审计与测量口径；正式科学T/T_A/tau_res/R_min/alpha/D_ref/E_ref、决策周期、并行动作预算、搜索预算和算法仍null，不能据此开始正式性能比较。

完成最终封存验证后停止，等待审核。
