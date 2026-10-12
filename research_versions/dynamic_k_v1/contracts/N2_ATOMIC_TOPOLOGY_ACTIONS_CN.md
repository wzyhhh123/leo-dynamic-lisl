# N2 原子动态 K 动作与物理执行合同

仅适用于 dynamic_k_v1 修订 0006，授权范围为工程实现、解析/集成验收及一个受控短时160星真实SGP4几何闭环。前置完整保护验证为PASS；不改旧Gate B/C/D2内核、冻结合同、旧测试/结果和0001–0005。

## 原子动作

HOLD 不提交主动终端变更，事件、自然失效、业务及能耗仍由已验收的固定时域推进。ADD显式给出双端和setup时长；两端必须真正IDLE、无预约，不能通过Connect的占用端或同卫星对副作用释放任何旧连接。无旧连接、K=0时仍枚举ADD。接受与ACTIVE分离，以真实RETARGETING/ACQUIRING/LINK_UP为准。

DROP以link_id及精确双端引用指定一个现有、未锁定、未DRAINING的连接。调用Gate B Disconnect；真实非抢占TX决定DRAINING结束。无待结束TX时Gate B可在同刻完成释放，不能人为固定正释放时长，也不假设所有DROP都立即IDLE。Gate B中已登记TX包括最后信号接收；D2连续in-flight按原传播内核独立保留。DRAINING计45 W，不计K_admit。

REPLACE显式提供非空旧连接引用集合、新双端、setup与BBM/MBB模式。提交前计算Connect的所有占用端/同卫星对隐式旧绑定。BBM隐式集合必须包含于声明集合，额外声明的旧连接用显式Disconnect释放；事务预演与实际即时释放集合必须严格等于声明集合。MBB新双端必须空闲，隐式集合必须为空；release_after只包含声明旧绑定，LINK_UP后才释放。旧绑定可在setup期间自然失效，这记录为自然结束，不虚称无中断。setup失败保留真实Gate B abort语义，未自动改为其他动作。

拒绝非法/过时link_id、重复引用、预约/双端资源冲突、第三方释放、LOS/FoR失败、窗口不足及未知动作。原子拒绝不修改实际终端；每次提交重新验证，不信任旧候选掩码。未来联合批次接口预留但不执行，不冻结最大并行动作数。默认不使用STRICT_CONNECTED、BOUNDED_OUTAGE、交付率或固定K/Kmax硬掩码；允许临时分区，真实物理合法性仍严格检查。

## 物理与候选

Gate C terminal-pair窗口及资源预演为建链依据，几何guard检查当前LOS/FoR及预测ready。真实工程案例使用冻结SGP4合成TLE、Gate C理想RTN双端FoR和数值窗口；窗口精度沿用已有Gate C数值模型的限制，不声称商业硬件标定或无漏事件数学证明。合成解析测试显式标为synthetic，不替代真实几何验收。

独立候选源枚举当前catalog全部双端窗口：ADD与DROP各有独立路径；REPLACE枚举最小占用释放集合以及空闲双端对单个旧绑定的BBM/MBB，不枚举所有任意超集。验证器可接受任意显式合法旧释放集合，未设置释放数上限。该候选覆盖用于原子机制验收，不选择正式控制算法。

候选按动作种类、模式、双端和旧引用的规范键排序，与dict/文件顺序无关。默认不截断；调用者可显式提供分动作类型工程保留预算。报告逐类considered/legal/retained/truncated及NO_LEGAL_PHYSICAL_ACTION、LEGAL_BUT_BUDGET_TRUNCATED或RETAINED，不能把预算截断称物理无候选。HOLD始终保留，ADD/DROP不经过旧REPLACE-only截断。候选只用当前物理窗口、终端及预约状态，不读未来业务。

## 连续执行、指标与绑定

控制器只向真实TerminalExecutor提交原命令，并使用D2当前时刻settle及已验收DeliveredFluidEvaluator继续推进；不编辑邻接矩阵、业务量或cohort。原N1a/N1b对象保留完整结果，N2在外层增加动作回执、释放审计及320终端当前状态。K_admit按双端ACTIVE连接实例计数，不按卫星邻接边去重；DRAINING、SETUP终端占用、预约占用与K时间序列独立保留。

正式T/T_A/tau_res/R_min/alpha/D_ref/E_ref、决策周期、并发预算、搜索预算及算法继续null。工程有限T、setup、采样点、几何数值参数必须明确记录。每次提交、推进和验收核对候选0006清单及原0004/0005实现清单；运行证据最终由连续修订绑定，避免自引用。clone/checkpoint/restore整体复制物理状态、动作回执与FIFO/能耗累计；真实SGP4模型在新版本clone适配层从同一TLE重建，不改旧模型。

若必须修改冻结生产内核或无法保持FIFO/守恒，则STOP并保留具体证据。N2工程PASS只说明动作与执行计量接口可用；N3业务回归/非学习基线需要下一次授权。无正式性能比较、RL/MAPPO/GNN、MADRL或科学Gate PASS。
