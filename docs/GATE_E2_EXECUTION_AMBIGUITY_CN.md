# Gate E2 执行点歧义报告

## 已经无歧义并完成的部分

1. Pre-E2 absolute-time regression：PASS。
2. 160 星自然 terminal-pair candidate inventory：已生成，未读取性能结果。
3. E0 冻结 selector：已严格应用，所有空分层被保留。
4. selected scenarios：已在 paired branch 运行前冻结并做 SHA-256。
5. selected case Gate C/Gate B 实际合法性复验：PASS。

## 阻止 paired execution 的歧义

`configs/gate_e0_sweep_manifest.json` 同时列出：

- `rho={0.2,0.5,0.8,1.0,1.2}`；
- `setup={0,0.5,1,2,4,8,16} s`；
- synthetic E1 的 `kappa1/kappa2` 映射。

它没有明确规定 E2 自然几何 case 应运行：

- 仅 Gate C 基准 setup=2 s，还是全部 positive setup sensitivity；
- 单一 rho、全部 rho，还是某个预注册子集；
- 若 setup 改变，是否保持当前 selected case，还是必须重新按新的 natural kappa2 分层选择。

这三个解释会产生不同实验点集合；自行选择任何一个都会构成新的实验规则。因此本轮状态为：

`GATE_E2_CANDIDATE_SELECTION_FROZEN_AWAITING_EXECUTION_CONTRACT`

HOLD / IDEAL / REAL branch count 为 0，Gate E2 不能记录 PASS。

## 需要人工冻结的最小信息

只需明确两项即可继续：

1. E2 的 `rho` 集合；
2. setup 处理：只跑 2 s，或指定 sensitivity 集合，并明确 setup 变化时是否重新分层选择。

其余 branch identity、router、objective、censor、integrity 和 reporting 语义继续直接使用 E0，不再改动。
