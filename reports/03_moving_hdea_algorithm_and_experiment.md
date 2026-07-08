# Moving Colony HDEA 算法实现与实验分析

## 1. 当前阶段目标

本阶段在普通 HDEA 的基础上实现论文中的 ring global migration with moving colony，并将 MOVING_HDEA 加入统一正式实验流程。实验对 SERIAL、DEA、HDEA 和 MOVING_HDEA 使用同一组 10 个随机种子，统计 best、mean、std 和 avg_time，并使用 Welch t-test 分析差异是否显著。

本阶段只完成 MOVING_HDEA 的正式实验和阶段文档整理，不写最终总报告。

## 2. 从普通 HDEA 到 Moving Colony HDEA

普通 HDEA 的 global migration 迁移对象是单个个体。每次 global migration 时，一个 rank 将本地最优个体发送到另一个 group 中的 rank，并用接收个体替换本地最差个体。

Moving Colony HDEA 的 global migration 不迁移个体，也不复制或发送整个种群数组。它移动的是“子种群在逻辑 group 中的归属关系”。物理 rank 和本地子种群都留在原进程中，改变的是后续 local migration 采用的逻辑分组关系。

这样做的效果是：一个子种群在 global moving colony 后进入新的逻辑 group，并在后续 local migration 中持续与新 group 内的其他子种群交换个体，从而让整个子种群携带的搜索结构参与新 group 的局部交流。

## 3. Moving Colony HDEA 算法设计

MOVING_HDEA 维护逻辑分组映射：

```c
group_members[g][i] = 当前逻辑 group g 的第 i 个位置由哪个 rank 的子种群担任
```

初始化时：

```text
group_members[g][i] = g * subpops_per_group + i
```

ring moving colony 每次只对一个 `moving_position` 做环形轮转：

```text
tmp = group_members[num_groups - 1][moving_position]
group_members[g][moving_position] = group_members[g - 1][moving_position]
group_members[0][moving_position] = tmp
moving_position = (moving_position + 1) % subpops_per_group
```

因此 global moving colony 本身没有个体通信，后续 local migration 根据新的 `group_members` 重新确定通信对象。

## 4. MPI 实现细节

实现文件为 `src/tsp_mpi_moving_hdea.c`。主要实现点如下：

- 命令行参数包括输入 TSP 文件、`maxGen`、`local_migration_interval`、`local_to_global_ratio`、`num_groups`、`base_seed` 和输出 CSV。
- 参数合法性检查要求 `nproc >= 4`、`num_groups >= 2`、`nproc % num_groups == 0`、每组至少 2 个 rank。
- 每个 rank 独立读取 `data/pcb442.tsp`，独立维护本地 `N_COLONY=100` 的子种群。
- 随机种子为 `rankSeed = baseSeed + rank * 10007`。
- `find_logical_position()` 根据 `group_members` 查找当前 rank 的 `logical_group` 和 `logical_pos`。
- local migration 使用逻辑 group 内的 ring 邻居，通过 `MPI_Sendrecv` 发送本地最优个体、接收个体并替换本地最差个体。
- global moving colony 只更新 `group_members`，不调用 `MPI_Sendrecv`，不迁移个体或种群数组。
- rank 0 汇总所有 rank 的 local best 得到 global best。
- rank 0 以追加模式写 CSV，算法名为 `MOVING_HDEA`。

## 5. 正确性验证：逻辑分组改变后的 local migration

smoke test 中已经验证 moving colony 后下一次 local migration 的通信对象确实发生变化。关键日志如下：

```text
[rank 0] local migration plan generation 20: group 0=[0->1,1->0] group 1=[2->3,3->2]
[rank 0] global moving colony generation 40: moving_position=0
[rank 0] after moving colony: group 0=[2,1] group 1=[0,3]
[rank 0] local migration plan generation 60: group 0=[2->1,1->2] group 1=[0->3,3->0]
```

初始逻辑分组为 `group 0=[0,1]`、`group 1=[2,3]`，因此 local migration 是 `0<->1` 和 `2<->3`。第一次 moving colony 后，逻辑分组变为 `group 0=[2,1]`、`group 1=[0,3]`，下一次 local migration 变为 `2<->1` 和 `0<->3`。

这证明后续 local migration 确实基于新的逻辑 group，而不是固定使用物理 rank group。

## 6. 实验设置

正式实验设置如下：

