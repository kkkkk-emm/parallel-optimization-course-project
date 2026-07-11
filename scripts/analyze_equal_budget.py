import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_COLUMNS = {
    "algorithm",
    "nproc",
    "maxGen",
    "migration_interval",
    "local_to_global_ratio",
    "num_groups",
    "local_colony_size",
    "total_colony_size",
    "base_seed",
    "global_best",
    "elapsed_sec",
}


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
                "maxGen": int(row["maxGen"]),
                "migration_interval": int(row["migration_interval"]),
                "local_to_global_ratio": int(row["local_to_global_ratio"]),
                "num_groups": int(row["num_groups"]),
                "local_colony_size": int(row["local_colony_size"]),
                "total_colony_size": int(row["total_colony_size"]),
                "base_seed": int(row["base_seed"]),
                "global_best": float(row["global_best"]),
                "elapsed_sec": float(row["elapsed_sec"]),
            }
            if parsed["global_best"] <= 0 or not math.isfinite(parsed["global_best"]):
                raise ValueError(f"invalid global_best on line {line_no}")
            key = (parsed["algorithm"], parsed["nproc"], parsed["base_seed"])
            if key in seen:
                raise ValueError(f"duplicate row on line {line_no}: {key}")
            seen.add(key)
            rows.append(parsed)
    return rows


def label(row):
    return f"{row['algorithm']} n={row['nproc']} local={row['local_colony_size']}"


def sample_std(values):
    return statistics.stdev(values) if len(values) > 1 else 0.0


def summarize(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[label(row)].append(row)
    serial_mean = None
    for key, group in grouped.items():
        if key.startswith("SERIAL "):
            serial_mean = statistics.mean(row["global_best"] for row in group)
            break

    summaries = []
    for key, group in sorted(grouped.items()):
        values = [row["global_best"] for row in group]
        times = [row["elapsed_sec"] for row in group]
        first = group[0]
        mean_value = statistics.mean(values)
        improvement = 0.0 if serial_mean is None else (serial_mean - mean_value) / serial_mean * 100.0
        summaries.append(
            {
                "record_type": "summary",
                "label": key,
                "algorithm": first["algorithm"],
                "nproc": first["nproc"],
                "maxGen": first["maxGen"],
                "migration_interval": first["migration_interval"],
                "local_colony_size": first["local_colony_size"],
                "total_colony_size": first["total_colony_size"],
                "count": len(group),
                "best": min(values),
                "mean": mean_value,
                "std": sample_std(values),
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
                "avg_time": statistics.mean(times),
                "time_median": statistics.median(times),
                "improvement_vs_equal_budget_serial_mean_pct": improvement,
            }
        )
    return summaries


def fmt(value):
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_csv(path, summaries):
    fieldnames = [
        "record_type",
        "label",
        "algorithm",
        "nproc",
        "maxGen",
        "migration_interval",
        "local_colony_size",
        "total_colony_size",
        "count",
        "best",
        "mean",
        "std",
        "median",
        "min",
        "max",
        "avg_time",
        "time_median",
        "improvement_vs_equal_budget_serial_mean_pct",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in summaries:
            writer.writerow({key: fmt(row[key]) for key in fieldnames})


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def write_txt(path, summaries):
    lines = [
        "Equal-budget experiment summary",
        "",
        "All configurations use total_colony_size=100. This checks algorithmic structure under a fixed total population budget, not scale-out resource growth.",
        "",
    ]
    lines.extend(
        markdown_table(
            [
                "label",
                "count",
                "best",
                "mean",
                "std",
                "median",
                "avg_time",
                "improvement_vs_serial_mean",
            ],
            [
                [
                    row["label"],
                    str(row["count"]),
                    f"{row['best']:.0f}",
                    f"{row['mean']:.3f}",
                    f"{row['std']:.3f}",
                    f"{row['median']:.3f}",
                    f"{row['avg_time']:.6f}",
                    f"{row['improvement_vs_equal_budget_serial_mean_pct']:.3f}%",
                ]
                for row in summaries
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def default_paths(argv):
    input_path = Path(argv[1]) if len(argv) > 1 else ROOT / "results" / "equal_budget_results.csv"
    output_csv = Path(argv[2]) if len(argv) > 2 else ROOT / "results" / "equal_budget_summary.csv"
    output_txt = Path(argv[3]) if len(argv) > 3 else ROOT / "results" / "equal_budget_summary.txt"
    return input_path, output_csv, output_txt


def main(argv):
    input_path, output_csv, output_txt = default_paths(argv)
    summaries = summarize(read_rows(input_path))
    write_csv(output_csv, summaries)
    write_txt(output_txt, summaries)
    print(Path(output_txt).read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main(sys.argv)
