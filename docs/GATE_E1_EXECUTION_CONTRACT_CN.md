# Gate E1：小规模可解释机制实验执行合同

状态：人工批准启动 E1。本 Gate 只执行 deterministic small-scale mechanism validation；禁止进入 160 星 E2、Gate F topology controller、matching、MPC 或 RL。

## 1. Preflight 与冻结边界

运行前必须同时满足：Gate E0 状态为 PASS；`gate_e0_manifest_hashes.json` 中 sweep 与 scenario-selection manifest 的 SHA-256 一致；Gate A–E0 full regression PASS。任一失败立即停止。E1 不修改任何 E0 manifest 或 Gate C hardware asset。

四个 synthetic templates、break-even families 和完整 execution point list 必须在首次科学运行前 canonical JSON + SHA-256 冻结。runner 只消费 manifest，禁止根据 `J` 修改模板、选点或删点。

## 2. Setup sensitivity mapping

每个模板冻结 base transition：`tau_i0_ret`、`tau_j0_ret`、`tau0_acq`，并定义

`tau0 = max(tau_i0_ret,tau_j0_ret)+tau0_acq`。

目标 `tau_setup=tau` 使用 `s=tau/tau0`，分别令 endpoint retarget 与 acquisition 乘 `s`。因此 base 比例和 endpoint asymmetry 不变。override 只存在 `gate_e1` namespace。`tau=0` 仅为 REAL/IDEAL correctness point，不定义 kappa。

## 3. Paired branch 与 censor

每个 point 从同一 `S0` 克隆 HOLD、IDEAL-SWITCH、REAL-SWITCH；delayed anchor 另含注册的 DELAYED-SWITCH。各分支共享 geometry、terminal state、future traffic、router、capacity 和 drain limit。

若 HOLD、REAL、IDEAL 任一分支在 common drain limit 仍有残余工作，该 point 记 `CENSORED_AT_DRAIN_LIMIT`，输出每分支 residual backlog，并强制：

```text
reversal_status = NOT_EVALUABLE_CENSORED
break_even_use = false
```

禁止用截断 `J` 判断 reversal。执行时不合法的 delayed action 记 `INFEASIBLE_AT_EXECUTION_TIME`，不得换 candidate。

## 4. 冻结 templates

`configs/gate_e1_execution_manifest.json` 内嵌四个模板的 nodes、fixed edges、每星 D1/D2、old/target terminal pair、capacity、edge delay、commodity、focus/third-party sets、base action 和 structural reason：

- E-A `BBM_NO_ROUTE`：occupied terminal BBM，LINK_DOWN 到 LINK_UP 之间 focus OD 无路；
- E-B `BBM_CONNECTED_REROUTE`：BBM 期间固定 alternate path 始终存在；
- E-C `GENUINE_MBB`：target 两端存在真实 IDLE terminal，先 LINK_UP 再 release old；
- E-D `SHARED_CONGESTION_EXTERNALITY`：focus 与第三方 OD；释放 old link 后第三方流量进入共享 capacity-constrained edge。

所有 dynamic links 与 fixed links使用相同 per-direction payload capacity。流量为 deterministic fluid bit trace；`rho` 乘冻结的 template reference spatial shape。

## 5. E1-A core regime sweep

完整笛卡尔积：`rho={0.2,0.5,0.8,1.0,1.2}`、`kappa1={0.05,0.2,0.5,1.0}`、`kappa2={0.05,0.2,0.5,0.8}`、positive `tau={0.5,1,2,4,8,16}s`、四个 templates、两个 routers。每点令 `T_demand=tau/kappa1`、`L_remain=tau/kappa2`，且只注册 `ready<end` 的 Gate C/legal point。

另为每个 template/router 注册一个 `rho=0.8, tau=0, T_demand=10s, L_remain=10s` correctness point；其 kappa 值为 null。

每点保存三分支 `J`、Delta J、relative effects、reversal、mean bit delay、peak queue、transition backlog、no-route duration、route changes、focus/third-party Delta J、delivered bits、residual backlog和物理/守恒检查。

## 6. E1-B delayed anchor

冻结：`rho=0.8`、`tau=2s`、`kappa1=kappa2=0.2`，所以 `T_demand=L_remain=10s`。四模板和两个 routers 都执行 `delta/T_demand={0,0.25,0.5}`，单独报告，不和 core 合并选点。

## 7. E1-C break-even families

机器真值为 `configs/gate_e1_break_even_manifest.json`。每个 family 固定 template、`S0`、target、rho、`T_demand`、`L_remain`、traffic trace 和 router，只改变 `tau={0,0.5,1,2,4,8,16}s`。不得使用随 tau 改变的 kappa 构造。

相邻可评价点 Delta J 异号则按 E0 deterministic refinement 缩至 `<=0.01s`；不假设单调。多 crossing 全部保留；无 crossing 报 `NO_BREAK_EVEN_IN_SCANNED_RANGE`，不得扩展范围。

## 8. Routing robustness

Primary 为 deterministic shortest-propagation-delay router；robustness 为 deterministic current-state load-aware router。二者完整重放同一 frozen parameter-point IDs。load-aware 仅在当前路由重计算事件读取当前 `G_admit`、edge service utilization、node queue 与当前 offered rate；不得读取 future traffic/action 或 branch identity。

## 9. 解释、无筛选与 PASS

`epsilon_r=1e-9` 只作浮点符号分类。每个 reversal 同时报告 absolute Delta J、relative effect、mean-delay difference、transition backlog 和 no-route/reroute 行为；不能把仅跨数值 deadband 的微小差异称为工程显著。

所有 `NO_REVERSAL`、`NUMERICALLY_TIED`、`INFEASIBLE`、`NO_BREAK_EVEN`、`CENSORED` 结果必须保留。E1 PASS 不要求 reversal；没有时正式结论为 `NO_REVERSAL_OBSERVED_IN_REGISTERED_DOMAIN`。

PASS 要求 manifest 完整执行、paired identity、work conservation、nonnegative queue、capacity、deterministic replay、result-blind selection、E0 classifier/break-even 合同、两 router point 集一致、Gate A–E0 hashes unchanged 和 full regression 全部通过。

完成后写入 E1 result/status/report 并停止；`Gate E2 started=false`、`Gate F started=false`。
