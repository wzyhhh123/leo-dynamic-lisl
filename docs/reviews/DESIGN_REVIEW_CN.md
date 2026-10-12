# v0.1 设计审查与 Gate A 预审

日期：2026-09-18。已通读用户提供的实验合同和 generate_scenario_X720.py。没有修改上传文件、旧生产执行器或 traffic generator，没有启动 STK 场景生成、网络性能实验或 RL。仅在本目录运行脚本原有纯审计函数的负向测试。

总体判断：研究问题可实施，720母星座→160/240完整轨道面子集的设计比重新生成稀疏小星座清楚；但v0.1还不能作为可执行冻结合同。主要阻塞是：Gate A验收器会误报PASS、terminal-level动作未完全定义、transition安全性不是目标图连通性、参考图与归一化的状态语义未冻结，以及matching边权的非可加性。以下“必须修订”是设计审查结论，不是已经替用户改定了合同。

## 1. Gate A：已执行预审，验收器 FAIL；STK生成尚未运行

对上传脚本通过AST只提取六个纯函数，不导入COM入口、不启动STK。构造720条合成轨道记录，使用原audit_constellation和原容差：

| 输入 | 应有判定 | 原函数返回 |
|---|---|---|
| 18轨，RAAN=0,10,...,170°，全局相位增量+0.5° | PASS | PASS |
| RAAN=0,20,...,340°，其余相同 | FAIL（不是指定Star） | **PASS** |
| RAAN=0,1,...,17°，其余相同 | FAIL（不是指定Star） | **PASS** |
| 正确RAAN，相邻相位+0.5,-0.5交替 | FAIL（不是固定F=1全局相位递进） | **PASS** |

这是验收函数假阳性，不是“STK实际生成了错误星座”的证据。gate_A_preflight.json保存全部返回值，check_gate_A_preflight.py可复现。

