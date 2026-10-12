# F3-v2 自然 K0 输入证据链检查

状态：**NATURAL_K0_INPUT_PROVENANCE_AUDIT_PASS / ENGINEERING_ONLY**。这不是 Gate K0 PASS，不是 K* 选择，也不冻结 K0-v1.1。

## 输入与复用关系

独立只读入口为 `python tools/audit_f3_v2_natural_inputs.py`，使用现有 conda pytorch。它不调用 matching、topology builder、uncapped REPLACE inventory、controller、traffic 或服务推进；只读取既有资产，并对每个结构采样点调用一次原 Gate C 的双空闲终端建链资格检查。Gate B 的这20个 executor 是临时资格检查状态，不是正式初始拓扑。

几何来源是 `outputs/geometry_20260921T053240_016088Z`；可见性来源是 `outputs/visibility_20260921T055451_308214Z/subset_160`；终端对窗口来源是 `outputs/gate_c_simplified_20260922T064019_313843Z`。原报告分别采用 `metadata.json`、`manifest.json`、`inputs.json`、`hashes.json` 的既有格式，不要求补造新的历史 manifest。

720母场景仍为 synthetic TLE + SGP4/WGS72/TEMEOfDate，epoch 为 `01 Jan 2026 00:00:00.00`，位置/距离为 km、速度 km/s、时间 s。160星是母ID中0–3 plane、每plane40个slot；没有重命名、重新传播或边界wrap。读取母/子NPZ并逐值检查位置、速度、时间和ID；子可见性记录逐条等于母记录诱导子集，不使用近似比较。

Gate C 的14份历史文件、visibility的13份历史文件、Gate C生成时登记的代码和输入均按原哈希检查。Gate A 的原始绝对姿态审计保留；当前使用依据是 `configs/gate_a_acceptance_v0.3.json` 的人工接受记录，其 absolute TEME common-mode offset 对当前 satellite-only 研究不阻塞。没有重拟TLE或放宽原阈值。

terminal executor与最初Gate B哈希不同，必须逐项核对历史Phase 1 overlay的父哈希、当前哈希、固定canonical hash、支持报告哈希和明确等价PASS；不是“接受当前文件”。其余原Gate B baseline字段保持原哈希。全部3164个既有基线文件检查期间不变；相对最初基线仅四份已经明确授权修订的October计划有登记差异，不包含科学/runtime变更。

## 实际结果与覆盖边界

首个报告：[report.json](../outputs/f3_v2_natural_input_audit_20261008T190116_616972Z/report.json)。共77项检查通过，耗时13.7042297 s；单独9项控制测试覆盖错误frame/epoch/单位、重复ID、parent错绑、删失标志、重叠、非有限值、路径越界和未授权hash。这些是新审计器的测试，不代替完整K0求解验收。

|对象|检查结果|
|---|---|
|终端窗口|2742条；1992条右删失、750条已知终端对FoR到期窗口|
|结构采样|0,30,…,570，共20点；不能声称覆盖全部controller epochs|
|t=0|1996个当前窗口；双空闲端口2s setup假设下1996个合格|
|t=570|1988个当前窗口；上述假设下1988个合格|
|最后代表例|原Gate C ready=572s，600s观察截止内usable=28s，RIGHT_CENSORED_AT_600|

代表例的2s来自当前retarget 1/1s和acquisition 1s；这是两端未预约且真实IDLE时的资格检查，不适用于已有TX draining的occupied-terminal BBM，也不证明任意MBB终端可用。完整K0必须从具体终端状态调用现有Gate B/C，不能统一用t+2替代真实ready。

删失窗口仅能支持 `max(0,min(window_end,600)-ready)` 的观察窗口内截断可用时间；完整物理寿命未知。自然FoR到期的窗口保留真实end，严格合法性和原数值epsilon不变。right-censor的边界分类容差复用原1ms，不延长实际窗口。5000km仍是diagnostic cutoff、90°FoR仍是未硬件标定的参数模型。

## 仍需完成

原Gate C 2s/1s扫描边界一致性报告已通过，最大偏移0.0003411487604125796s；它不是“不漏切点”的数学证明。本轮也没有重新计算SGP4物理轨迹或窗口。输入链检查没有证明全局matching/lexicographic最优、REPLACE枚举完整性、联合safety或K*合格性。

目前输入可用于获批的自然结构审计，无需因为t=600发起动作的问题重建1800s窗口。完整自然K0仍依赖集中审批：独立预建立快照初始化约定、K0-v1.1阈值、计算预算、执行manifest及结构运行授权。正式K1、生产pool策略、最终B4自然场景8worker验收、逐run费用和42项正式运行仍未完成或未授权。历史证据保留，未启动正式P1-v2/P2/RL。
