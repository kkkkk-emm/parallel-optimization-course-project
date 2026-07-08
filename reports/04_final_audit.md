# 最终报告前项目审计

审计日期：2026-07-07

本文件只用于最终报告前的项目审计和整理，不作为最终总报告正文。审计依据为当前项目文件、`results/final_experiment_results.csv`、`results/final_analysis_summary.txt`、`results/final_analysis_summary.csv`、源码和阶段文档。

## 1. 文件完整性审计

| 类别 | 文件 | 是否存在 | 说明 |
|---|---|---|---|
| 原始串行代码 | `src/TSP0.C` | 是 | 老师提供的原始串行版本，保留作为基线来源。 |
| 修复串行代码 | `src/tsp_serial_fixed.c` | 是 | 用于串行代码可运行性检查。 |
| 串行实验代码 | `src/tsp_serial_exp.c` | 是 | 支持 seed 和 CSV 输出的串行实验版本。 |
| DEA 代码 | `src/tsp_mpi_dea.c` | 是 | MPI 分布式进化算法 DEA 实现。 |
| HDEA 代码 | `src/tsp_mpi_hdea.c` | 是 | 普通分层分布式进化算法 HDEA 实现。 |
| MOVING_HDEA 代码 | `src/tsp_mpi_moving_hdea.c` | 是 | moving colony HDEA 实现。 |
| 最终实验脚本 | `scripts/run_experiments_final.ps1` | 是 | 编译并运行 7 组算法配置、10 个 seed。 |
| 最终分析脚本 | `scripts/analyze_results_final.py` | 是 | 计算分组统计和 Welch t-test。 |
| 最终结果 CSV | `results/final_experiment_results.csv` | 是 | 最终统一实验原始结果。 |
| 最终统计结果 TXT | `results/final_analysis_summary.txt` | 是 | 最终统计表和 t-test 结论。 |
| 最终统计结果 CSV | `results/final_analysis_summary.csv` | 是 | 机器可读统计结果和 t-test 结果。 |
| DEA 阶段文档 | `reports/01_dea_algorithm_and_experiment.md` | 是 | DEA 阶段说明和实验分析。 |
| HDEA 阶段文档 | `reports/02_hdea_algorithm_and_experiment.md` | 是 | HDEA 阶段说明和实验分析。 |
| MOVING_HDEA 阶段文档 | `reports/03_moving_hdea_algorithm_and_experiment.md` | 是 | MOVING_HDEA 阶段说明和最终统一实验分析。 |
| 项目进度文档 | `reports/project_progress.md` | 是 | 项目阶段进度与结果索引。 |
| 参考论文 | `docs/hierarchical.pdf` | 是 | moving colony HDEA 的参考论文。 |
| TSP 数据 | `data/pcb442.tsp` | 是 | 第一行为 `442`，后续为城市编号和坐标。 |

文件完整性结论：通过。目标清单中的文件均存在。

## 2. 实验结果行数审计

`results/final_experiment_results.csv` 使用 UTF-8 BOM 格式保存，审计时按 `utf-8-sig` 读取。数据行数不含表头。

| 算法配置 | count | seed 是否完整 | 重复行 | 非法数值 |
|---|---:|---|---|---|
| SERIAL n=1 | 10 | 是 | 无 | 无 |
| DEA n=2 | 10 | 是 | 无 | 无 |
| DEA n=4 | 10 | 是 | 无 | 无 |
| HDEA n=4 groups=2 | 10 | 是 | 无 | 无 |
| HDEA n=6 groups=3 | 10 | 是 | 无 | 无 |
| MOVING_HDEA n=4 groups=2 | 10 | 是 | 无 | 无 |
| MOVING_HDEA n=6 groups=3 | 10 | 是 | 无 | 无 |

总数据行数：70。

期望 seed：

```text
12345, 22345, 32345, 42345, 52345, 62345, 72345, 82345, 92345, 102345
```

行数审计结论：通过。7 组算法配置均为 10 行，共 70 行；未发现缺失 seed、重复配置行、非法空值、非数值 `global_best` 或非数值 `elapsed_sec`。

## 3. 统计结果一致性审计

已从 `results/final_experiment_results.csv` 重新计算 `count`、`best`、`mean`、`std`、`min`、`max`、`avg_time`，并与 `results/final_analysis_summary.txt` 和 `results/final_analysis_summary.csv` 对比。重新运行 `scripts/analyze_results_final.py` 到临时文件后，TXT 与 CSV 对比差异行数均为 0。

