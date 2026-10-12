# LEO 动态 LISL 实验合同 v0.2

日期：2026-09-18  
状态：**审阅稿；六项核心语义按用户决定冻结，数值参数与未决实现选择不得冒称已验证。**  
依据：LEO_dynamic_LISL_experiment_plan_v0.1.md、DESIGN_REVIEW_CN.md及本轮六项修订要求。  
配套文件：[Gate A 修复方案](./GATE_A_REPAIR_PLAN_v0.2.md)。

本轮仅生成合同和修复方案。不修改旧生产执行器、上传生成脚本或traffic generator；不运行STK，不实现B–G，不训练RL，不启动主实验。后续开发顺序不是本轮执行记录。旧Gate A预审已经发现假阳性；本合同不将其改标为PASS。

## 0. 研究问题与范围

面对时变多OD聚合业务，在双端独占动态LCT、非零重构时间和有限可见窗口下，决定何时重构、释放哪些物理绑定、建立哪些新绑定，使端到端网络服务收益超过重构及共享网络产生的损失。

第一阶段采用2 fixed intra + 2 dynamic inter。固定同轨环不能独立提供全局连通；动态跨轨边同时承担连通与容量。这里不再使用“始终存在全局固定骨干”的3+1前提。

固定快层routing/scheduling，慢层控制持久拓扑；所有方法使用相同执行器、容量、物理过滤、安全约束和外生输入。先建立正确性与强非学习基线，不以RL为研究前提。

## 1. 星座、时间与几何资产

### 1.1 母星座

| 字段 | v0.2合同 |
|---|---|
| 类型 | 理想化Walker-Star，不是真实OneWeb TLE |
| N / P / S | 720 / 18 / 40 |
| 种子半长轴a | 6378.137+1200=7578.137 km |
| 偏心率 / 倾角 | 0 / 85° |
| F | 1 |
| 种子RAAN / argument of latitude | 0° / 0°，共同epoch定义 |
| plane RAAN | Ω_p=0°+p×10°，p=0,...,17 |
| 轨内相位 | u_(p,k)=u_seed+σp×0.5°+k×9° mod360°，k=0,...,39 |
| 相位方向 | 同一run只有一个预先声明的σ；默认+1。不得逐对选±或依据正式结果自动选方向 |
| 传播器 / 中心天体 | 显式TwoBody / Earth |
| 生成、审计、导出frame | 统一J2000；禁止混用ICRF根数直接比较 |
| 日期 / 距离 / 角度 | UTCG / km / deg；速度km/s |
| 初始epoch | 01 Jan 2026 00:00:00.00 UTC，与种子状态epoch和导出t=0一致 |
| 几何归档窗 | 至02 Jan 2026 00:00:00.00 UTC；不等于主实验必须运行24h |

σ若需按STK约定改为−1，必须在小样校准说明中给出依据并显式更新配置；校准后所有18个plane使用同一符号。默认+1失败时不得通过对每对取绝对值掩盖。正式审计同时校验绝对RAAN位置、10°递进、9°轨内间隔及全局有符号相位残差。18个RAAN中心是0至170°；180°表示分布区间，不要求最大减最小等于180°，不添加跨缝周期连接。

1200km是上述半长轴定义中的参考高度，不声称相对椭球的大地高度恒定。TwoBody的μ、STK版本、实际frame/单位/epoch必须入manifest。LOS地球形状和净空属于Gate C配置，不能悄悄沿用不同地球半径。

### 1.2 输出与子场景

至少输出母星座config、卫星manifest、audit和带时间的Cartesian位置/速度；保存脚本、配置、manifest及ephemeris hash。CSV每颗卫星记录原始对象名、稳定satellite ID、plane ID、slot ID、epoch、frame、单位、根数及共同epoch的r/v；时序ephemeris记录采样网格、插值规则和误差验证。

