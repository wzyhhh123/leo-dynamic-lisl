# CP_POOL：候选政策规范及结构遗漏审计

本文件是本轮隔离工程探测的完整解释，状态为 **ENGINEERING_ONLY / NOT_FROZEN**。政策名为 `RR_STRUCTURAL_SCOUT256_RAW64_SINGLE16_SEED4_V1`。注册生产入口仍使用旧source/proposer；本轮不接入生产，不修改旧审批包，也不依据最终J制定候选规则。

## 输入、身份与canonical order

只读取共同decision root、当前Gate C窗口、终端占用、原setup参数、plane mapping及共同schedule的非负整数epoch index。eligible old必须是真实ACTIVE binding，且没有draining或release_owner；排序键为规范化的双端terminal pair。old访问起点为epoch index模old数量，HOLD机会也计入该index。

当前窗口排序为 `(-end_s, abs(plane_i-plane_j), canonical_new_terminal_pair)`。不使用循环plane-gap，不改历史plane映射。每个old在未旋转的canonical列表的序号q对应起点 `floor(q*n_windows/n_old)`；第r轮访问该old的 `(offset_q+r) mod n_windows`。同一old最多走完一圈；没有old或没有窗口则空raw/HOLD。若当前同一terminal pair同时出现多个窗口，本probe明确拒绝，不能悄悄选一个。

成员ID仍为 `V2-RAW-`加canonical SHA256(time_s, old, new)，terminal pair规范化规则及JointAction身份/hash公式不变。这不代表新政策与旧政策产生相同成员集合或proposal hash；新集合属于需要单独科学审批的输入政策。

## source：访问、物理验证与raw输出

visits最多256，包含exact old==new、同轨目标这类静态拒绝；静态拒绝不调用物理validator。其余每个identity调用原BatchPhysicalValidator一次，记录accepted/reason、实际BBM/MBB及ready time。达到256或穷尽当前元数据域即停止，不按返回数量扩大预算。source物理调用最多256，不代表整次决策物理调用最多256。

accepted候选按实际MBB/BBM分组，每组最多32，总raw最多64。两组顺序MBB、BBM，各组按old分桶并round-robin；桶内排序 `(-usable_lifetime, plane_gap, old, new, id)`。**raw阶段没有terminal-footprint覆盖规则，也不跨组回填raw的32槽。** 因而old-binding覆盖不能保证新端口覆盖。输入域未被访问部分为UNKNOWN，不是不可行证明。

## singleton：8+8、回填与footprint覆盖

raw按member_id排序进行原物理screen，最多64次。MBB先取8、BBM再取8；共用贪心cover。对尚未进入cover的old，优先选footprint与已覆盖端口完全不相交的桶项；找不到时取桶首，但不把冲突项加入cover。已经进入cover的old依原排序取项。此规则不承诺覆盖全部old或全部端口。

槽不足时MBB再BBM回填到最多16，**继续同一剩余桶和同一cover，不重新从桶首重选**。最终按MBB后BBM及实际选择顺序赋canonical index。batch1使用完全相同的singleton来源，只禁止联合扩展。单项网络安全失败的物理合法项仍可作联合扩展前缀，不能用它证明组合失败。

## seed、beam、去重及预算

16个singleton先做整批安全验证。首四个不同old的canonical代表作为anchor；每个anchor按canonical index扫描，仅追加不同old、footprint不相交的成员，最多4项。每个prefix重排为递增index tuple；size4先于3先于2，同size按tuple排序，每size最多4个seed，合计最多12。

然后使用原W4 beam：初始按 `(-min_usable,-sum_usable,index_tuple)` 取四个singleton前缀；只追加更大index且footprint不相交的成员。原Gate B/C及whole-transition安全判定不变。可生成commands但网络安全失败的前缀仍可继续扩展。

singleton、seed和beam共用184次joint validation及184次计费expansion；同一index tuple在本次propose中只验证一次，命中计cache hit，不重复计预算。不跨root/时间/epoch保存结果。资源冲突是廉价排除记录，不消耗joint validation。**这不是CPU操作次数上限**：metadata排序、组合访问、资源检查、hash、每个joint最多四个Gate C成员验证及事件profile均另有成本。

原草案对seed保留和beam截断的衔接不够唯一；本轮独立probe明确采用“安全seed与每size原top-W安全beam结果取并集，按同一tuple去重”。这是供审阅的规范补足，尚未人工冻结。缺槽回填的上述解释也需随完整规范审批，不能只批准数字256。

## 最终pool与计数边界

安全singleton先保留；其余safe joint按size2/3/4轮取，同size按原lifetime/index键排序，直到最多M32个非HOLD。最终按(batch_size,index_tuple)排序，HOLD第一项。branch上限33，batch1上限17，实际pool可能更小。proposal集合hash仍含root、原identity document及新audit；所有controller必须消费同一pool，不能根据controller分叉筛选。

source<=256次单项物理验证；proposer screen<=64；joint<=184次batch物理/安全验证；最后B4最多33个真实rollout。即便前两层只算batch-validator入口，也可达504次，且joint含多个成员。raw64只是输出上限。Gate B/C wall嵌套在source/proposer wall中，报告时禁止叠加计费。

本轮计时文件中的`source_Gate_B_C_calls`、`proposer_Gate_B_C_calls`精确含义是 **BatchPhysicalValidator.evaluate入口次数**，包括在resource检查就返回的reject；`joint_safety_calls`是BatchSafetyValidator.evaluate入口次数。它们不是底层Gate C.evaluate/connect_command或TerminalExecutor.submit的实测次数。该层wall包含实际B/C trial及资源检查；未独立打点的底层次数仍为UNKNOWN，不能把入口数冒充底层调用数。

## 预声明fixture的结构结果与归因

本轮固定五个fixture：原20-node/144-identity四条合法MBB witness；自然K4/t0、K24/t0、K48/t270、K80/t570。后三个K>4使用既有局部certificate构造独立预建立root，仍按原Gate C复核，不是正式K1或连续topology演化。

原witness fixture全144项都被访问并物理验证，四个old都进入raw，但raw的新C端仅C0/C1。C端是每个新链的必占资源，所以raw域内任何资源独立batch大小至多2。C2/C3 witness已scout到却在raw截断丢失；后续singleton、seed或beam不能恢复它们。最终size2=4、size3=0、size4=0，而原四成员witness经当前validator仍合法。

上述四个自然结构snapshot均是独立fixture的首个决策，显式epoch index=0、schedule origin=该snapshot时间；不能冒充从绝对0开始连续5 s运行到270/570 s时的epoch54/114覆盖。真实网络prefix另行使用t0/index0、t5/index1，确实验证状态演化。各阶段未测试的rotation仍为UNKNOWN。

这是 **FULL_SCOUT_COVERAGE_RAW_TRUNCATION_OMISSION**；不是物理不存在，不是scout未覆盖，也不是仅增加beam能解决的问题。自然四点均找到size2/3/4，但它们不能抵消注册witness失败。自然K4原指定witness本身未被scout到，虽然发现了另一些合法同规模batch，必须同时保留“该identity未覆盖”和“存在已发现合法batch”两项事实。

因此HF_SEARCH本版最终冻结建议为 **NO-GO**。唯一下一步是提出独立的新政策revision，在固定raw/visit预算内明确定义raw阶段terminal-footprint覆盖，然后对同一失败fixture和同一自然fixture复验；不在本轮悄悄改变v1，也不按J调参数。该revision实际成本为UNKNOWN。自然短prefix的serial/8-worker精确等价只能证明被检验pool的执行一致，不能证明候选全集召回率或完整工程PASS。
