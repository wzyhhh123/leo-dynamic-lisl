# 能源约束下的按需动态激光星间链路重构：研究框架草案

日期：2026-10-09。状态：**RESEARCH_DIRECTION_ACCEPTED_FOR_DISCUSSION / MATHEMATICAL_CONTRACT_DRAFT_NOT_FROZEN**。

本轮用户明确要求暂停旧实验，按持续连通、动态K、每星动态终端能源预算的新框架继续梳理。旧F3-v1/F3-v2、K0及历史证据保持原样。本文件是新的研究草案，不修改生产执行器、冻结资产或旧42项实验manifest，不授权实现ADD/DROP、能源模块、控制器或正式实验。

## 1. 研究问题与范围

暂定题目：**面向低轨卫星网络的能源约束低时延按需拓扑重构**。

英文暂定：Energy-Constrained On-Demand Topology Reconfiguration for Low-Latency LEO Satellite Networks。

研究问题：在网络持续连通、动态激光终端数量和每星能源预算有限的条件下，如何根据时变多OD业务建立、保持、释放和重构跨轨激光连接，并显式考虑双端状态化建链、有限可用窗口及真实队列服务，最小化全网累计未交付业务。

核心矛盾：额外连接可以提供捷径或缓解共享瓶颈，却持续消耗本端能源和占用终端；释放连接节省后续运行能量，却可能降低服务或破坏连通；替代连接需要setup和资源重叠，收益只有在建成后且仍可用时才能实现。

用户本轮确定的新方向边界：

- 场景继续以已有160星、4轨道面、每星2固定同轨+2动态LCT为基础；不自动改为3+1。
- K允许变化；持续连通；能源作为每星硬约束；J为唯一主要通信目标。
- 动作概念扩展到HOLD/ADD/DROP/REPLACE；先集中式；暂不选MPC或RL。
- 不研究临时分区保障、DTN路由、完整电池/太阳能、姿态/热管理或光发射功率联合优化。

这使动机更明确，但**不是自动简化算法**：2+2仍须维护跨轨连通，ADD/DROP增加动作种类，能源增加未来可行性条件。候选计算昂贵的问题仍需要分层和有限预算解决，不能期待变量K自动消除它。

## 2. 图与真实资源定义

设卫星集合V，动态端点集合T={(i,D1),(i,D2):i∈V}。物理动态binding必须为具体双端pair b=((i,k),(j,l))，不能只保存i-j。

定义固定可服务边E_fix,admit(t)，动态物理存在边E_dyn,active(t)，动态可接纳新TX边E_dyn,admit(t)。物理存在的旧链在DRAINING期间仍可完成已开始TX，但不能接纳新的TX，因此两动态图可能不同。图投影为卫星级边时需保留端点绑定；默认不允许同卫星对两条并行动态链。

G_admit(t)=(V,E_fix,admit(t)∪E_dyn,admit(t))。

K_active(t)=|B_active(t)|，K_admit(t)=|B_admit(t)|，其中B按无向physical binding计数，一条双向链只计一次。容量沿用已有冻结full-duplex/调度语义，在新合同中明确引用，不能与能量计数混淆。

### 是否必须额外设置全局K_max？

建议第一版**不引入额外的人为全网链数硬上限**，待审议，不视为已冻结。

每星两个dynamic terminals、每条物理链占两个端点、端点独占，已经给出：

\[
K_{active}(t)\le\frac{|T|}{2}=160.
\]

该上界是端口计数上界，不是当前几何可达到的链数，不说明160条链可建；FoR、窗口、同星对禁并行及busy/setup会进一步缩小可行域。reservation/SETUP不是ACTIVE链，必须由独立终端资源约束计入占用，不能仅靠K_active检查。current_peer+target_peer在BBM预约中不是两套虚构端口。

若以后有独立工程依据（全网光学运行配额、控制开销或另一个任务资源政策），可另外引入K_max^op<160。须写明来源，且MBB重叠期计入实际K_active；不能把setup中的pending连接和ACTIVE数混为一谈。能源预算不是瞬时链数限制，也不等于瞬时电功率限制。

四个固定同轨连通分量要由动态边连接，所以K_admit≥3是必要条件；轨道面收缩图必须实际连通，任意三边不充分，端口/几何可行也不能由计数证明。

## 3. 连通安全与自然失效

要求研究窗口H内所有会改变图的事件之后及事件之间：

\[
\operatorname{Connected}(G_{admit}(t))=1,\qquad 0\le t\le H.
\]