160=连续4个完整plane，240=连续6个完整plane，均从同一母星座资产抽取，保留原ID和所有r/v；不得重新分配RAAN、相位或把ID排序变成新星座。明确列出plane IDs、母资产hash、起止时间和边界标签。默认子集不跨Star seam，不虚构外部边或周期wrap。

4-plane子集边界轨道占50%，6-plane占33.3%；报告内部/边界的候选数量、lifetime、可达性和负载差异。主场景位置、起始时间及OD选择在性能结果前冻结。40星左右仅作机制/回归；720仅作最后扩展性验证。

## 2. 图、端口和容量

定义下列不同对象：

- E_intra：固定同轨前后相邻环边，必须按整个研究窗验证可维持性。
- E_geom(t)：满足距离、LOS等卫星对几何条件的跨轨无向边。
- P_geom(t)：满足安装/FOV/跟踪条件的端口对((i,k),(j,l))集合。
- A_legal(s,t)：在几何基础上再满足方向机动、预约、lifetime和transition safety的可执行命令。
- Z_cmd(t)：已提交的terminal-pair目标绑定及transition计划；没有服务容量。
- E_dyn_active(t)：双端完成acquisition、可跟踪、尚未失效的物理动态连接。
- E_active(t)=E_intra∪projection(E_dyn_active(t))：快层唯一可用图。

保留Ecand一词时，必须注明是E_geom的卫星对候选还是state-conditioned端口对候选，不混用。不同策略共享geometry trace；当前orientation/reservation不同，可以产生不同合法动作集合。

每星四个独立full-duplex LCT：FWD_INTRA、BWD_INTRA、D1、D2。每条physical link占双方各一个端口，每方向各C bit/s，固定和动态同C。反向容量不相互扣减；不同端口可并行。不沿用旧整星单发送器限制。交换背板/处理能力足够是本阶段建模假设。

默认禁止同一卫星对出现两条并行dynamic link；否则simple graph和2C多重边语义会冲突。D1/D2不预设left/right，但两者的安装坐标系、可指向包络和姿态变换须显式配置；宽FOV结果只能标provisional。

## 3. 终端状态与terminal-pair action

### 3.1 每个(i,k)的最小状态

    terminal_id = (satellite_id, D1|D2)
    phase = IDLE | DRAINING | RETARGETING | ACQUIRING | ACTIVE
    current_peer = (peer_satellite_id, peer_terminal_id) | null
    target_peer = (peer_satellite_id, peer_terminal_id) | null
    reservation_id, event_version
    orientation（在已声明安装/机体系下）
    terminal_free_time
    retarget_start, retarget_end
    acquisition_start, acquisition_end
    active_link_start, visibility_end

端口peer指向对端具体terminal，不仅是对端卫星。ACTIVE时current_peer相互指向；建立中target_peer和reservation_id双端一致。DRAINING阶段旧current_peer与新target_peer可同时存在，但这是同一个端口的前后状态，不是两个并发物理连接。预约阻止第三方命令占用；旧peer在LINK_DOWN前不能被第三方抢用。

### 3.2 动作与公共执行合同

动作由terminal绑定表达：

- KEEP((i,k),(j,l))：保持已有绑定，不重复setup。
- CONNECT((i,k),(j,l))：申请新绑定，可在两端无业务时主动建立。
- DISCONNECT((i,k),(j,l))：释放已存在绑定。
- HOLD：不提交新的主动重构，继续执行已有pending事件；不是取消自然失联。

控制器输出的完整action包含保留/释放/建立绑定、依赖顺序和预约标识。卫星级proposal不是最终动作，必须经公共terminal allocator补全。保留边优先复用原terminal；同peer更换terminal是新连接。setup中禁止主动改目标；几何失效必须中止并释放预约，stale LINK_READY靠version失效。

一个新连接可能释放两条旧连接：i.D1原连j，而m.D2原连n时，CONNECT(i.D1,m.D2)的冲突释放集包括i-j与m-n。必须计入两条边的过渡影响和j/n端口变化。多命令统一预留/检查后提交；不能拆了一端才发现另一端预约失败。

