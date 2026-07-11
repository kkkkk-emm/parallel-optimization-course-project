import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_A_SUMMARY = ROOT / "results" / "final_analysis_summary.csv"
VERSION_A_MEAN_FALLBACK = 427890.600
VERSION_A_BEST_FALLBACK = 415765.0

REQUIRED_COLUMNS = {
    "algorithm",
    "nproc",
    "mode",
    "seed",
    "time_budget_sec",
    "iteration_budget",
    "best_length",
    "elapsed_sec",
}


def read_version_a_baseline():
    best_mean = VERSION_A_MEAN_FALLBACK
    best_single = VERSION_A_BEST_FALLBACK
    if not VERSION_A_SUMMARY.exists():
        return best_mean, best_single

    with VERSION_A_SUMMARY.open(newline="", encoding="utf-8-sig") as fp:
        rows = list(csv.DictReader(fp))
    summary_rows = [row for row in rows if row.get("record_type") == "summary"]
    means = [float(row["mean"]) for row in summary_rows if row.get("mean")]
    bests = [float(row["best"]) for row in summary_rows if row.get("best")]
    if means:
        best_mean = min(means)
    if bests:
        best_single = min(bests)
    return best_mean, best_single


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        if reader.fieldnames is None:
            raise ValueError(f"{path} is empty")
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"{path} missing columns: {', '.join(sorted(missing))}")
        rows = []
        seen = set()
        for line_no, row in enumerate(reader, start=2):
            parsed = {
                "algorithm": row["algorithm"],
                "nproc": int(row["nproc"]),
                "mode": row["mode"],
                "seed": int(row["seed"]),
                "time_budget_sec": float(row["time_budget_sec"]),
                "iteration_budget": int(row["iteration_budget"]),
                "best_length": float(row["best_length"]),
                "elapsed_sec": float(row["elapsed_sec"]),
            }
            for field in ("best_length", "elapsed_sec", "time_budget_sec"):
                if not math.isfinite(parsed[field]):
                    raise ValueError(f"non-finite {field} on line {line_no}")
            key = (parsed["algorithm"], parsed["nproc"], parsed["mode"], parsed["seed"])
            if key in seen:
                raise ValueError(f"duplicate result row on line {line_no}: {key}")
            seen.add(key)
            rows.append(parsed)
    return rows


def group_key(row):
    return (
        row["algorithm"],
        row["nproc"],
        row["mode"],
        row["time_budget_sec"],
        row["iteration_budget"],
    )


def sample_std(values):
    return statistics.stdev(values) if len(values) > 1 else 0.0


def summarize(rows, version_a_mean, version_a_best):
    grouped = defaultdict(list)
    for row in rows:
        grouped[group_key(row)].append(row)

    summaries = []
    for key, group_rows in sorted(grouped.items(), key=lambda item: (item[0][2], item[0][1], item[0][0])):
        algorithm, nproc, mode, time_budget, iteration_budget = key
        values = [row["best_length"] for row in group_rows]
        times = [row["elapsed_sec"] for row in group_rows]
        mean_value = statistics.mean(values)
        best_value = min(values)
        summaries.append(
            {
                "record_type": "summary",
                "algorithm": algorithm,
                "nproc": nproc,
                "mode": mode,
                "time_budget_sec": time_budget,
                "iteration_budget": iteration_budget,
                "count": len(group_rows),
                "best": best_value,
                "mean": mean_value,
                "std": sample_std(values),
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
                "avg_time": statistics.mean(times),
                "time_median": statistics.median(times),
                "beats_version_a_mean": "yes" if mean_value < version_a_mean else "no",
                "beats_version_a_best": "yes" if best_value < version_a_best else "no",
                "mean_improvement_vs_version_a": (version_a_mean - mean_value) / version_a_mean * 100.0,
                "best_improvement_vs_version_a": (version_a_best - best_value) / version_a_best * 100.0,
            }
        )
    return summaries


def fmt(value, digits=6):
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_summary_csv(path, summaries):
    fieldnames = [
        "record_type",
        "algorithm",
        "nproc",
        "mode",
        "time_budget_sec",
        "iteration_budget",
        "count",
        "best",
        "mean",
        "std",
        "median",
        "min",
        "max",
        "avg_time",
        "time_median",
        "beats_version_a_mean",
        "beats_version_a_best",
        "mean_improvement_vs_version_a",
        "best_improvement_vs_version_a",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in summaries:
            writer.writerow(
                {
                    key: fmt(value, 6) if isinstance(value, float) else value
                    for key, value in row.items()
                }
            )


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def write_summary_txt(path, summaries, version_a_mean, version_a_best):
    lines = [
        "Version A baseline",
        f"- best formal mean: {version_a_mean:.3f}",
        f"- best single run: {version_a_best:.0f}",
        "",
        "Scratch grouped statistics",
    ]
    lines.extend(
        markdown_table(
            [
                "algorithm",
                "nproc",
                "mode",
                "count",
                "best",
                "mean",
                "std",
                "avg_time",
                "beats_version_a_mean",
                "beats_version_a_best",
                "mean_improvement_vs_version_a",
                "best_improvement_vs_version_a",
            ],
            [
                [
                    row["algorithm"],
                    str(row["nproc"]),
                    row["mode"],
                    str(row["count"]),
                    f"{row['best']:.0f}",
                    f"{row['mean']:.3f}",
                    f"{row['std']:.3f}",
                    f"{row['avg_time']:.6f}",
                    row["beats_version_a_mean"],
                    row["beats_version_a_best"],
                    f"{row['mean_improvement_vs_version_a']:.3f}%",
                    f"{row['best_improvement_vs_version_a']:.3f}%",
                ]
                for row in summaries
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def default_paths(argv):
    input_path = Path(argv[1]) if len(argv) > 1 else ROOT / "results" / "scratch_experiment_results.csv"
    summary_csv = Path(argv[2]) if len(argv) > 2 else ROOT / "results" / "scratch_analysis_summary.csv"
    summary_txt = Path(argv[3]) if len(argv) > 3 else ROOT / "results" / "scratch_analysis_summary.txt"
    return input_path, summary_csv, summary_txt


def main(argv):
    input_path, summary_csv, summary_txt = default_paths(argv)
    version_a_mean, version_a_best = read_version_a_baseline()
    rows = read_rows(input_path)
    summaries = summarize(rows, version_a_mean, version_a_best)
    write_summary_csv(summary_csv, summaries)
    write_summary_txt(summary_txt, summaries, version_a_mean, version_a_best)
    print((Path(summary_txt).read_text(encoding="utf-8")), end="")


if __name__ == "__main__":
    main(sys.argv)