| algorithm | nproc | groups | ratio | count | best | mean | std | min | max | avg_time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SERIAL | 1 | 0 | 0 | 10 | 430142 | 438472.100 | 4628.069 | 430142 | 444429 | 2.869 |
| DEA | 2 | 0 | 0 | 10 | 415765 | 430223.600 | 6134.273 | 415765 | 438572 | 3.563 |
| DEA | 4 | 0 | 0 | 10 | 424318 | 430458.000 | 3508.236 | 424318 | 434823 | 3.595 |
| HDEA | 4 | 2 | 5 | 10 | 426732 | 431573.700 | 4266.830 | 426732 | 438677 | 4.466 |
| HDEA | 6 | 3 | 5 | 10 | 426245 | 430320.900 | 2496.949 | 426245 | 433564 | 4.597 |
| MOVING_HDEA | 4 | 2 | 5 | 10 | 424632 | 429704.000 | 3745.679 | 424632 | 435465 | 5.077 |
| MOVING_HDEA | 6 | 3 | 5 | 10 | 423208 | 427890.600 | 3380.349 | 423208 | 433889 | 4.893 |

统计一致性结论：通过。当前正式结果与最终统计文件一致。

## 4. 阶段文档数字一致性审计

| 文档 | 审计结果 | 说明 |
|---|---|---|
| `reports/01_dea_algorithm_and_experiment.md` | 部分一致 | SERIAL、DEA n=2、DEA n=4 的 `best`、`mean`、`std` 与最终统计一致；`avg_time` 是 DEA 阶段实验运行时间，不等同于最终统一脚本的运行时间。 |
| `reports/02_hdea_algorithm_and_experiment.md` | 部分一致 | SERIAL、DEA、HDEA 的 `best`、`mean`、`std` 与最终统计一致；`avg_time` 是 HDEA 阶段实验运行时间，不等同于最终统一脚本的运行时间。 |
| `reports/03_moving_hdea_algorithm_and_experiment.md` | 一致 | 7 组算法的 `best`、`mean`、`std`、`avg_time` 与最终统计结果一致。 |
| `reports/project_progress.md` | 部分一致 | `best`、`mean`、`std` 和 t-test 结论与最终结果一致；SERIAL、DEA、HDEA 的 `avg_time` 仍保留阶段性实验时间，不完全等同于最终统一脚本。 |

阶段文档审计结论：最终报告应以 `results/final_experiment_results.csv`、`results/final_analysis_summary.txt` 和 `results/final_analysis_summary.csv` 为准。早期阶段文档中的运行时间列可作为阶段记录，不应作为最终报告中的统一运行时间引用。

## 5. Welch t-test 结果审计

`scripts/analyze_results_final.py` 的 Welch t-test 输出与 `results/final_analysis_summary.txt` 一致。

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

t-test 审计结论：

| 结论 | 是否可写 | 依据 |
|---|---|---|
| MOVING_HDEA n=4 显著优于 SERIAL | 可以 | p=0.000218。 |
| MOVING_HDEA n=6 显著优于 SERIAL | 可以 | p=0.000022。 |
| MOVING_HDEA n=4 相比 DEA n=4 均值更低，但不显著 | 可以 | p=0.647810。 |
| MOVING_HDEA n=6 相比 DEA n=4 均值更低，但不显著 | 可以 | p=0.112945。 |
| MOVING_HDEA n=4 相比 HDEA n=4 均值更低，但不显著 | 可以 | p=0.311721。 |
| MOVING_HDEA n=6 相比 HDEA n=6 均值更低，但不显著 | 可以 | p=0.085502。 |
| MOVING_HDEA 显著优于 DEA | 不能写 | 与 t-test 不一致。 |
| MOVING_HDEA 显著优于普通 HDEA | 不能写 | 与 t-test 不一致。 |
| HDEA 显著优于 DEA | 不能写 | 与 t-test 不一致。 |
| 所有并行算法均显著优于串行基线 | 可以谨慎写 | 当前被列入 t-test 的并行组相对 SERIAL 均达到 p<0.05。 |

## 6. 算法实现审计

### 6.1 DEA

