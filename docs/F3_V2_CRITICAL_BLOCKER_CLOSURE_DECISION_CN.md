# F3-v2 Critical Blocker Closure 集中决策报告

审查日期：2026-10-09；决策节点：2026-10-11。性质：**ENGINEERING / STRUCTURAL REVIEW，NOT FROZEN**。本轮根据现有集中审批包完成隔离政策审计、注册fixture结构验收、组件成本检查和当前版本正确性复核。不修改历史审批包、F3-v1、Gate B/C/D或K0合同，不执行正式P1/P2，也不选择K*。

## 结论

截至本轮，正式科学冻结及42项正式运行的决定为 **NO-GO**。这不是认定研究方向无效：自然四个预声明点已经发现合法size2/3/4联合动作；但候选政策v1在原合法witness上有可证明的raw阶段遗漏，完整K0及最终运行预算也未闭合。不能用某个自然点成功、serial/8-worker局部一致或历史回归PASS代替这些门槛。

|阻塞项|本轮已经完成|仍然阻塞的内容|
|---|---|---|
|CP_POOL|完整规范、canonical顺序、真实B/C验证、逐阶段覆盖、seed/beam去重和预算审计；保留失败witness|raw阶段terminal-footprint覆盖不足；本版HF_SEARCH最终冻结NO-GO|
|CP_SOURCE_COST|原政策隔离probe的source、嵌套B/C、joint proposer、真实serial/8-worker rollout计时及完整证据|最终获批政策、K*、业务阶段、负载、router、完整episode及RSS费用UNKNOWN；不能批准42项总运行时间|
|CP_K|完整原规则的等价优化可行性分析、局部证书覆盖说明|完整两replay K0 ledger未执行；K*=UNKNOWN；索引/预计算overlay未实现验收|

研究范围A由本轮用户明确锁定：固定名义K，主周期5 s，每epoch最多4条资源独立REPLACE，B3/B4共享候选池，J为唯一主要目标；不开发ADD/DROP、可变K、MARL。其他尚未批准的草案参数仍是建议，不因本报告存在而自动冻结。

## 1. 搜索政策的完整规范与覆盖检查

详细规范见 [CP_POOL政策审计](F3_V2_CP_POOL_POLICY_AUDIT_CN.md)，对应独立probe为 `src/dynamic_lisl/f3_v2/search_policy_probe.py`。注册生产入口未导入它；旧source/proposer保留。本政策不是保持旧候选集合的runtime优化，未来采用必须登记独立科学revision。

规范现已明确old轮转、窗口顺序、offset、空域、exact-noop/同轨拒绝、source256访问与真实物理调用边界、raw32/32、singleton8+8、继续剩余桶回填、共享footprint cover、seed4 anchors/每size最多4项、seed与原beam共享184预算及tuple去重、最终pool顺序和原身份/hash公式。原审批草案对seed输出保留和回填衔接不够唯一，本轮probe解释为“safe seeds并入原top-W safe beam”“继续同一bucket/cover”；这些解释必须随新版完整规范人工审阅。

raw层只做old round-robin，没有footprint覆盖。singleton层才试图做贪心footprint覆盖；其输入已经丢失的端口不能补回。

|预声明fixture|scout访问|raw数量；raw old覆盖|singleton old覆盖|最终size2/3/4数量|判定|
|---|---:|---|---:|---|---|
|原20-node合法witness|144，全域|32；4/4|4|4 / 0 / 0|FAIL：已访问identity在raw截断丢失|
|自然K4/t0|256|41；4/4|4|4 / 4 / 4|发现合法组合；原指定witness本身未被scout覆盖|
|自然K24/t0|256|43；21/24|11|4 / 4 / 4|发现合法组合，域外UNKNOWN|
|自然K48/t270|256|37；29/48|10|4 / 4 / 4|发现合法组合，域外UNKNOWN|
|自然K80/t570|256|34；29/80|11|4 / 4 / 4|发现合法组合，域外UNKNOWN|

自然K>4的root是既有局部certificate的独立预建立fixture，重新经过当前原Gate C验证；不是正式K1或继承t0后的连续拓扑。所有fixture在执行前声明，没有根据J换点。

四个自然结构snapshot均以各自fixture起点作为schedule origin，首decision index=0。它们不等于连续F3 episode在t270/index54、t570/index114的候选覆盖验收。真实网络prefix使用t0/index0、t5/index1；完整rotation/阶段覆盖仍待最终政策验收。

已知witness的所有144个identity被scout并物理验证，但raw只保留C0/C1两种新链C端口。每个目标链必须占用一个C端，因此raw域内资源独立batch的上界是2；size2已找到，size3/4不可能由该raw恢复。原size4 witness仍合法。新端口总数从scouted的12降到raw的8，再降到singleton的6。原four-old覆盖完整并不能证明联合动作覆盖完整。

