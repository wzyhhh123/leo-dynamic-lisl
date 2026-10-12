# Walker-Star Gate A 修复方案 v0.2

日期：2026-09-18。状态：**方案供审阅，未修改/运行生成脚本。**  
配套：[实验合同v0.2](./LEO_dynamic_LISL_experiment_plan_v0.2.md)。  
审查来源：[DESIGN_REVIEW_CN.md](./reviews/DESIGN_REVIEW_CN.md)。

## 1. 修复目标与当前证据

目标是使指定720/18/40 Walker-Star的几何验收真正拒绝错误输入，并在显式TwoBody/J2000/km/deg/UTCG/common epoch下生成可重放资产。这里不实现终端、traffic、routing或topology算法。

旧脚本SHA256：3891f4725912902796ba7cd658254784ddb7fe2d101873759ce07a708849659e。旧纯函数预审见[gate_A_preflight.json](./reviews/gate_A_preflight.json)：10°、20°、1°RAAN递进和交替±0.5°相位均返回PASS。只有第一项符合指定目标；旧预审状态继续是FAIL，不因发布v0.2而改标。

本机STK11 COM注册、comtypes及类型库存在；STK许可、实际启动、Walker命令和数据输出尚未实跑确认。环境存在不是runtime PASS。

## 2. 实现边界与拟修改位置

不覆盖Downloads中的用户原文件，不修改network_skeleton/generate_scenario_X100.py或旧生产执行器。后续拟在独立Gate A模块维护修订版及纯验收器；本轮不创建可执行修订版。

| 原文件位置 | 拟修复 |
|---|---|
| audit_constellation，322–337 | RAAN从“相对自身均值均匀”改成“相对指定Star模板逐plane匹配” |
| 350–354 | 移除每对独立±最小值；校验同一预声明σ的全局相位递进 |
| read_classical_elements，91–94 | 只读取合同J2000；不可用则FAIL，不静默换ICRF |
| 486–499 | 先SetPropagatorType(ePropagatorTwoBody)，使用有名称的J2000枚举；显式设单位、state epoch、传播窗 |
| 453–475、515–517 | 独立新场景，失败不吞异常；只操作本次新建对象；不卸载用户原对象 |
| write_manifest | 补epoch/frame/units/r-v/source name/稳定ID与hash |
| 保存及退出 | 审计前产物标unverified；失败保留诊断但无PASS标记；不覆盖成功run |
| parse_args | 合法范围/有限数/时间顺序校验；正式profile强制18×40/F1，其余仅smoke模式 |

旧script直接使用数值3，本机STKUtil映射为J2000；修复不是把3猜成ICRF。传播、审计和r/v导出统一J2000；需要其他frame时先统一转换并验证，不混合数值。

## 3. 预先冻结的形式化验收

### 3.1 配置及数值

正式profile：N=720，P=18，S=40，Star span=180°，a=7578.137km，e=0，i=85°，F=1，Ω_seed=0°，u_seed=0°，epoch=2026-01-01T00:00:00Z。所有输入/观测必须finite。

sigma默认+1。若STK小样的确定性约定需要−1，必须显式更新配置和校准记录；完整运行前冻结。验收器不能从任意正式观测中按边自由推断符号。

容差初值沿用旧合同并明确单位：半长轴1e-3km，e为1e-9，inclination为1e-6deg，轨内间隔1e-4deg，RAAN目标及轨内RAAN聚类最大偏差1e-4deg，相位1e-3deg。这些是拟采用的数值阈值；任何变更必须有精度依据和版本记录，不能因负向测试失败临时放宽。

### 3.2 plane grouping与RAAN

定义角误差wrap180(x)=((x+180) mod360)−180。对每个目标plane：

    Ω_expected[p] = wrap360(Ω_seed + 10*p)
    abs(wrap180(Ω_observed[p]−Ω_expected[p])) <= eps_RAAN

将卫星按到目标plane模板的圆周角误差唯一分组，要求18组、每组40颗、组内每颗RAAN对目标均满足容差；不得靠过宽聚类把错误plane并入。正式场景固定种子0°，不能通过自动旋转模板把错误绝对RAAN消掉。