每个terminal任一时刻至多一个服务peer和一个已承诺的后续目标，不允许重叠建立两个新目标。每星最多两个dynamic端口实际被占用；DRAINING的old/target不得被按两个独立端口重复计算。

## 4. 每终端BBM，允许真实资源支持的network-level MBB

### 4.1 占用终端换peer

冻结顺序：接受命令并预留→停止旧边双方向新TX→已开始非抢占服务完成且最后信号被接收→双方LINK_DOWN并释放旧绑定→双方各自retarget→双方到位后acquisition→LINK_UP。

DRAINING仍属于物理活动连接，但只完成已开始服务，不再接受新TX。LINK_DOWN起旧连接两方向capacity均为零。另一个dynamic端口和两个fixed端口继续服务。

新连接a=(i,k), b=(j,l)的ready：

    t_ret_end_a = t_free_a + tau_a
    t_ret_end_b = t_free_b + tau_b
    t_acq_start = max(t_ret_end_a,t_ret_end_b)
    t_ready = t_acq_start + tau_acq

先到位端等待并跟踪运动目标。tau需来自与姿态/星历一致的运动模型；angle/constant_slew仅能是明确标注的近似。第一版acquisition成功率1，控制信令延迟统一设0；算法计算耗时先单独报告，若以后计入控制延迟则所有方法同规则。

### 4.2 第二终端空闲时的MBB

若新边两端所选端口均真实IDLE且没有reservation，可在旧连接仍存在时建立新边；新边LINK_UP、公共安全检查通过后，再关闭旧边。这是合法network-level MBB，每个terminal仍遵循自己的BBM。

不得复制端口、借用fixed端口、占用已预留终端或提前把target边加入active图。两个端点均需有可用资源；只有一端空闲不足以免费MBB。同卫星对禁止并行边仍适用。

所有基线享有相同MBB能力。报告真实MBB次数、BBM次数、闲置端口比例和端口饱和条件。setup反例不能通过人为禁用空闲第二端口制造；需要说明资源竞争为何要求释放旧连接。

## 5. 全网连通的transition safety

### 5.1 硬条件与保护区间

对所选场景全部节点V，要求整个测量窗：

    G_active(t)=(V,E_active(t)) is connected, for every t.

不是仅保护有业务的节点或OD，也不是仅检查最终Z。初始图必须已active且连通，孤立无业务节点同样违规。

同时增加服务安全检查：将DRAINING、故障/过期及其他不能接受新TX的边从新发送服务图E_admit(t)移除；也要求G_admit(t)连通。理由是仅在E_active中保留“正在排空但不能接纳新包”的桥边，会形成账面连通、实际新业务无路。路由/dispatch必须遵守该admission状态。这是对用户全active图连通要求的保守执行细化，不是把DRAINING当成可无限继续服务。

### 5.2 验证方法

公共transition validator从当前terminal/active/pending状态建立候选事件序列，包含停止新TX、drain完成、LINK_DOWN、retarget/acquisition完成、LINK_UP以及visibility expiry。每个事件时刻前后和之间的常值图区间检查全网连通；相同时间的一组事件按真实并发结果原子检查，不允许依靠有利的任意排序制造零时桥接。

LINK_UP事件只有在双端ready、reservation有效、未过期时可增加边；已经知道的visibility expiry不能因控制器HOLD而忽略。若旧边到期与新边ready恰好同刻，按严格ready<visibility_end和保护余量处理，不能据时间舍入宣称无缝。

验证区间至少覆盖本批transition完成以及下一个可以重新决策的时刻；所有pending命令合并审计，不只检查新提交命令。若在任何时刻都已知无合法安全续接方案，该场景/初始化不得进入主实验。有限预测检查并不是任意未来的可生存性证明；运行期必须逐事件断言，全测量窗connectivity_violations必须为0，否则该run判FAIL而非性能差。

