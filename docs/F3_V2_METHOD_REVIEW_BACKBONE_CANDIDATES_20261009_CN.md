# 重读文献后的方法收敛审查：固定骨干、候选生成与重构决策

日期：2026-10-09。性质：READ_ONLY_RESEARCH_REVIEW / ADVISORY_NOT_FROZEN。

本报告重新阅读用户提供的三篇PDF、检索两篇相关原始论文，并核对当前候选源、批量验证器、transition profiler及最新成本/结构证据。没有修改生产代码、冻结合同、候选策略或业务资产；没有运行控制器实验、K0、P1/P2或RL。这里的建议不构成人工批准的新合同，也不替代历史FAIL。

## 结论

建议修改方法的组织方式，并审议是否调整第一篇论文的网络架构。当前难点不只是2-fixed+2-dynamic，而是同时承担：基础连通维护、性能增强链选择、状态相关双端物理重构、四链联合搜索、全网队列rollout，以及精确K选择。研究setup造成的服务机会成本，不要求第一篇论文同时解决上述所有问题。

首选的科学收敛方向是：**已经物理验证的连通骨干 + 受资源限制的动态增强链，在多OD队列下判断重构是否值得**。3-fixed+1-dynamic是有文献依据的候选架构，但只有在当前Walker-Star/子场景、双边固定端口和整个窗口上验证后才能采用，不能因为文献画了T-shaped就认定当前160星可直接成立。若不可行，可审议保留2+2但使用真实端口和真实寿命的受保护跨轨骨架；不允许凭空添加永久连接。

## 1. 2+2的确带来连通性耦合，但不是全部成本原因

`src/dynamic_lisl/reference_topology.py::intra_plane_rings`只构造同轨环。当前四轨160星的固定部分本身是四个分量。动态跨轨链既承担基础连通，又承担业务加速。移除bridge的BBM会使分量分裂；四个各自安全的单项动作组合起来也未必安全，因为资源独立不等于图连通性独立。

`src/dynamic_lisl/transition_profiler.py`并非只做一次连通图检查：它克隆真实执行器、提交命令、推进事件，在不同阶段检查active/admit图。`BatchSafetyValidator.evaluate`先执行完整physical validation，再调用该profiler。保留严格连通合同期间不能只检查最终新图。

但`src/dynamic_lisl/f3_v2/candidate_source.py::replacement_inventory`已经在连通性检查之前遍历old binding ×全部当前terminal-pair窗口，并逐项调用`BatchPhysicalValidator`。raw cap是输出截断，不是物理验证调用上限。历史K4/t0有7980次物理调用；本轮有限scout probe的source仍有约255/256次单项validator入口。source不调用BatchSafetyValidator，因此不能把全部source成本归给全网连通性。

最新独立K4/t0测量：source19.155秒，joint proposer22.926秒。source主要是资源/物理验证、状态克隆和hash等；proposer含物理与全transition safety。K24/t0 proposer75.268秒。两类嵌套wall不能重复相加，且当前没有单独测出纯BFS/DFS的时间占比，不能声称连通性检查占百分之多少。

另一个独立瓶颈是全网服务rollout：自然t5的27分支，serial observe895.703秒，8-worker194.355秒。这不是候选几何计算或连通性判断本身的费用。

已知20-node fixture遗漏也不是连通性导致：144个身份全部被scout并物理验证，raw只保留C0/C1目标端口，使资源独立batch上界成为2；原size3/4 witness经原B/C仍合法。换成3+1也不会自动修复这类截断偏置。

## 2. 文献实际如何缩小问题

