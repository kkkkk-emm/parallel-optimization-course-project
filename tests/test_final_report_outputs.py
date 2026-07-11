from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_final_report_artifacts_exist():
    required = [
        ROOT / "scripts/generate_report_figures.py",
        ROOT / "reports/final_report_draft.md",
        ROOT / "results/figures/fig_algorithm_framework.png",
        ROOT / "results/figures/fig_final_mean_comparison.png",
        ROOT / "results/figures/fig_final_best_comparison.png",
        ROOT / "results/figures/fig_final_time_comparison.png",
        ROOT / "results/figures/fig_final_improvement_ratio.png",
        ROOT / "results/figures/fig_convergence_trend.png",
        ROOT / "results/figures/fig_reproduction_improvement_ratio.png",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert missing == []


def test_final_report_contains_required_sections_and_data():
    report = (ROOT / "reports/final_report_draft.md").read_text(encoding="utf-8-sig")
    required_text = [
        "# 基于 MPI 的旅行商问题双路线综合实验报告",
        "## 摘要",
        "## 1. 引言",
        "## 2. 问题背景：TSP 与进化算法",
        "## 3. 原始串行程序分析",
        "## 4. 并行化设计动机",
        "## 5. DEA 算法设计",
        "## 6. HDEA 算法设计",
        "## 7. MOVING_HDEA 算法设计",
        "## 8. MPI 通信与数据流设计",
        "## 9. 实验环境、数据集与配置",
        "## 10. 评价指标",
        "## 11. 实验结果与统计分析",
        "## 12. 收敛趋势与参数敏感性分析",
        "## 13. 与参考论文的对应关系和差异",
        "## 14. 复现程度分析",
        "## 15. 并行效果分析：解质量与运行时间",
        "## 16. Version B：完全独立实现的 SCRATCH_ILS_2OPT 路线",
        "## 17. 双路线综合讨论",
        "## 18. 局限性",
        "## 19. 结论",
        "## 参考文献",
        "## 附录 A：运行命令",
        "## 附录 B：文件清单",
        "## 附录 C：复现实验步骤",
        "MOVING_HDEA n=6",
        "427890.600",
        "p=0.000022",
        "p=0.647810",
        "439479.000",
        "156517.667",
        "reproduction_extension_results.csv",
        "105127.400",
        "38.722%",
        "SCRATCH_ILS_2OPT",
        "TSPLIB official optimum 50778",
        "Version B best formal mean",
        "52160.600",
        "51843",
        "2.10%",
        "2.72%",
        "不是严格公平消融",
        "完全独立实现",
        "0<->1",
        "2<->1",
        "results/figures/fig_final_mean_comparison.png",
        "results/figures/fig_final_improvement_ratio.png",
        "results/figures/fig_reproduction_improvement_ratio.png",
    ]
    missing = [text for text in required_text if text not in report]
    assert missing == []


def test_final_report_avoids_forbidden_claims():
    report = (ROOT / "reports/final_report_draft.md").read_text(encoding="utf-8-sig")
    forbidden = [
        "MOVING_HDEA 显著优于 DEA",
        "MOVING_HDEA 显著优于 HDEA",
        "完全复现了论文结果",
        "已经收敛到最优解",
        "达到 TSPLIB 最优解",
        "显著加速了运行时间",
    ]
    present = [text for text in forbidden if text in report]
    assert present == []