- 数据集：`data/pcb442.tsp`
- `maxGen = 1000`
- DEA `migration_interval = 100`
- HDEA `local_migration_interval = 100`
- HDEA `local_to_global_ratio = 5`
- MOVING_HDEA `local_migration_interval = 100`
- MOVING_HDEA `local_to_global_ratio = 5`
- 10 个随机种子：`12345, 22345, 32345, 42345, 52345, 62345, 72345, 82345, 92345, 102345`
- 结果文件：`results/final_experiment_results.csv`
- 分析文件：`results/final_analysis_summary.txt`

对比算法如下：

| algorithm | nproc | migration_interval | local_to_global_ratio | num_groups |
|---|---:|---:|---:|---:|
| SERIAL | 1 | 0 | 0 | 0 |
| DEA | 2 | 100 | 0 | 0 |
| DEA | 4 | 100 | 0 | 0 |
| HDEA | 4 | 100 | 5 | 2 |
| HDEA | 6 | 100 | 5 | 3 |
| MOVING_HDEA | 4 | 100 | 5 | 2 |
| MOVING_HDEA | 6 | 100 | 5 | 3 |

## 7. 实验结果

以下统计结果来自 `results/final_analysis_summary.txt`。TSP 是最小化问题，`global_best` 越小越好。

| algorithm | nproc | groups | ratio | count | best | mean | std | avg_time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SERIAL | 1 | 0 | 0 | 10 | 430142 | 438472.100 | 4628.069 | 2.868900 |
| DEA | 2 | 0 | 0 | 10 | 415765 | 430223.600 | 6134.273 | 3.562728 |
| DEA | 4 | 0 | 0 | 10 | 424318 | 430458.000 | 3508.236 | 3.594641 |
| HDEA | 4 | 2 | 5 | 10 | 426732 | 431573.700 | 4266.830 | 4.466030 |
| HDEA | 6 | 3 | 5 | 10 | 426245 | 430320.900 | 2496.949 | 4.596891 |
| MOVING_HDEA | 4 | 2 | 5 | 10 | 424632 | 429704.000 | 3745.679 | 5.076744 |
| MOVING_HDEA | 6 | 3 | 5 | 10 | 423208 | 427890.600 | 3380.349 | 4.892686 |

当前 10 次实验中，均值最小的是 `MOVING_HDEA n=6 groups=3`，mean 为 `427890.600`。单次最优值仍来自 `DEA n=2`，best 为 `415765`。

## 8. Welch t-test 显著性检验

以下 t-test 结果来自 `results/final_analysis_summary.txt`。检验为双侧 Welch t-test，显著性水平取 `0.05`。

| comparison | mean_left | mean_right | p-value | better | significant |
|---|---:|---:|---:|---|---|
| SERIAL n=1 vs DEA n=2 | 438472.100 | 430223.600 | 0.003512 | DEA n=2 | yes |
| SERIAL n=1 vs DEA n=4 | 438472.100 | 430458.000 | 0.000435 | DEA n=4 | yes |
| SERIAL n=1 vs HDEA n=4 groups=2 | 438472.100 | 431573.700 | 0.002782 | HDEA n=4 groups=2 | yes |
| SERIAL n=1 vs HDEA n=6 groups=3 | 438472.100 | 430320.900 | 0.000242 | HDEA n=6 groups=3 | yes |
| SERIAL n=1 vs MOVING_HDEA n=4 groups=2 | 438472.100 | 429704.000 | 0.000218 | MOVING_HDEA n=4 groups=2 | yes |
| SERIAL n=1 vs MOVING_HDEA n=6 groups=3 | 438472.100 | 427890.600 | 0.000022 | MOVING_HDEA n=6 groups=3 | yes |
| DEA n=4 vs HDEA n=4 groups=2 | 430458.000 | 431573.700 | 0.531355 | DEA n=4 | no |
| DEA n=4 vs HDEA n=6 groups=3 | 430458.000 | 430320.900 | 0.921034 | HDEA n=6 groups=3 | no |
| DEA n=4 vs MOVING_HDEA n=4 groups=2 | 430458.000 | 429704.000 | 0.647810 | MOVING_HDEA n=4 groups=2 | no |
| DEA n=4 vs MOVING_HDEA n=6 groups=3 | 430458.000 | 427890.600 | 0.112945 | MOVING_HDEA n=6 groups=3 | no |
| HDEA n=4 groups=2 vs MOVING_HDEA n=4 groups=2 | 431573.700 | 429704.000 | 0.311721 | MOVING_HDEA n=4 groups=2 | no |
| HDEA n=6 groups=3 vs MOVING_HDEA n=6 groups=3 | 430320.900 | 427890.600 | 0.085502 | MOVING_HDEA n=6 groups=3 | no |
| MOVING_HDEA n=4 groups=2 vs MOVING_HDEA n=6 groups=3 | 429704.000 | 427890.600 | 0.270783 | MOVING_HDEA n=6 groups=3 | no |