|论文|原文中的具体做法|对本研究的启发与边界|
|---|---|---|
|Wang等，TCOMM 2024，Optimization for Dynamic Laser Inter-Satellite Link Scheduling With Routing|Sec. II-B、Fig.2：3个固定LISL形成T-shaped，保障连通和基本通信；动态端口有7个对象或关闭；Sec. II-C要求每槽业务在槽内完成；模型包含流量/容量和逐槽链负载，而不是本项目跨时刻Q/I持久执行器|固定骨干与动态增强分工、小局部动作集可借鉴；不能声称采用其MARL或7对象集合就解决本项目物理/队列问题。论文已涉及负载，不能称其完全不考虑拥塞|
|Nie等，TVT 2026，Dynamic Topology Control Strategy for LEO Mega-Constellation Networks|Sec. II/Fig.2：同轨前后两固定链+交替向左右相邻轨道的一固定链；剩余端口动态连接。候选经过距离、角度、寿命过滤；Sec. II link-duration段明确不聚焦重构时间/能耗，认为几秒建链相对长slot较短；Sec. III采用DPSO及matching修正端口冲突|支持稳定骨干+几何过滤+匹配proposal的分层思想；其目标和长slot近似不能代替setup期间真实服务/队列演化。matching只处理资源，不等于求解本项目整体动态控制|
|Bhattacharjee等，TAES 2024，On-Demand Routing…|Sec. IV：ILPR持有现有路由直到失效；ALPR考虑平均时延；ISASR结合link stability与已激活状态。结论明确将queue status/congestion与setup的联合考虑列为后续方向|保持连接和剩余寿命是合理切入点；该文主要按OD路径和setup时延组织问题，不等于本项目多OD、具体terminal-pair占用与network-wide J|
|Ron等，INFOCOM 2025，Time-Dependent Network Topology Optimization…|DTEG/DoTD将capacity、latency和link churn转为时间相关score，再按端口约束选连接；没有采用当前真实Gate B/C及Q/I/D joint rollout合同|说明预测不必等于对每个动作调用完整仿真器；该预印本的score、无线信道参数和模型与光学终端执行器不同，不能借其复杂度/最优性声明推断本项目保证|
|Wang与Javidi，Adaptive Policies for Scheduling With Reconfiguration Delay|非零重构时间的光交换系统中，用queue-weight improvement与保持阈值决定是否换配置，并在特定条件下证明稳定性|低复杂度setup-aware保持策略有充分研究基础；直接把hysteresis改名不能作为新贡献。其单交换机、到达过程及可行调度假设不直接适用于多跳卫星有限寿命网络|

以上不是穷尽性新颖性检索。它们支持方法收敛，但不能证明“文献从未联合考虑本项目要素”。论文仍需针对具体新算法进行查重。

## 3. 不能把候选链路、物理动作与控制价值混为一层

应明确三层：

1. **几何候选链**：由distance/LOS/FoR/双边terminal-pair窗口给出，与当前要释放哪条旧链、未来业务实现不同。当前已存窗口可以作为索引输入；只有真正与占用/历史无关的部分才能预计算。
2. **物理动作候选**：某条旧binding到某个新pair，或多项组成batch。包含占用、预约、draining、setup-ready、usable window等状态条件。几何可见不等于当前可建；静态索引不能跳过最终B/C验证。
3. **控制价值**：动作可建之后判断是否值得。应体现整条路径或网络队列的有效服务改变，不能只按新链距离、链路容量或剩余寿命评分。J仍为主评价目标。

建议的新政策方向为“几何索引→低成本资源排除→有限且有端口多样性的局部候选→资源独立batch→完整B/C和安全验证→轻量service估计/少量真实rollout”。需要重新批准明确的输入域、覆盖规则、预算及遗漏报告。这是启发式候选/方法修订，**不是声称保持原候选集合的工程缓存优化**。

B1/B2/B3/B4必须共用相同规则和预算；只允许控制器按本来信息边界作决策。初始K/骨干构造继续不得用最终J选取。若引入current-queue候选排序，它本身也须单独预声明，不能在当前结构probe中悄悄加入。

不要把“每种状态必须找到size4”当作物理要求。需要区分无合法size4、未覆盖、截断遗漏及组合搜索遗漏；只有已证明存在的witness才必须在对应验收域被发现，不能用自然域UNKNOWN假装无解。

## 4. 架构调整的比较

|方案|第一篇论文中主要回答的问题|真实代价/限制|
|---|---|---|
|2固定+2动态，全动态域自由REPLACE，严格全过程连通|同时解决基础跨轨连通与性能增强|连通维护、资源、自然expiry、动作组合强耦合；不能只靠增加beam或worker化解科学问题范围过大|
|2+2，真实受保护跨轨骨架，其余动态链可重构|在2+2硬件下把基础连通与业务增强分层|骨架占用D1/D2；不能额外占用虚构fixed端口。骨架自然到期时需预声明维护策略或证明整窗可维持；当前可行性UNKNOWN|
|3固定+1动态，物理验证连通的T-shaped骨干|动态增强链的服务收益是否抵消setup/绕行/共享拥塞代价|动态资源减少，骨干构造与固定链PAT/FoR须验证；原同星第二动态端口MBB不能沿用；新链两端在其他卫星真实空闲时不必排除所有network-level MBB|

