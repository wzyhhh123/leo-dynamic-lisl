# 报告生成入口的编码问题

直接调用原 write_report.py 时，当前 Python CLI 报告 line 25 的 Non-UTF-8 SyntaxError。随后检查确认该文件 SHA-256 仍为实现 manifest 已绑定的 cd6e5c63d65665c934786ab46d29f7f844d311aff49938513f198210c5b717bf，全部字节可严格 UTF-8 解码，tokenize.detect_encoding 为 utf-8，AST 和显式 Unicode compile 均通过。未修改该已绑定文件或任何验收实现。

新增 execute_utf8_bound_helper.py 在执行前完整验证独立 SHA-256 固定的 N3 实现 manifest，然后严格 UTF-8 解码、编译并执行其原始报告/封存辅助源码。没有更换源码字节或放宽版本校验。封存辅助源码中的完整原始字节扫描、独立起点/父修订验证和新增清单检查仍按原逻辑执行。

此问题属于辅助脚本直接启动入口，不涉及已经通过的 N3/N1a/N1b/N2 工程执行与测试。旧原始资产、历史证据和修订仍受完整版本保护。
