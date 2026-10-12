# Gate F3-v2 baseline重新设计草案

**DRAFT_NOT_FROZEN；没有实现或运行新控制器。** 公共动作/时间/搜索预算详见联合重构设计与四份DRAFT JSON。核心contrast=B4-v2 vs B3-v2，先共享搜索机会，再比较当前状态proxy和显式网络预测；暂不MARL。

| baseline | 信息边界 | 决策评价 | eligibility |
|---|---|---|---|
| B0-v2 | CURRENT_STATE_ONLY | HOLD only | none; physical timeline identical |
| B1-v2 | CURRENT_STATE_ONLY | whole ideal batch V_v2 | common physical/safety pool |
| B2-v2 | CURRENT_STATE_ONLY | B1-v2 deltaV + per-binding hold | common pool + own hold filter |
| B3-v2 | CURRENT_STATE_ONLY | whole batch deltaV*min_eta | common physical/safety pool |
| B4-v2 | SHORT_HORIZON_FORECAST | actual cloned joint-root J_H | exact same pool as B3 |

## 公共数学与动作

公共pool由物理/结构信息确定，含HOLD和合法size1..4 batch；snapshot目标图为 `G_A=(G_admit−all old edges)∪all new edges`，只将本次选择的batch理想瞬时执行，其余pending transition仍以root现状表示。每个batch重新调用selected frozen common router和V_v2 evaluate_edges，不加单动作分数。

V_v2继承scheduler-consistent定义：N_f=Q_f+I_f，C_prop为source路线传播时间和。当前local demand由queue>state_tol或current source/inflight input决定，按原equal_weight_fair_share计算实际allocation；有需求时R_snap为这些local需求节点allocation最小值，Psi=N_f²/(2R_snap)，没有local需求时Psi=0。V=sum[N_f*C_prop+Psi]。这不是path上所有commodity等分capacity的旧v1公式，也不是推进Q/I/D得到的真实J。保留无route/非正allocation等invalid理由和exact ties。

## B1-v2

在HOLD与共同pool的完整理想目标图中选最小V_v2，忽略setup导致的服务中断/延迟收益。真实physical readiness只用于共同合法性，不用eta或真实transition经济性给B1改选候选。执行选中的完整batch必须真实Gate B/C。总unfinished=0沿用HOLD；双方V=Infinity不构造NaN改善值。安全层拒绝，不经济修复。

## B2-v2

明确base=B1-v2，不混用B3。对每个将被替换的old binding检查actual elapsed seconds；建议time origin是该binding实际LINK_UP，new link只有LINK_UP后重置。initial links age需明确，建议constructed initial active_start=0；这会使H4初次可用t=5、H8为t=10，而旧B2首次无hold限制，属于科学语义变更。

旧B2_H4/H8配置均threshold=0，role=ENGINEERING_ROBUSTNESS_ONLY，代码是全局last accepted command timer，保持历史原样。一般5s采样使实际等待在[H,H+5)附近（其余eligibility可再延长），不能把4s/8s机械换成2/4个旧epoch。v2先读取共同pool，再要求每条member eligible，按B1全batch deltaV及threshold选择；threshold equality允许，但经济exact tie仍HOLD。H4/H8是否继续使用、initial-age规则与per-link timer等待人工批准，不按性能调参。建议最终鲁棒性纳入两配置，不让B2开发阻塞B3/B4。

## B3-v2

不是取单链前三/四名。共同结构beam对新增member形成的整个batch生成目标图；B3对每个保留batch重算V。建议 `deltaV_A=V_H−V_A`，`eta_r=L_usable,r/L_remaining,r`，`eta_A=min_r eta_r`，`S_A=deltaV_A*eta_A`。选择最大正S，否则HOLD。m可为1/2/3/4，不强制填满；所有时间来自actual Gate C/Gate B，并保留window右删失标记。

min_eta是新的待批准保守聚合，不是精确network service loss定理；one-member时恢复旧eta公式。不能用独立deltaV求和替代共享拥塞作用，也不执行10s service rollout。B3可使用current lambda、Q/I、current router/service和known windows，但不读forecast对象/真实未来trace。

## B4-v2

评价同一pool每个完整batch的 `J_H(A;t)=sum_f integral_t^(t+H_eff) N_f^A(s) ds`，HOLD同时评估。branches从同canonical root和current-rate-persistence forecast构造，真实joint Gate B/C→graph→common router→service→Q/I/D。root后不再调用controller，没有未来action tree，无terminal/switch/setup/outage penalty，所有effects自然进入J。nominal H=10，late截止统一H_eff=min(10,600-t)待批准。

持久8workers只是调度，不产生额外candidate；parent依次HOLD及canonical pool order归并，不按future完成顺序或机器速度选动作。live root不得被clone修改，branch之间/epoch之间mutable state不共享。v2 task是batch，旧单动作8-worker PASS只提供机制参考，必须重新通过多epoch exact/state-chain/orphan检查。

## 搜索公平性与解释边界

B3/B4对同一个root拥有完全相同的raw universe、singleton预算、joint beam/pool、整体safety和m<=4权限。共同pool在评分前hash；不同controller造成后续状态分叉后，不要求其实际proposal hashes仍相同。主路由条件内同primary router；robustness重放同initial topology/trace/params，仅换common router。

这一设计不需要额外search-matched controller，B3本身就是search-matched对照。若以后B4改用J-guided adaptive beam而B3使用不同beam，则必须新增B3-SEARCH_MATCHED：在同一由B4选出的pool内做snapshot选择，承认proposal generation含预测信息，分开报告搜索贡献与评价贡献；不能仍声称纯rollout收益。本轮不采用这种变体。

tiny B5仅穷举小fixture完整root batches，报告bounded pool recall、遗漏size及最佳动作是否遗漏，并分别比较B3的snapshot oracle和B4的same-forecast J oracle。两者通常不同不能当FAIL；只有专门proxy-exact条件才检验一致性。主实验双方COMPLETE时报告完整J contrast；任一CENSORED报告残余work/delivery/time，不截断J排名。

设计就绪不等于baseline已实现，所有预算/数值仍需人工冻结。STOP，不运行controller性能。
