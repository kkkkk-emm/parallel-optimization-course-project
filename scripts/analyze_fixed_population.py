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
    "migration_comm_sec",
    "final_collective_comm_sec",
    "mpi_comm_sec",
    "computation_sec",
    "comm_ratio",
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
                "migration_comm_sec": float(row["migration_comm_sec"]),
                "final_collective_comm_sec": float(row["final_collective_comm_sec"]),
                "mpi_comm_sec": float(row["mpi_comm_sec"]),
                "computation_sec": float(row["computation_sec"]),
                "comm_ratio": float(row["comm_ratio"]),
            }
            if parsed["global_best"] <= 0 or not math.isfinite(parsed["global_best"]):
                raise ValueError(f"invalid global_best on line {line_no}")
            if parsed["elapsed_sec"] <= 0 or not math.isfinite(parsed["elapsed_sec"]):
                raise ValueError(f"invalid elapsed_sec on line {line_no}")
            if parsed["total_colony_size"] != parsed["nproc"] * parsed["local_colony_size"]:
                raise ValueError(f"total_colony_size mismatch on line {line_no}")
            key = (
                parsed["algorithm"],
                parsed["nproc"],
                parsed["local_colony_size"],
                parsed["base_seed"],
            )
            if key in seen:
                raise ValueError(f"duplicate row on line {line_no}: {key}")
            seen.add(key)
            rows.append(parsed)
    return rows


def group_key(row):
    return (
        row["algorithm"],
        row["nproc"],
        row["migration_interval"],
        row["local_to_global_ratio"],
        row["num_groups"],
        row["local_colony_size"],
        row["total_colony_size"],
    )


def label_from_key(key):
    algorithm, nproc, _migration_interval, _ratio, _groups, local_colony_size, total_colony_size = key
    return f"{algorithm} n={nproc} local={local_colony_size} total={total_colony_size}"


def sample_std(values):
    return statistics.stdev(values) if len(values) > 1 else 0.0


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[group_key(row)].append(row)

    serial_groups = [group for key, group in groups.items() if key[0] == "SERIAL" and key[1] == 1]
    if len(serial_groups) != 1:
        raise ValueError("expected exactly one SERIAL n=1 group")
    serial_values = [row["global_best"] for row in serial_groups[0]]
    serial_times = [row["elapsed_sec"] for row in serial_groups[0]]
    serial_mean = statistics.mean(serial_values)
    serial_avg_time = statistics.mean(serial_times)

    summaries = []
    for key in sorted(groups, key=lambda item: (item[1], item[0], item[5])):
        group = groups[key]
        values = [row["global_best"] for row in group]
        times = [row["elapsed_sec"] for row in group]
        migration_comm = [row["migration_comm_sec"] for row in group]
        final_comm = [row["final_collective_comm_sec"] for row in group]
        mpi_comm = [row["mpi_comm_sec"] for row in group]
        computation = [row["computation_sec"] for row in group]
        comm_ratio = [row["comm_ratio"] for row in group]
        first = group[0]
        mean_value = statistics.mean(values)
        avg_time = statistics.mean(times)
        speedup = serial_avg_time / avg_time if avg_time > 0 else math.nan
        efficiency = speedup / first["nproc"] if first["nproc"] > 0 else math.nan
        improvement = (serial_mean - mean_value) / serial_mean * 100.0
        summaries.append(
            {
                "record_type": "summary",
                "label": label_from_key(key),
                "algorithm": first["algorithm"],
                "nproc": first["nproc"],
                "maxGen": first["maxGen"],
                "migration_interval": first["migration_interval"],
                "local_to_global_ratio": first["local_to_global_ratio"],
                "num_groups": first["num_groups"],
                "local_colony_size": first["local_colony_size"],
                "total_colony_size": first["total_colony_size"],
                "count": len(group),
                "best": min(values),
                "mean": mean_value,
                "std": sample_std(values),
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
                "avg_time": avg_time,
                "time_median": statistics.median(times),
                "avg_migration_comm_sec": statistics.mean(migration_comm),
                "avg_final_collective_comm_sec": statistics.mean(final_comm),
                "avg_mpi_comm_sec": statistics.mean(mpi_comm),
                "avg_computation_sec": statistics.mean(computation),
                "avg_comm_ratio": statistics.mean(comm_ratio),
                "speedup_vs_serial": speedup,
                "efficiency_vs_serial": efficiency,
                "improvement_vs_fixed_serial_mean_pct": improvement,
            }
        )
    return summaries


def fmt(value, digits=6):
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        return f"{value:.{digits}f}"
    return str(value)


def write_csv(path, summaries):
    fieldnames = [
        "record_type",
        "label",
        "algorithm",
        "nproc",
        "maxGen",
        "migration_interval",
        "local_to_global_ratio",
        "num_groups",
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
        "avg_migration_comm_sec",
        "avg_final_collective_comm_sec",
        "avg_mpi_comm_sec",
        "avg_computation_sec",
        "avg_comm_ratio",
        "speedup_vs_serial",
        "efficiency_vs_serial",
        "improvement_vs_fixed_serial_mean_pct",
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
        "Fixed population experiment summary",
        "",
        "All configurations use total_colony_size=400. This is a stricter fairness check than the formal scale-out experiment: SERIAL uses local_colony_size=400, while DEA distributes the same total population across MPI ranks.",
        "",
        "Solution quality and scalability",
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
                "speedup",
                "efficiency",
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
                    f"{row['speedup_vs_serial']:.3f}",
                    f"{row['efficiency_vs_serial']:.3f}",
                    f"{row['improvement_vs_fixed_serial_mean_pct']:.3f}%",
                ]
                for row in summaries
            ],
        )
    )
    lines.extend(["", "Computation and communication time"])
    lines.extend(
        markdown_table(
            [
                "label",
                "avg_computation_sec",
                "avg_migration_comm_sec",
                "avg_final_collective_comm_sec",
                "avg_mpi_comm_sec",
                "avg_comm_ratio",
            ],
            [
                [
                    row["label"],
                    f"{row['avg_computation_sec']:.6f}",
                    f"{row['avg_migration_comm_sec']:.6f}",
                    f"{row['avg_final_collective_comm_sec']:.6f}",
                    f"{row['avg_mpi_comm_sec']:.6f}",
                    f"{row['avg_comm_ratio']:.6f}",
                ]
                for row in summaries
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def default_paths(argv):
    input_path = Path(argv[1]) if len(argv) > 1 else ROOT / "results" / "fixed_population_results.csv"
    output_csv = Path(argv[2]) if len(argv) > 2 else ROOT / "results" / "fixed_population_summary.csv"
    output_txt = Path(argv[3]) if len(argv) > 3 else ROOT / "results" / "fixed_population_summary.txt"
    return input_path, output_csv, output_txt


def main(argv):
    input_path, output_csv, output_txt = default_paths(argv)
    summaries = summarize(read_rows(input_path))
    write_csv(output_csv, summaries)
    write_txt(output_txt, summaries)
    print(Path(output_txt).read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main(sys.argv)
