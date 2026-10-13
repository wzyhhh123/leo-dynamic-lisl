# PILOT_PARAMETER_MANIFEST_DRAFT

状态：PILOT_ONLY / DRAFT_FOR_REVIEW / EXECUTION_BLOCKED_PENDING_NEW_SCORER。编制日期：2026-10-12，北京时间。用途：探索突发热点下滚动预测控制是否值得继续研究；不是正式实验预注册冻结，不是 MPC 必要性证明，也不是 GNN 验收。

本轮仅完成只读审计、静态几何抽查和仓库外文档。未运行网络仿真、预测分支、预实验、训练或回归测试。所有下列新增数值仅为待审核 PILOT_ONLY 草案，不写入任何正式配置。

## 版本和信任绑定

研究根目录：`D:/Document/leo_routing_attitude/dynamic_lisl_v2`。实施基线为 `research_versions/dynamic_k_v1/revisions/0007/record.json`，当前完整记录链已到 0009；0008/0009 为 README 文档修订，不更换 N1a/N1b/N2/N3 实施绑定。

|对象|独立 SHA-256|
|---|---|
|版本起点|`ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691`|
|实施修订 0007|`f58cc5eb037eaf6ee804c9aa1c5ec54f38894d00ca0d715f8b7baae8a47e06db`|
|0007 implementation_manifest_attempt02.json|`dbc7e0d54d6d9bb864ec216a0b7c6cd1b86ec6353ed3ab41a3c3c64b471b9129`|
|当前记录 0009|`bd54f8efb78375acca995b8ed43f5ccbfb4be80228d46eb2ca2ab5e954d86342`|
|迁移前 baseline seal|`2c4d329a9fa2839ab181115e97a75a3dabfb6472961b69909f6b789ec04a6f4f`|

本轮起始完整验证 PASS：5966 个受保护文件，5810 个基线文件，202 个已登记排除项；未登记新增、删除、修改、重命名均为空。使用 `tools/version_control_readme_v1.py verify` 验证当前 0009 和版本起点，并核对上述 0007 实施哈希。原校验器对根 README 的限制没有被静默绕过，0009 的精确文档例外使用已有专门校验器。该 PASS 仅证明版本完整性，不是新预实验、MPC 或科学 Gate PASS。

## PILOT_ONLY 参数草案

|参数|草案值|单位与边界|
|---|---:|---|
|真实评价 T|30|s；每个控制器推进到同一 T，提前排空仍继续计能耗|
|真实注入 T_A|20|s；真实业务仅在 [0,20) 注入；控制器不得读取未来分段|
|最大预测 H|6|s；实际 h(t)=min(6,30−t)，不预测到真实评价终点之外|
|决策间隔|1|s；epoch 为 0,1,…,29；30 只结算，不提交新动作|
|双端 retarget|各 0.5|s；两端空闲时并行重指向，随后共同捕获|
|acquisition|0.5|s；保持 Gate B 真实动作时序|
|原子动作提交上限|每 epoch 1 个|仅本轮工程约定；不冻结最终联合动作空间|
|预测分支动作计划|首个原子动作后 HOLD 到 t+h|不搜索未来多步动作序列，不使用未来策略 oracle|
|每个有向边容量 C|1,000,000|bit/s；固定边和动态边相同，两个方向各自约束；不是单条双向链路共享总容量|
|commodity 权重|均为 1|跨 commodity 原 equal-weight max-min 不变|
|数值检查|time=1e−9 s；energy=1e−6 J；business=1e−6 bit|显式工程容差，沿用 N3 fixture 形式；不得放宽以吞掉失败|
|预测候选保留|HOLD 1、ADD 至多 2、DROP 至多 2、REPLACE 至多 2|总计至多 7；REPLACE 尽量各保留一个合法 BBM/MBB；仅小候选域|
|新增并行 workers|暂不设定|先串行正确性；不继承旧 B4 的 8-worker 要求|

正式 `T_A,T,tau_res,R_min,alpha,D_ref,E_ref`、正式决策周期、并行动作上限和搜索预算继续 null。功率继续使用已授权模型：IDLE=5 W，RETARGETING/ACQUIRING=40 W，ACTIVE/DRAINING=45 W，每个真实动态终端单独计费。

## 时间参数可执行性审计

Gate B 空闲双端的 ready 为 `max(t_free_a+retarget_a,t_free_b+retarget_b)+acquisition`。因此 0.5/0.5/0.5 对应 1.0 s 空闲 setup，而不是 1.5 s。BBM 还可能增加真实 TX drain 等待；MBB 必须有真实空闲双端。每次仍由 N2 判定 ready 严格早于合法窗口结束，setup 中 K_admit 不增长。

静态抽查使用冻结合成 TLE 的真实 SGP4 状态、球体 LOS 和双端 RTN FoR。在 t=0,1,…,30 共 31 个时刻，初始桥 `X0_1/D2↔X1_1/D1` 与热点直连 `X0_10/D2↔X1_10/D1` 均通过。前者 catalog 窗口 [0,600]、右删失；后者 [0,147.04275553019596]、非右删失。两者覆盖本轮所有 free-end setup 和截短预测窗口。这是点位抽查加既有窗口证据，不是新连续可见性证明或硬件校准；所有其他候选仍需实时 N2 验证。

