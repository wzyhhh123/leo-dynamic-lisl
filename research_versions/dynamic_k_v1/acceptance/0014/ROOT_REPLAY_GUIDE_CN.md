# N4-P0E：新独立根的完整可执行重放

场景ID：`P0E_0014_NEW_160_PERSIST_T3_SEED1414`。采用**明确绑定的可执行确定性重建方案**，不是native pickle，也不依赖把JSON摘要反序列化成猜测的对象。本方案不恢复或替换0011根。

## 已执行的恢复验收

ROOT_BASELINE从0推进至3秒；CLEAN_REBUILD在另一个干净Python进程从0重建。live、净化atomic及SanitizedRoot完整对象图均逐字段相同，原causal SHA、forecast SHA和历史前缀SHA一致，ROOT_RECONSTRUCTION_PASS。HOLD、ADD各自在独立进程重新验证相同源根后才执行。DURABLE_REPLAY_VERIFICATION另行验证了供封存后使用的持久入口，也全部严格一致。

新根causal SHA：`1a6a346c324c6a9d34721ba1d049ac4ea5de62036a62d1a89d17a02255cb5fb3`。

完整SanitizedRoot对象图SHA：`a36f45f5875ad4dc1323260d87a07654a369a7b618a6ad75ce436cf463a77cc3`。

净化atomic对象图SHA：`42f133cb5cbf54f785caa1dab9a68e8fdb118256ad80227c844a953981262149`。

## 重建材料及保证范围

- replay_recipe.json绑定1163个文件、59,123,937原始字节，包括源码、N1a/N1b/N2/N3/P0冻结依赖、0011原构造器、独立新worker/codec、160星固定几何、完整2742窗口输入、硬件配置、SGP4/TLE、Python解释器/DLL以及已捕获的Python和第三方运行依赖。每次重建原字节重新核验，不能使用不同输入代替。
- 进程局部PYTHONHASHSEED=1414，Python3.9.21，固定现有pytorch解释器。seed只为本新工程场景服务，不搜索原0011未知seed，不冻结论文随机种子。
- 完整执行原绑定构造器及0→3连续事件推进，恢复所有队列/在途/补偿累加器、调度/路由、terminal links/预约/agenda、FIFO/cohort及审计/游标、N1a驻留/历史，以及净化clone的forecast与历史前缀。
- full_state.py比较每个Python对象的类型、全部vars字段、可变对象别名、字典插入顺序、列表/tuple/heap与集合遍历布局、float.hex位级表示、Fraction分子分母、数组dtype/shape/strides/字节等。没有用原encode的JSON摘要冒充恢复协议。
- native SGP4对象由绑定TLE、二进制和完整确定性调用流程重新产生；所有暴露native字段也进入比对。隐蔽C内部字节不宣称已导出，也没有自制Satrec pickle。恢复能力来自执行重建配方，JSON图只是完整状态核对证据。此保证限于匹配绑定环境和通过严格状态核对的运行，不承诺任意平台可重放。
- independent_root_evidence_anchor.json独立哈希绑定所有基准状态/原文/日志；持久入口另外钉住该锚和recipe SHA。当前修订锚由调用者独立提供，必须验证完整版本父链，并仍匹配原0013锚。

## 封存后入口

使用 `acceptance/0014/replay_entry.py`，它只有只读恢复功能，没有预测/拓扑动作入口。示例在dynamic_lisl_v2目录执行：

```powershell
$env:PYTHONHASHSEED = '1414'
& 'D:/Program_Files/anaconda3/envs/pytorch/python.exe' -B research_versions/dynamic_k_v1/acceptance/0014/replay_entry.py --expected-revision-sha256 '<独立保存且可信的当前最新修订SHA-256>'
```

省略--output时不写项目文件，只输出严格比对结果；-B不生成字节码。最新独立修订SHA从本轮交付获取，不自引用写进被封存文档。需要新增持久证据时必须使用新的授权目录并登记下一修订。

原replay_worker.py是本轮顺序验收工具，父链固定在准备时的0013且输出目录采用排他创建，不用它覆盖或续跑已封存HOLD/ADD资产。持久入口保留原worker/recipe原字节，只独立处理“父链已前进”的验证生命周期：核验调用者新锚的整条链、原0013父锚、旧recipe/输入/基准文件，构造过程不变。

## 分清源根、clone与动作阶段

源根完整重建的主比较是严格逐字段相同，未忽略任何字段。原冻结deepcopy重建set/frozenset时会改变集合遍历布局，导致“源atomic图”和“branch clone图”完整SHA不同；这不是源根重建失败。两个分支的PRE_ACTION clone图逐字段完全相同，SHA均为 `f32c018dc5596429415d8420cc288b816eb45fabafffd6fd997f10b69cbdb92f`，causal SHA也与源根相同。

CLONE_SET_LAYOUT_AUDIT显式保留原始不相等事实；只在额外的离线比较中按数学集合语义核对，证明其余类型、值、顺序和对象别名一致。该辅助检查没有替换任何主SHA、排序回写实际状态或放宽原根恢复比较。PRE_ACTION、POST_ACTION、CHECKPOINT和STOP各有独立全状态/causal原文/摘要，不能把相同t=3的动作前后阶段混为一谈。

本轮只执行一个HOLD和一个ADD预测。进一步恢复只读源根不意味着获得继续预测的授权。
