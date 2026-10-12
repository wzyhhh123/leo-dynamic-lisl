# F3-v2 K0：有界隔离编排工程验收

工程范围为固定8节点synthetic fixture。自然160星完整K0未执行；Gate K0未PASS，K*未选择，历史DRAFT/FAIL和生产F3-v1不变。

## 实际接口与证据

`src/dynamic_lisl/f3_v2/k0_audit_runner.py`以spawn子进程运行每个结构点，每点必须显式提供solver节点/时间预算、uncapped inventory验证预算、batch diagnostic预算、总点超时及清理时限。预算是运行资源约束，耗尽不生成完整库存、不改结构阈值、不推断无候选。

每点按IDLE_ROOT、IDLE_INVENTORY、MATCHING、SOLVER、PHYSICAL_ROOT、逐条REPLACE_ROW、UNCAPPED_REPLACE_INVENTORY、BATCH_DIAGNOSTIC、SNAPSHOT_COMPLETE保存证据。stage sink接收只读副本，不得修改计算结果。solver exact证书和uncapped库存是否完成是两个独立状态。

UNKNOWN/异常/超时先保存已完成stage、候选前缀、子进程退出/清理记录和hash，再STOP；不重跑、不继续后续点、不把UNKNOWN标为EXACT_INFEASIBLE。超时只清理本attempt创建的进程，绝不处理用户已有实验进程。stdout/文件存在不是运行完成证据。

工程验收入口：`python tools/check_f3_v2_k0_orchestration.py`。六点为K4、t=0/30/570各两个replay；另设库存预算1、solver预算1、极短超时和未审批自然请求的负对照。所有阈值只用于8节点fixture，不成为生产默认值。全部spawn进程退出且join后才通过。

## 有条件自然入口

`python tools/run_f3_v2_k0_audit.py --manifest <path> --contract <path> --authorization <path> --preflight-only`只校验，不能将DRAFT自动变成FROZEN。正式结构执行还需去掉preflight-only并取得该scope的人工授权；这不授权K*选择或controller performance。

准入要求新合同与manifest明确FROZEN且canonical hash正确；原12个K×20个t×两个replay=480点原序列；科学字段与保留的K0-v1.1 DRAFT一致；独立人工批准精确绑定manifest/points，不允许K*选择。scene必须从精确绑定的原backbone、Gate C窗口及setup文件逐项恢复，节点160、4 plane×40、单位/epoch沿用原资产。所有消费的源码及CLI入口必须显式登记hash。

authorization文件在manifest形成后签署，所以其文件本身不反向纳入该manifest的hash而造成循环；入口验证批准内容后将其actual byte hash纳入before/after点保护。manifest中的contract_path/authorization_path必须与CLI参数一致。不接受任意当前源码、路径模糊匹配、遗漏父DRAFT或仅改status的伪冻结。

输出COMPLETE_STRUCTURAL_POINT只说明该点完成；全部480点完成仍只产生待独立review的结构证据，不直接记录Gate K0 PASS，更不选择K*。

## 尚未闭合

完整自然窗口provenance、全部solver证书、uncapped库存及batch diagnostic独立复核仍需正式审计。观察截止600不是自然失效；独立预建立snapshot初始化约定仍待人工冻结。K0运行预算须集中审批，不能用runtime的raw64输出cap替代uncapped结构库存完整性。

工程结果及源码hash以最新`outputs/f3_v2_k0_orchestration_*/report.json`和当前完整回归seal为准，不因历史文件存在继承PASS。
