# DEA 并行进化算法实现与实验分析

## 1. 作业背景与当前阶段目标

本作业要求基于老师提供的 TSP 串行进化算法，使用 MPI 进行并行化，并通过实验说明并行算法相对于原始串行版本能够得到更好的路径长度。当前阶段只整理已经完成并验证的最简单并行算法，即分布式进化算法 DEA，也可称为 island model 或 ring DEA。

本阶段不涉及普通 HDEA 和 moving colony HDEA 的实现。参考论文 `docs/hierarchical.pdf` 说明了简单 DEA、HDEA 以及 moving colony 全局迁移策略之间的关系：DEA 将单一种群划分为多个子种群，各子种群独立演化并周期性迁移个体；HDEA 在此基础上加入分组和局部/全局两级迁移；moving colony HDEA 则将全局迁移对象提升为子种群。本项目当前只完成 DEA 层次。

## 2. 原始串行算法概述

根据 `src/TSP0.C`、`src/tsp_serial_fixed.c` 和 `src/tsp_serial_exp.c`，串行算法的核心流程如下。

1. 读取 TSP 数据 `pcb442.tsp`。该数据第一行为城市数量 442，后续每行为城市编号和二维坐标。
2. 根据城市坐标构造 `city_dis[CITY][CITY]` 距离矩阵，距离使用欧氏距离并四舍五入为整数。
3. 初始化 `N_COLONY=100` 个随机路径个体，每个个体是 442 个城市的一个排列。
4. 计算每个个体的闭环路径长度，即从路径最后一个城市回到第一个城市。
5. 每代对每个个体复制出候选路径，并执行类似 inver-over 的路径片段反转操作。反转片段有时由随机选择城市触发，有时由另一个随机个体中的相邻关系决定。
6. 如果候选路径长度比原个体更短，则用候选路径替换原个体。
7. 每代更新当前最优路径长度 `sumbest`。

TSP 是最小化问题，因此路径长度越小表示解越好。`src/tsp_serial_fixed.c` 主要用于串行可运行性检查；`src/tsp_serial_exp.c` 在保留核心进化逻辑的基础上增加了固定随机种子和 CSV 输出，用于可复现实验。

## 3. DEA 算法设计

DEA 的核心思想是将原来单一的进化种群拆分为多个相对独立的子种群。每个 MPI rank 维护一个 island 或 subpopulation，独立执行串行进化逻辑。经过固定代数后，不同 island 之间通过迁移交换优良个体。

本项目采用 ring 拓扑：

```text
rank 0 -> rank 1 -> rank 2 -> rank 3 -> rank 0
```

一次迁移中，当前 rank 将本地最优个体发送给右邻居 `(rank + 1) % size`，同时从左邻居 `(rank - 1 + size) % size` 接收一个个体。接收个体替换本地最差个体，并重新计算该个体的路径长度。

这种设计的作用是：各子种群先保持相对独立以维持搜索多样性，再通过周期性迁移传播较优路径结构，从而在独立探索和信息共享之间取得平衡。

## 4. MPI 并行实现细节

MPI DEA 实现在 `src/tsp_mpi_dea.c` 中。主要结构如下。

- 使用 `MPI_Init` 初始化 MPI 环境。
- 使用 `MPI_Comm_rank` 获取当前 rank，使用 `MPI_Comm_size` 获取总进程数。
- 每个 rank 独立读取 `data/pcb442.tsp`，并各自构造距离矩阵。
- 随机种子采用：

```c
rankSeed = baseSeed + rank * 10007
```

