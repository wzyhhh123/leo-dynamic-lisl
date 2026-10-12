# CP_K：完整K0等价优化可行性审计

本轮只分析原K0-v1.1执行器的依赖，不修改它，不运行完整480点，不选择K*。原12个K、20个采样点、两独立replay、matching、Fraction lex排序及门槛保持。

## 已有证明及未证明范围

`exact_terminal_maximum_matching()`调用NetworkX general-graph blossom，`maxcardinality=True`，使用superincreasing整数权重冻结canonical tie。tiny exhaustive oracle已覆盖奇环、重复/乱序、terminal-degree约束。自然三点的完整idle inventory有EXACT matching结果；这只是terminal-degree relaxation，未约束同星对并行和全局图安全，不能直接证明Z_K可行。

`certified_bound_topology()`仅在找到同时达到plane端点均衡下界、plane-pair覆盖上界、最大总寿命、最大最短寿命的canonical-first解时返回EXACT。自然t0/K24、t270/K48、t570/K80有完整局部解析界证书及独立验证。一般bounded exhaustive reference在这三个成本探测中仍为UNKNOWN，不能把它改判EXACT。其他K/t的证据缺失，完整K0为未执行，不是PASS。

解析证书未找到界层解时不能证明全域不可行；只能使用原exact reference，或保留UNKNOWN。matching<K可给出该点的严格infeasibility upper-bound证书，但不能用matching≥K反向证明可行。

本轮另对三个旧完整inventory作独立基数上界检查：每个图恰有272个incident terminals，matching witness包含136条合法、不共享端口的边，达到floor(272/2)=136。因此这三个graph的最大cardinality具有“合法witness+incident-terminal上界闭合”的完整基数证书，而不只是读取EXACT状态字符串。canonical tie仍依据原superincreasing-integer exact solver及当前回归，未声称另做自然大图的exhaustive tie oracle。该证明只适用于各自冻结输入graph，既不是Z_K约束证书，也不是完整20时刻/两replay K0证书。

由136上界还能严格推出：原K0 setup-qualified idle graph在t0/270/570下无法容纳K160。这是三个cell的数学infeasibility bound，尚未成为正式双replay K0 ledger；12个K及全部点仍保留，不能删除这些不可行记录。其他K<=136不能靠此上界认定可行。

## 可以优先证明的优化

|候选|严格key/失效条件|可证明保持的内容|实施状态|
|---|---|---|---|
|每replay的idle inventory预计算|精确t、完整ID/plane mapping、Gate C asset/hardware/source hash、端点setup/orientation参数、idle executor canonical hash；出现任何改变重算|同一snapshot的12个K共享相同全IDLE根状态；K只进入随后builder，因此可复用完全相同StructuralEdge/rejection序列|依赖隔离可证明；未接入K0；须在新工程overlay上逐字段旧/新对照|
|同一inventory的matching复用|exact canonical edge inventory hash、NetworkX版本与solver/source hash|matching不读K，cardinality/bindings/hash不变；不能替代builder|可证明；未接入|
|window/terminal-owner/reservation/satellite-pair只读索引|同一完整physical root与catalog/hash；只在该root内有效|减少重复lookup；resource reject需按原先检查顺序返回相同reason，随后仍执行原Gate B/C|合理实施候选；尚无完整reason/order等价证据|
|root canonical serialization复用|本次枚举起止root hash相同；期间禁止mutable state变化；源代码类型严格限制|减少重复序列化；不能以缓存hash替代每个未知extension的live隔离验证|需要专门状态依赖及mutation负控，未实现|
|同tuple joint validation复用|同root、action时间/frame/成员参数、catalog/config、policy、fixed graph；限定单次诊断|相同物理/安全结果；必须保留完整拒绝和预算计数定义|可作局部证明；不可用runtime proposer的bounded cache替代uncapped inventory|
|跨old binding复用Gate C几何|目标pair/t/setup相同仍不够；Gate B读取release_after、旧链tx/drain/visibility、terminal free-time、reservation/version及future events|仅distance/window metadata可以直接共享；完整Gate C返回不能按new pair alone缓存|完整返回复用未证明，保持原计算|

两次replay应使用独立cache实例、独立实际生成/验证，再比较canonical结构输出。不能把第一次replay完整结果复制为第二次的“确定性验证”。跨process的磁盘预计算必须content-addressed、锁定输入与当前source、只读加载、hash/schema校验；不允许“文件存在就接受”。

## 实际瓶颈与节省上限的区别

当前 `produce_snapshot()`在每个K/t重新创建全IDLE根，重新生成全量idle inventory和matching。将同一replay内相同t复用，可把这两类重复计算从480次降至40次；这是调用量12倍减少，不是完整K0的12倍提速。

最主要未闭合项仍是每个已认证Z_K上的uncapped REPLACE扫描。现有source在各old与current window之间逐项调用BatchPhysicalValidator；原raw32/32和runtime256 scouting均不得应用于K0。全部480点均可构造时条件调用数55,077,664；真实可构造点尚未全部求解，因此这既非已发生次数，也非耗时上界。

上述“全cell可构造”假设已在三个时刻的K160上不满足；55,077,664只能作为此前代数工作量包络，不能套平均成本当实际K0预估。正式执行应为每个不可行cell保留原完整证明和outcome，随后按原规则记录source阶段不适用，不以隐藏删除点减少工作量。

资源索引可以排除必然争用其他old binding的target，但必须保留原输出含义、reject reason和canonical顺序。target两个端口都IDLE时仍可能适用于很多old；Gate B/C、old release和whole-transition safety不能由索引代替。因此仅idle预计算不能据此宣布月底运行预算闭合。

## 唯一下一步

先做独立工程overlay的idle-inventory/matching预计算与原reference exact equivalence，并在上述三个预声明点测成本；同时对uncapped source的有序resource reject/index做字段级证明和完整有限fixture对照。任何未证明的Gate C/counterfactual字段保留。不得先启动完整480点长扫描或修改K/阈值。

overlay开发及小fixture验收成本尚未实测，标记UNKNOWN；原三点idle inventory约48–59秒、matching约0.46–0.71秒，仅能提供短探测的资源量级。它们不是40次或480次运行的保守wall保证。完整K0费用与最终K*仍UNKNOWN。
