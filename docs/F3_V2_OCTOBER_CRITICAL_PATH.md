# F3-v2：2026年10月31日非MARL论文实验完整交付计划

状态：**DRAFT_NOT_FROZEN / PLAN_READY_FOR_CONSOLIDATED_HUMAN_REVIEW**。修订日期：2026-10-09，Asia/Shanghai。本轮只读取已有证据并更新四份计划，不运行算法、benchmark或正式实验；未授权冻结合同或正式运行。历史F3-v1/K0/FAIL/旧8-worker证据全部保留。

## 目标、当前进度与关键路径

10月31日前争取完成全部获批预注册的非MARL论文实验、数据检查和主要图表。12月中下旬投稿；11月安排解释、写作和审阅，不把第一轮主实验留到11月。正式规模为160星，不新增240/720实验。MARL/PPO、ADD/DROP、可变K、事件触发控制、自适应预测时域和大规模全局联合搜索均不进入本轮。

仓库已有隔离的JointAction/BatchPhysicalValidator、服务adapter、B1/B2/B3、joint B4、tiny oracle、evidence/preflight和图表接口。它们是可复用工程资产；K*尚未选择，正式K0/K1、最终共享候选政策与生产配置验收仍未完成。历史110项focused/439项全回归PASS后源码已有变化，当前验收不能沿用这些数字。旧v1 multiprocessing PASS，以及v2的K4/9分支/2s受限自然fixture PASS，均不等于最终K*/5s/完整pool验收。

**关键路径：集中合同审批 → 共享候选覆盖与计算上限 + batch物理安全 → 完整K0/K1 → B1/B3/B4-v2最终接入 → 当前tiny oracle/serial8/全回归 → 逐run实测预算 + 最终manifest/preflight → 单独正式运行授权 → 42项实验 → 验证/图表/封存。** 工程测试准备、evidence和绘图接口可与结构工作交错，不能绕过依赖或另造模拟器。

## 已经出现的阻塞：必须在10月11日前解决政策

1. **CP_POOL：真实候选池退化。** 160星K4/t0，7596个物理合法REPLACE经raw64截断及singleton16后，16项全部替换同一条old link，共享池无size2/3/4；同时存在原Gate B/C验过的安全四链MBB witness。仅把batch上限设为4不足以形成联合控制。需集中审批result-blind的old-binding/terminal-footprint覆盖规则及按size结构种子；所有B1/B3/B4共用，不据最终J调参。该发现只说明固定K4/t0，不能推广为所有K*/epoch。
2. **CP_SOURCE_COST：输出cap不约束筛选成本。** 相同自然场景7980次物理验证，source约455.081 s，proposer约7.683 s。runtime仍是全扫描再截断，raw64不能称为64次物理计算上限。需与覆盖政策一起批准有限scouting/physical-evaluation budget、canonical枚举及未扫描空间报告。K0的uncapped结构审计另行保留。当前不擅自改变候选宇宙。
3. **CP_K：结构前提未闭合。** 预声明三点t0/K24、t270/K48、t570/K80的inventory约48–59 s、exact matching约0.46–0.71 s；解析exact证书约0.016–0.020 s并有独立验证，bounded reference仍UNKNOWN。三点只证明局部求解路线，不代替原K列表×20 snapshots、正式K*或K1。
4. **CP_CURRENT_ACCEPTANCE / CP_EPISODE_BUDGET：最终自然配置与全矩阵费用待验。** 旧9分支自然B4的parallel observe约49–72 s/epoch，不能据此线性推算完整33分支或K*费用；physical clone局部等价通过也不能代替新B4全链验收。

上述原始report路径与SHA均录入runtime JSON。当前风险为**HIGH**，10月31日是目标，尚无可信全episode/全矩阵费用可保证日期。审批或验收延迟须立即报告受影响节点、预计延期范围/UNKNOWN、缺测项和可批准资源/非核心减项，不等最后一周。

## 里程碑与依赖

