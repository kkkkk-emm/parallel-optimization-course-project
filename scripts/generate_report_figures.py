import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
FINAL_SUMMARY = ROOT / "results" / "final_analysis_summary.csv"
CONVERGENCE_SUMMARY = ROOT / "results" / "convergence_sensitivity_summary.csv"
REPRODUCTION_SUMMARY = ROOT / "results" / "reproduction_extension_summary.csv"
ASSET_DIR = ROOT / "reports" / "assets"
FIGURE_DIR = ROOT / "results" / "figures"


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as fp:
        return list(csv.DictReader(fp))


def label(row):
    algorithm = row["algorithm"]
    nproc = int(row["nproc"])
    groups = int(row["num_groups"])
    if algorithm in {"HDEA", "MOVING_HDEA"}:
        return f"{algorithm}\nn={nproc}, g={groups}"
    return f"{algorithm}\nn={nproc}"


def final_summary_rows():
    return [row for row in read_csv(FINAL_SUMMARY) if row["record_type"] == "summary"]


def final_ttest_rows():
    return [row for row in read_csv(FINAL_SUMMARY) if row["record_type"] == "ttest"]


def convergence_rows(record_type):
    return [row for row in read_csv(CONVERGENCE_SUMMARY) if row["record_type"] == record_type]


def save_current(path):
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    if path.parent != FIGURE_DIR:
        figure_path = FIGURE_DIR / path.name
        plt.savefig(figure_path, dpi=180, bbox_inches="tight")
        print(f"wrote {figure_path}")
    plt.close()
    print(f"wrote {path}")


def plot_algorithm_framework():
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    ax.axis("off")
    nodes = {
        "Serial EA": (0.08, 0.55),
        "DEA\nring migration": (0.35, 0.78),
        "HDEA\nlocal + global\nindividual migration": (0.63, 0.55),
        "MOVING_HDEA\ngroup_members +\nmoving colony": (0.35, 0.25),
    }
    colors = {
        "Serial EA": "#eef2ff",
        "DEA\nring migration": "#e0f2fe",
        "HDEA\nlocal + global\nindividual migration": "#dcfce7",
        "MOVING_HDEA\ngroup_members +\nmoving colony": "#fef3c7",
    }
    for text, (x, y) in nodes.items():
        ax.text(
            x,
            y,
            text,
            ha="center",
            va="center",
            fontsize=12,
            bbox=dict(boxstyle="round,pad=0.55", facecolor=colors[text], edgecolor="#334155", linewidth=1.2),
        )
    arrows = [
        ("Serial EA", "DEA\nring migration"),
        ("DEA\nring migration", "HDEA\nlocal + global\nindividual migration"),
        ("HDEA\nlocal + global\nindividual migration", "MOVING_HDEA\ngroup_members +\nmoving colony"),
        ("Serial EA", "MOVING_HDEA\ngroup_members +\nmoving colony"),
    ]
    for start, end in arrows:
        x1, y1 = nodes[start]
        x2, y2 = nodes[end]
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5, shrinkA=34, shrinkB=34),
        )
    ax.text(
        0.64,
        0.22,
        "Global moving colony changes logical groups;\nsubpopulation data stays on its MPI rank.",
        ha="left",
        va="center",
        fontsize=10,
        color="#334155",
    )
    ax.set_title("Algorithm Framework", fontsize=16, pad=16)
    save_current(ASSET_DIR / "fig_algorithm_framework.png")


def plot_final_bar(metric, output_name, title, ylabel):
    rows = final_summary_rows()
    labels = [label(row) for row in rows]
    values = [float(row[metric]) for row in rows]
    colors = ["#64748b", "#2563eb", "#3b82f6", "#16a34a", "#22c55e", "#f59e0b", "#f97316"]
    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    bars = ax.bar(labels, values, color=colors)
    ax.set_title(title, fontsize=15, pad=14)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", labelrotation=0)
    ax.text(0.99, 0.96, "Lower is better for TSP path length", transform=ax.transAxes, ha="right", va="top", fontsize=9, color="#334155")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.0f}", ha="center", va="bottom", fontsize=8)
    save_current(ASSET_DIR / output_name)


def plot_final_time():
    rows = final_summary_rows()
    labels = [label(row) for row in rows]
    values = [float(row["avg_time"]) for row in rows]
    colors = ["#64748b", "#2563eb", "#3b82f6", "#16a34a", "#22c55e", "#f59e0b", "#f97316"]
    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    bars = ax.bar(labels, values, color=colors)
    ax.set_title("Average Runtime Comparison", fontsize=15, pad=14)
    ax.set_ylabel("avg_time (seconds)")
    ax.grid(axis="y", alpha=0.25)
    ax.text(0.99, 0.96, "Runtime is not the main improvement target here", transform=ax.transAxes, ha="right", va="top", fontsize=9, color="#334155")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.2f}", ha="center", va="bottom", fontsize=8)
    save_current(ASSET_DIR / "fig_final_time_comparison.png")


def plot_final_improvement_ratio():
    rows = final_summary_rows()
    serial = next(row for row in rows if row["algorithm"] == "SERIAL")
    serial_mean = float(serial["mean"])
    labels = [label(row) for row in rows]
    values = [
        0.0 if row["algorithm"] == "SERIAL" else (serial_mean - float(row["mean"])) / serial_mean * 100.0
        for row in rows
    ]
    colors = ["#64748b", "#2563eb", "#3b82f6", "#16a34a", "#22c55e", "#f59e0b", "#f97316"]
    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    bars = ax.bar(labels, values, color=colors)
    ax.set_title("Final Experiment Improvement Ratio vs SERIAL", fontsize=15, pad=14)
    ax.set_ylabel("mean improvement (%)")
    ax.grid(axis="y", alpha=0.25)
    ax.text(0.99, 0.96, "Positive values mean lower mean global_best than SERIAL", transform=ax.transAxes, ha="right", va="top", fontsize=9, color="#334155")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.2f}%", ha="center", va="bottom", fontsize=8)
    save_current(ASSET_DIR / "fig_final_improvement_ratio.png")


