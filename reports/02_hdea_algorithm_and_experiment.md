# HDEA 分层分布式进化算法实现与实验分析

## 1. 当前阶段目标

本阶段在已完成 DEA 的基础上实现普通 HDEA，并将 SERIAL、DEA、HDEA 放入统一实验流程中进行对比。实验目标是对每组算法使用相同的 10 个随机种子，统计最优值、平均值、标准差和运行时间，并使用 Welch t-test 判断不同算法之间的结果差异是否显著。

本阶段只实现普通 HDEA。全局迁移的对象仍然是单个个体，不是整个子种群，因此还没有实现 moving colony HDEA。

## 2. DEA 到 HDEA 的扩展思路

DEA 中所有 MPI rank 构成一个全局 ring，每个 rank 维护一个本地子种群并独立进化，周期性把本地最优个体迁移给下一个 rank。

HDEA 在 DEA 的基础上加入 group 层级。所有 rank 先划分为多个 group，组内较频繁执行 local migration，组间较低频执行 global migration。这样做的目的是让同一 group 内的信息共享更充分，同时让不同 group 保持一定隔离，降低所有子种群过快同质化的风险。

本实现中的 HDEA 是普通 individual HDEA：global migration 仍然迁移单个最优个体，不迁移整个子种群，也不改变子种群所在 group 的映射关系。

## 3. HDEA 算法设计

rank 到 group 的映射方式为：

```text
subpops_per_group = nproc / num_groups
group_id = rank / subpops_per_group
local_id = rank % subpops_per_group
```

local migration 在同一 group 内使用 ring 拓扑：

```text
local_send_to = group_id * subpops_per_group + (local_id + 1) % subpops_per_group
local_recv_from = group_id * subpops_per_group + (local_id - 1 + subpops_per_group) % subpops_per_group
```

迁移过程为：当前 rank 发送本地最优个体，从左邻居接收一个个体，用接收个体替换本地最差个体，然后重新计算该个体路径长度。

global migration 在不同 group 之间使用 ring 拓扑，相同 `local_id` 的 rank 之间进行迁移：

```text
global_send_group = (group_id + 1) % num_groups
global_recv_group = (group_id - 1 + num_groups) % num_groups
global_send_to = global_send_group * subpops_per_group + local_id
global_recv_from = global_recv_group * subpops_per_group + local_id
```

本阶段设置为每隔 `local_migration_interval=100` 代执行一次 local migration，每执行 `local_to_global_ratio=5` 次 local migration 后，再执行一次 global migration。

## 4. MPI 实现细节

HDEA 源码位于 `src/tsp_mpi_hdea.c`。程序支持命令行参数指定输入文件、`maxGen`、local migration 间隔、local-to-global 比例、group 数量、随机种子和输出 CSV 文件。

实现中的关键点如下：

- 参数合法性检查要求至少 4 个 MPI rank，`num_groups >= 2`，`nproc` 能被 `num_groups` 整除，并且每个 group 至少 2 个 rank。
- 每个 rank 独立读取 `pcb442.tsp`，独立初始化距离矩阵和本地 `N_COLONY=100` 的子种群。
- 随机种子沿用 DEA 设计：`rankSeed = baseSeed + rank * 10007`。
- local migration 和 global migration 都使用 `MPI_Sendrecv`，避免 ring 拓扑中的死锁。
- 每次迁移发送本地最优个体，接收个体替换本地最差个体。
- 程序结束时，rank 0 通过 MPI 汇总所有 rank 的 local best，得到 global best。
- elapsed time 使用 `MPI_Reduce(..., MPI_MAX, ...)` 取最慢 rank 的运行时间。
- rank 0 使用追加模式写 CSV。

## 5. 实验设置

数据集为 `data/pcb442.tsp`。所有算法统一使用：

- `maxGen = 1000`
- 10 个随机种子：`12345, 22345, 32345, 42345, 52345, 62345, 72345, 82345, 92345, 102345`
- 结果文件：`results/all_experiment_results.csv`
- 分析文件：`results/all_analysis_summary.txt`

对比算法如下：

| algorithm | nproc | migration_interval | local_to_global_ratio | num_groups |
|---|---:|---:|---:|---:|
| SERIAL | 1 | 0 | 0 | 0 |
| DEA | 2 | 100 | 0 | 0 |
| DEA | 4 | 100 | 0 | 0 |
| HDEA | 4 | 100 | 5 | 2 |
| HDEA | 6 | 100 | 5 | 3 |

## 6. 实验结果

以下统计结果来自 `results/all_analysis_summary.txt`。TSP 是最小化问题，`global_best` 越小越好。

| algorithm | nproc | groups | ratio | count | best | mean | std | avg_time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SERIAL | 1 | 0 | 0 | 10 | 430142 | 438472.100 | 4628.069 | 2.613500 |
| DEA | 2 | 0 | 0 | 10 | 415765 | 430223.600 | 6134.273 | 2.701971 |
| DEA | 4 | 0 | 0 | 10 | 424318 | 430458.000 | 3508.236 | 2.774825 |
| HDEA | 4 | 2 | 5 | 10 | 426732 | 431573.700 | 4266.830 | 3.457383 |
| HDEA | 6 | 3 | 5 | 10 | 426245 | 430320.900 | 2496.949 | 3.458822 |

从平均值看，当前 10 次实验中 `DEA n=2` 的 mean 最小，为 `430223.600`；单次最优值也来自 `DEA n=2`，为 `415765`。HDEA 两组都明显优于 SERIAL，但没有超过所有 DEA 配置。

## 7. Welch t-test 显著性检验

以下 t-test 结果来自 `results/all_analysis_summary.txt`。检验为双侧 Welch t-test，显著性水平取 `0.05`。

