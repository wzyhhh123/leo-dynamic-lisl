仿真平台提供三大接口，支持导入自定义的卫星网络拓扑，卫星实际流量数据，卫星流量预测数据。文件名与其简介对照表如下，表格后将简要介绍各个接口的运行流程。

|  |  |
| --- | --- |
| **文件名（gensat文件夹下）** | **简介** |
| gen432sat1.py | 用于在STK中构建星座 |
| STK.txt | 用于在MATLAB中批量导出STK中的TLE数据 |
| generate\_graph432final.py | 用于将TLE数据转换为拓扑图 |
| stkinitial.py | 用于STK与Python联调的初始化 |
| graph\_data432final | generate\_graph432final.py生成的拓扑图 |
| KnowledgeMap.py | 基于拓扑图和流量值，调用neo4j来构建知识图谱 |
| sat432 | gen432sat1.py创建的星座 |
| TLEData\_432.tle | STK.txt导出的tle数据 |
| **文件名（gentraffic文件夹下）** | **简介** |
| 432sat\_sawable | 910个星地可见性csv文件 |
| 432Sat\_gnd\_visibility.py | 用于星地可见性预测 |
| satellite\_traffic\_original.csv | 原始卫星流量数据 |
| satellite\_traffic\_predicted.csv | 预测的卫星流量数据 |
| converted\_traffic.csv | 转换后的原始卫星流量数据 |
| converted\_traffic\_0.25.csv | 转后后并抽样的原始卫星流量数据 |
| converted\_traffic\_predicted.csv | 转换后的预测卫星流量数据 |
| converted\_traffic\_predicted\_0.25.csv | 转后后并抽样的预测卫星流量数据 |
| GroundSat\_TrafficMatch.py | 用于星地流量映射 |
| GroundTraffic\_predict.py | 用于地面站流量预测 |
| predicted\_traffic\_lstm\_full.csv | 预测得到的地面站交互流量数据 |
| structured\_traffic\_data.csv | 历史地面站交互流量 |
| trafficchoose.py | 用于抽样卫星流量数据 |
| trafficturn.py | 用于抓换卫星流量数据 |
| Passive\_Measurement.py | 被动测量统计卫星流量数据 |
| Active\_Measurement.py | 主动动测量统计卫星流量数据 |
| 地面站.csv | 地面站位置信息 |
| **文件名（simulation文件夹下）** | **简介** |
| 432\_dijktest\_pre.py | 用于实现并测试Dijkstra算法 |
| 432\_kddqntest\_pre\_kg.py | 用于测试KD-DQN算法 |
| 432dqn\_pre\_kg.py | 用于训练KD-DQN算法 |
| dqn\_model.pth | 训练完成的KD-DQN算法的权重 |
| test\_knowledge\_per\_double\_dqn\_pre\_kg.log | KD-DQN算法的测试结果 |
| traffic\_gen1.py | 用于将包含流量数据的csv文件转换为仿真平台中的具体业务 |
| traffic\_load\_evaluator.py | 用于根据预测流量添加先验知识 |
| visual5.py | 用于实现结果可视化 |

一：虚拟环境安装与激活，python脚本运行教学。

步骤1：虚拟环境安装

把名为route1的压缩包拖到anaconda3文件夹下的envs文件夹内，解压即可。

步骤2：虚拟环境查看与激活

打开命令行后，使用conda env list命令可以查看存在的虚拟环境。

使用conda activate route1命令可以激活route1虚拟环境，使用conda deactivate可以退出该环境。

接下来运行的代码均在虚拟环境route1中运行，运行前需要激活该环境。

步骤3：切换目录

激活虚拟环境后，使用cd命令可以切换到指定的目录下。例如：想要切换到a/b/c文件夹下，则使用命令cd a/b/c。

步骤4：运行脚本

当切换到脚本所在目录下后，假设脚本名为jiaoben1.py，则使用命令python jiaoben1.py即可运行对应脚本。

二：自定义卫星网络流程

步骤1：自定义星座生成

在STK中生成任意的星座，示例中生成的星座参数如下：24\*18的Walker-Delta星座构型，相位因子F=7，轨道高度为1150km。运行gensat文件夹下名为名为gen432sat1.py的脚本将自动在STK中构建上述星座。

步骤2：TLE数据批量导出

打开Matlab，将gensat文件夹下名为STK.txt的文件里的命令复制进Matlab的命令行，能够实现卫星星座的TLE数据的批量化自动导出。

步骤3：TLE数据转换为拓扑图

运行gensat文件下名为generate\_graph432final.py的文件，将自动实现从TLE数据转为为拓扑图。

步骤4：知识图谱生成

运行gensat文件下名为KnowledgeMap.py的文件，可将上一步生成的拓扑图与satellite\_traffic\_original.csv原始卫星流量数据，共同在neo4j中构建为知识图谱。（需安装neo4j图谱绘制工具，终端输入neo4j console激活neo4j后才可运行脚本进行绘制，并且在浏览器输入终端生成的访问地址，即可进入图谱绘制UI界面，neo4j初次进入的账号密码都为neo4j，见下图）

![文本  AI 生成的内容可能不正确。](data:image/png;base64...)

三：自定义卫星流量数据流程

步骤1：星地可见性分析

启动STK仿真，基于432Sat\_gnd\_visibility.py脚本计算每个地面站在哪些时间区间能被哪颗卫星覆盖接入的信息。

步骤2：星地流量映射

通过GroundSat\_TrafficMatch.py将历史的地面站交互流量数据（structured\_traffic\_data.csv）映射为历史卫星流量数据（satellite\_traffic\_original.csv）。

步骤3：数据抽样

如果流量数据过多或者需要筛选，我们在gentraffic文件夹下提供了名为trafficchoose.py的脚本进行抽样。

步骤4：数据转换

数据转换的内容是源目的节点的编号，在仿真系统中的卫星命名为LEOXXXXX,例如如果只有432颗星，范围是LEO10000-LEO10431。

步骤5：业务生成

这一步不需要手动运行脚本，负责将csv文件转换为业务的脚本在simulation文件夹下，名为trafficgen1.py。

步骤6：流量测量

通过gentraffic文件夹下的Passive\_Measurement.py和Active\_Measurement.py脚本，分别实现卫星流量的无干扰统计与链路性能的主动探测，输出流量分布、链路时延、连通性等核心测量指标的统计文件。

四：自定义卫星预测流量数据流程

步骤1：地面流量交互值预测

通过GroundTraffic\_predict.py基于LSTM对历史地面站交互流量进行预测。

步骤2：星地可见性分析

启动STK仿真，基于432Sat\_gnd\_visibility.py脚本计算每个地面站在哪些时间区间能被哪颗卫星覆盖接入的信息。

步骤3：星地流量映射

通过GroundSat\_TrafficMatch.py将预测的地面站交互流量数据（predicted\_traffic\_lstm\_full.csv）映射为预测的卫星流量数据。

步骤4：知识嵌入

知识嵌入的不需要手动运行脚本，负责将csv文件转换为嵌入知识的脚本在simulation文件夹下，名为traffic\_load\_evaluator.py。

四：训练

如果引入了自定义的星座与数据，需要重新训练，训练的脚本在simulation文件下名为432dqn\_pre\_kg.py。

五：仿真运行

仿真的主要内容在simulation文件夹下，名为432\_kddqntest\_pre\_kg，可直接运行。