遗漏分类必须分别报告：

- **物理不存在**：仅能由完整域证明或可核验的上界证书认定；本轮没有据此否定自然全域。
- **scout未覆盖**：identity没有进入256访问域，例如自然K4原witness；状态UNKNOWN，不等于非法。
- **raw截断遗漏**：原144域witness的C2/C3动作属于这一类；本轮已定位。
- **singleton/seed/beam遗漏**：只有进入前一层但未被后一层保留/验证才能这样归因；不能把raw遗漏统称beam问题。

自然成功不能抵消注册witness失败；本轮没有增加visits、W、K或改fixture来取得PASS。

## 2. 成本边界与测量解释

raw64是输出上限。source最多256次单项物理验证，proposer还有最多64次物理screen及184次joint validation；joint最多4成员，内部还有Gate C建链trial、Gate B transaction、事件profile及hash。B4最多33个真实rollout和实际commit还会增加工作量。不能将raw64当作64次计算量上限，也不能把184称为CPU操作次数上限。

source wall、joint proposer wall、serial observe wall及8-worker observe wall分开测量。B/C wall和whole-transition safety wall是嵌套计时，已经包含在source/proposer内，不相加。worker累积CPU也不能当作parent wall。第一个结构attempt曾与rollout重叠，保留其证据，但不用于独立资源准入；随后同一五fixture顺序复测。自然t0 serial受初始重叠影响；t5在本任务没有其他并行测试/成本作业时复核。外部机器竞争没有被控制，不能称为实验室性能上界。

计时字段`*_Gate_B_C_calls`记录的是BatchPhysicalValidator.evaluate入口次数，包含资源层就拒绝的调用；`joint_safety_calls`记录BatchSafetyValidator入口。底层Gate C.evaluate/connect_command/TerminalExecutor.submit次数没有单独打点，仍为UNKNOWN。不能用adapter入口数冒充底层执行次数。

自然t0实际pool为29项：HOLD、16 singleton、各4个size2/3/4。serial observe约788.54 s，8-worker约150.96 s；约5.22倍是受竞争影响的参考比值，不能直接冻结为正式吞吐。cost文件不比较不同controller的J，只用于等价及工作量测量。

一次t0 serial分支证据已约1.16 GB；这提醒我们必须预算evidence I/O、存储和parent/worker内存，不能只预算observe调用。短prefix的峰值RSS和完整episode证据量仍为UNKNOWN。1800 s前缀资源检查在完成epoch后才判断，是cooperative检查，不是硬墙钟上限；即使两个epoch都exact一致，也不代表满足1800 s预算。

最终独立计时、当前回归及自然state-chain结果见末尾“本轮封存结果”和attempt内machine-readable报告。

## 3. K0：证书范围与保持原结果的优化

详细分析见 [CP_K等价优化审计](F3_V2_CP_K_EQUIVALENT_OPTIMIZATION_AUDIT_CN.md)。本轮不更改原12个K、20个时刻、matching/lex排序、18/20门槛或min admissible K规则。

|对象|已证实范围|尚未证实范围|
|---|---|---|
|exact matching|三个自然时刻的完整idle inventory；均得到terminal-degree relaxation最大cardinality136；tiny exhaustive oracle及canonical tie检查|其余17个时刻；完整两replay ledger；matching≥K不证明同星对约束或Z_K可行|
|lex topology builder|t0/K24、t270/K48、t570/K80的解析界证书及独立验证，保持全部lex优先级|其余237个K/time cell；这三个点的bounded exhaustive reference仍是UNKNOWN，未被改判EXACT|
|uncapped REPLACE及admissibility|已有局部诊断资产可以复用为工程参考|完整480点结构记录、原门槛与K*选择尚未执行|

三个matching图都只有272个incident terminals；136条合法且端口不重复的witness恰好达到floor(272/2)=136，本轮据此独立闭合最大基数上界。canonical tie继续由原exact整数权重solver及回归支持，不声称自然大图另有exhaustive tie证书。这个relaxation仍允许同卫星对多terminal边，不能当作受全部Z_K约束的拓扑证书。

136上界严格排除这三个时刻的K160 setup-qualified topology，但这只是数学推论，不是已执行的正式双replay cell；原12K全部保留，不删除不可行记录。其他K<=136仍不能由matching上界反推Z_K可行。

优先优化同一replay内的idle inventory及matching：K不进入这两个计算，同一时刻完整输入不变时可精确复用，调用量480→40。两replay仍分别建立cache、实际生成和验证。key须包含exact time、ID/plane、idle canonical state、window/hardware/code hash及setup/orientation；不能只按时间或文件存在匹配。