同时沿用原STRICT_CONNECTED的active/admit双图检查。若固定admit边始终服务且active包含admit，admit连通蕴含active连通；仍保留两个状态和原检查用于审计。

连续时间由真实事件驱动：DRAINING、LINK_DOWN、LINK_UP、expiry、abort和原事件优先级/同时间原子settlement均不得跳过。即使决策只在离散时刻发生，也不能仅检查决策快照或目标图。

- ADD：仅用双端真实IDLE且未预约端口；旧图不改变的情况下新增边单调改善连通。但同时发生的旧链自然expiry仍需验证。
- DROP：双端释放；DRAINING起即移出admit图，已有非抢占TX完成后物理LINK_DOWN。删除单个非bridge是当前图必要的安全检查；多个各自非bridge边可能构成cut，因此联合DROP仍须整批验证。
- REPLACE：同一occupied端口严格BBM；真实idle资源允许先建后释放的network-level MBB。释放时间不得提前于新链ready及旧TX draining完成要求；实际B/C决定类型，控制器不能自称MBB绕过状态检查。
- HOLD：不是无条件安全。已知桥链即将自然到期时，HOLD也可能使下一次决策来不及恢复连通。

周期Δ和最大setup/drain时间决定必须提前准备多久。提前看见至少Δ+所需setup只是一个保守准备条件，不是完整可行性证明；候选不存在、能量不足、端口冲突或同时expiry都可能使问题无解。决策周期、batch大小、准许的操作组合及是否使用独立维护层尚待新合同定义，不自动继承旧5秒/4条数值。

**转移安全**（本动作直到完成的图连通）与**递归可行**（之后仍有合法、能源足够的继续控制）须区分。有限10秒profile不能证明600秒持续连通。若采用共同连通维护层，它的动作、代价、端口权限和信息必须对所有方法一致、显式记录，不能只帮助某个方法选更经济的链。

建议先寻找并验证完整窗口的一个资源/能源可行maintenance witness，作为场景可行性证据；尚未生成，存在性UNKNOWN。若用它保障在线递归可行，必须证明候选执行后的状态还能接续该策略，不能只拿初始witness当保证。维护过程中能源余量要一起检查。

600秒是观察截止，不是自然expiry。右删失链窗口只能证明观察范围内可用；不能伪造失效或根据600秒以后的未知信息修复动作。

## 4. 终端能源模型与计量合同

直接沿用Gate B五种phase：IDLE、DRAINING、RETARGETING、ACQUIRING、ACTIVE，不改名或另造状态机。第一版不加入OFF、开机/预热、太阳能、电池SOC或姿态功耗。

每终端的piecewise-constant功率为P_(i,k,x)，量纲W；可以先采用同类型终端相同状态参数。每星累计动态终端能量为

\[
E_i(t)=\int_0^t\sum_{k\in\{D1,D2\}}P_{i,k,x_{i,k}(u)}\,du,\qquad E_i(H)\le B_i.
\]

量纲J。每条链两端各计本端功耗，不能一端漏计或把单terminal功率误当双端链总功率。ACTIVE在无payload时仍需PAT；固定参数模型可忽略传输负载对功率的变化，但须声明近似。DRAINING仍可能发送，不能默认功率为零。abort前已经耗费的setup能量不退回，KEEP不重复setup。

按每端点状态分段区间[t_a,t_b)积分；同时间settlement不产生虚构持续时间。终端不是通信图边，能源计量不能只按E_active乘一个系数。若没有OFF且所有状态功率非负，应检查B_i是否至少覆盖允许策略的standby/maintenance需要；不能假设预算小于必要能量仍总能执行。

若参数P_x=P_idle+δP_x且δP_x≥0，可写E_i=2P_idle H+E_i^incremental。增量能量只能用于明确转换后的预算，不能把总能量预算B_i直接与增量核算比较。若无足够依据证明所有δP_x非负，不作该分解或额外下界声明。

**硬件来源边界**：TESAT官方SCOT80页面给出10 Gbps bidirectional与60–80 W产品功耗，但并未在该页给出本模型五状态各自功率，也不说明两个当前动态终端必须使用该产品。Honeywell LCT资料中的Tx optical W也不能当整终端电功率。各状态参数未冻结，应从同一类型资料获取或明示为参数化假设；不得将多产品数值拼成一个已验证硬件合同，不默认P_ret/P_acq一定高于P_active。

模型仅代表动态LCT子系统能耗，不代表整星耗电、剩余电池寿命或太阳能平衡。每星能量预算不是瞬时总线功率保证；第一版可以声明平台支持两个动态LCT并发工作，不另优化P_max。若缺乏依据或硬件明确限制，则须另定义每星瞬时功率约束，不能借B_i替代它。

