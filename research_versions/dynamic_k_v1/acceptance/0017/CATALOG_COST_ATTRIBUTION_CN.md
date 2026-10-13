# 完整候选枚举成本归因

本轮只重读0016前缀并核算，没有调用CandidateSource或物理验证器。完整catalog仍未通过300秒验收，完整合法集合数量保持null。

## 实测前缀

2742为已登记目录行数，t=3的160星当前窗口1996，完成合法性检查2598次，合法前缀2566个。HOLD 1/1、ADD 1996/1965、DROP 1/1、REPLACE 600/599（完成/合法）。拒绝ADD_WOULD_IMPLICITLY_RELEASE31、DUPLICATE_LINK1；被中断调用没有记录结果。前缀包含599个成功BBM，没有已完成MBB检查，不能推断MBB不存在。

逐行已有wall_s之和298.021819s，目录硬停止墙钟300.0830555s。成功ADD1965次总225.0650167s、中位0.1120928s；成功BBM599次总72.8737779s、中位0.1167791s；31次ADD隐式释放拒绝合计0.0017327s，DROP一次0.0236091s，重复链路拒绝0.0576544s。没有用这些数值外推未访问REPLACE或整个epoch的时间。

第2500次完整快照：墙钟288.544831s；physical_window_bilateral独占192.1205672s、LOS_FOR独占2.7652716s、SGP4_native独占0.8373567s、binding_and_root_physical0.1124807s、catalog_window_lookup0.0030412s。physical_window_bilateral调用2467次，LOS_FOR和SGP4各4933次。计时包装扣除了嵌套LOS/SGP4，所以192秒**不等于192秒SGP4**。剩余约92.706秒包含N2试事务、快照日志、不在分类栈内的工作、序列化等，尚未逐项测量。最后98次检查的阶段没有完整结算，禁止补填。

## 重复工作调用链

CandidateSource.generate先取全部窗口，对每窗构造ADD并调用implicit_releases扫描L条旧连接；无冲突时为每条旧连接生成BBM/MBB，否则生成最小冲突集BBM；随后按种类去重、action_key排序、逐个validate，最后才做显式预算保留。最坏提案规模O(WL+W+L)，implicit扫描O(WL)，去重/排序至少O(P log P)，每次资源验证还扫描旧连接。多K时这是窗口与旧连接的组合增长；当前实现也不是任意释放子集的穷举，覆盖定义是最小冲突集合或单条旧连接加空闲双端。

前缀已有1996个不同有向终端对，其中600个检查两次、1396个一次。这是可证的重复终端对，**不是600个一定可复用完整物理判决**：mode、release_after、root资源和setup均可能不同，31个ADD甚至在物理层之前拒绝。

成功ADD/REPLACE典型路径：

1. ActionValidator检查引用/预约/隐式释放/模式，保持首个拒绝原因顺序。
2. N2PhysicalLayer先SGP4当前时刻LOS/FoR → Gate C.evaluate。
3. TerminalPairPhysicalFeasibility查current_window，可选hardware.check，再调用catalog.connect_command再次查current_window。
4. [connect_command](D:/Document/leo_routing_attitude/dynamic_lisl_v2/src/dynamic_lisl/terminal_pair_intervals.py:200)递归deepcopy(executor)，包含历史日志中的320终端快照；trial.submit又作一次structural transaction clone，执行真实_connect/事件/不变量，从RESERVE_BOTH日志读predicted_ready。
5. N2再在真实ready_time做SGP4 LOS/FoR。
6. ActionValidator另作executor.clone_for_transaction；trial.submit再次clone，执行声明的Disconnect+Connect或MBB命令，核对真实释放集合。

因此典型成功建链存在一次递归执行器复制及三次结构事务复制，是调用链推导，不是已测call counter。Gate C trial与N2 trial目的不同：前者建立command/ready与窗口判定，后者验证明确释放集合；不能直接去掉后者。目录枚举没有调用AtomicTopologyController.submit的现场前后snapshot；现场提交的snapshot相等性和实际释放核验属于评分/执行，不能错误归因到每条枚举。

TerminalExecutor._log每条新日志遍历排序全部320终端并asdict，形成全状态记录；recursive deepcopy又复制历史记录。clone_for_transaction已是冻结实现中的结构复制，保留独立log列表、约定不可改的旧记录和全部受审计字段。snapshot本身也排序/asdict，但本轮没有它们的分项次数/耗时。当前hardware是否回调应由初始化绑定决定，不能把所有Gate C检查默认当作有非空hardware；真实fixture使用的简化层不应被通用PhysicalFeasibility路径混淆。

## 可以设计的复用与禁区

优先设计独立版本的Gate C预演复制接缝：将connect_command中递归deepcopy换为已有clone_for_transaction，其余代码、事件顺序、旧日志及ready查找保持。这需要日志只追加和clone审计字段证明，不能直接改冻结文件，也不减少N2最终真实提交核验。

同一不可变epoch根，可按完整window、时间float.hex、双端、setup、orientation、release_after、硬件/代码绑定及资源摘要复用Gate C command/geometry纯计算结果；仍按原顺序执行动态资源与释放引用检查。cached结果必须防别名写入，不共享可变trial。资源摘要须覆盖320终端全部字段、links及tx_end/release_owner、reservations、agenda、序号、固定口和历史绑定；不能只用K或双端ID。状态变化、checkpoint恢复及依赖变化使缓存失效，未登记字段直接拒绝。

原SGP4Model.state调用native Satrec对象，不应仅凭函数名断言无可观察副作用。0015完整根审计包括native公开字段；缓存跳过state调用可能改变其最后调用状态。纯几何复用要证明这一点，或保留原state调用仅缓存从同一向量算出的LOS/FoR。当前SGP4耗时占比本就很小，优先级低。任意hardware回调可能读取executor或有副作用，未证明纯性前禁止缓存。窗口缓存必须保留半开区间、right_censored及数值epsilon，ready由TX/预约决定，不能用固定1s公式代替预演。

结论：Gate C窗口/双端预演阶段为实测主要类别，历史深拷贝与320终端日志重建是明确重复工作；各子项独占比例仍未测。保持完整枚举的优化和改变候选算法是两种不同方案，均尚未实施。
