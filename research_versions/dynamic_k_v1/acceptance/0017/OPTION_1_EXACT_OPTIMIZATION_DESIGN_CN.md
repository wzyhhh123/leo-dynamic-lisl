# 方案1：保持完整合法候选枚举的精确优化设计

状态为DESIGN_ONLY，需要后续人工授权；本轮没有实施优化，也没有修改旧合同。目标仍是冻结CandidateSource定义下的完整候选/合法/拒绝集合、相同action_key排序和真实释放集合，而非任意联合释放子集全局搜索。

## 最小FIFO接缝

在独立版本新模块中提供显式选择的年龄实现变体，复用原业务/事件时钟、LocalFIFO服务、Cohort/Stream数据类型及所有守恒和误差判定。先只替换_interval的检索与切分扫描，不改变连续解析式。

- 按commodity和接收节点建立flight键索引，遍历顺序仍等于原self.flight的插入顺序；同一interval内新增下游流必须同步更新，不能使用失效的开头快照。未删除原字典键/空队列，保持原全状态布局。
- 采用精确Fraction端点扫线；仍使用全部原cuts，不量化时间。在lo先移除end==lo的流、再加入start==lo的流；按原incoming序号枚举活动流，对每个[lo,hi]调用原clip。端点集合包含所有Stream起止点，所以活动条件与原start<=lo且end>=hi严格相同。重复流保留不同序号，不删除、不合并不同注入时刻，不把同时到达混合变成任意FIFO。
- 保留每个区间的原parts顺序及原advance_piece、_deliver、_roundoff调用。原始注入时间仿射分布、服务时刻、队列追加、部分消费、在途偏移、审计记录逐项保持。目标成本从O(mc)扫描变成端点排序/更新O(m log m)+实际活动输出O(p)；若p本身二次增长，仍可能高成本，不能保证线性或降到几秒。
- _order只在完全相同的nodes/commodity/正服务边集合下复用，并返回独立的同序结构；_budget可在scale和cursor未变的interval内复用精确值。审计不能跳过；暂不改total、moment、components或metrics生成，避免扩大证明范围。

额外缓存和索引放在不参与业务账本的受控旁路，不能把计时/counter方法写入vars(age)。如果需要新的年龄类型或工厂，应登记明确的实现身份；完整checkpoint中的类型差异属于版本身份差异，不能伪称旧typed object graph相同。业务字段、Fraction分布、规范状态哈希、原始误差记录及最终评分必须精确相同，允许差异只能是预先声明的版本身份和真实计时。

## 最小Gate C接缝

优先建立独立catalog适配变体，仅将connect_command内部deepcopy(executor)替换为已有executor.clone_for_transaction，继续原trial.submit、predicted_ready日志提取、窗口/epsilon/删失规则及返回字段。冻结TerminalExecutor和所有旧文件不改。clone_for_transaction的字段审计和旧日志只追加契约必须有效；故意改旧日志、增未登记字段时拒绝。

第二步才设计一次epoch内的精确command/geometry复用：在经过原动态引用/预约/隐式释放/模式检查后，相同完整根和相同Connect参数可复用只读Gate C结果。最终ActionValidator独立事务仍执行，现场Atomic.submit重新核对资源、真实释放集合和trial/live状态，不能把缓存许可当成现场成功。

缓存生命周期绑定独立版本起点、完整父修订、源码/manifest原始字节、实体路径/打开句柄保护、catalog全内容、硬件配置、root完整状态和now。键包含有序双端、setup、orientation、release_after、window全字段、numerical_epsilon和所有资源字段；不能仅以K或“双端空闲”索引。状态变动、恢复、资源预约、旧链接TX时间改变、文件修改/替换/删除/路径重解析使缓存失效或拒绝。返回小结果防别名写入，绝不共享可变试事务。

SGP4 native公开状态可能随调用改变，先不跳过原SGP4.state调用；若将来复用纯LOS/FoR，要保持输入向量顺序、float.hex时间和数值次序并证明native可观察状态一致。硬件任意回调未证明纯性时不缓存。保持原首个拒绝原因优先级，不为减少成本将后面的几何拒绝提前返回。

## 可证明性与验收设计

FIFO先用有连续注入、部分服务、同刻比例混合、部分cohort、断路、多跳尾流、亚1e-12区间的短解析fixture逐记录对照：精确Fraction质量/年龄矩、所有Cohort/Stream字段/顺序、误差/闭合审计、A/Q/I/D、终端事件/能耗均相同。扫线要专门验证端点相同、不同原始注入时间却相同到达时间、重复Stream，以及无输入仍服务积压；保持1bit真实丢失负向拒绝。

Gate C先比较每个受控动作的accepted/reason、Connect全部字段、ready、window删失字段、实际释放集合与完整terminal snapshot，覆盖ADD/DROP/BBM/MBB、占用/预约冲突、TX、setup abort和自然失效；篡改源码/路径/资源/摘要键负向测试必须拒绝。纯计算缓存命中与未命中顺序交叉，结果完全相同。

之后才申请有界原/变体配对成本测量，分别记录完整物理目录覆盖和小分支，不自动重跑1100秒BBM或完整目录。运行时测量与profiler计数分开；预解析code对象以区分Cohort.consume、ledger.consume、metrics，计数器不得进入业务对象哈希。数值精度、不变量及FIFO业务记录不可关闭。只有这些验收通过，才能申请160星BBM受控复测及完整枚举/epoch恢复，仍不启动预实验矩阵。

## 工程工作和风险估计

工作规模为中等至偏高：两个独立接缝模块（FIFO索引/扫线、Gate C结构复制）、一个受控epoch缓存上下文、等价/篡改/事件/恢复证据与新的绑定工厂。建议拆为至少“Gate C一行复制策略变体”“FIFO检索变体”“后续精确结果缓存”三个独立验收单位，先做最小、较容易证明的结构复制。

结构复制已有冻结参考接口，可证明性较高；扫线对大量重叠流的输出增长、索引维护和端点顺序证明难度中等至高；跨root/跨epoch缓存一律不在最小设计内。无法承诺300秒完整目录或3秒实时决策，也没有优化后墙钟实测。任何需要覆盖冻结内核的接缝缺口应STOP另报，不通过继承隐藏改变业务行为。