|截止|必须完成|准入/停止条件|
|---|---|---|
|10月11日|科学合同、K0/K1方案、覆盖与scouting政策、资源预算及集中审批包|局部实测和NOT_MEASURED分开；CP_POOL/CP_SOURCE_COST有明确获批路线|
|10月16日|获批完整K0/K1、共享batch executor及5s调度安全验收|整批双端原子性、BBM/MBB/mixed、TX draining、expiry、全时间线STRICT_CONNECTED；无合格K或UNKNOWN按合同停止|
|10月20日|同一pool的B1/B3/B4-v2核心、最小B2、正式evidence接口|真实joint rollout；B3 full-graph snapshot；无未来realization/不同权限对比|
|10月23日|新serial/8worker自然多epoch、tiny oracle、当前全回归、逐run预算、P1-v2 preflight|全state-chain exact、隔离/无孤儿进程、全部hash、最终42项manifest；任何失败不得启动|
|10月24–29日|单独人工授权后，按冻结次序执行全部42项|逐项COMPLETE/CENSORED；invariant failure先持久化再STOP；不静默重跑、不删失败|
|10月30–31日|原始证据校验、paired统计、图表/caption、11项交付封存|正式结果与engineering PASS分开；阴性/tied/censor均保留|

更细的12项任务、开始/截止/依赖/权限在deliverables JSON。10月9–11准备合同和独立工程fixtures；12–16先处理共享pool/结构与安全；17–20接入；21–23集中验收。若节点失约，重新用剩余任务与实测费用估算日期，不沿用旧从零人日预测。

## 最小完整实验矩阵：42项，维持原ID和执行次序

|块|研究配置|新增runs|
|---|---|---:|
|CORE|K*、热点迁移、primary、5s/batch4；ρ=.5/.8/1 × B0/B1/B3/B4|12|
|STABLE|K*、稳定业务、ρ=.8、primary、5s/batch4；四控制器|4|
|SPARSE|历史K4、热点、primary；B3/B4 ×三负载，ρ=.8另加B0/B1|8|
|FACTORIAL|K*、热点、ρ=.8；B3/B4 ×(2s,1)/(2s,4)/(5s,1)，(5s,4)复用CORE|6|
|HOLD|K*、热点、primary、5s/batch4；B2-H4/H8 ×三负载|6|
|ROUTER|K*、热点、5s/batch4；load-aware B3/B4 ×三负载，primary复用CORE|6|
|总计|B4=13、B3=13、B1=5、B0=5、B2=6|42|

每项run_id、状态、配置、科学作用、对照引用及预算字段已在matrix JSON，42项仍PLANNED_NOT_AUTHORIZED。K* artifact/hash、最终搜索政策和费用尚待填齐，不能作为可执行manifest。本轮不新增或删除run。

主比较是同配置B4-B3；B1决策忽略setup而真实执行仍走Gate B/C，B0不主动重构，B2只加逐链LINK_UP H4/H8最小hold。无额外算法功能。动作权限、共享pool构造、Gate B/C、router、traffic、scheduler、forecast source与决策时点相同；两算法真实状态分歧后pool可以不同，不能强迫相同实际候选。2s/5s是决策周期，不是将物理或arrival事件量化为时隙。

复用16 OD、D0 reference alpha*与统一ρ，arrival0–240s，真实drain最多600s，600不发起新decision。nominal H10，末端min(10,600−t)是待审批边界裁剪，非自适应预测。K固定指名义/初始预算，自然expiry照常发生；不ADD/DROP补链。K4保留VERY_SPARSE_HISTORICAL_REFERENCE，不能混用三链Z_SPARSE。两个K regime拟用相同STRICT_CONNECTED政策，须验证初态及全过程可行。

## 运行预算与准入

机器已有只读库存：Intel Core Ultra 9 275HX、24核/逻辑CPU、总RAM约31.43 GiB，conda pytorch。瞬时空闲RAM不能当长期保证。建议一个B4 episode、persistent8workers+parent；并行episode和线程上限需用实测RAM/争用与exact gate批准，不按24核自动启动三组。无需实时监控；只在获批测量/启动时采样。

建议Oct24–29每日至多20h可用，6天120h，20%余量，净96h；暂分B4 72h、其他24h。按600s全部决策机会计，B4最多1920 epoch、其他最多3840，零额外开销平均资源上限135s/B4和22.5s/其他epoch。B0本身不需要source/proposer；该上限是保守资源划拨，不是假定B0也搜索。每run的暂定资源额度与校准键列在runtime JSON；**实测预测和获批timeout仍为null**，必须扣除source/advance/冷启动/传输/I/O/shutdown后才判断准入。

455s的K4单点已经超过这些均值上限，是提前风险证据，不等于全episode均值。费用须在最终K*、scouting/pool政策下，用预声明阶段/状态实测source、整batch safety、真实rollout、serial/8worker、cold/warm池、推进与evidence，再给逐run保守范围。不得用9分支速度外推33分支，不据J挑K、业务或beam。source cap、joint cap和rollout cap分别计数；费用分解不得把worker累计CPU当wall或重复计算共享source。