再独立检查按seed展开后17个相邻plane的有向间隔均为10°，首末中心差170°。不检查17→0为10°，也不要求首末差180°。通用测试可用跨360°的非零seed验证圆周实现，但不改变正式profile。

同时断言总数720、ID唯一、plane_id恰为0..17、每组slot ID恰为0..39（显示名可1-based，manifest须说明）。命名正确不是轨道正确的替代。

### 3.3 轨内及全局相位

圆轨道使用同一J2000 frame的argument of latitude u；如由r/v计算，固定节点线与轨道法向符号。AOP+true anomaly在e≈0退化时应与向量重建交叉核对；mean anomaly不能在非圆轨道时无条件当true anomaly，本profile非圆e违规直接FAIL。

先对每plane的40个u做完整环排序，40个差分（包含最后到第一个）均为9°。再对每个u检查模9°的全局模板残差：

    expected_phase[p] = u_seed + sigma*p*0.5
    residual(u,p) = ((u−expected_phase[p]+4.5) mod9)−4.5
    abs(residual(u,p)) <= eps_phase

每组40颗均须通过，同时独立记录相邻plane的有符号相位偏移；所有17对接近同一个sigma×0.5°。这样既检查绝对相位又检查局部递进，不允许+0.5/−0.5交替。

稳定slot分配按从本plane预期phase展开的9°位置计算，不能仅用STK Children返回顺序。节点ID在其他时间不重排；propagate后不能重新按相位排序造成卫星身份交换。

### 3.4 propagator、frame、units、epoch

STK新建卫星后显式设置TwoBody，再查询实际propagator类型与接口；不能只在config里写TwoBody。设置并读取单位偏好，确认km、deg、UTCG；时间数值导出用epoch-relative SI seconds，记录UTC字符串和epoch，不将展示格式当独立epoch。

种子InitialState epoch、传播起始和采样t=0必须一致，arg_latitude=0°在这个epoch成立。实际J2000 provider不可用时返回明确失败原因。Frame transform仅在显式校验路径内使用，不默认fallback。

r/v额外检查：r大小约a、r·v≈0、v大小约sqrt(mu/a)，由r/v重建a/e/i/Ω/u与根数一致；TwoBody比能与角动量在多时刻守恒。允许的r/v重建与守恒误差在smoke输出中量化后按预注册阈值验证，不通过大角度容差掩盖frame错误。

拟定交叉验证初值：解析TwoBody同μ同epoch同frame位置误差≤1m、速度误差≤1mm/s、相对能量/角动量范数变化≤1e-8。若STK输出舍入/采样造成误差，先增加输出精度、修正共同frame/μ，任何阈值更改写明原因；这些拟定标准尚未实测验证。

## 4. 必须新增的验收测试（计划，未运行修订版）

| ID | 用例 | 预期 |
|---|---|---|
| A-T01 | 正确18×40、10°、全局+0.5° | PASS |
| A-T02 | RAAN间隔20°的Delta式记录 | FAIL：RAAN_TARGET |
| A-T03 | RAAN间隔1° | FAIL：RAAN_TARGET |
| A-T04 | 相邻phase交替+0.5/−0.5 | FAIL：GLOBAL_PHASE |
| A-T05 | 全部−0.5°，配置sigma=+1 | FAIL；不能自动转正 |
| A-T06 | 全部−0.5°，预声明校准sigma=−1 | PASS（显式非默认配置测试） |
| A-T07 | 某plane整体相位错0.1° | FAIL：GLOBAL_PHASE |
| A-T08 | 单星轨内间隔或RAAN超差 | FAIL；组均值不能掩盖 |
| A-T09 | 缺星/重复星/错误plane population/重复ID | FAIL |
| A-T10 | 正确轨道但Children顺序随机打乱 | 结果及稳定ID不变 |
| A-T11 | 非零seed跨360°的通用测试 | 圆周计算正确；正式profile仍固定seed0 |
| A-T12 | 非finite、非法P/S/F、stop<=start | FAIL，COM前拒绝 |
| A-T13 | 元数据写km但实际读取m、frame混合、epoch错位 | FAIL：UNIT/FRAME/EPOCH |
| A-T14 | 非TwoBody类型或未传播完整范围 | FAIL |
| A-T15 | 160/240子集改过RAAN、相位、r/v或ID | FAIL：PARENT_MISMATCH |
| A-T16 | 同配置同环境重复生成 | 稳定几何字段在容差内一致；非几何运行时间字段不要求hash相同 |
| A-T17 | output目录已有成功产物或场景非本run | 拒绝覆盖；不删除/重命名原对象 |
| A-T18 | 只在t=0正确、后续状态不符共同TwoBody传播 | FAIL：EPHEMERIS |