共享执行器可产生串行安全交换或利用MBB，但不得对不同算法使用不同修复规则。不存在安全非HOLD动作时记录blocked原因；HOLD如果无法避免已知断网也不能被标成安全，必须提前触发reference/可行性失败处理。第一版不通过允许临时分区继续计算性能。

## 6. 物理candidate和lifetime

检查distance、整条线段Earth LOS、安全净空、双方安装FOV/遮挡、相对机体系tracking rate/acceleration和retarget轨迹。选择哪一terminal会影响ready和可用窗口；每个端口对分别记录。

合法建链要求完整acquisition区间可行、t_ready<t_vis_end，并报告L_usable=t_vis_end−t_ready。物理最小窗口包含完整发送/接收所需时间和数值保护余量；额外minimum-hold-time是策略参数，不由物理mask代替经济决策。

visibility用明确步长筛查和边界求根/误差界；预测窗末仍可见则标右删失，不将窗末当真实断链。每条候选记录range、propagation delay、plane gap、相对E_ref的hop saving、端口对、visibility interval、retarget/acquisition和usable lifetime。由于E_intra不全局连通，跨轨hop saving不能相对intra-only计算有限值。

硬件C、FOV、slew/acceleration、tracking限制、acquisition、姿态和机体遮挡参数尚待Gate C文献标定；本合同不给宽FOV测试赋予硬件认证含义。

## 7. Reference topology和负载归一化

先冻结双端合法、全网连通、全窗可维持的reference terminal bindings Z_ref，E_ref=E_intra∪projection(Z_ref)。默认首轮使用全窗静态reference，所有方法共享它作为初始active状态，初始建链通过统一warmup排除。nearest-left/right只能是待审计的构造规则，不能逐星独立选择后忽略接收端端口冲突。

若找不到全窗静态reference，应缩短预先声明的窗口，或另行修订为真实执行handover的reference policy；不得免费更新Z_ref后仍称静态不重构。参考规则、初态和warmup不因待测算法改变。

给定G_f(t) bit/s，在有向reference图求：

    U_ref(G,t) = min_x max_e [sum_f x_e^f / C]

约束包含各commodity源注入G_f、汇吸收G_f、中间流守恒、x>=0。正需求OD不可达即归一化FAIL。g*=max_t U_ref(G,t)>0，F0=G/g*，F_rho=rho F0；理想LP精确解与完整时间覆盖下peak U_ref(F_rho)=rho。记录采样和数值误差；不逐phase重新归一化消掉热点强弱。

rho先取{0.2,0.5,0.8,1.0,1.2}，只缩放需求强度；不改C、chunk cap、setup或phase时长。它是理想可分流reference容量标尺，不是实际链路utilization，也不保证指定快层在rho<1稳定。短时rho>1不等于长期不可排空。

不同规模分别归一化会改变总Gbps；必须同时报告OD数、总/每星/每OD速率、源目的cut load、reference瓶颈及实际逐边TX/available-time利用率。冻结有限OD集合及其随规模增长的规则，不默认720 all-to-all。

## 8. 外生work trace与simulator chunking分离

### 8.1 不可变的基础业务

第一阶段f=(source_sat,destination_sat)，端点固定，profile为stable、localized-hotspot、hotspot-migration。规定normal/hotspot/migration-recovery phase边界及intensity，暂不引入地面接入切换。

外生累计到达A_f(t)以bit/work定义，与控制动作和chunk cap无关。基础trace为不可变记录：

    work_id, flow_id, arrival_time, work_size_bits, source, destination

可用连续时间compound-Poisson聚合work记录作为首版：事件时间由预定lambda_f(t)生成，work_size来自冻结的业务分布K_f，满足lambda_f E[K_f]=rho F0_f。K_f是业务特征，不是simulator chunk cap B_sim。改变B_sim不得改变lambda、K、work_id、arrival_time或基础trace hash。

