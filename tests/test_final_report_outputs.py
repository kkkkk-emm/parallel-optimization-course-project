from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_final_report_artifacts_exist():
    required = [
        ROOT / "scripts/generate_report_figures.py",
        ROOT / "reports/final_report_draft.md",
        ROOT / "reports/assets/fig_algorithm_framework.png",
        ROOT / "reports/assets/fig_final_mean_comparison.png",
        ROOT / "reports/assets/fig_final_best_comparison.png",
        ROOT / "reports/assets/fig_final_std_comparison.png",
        ROOT / "reports/assets/fig_final_time_comparison.png",
        ROOT / "reports/assets/fig_convergence_trend.png",
        ROOT / "reports/assets/fig_ttest_summary.png",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert missing == []


def test_final_report_contains_required_sections_and_data():
    report = (ROOT / "reports/final_report_draft.md").read_text(encoding="utf-8-sig")
    required_text = [
        "# 基于 MPI 的旅行商问题分层分布式进化算法并行化实验报告",
        "## 摘要",
        "## 1. 问题背景与任务要求",
        "## 4. MPI 并行算法设计",
        "## 7. 正式实验结果与分析",
        "## 8. 收敛趋势补充实验",
        "## 10. 局限性与改进方向",
        "## 附录 A：主要运行命令",
        "MOVING_HDEA n=6",
        "427890.600",
        "p=0.000022",
        "p=0.647810",
        "439479.000",
        "156517.667",
        "0<->1",
        "2<->1",
        "reports/assets/fig_final_mean_comparison.png",
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