## 5. 统一窗口、交付与主目标

建议数学合同用统一H=600秒和已有arrival0–240秒作为草案示例；是否正式沿用以及traffic归一化参照待批准。定义

\[
N_f(t)=A_f(t)-D_f(t)=\sum_iQ_i^f(t)+\sum_eI_e^f(t),
\qquad J_H=\sum_f\int_0^HN_f(t)\,dt.
\]

为避免有限窗口J鼓励截断尾项，完整交付问题须增加

\[
N_f(H)\le\varepsilon_f,\quad\forall f.
\]

ε_f必须单独冻结。旧F3总unfinished≤0.01 bit不是每flow各0.01 bit；不能复制后暗中放宽总容差。若所有业务提前完全排空，则N=0后的积分为零，J_H与积分到最终completion的J等价；若只剩容差尾项，须按统一未送达核算保持一致，不clamp。

只有所有工作都按完整业务守恒计入且完成时，J/A_total才可解释为平均bit sojourn time（零初始业务条件下）。它包括排队与传播，并非仅packet传播时延。若有初始Q/I，则需明确其到达/年龄及目标积分起点。

**能耗比较继续到H**：业务提前排空不代表全网连通要求结束，也不代表所有dynamic terminals自动OFF。必须保留自然expiry、maintenance、终端状态及能耗积分至H；无业务的拓扑尾段策略须共同预声明或明确作为各方法策略的一部分。不能把完成时的状态直接乘剩余时长而忽略自然失效/维护。新的能源run不能直接使用旧early-return当能耗结束。

实验状态区分：COMPLETE且资源/连通合法；CENSORED残余未达交付门槛；ENERGY/CONNECTIVITY_INFEASIBLE；执行invariant失败。censored保留J_H诊断、residual/delivery等，不用截断J作完整性能排名、不把未送达当丢失。算法未完成不等于全局问题无解；只有严格证书才可断言场景不可行。

## 6. 修订后的概念全局问题

\[
\begin{aligned}
\min_\pi\quad &J_H(\pi)\\
\text{s.t.}\quad &\operatorname{Connected}(G_{admit}^\pi(t))=1,\ \forall t\in[0,H],\\
&E_i^\pi(H)\le B_i,\ \forall i,\\
&N_f^\pi(H)\le\varepsilon_f,\ \forall f,\\
&A_n\in\mathcal A_{physical}(S_{t_n}),\\
&\text{双端资源/预约、真实BBM/MBB、LOS/FoR、窗口及expiry约束},\\
&\text{容量、固定common routing/service、Q/I/D业务守恒约束}.
\end{aligned}
\]

K_active上界由端口独占自然导出；只有存在独立资源理由才增加K_max^op。不加任意switch/setup/outage penalty到主目标。能源资源约束会改变可行域，但不自动保证控制器主动节能：预算宽松时可能多保留链路，低负载时K下降只是待验证假设。

预算余量R_i(t)=B_i−E_i(t)。只检查setup能量不够；还须处理后续维持连通的消耗。剩余时间的能源lower bound可以拒绝确定不可行的状态，不能证明可行。若用显式可行maintenance continuation的能量upper bound认证，则该continuation需真实可执行、所有卫星分别满足预算、与candidate之后的状态/事件相容；不能重复计费或将lower bound冒充reserve guarantee。

## 7. 算法接口与信息边界

观察当前几何/terminal-pair窗口、真实端口/预约、active/admit图、Q/I/D、当前业务速率、累计能量/预算。可预测轨道与已知物理expiry；业务forecast与未来realization区别沿用，主方法不可读取实际未来arrival trace实现、未来动作或最终J。

流程：几何候选索引→廉价资源排除→有限ADD/DROP/REPLACE候选→真实整批物理与连通/能源可行性→时延决策→原执行器及service推进→按状态积分能源。筛选与评估预算、候选端口多样性、联合动作规模及合法重叠顺序仍待合同，不预设原beam/scout数字继续合适。

ADD只能占用真实idle端口；DROP不能粗暴删除在途业务或已开始TX；REPLACE不等于任意同步DROP+ADD。整批命令原子预约与物理过程非瞬时仍分离。BBM是每端口约束，MBB必须有真实spare。多个ADD/DROP/REPLACE之间是否允许共享未来释放端口尚未定义，先不要实现跨动作隐式资源借用。