也可使用累计bit曲线格式，但必须在manifest明确格式及其与上述离散work记录的对应规则；不同外生过程是业务敏感性实验，不是chunk收敛实验。每OD独立随机流；基础背景和额外hotspot分别生成，所有策略重放完全相同trace。MPC仅使用已公开强度/预测，不能查看未来随机样本；oracle明确标未来信息优势。

### 8.2 到达后切块

B_sim仅限制一次非抢占网络传输单元的最大bit数。work在原arrival_time立即可入队；可拆为多个chunk，最后不足B_sim的尾块允许立即服务，不等待凑满。若合并已到达work，必须保留每段的work_id、bit区间和原arrival_time，不改计时起点。没有到达的bit不能提前发送。

建议首版不跨work合并，以减少实现歧义；所有work按不大于B_sim分段，保持commodity FIFO和稳定bit区间ID。B_sim改变时chunk数量/hash可以改变，基础work trace、各flow累计A_f(t)及基础总bits必须逐时间一致。

禁止通过Poisson rate=R/B_sim随chunk改变来维持均值：那会改变到达方差R B_sim T，属于不同traffic。slot-batched消融单独产生带新hash的业务时间戳版本，不与chunk-granularity测试混淆。

### 8.3 粒度检验

在完全相同基础trace上扫描B_sim、B_sim/2、B_sim/4，检查包/bit守恒、累计到达一致、bit·s目标和策略差值的收敛。chunk cap仍会影响串行化、drain、事件调度及路径变化时机，因此分离trace不等于性能自动不变。Gate D必须预注册数值容差与预算，接近决策零差值处报告不确定而不是强求排名固定。

规模加速不得用改变基础业务突发性替代数值优化。10Gbps只是参考容量候选；C与K_f、B_sim分别记录，不能将归一化toy packet大小当真实网络包长。

## 9. Queue、快层与目标

节点按commodity维护bit/work队列，按需创建。chunk记录父work bit区间、flow、size、arrival_time、current_node及服务/传播状态。setup期间未开始发送的work留在队列，可沿其他active且admitting边绕行。已发送chunk不能通过换路重复注入。

精确bit守恒：arrived_bits=queued_bits+serializing_bits+propagating_bits+delivered_bits+dropped_bits。固定chunk cap的单次运行另做chunk计数守恒；跨不同chunk cap不比较chunk数量是否相等。第一版drop=0，不以丢弃减少目标。

主目标：J=E[∫_0^H sum_f w_f N_f(t)dt]，N_f是已到达尚未交付的bit，包括queue、serializing、propagating，单位bit；J单位bit·s。分段交付按被交付bit范围减少N，保留原work出生时间。完整排空时等于各交付bit的加权端到端驻留时间积分；work整体完成时延另报，不冒称等于bit加权指标。

不另外加C×setup惩罚，避免双重计数。辅助指标包括bit-weighted delay、work-completion P95、delivery-by-deadline、final residual、queue-area、non-target外部性、BBM/MBB次数、setup双端terminal-seconds、usable lifetime、path stretch、逐边利用率、连通违规和运行时。chunk P95只作执行诊断，不当粒度不变的业务QoS。

所有算法使用共同H及arrival trace。drain作为独立共同协议，必须有足够长合法geometry；无法排空时报告共同截止面积及残余，不只计算成功交付work。不能在visibility之后冻结旧图继续drain。

快层必须在Gate D前从候选routing/scheduling方案中选择一个并冻结：更新时机、平局、FIFO/跨flow调度、多路径、环路保护和无路等待都有统一规则。v0.2不冒称queue-aware shortest-path与backpressure是同一已实现算法；该选择仍是放行前待决项。控制周期Delta_c、几何步长、arrival时间互相独立。

## 10. 算法路线：proposal、allocation、safety、rollout

b-matching只作为卫星级或端口展开图上的候选方案生成器。近似边权可用queue pressure、预估路径收益、setup、lifetime及释放边代价；不声称权重精确可加，也不声称matching直接求解完整网络目标。

