# F3-v2 K0独立单点复核工程范围

新增`k0_independent_review.py`，工程验收入口`python tools/check_f3_v2_k0_independent_review.py`。固定8节点，K4/t=0/30/570及K16/t0匹配上界不可行点。无traffic、queue、controller或J输入，不选择K*，不修改K0-v1.1草案。

复核首先校验磁盘支持内容一致性，再将节点、固定边、plane mapping、setup和input hashes与外部调用上下文逐项绑定。用原Gate C catalogue和physical evaluator重新扫描所有idle terminal-pair，比较ready、window end、right-censor及600内截断usable lifetime。然后重建原Gate B预建立状态，从old binding×全部window独立枚举REPLACE，通过原BatchPhysicalValidator核验并重算canonical ID/order、stratum、拒绝原因和完整库存。

独立穷举不调用producer、candidate source、matching solver或topology builder来证明其结果。matching穷举只约束terminal degree，允许同卫星对不同终端的matching relaxation；topology穷举另禁止并行卫星对。两者不可混淆。lex目标独立按plane端点range、plane-pair覆盖、总截断寿命、最小截断寿命、canonical binding五级顺序，以精确Fraction解释float，不量化、不调整tie。8-edge fixture独立matching枚举255个非空subset，K4 topology枚举70个subset；Gate C/REPLACE共36次物理验证。

调用方必须提供physical/subset/wall预算。穷举未完成即UNKNOWN，不拿incumbent或已有matching证明代替完整topology证明。任何catalogue/上下文/库存/最优解不一致为FAIL_STOP。单次原Gate C调用和内容loader的matching重算不能靠软wall tick中断；大规模使用必须置于已实现的独立进程总超时边界内，不能宣称本helper提供硬实时中断。

PASS只适用于提供的单点物理catalogue和穷举完成范围。它不证明原SGP4/FoR窗口生成正确、不批准输入asset hash链、不独立核验所有batch diagnostics、不证明自然160星全K×20。自然输入必须另由已获批合同/manifest/hash链绑定；大规模穷举可能返回UNKNOWN，不能为了速度放宽证明条件。

科学与工程状态分开：Gate_K0_PASS=false，K_star_selected=false，full_natural_K0_executed=false。独立tiny证明的实际报告、源码hash、负对照及完整回归证据在新增attempt内保留。
