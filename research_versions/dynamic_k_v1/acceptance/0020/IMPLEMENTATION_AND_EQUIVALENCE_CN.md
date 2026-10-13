# 最小差异与精确等价证明

新增独立SweepDeliveredAgeLedger，冻结n1b_fifo.py保持原字节。MINIMAL_INTERVAL_DIFF.patch只把原`for lo,hi`及parts列表推导替换为`for lo,hi,parts in self._coverage(incoming,cuts)`。prepare_seam.py从绑定源码静态生成该方法，恢复替换语句后AST逐字段相同。业务调度、flight-key遍历、cut排序、混合、Cohort消费、原始时间矩、传播位移、roundoff和_check_state不改变。

原cuts含窗口起终点及每个incoming端点，因此相邻lo、hi之间无任何片段端点。正长度片段覆盖该段，当且仅当start<=lo且end>=hi。按端点维护活动集合，在lo先删end==lo、后加start==lo得到完全相同集合。整数位编号为原incoming序号；取最低置位递增枚举，重复对象/相同端点的不同ordinal仍独立，顺序完全相同。每条有效片段调用同一个原Stream.clip，输出精确Fraction值相同；不预先clip或合并片段。

保持原incoming和cuts不变是接缝前提，原业务代码满足。正区间无法被零长度流片覆盖，索引排除零长度；直接检索测试也覆盖此边界。没有跨节点缓存、不移动观察游标、不改变Closure处理，不把在途业务当成重新注入。其他继承方法与类完全来自原模块。from_ledger只深复制原vars，所有队列、flight列表和审计独立。

29项初始专项包括16个parts排列/逆序检索、8个完整_interval账本/clone检查、2种Closure、2组真实D2服务序列及1bit负向；全部通过。覆盖不重叠、完全重叠、嵌套、同端点、10^-30秒精确差、零长度、部分重叠；160节点多commodity、多跳、部分服务、动态断连及恢复、setup、传播尾流、逐时刻完整vars、canonical state、metrics、审计、clone和确定性重放。1bit交付损失被原1e-6 bit BUSINESS_CONSERVATION_MISMATCH拒绝。

多个incoming同本地时间的parts保持原顺序；其后比例混合和canonical_components原样复用。专项单元部分手工账本是检索fixture，不冒称实际仿真注入轨迹；真实服务语义另外由D2积分用例、原N1b合流/本地FIFO测试和N2/N3/P0回归核对。

真实160星根因果hash精确匹配0015独立根，PERSIST输入因果隔离和N2 BBM合法性照常验证。原/扫线3→3.125秒回执、N1a/N1b/N2结果、全部账本字段、现有canonical+vars业务hash及causal hash相同。包含外层Python类名或源码绑定的native完整图哈希不能相同，CORRECTNESS.json明确记录这个代码来源边界；没有改原哈希算法或替换旧锚来制造等价。

源码和代码绑定分别保存SOURCE_PROVENANCE.json；既有哈希值比较没有更改容差。计数用于独立MeasuredSweep类的静态方法闭包，不进入账本vars或改变生产全局。真实轻量观察是同一真实记录前缀的独立账本重放，未再次推进网络；仅用于成本和对象计数，不用它冒充包含全部评价器附加roundoff记录的最终分支状态。

没有优化flight-key、_order、total、metrics或审计copy。整数位集不是常数成本：Python大整数操作的时间/内存随最高ordinal位宽增长，因此不声称全算法O(m log m+p)或消除密集p规模。索引端点引用2m、每段parts最大活跃k、原clip产生p个Stream；这些是覆盖接缝内对象规模，不是所有Fraction临时对象或完整BBM cohort峰值。
