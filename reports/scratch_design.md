# Version B Scratch TSP Design

## 定位

Version B 是一个放在 `src_scratch/` 下的独立 TSP 求解实现。它不修改 Version A，也不复制以下 Version A 算法源码：

- `src/TSP0.C`
- `src/tsp_serial_exp.c`
- `src/tsp_mpi_dea.c`
- `src/tsp_mpi_hdea.c`
- `src/tsp_mpi_moving_hdea.c`

Version B 的目标不是复刻老师原始进化算法，而是以独立启发式搜索方式，在 `data/pcb442.tsp` 上得到尽可能短的路径，并与 Version A 正式实验基准比较。

## 独立数据结构

核心实现位于 `src_scratch/tsp_scratch_core.h`，入口文件为：

- `src_scratch/tsp_scratch_serial.c`
- `src_scratch/tsp_scratch_mpi.c`

该实现从零提供以下组件：

1. TSP parser：读取第一行城市数量，再读取城市编号和二维坐标。
2. integer Euclidean distance matrix：对 `sqrt(dx^2+dy^2)+0.5` 取整数，构造完整距离矩阵。
3. tour length：计算包含最后城市回到起点的闭环路径长度。
4. tour 合法性 checker：检查 tour 长度为城市数，且每个城市恰好出现一次。
5. scratch smoke test：在 4-city square 上验证距离、闭环长度、合法性检查和搜索结果。

这些代码不依赖 Version A 的全局数组、随机初始化、inver-over 逻辑或 MPI 迁移逻辑。

## 算法候选

Version B 的算法锦标赛尝试了三个候选：

- `SCRATCH_NN_2OPT`：nearest-neighbor initialization + 2-opt local search。
- `SCRATCH_GREEDY_2OPT`：randomized greedy nearest-neighbor initialization + 2-opt local search。
- `SCRATCH_ILS_2OPT`：randomized greedy initialization + double-bridge perturbation + repeated 2-opt。

最终正式实验选择 `SCRATCH_ILS_2OPT`。选择原因是 trial 中 MPI n=4 的 `SCRATCH_ILS_2OPT` mean 最低，且 best 也低于其他大多数候选。

## 并行策略

MPI 版本采用 independent multi-start parallel search。每个 rank 读取同一 `data/pcb442.tsp`，使用不同派生 seed 独立运行同一 scratch 算法，然后通过 `MPI_Reduce` 汇总全局最短 `best_length`，并用 `MPI_Reduce` 的 `MPI_MAX` 汇总本次运行的并行 elapsed time。

当前 Version B 没有实现 island exchange。这样做的原因是 trial 已显示独立多启动 2-opt/ILS 已显著超过 Version A 基准，保留简单并行策略更利于说明 Version B 与 Version A 的独立性。

## 统一输出字段

所有 scratch 结果 CSV 使用统一 schema：

```csv
algorithm,nproc,mode,seed,time_budget_sec,iteration_budget,best_length,elapsed_sec
```

结果文件为：

- `results/scratch_algorithm_trials.csv`
- `results/scratch_experiment_results.csv`
- `results/scratch_analysis_summary.csv`
- `results/scratch_algorithm_trials_summary.txt`

分析脚本 `scripts/analyze_scratch_results.py` 会读取 `results/final_analysis_summary.csv` 中 Version A 的正式基准，并输出：

- `beats_version_a_mean`
- `beats_version_a_best`
- `mean_improvement_vs_version_a`
- `best_improvement_vs_version_a`

## 公平性边界

Version B 使用的是启发式局部搜索，不是 Version A 的进化算法。因此比较应理解为“独立 scratch 实现在同一 `pcb442.tsp` 上的效果对照”，不能写成对 Version A 算法机制的严格公平消融。尤其是：

1. Version B 使用 time budget 和 iteration budget。
2. MPI 版本通过更多 rank 获得更多独立起点。
3. Version A 的正式结果来自 `maxGen=1000` 进化搜索。
4. Version B 明显更短的路径主要说明 scratch 启发式局部搜索更适合该实例，不等价于证明所有 TSP 上都优于 Version A。