- 每个 rank 本地保留 `N_COLONY=100` 个体，不在 DEA 阶段固定全局总种群规模。
- 每个 rank 独立执行与串行版本一致的 `invert`、`select1` 和路径长度计算逻辑。
- 每隔 `migration_interval` 代执行一次 ring migration。
- 迁移使用 `MPI_Sendrecv`，同时发送和接收，避免环形通信中的死锁。
- 迁移后调用 `compute_path_length` 重新计算移入个体的路径长度，并调用 `update_best_worst` 更新本地最优和最差个体。
- 结束后使用 `MPI_Gather` 将各 rank 的本地最优值汇总到 rank 0。
- 使用 `MPI_Reduce(... MPI_MAX ...)` 汇总并行运行时间，取最慢 rank 的时间作为并行 elapsed time。
- rank 0 负责向 CSV 追加写入实验结果。

核心伪代码如下：

```text
MPI_Init
rankSeed = baseSeed + rank * 10007
每个 rank 读取 TSP 数据并初始化本地 100 个体种群

for generation in 1..maxGen:
    每个 rank 独立执行一代串行进化逻辑
    if generation % migration_interval == 0:
        send 本地最优个体 to 右邻居
        receive 个体 from 左邻居
        用接收个体替换本地最差个体
        重新计算该个体路径长度

rank 0 汇总所有 rank 的 local best
rank 0 输出 global best 和 elapsed time
MPI_Finalize
```

## 5. 实验设置

实验自动化脚本为 `scripts/run_experiments.ps1`，统计分析脚本为 `scripts/analyze_results.py`。

正式实验设置如下。

- 数据集：`data/pcb442.tsp`
- 算法组：
  - `SERIAL n=1`
  - `DEA n=2`
  - `DEA n=4`
- `maxGen = 1000`
- `migration_interval = 100`
- 每组运行 10 次
- seeds：

```text
12345, 22345, 32345, 42345, 52345, 62345, 72345, 82345, 92345, 102345
```

- 实验输出：`results/experiment_results.csv`
- 统计摘要：`results/analysis_summary.txt`
- 统计脚本：`scripts/analyze_results.py`

`scripts/run_experiments.ps1` 会编译 `src/tsp_serial_exp.c` 和 `src/tsp_mpi_dea.c`，然后按上述 seeds 运行三组算法，并将所有结果统一写入 `results/experiment_results.csv`。

## 6. 实验结果

以下结果来自 `results/analysis_summary.txt`。TSP 是最小化问题，因此 `best` 和 `mean` 越小越好。

| algorithm | nproc | count | best | mean | std | avg_time |
| --------- | ----: | ----: | ---: | ---: | --: | -------: |
| DEA | 2 | 10 | 415765 | 430223.600 | 6134.273 | 3.484536 |
| DEA | 4 | 10 | 424318 | 430458.000 | 3508.236 | 3.628990 |
| SERIAL | 1 | 10 | 430142 | 438472.100 | 4628.069 | 3.314700 |

从平均路径长度看，DEA n=2 和 DEA n=4 均低于 SERIAL n=1。单次最优值方面，DEA n=2 的最好结果为 415765，也低于串行组的最好结果 430142。

## 7. Welch t-test 显著性检验

Welch t-test 用于比较两组算法的平均路径长度是否存在显著差异。原假设是两组均值没有显著差异。本实验使用双侧检验，若 `p-value < 0.05`，则认为在 95% 置信水平下差异显著。

以下结果来自 `results/analysis_summary.txt`。

| comparison | p-value | conclusion |
| ---------- | ------: | ---------- |
| SERIAL n=1 vs DEA n=2 | 0.003512 | DEA n=2 显著优于 SERIAL |
| SERIAL n=1 vs DEA n=4 | 0.000435 | DEA n=4 显著优于 SERIAL |
| DEA n=2 vs DEA n=4 | 0.917916 | DEA n=2 与 DEA n=4 之间无显著差异 |

因此，在当前实验设置下，DEA n=2 和 DEA n=4 相对于串行版本均表现出统计显著的更低平均路径长度。但 DEA n=2 与 DEA n=4 之间的均值差异不能认为显著。

## 8. 为什么 DEA 结果更好

DEA 的改进不是单纯来自“并行执行”，而是来自并行种群结构和迁移机制。