拟议结构化算法统一流程：

1. 从当前状态生成有限top-K topology proposals，包含保留当前方案。
2. 公共terminal allocation保留既有绑定，补全双方具体D1/D2，识别全部冲突释放边和可用MBB资源。
3. 公共safe transition checker产生/验证完整事件顺序；失败proposal不提交，不部分拆链。
4. 使用同一快层、同一预测信息、同一预算的短期network rollout评估合法方案；包含setup、绕行、其他OD及末端残余代价。
5. 与HOLD比较，选择完整terminal-pair action并原子提交；运行期逐事件断言安全。

rollout horizon需覆盖候选setup和部分可用服务窗口，或使用预先声明的统一terminal value；不能只选Hp<setup令所有重构天然劣势。不得用真实未来随机trace评估普通控制器。

基线保留Static、Ignore-Setup、Hysteresis/Minimum-Hold、AMW-style、短时MPC及小图oracle。它们共享几何过滤、terminal allocator和安全执行层。上述rollout择优是拟议算法/使用rollout的方法流程；**不得用setup-aware rollout替Ignore-Setup重新选择更优proposal**，否则它不再是Ignore-Setup。该基线仍按忽略setup的评分排序，安全层只按固定规则拒绝不合法动作并回退HOLD/下一候选；真实执行经历真实setup。分别保存建议动作、过滤原因和执行动作。

MPC比单步proposal增加搜索深度/时间计划；matching与MPC要报告K、Hp、调用次数和计算预算。AMW-style为启发式迁移，未获得原理论在该模型下的稳定性保证。oracle说明枚举的是连接/端口/顺序还是也包括routing，以及是否具有未来信息。

RL/PPO/MARL不在本合同当前实现范围。

## 11. Gate与放行条件

| Gate | 内容 | 放行条件 | 当前状态 |
|---|---|---|---|
| A | Walker-Star审计修复与几何资产 | 负向测试拒绝错误、STK smoke、720 r/v审计、160/240严格抽取 | 旧预审FAIL；本轮仅修复方案 |
| B | 独立双dynamic状态机 | terminal唯一性、双边预约、BBM/MBB、drain、abort、stale event | NOT_RUN；本轮禁止实现 |
| C | geometry、candidate、reference与安全 | 参数表/标定状态、lifetime、全窗reference、全transition全网连通 | NOT_RUN |
| D | traffic、queue、快层 | 基础trace与chunk分离、bit/事件守恒、rho、粒度收敛、快层冻结 | NOT_RUN |
| E | 机制反例 | 在新2+2模型重新验证等容量错切、其他OD外部性、arrival timing | NOT_RUN |
| F | 160/240主实验 | 强基线、公平信息/资源、配对seeds、动作空间非退化 | NOT_RUN |
| G | 720扩展性 | 少数冻结方法、OD/candidate增长规则、运行时/内存 | NOT_RUN |

每Gate输出deterministic配置、seed（确定性几何也记录不使用随机数）、manifest、断言、输入/输出hash和明确PASS/FAIL。不能把文档冻结、配置存在、几何采样通过当作后续执行或性能通过。

## 12. 当前未决项与修订追踪

用户六项决定在§1、§3、§4、§5、§8、§10落地。尚待正式实验前冻结：硬件/姿态数值与文献来源；reference具体绑定及可维持窗口；OD列表/业务K分布及跨规模规则；快层算法；Delta_c与几何步长/误差界；rollout预算、chunk收敛容差、测量/初始化/drain协议。

这些未决项不影响本轮文档交付，也不授权现在进入B–G。Gate A的实现只按配套修复方案另行执行。本轮输出不是新仿真器，也不继承旧sender-only实验的topology-control性能结论。

> 几何合同已更新至 [v0.3](LEO_dynamic_LISL_experiment_plan_v0.3.md)：正式采用 synthetic-TLE + SGP4/WGS72 + TEME。本文仅保留历史语义。