主要成本仍是各Z_K上的uncapped REPLACE。全部cell都可构造时，条件工作量为55,077,664次物理验证；这是条件计数，不是已经执行的数量，也不是运行时间预测。runtime256上限不适用于K0。只读window/owner/reservation/satellite-pair索引值得优先证明，但必须保留原reject优先级、reason、canonical顺序和完整B/C验证。

全cell可构造的条件已在上述三个K160 cell上不满足，因此该计数仅是代数工作量包络，不是本次数据实际运行费用。正式K0必须保留每个不可行cell及完整证据，不能删除它们，也不能直接从本轮推论生成完整K0 PASS。

new pair/t/setup相同不足以缓存完整Gate C返回：old release、TX/drain、visibility、terminal free-time、reservation/version及future events都可能不同。不能以几何相同跳过真实transition。原解析证书找不到解时仍需原exact reference或保留UNKNOWN；禁止用bounded incumbent替代完整certificate。

## 4. 六组审批建议

|组|明确建议值/内容|批准条件|
|---|---|---|
|HF_SCIENCE|按A：160星、fixed nominal K、5 s、最多4 REPLACE、共同pool、J唯一主目标；建议STRICT_CONNECTED、B3 whole-graph snapshot×min eta；B4 H10/current-rate persistence、H_eff=min(10,600−t)|明确forecast不读realized future，B3为proxy；最终pool正确性及公平性验收。固定“名义K”不等于恒定active K，自然expiry和MBB暂增链必须写清|
|HF_K|建议原12K、0:30:570、20点、18/20、occupancy .15–.5、min admissible K、600 s截断寿命和RIGHT_CENSORED标记|人工批准独立pre-established snapshot+forward Gate C证书的初始化；优化exact验收；完整两replay K0/K1。**不建议任何数值K***|
|HF_B2|建议实际LINK_UP计龄、初始age0、H4/H8秒、threshold0；只做最小minimum-hold|秒不是epoch数；5 s cadence下按真实LINK_UP age筛选，最终共享pool的回归通过；不按结果挑最佳H|
|HF_MATRIX|建议保留现有42个ID、顺序、科学作用和B4−B3同权限主比较；不新增/删除|最终政策、K*、topology/traffic/router/config hash、逐run成本与正式manifest绑定；另行人工运行授权；删失不按截断J排名|
|HF_RESOURCE|建议单episode、persistent8 workers；96净小时仅为资源提案，当前预算准入NO-GO|最终场景峰值RSS、阶段费用、完整episode开销实测；保守总费用≤已确认资源；不存在孤儿worker或超额并发|
|HF_SEARCH|**本版NO-GO，不建议最终冻结**；现有probe保留256/64/16/W4/184/33作为被检验输入|先提交raw-footprint覆盖revision，保留原失败fixture、相同自然点、预算和J盲选；结构/成本/current regression全部重新验收|

18/21=85.714%→18/20=90%，提高4.286个百分点；建议按原v1.1草案18/20审批，不偷偷保留旧分母或改分子。K4继续是VERY_SPARSE_HISTORICAL_REFERENCE，不进入primary K*选择。

## 5. 10月11日Go/No-Go与唯一下一步

|决定|当前Go/No-Go|唯一下一步|预计计算成本|
|---|---|---|---|
|A研究范围|GO，用户已锁定|把名义K/expiry/MBB边界写入待冻结科学合同|静态修订，无性能运行|
|CP_POOL / HF_SEARCH|NO-GO|独立raw阶段footprint覆盖revision草案，固定预算，复验同一注册失败及自然fixture|新revision为UNKNOWN；本轮实际测量仅供排资源|
|CP_SOURCE_COST / HF_RESOURCE|NO-GO预算准入|获批政策与K*确定后，完成预声明阶段/负载/router的组件、RSS及episode费用测量|UNKNOWN，不用K4初始点代替|
|CP_K / 数值K*|NO-GO|独立idle/matching预计算及有序resource索引overlay，先做reference exact对照与成本测量|overlay和完整K0耗时UNKNOWN；原三点idle inventory48–59 s、matching0.46–0.71 s只是局部参考|
|正式科学冻结与42项运行|NO-GO|上述门槛齐全后集中审批、绑定完整manifest并另行授权运行|UNKNOWN；当前不能承诺10/31完成|

如果10/11仍无合格搜索政策、K0可执行成本或资源准入，立即记录critical-path blocker。预计延期天数UNKNOWN。优先补足核心对比和正确性；工期、资源或非核心范围缩减只能集中提交人工决定，不自动删除42项中的任何run，不放宽正确性或漏报失败。

## 6. 42项保守运行预算

