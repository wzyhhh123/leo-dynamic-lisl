# 动态 K v1 独立版本记录

当前仅实施 N0a/N0b：文件级基线、版本骨架和完整性验收。
合同/配置仍 DRAFT；未修改生产代码，未运行仿真、训练或性能实验。

## 文件与信任入口

- `baselines/<UTC 时间戳>/files.json`：创建新资产前的全部研究文件原始字节 SHA-256 和大小。
- 同目录 `exclusions.json`：缓存、IDE、虚拟环境、字节码和锁文件的逐文件排除原因；outputs/tmp 研究证据不因 gitignore 排除。
- `record.json`：两轮采集核对、UTC/北京时间、Git 状态（当前无 HEAD）和旧冻结记录引用。
- `seal.json`：绑定前三个文件的哈希，不包含自哈希。
- `version_record.json`：绑定 baseline seal、首份修订、初始合同与配置。
- `revisions/0001/record.json`：本次授权、原因、完整新增文件列表及合同/配置绑定；不把自身哈希递归写入自身。
- `acceptance/0001/`：仅 N0 完整性控制测试的原始输出和执行记录。

必须在仓库外独立保留交付时的 **version_record.json SHA-256 与最新 revision record SHA-256**。
只读取目录中可一起被改写的清单与 seal，不能认证原始基线；历史末尾修订被删除也需由独立保存的最新修订哈希发现。
哈希不证明人工授权真实性、科学正确性或 Gate PASS，也不提供文件恢复备份。

## 只读验证

使用既有 Conda pytorch，参数中的哈希应来自独立保存的交付记录，不从待验证文件现场计算后当作可信输入。

```powershell
& 'D:/Program_Files/anaconda3/envs/pytorch/python.exe' -B research_versions/dynamic_k_v1/tools/version_control.py verify --expected-version-sha256 <独立保存的版本记录SHA256> --expected-revision-sha256 <独立保存的最新修订SHA256>
```

运行位置为 dynamic_lisl_v2；也可传 `--project-root`。验证不写报告或修改文件。
验证清单/seal/版本记录/修订父链、合同配置绑定、全部现存文件集合与哈希。
未登记新增、删除、内容/换行修改均失败；内容相同的删除/新增另列 POSSIBLE_RENAME，不把重复内容猜成唯一重命名。
读取失败、路径越界、符号链接/重解析点、重复 JSON key、扫描期间变化均拒绝。

## 后续修订

不得覆盖现存基线、版本起点或历史修订。下一修订使用连续编号目录和全新的 record.json，父记录绑定上一编号的路径/大小/哈希。
修订结构沿用 0001，逐文件列 added、modified（before/after）、deleted（before），并记录明确的人类授权、原因与当前合同/配置哈希。
新版本资产可按登记修订变化；旧路径默认受保护，仅 src/、tools/ 的明确登记实现变更可接受。旧测试、Gate 合同/manifest、历史输出和数据不可改写。
在修改前独立保存父版本/修订哈希；修改后登记并封存新的修订记录，再验证并独立保存其哈希。仅写一段变更说明不满足登记要求。
若需新的授权范围，应另立版本/保护合同，不通过篡改旧基线排除规则放行。

## 后续实验绑定

`experiments/record_template.json` 只是拒绝执行的空模板，不是实验结果。
每个正式实验必须绑定具体 revision record、baseline seal、合同、配置，以及由冻结配置登记的完整源码/输入/验收文件 manifest。
`verify-experiment --record <相对路径> --expected-experiment-sha256 <外部保存的哈希>` 同时要求上述两个版本哈希。
该入口只核对绑定、参数冻结及授权记录，**不运行实验**；后续 N5 运行入口还必须集成完整项目验证、科学验收和真正的人类运行授权，不能将哈希验证 PASS 视为运行授权。
T_A/T 等未决值不得沿用旧 240/600；DRAINING 的能耗映射已确定，K 的统计约定尚未冻结。
