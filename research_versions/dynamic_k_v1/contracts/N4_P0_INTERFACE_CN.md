# N4-P0 最小接口说明

仅为 PILOT_ONLY 工程接口；不提供四臂预实验 runner，不声称科学性能优越性。实现入口为 `../runtime/n4_p0.py`，验收与成本结果入口为 `../acceptance/0010/RESULT_CN.md`。

|接口|输入|输出与约束|
|---|---|---|
|`P0EvidenceBinding.verify()`|项目根、候选 manifest 路径及独立 SHA-256|逐文件原字节绑定、参数 null、PILOT_ONLY 周期为 3 秒；每次实际运行保留原绑定验证|
|`causal_view(atomic)`|原 N2 AtomicTopologyController|不可变 CurrentObservation 和已承诺状态 JSON/hash；不含真 trace、外生未来边界或真源 hash|
|`ForecastInput.from_current(obs,T_s,H_s,mode)`|当前观测、显式工程 T/H、ZERO 或 PERSIST|同 epoch 的不可变未来外生率定义及哈希，h=min(H,T−t)|
|`make_sanitized_root(live,forecast,binding=...)`|当前 N2 完整对象、预测、P0 绑定|SanitizedRoot；观察日志构造历史前缀，deepcopy memo 在复制时替换真 trace/边界/旧缓存源哈希；预测率必须精确等于当前 ZERO/PERSIST 定义|
|`SanitizedRoot.verify_isolation()`|净化对象|遍历可达数据与函数闭包/默认参数，拒绝外来 trace，核对分支源/边界/未来政策；不是恶意 Python 或文件系统安全沙箱|
|`clone/checkpoint/restore`|净化根|完整 N1a/N1b/N2 对象及 FIFO/能耗游标的内存副本；不声称跨进程/磁盘序列化保证|
|`score_action(root,action,cost,cadence_s=3)`|净化根、原 N2 动作、PilotCost|原 N2 提交回执、原子动作之后 HOLD 的真实推进、J_h/N_end/E_h/DeltaE_h/单位正确综合代价、原始 N2 嵌套结果、状态 hash、事件/cohort 和计时|
|`retain_small_domain(source)`|原 N2 未设保留预算的完整合法集合|HOLD 1、ADD≤2、DROP≤2、REPLACE≤2，当前公开 OD 目标与字典序排序；逐类合法/保留/截断数|
|`score_candidates(root,candidates,cost)`|同根、同预测的小域|固定排序评分、去重、非法动作拒绝记录、最小代价/HOLD 平分优先/action_key 确定性选择；不执行 live 选择动作|

评分公式：`J_h=J(t+h)−J(t)`，`DeltaE_h=E(t+h)−E(t)−1600h`，`C_h=J_h+lambda_N*N(t+h)+lambda_E*DeltaE_h`。单位分别为 bit·s、J、bit·s；N 包含 Q/I。N1a/b 原计量器仍从 0 保留完整历史，不能把根以前的 J/E 再收取一次。无交付均值仍为 null，不使用 J/D。

新评分对象不会持有 live engine。live 的完整真 trace 可继续供实验管理器真实注入，但不得传入评分器或预测候选排序。因果观测中的已承诺 setup/TX/传播到达日程及原始 cohort 年龄不是未观测未来外生业务；原 N3 CurrentObservation 自身不足以预测完整物理/业务演化，此只读扩展单独披露。

每个分支只提交一个首动作，后续沿 3 秒检查点和原事件循环保持；t=27 的 h=3，其余注册 epoch 的 h=6。中途排空不停止能耗；终端事件、注入变化、传播完成不与三秒网格强制对齐。分支未到真实 T 时的 N1a 完成标志为 checkpoint，预测另以到 t+h 判断正常结束。

不导入或调用旧 B4/f3_v2 的评分器、预测器、安全策略或克隆器。物理合法性、资源、显式释放、BBM/MBB、流体数量和 FIFO 都由冻结 N1a/b/N2 处理；不创建第二套状态机或调度器。

成本计时同时记录外层墙钟和嵌套调用的互斥分类时间。分类包括绑定/hash、网络、FIFO、终端能耗、其余阶段工作，避免把嵌套时间重复相加。计时包含 Python profile 开销；进程峰值工作集是 Windows 高水位，包含 fixture 构造，不能解释为一个瞬间新增 clone 的精确内存大小。

独立 Current-State Greedy 建议：共享候选域，只依据当前排队、当前率、已保存路由上当前瓶颈容量压力及候选对瓶颈/传播长度的即时改善进行确定性排序，可公开一个 setup/能耗单步代理，但不进行 H 秒 rollout。与原 N3 Reactive 分开命名，阈值和代理须另行审阅；本轮不实现。它可以帮助区分“原可达性规则不响应拥塞”与“多步预测确有额外价值”。
