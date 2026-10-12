# N1b — Node-Local Per-Commodity FIFO 独立语义合同

适用范围：仅 dynamic_k_v1 新研究版本。人工授权来自本轮用户指令。旧 D0/D2 冻结合同、commodity 级 equal-weight max-min 服务分配、原事件时钟及数值闭合保持不变。本文冻结业务选择语义，不冻结 T_A、T、tau_res、R_min、alpha、D_ref、E_ref 或算法；上述正式科学参数继续为 null。

## 服务与年龄

每个 (node, commodity) 有独立 FIFO。排序键为业务抵达本节点并进入本地队列的时间 t_local，不是全网原始注入时间 t_original。原始注入时间必须跨排队、部分发送、多跳传播、断连等待、恢复与重路由保留到目的节点。

同一 commodity、同一节点、同一时刻的多入边到达（包括在 source 返回的业务与新注入）按到达 bit 数量比例混合。不由边枚举顺序、文件顺序或事件 ID 选择先后。若密度 r_j(u) 同时到达，混合权重为 r_j(u)/sum_j r_j(u)。部分服务同样按此比例切分混合 cohort。

连续 cohort 以本地到达时间区间、bit 密度和原始注入时间的分段映射表示。对于仿射段 t_original(u)=a*u+b，任意部分区间的原始时间一阶矩为 integral r*(a*u+b) du；禁止把区间中点作为每个 bit 的注入时间。混合段保留各映射和权重。FIFO 可以在 cohort 内任意切分，保留被切分区间的真实分布。

目的节点到达计为交付；M_D=integral_delivered(t_delivery-t_original) db，D>0 时 mean=M_D/D，D=0 时 mean=null。截止 T 尚在 queue/in-flight 的业务不计入 M_D。年龄层不得修改 A/Q/I/D、容量、路由、Gate B/C、J_T、N(T)、R_del、固定 T、终端能耗或 K。

## 解析案例（非科学参数冻结）

1. 两批连续注入：r=6 bit/s 在 [0,1]、[2,3]，其他时段为零；[3,4] 服务6 bit、传播1 s、随后无服务，T=5。FIFO交付第一批，t_delivery=t_original+4，D=6、M_D=24 bit·s、mean=4 s、剩余6 bit年龄积分15 bit·s、原J_T=39 bit·s。
2. 同时合流：本地时刻 [4,5] 入边甲2 bit/s、t_original=u-4；乙6 bit/s、t_original=u-2。混合权重1/4与3/4。取本地到达区间的前半部分，甲1 bit、乙3 bit；若 [6,7] 以4 bit/s发送该4 bit，再传播1 s，M_D=23 bit·s、mean=5.75 s。边输入顺序不得改变结果。
3. 本地 FIFO 与原始年龄不同：更早原始注入的业务若更晚抵达某节点，不能越过已经在该节点等待的业务。
4. 单次连续注入10 bit/s、[0,1]，无排队、单跳传播1 s：D=10、M_D=10 bit·s。两跳各1 s且无排队：M_D=20 bit·s。无路由直至2 s，随后20 bit/s发送10 bit、传播1 s：交付区间[3,3.5]，M_D=27.5 bit·s、mean=2.75 s。
5. 零交付：M_D=0、D=0、mean=null；不能报告0或无穷平均时延。

在初始无历史业务、全部业务在[0,T]注入、无丢弃/重复的条件下，J_T=M_D+W_remaining(T)。全部交付时 W_remaining=0。初始历史业务存在时，必须另行提供原始注入分布，不可以默认年龄0，也不能无条件使用此恒等式。

## 观察接口与精度边界

优先以新版本独立适配子类观察原 D2 的 _integrate、_schedule_service_segments、_finalize_quiescent_propagation，原业务调用原方法执行一次。观察层不插入 D2 事件、不重新调用传播 delay provider、不修改服务 rates、队列数值或传播 agenda。对照原内核应证明完整业务状态、J_T、N(T)、能耗和拓扑指标一致。

年龄层内部可在 cohort 边界分段，而不推进原 D2 时钟。数值策略须明确：精确有理运算只可称对所表示的输入/事件段解析精确；浮点转换误差和原内核的舍入误差必须单列，不把工程浮点近似宣传为解析精确。任何质量差额必须可归属至已有 cohort；未知原始年龄、无法归属的数值闭合、先于真实到达的发送或超出已发送 cohort 的交付均拒绝，不创建虚构业务年龄。

若原 D2 服务事件与 FIFO 无法一致解释，或必须修改冻结生产内核才能准确追踪，立即 STOP 并保存具体证据，不以容差吞掉语义冲突。clone/checkpoint/restore 必须同时保留 cohort、本地顺序、原始时间映射、在途段、交付年龄矩与观察游标。

静态语义检查通过后才允许本轮实施 N1b。工程验收不代表科学性能结果；不实施 N2、MADRL、主性能实验或训练。