矩阵保持CORE12、STABLE4、SPARSE8、FACTORIAL6、HOLD6、ROUTER6。controller数量为B4=13、B3=13、B1=5、B0=5、B2=6。最大600 s内的决策机会按原2 s/5 s分别计算，不假设提前drain，不在600 s新决策：

|controller|最大决策机会|
|---|---:|
|B4|1920|
|B3|1920|
|B1|600|
|B0|600|
|B2|720|
|合计|5760|

需要候选生成的机会为5160；B0没有主动搜索。每run的保守模型为“初始化 + 最大epoch数×经过代表性阶段验证的保守总epoch成本 + 实际service/evidence/shutdown开销”。嵌套B/C不重复计入；worker累计CPU不当wall。late drain、load-aware router、rho .8/1、最终K*均未测齐，**总42项wall预算=UNKNOWN**；machine-readable预算为每个run保留estimated null及UNKNOWN标志。

6天×20 h×0.8=96净小时是资源提案，其中B4 72 h、其他24 h。除去所有额外开销前，分配上限仅为B4 135 s/epoch、其他22.5 s/epoch；它们不是实测预计耗时。自然t0仅8-worker rollout已经约151 s，提示明显预算风险，但不能把这一点线性外推为最终K*/全部业务阶段的费用或下界。证据写入、候选和service开销还需另算。禁止声称成本已闭合或月底完成已获得保证。

## 7. 正确性、历史保护与STOP

当前源码必须对应本轮新focused/full CLI结果；旧194/523和旧serial/8 seal保留为历史，不当本轮PASS。原合法witness的结构断言保留，不能改测试期望、删fixture或放宽容差来使整个suite绿灯。区分候选政策结构验收失败与routing/service/Q/I/D执行不一致；两者都如实保存，不用分类说明覆盖真实退出码。

保护检查对原3164文件baseline及其已授权四份计划revision链核验，并对本轮初始源码hash与最终源码hash比较。新probe/工具/测试位于v2隔离目录；所有正式资产保持原样。首轮7-test FAIL及初始竞争计时attempt均保留。最终code hash、测试stdout/stderr、真实returncode、自然完整分支状态、组件成本、证书覆盖和artifact SHA256随新attempt封存。

本轮不冻结科学合同、不接入新source到production、不执行完整自然K0、不选择K*、不运行registered P1/P2/RL，不宣称完整工程PASS或正式科学实验完成。报告完成后停止在人工科学冻结及正式运行授权边界。

## 8. 本轮封存结果

|fixture|source wall s|source validator entries|source nested B/C s|joint proposer wall s|proposer validator entries|proposer nested B/C s|joint safety entries|
|---|---:|---:|---:|---:|---:|---:|---:|
|KNOWN_20_NODE_WITNESS|1.238|144|1.228|0.884|57|0.563|25|
|NATURAL_K4_T0|19.155|256|19.059|22.926|106|13.143|65|
|NATURAL_K24_T0|16.199|255|16.118|75.268|209|39.926|166|
|NATURAL_K48_T270|13.627|255|13.541|58.851|173|30.857|136|
|NATURAL_K80_T570|9.962|255|9.868|68.955|180|34.805|146|

|natural epoch|pool branches|serial observe s|8-worker observe s|reference speedup|
|---|---:|---:|---:|---:|
|t=0|29|788.539|150.965|5.223x|
|t=5|27|895.703|194.355|4.609x|

t0 serial 受竞争影响；t5 无本任务另一计算作业并行。自然两epoch的所有分支元数据、决定、四类checkpoint及到10s的状态链精确一致，no orphan PASS。整个前缀wall=2378.118s，超过1800s cooperative资源检查值；此不能当作资源准入PASS。

|current CLI suite|tests|passed|failed|returncode|wall s|
|---|---:|---:|---:|---:|---:|
|focused|203|202|1|1|121.639|
|full|532|531|1|1|196.224|

两套都只有同一known-witness结构覆盖断言失败，其他行为测试未新增失败。整体regression=FAIL，不改判PASS。原合法witness的size2/3/4均已用当前validator单独重验合法，进一步确认是候选收集遗漏。

历史完整性PASS：3164文件baseline与已授权的四份计划revision链核验通过，本轮受保护文件变更为0。当前源码与新测试hash完全对应。

- [Machine-readable decision](../outputs/f3_v2_blocker_closure_20261009T020009_842972Z/decision_report.json)
- [Component costs](../outputs/f3_v2_blocker_closure_20261009T020009_842972Z/component_cost_report.json)
- [42-run conservative budget](../outputs/f3_v2_blocker_closure_20261009T020009_842972Z/runtime_budget_conservative.json)
- [Oct11 Go/No-Go](../outputs/f3_v2_blocker_closure_20261009T020009_842972Z/go_no_go_20261011.json)

**STOP: formal scientific freeze / registered run authorization boundary.**
