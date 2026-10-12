# N3 当前业务感知闭环工程合同

仅适用于 dynamic_k_v1 修订 0007。复用已绑定的 N2 AtomicTopologyController、Gate B/C/D2、N1a 固定 T/320 终端事件积分和 N1b 本地 per-commodity FIFO，不修改其源码、合同或历史结果。本轮是工程机制验证，不是科学 Gate 或控制器性能实验。

STATIC_HOLD 每个工程 epoch 提交 HOLD；自然失效与业务/传播/终端事件继续推进。它不是严格固定 K。

REACTIVE_DYNAMIC_K 的输入是不可变 CurrentObservation，以及 N2 当前合法且保留的候选。观察只包含当前时刻、节点、固定和 admit 边、commodity OD、本地 Q、边上 I、当前注入率、连接、终端及预约标识和 K。不提供 trace 对象、未来边界/业务、评价 T、指标、未来控制动作或 evaluator。读取当前注入率调用 rate_at(now)，不读取后续 trace。

规则只比较当前无路由需求是否能通过候选新边变为可达。队列 bit 与当前 bit/s 分开排序，不混合单位。先按改善的当前队列 bit 降序，再按改善的当前注入率降序；相同改善优先 REPLACE（移除旧边后不损失已有需求可达性），其次 ADD；合法 REPLACE 中优先真实有资源的 MBB，再 BBM，最后使用 N2 action_key 字典序。不声称经济最优或全局最优。此处只是假想完成建链后的规则收益排序，真实结果必须等 N2 完成 setup 才增加 K；物理合法性始终由 N2 判断。规则不是全网连通硬掩码，允许分区。

不存在收益动作且所有当前 Q、I 和注入率均无正需求时，按 action_key 释放一条合法旧连接；否则 HOLD。使用精确正/零判断，未引入低利用阈值。未来业务不可见，因此当前无需求 DROP 可能影响未来业务，此限制必须在工程报告保留。对未交付业务和在途业务不做删除操作。

运行器接收显式 TEST_ONLY epoch 序列、setup 和可选候选保留预算。每个 epoch 恰好提交一个原子动作；这是本轮工程运行约定，最终联合动作上限未冻结。预算在物理验证后截断，审计保留 considered/legal/retained/truncated 和 NO_LEGAL_PHYSICAL_ACTION / LEGAL_BUT_BUDGET_TRUNCATED 状态；不继承 F3 REPLACE-only 路径。正式决策周期、搜索预算、最大并行动作数、fixed_K/Kmax 与所有科学参数保持 null。

每个 epoch 先将 N2 推进到时刻 t、只读生成观察及候选、选动作、再次由 N2 事务验证和执行，保存 Gate 接受/拒绝原因与显式/真实释放集合。保存前后业务和终端观察、完整状态哈希、从上个 epoch 到本次操作结束的 Gate B 日志、到本时刻的 K 时间线；最后一段无控制事件区间仍推进到 T 并保存终端日志。状态哈希和配对 trace 哈希只用于运行审计，不作为策略输入。候选生成及选择前后必须保持 D2 状态哈希不变。

配对运行克隆同一 N2 初态，使用同一完整 traffic trace、几何、固定边、容量、内核、T、epoch 与 setup。展示 K(t)、交付率、J_T、已交付 bit 加权时延、E_LCT 和 DeltaE，仅用于验证功能。反应策略必须产生真实非 HOLD 动作，才能演示动态 K 机制。

完整 catalog 诊断绑定全部已登记窗口，核对每条记录与物理验证的覆盖；当前 t=0 使用完整 N2 CandidateSource，而尚未开始的窗口在各自左端点进行无业务只读 ADD 探测。另诊断当前连接的 DROP/REPLACE 路径。覆盖仅指冻结 catalog 的全部记录、160 星及上述受控采样时刻，不代表未登记全空间、连续所有时刻、所有释放子集或真实硬件校准。LOS/FoR 检查和 ready 检查、数值窗口及删失边界语义沿用 N2，拒绝原因据实记录。

年龄统计精度不重新定义：沿用 N1b 对编码 binary64 输入的分段分布有理积分及有条件数值闭合误差界；IEEE reconciliation 案例不得称为解析精确。J_T、A/Q/I/D、已交付时延与剩余年龄的一致性检查沿用已验收层。没有交付返回 null，禁止 J_T/D 代替。

遇到必须修改冻结生产内核、无法解释的业务守恒/FIFO/资源/候选覆盖错误立即 STOP。通过工程测试不意味着科学验收；N4 仍需新授权及 RL 问题定义，不实现学习算法或主实验。