实时距离/c 的单跳延迟：初始桥 t=0 为 0.004430762292133393 s、t=30 为 0.0044284237027775305 s；热点直连分别为 0.0009002128960939169 / 0.0008119613681385577 s。固定环边 t=0 为约 0.00396651–0.00396663 s。热点经初始桥的 19 跳最短传播路径 t=0 共 0.07582903736974946 s。传播按 D2 服务段发起时刻采样，不能用 catalog 中旧 `distance_km` 列替代实时距离。

H=6 s 能覆盖这两个候选的 1 s setup 和上述无排队传播，但不保证覆盖拥塞排空、任意 BBM 等待或全 catalog 的短窗口。1 s 决策会与 setup 完成时刻重合，必须沿用冻结微步顺序处理后再观察。短暂突发持续 2 s，只比空闲 setup 多 1 s，适合检查过度持久预测的代价；它并不能演示突发前的预知控制。T−T_A=10 s 大于该静态传播/setup 时间，仍不保证所有积压排空。正常到 T 与全部交付分别报告。

结论：保留用户提供的 30/20/6/1/0.5/0.5/0.5；对指定 OD 的机械时间尺度有条件适用，不自动修改。若后续实际验证发现 setup/窗口/排空不满足，先报告并停在相应阻塞点，不能暗调 T、H 或 burst 持续时间。600 s 是该 catalog 的观测边界，与母 TLE manifest 的 86400 s 传播输入范围不同，二者均不继承为科学 T。

## 严格因果预测定义

在 epoch t，先结算所有 t 时刻既有终端和传播事件，再读取当前 Q/I、路由、终端、预约和当前注入率。预测不得获得 scenario_id、突发开始/结束时刻、未来真实 traffic 段、未来控制动作或最终结果。实验管理器可保存完整真实 trace 及哈希用于配对；该对象和哈希不传给评分器。

- MPC-ZERO：保留 t 时刻全部 Q/I 和年龄历史；对 (t,t+h) 的外生新注入率设为 0。不是清空业务，也不是关闭在途到达。
- MPC-PERSIST：同样保留 Q/I；每个 commodity 对 (t,t+h) 使用 t 时刻可观测当前率的常值延拓。不得从真实 trace 读取下一边界，也不使用尚未观察到的 T_A 截止来修正预测。真实到 20 后观察率为 0，才反映到后续预测。

每个预测模式在同一 epoch 只生成一个不可变预测输入，全部候选共享同一对象内容与 SHA-256。不同模式可以不同预测；不要求不同控制器在已分化状态上预测相同输入。几何是已知物理模型，可以外推；这不授权外推真实业务。预测 clone 的外生输入只能是已观测历史前缀加该预测，不能保留真实未来 trace/边界/缓存/未来策略。精确评分还需只读扩展当前已承诺 setup/TX/传播日程及 cohort；原 N3 observation 不完备，这对应前次系统审计 G29。四臂物理输入相同，但不能隐瞒评分器所需的内部状态访问扩展。具体隔离缺口见 `MPC_INTERFACE_GAP_AUDIT.md`。

## 单位正确的预测代价与敏感性预指定

对于 action a，设 `J_h(a)=J(t+h)−J(t)`，`DeltaE_h(a)=E(t+h)−E(t)−320×5×h`：

`C_h(a) = J_h(a) + lambda_N × N_a(t+h) + lambda_E × DeltaE_h(a)`。

J_h 单位 bit·s，N 为 Q+I、单位 bit，lambda_N 单位 s；DeltaE_h 单位 J，lambda_E 单位 bit·s/J。三项同为 bit·s。默认草案 lambda_N=6 s、lambda_E=1000 bit·s/J。前者是残余量的工程尾项时间尺度，后者是公开任意工程折算系数，均非正式 tau_res/alpha，未经优化，不设交付率硬掩码。固定待比较情景和输入后按代价、HOLD 优先的精确平分规则、N2 action_key 字典序确定选择；不增加隐含收益阈值。

预指定单因素敏感性：lambda_N∈{0,3,6,12} s，在 lambda_E=1000 下；lambda_E∈{0,100,1000,10000} bit·s/J，在 lambda_N=6 下。只对 C-SHORT 与 C-SUSTAIN、两个 MPC 模式执行，基础点复用；不做笛卡尔积搜索，不据结果挑选最优系数替代主草案。6 个主场景×4 臂=24 次，敏感性额外 24 次，合计最多 48 次确定性短运行，均需后续授权且以评分器工程通过为前置。

验算而非预实验结果：全 IDLE、T=30 时 E=48,000 J，DeltaE=0，320 终端驻留总和=9600 terminal·s。一个已有 ACTIVE 双端桥维持 30 s 为 E=50,400 J，DeltaE=2400 J，不添加虚构初始 setup。空闲双端在预测窗口 h=6 的 t 发起 ADD、t+1 ACTIVE 且保持到 t+6，DeltaE_h=2×35×1+2×40×5=470 J，E_h=10,070 J。能耗代价为 470,000 bit·s；若末端残余增加 100,000 bit，残余代价为 600,000 bit·s。这些数值只是公式手算，不是评分器测量或 MPC 优越性证据。

## 执行状态

新 dynamic_k_v1 精确反事实评分器尚缺。本草案的可执行性为 `CONDITIONALLY_DESIGNED / NOT_IMPLEMENTED`。先审核四份文档，再另行授权最小独立评分接缝及验收；本轮在文档阶段 STOP，不运行主场景或敏感性。
