# 精确FIFO成本归因

证据分级：M=0016直接测量/封存数据；D=绑定源码与记录的可核算推导；S=静态复杂度/成本机制；U=未测量或无法验证。本轮仅读取文件，不调用模拟器或重建根。

## 已确认的边界

M：PERSIST/BBM总评分1100.5151s，其中冻结评分器的advance_network_fifo_energy_including_binding_s为1099.380509s。其他已测段为clone 0.1383551s、显式绑定0.0971620s、N2提交0.5762523s、能耗/代价/证据0.1429439s。推进段包含网络、FIFO、能耗、绑定、测量及审计，不能称作FIFO独占1099秒。外部只读栈两次落在DeliveredAgeLedger._interval的incoming扫描，记录区间和节点持续变化，支持精确年龄处理是重要热点，不能证明唯一瓶颈或耗时占比。

M：final resident cohort_count=27，终端日志增量10，年龄观察记录增量479，最终closure_audit有10项、roundoff_audit有7595项。后者包括INTERVAL_END 7445、FINAL 116，另34项无boundary字段；按state分解I=3428、Q=3141、A=498、D=494、SERVICE=21、CLOSURE=10、REPORTED_DELIVERY=3。只记录非零差异，不能用7595反推全部状态检查次数。266个不同审计时间也不是事件总数。

D：0015完整t=3根有43条年龄观察（SCHEDULE22、INTERVAL21），初始closure_audit=0；图内318个LocalFIFO对象、20个Stream、0个Cohort。图中LocalFIFO包含空队列，不能称为318个有积压队列。成功评分路径在submit时t=3以及t=6、9调用advance_to三次，每次结束有一次settle/_microstep；每个正时间_step产生一条SCHEDULE和一条INTERVAL，每条CLOSURE被年龄账本消费并登记一次。因此：

`新增观察记录 = 2 × 正时间_step次数 + 3 × 终点settle + 新增CLOSURE`。

|PERSIST动作|观察增量(M)|closure增量(M)|正时间_step(D)|_microstep/SCHEDULE(D)|评分墙钟(M，s)|
|---|---:|---:|---:|---:|---:|
|HOLD|7|0|2|5|1.3340|
|ADD|363|18|171|174|21.4653|
|DROP|54|7|22|25|1.9553|
|BBM|479|10|233|236|1100.5151|
|MBB|383|18|181|184|33.7395|

推导依赖成功、无额外推进的冻结调用路径，完整前提写入STRUCTURAL_EVENT_COUNTS.json。它不是本轮新增运行计数器，传播agenda的单个heap pop、同一时间的复合事件数仍U。每分支age.consume=3、age.metrics=6也是调用链推导；consume使用cursor只处理新增观察，源码不支持“每次从零重复全部FIFO推进”的说法。

BBM的正时间_step为MBB的233/181≈1.287倍，墙钟约32.62倍。线性事件数量不能单独解释差异。BBM立即释放旧跨轨链路，MBB先保留旧路；连续有业务时，临时分区、恢复、多跳路径和队列排空切点可能放大流片段处理。该放大机制是S，未保存所有中间路由及片段表，不能将特定峰值或增长率当作M。

## 调用链与重复工作

冻结score_action → AtomicTopologyController.advance_to → DeliveredFluidEvaluator.advance_to → N1a网络/能耗推进 → age.consume → 按cursor消费SCHEDULE/INTERVAL/CLOSURE → _interval → _order / flight裁剪 / cuts / LocalFIFO.advance_piece → Cohort.consume → _check_state → 两次metrics。

在[n1b_fifo.py](D:/Document/leo_routing_attitude/dynamic_lisl_v2/research_versions/dynamic_k_v1/runtime/n1b_fifo.py:212)中，每个INTERVAL、每个commodity重新构建DAG顺序；每个节点遍历list(self.flight.items())，对匹配边逐Stream.clip并保留未消费前缀/后缀。incoming每个起止点进入cuts，随后每个相邻cut重新扫描全部incoming做Fraction包含判断和clip。设incoming数m、切分区间c，这段扫描O(mc)，c可达O(m)，存在二次工作；有效重叠输出本身也可能是二次数量，扫线不能承诺整体线性。

LocalFIFO.advance_piece会创建连续cohort、对wanted循环进行部分消费、重建canonical_components并创建输出Stream；total()在每次服务检查重扫当前队列，prefix_moment在consume中计算（返回moment未被当前调用者使用），_budget在同一INTERVAL内重复生成相同界限。_check_state重扫所有队列/在途及每个commodity的守恒量；metrics又扫描剩余年龄积分并deepcopy全部误差/closure审计记录。这些为S，其实际执行次数和独占秒数U。

2 commodity × 160节点 × 233新INTERVAL＝74560次节点迭代可由固定循环推导；不等于74560次队列更新，实际cuts及服务次数未知。队列排序、Cohort创建/拆分/consume累计次数、Stream创建及峰值、活动组分数和Fraction中间操作数位宽均未封存，保持null。已存22720个Fraction见证（最终精确量及差异账本）最大分子131bit、分母112bit，不能据此断定中间位宽没有增长，也不支持“已测得大整数爆炸”。

## profiler解释修正

0016的OBSERVER_PROFILE_TIMING_PAIR只测PERSIST/HOLD，不是BBM。其FIFO category以文件名加函数名consume/metrics分类，同时包括Cohort.consume、DeliveredAgeLedger.consume和metrics；391不是ledger消费了391次。按相同冻结路径可条件推导391−3−6＝382次Cohort.consume，仅属于该HOLD计时运行，不能套到BBM。4.6818509s也是HOLD仪器化的混合类别时间。

只读profiler墙钟27.043725s、对应非仪器化1.7483777s；7287604个全局线程回调带来明显开销。类别exclusive仅扣除被分类的嵌套调用，未分类子函数、分类判断及回调开销仍可计入所属段，不能当成无仪器化算子耗时。原证据的exact_result...false源于native tuple与持久JSON list比较，0016最终SMALL_DOMAIN_ACCEPTANCE已在同序列化层核对所有非timings输出和最终状态哈希一致，本轮不覆盖这些记录。

结论：精确FIFO片段遍历和有理数处理为有栈证据的热点；各算子占比、瞬态片段增长根因仍未完全归因。下一步应先获得最小精确扫线/索引设计及计数审计的授权，不能以删cohort、合并不同注入时刻、量化时间或放宽容差消除成本。
