# Version B Scratch Audit

## Scope

本审计覆盖 Version B scratch 实现、trial、正式实验和报告产物。Version B 代码和结果均放在独立路径中：

- `src_scratch/`
- `results/scratch_algorithm_trials.csv`
- `results/scratch_algorithm_trials_summary.txt`
- `results/scratch_experiment_results.csv`
- `results/scratch_analysis_summary.csv`
- `results/scratch_analysis_summary.txt`
- `reports/scratch_design.md`
- `reports/scratch_algorithm_search_log.md`
- `reports/scratch_audit.md`

## Version A Protection

本轮不修改 Version A。受保护文件的审计对象包括：

- `data/pcb442.tsp`
- `src/TSP0.C`
- `results/final_experiment_results.csv`
- `results/final_analysis_summary.csv`
- `results/final_analysis_summary.txt`

当前校验哈希为：

| file | SHA256 |
|---|---|
| `data/pcb442.tsp` | `62C069B71B749ED0EE292B97214387EE0C758323511CD9EB906691C7D129EA50` |
| `src/TSP0.C` | `0710750630FFAB9AD037344399592A1A853BCAB606AB959C12F269A8E915046C` |
| `results/final_experiment_results.csv` | `323756752ABF7A2C8BB00249EE706A26D9FC1B5001A5DA9E8D92AD6F6093B044` |
| `results/final_analysis_summary.csv` | `A3372D0A1B0621DB5EB744726652BD99DF35FBF5204AF58E648BA5C957DF2FC4` |
| `results/final_analysis_summary.txt` | `01CECF32C47A5FB9B462A298A623FFA2906F4D0EFA0DF14623BA487108C1FD70` |

runner 中包含 `Assert-NotProtectedResultPath`，拒绝将 scratch 结果写入 Version A 正式结果文件。

## Independence Evidence

Version B 代码位于 `src_scratch/`：

- `src_scratch/tsp_scratch_core.h`
- `src_scratch/tsp_scratch_serial.c`
- `src_scratch/tsp_scratch_mpi.c`

该实现独立提供 parser、distance matrix、tour length、tour 合法性 checker、nearest-neighbor、randomized greedy、2-opt、double-bridge perturbation 和 ILS。它没有修改 Version A 文件，也没有把 scratch 结果写入 `results/final_*`。

## Tour Validity Evidence

tour 合法性由 `scratch_tour_is_valid` 检查：每个城市编号必须在 `[0,n)` 内，且每个城市恰好出现一次。闭环路径长度由 `scratch_tour_length` 计算，包含最后城市回到起点。

smoke test 由以下命令触发：

```powershell
bin\tsp_scratch_serial.exe --smoke
```

smoke test 检查：

1. 4-city square 的闭环长度为 40。
2. 合法 tour 通过，重复城市 tour 被拒绝。
3. nearest-neighbor 生成 tour 合法。
4. `SCRATCH_ILS_2OPT` 在 4-city square 上得到长度 40。

pytest 也会编译 serial scratch 程序并运行该 smoke test。

正式配置的 best tour 已保存到：

```text
results/scratch_best_tours/
```

包含文件：

- `best_SCRATCH_ILS_2OPT_serial_n1.tour`
- `best_SCRATCH_ILS_2OPT_mpi_n2.tour`
- `best_SCRATCH_ILS_2OPT_mpi_n4.tour`
- `best_SCRATCH_ILS_2OPT_mpi_n6.tour`

验证脚本为：

```powershell
python .\scripts\verify_scratch_tours.py
```

验证内容包括：

1. 每条 best tour 城市数量为 442。
2. 每个城市编号 1..442 恰好出现一次。
3. 路径长度按闭环方式重新计算，即包含最后城市回到起点。
4. 重新计算长度与 `results/scratch_experiment_results.csv` 中对应正式配置的 `best_length` 完全一致。

当前验证结果：

```text
SCRATCH_TOUR_VERIFY_OK
verified_configs=4
official_optimum=50778
version_b_best=51843
optimality_gap_pct=2.10
version_b_best_formal_mean=52160.600
mean_gap_pct=2.72
```

## Result Provenance

trial 结果来自实际程序运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_scratch_trials.ps1
```

正式 Version B 结果来自实际程序运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_scratch_final.ps1
```

正式结果文件 `results/scratch_experiment_results.csv` 当前有 40 行：

- serial n=1：10 rows
- MPI n=2：10 rows
- MPI n=4：10 rows
- MPI n=6：10 rows

## Version A Comparison

Version A 正式基准：

- best formal mean：`427890.600`
- best single run：`415765`

Version B 正式最佳配置：

- `SCRATCH_ILS_2OPT` MPI n=6
- mean：`52160.600`
- best：`51843`
- avg_time：`2.061900`

TSPLIB pcb442 official optimum = 50778。

Version B best = 51843。

optimality gap = 2.10%。

Version B best formal mean = 52160.600。

mean gap = 2.72%。

Version B 达标情况：

- `beats_version_a_mean = yes`
- `beats_version_a_best = yes`
- `mean_improvement_vs_version_a = 87.810%`
- `best_improvement_vs_version_a = 87.531%`

## Risk Notes

1. Version B 与 Version A 算法机制不同。它证明了独立 scratch 启发式在 `pcb442.tsp` 上表现更好，不是对 Version A 每个并行机制的公平消融。
2. 当前只测试一个 TSP 实例，不能外推到全部 TSPLIB。
3. MPI 版本是 independent multi-start parallel search，没有实现 island exchange。
4. 运行时间来自单机 Windows/MS-MPI 环境，不能泛化为稳定加速结论。
