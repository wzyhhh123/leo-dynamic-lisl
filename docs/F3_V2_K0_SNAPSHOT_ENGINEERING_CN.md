# K0逐点结构证据生产器：工程范围与验收

状态：ENGINEERING_ONLY；不是Gate K0 PASS，不冻结K0-v1.1，不选择K*。本轮使用8星合成fixture，不运行160星完整K×20、不运行controller/traffic/service/J或注册论文实验。10月31日总目标仍未完成。

## 实际执行与接口

`src/dynamic_lisl/f3_v2/k0_snapshot.py`接收明确的节点/固定边/plane mapping、Gate C physical layer、K/t、双端retarget/acquisition、solver节点与wall预算、输入hash，以及逐点初始化约定。可选的BatchDiagnosticSpec必须给出子集evaluation预算和原OperationalPolicy，无隐式main-scale预算。

顺序为：该时刻双端IDLE root → 原Gate C uncapped setup-qualified候选 → exact terminal matching上界 → 原解析证书solver；不能证实时回退原bounded exhaustive reference → 精确K/端口/禁止并行卫星对与lex目标校验 → 所选每条link重新调用Gate C → 假设预建立的原Gate B原子事务 → 图结构 → uncapped REPLACE inventory → 可选原batch整段transition safety。没有第二套仿真器。

matching是terminal-degree relaxation，不能据matching容量大就宣布受额外约束的Z_K可行；只有capacity<K时可给出明确infeasibility证明。解析界未达成不是一般不可行，仍可由原reference求解；超budget保留UNKNOWN，不把incumbent用于预建立或正式K1。

独立快照约定为`INDEPENDENT_PREESTABLISHED_AT_SNAPSHOT_WITH_FORWARD_GATE_C_CERTIFICATE`。forward资格的ready使用原Gate B/C retarget/acquisition；snapshot预建立状态构造使用零时长，仅表达该结构点已有连接的条件假设。它不证明这些链接已经沿真实历史建好、不允许production action跳过setup，不等于K1初始化已审批。HF_K集中审批清单已增加此事项。

输入geometry/window不改。右删失end=600代表观察截止；physical_end=null，有限窗口寿命为min(end,600)-actual_ready；自然end已知时保存其真实时间。两个类型及严格ready<end分别检验。截断寿命不冒充完整寿命。

## 证据内容校验

每点独占目录保存snapshot、solver及各求解attempt、physical、uncapped inventory、lifetime、matching、component wall、预算、四类support引用及artifact hash。目录/文件不允许覆盖旧attempt；输出必须位于调用者指定root内，replay_index只允许0/1。

`k0_support.py`及ledger磁盘loader在精确path/hash校验后检查实际JSON内容：solver语义/坐标/hash、scene mapping、原IDLE root、候选记录/删失/摘要、重新matching、selected membership/resource/lex objective、原Gate B预建立state/event/counter重构、graph/bridge、REPLACE root/成员ID/index、重建snapshot及统计一致性。hash正确的空support文件和重封存的错误terminal/lifetime/metrics均拒绝。

此loader明确不是全局optimality独立证明，也不独立重新生成Gate C窗口或证明uncapped inventory枚举完整性。报告这三项为false；正式完整K0仍需要输入provenance、独立solver证书验证与原source重放。直接ledger函数的literal fixtures仅验证汇总阈值，不能提供自然审计provenance。

## 工程验收入口与范围

在conda pytorch执行：

```powershell
python tools/check_f3_v2_k0_snapshot.py
```

这是固定8星/四plane fixture：每plane两星与一条fixed edge，A/B两组跨plane环的8个terminal-pair窗口，全部0–600右删失；retarget两端各1s、acquisition1s。仅t=0/30/570、K4各双replay，另外保存预算1节点UNKNOWN、K16超过matching上界EXACT_INFEASIBLE两个control。没有完整自然扫描开关或正式K*选择。

tiny匹配证书达到16个terminal/2的8边上界；独立穷举8条候选的70个K4子集，验证原solver完整lex解，三个t均成立。正常ready=2/32/572，可用寿命598/568/28s。每点双replay的语义hash完全一致，wall从canonical replay中排除，求解节点/预算结果保留。

t0的批量诊断使用2516个size1..4子集上限，记录supplementary singleton mode revalidation数量、模式构成及size计数。真实Gate B/C+STRICT_CONNECTED验证存在四链MBB witness，且root不变。最大4的action权限提供上界，witness达到4只证明该允许范围的最大值；底层较大全集UNKNOWN不改判。t30/570未执行该诊断，不能扩展t0结论。诊断不参与原K-admissibility。

当前完整入口证据：[report.json](../outputs/f3_v2_k0_snapshot_20261008T172718_339531Z/report.json)。focused测试覆盖双replay、solver UNKNOWN/上界infeasible、Gate C certificate变更、strict lifetime、generator输入、独占写入、内容扰动、四链witness与诊断预算不足。原开发版本的SyntaxError及源码bytes独立保存在`outputs/f3_v2_k0_snapshot_development_20261008T171603_145700Z`，未覆盖旧失败；之后的新attempt独立验收。

## 剩余依赖

完整K0编排仍需实现和验收审批/哈希/逐点费用上限/partial checkpoint/失败封存；main-scale uncapped source不得因耗时把部分库存伪作完整结果。正式执行还需K0-v1.1及快照初始化冻结、输入provenance、资源预算和结构运行授权。K*及K1仍待这些依赖；B4最终K*/5s/完整pool自然多epoch、正式manifest和性能运行授权仍未满足。现有42项计划/ID/配置及历史Gate资产保持不变。