Oct11提交局部成本与缺口；Oct16确认结构/安全费用；Oct20–22完成新B4与阶段费用；Oct23前42项预算、机器时段、RAM、超时全部填写并获批。未测代表阶段为UNKNOWN，不能假定提前drain。保守费用超过96h即立即提出资源/工期/非核心范围修订；未经审批不采用减项，不改tolerance或截短科学horizon。

## 工程验收、分析与主要图表

新增最终配置必须重验serial/8worker分支J_H、合法性/原因、Gate B events、terminal/reservation/version、G_active/G_admit、Q/I/D、objective/diagnostics、proposal ID/order/hash、action/tie和四checkpoint；自然跨epoch状态链exact、live隔离、确定性、clean shutdown。tiny oracle分别验证B3 snapshot与B4 rollout的合法集、best-in-pool及遗漏，不要求两目标选择相同，不宣称大规模全局最优。

每个正式run验证immutable traffic、work conservation、queue非负、capacity、batch资源/原子性、candidate budgets、decision边界、drain及报告一致性。内部1bit返回不是F3 .01bit排空；无clamp/drop/virtual drain。超时为execution failure，先完整写出invariant/failure/finalstate/metrics/timelines/audit/hash再STOP；CENSORED为合法科学结果，保留residual/delivery，禁止truncated-J ranking。

主目标仍network-wide unfinished-work J，无人为switch/setup penalty。双方COMPLETE才计算完整J差值；其余报告censor、backlog、delivery和completion time。42项是deterministic场景比较，不当独立随机样本生成p-value/CI，不生成global ranking。B4不优于B3仍可形成有效、完整结果。

固定ρ=.8 opening case及原run引用，画N/Q/I、REPLACE与Gate B markers、60/120/180/240s phase boundaries；其余是三负载核心对照、完整2×2cadence/batch、K/stable/B2/router、费用/候选覆盖、BBM/MBB与transition outage/post-expiry分拆。曲线重合不得换case。图表接口可提前用literal fixture检查，论文图必须引用全部正式run证据与seal。11项交付全部逐项验收，不以文件存在或engineering PASS替代。

## 一次性审批清单与可立即准备的工程任务

|组|集中审批内容|
|---|---|
|HF_SCIENCE|terminal-level joint REPLACE、whole-transition safety、5s/batch4、B1/B3/B4评分及H10/persistence/末端裁剪|
|HF_K|K0-v1.1 20点/18-of20/600右删失截断寿命、batch结构诊断、原候选K与选择规则、K1初始化/age0|
|HF_SEARCH|原raw32/32/64、singleton16/8+8、W4/M32/184/33提案；同时批准具体结构覆盖、有限scouting预算及遗漏报告，不能只批输出caps|
|HF_MATRIX|42项ID/配置/次序、三负载、stable、K4、2×2、B2-H4/H8、router、固定图case与censor分析|
|HF_RESOURCE|确认机器20h/day建议、一B4/8worker、RAM准入、成本fixture范围；最终实测预算集中补齐|
|HF_BUILD|确认现有工程复用与剩余实施/验收范围；不增加算法、星座或无关runtime重构|
|HF_RUN|前述冻结、验收、预算、manifest/hash及preflight齐全后，单独授权正式运行；本计划不授予此权限|

不依赖科学数值、可立即准备的工程工作：核对源码与seal版本、设计冲突/expiry/drain/checkpoint/tiny fixtures、复用evidence/ledger/censor接口、绘图/caption数据QA、成本字段和资源准入协议。实际运行这些工程任务仍遵守既有工程授权；此次只更新计划。候选覆盖/scouting、K*、生产评分与正式manifest必须等集中审批，不能为每个小参数反复中断。

若资源缺口无法解决，首先保全CORE12、同权限B4-B3、完整正确性及关键2×2消融；只可在任何性能结果前，申请减少非核心B2/router/sparse/stable覆盖并明确结论损失、替代manifest及延期。当前没有采用任何减项。若依赖/费用未知，完工日期写UNKNOWN，不保证10月31日。

本轮完成计划和静态一致性校验后停止。未冻结合同、未执行正式K0/K1/K*选择、未运行P1-v2/P2/RL。下一步为集中人工审批。