| comparison | mean_left | mean_right | p-value | better | significant |
|---|---:|---:|---:|---|---|
| SERIAL n=1 vs DEA n=2 | 438472.100 | 430223.600 | 0.003512 | DEA n=2 | yes |
| SERIAL n=1 vs DEA n=4 | 438472.100 | 430458.000 | 0.000435 | DEA n=4 | yes |
| SERIAL n=1 vs HDEA n=4 groups=2 | 438472.100 | 431573.700 | 0.002782 | HDEA n=4 groups=2 | yes |
| SERIAL n=1 vs HDEA n=6 groups=3 | 438472.100 | 430320.900 | 0.000242 | HDEA n=6 groups=3 | yes |
| DEA n=4 vs HDEA n=4 groups=2 | 430458.000 | 431573.700 | 0.531355 | DEA n=4 | no |
| DEA n=4 vs HDEA n=6 groups=3 | 430458.000 | 430320.900 | 0.921034 | HDEA n=6 groups=3 | no |
| HDEA n=4 groups=2 vs HDEA n=6 groups=3 | 431573.700 | 430320.900 | 0.435846 | HDEA n=6 groups=3 | no |

HDEA 两组相对 SERIAL 都达到显著差异，说明当前普通 HDEA 实现相对于串行基线有显著改进。

HDEA 相对 DEA 的结论要更谨慎。`HDEA n=4 groups=2` 的均值高于 `DEA n=4`，且差异不显著。`HDEA n=6 groups=3` 的均值略低于 `DEA n=4`，但 p-value 为 `0.921034`，远大于 `0.05`，不能说明 HDEA 显著优于 DEA。

## 8. HDEA 与 DEA 的结果比较

在当前参数下，HDEA 没有显著优于 DEA。

`HDEA n=4 groups=2` 和 `DEA n=4` 的总子种群数量相同，都是 4 个 rank，每个 rank 一个 `N_COLONY=100` 的子种群。这个比较相对更公平。结果显示 `DEA n=4` 的 mean 为 `430458.000`，`HDEA n=4 groups=2` 的 mean 为 `431573.700`，DEA 均值略好，但 p-value 为 `0.531355`，差异不显著。

`HDEA n=6 groups=3` 的 mean 为 `430320.900`，略优于 `DEA n=4` 的 `430458.000`，但 p-value 为 `0.921034`，差异不显著。同时，HDEA n=6 使用了 6 个 rank，总个体数更大，因此不能把这个结果直接解释为 HDEA 机制本身优于 DEA。

## 9. 为什么 HDEA 可能更好

从机制上看，HDEA 的潜在优势来自层次化迁移结构。

首先，组内 local migration 较频繁，可以让同一 group 内的优秀个体较快传播，增强局部开发能力。其次，组间 global migration 频率较低，可以减少不同 group 之间过快同质化，保留更强的全局探索能力。第三，半隔离的 group 结构可以减缓早熟收敛，使不同组在一段时间内保留不同搜索方向。

不过，本实验只能说明 HDEA 相对 SERIAL 显著更好。相对 DEA，当前结果没有显著优势。因此更准确的表述是：HDEA 机制上可能在更难问题、更长运行代数或更合适迁移参数下表现出优势，但本阶段实验还不能证明 HDEA 显著优于 DEA。

## 10. 公平性说明与局限性

当前所有并行算法每个 rank 都保留 `N_COLONY=100`，因此不同算法组的总个体数不同：

```text
SERIAL n=1: 总个体数 100
DEA n=2: 总个体数 200
DEA n=4: 总个体数 400
HDEA n=4: 总个体数 400
HDEA n=6: 总个体数 600
```

因此，HDEA n=6 的计算规模比 DEA n=4 和 HDEA n=4 更大，不能简单作为完全公平比较。当前结果适合证明并行化后相对于串行基线有改善，也适合比较不同并行结构的初步趋势，但不能作为严格相同计算预算下的最终结论。

如果要做更严格公平的实验，后续应增加以下设计之一：

- 固定所有算法的总种群规模；
- 固定总函数评价次数；
- 或让串行版本使用与并行算法相同的总个体数。

## 11. 可复现运行方式

完整实验运行方式：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_experiments_all.ps1
python .\scripts\analyze_results_all.py .\results\all_experiment_results.csv
```

单次 HDEA 运行方式：

```powershell
mpiexec -n 4 bin\tsp_mpi_hdea.exe data\pcb442.tsp 1000 100 5 2 12345 results\temp_hdea.csv
mpiexec -n 6 bin\tsp_mpi_hdea.exe data\pcb442.tsp 1000 100 5 3 12345 results\temp_hdea.csv
```

统一实验脚本会自动编译 `src/tsp_serial_exp.c`、`src/tsp_mpi_dea.c` 和 `src/tsp_mpi_hdea.c`，并将每次运行结果标准化追加到 `results/all_experiment_results.csv`。

## 12. 本阶段结论

本阶段已经完成普通 HDEA 的正式实验集成，生成了包含 SERIAL、DEA、HDEA 的统一 50 行实验结果，并完成统计分析和 Welch t-test。

实验结果表明，HDEA n=4 和 HDEA n=6 相对 SERIAL 都显著更好，说明分层分布式进化算法可以作为串行基线之外的有效并行扩展。但在当前参数下，HDEA 尚未显著优于 DEA。`HDEA n=6` 的均值略好于 `DEA n=4`，但差异不显著，并且总种群规模更大，需要谨慎解释。

下一步可以在普通 HDEA 的基础上实现 moving colony HDEA，并将其加入统一实验流程，与现有 SERIAL、DEA、HDEA 结果继续对比。