| 检查项 | 结论 | 源码依据 |
|---|---|---|
| 每个 MPI rank 维护一个本地子种群 | 通过 | `src/tsp_mpi_dea.c` 每个 rank 初始化并演化本地 `N_COLONY=100`。 |
| 所有 rank 构成 ring | 通过 | `migrate_ring()` 中使用 `(rank+1)%size` 和 `(rank-1+size)%size`。 |
| 周期性发送本地最优个体 | 通过 | 主循环按 `migrationInterval` 调用 `migrate_ring()`。 |
| 接收个体替换本地最差个体 | 通过 | `colony[iworst] = recvPath` 后重新计算距离。 |
| 使用 `MPI_Sendrecv` | 通过 | `migrate_ring()` 使用 `MPI_Sendrecv`。 |
| rank 0 汇总 global best | 通过 | 使用 `MPI_Gather` 汇总各 rank 最优值，rank 0 取全局最优。 |

DEA 审计结论：实现与文档描述一致。

### 6.2 HDEA

| 检查项 | 结论 | 源码依据 |
|---|---|---|
| rank 被划分为 group | 通过 | `groupId = mpiRank / subpopsPerGroup`，`localId = mpiRank % subpopsPerGroup`。 |
| group 内执行 local migration | 通过 | `migrate_local_ring()` 在同一 group 内计算发送和接收 rank。 |
| group 间执行 global migration | 通过 | `migrate_global_ring()` 在 group 间按相同 local id 迁移。 |
| global migration 迁移对象是个体 | 通过 | `migrate_individual()` 发送 `colony[ibest]`。 |
| 使用 `MPI_Sendrecv` | 通过 | `migrate_individual()` 使用 `MPI_Sendrecv`。 |
| 支持 HDEA 参数 | 通过 | 命令行参数包括 `local_migration_interval`、`local_to_global_ratio`、`num_groups`。 |

HDEA 审计结论：实现与文档描述一致。

### 6.3 MOVING_HDEA

| 检查项 | 结论 | 源码依据 |
|---|---|---|
| 使用 `groupMembers` 维护逻辑分组 | 通过 | `groupMembers[group * subpopsPerGroup + pos]` 保存逻辑 group 到 rank 的映射。 |
| global moving colony 只更新 `groupMembers` | 通过 | `move_colony_ring()` 旋转 `groupMembers`。 |
| global moving colony 不发送个体 | 通过 | `move_colony_ring()` 内没有 `MPI_Sendrecv`。 |
| 不交换整个子种群数组 | 通过 | 只更新逻辑映射，不复制 `colony` 数组。 |
| 后续 local migration 基于新的逻辑 group 执行 | 通过 | `migrate_local_ring()` 每次调用 `find_logical_position()` 和 `group_member()` 重新计算通信对象。 |
| moving 后 local migration 对象变化已有证据 | 通过 | `reports/moving_colony_mapping_check.md` 记录 n=4 短运行：`0<->1, 2<->3` 变为 `2<->1, 0<->3`。 |

MOVING_HDEA 审计结论：实现与文档描述一致。当前实现对应 ring global migration with moving colony；没有实现 random moving colony。

## 7. 公平性与局限性审计

当前实验中，每个 MPI rank 均保留 `N_COLONY=100` 个个体，因此不同 nproc 的总个体数量不同。

| 算法配置 | 总个体数 |
|---|---:|
| SERIAL n=1 | 100 |
| DEA n=2 | 200 |
| DEA n=4 | 400 |
| HDEA n=4 | 400 |
| HDEA n=6 | 600 |
| MOVING_HDEA n=4 | 400 |
| MOVING_HDEA n=6 | 600 |

必须说明的公平性边界：

| 边界 | 说明 |
|---|---|
| SERIAL vs 并行算法 | 不是严格固定总计算预算比较；并行组总个体数更大。 |
| n=6 vs n=4 | 不是严格同规模比较；n=6 总个体数为 600，n=4 总个体数为 400。 |
| 更公平的同规模比较 | DEA n=4 vs HDEA n=4 vs MOVING_HDEA n=4；HDEA n=6 vs MOVING_HDEA n=6。 |
| 若要求严格公平 | 需要补充固定总种群规模或固定函数评价次数的实验。 |
| 运行时间解释 | 当前 `avg_time` 受 MPI 启动、进程数、通信和机器状态影响，不应单独作为算法质量结论。 |
| 数据集范围 | 当前正式实验只基于 `pcb442.tsp`，不能推广为所有 TSP 实例结论。 |

