# F3-v2 结构求解、评分与交付管线工程结果

状态：ENGINEERING_ONLY；科学合同仍DRAFT_NOT_FROZEN。不选择K*，不运行正式实验，不将工程检查解释为算法性能优势。

## K0：一个真实物理输入点的精确证书

预声明工程成本点t=0、K=24，160星、原Gate C 0–600 s窗口、所有动态终端初始IDLE；不是正式K1初始状态。原Gate C逐项筛查得到1996条候选，耗时59.241 s；exact terminal matching耗时0.710 s、cardinality=136。matching只放松了终端度约束，不能证明实际Z_K容量或K*。

原bounded穷举reference在5000节点预算结束，仍为UNKNOWN，耗时0.201 s。新增解析界证书路径不放宽原五级lexicographic objective：先用全部原候选形成平面端点失衡下界、plane-pair覆盖上界、总/最小截断寿命上界，只在同一方案同时达到四项界时声明EXACT；canonical include-first搜索保证该界层中的字典序最小方案。不能达到界或耗尽预算时返回UNKNOWN，不授权incumbent给K1。

该点证书搜索1223节点、0.017650 s；四平面各12个端点、六类plane-pair、24条链各598 s可用窗口，总14352 s。另一个独立验收检查了原inventory成员关系、精确K、终端度、无并行卫星对、plane mapping、严格ready<end、四项界与canonical replay；均PASS。598 s是600 s观察窗内的截断可用寿命，不能称完整物理寿命。

证据：[原成本点](../outputs/f3_v2_structural_cost_probe_20261008T152937_945871Z/probe_report.json)、[独立证书验收](../outputs/f3_v2_certificate_verification_20261008T154931_292950Z/report.json)。原报告的`main_scale_builder_ready=true`仅指`certificate_scope`指定的这一个成本点；新增工具已改成`this_cost_point_certified`，并明确`formal_main_scale_builder_ready=false`，旧证据未改写。

这不证明全部K×20 snapshots可解，不完成完整K0，不选择K*，不生成正式Z_K*。自然末段窗口、不同K及不满足解析界的实例仍可能UNKNOWN。不能用这个点将K0预算或完整审计状态填成PASS。

解析求解的6项tiny独立穷举测试包含50个固定随机子图、非均匀寿命、平行连接、mapping、cap和canonical replay。第一次测试发现现有pytorch Python不支持`int.bit_count`，FAIL及当时源码已原样保存；改用精确整数`bin(...).count('1')`后建立新attempt。没有修改环境、目标函数或容差。

### 三个预声明成本点的完成情况

|snapshot / K|物理候选数|原Gate C inventory (s)|exact matching (s)|解析证书 (s)|独立验收|
|---|---|---|---|---|---|
|0 / 24|1996|59.240935|0.709967|0.017650|PASS|
|270 / 48|1988|50.664379|0.512042|0.015548|PASS|
|570 / 80|1988|48.324422|0.459696|0.019520|PASS|

三点均从所有dynamic terminal真实IDLE的工程根状态筛查；没有traffic/Q/J，没有调用controller，没有选择K*。原bounded reference三点仍UNKNOWN，解析路径只在四项数学界同达时给出EXACT。570点使用真实ready=572与600观察截止；该点被选链的28 s窗口仍是截断可用寿命，不能视作自然失效时间。全部逐项证据与seal见 [成本汇总](../outputs/f3_v2_predeclared_cost_summary_20261008T155819_547812Z/report.json)。

三点不是完整K×20，也不是真实occupied-state REPLACE inventory、max33分支pool、整episode或42-run预算。不能将inventory单点费用线性乘snapshot/old binding/epoch后当实测总费用；这些缺项仍明确NOT_MEASURED。

## B3：真实current-state评分中的短寿命批次效应

固定8节点、等链路容量40 bit/s、每边传播0.05 s、两个OD各60 bit/s，真实D2推进至t=1后，只做current-state snapshot，不读取未来实现，不运行rollout。两条genuine MBB成员m0/m1和联合batch均由真实whole-transition validator生成。同一根状态在两种预先定义的窗口下比较，评分公式保持不变。

|窗口模板|动作|Delta V (bit·s)|min eta|B3 score (bit·s)|
|---|---|---|---|---|
|两条同寿命|m0|4.5|0.93103448|4.18965517|
|两条同寿命|m1|8.9|0.93103448|8.28620690|
|两条同寿命|m0+m1|8.9|0.93103448|8.28620690|
|m1短寿命|m0|4.5|0.93103448|4.18965517|
|m1短寿命|m1|8.9|0.11111111|0.98888889|
|m1短寿命|m0+m1|8.9|0.11111111|0.98888889|

等eta时公式没有显式batch-size惩罚，但本例联合snapshot收益与m1相同，因此出现真实exact tie。m1变短后，联合batch理想snapshot收益大于m0，却因min eta得分更低，B3选择m0。这说明该聚合可偏向小批次，是保守启发式，不是精确服务机会成本。对正收益动作，联合方案胜出需要`DeltaV_batch / DeltaV_single > eta_single / eta_batch`；这只是评分代数条件，不是网络真实J的break-even定理。

证据：[tiny实际评分报告](../outputs/f3_v2_tiny_eta_20261008T152205_955774Z/report.json)。没有根据结果调整B3公式、beam、pool预算或选择主场景；不推断主160星场景效应大小。是否接受`min eta`作为正式B3-v2定义需HF_SCIENCE一次性审批。

## manifest、结果审计和图表接口

42-run审阅manifest保留原run ID、配置、顺序和13组B4–B3公平主比较，核验原parent与traffic/K4资产hash；K*、科学freeze、production验收和逐run实测预算继续留空。输入必须与磁盘原草案一致，不能将重签的内存改稿冒充原源文件。

固定opening case绘图入口先加载全部registered sealed results；任何未完成、未冻结、wrong-input/config、缺尾时间线均拒绝。保留COMPLETE/CENSORED，不按truncated J排序、不换case；输出原N/Q/I和REPLACE、实际LINK_UP/DOWN、60/120/180/240 s phase标记。PNG/PDF版式已用明确标注的literal engineering fixture检查，此图不是论文实验结果。

新代码均隔离在`src/dynamic_lisl/f3_v2`及独立tools/tests路径；原Gate B/C/D与controller未改。正式preflight仍须fail closed；工程报告或审阅草案不构成正式运行授权。

最新当前代码验收：[110项v2与439项full regression](../outputs/f3_v2_engineering_check_20261008T155127_587459Z/report.json)，全PASS；3164项受保护基线完整性PASS，仅明确授权的4份October计划改稿由独立hash链接受。正式preflight实际运行结果为 [NOT_READY](../outputs/f3_v2_preflight_20261008T155444_270513Z/report.json)；新版本总体B4-v2工程PASS仍false，不启动P1-v2/P2/RL。