集中式安全层只做物理与明确硬约束检查；若有强制维护动作，要单独定义common maintenance policy，不静默替控制器优化经济决策。控制器比较需同初态、同budget/power参数、同trace、同fast layer、同action权限/候选规则、同信息和共同评估窗口。

方法暂不锁定MPC或RL。先在小场景检验可解释的资源-aware保持/释放/建链规则及路径级有效服务估计；真实rollout可作为参照，后续再判断是否值得主算法成本。新框架不继承旧B4或旧search policy的PASS，尤其ADD/DROP和energy尚未实现。

## 8. 新颖性与资产迁移

能源与可变连接数本身不是空白。用户TCOMM 2024原文已采用3fixed+1dynamic、可关闭dynamic link，并优化通信hop与运行能源；TVT 2026也以hop/动态链数衡量性能和资源。TNSM 2022研究从grid-mesh移除部分ISL以改善资源利用并维护可靠性。官方Journal of Astronautics 2026摘要也已有资源受限小星座动态拓扑研究。因此不能以“首次考虑能源”“动态K就是创新”直接立题。

待论证的贡献应落在：**每星硬预算 + 有状态真实重构 + 持续可服务连通 + 多OD持久队列**的具体决策方法/可行性机制与收益边界。该组合是否已被完整覆盖仍需针对原文审计，目前不宣称新颖性已通过。

资产分类：轨道/TLE/SGP4、窗口与B/C、Q/I/D和守恒/clone/配对方法可作为基础资产；旧归一化参照与traffic模板须在新初始拓扑和资源合同下审议后使用，rho不能按每方法自身容量重新归一化。旧controller评分、K*选择、固定K动作与42项比较不是新科学合同。旧结果均保留，只能按其原问题解释。

现有Gate B已具备Connect/Keep/Disconnect等低层命令，但F3-v2上层JointAction/候选与validator仍是REPLACE专用；低层有Disconnect不代表新的DROP控制路径已经验收。状态时间线可支持能源积分，但功率、预算、reserve和能源正确性测试尚不存在，不视为已实现。

## 9. 未决项与下一步

第一步只完成物理/数学合同及小例子，不进入大型实现：

1. 以原几何窗口审议全窗连通maintenance witness、自然expiry准备策略及其端口/能源需求；成本/存在性UNKNOWN。
2. 定义五phase功率参数来源与预算标度，区分总energy与incremental；所有数值未冻结。
3. 定义初始connected状态、预算起点、固定H及业务排空后的共同能耗/维护尾段。
4. 定义每flow/全网delivery容差、energy/连通失败与censor分类。
5. 定义决策周期、操作batch/候选预算、maintenance与性能控制的职责；再选择低复杂度方法与对照。

没有足够依据时不要填入具体K_max、B_i、P_x、周期、batch或新run矩阵。旧10/31/11月底目标需待新合同及成本重新评估，不保证原42run时间表仍适用。

## 10. 原始来源

- [TESAT官方产品参数](https://www.tesat.de/products)，SCOT80部分；仅支持产品级数量级，五phase功率未知。
- [Honeywell LCT100Y原厂资料](https://prod-edam.honeywell.com/content/dam/honeywell-edam/aero/en-us/products/emerging-technologies/space/space-communications/lct100y/documents/hon-aero-n61-3119-000-000-lct100y-laser-communication-terminal-en.pdf?download=false)，区分optical Tx与整terminal用电。
- [TCOMM 2024原文](D:/Document/leo_routing_attitude/参考文献/Optimization_for_Dynamic_Laser_Inter-Satellite_Link_Scheduling_With_Routing_A_Multi-Agent_Deep_Reinforcement_Learning_Approach.pdf)，Fig.2/Sec.II及优化目标。
- [TVT 2026原文](D:/Document/leo_routing_attitude/参考文献/Dynamic_Topology_Control_Strategy_for_LEO_Mega-Constellation_Networks.pdf)，Sec.II/III。
- [TNSM 2022出版社摘要](https://doi.org/10.1109/TNSM.2022.3168148)。
- [Journal of Astronautics 2026官方摘要](https://yhztjs.spacejournal.cn/en/article/id/a119ecbb-c655-4a06-88be-2b5e08666580)，未完成全文重构/queue语义审计，不据摘要断言已覆盖本问题。
- [On-Demand Routing作者原文](https://arxiv.org/html/2406.01953v1)。
- [Adaptive Policies作者原文](https://arxiv.org/html/1511.03417)，交换机理论不能直接作为卫星网络保证。

STOP：旧实验暂停；新问题只做讨论草案，不实施算法、不执行正式实验。