Gate A负向测试是验收器正确性，不是论文性能实验。修订验收器应有自动assert期待结果；不能只打印PASS字符串供人工猜测。

## 5. 实际执行顺序（后续实现计划）

### A0：纯函数验收器

读取合成记录，无COM依赖；执行A-T01至适用的负向测试并出machine-readable结果。原始坏例必须全部被拒绝。通过后才进入STK smoke。

### A1：STK小样smoke

独立隐藏的新STK实例/唯一场景，不附着修改用户场景；明确创建/关闭资源归属。先一颗seed检验units/frame/epoch/propagator/provider，再用少量Walker卫星检验命令和分组，例如3 planes×4 sats的测试profile。

smoke采用与其规模对应的180/P、360/S、F×360/(PS)，不能把小样硬套正式10°/9°/0.5°。正式profile不会因smoke参数改变。STK实际版本、许可/COM异常原样记录。若接口不支持预期调用，修正适配层后重复smoke，不继续批量创建720。

### A2：720正式母资产

干净独立run，以冻结profile创建720；只统计本次生成对象，完成全量根数与共同epoch r/v审计。校验完成再写完成标志；FAIL保留diagnostics并禁止后续使用。生成过程不进入网络模型。

### A3：ephemeris验证

共同时间点至少含0、60、600秒、窗口末，以及非整步验证点17.3秒。按实际传播覆盖导出r/v，另与同μ的解析TwoBody对照。

时序导出步长、压缩格式和连续覆盖区间由manifest明确；不默认720×86401个1秒CSV记录。可以先导出覆盖smoke/验证窗口的稀疏样本及完整初始状态，验证可重建轨道；若完整24h尚未导出或重建验证，应标coverage范围，不能称完成24h ephemeris认证。后续Gate C需要的采样精度另做误差验证，Gate A不凭粗采样证明lifetime。

### A4：严格子集

从母资产选择明确的4/6连续plane IDs，输出160/240 manifest、边界标记及母hash。每个选中卫星在每个共同样本时刻r/v与母记录完全对应；若重新编码浮点，比较解析数值和单位并记录文件hash差别，不把文本序列化差别误认为轨道变化。不重新传播一个缩小Walker星座，不加外部连接。

A4只提取几何数据，不定义网络edge，不执行B–G。

## 6. 产物与PASS含义

建议每个独立run输出：

- constellation_config_720.json：请求值＋实际propagator/frame/units/epoch/STK版本/μ。
- constellation_manifest_720.csv：稳定ID、根数、共同epoch的r/v及来源。
- constellation_audit_720.json：逐断言、误差、阈值、FAIL reason、实际验证覆盖。
- ephemeris资产及索引：时间范围/步长/frame/units/hash、插值或重建说明。
- subset_160/subset_240：母ID、选定plane、边界、逐状态一致性审计。
- provenance.json：脚本/config/input/output hash和环境。
- gate_status.json：A0/A1/A2/A3/A4分项状态，不用单一PASS遮盖NOT_RUN。

只有要求的分项都通过，才写Gate A总PASS；本轮status仍为DESIGN_ONLY，旧A0结果仍FAIL。物理端口FOV、tracking、LINK_READY、全网连通和traffic均不在Gate A PASS含义内。

## 7. 依据

本方案使用已核对的STK接口定义，不在本轮重新声称实际跑通：[Walker Star范围与相位定义](https://help.agi.com/stk/Content/stk/tools-12.htm)、[Walker Connect命令](https://help.agi.com/stk/12.10.0/SubSystems/connectCmds/Content/cmd_WalkerSatellites.htm)、[SetPropagatorType](https://help.agi.com/stkdevkit/Content/DocX/STKObjects~IAgSatellite~SetPropagatorType.html)。文档版本与本机STK11差异通过A1验证，不以较新文档替代本机测试。