MOVING_HDEA 两组相对 SERIAL 都显著更好。MOVING_HDEA 相对 DEA n=4 和普通 HDEA 的均值更低，但 p-value 均大于 `0.05`，不能说显著优于 DEA 或普通 HDEA。

## 9. MOVING_HDEA 与 HDEA/DEA 的结果比较

MOVING_HDEA n=4 的 mean 为 `429704.000`，低于 HDEA n=4 的 `431573.700`，但 p-value 为 `0.311721`，差异不显著。

MOVING_HDEA n=6 的 mean 为 `427890.600`，低于 HDEA n=6 的 `430320.900`，但 p-value 为 `0.085502`，仍未达到 `0.05` 显著性水平。

与 DEA n=4 比较时，MOVING_HDEA n=4 和 MOVING_HDEA n=6 的均值都更低，但 p-value 分别为 `0.647810` 和 `0.112945`，均不显著。因此当前实验只能说明 MOVING_HDEA 在均值上表现出更好的趋势，不能得出显著优于 DEA 的结论。

## 10. 为什么 moving colony 可能更好

普通 HDEA 的 global migration 只引入单个个体，而 moving colony 让整个子种群改变逻辑 group 归属。迁入新 group 的子种群可以在后续 local migration 中持续传播自身的搜索结构，而不是只提供一次单个个体的输入。

这种机制可能降低组内子种群之间的相似性，提高后续 local migration 的有效性。与此同时，global moving colony 只更新逻辑映射，不发送个体或种群数组，因此全局阶段通信成本很低。

不过，本阶段实验没有显示 MOVING_HDEA 相对 DEA 或普通 HDEA 的显著优势。因此文档中只能说 moving colony 在机制上可能更好，并且在当前实验中表现出更低均值趋势，不能说已经显著优于 DEA 或 HDEA。

## 11. 公平性说明与局限性

当前所有并行算法仍然是每个 rank 保留 `N_COLONY=100`：

```text
SERIAL n=1: 总个体数 100
DEA n=2: 总个体数 200
DEA n=4: 总个体数 400
HDEA n=4: 总个体数 400
HDEA n=6: 总个体数 600
MOVING_HDEA n=4: 总个体数 400
MOVING_HDEA n=6: 总个体数 600
```

更公平的同规模比较是：

```text
DEA n=4 vs HDEA n=4 vs MOVING_HDEA n=4
HDEA n=6 vs MOVING_HDEA n=6
```

其中 MOVING_HDEA n=6 的总个体数为 600，因此不能和 DEA n=4 或 HDEA n=4 做完全公平比较。如果要更严格公平，应补充固定总种群规模或固定函数评价次数实验。

## 12. 可复现运行方式

完整实验运行方式：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_experiments_final.ps1
python .\scripts\analyze_results_final.py .\results\final_experiment_results.csv
```

单次 MOVING_HDEA 运行方式：

```powershell
mpiexec -n 4 bin\tsp_mpi_moving_hdea.exe data\pcb442.tsp 1000 100 5 2 12345 results\temp_moving_hdea.csv
mpiexec -n 6 bin\tsp_mpi_moving_hdea.exe data\pcb442.tsp 1000 100 5 3 12345 results\temp_moving_hdea.csv
```

## 13. 本阶段结论

MOVING_HDEA 已实现，并通过 smoke test 验证：moving colony 后下一次 local migration 的通信对象确实基于新的逻辑 group 发生变化。

本阶段已经完成 7 组算法、每组 10 个 seed 的正式实验，共 70 行结果。实验显示 MOVING_HDEA n=4 和 n=6 都显著优于 SERIAL。相对 DEA n=4 和普通 HDEA，MOVING_HDEA 的 mean 更低，但差异没有达到 `0.05` 显著性水平。

因此，MOVING_HDEA 可以作为最终报告中的高级算法实现；但最终报告中需要如实说明，它在当前实验中表现出均值优势和机制优势，但没有被 t-test 证明显著优于 DEA 或普通 HDEA。
