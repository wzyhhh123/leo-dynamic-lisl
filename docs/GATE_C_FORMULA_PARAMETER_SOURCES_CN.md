# Gate C 公式、参数与来源台账

本文件将“文献支持的模型结构”“本研究的简化假设”和“仅用于验收的数值”分开。没有来源的数值不标为真实硬件参数。

## 1. 可追溯来源

| 条目 | 当前使用方式 | 来源 | 来源支持到什么程度 |
|---|---|---|---|
| SGP4/TLE | synthetic TLE 由 SGP4/WGS72 传播，原生状态采用 TEME-of-date | Vallado, Crawford, Hujsak, Kelso, *Revisiting Spacetrack Report #3*, AIAA 2006-6753, DOI `10.2514/6.2006-6753`; CCSDS 502.0-B-2 Orbit Data Messages | 支持 TLE/SGP4 技术链和 TEME 语义；不证明 synthetic TLE 等于真实星座轨道 |
| RTN 定义 | `R=r/|r|, N=(r×v)/|r×v|, T=N×R` | CCSDS 500.0-G-2, Sec. 4.3.6.4, Local Orbital Frame QSW/RTN；CCSDS 508.0 conjunction-data RTN 定义 | 支持坐标系公式、正交与右手关系 |
| 有限终端资源 | 一个激光终端同时只能建立一条物理链 | Wang et al., IEEE TCOM 2024, DOI `10.1109/TCOMM.2023.3347775`, system model | 支持 terminal-level occupancy；不直接支持本研究的 `2 fixed + 2 dynamic` 数量选择 |
| 动态终端 + 固定骨干 | 文献采用三固定一动态、T-shaped 骨干 | Wang et al., DOI `10.1109/TCOMM.2023.3347775`；Nie et al., DOI `10.1109/TVT.2026.3660872` | 是架构参考；当前研究的两固定两动态是独立合同，不能写成文献原方案 |
| 圆锥指向约束 | 使用夹角或 `cos ψ ≥ cos ρ` 判据 | Nie et al., *Dynamic Topology Control Strategy for LEO Mega-Constellation Networks*, IEEE TVT 2026, DOI `10.1109/TVT.2026.3660872`, link-establishment model | 支持以终端扫描半锥角筛候选；当前实现进一步要求双端同时通过 |
| 剩余持续时间 | 候选链需考虑可见持续时间 | Nie et al., DOI `10.1109/TVT.2026.3660872` | 支持把 duration/lifetime 纳入建链模型；本文的 ready/usable 分解是执行合同的进一步细化 |
| setup 不可忽略 | 动态 LISL 建立有指向、捕获、跟踪过程，setup delay 会影响路由和 outage | Bhattacharjee et al., IEEE TAES 2024, DOI `10.1109/TAES.2024.3415571` | 支持非零 setup 与延迟/中断机制；不提供本项目唯一的 retarget/acquisition 分解参数 |
| setup sensitivity 范围示例 | 文献比较 1、10、100、1000 ms setup delay，并讨论秒量级过程 | Bhattacharjee et al., DOI `10.1109/TAES.2024.3415571` | 只能作为后续 sensitivity 设计参考；当前 1 s + 1 s fixture 没有按该文校准 |

可核验链接：

- SGP4 论文：<https://celestrak.org/publications/AIAA/2006-6753/AIAA-2006-6753.pdf>
- CCSDS RTN：<https://ccsds.org/Pubs/500x0g2s.pdf>
- CCSDS Orbit Data Messages：<https://www.nasa.gov/wp-content/uploads/2023/09/ccsds-orbit-data-messages.pdf>
- Wang et al.：<https://doi.org/10.1109/TCOMM.2023.3347775>
- Nie et al.：<https://doi.org/10.1109/TVT.2026.3660872>
- Bhattacharjee et al.：<https://doi.org/10.1109/TAES.2024.3415571>

项目内三篇原始 PDF 位于 `D:/Document/leo_routing_attitude/参考文献/`。本轮曾在临时目录中只读转换论文以核对内容；提取完成后已清理临时副本，没有改动原始论文。

## 2. 模型推导与物理假设

### 2.1 双端 FoR

文献中的单终端圆锥判据应用到 physical link 两端，得到：

\[
F_{pair}=F_{local}\land F_{remote}.
\]

这是由“双边物理链必须在两端均能指向”得到的模型组合，不是声称上述文献已经实现了本项目相同的 terminal-pair 状态机。

### 2.2 ready time

\[
t_{ready}=\max(t^{free}_i+\tau_i,t^{free}_j+\tau_j)+\tau^{acq}_{ij}.
\]

该式依赖以下合同假设：两端 retarget 可以并行；acquisition 必须等待两端 retarget 完成；同一具体终端不能并行服务旧 peer 和重构到新 peer；DRAINING 必须等不可抢占 TX 完成。它是 Gate B 事件语义的推导式，不冒充硬件测量公式。

### 2.3 usable lifetime

\[
L_{remain}=t_{end}-t_{now},\qquad L_{usable}=t_{end}-t_{ready}.
\]

这是时间区间定义。Gate C 只检查 `L_usable > 0`；收益是否足以覆盖 setup 损失属于后续控制问题。

## 3. 未校准参数

| 参数 | v1 数值/状态 | 性质 | 可否用于真实性宣称 |
|---|---:|---|---|
| D1 mounting | `+N` | 简化研究假设 | 否 |
| D2 mounting | `-N` | 简化研究假设 | 否 |
| FoR half-angle | `90°` | sensitivity-only 默认配置 | 否 |
| FoR sensitivity | `60°/75°/90°` | 结构敏感性接口 | 否 |
| audit retarget | 两端各 `1 s` | synthetic fixture | 否 |
| audit acquisition | `1 s` | synthetic fixture | 否 |
| 5000 km | diagnostic candidate search cutoff | 几何搜索参数 | 否，不能称 LCT range |
| tracking rate | `not_explicitly_modeled_v1` | 明确延期 | 不适用 |
| tracking acceleration | `not_modeled_v1` | 明确延期 | 不适用 |
| lifetime epsilon | `1e-9 s` | 浮点数值裕量 | 不是物理参数 |
| boundary tolerance | `0.001 s` | 数值求根容差 | 不是物理参数 |

## 4. 不能从当前文献推出的内容

- 不能由 3-fixed+1-dynamic 文献推出当前 2-fixed+2-dynamic 的硬件可实现性。
- 不能由 `90°` sensitivity 配置推出实际终端扫描范围。
- 不能由 5000 km diagnostic cutoff 推出可靠通信量程。
- 不能由 setup sensitivity fixture 推出真实终端 acquisition time。
- 不能由 FoR 通过推出真实 tracking-rate、抖动、链路预算或误码性能。

这些项目保留为后续硬件校准或链路预算工作，不阻塞本轮网络层最小物理抽象。