脚本322–337行只检查各RAAN间隔相对其自身均值的偏差；必须改为检查配置目标180/P=10°，种子RAAN、展开顺序及跨度。Star的18个节点RAAN中心为0至170°，分布区间定义为180°；不能错误要求max−min恰等于180°。跨缝170→0不能用Delta周期邻居规则自动闭合。[STK Walker官方说明](https://help.agi.com/stk/Content/stk/tools-12.htm)

脚本350–354行逐对取±0.5°最小误差，因此错误的交替方向也通过。应冻结一个全局方向σ∈{+1,-1}（由明确STK约定/校准确定），对所有plane检查u_p=u_0+σp×0.5° mod 9°，不能每一对自由选符号。其他F要在模9°的环上比较，当前绝对值实现也不适合所有合法F。

本机检查：STK11.Application已注册，指向D:/Program Files/AGI/STK 11/bin/AgUiApplication.exe；Python3.9.21的pytorch环境有comtypes及已生成STKObjects/STKUtil类型库。因此不能说缺STK；但注册/依赖存在不证明许可、COM运行和Walker命令成功。

Gate状态：A.preflight FAIL（验收器失效）；A.STK NOT_RUN；B–G NOT_RUN。先修复验收器再生成，否则720产物即使标PASS也不足以放行后续Gate。

## 2. 720脚本的具体问题

| 位置 | 严重性/证据 | 修订要求 |
|---|---|---|
| 322–337 | 阻塞，负向测试已复现 | 校验Star的目标10°间隔，不仅均匀性 |
| 350–354 | 阻塞，负向测试已复现 | 全局相位符号一致；模轨内间隔的相位合同 |
| 486–488 | 运行风险，未在STK实跑确认 | 在QueryInterface前显式SetPropagatorType(ePropagatorTwoBody)，不依赖新卫星默认传播器 |
| 491–499及91–94 | 已确认坐标枚举不一致 | 本机STKUtil中3=J2000，脚本读provider先选ICRF；统一生成、读取、导出的frame。以1e-6°容差比较不同frame可能产生假失败，不应靠放宽容差掩盖 |
| 全局 | 缺单位和epoch冻结 | 显式设Distance=km、Angle=deg、DateFormat=UTCG；明确state epoch/传播起止及步长。config记录实际读取的单位与frame，不只写计划值 |
| 453–475 | 重复运行/状态风险 | 不吞所有NewScenario异常后继续修改同名场景；使用干净独立实例/唯一审计场景，只处理本次新建对象。两阶段重命名不等于整脚本可安全重跑 |
| 515–517 | 结果集合风险 | 当前枚举场景内全部卫星；必须限定本次Walker生成对象，否则旧卫星会导致计数失败或混入重命名 |
| write_manifest | 数据合同不完整 | 现有CSV只有根数，没有timestamp/frame/position/velocity；可据严格TwoBody根数重建，但还没有实现或验证这个路径。优先导出共同epoch的Cartesian r/v及带时间的ephemeris，记录mu、步长、插值、单位、hash |
| read_classical_elements | 数值/版本适配 | 圆轨道AOP退化；统一用argument-of-latitude或在同frame由r/v重建；不能把不同anomaly/provider成功读取即视作同一量 |
| parse_args/文件名 | 可复现性 | 检查P、S、F、时间窗合法性；自定义规模仍输出*_720容易误标。输出加完整配置、脚本hash、STK版本、唯一run目录及失败标志 |

[STK SetPropagatorType官方接口](https://help.agi.com/stkdevkit/Content/DocX/STKObjects~IAgSatellite~SetPropagatorType.html)。这里没有断言原脚本必然在默认传播器处报错：它是否运行取决于本机默认对象设置。

建议A拆为：A0纯审计负向测试→A1独立STK少量对象API/单位/frame smoke→A2生成720及正确审计→A3公共时间网格r/v导出与解析TwoBody交叉校验→A4抽取160/240，逐样本与母星座r/v/hash完全一致。A只证明几何资产，不提前冒称candidate/终端硬件可行。

## 3. 物理假设和2-fixed+2-dynamic语义

### 3.1 架构本身不矛盾，但研究边界已经改变

2-fixed同轨环确实不保证跨轨连通，合同对此认识正确。现在研究的是“动态跨轨连接承担连通与容量”的重构问题，不再是先前3-fixed全局骨干上的可选捷径优化。若不停保留这个区别，旧服务损失分析会错把一个不连通的intra-only图当作可用fallback。

4个full-duplex端口各方向C、可并发，是可实现的抽象合同，但不代表已验证实际四终端硬件可同时指向任何方向。两个dynamic全向可转、忽略共同遮挡/机械干涉、足够交换背板、理想控制均需明确标作第一版假设。

1200km按a=6378.137+1200定义是相对赤道半径的轨道高度参数，不是沿85°倾角轨道恒定的椭球大地高度。LOS需指定球形保守地球或椭球、净空。TwoBody适合机制隔离，但不是一天尺度真实OneWeb轨道真实性声明。24小时生成窗也不能自动成为网络实验窗。

### 3.2 动作必须含两端terminal identity

CONNECT应为(i,k,j,l)，k,l∈{1,2}；current_peer/target_peer至少为(peer_sat,peer_terminal)。Z_sat只表示卫星对，不唯一决定setup：同一i-j，选不同端口有不同orientation、旧peer、free_time和被释放边。因此完整动作应为保留绑定＋释放绑定＋建立绑定＋执行顺序，或明确由所有算法共用的确定性terminal allocator补全。

默认禁止同一卫星对双dynamic并行链；如允许多重边，需要显式把它当成2C并行资源，不能simple graph去重后既占两端口又只计C。动态active/reserved的计数应按端口所有权定义：DRAINING旧peer与新target reservation是同一终端的时序状态，不能在同一时间把它当成两个物理活动端口。

例：i.D1连j，i.D2连k，准备让i.D1连m.D2，而m.D2原连n。释放集至少包含i-j及m-n，两条旧边的业务和j/n端口都受影响；不是只算i-j机会成本。跨多命令预留必须原子检查，避免一边已拆另一边预留失败。

### 3.3 BBM需要明确是终端级还是网络级

每个终端自身BBM与“另一终端继续工作”一致。但如果i.D2和m的某终端空闲，先用它们建i-m、再释放i.D1-j，网络层就是MBB。这在2+2下合法且可能显著消除损失。

建议第一阶段采用**每终端BBM，允许使用真实空闲端口先建后断**；无需强制为了证明setup代价而禁用合理闲置资源。机制反例应明确冲突端点端口已占用。若研究坚持网络级BBM，则必须另加全局顺序约束并声明这是策略限制，不是硬件必然。

LINK_DOWN必须等双方向正在发送的数据及最后光信号接收完成（或另定义丢弃策略），不仅发送端TX_finish。ready公式中的i,j必须是新连接两个端点，不要沿用步骤里旧peer j造成歧义。

setup中不可改目标可以冻结；但可见性提前失效仍需强制abort和释放预约，不能让不可实现的pending链接永远占端口。同peer/同绑定保持不应重新acquire；同peer换端口则是新物理连接。

### 3.4 物理候选与动作合法性分层

v0.1把range/FOV与orientation、free_time、ready全塞进Ecand，导致候选图随控制历史变化；有两个不同端口后，一条卫星边也没有唯一ready/lifetime。

建议：Egeom(t)记录卫星对几何可见区间；Pgeom(t)记录可用的(i,k,j,l)安装/FOV/跟踪组合；Alegal(s,t)再检查当前方向、预约、BBM、ready和连通性。Ecand若保留原名称，须声明是state-conditioned的terminal-pair候选，不再假装所有策略共享同一边集；共享的是geometry trace。

必须有机体系姿态规律，才可定义FOV和tracking angular rate；ECI视线角速率不等于相对转台安装坐标系的角速率。retarget/acquisition跟踪的运动目标必须由同一姿态/星历求解。lifetime右删失、根查找容差、硬件未标定状态均入manifest。

## 4. 连通性约束：最终目标图连通不够

两条各自可安全删除的边，同时删除可能断网。用三轨道quotient三角形举例：单独去掉AB或AC均连通，同时去掉AB与AC则隔离A。仅对每个CONNECT独立检查或只检查最终Z_n，不足以保证过渡安全。

必须由统一transition executor生成删除/建立时序，沿所有事件断点检查active图；包括同时LINK_DOWN、LINK_UP和外生visibility expiry。必要时采用安全的序列交换，不能任意重排并行命令。

仅要求commodity的原始source→destination可达仍会漏检已经走到中间节点的包。至少保护所有有Q_i^f>0的节点i及在途包未来接收节点到d_f的可达性，再保护下一控制/建链区间内具有已知正强度的OD。不能根据未发生的随机arrival选择保护集合，避免信息泄露。第一阶段更清楚的选择是保护全体节点连通，或者提前冻结protected OD集合及上述backlog规则；二者是不同可行域，不能随算法改变。

必须验证初始Z_ref已active、连通且有可行动作。全端口占满加安全连通并不必然无解，但可能锁死某些交换；报告合法非HOLD动作数、blocked原因和安全过滤拒绝率，否则“算法不切换”可能只是无合法动作。自然失联若使保护约束不可维持，应标场景不可行，不静默放宽。

## 5. Traffic归一化与chunk：公式方向正确，尚缺四个合同

### 5.1 Z_ref必须是活动参考网络

reference nearest-left/right必须是双端一致、端口合法的匹配规则；每星独立选择最近邻不能保证对端端口≤2。子集边界不能假造wrap。若Z_ref有必要handover，必须给同样setup、双端占用和安全时序；“固定基线”只能指固定规则，不是零setup瞬移。

首轮宜选一个经过Gate C证明可全窗保持的connected reference，初始已active，所有策略共享同一初态。如果找不到该窗口，要么缩短共同窗口，要么使用真实reference executor并更名为reference policy，不能继续称不变拓扑。

### 5.2 rho是理想容量标尺，不是实际利用率

G需明确单位bit/s，C同为可用payload bit/s；有向边两个方向分别约束，LP含每commodity源/汇/中间流守恒。在静态合法E_ref上，U_ref正齐次，g*>0时可得到max_t U_ref(rho G/g*)=rho；不是仅“约等于”，近似来自时间抽样与求解容差。

若某个有需求OD在参考图不可达，则U_ref无有限可行解，归一化应拒绝；不能把infinity变成F0=0。如果仅某些时刻不可达，即使长期可存储转发，瞬时LP也不能直接使用，应改用明确时扩展容量定义或保持首轮全窗连通。

rho=1是可分流、理想静态参考的边界，不保证固定快层packet routing稳定；rho>1峰值phase也不等于整个有限实验必然不稳定。所有算法共享同一F0，不能按各自优化后的拓扑重标负载。

160、240、720分别归一化使跨规模注入总Gbps改变。必须同时报OD数量、总/每星/每OD注入率、源目的cut负载与参考瓶颈。把“固定总需求的weak/strong scaling”概念写清：固定总工作量为strong scaling式问题；保持每星/每OD负载为weak scaling式增长。这里是计算规模类比，不把这两个实验混成单一算法收益。

### 5.3 chunk不是单纯加速开关

若固定bit-rate R，令固定chunk长B、Poisson到达率λ=R/B，那么时间T内到达bit数方差=RBT。B增大同时增大业务突发性，并延长非抢占串行化、drain和setup前等待。因此改变chunk大小再调λ，得到的是不同arrival过程，不是同一物理业务的纯数值离散化。

推荐将外生累计bit/work trace与网络切分粒度分开：先冻结业务到达工作过程，再对已到达工作切块；若刻意用compound Poisson聚合业务，则B是业务模型参数，粒度敏感性必须包括方差变化。定义小chunk的生成时刻不能通过等待凑满大chunk引入未计量assembly delay。FIFO、serialization、到达ordering共同冻结。

若N_f以bit计，J=Σ包B×sojourn（完整排空）；若以chunk个数计，更换B会改变目标量纲。主目标明确bit·s，P95说明按chunk、按bit加权还是真实packet口径。

### 5.4 有限窗目标与drain

所有策略使用共同测量H和相同外生trace，统计截止残余；不能各自提前停止后直接比较不同积分区间。full drain要保持足够长的合法后续几何，不能超过visibility后冻结拓扑继续交付。持续过载时不等待无限排空。初始active链的建立成本作为统一warmup排除或统一计入，不能只豁免Static。

## 6. 算法路线：合理，但b-matching只宜作proposal

保留固定快层、无RL路线。明确选一种确定性routing/scheduler，冻结平局规则、是否允许多路径、更新时机、零时循环保护和无路等待；“queue-aware shortest path或backpressure”还不是合同。backpressure需要目的队列差；按最短路重新路由则可能形成动态循环，需要对应保护，但不应强套旧four-neighbor的hop mask。

关键：W_ij依赖替换哪一个旧端口、另一端拆哪条边、同时选哪些新边、共享瓶颈和整个transition。一般不是状态固定后互相独立的边收益。b=2仅限制卫星度，既不决定terminal assignment，也不保证连通性。即便在terminal-expanded graph做matching，也只解决端口唯一性，不解决时序安全与非可加网络效益。

建议名义改为“matching proposals + terminal-aware safe transition + network rollout evaluation”：冻结状态下计算近似边权→生成少量候选匹配/局部交换→端口分配和完整transition检查→同一快层短预测评估→含HOLD择优。可以研究结构化近似权重，但不能称其精确求解了含外部性的最大权b-matching原问题。

Ignore-Setup与proposed必须共享相同candidate、terminal allocator、安全过滤和信息集，仅评分是否计setup不同；对照“过滤前建议动作”和“实际执行动作”，避免安全层替劣基线隐含优化。AMW-style只称启发式迁移，原理论的稳定性保证不自动延伸到可见窗、双端重构和安全连通限制。

MPC top-K限制K、Hp和rollout预算；若Hp<setup，所有切换看起来都差，必须设置覆盖setup与有效收益窗口或有统一终端价值。实际决策耗时若忽略，声明离线控制上界；若模拟部署，则所有算法按相同规则计入command latency，不能只有复杂方法消耗免费计算时间。

## 7. 规模、边界与Gate顺序

160/240抽取完整轨道面是合理母星座子集，不是完整全球覆盖星座。4轨场景边界轨道占50%，6轨占33.3%，边界效应可能支配性能。冻结所选plane IDs，优先不跨Star seam；至少多个连续窗口位置/初相位/起始时间复核，避免挑最有利区域。边界不借用外部卫星连接，也不虚构周期wrap。

720有244800个跨轨无向卫星对（未做range/LOS剪枝），不是全都要进入每次matching。all-to-all有517680个有向OD，若每节点为每OD密集建queue即372729600个队列；不能默认创建。第一轮冻结有限稀疏OD集合，按需建队列，并给流数随规模变化的规则。基于r/v计算range/LOS和缓存可见窗口，避免在每包事件里调用STK COM。控制Delta_c、业务强度更新周期、几何采样间隔互相独立。

建议保留A–G主顺序，但增加必要细分与验收：

| Gate | 本轮状态 | 下一步放行条件 |
|---|---|---|
| A0验收器 | FAIL，三类假阳性复现 | 修正Star/phase/单位frame合同，负向用例必须拒绝 |
| A1–A4几何资产 | NOT_RUN | STK小样smoke→720→公共epoch/r-v→160/240严格子集；输入/输出hash |
| B终端执行器 | NOT_RUN | 冻结terminal-pair action、BBM/MBB层级、DRAINING/abort；先合成可见窗状态机测试，不接traffic |
| C候选/参考网络 | NOT_RUN | 硬件假设表、全窗reference可行性、动作lifetime、transition安全性；宽FOV只能provisional |
| D业务/queue | NOT_RUN | F0/ρ参考LP、chunk语义、守恒/面积、同输入配对、固定快层 |
| E机制 | NOT_RUN | 在新2+2执行器重新证明等容量反例与第三流外部性；不能继承旧单dynamic toy的数值 |
| F主实验 | NOT_RUN | 160先pilot验证可行动作与算法预算，随后240；强简单基线与matching proposal公平比较 |
| G扩展性 | NOT_RUN | 720只跑少数已冻结方法；记录候选/OD规模、运行时、内存、合法率 |

不需要以“没有冻结所有硬件参数”为由阻止B的纯状态机验证；但参数化几何通过只能称provisional，不得转成硬件认证或直接放行正式性能解释。本轮实际停在A0，是因为已测出验收函数假阳性，不是因为720规模本身过大。

## 8. 建议v0.2最先改定的六句话

1. Star母星座的RAAN递进固定10°，全局相位递进固定同一方向0.5°，在同一epoch/frame验证。
2. 动作绑定双方具体terminal，并包含由公共执行器产生的安全transition计划。
3. BBM默认按terminal定义；空闲第二端口是否允许网络级MBB显式冻结。
4. 保护集和保护区间事先定义，检查active图完整transition及中间节点backlog，不只检查目标图。
5. ρ依据合法reference活动网络的理想多商品流容量；chunk大小与外生业务突发性分开定义。
6. b-matching负责生成候选方案，含共享网络外部性的最终决策由安全验证和统一网络服务评估完成。

研究问题不必推翻；但在以上合同未明确前启动160/240/720主实验，所得差异可能来自端口分配、断网过滤、参考图切换或chunk突发性，而不是所研究的setup-aware topology control。