公平性审计结论：当前结果足以支持课程作业中“并行化后相比串行基线结果更好”的实验说明；若要作严格算法优劣结论，需要补充固定预算实验。

## 8. 最终报告可引用结果

最终报告可以引用以下结果：

| 可引用内容 | 依据 |
|---|---|
| 已实现 DEA、普通 HDEA、MOVING_HDEA 三类 MPI 并行进化算法 | 源码和阶段文档均存在。 |
| 7 组算法配置每组 10 次独立运行，共 70 行结果 | `final_experiment_results.csv` 审计通过。 |
| 所有并行算法相对 SERIAL 的平均路径长度均更低 | 最终统计表。 |
| 所有被列入 t-test 的并行组相对 SERIAL 均达到显著性 | Welch t-test，p<0.05。 |
| MOVING_HDEA n=6 获得最低平均路径长度 | mean=427890.600。 |
| DEA n=2 获得最低单次 best | best=415765。 |
| MOVING_HDEA 相比 DEA/HDEA 具有均值趋势优势，但不显著 | 对应 p-value 均大于 0.05。 |
| moving colony 后 local migration 通信对象确实变化 | `reports/moving_colony_mapping_check.md` 和 `src/tsp_mpi_moving_hdea.c`。 |

最终报告不能写以下结论：

| 不能写的结论 | 原因 |
|---|---|
| MOVING_HDEA 显著优于 DEA | t-test 不支持。 |
| MOVING_HDEA 显著优于普通 HDEA | t-test 不支持。 |
| HDEA 显著优于 DEA | t-test 不支持。 |
| 本实验完全复现了论文结果 | 当前只是参考论文思想并完成课程项目实现。 |
| 本实验在严格相同计算预算下证明 MOVING_HDEA 最优 | 当前总个体数随 nproc 增加，不是固定预算实验。 |
| moving colony 一定能在所有 TSP 实例上取得最好结果 | 当前只验证 `pcb442.tsp`，且统计显著性有限。 |

## 9. 是否存在需要修复的问题

| 问题 | 严重性 | 建议 |
|---|---|---|
| 早期阶段文档中的部分 `avg_time` 与最终统一实验统计不一致 | 低 | 不必修改阶段文档；最终报告引用 `results/final_analysis_summary.txt/csv`。 |
| `results/final_experiment_results.csv` 带 UTF-8 BOM | 低 | 不影响分析脚本；读取时使用 `utf-8-sig` 更稳健。 |
| 当前实验不是固定总计算预算 | 中 | 在最终报告中明确作为公平性边界；如需更严格结论，补充固定预算实验。 |
| 未实现 random moving colony | 低 | 当前只声称实现 ring moving colony，不扩大表述。 |

审计未发现需要立即修复的源码问题、结果文件缺失问题或统计文件损坏问题。

## 10. 最终报告建议结构

# 并行分布计算期末大作业报告建议结构

## 1. 问题背景

说明 TSP、原始串行进化算法、课程要求和参考论文中的 DEA/HDEA/moving colony HDEA 思路。

## 2. 原始串行进化算法

说明 `TSP0.C` 的数据读取、种群表示、路径长度计算、选择交叉变异和输出逻辑，以及串行实验版本的最小修复。

## 3. MPI 并行算法设计

### 3.1 DEA

说明多子种群、rank ring、周期性个体迁移和 global best 汇总。

### 3.2 HDEA

说明 group 划分、local migration、individual global migration 和参数设置。

### 3.3 MOVING_HDEA

说明 `groupMembers` 逻辑映射、ring moving colony、无通信全局移动、moving 后 local migration 对象变化。

## 4. 实验设计

说明数据集、maxGen、迁移参数、进程数、seed、运行次数、统计指标和 Welch t-test。

## 5. 实验结果与统计分析

引用 `results/final_analysis_summary.txt/csv` 的统计表和 t-test 表，说明最低均值、最低单次 best 和显著性结果。

## 6. 结果讨论

解释并行子种群、迁移机制、分层迁移和 moving colony 为什么可能改善搜索质量，同时说明显著性边界。

## 7. 公平性与局限性

说明总个体数不同、n=4 与 n=6 规模不同、当前只使用 `pcb442.tsp`、未做固定预算实验。

## 8. 总结

总结已完成三类 MPI 并行算法、正式实验和统计分析；强调可以证明并行算法相对串行基线更好，但不夸大 MOVING_HDEA 相对 DEA/HDEA 的显著优势。