从科学问题隔离和第一篇论文可解释性出发，倾向3+1连通骨干方案；不因旧代码复用而保留复杂模型。**但不承诺它在当前自然几何中可行或一定更快**。Walker-Delta论文的左右交替规则不能直接复制到Walker-Star seam，也不能删成160星子图后默认仍连通。每星固定度数、双边一致、seam/边界、整窗可见/FoR及固定身份的持续性都要证明。逐时换固定peer实际上是重构，不能伪装永久fixed。

若E_backbone(t)在研究窗口每个时刻都连通且一直admit服务，则删除任意dynamic边不会造成全网partition。这是图论上的充分条件。此时setup仍然有经济代价：业务退回更长或更拥塞的骨干路径，Q/I和J上升。**连通不等于无setup代价**，因而研究核心并不消失。

若选择新骨干，需要新版本合同、重新验证物理窗口/固定port和traffic reference alpha*；不能沿用旧骨干的rho数值含义或旧controller性能。SGP4轨迹、终端执行器、服务kernel和旧证据可作为资产保留；不自动重跑所有历史实验。K0与42项旧草案若已不再服务新问题，应提交合同修订，不继续为了完成旧门槛而耗费大量计算，也不在此报告内自行删除。

## 5. 方法建议与唯一下一步

保留科学问题：**面对多OD队列、双端有限资源、setup和有限可用窗口，何时重构能降低network-wide unfinished work？**

不要预设MPC必须是主算法。先比较简单minimum-hold与具备路径/队列服务估计的setup-aware策略；真实rollout可暂作小规模/少量候选的参照，判断预测的增量价值是否足以支持其成本。当前B3/B4证据还不能宣布这一增量存在，也不能将现有B3 proxy直接封为新主方法。

建议唯一下一步是一个**result-blind连通骨干可行性审查**：在既有SGP4窗口中，检查可复现3-fixed+1-dynamic规则能否在整个当前研究窗口形成双边、端口合法、物理持续可行的连通骨干；同时静态评估2+2受保护骨架备选，保留UNKNOWN。先用这个结果决定架构，不运行J比较、不调traffic/K、不先实现新的controller。若需要重新计算固定terminal FoR或cross-plane窗口，先列出输入缺口及成本，不默认现有dynamic窗口覆盖新的固定端口。

本轮没有执行这个新Gate，只给出建议。当前scope A、生产2+2、5秒、batch上限4和历史hash约束保持原状态；任何变更须独立版本审批。报告不授权冻结或正式运行。

## 原始来源与代码证据

- [TCOMM 2024原文](D:/Document/leo_routing_attitude/参考文献/Optimization_for_Dynamic_Laser_Inter-Satellite_Link_Scheduling_With_Routing_A_Multi-Agent_Deep_Reinforcement_Learning_Approach.pdf)，Sec. II-B/II-C、Fig.2；[DOI](https://doi.org/10.1109/TCOMM.2023.3347775)。
- [TVT 2026原文](D:/Document/leo_routing_attitude/参考文献/Dynamic_Topology_Control_Strategy_for_LEO_Mega-Constellation_Networks.pdf)，pp.14757–14759、Sec. III；[DOI](https://doi.org/10.1109/TVT.2026.3660872)。
- [On-Demand全文](https://arxiv.org/html/2406.01953v1)，Sec. IV及VI。
- [DoTD作者预印本](https://arxiv.org/html/2501.13280v1)，Sec. II-D/III。
- [Adaptive Policies原文](https://arxiv.org/html/1511.03417)，Sec. III。
- [最新集中审计](D:/Document/leo_routing_attitude/dynamic_lisl_v2/docs/F3_V2_CRITICAL_BLOCKER_CLOSURE_DECISION_CN.md)。
- 当前候选源：`src/dynamic_lisl/f3_v2/candidate_source.py`；物理/安全：`src/dynamic_lisl/f3_v2/batch_executor.py`；事件图检查：`src/dynamic_lisl/transition_profiler.py`；同轨骨干：`src/dynamic_lisl/reference_topology.py`。

STOP：本轮仅文献与设计审查，不修改源码/冻结合同，不启动正式实验。