def reproduction_summary_rows():
    if not REPRODUCTION_SUMMARY.exists():
        return []
    return [row for row in read_csv(REPRODUCTION_SUMMARY) if row["record_type"] == "summary"]


def plot_reproduction_improvement_ratio():
    rows = reproduction_summary_rows()
    if not rows:
        return
    labels = [label(row) for row in rows]
    values = [float(row["improvement_vs_serial_mean_pct"]) for row in rows]
    colors = ["#64748b", "#2563eb", "#3b82f6", "#16a34a", "#22c55e", "#f59e0b", "#f97316"]
    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    bars = ax.bar(labels, values, color=colors[: len(values)])
    ax.set_title("Reproduction Extension Improvement Ratio vs SERIAL", fontsize=15, pad=14)
    ax.set_ylabel("mean improvement (%)")
    ax.grid(axis="y", alpha=0.25)
    ax.text(0.99, 0.96, "maxGen=5000, migration_interval=25, local_to_global_ratio=20", transform=ax.transAxes, ha="right", va="top", fontsize=9, color="#334155")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.2f}%", ha="center", va="bottom", fontsize=8)
    save_current(ASSET_DIR / "fig_reproduction_improvement_ratio.png")


def plot_convergence():
    summaries = convergence_rows("summary")
    by_alg = {}
    for row in summaries:
        alg_label = label(row).replace("\n", " ")
        by_alg.setdefault(alg_label, []).append((int(row["maxGen"]), float(row["mean"])))
    fig, ax = plt.subplots(figsize=(10.5, 6))
    colors = ["#64748b", "#2563eb", "#16a34a", "#f97316"]
    for color, (alg_label, points) in zip(colors, by_alg.items()):
        points.sort()
        ax.plot([p[0] for p in points], [p[1] for p in points], marker="o", lw=2.2, label=alg_label, color=color)
    ax.set_title("maxGen Sensitivity: Mean Global Best", fontsize=15, pad=14)
    ax.set_xlabel("maxGen")
    ax.set_ylabel("mean global_best")
    ax.grid(True, alpha=0.25)
    ax.legend()
    ax.text(0.99, 0.96, "All curves decrease from 1000 to 5000", transform=ax.transAxes, ha="right", va="top", fontsize=9, color="#334155")
    save_current(ASSET_DIR / "fig_convergence_trend.png")


def plot_ttest_summary():
    interesting = [
        "SERIAL n=1 vs MOVING_HDEA n=4 groups=2",
        "SERIAL n=1 vs MOVING_HDEA n=6 groups=3",
        "DEA n=4 vs MOVING_HDEA n=4 groups=2",
        "DEA n=4 vs MOVING_HDEA n=6 groups=3",
        "HDEA n=4 groups=2 vs MOVING_HDEA n=4 groups=2",
        "HDEA n=6 groups=3 vs MOVING_HDEA n=6 groups=3",
    ]
    rows_by_comparison = {row["comparison"]: row for row in final_ttest_rows()}
    rows = [rows_by_comparison[item] for item in interesting]
    labels = [
        "SERIAL vs MOVING n=4",
        "SERIAL vs MOVING n=6",
        "DEA n=4 vs MOVING n=4",
        "DEA n=4 vs MOVING n=6",
        "HDEA n=4 vs MOVING n=4",
        "HDEA n=6 vs MOVING n=6",
    ]
    pvalues = [float(row["p_value"]) for row in rows]
    colors = ["#dc2626" if p < 0.05 else "#64748b" for p in pvalues]
    fig, ax = plt.subplots(figsize=(10.8, 5.8))
    y = np.arange(len(labels))
    ax.barh(y, pvalues, color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xscale("log")
    ax.axvline(0.05, color="#111827", lw=1.2, ls="--", label="p=0.05")
    ax.set_xlabel("p-value (log scale)")
    ax.set_title("Welch t-test Summary", fontsize=15, pad=14)
    ax.invert_yaxis()
    ax.legend()
    for yi, pvalue in zip(y, pvalues):
        ax.text(pvalue * 1.08, yi, f"p={pvalue:.6f}", va="center", fontsize=8)
    save_current(ASSET_DIR / "fig_ttest_summary.png")


def main():
    if not FINAL_SUMMARY.exists():
        raise FileNotFoundError(FINAL_SUMMARY)
    if not CONVERGENCE_SUMMARY.exists():
        raise FileNotFoundError(CONVERGENCE_SUMMARY)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.edgecolor": "#334155",
        "axes.labelcolor": "#111827",
        "xtick.color": "#111827",
        "ytick.color": "#111827",
    })
    plot_algorithm_framework()
    plot_final_bar("mean", "fig_final_mean_comparison.png", "Final Experiment Mean Comparison", "mean global_best")
    plot_final_bar("best", "fig_final_best_comparison.png", "Final Experiment Best Comparison", "best global_best")
    plot_final_bar("std", "fig_final_std_comparison.png", "Final Experiment Std Comparison", "std of global_best")
    plot_final_time()
    plot_final_improvement_ratio()
    plot_convergence()
    plot_ttest_summary()
    plot_reproduction_improvement_ratio()


if __name__ == "__main__":
    main()