1. 多个子种群并行搜索，扩大了搜索覆盖范围。
2. 不同 rank 使用不同随机种子，使初始种群和后续搜索轨迹具有更高多样性。
3. ring migration 会将本地较优路径传播到邻近子种群，使较优结构能够被其他 island 继续利用。
4. 子种群之间保持半隔离状态，不会每代完全混合，因此可以减缓所有个体快速趋同到同一局部结构的风险。
5. 周期性迁移在独立探索和信息共享之间取得平衡。
6. 因此，在当前参数下，DEA 更容易找到比单一种群串行算法更短的路径。

参考论文也指出，DEA 通过多个子种群独立进化和间隔迁移，可以维持子种群差异并为其他子种群提供新的 building blocks，从而延缓进化停滞。本项目的 ring DEA 实验结果与这一机制解释一致。

## 9. 公平性说明与局限性

当前实验必须明确一个公平性边界：`src/tsp_mpi_dea.c` 中每个 rank 都保留 `N_COLONY=100` 个体。因此不同算法组的总个体数不同。

```text
SERIAL: 总个体数 100
DEA n=2: 总个体数 200
DEA n=4: 总个体数 400
```

所以，当前实验可以证明：使用 MPI 分布式进化算法后，在更多并行子种群和 ring migration 机制帮助下，结果优于原始串行版本。

但如果要求严格固定总计算预算，还需要补充更公平的对照实验，例如：

1. SERIAL 使用 400 个体 vs DEA n=4 每个 rank 100 个体；
2. SERIAL 使用 100 个体 vs DEA n=4 每个 rank 25 个体；
3. 固定总评价次数 function evaluations，而不是只固定 `maxGen`。

因此，本阶段结论适用于“并行分布式扩展后结果更好”的最低作业要求，但不应被表述为在严格相同计算预算下 DEA 一定优于串行算法。

## 10. 可复现运行方式

以下命令均从项目根目录运行。

串行实验版本编译：

```powershell
gcc -std=c11 -Wall -Wextra -O2 .\src\tsp_serial_exp.c -lm -o .\bin\tsp_serial_exp.exe
```

MPI DEA 编译。当前环境没有 `mpicc`，实际使用 MS-MPI SDK 和 MinGW gcc：

```powershell
$msmpiInc = $env:MSMPI_INC.TrimEnd('\')
$msmpiLibDir = $env:MSMPI_LIB64.TrimEnd('\')
gcc -std=c11 -Wall -Wextra -O2 "-I$msmpiInc" .\src\tsp_mpi_dea.c "-L$msmpiLibDir" -lmsmpi -lm -o .\bin\tsp_mpi_dea.exe
```

运行完整 10 次实验：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_experiments.ps1
```

运行统计分析：

```powershell
python .\scripts\analyze_results.py
```

单次运行示例：

```powershell
.\bin\tsp_serial_exp.exe .\data\pcb442.tsp 1000 12345 .\results\experiment_results.csv
mpiexec -n 2 .\bin\tsp_mpi_dea.exe .\data\pcb442.tsp 1000 100 12345 .\results\experiment_results.csv
mpiexec -n 4 .\bin\tsp_mpi_dea.exe .\data\pcb442.tsp 1000 100 12345 .\results\experiment_results.csv
```

## 11. 本阶段结论

本阶段已经完成最简单的 MPI 分布式进化算法 DEA，并完成 SERIAL、DEA n=2 和 DEA n=4 三组算法各 10 次独立运行。实验结果显示，DEA n=2 和 DEA n=4 的平均路径长度均低于串行版本，Welch t-test 结果表明这两组 DEA 相对于串行版本的差异均具有统计显著性。

因此，当前结果已经可以支撑最低要求：实现最简单并行算法，并用实验证明并行化后的结果相比原始串行版本更好。后续可在该 DEA 基线基础上继续实现普通 HDEA 和 moving colony HDEA，作为更高分目标的扩展。
