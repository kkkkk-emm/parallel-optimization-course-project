import csv
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "pcb442.tsp"
RESULTS_PATH = ROOT / "results" / "scratch_experiment_results.csv"
SUMMARY_PATH = ROOT / "results" / "scratch_analysis_summary.csv"
TOUR_DIR = ROOT / "results" / "scratch_best_tours"
OFFICIAL_OPTIMUM = 50778


def read_tsp(path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError(f"{path} is empty")
    n = int(lines[0].strip())
    coords = []
    for line_no, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        if len(coords) == n:
            break
        if line.strip().upper() == "EOF":
            break
        parts = line.split()
        if len(parts) < 3:
            raise ValueError(f"bad city row at line {line_no}: {line}")
        coords.append((float(parts[1]), float(parts[2])))
    if len(coords) != n:
        raise ValueError(f"expected {n} city rows, got {len(coords)}")
    return coords


def build_distances(coords):
    n = len(coords)
    dist = [[0] * n for _ in range(n)]
    for i, (xi, yi) in enumerate(coords):
        for j, (xj, yj) in enumerate(coords):
            if i == j:
                continue
            dist[i][j] = int(math.sqrt((xi - xj) ** 2 + (yi - yj) ** 2) + 0.5)
    return dist


def read_results(path):
    with path.open(newline="", encoding="utf-8-sig") as fp:
        rows = list(csv.DictReader(fp))
    if not rows:
        raise ValueError(f"{path} has no result rows")
    return rows


def read_summary(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fp:
        return list(csv.DictReader(fp))


def expected_best_rows(rows):
    grouped = {}
    for row in rows:
        key = (row["algorithm"], row["mode"], row["nproc"])
        grouped.setdefault(key, []).append(row)
    expected = {}
    for key, group_rows in grouped.items():
        expected[key] = min(group_rows, key=lambda row: (int(float(row["best_length"])), int(row["seed"])))
    return expected


def read_tour_file(path):
    metadata = {}
    values = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            payload = stripped[1:].strip()
            if "=" in payload:
                key, value = payload.split("=", 1)
                metadata[key.strip()] = value.strip()
            continue
        values.extend(int(part) for part in stripped.split())
    return metadata, values


def closed_tour_length(tour_zero_based, dist):
    total = 0
    n = len(tour_zero_based)
    for i in range(n - 1):
        total += dist[tour_zero_based[i]][tour_zero_based[i + 1]]
    total += dist[tour_zero_based[-1]][tour_zero_based[0]]
    return total


def verify_one(path, row, dist, city_count):
    metadata, tour_one_based = read_tour_file(path)
    if len(tour_one_based) != city_count:
        raise ValueError(f"{path.name}: expected {city_count} cities, got {len(tour_one_based)}")
    if sorted(tour_one_based) != list(range(1, city_count + 1)):
        raise ValueError(f"{path.name}: tour is not a permutation of 1..{city_count}")

    expected_length = int(float(row["best_length"]))
    metadata_length = int(metadata.get("best_length", "-1"))
    if metadata_length != expected_length:
        raise ValueError(f"{path.name}: metadata best_length {metadata_length} != CSV {expected_length}")

    tour_zero_based = [city - 1 for city in tour_one_based]
    recalculated = closed_tour_length(tour_zero_based, dist)
    if recalculated != expected_length:
        raise ValueError(f"{path.name}: recalculated length {recalculated} != CSV {expected_length}")

    return {
        "file": path.name,
        "algorithm": row["algorithm"],
        "mode": row["mode"],
        "nproc": row["nproc"],
        "seed": row["seed"],
        "city_count": city_count,
        "csv_best_length": expected_length,
        "recalculated_length": recalculated,
        "closed_edge_checked": "yes",
    }


def main():
    coords = read_tsp(DATA_PATH)
    dist = build_distances(coords)
    rows = read_results(RESULTS_PATH)
    expected = expected_best_rows(rows)

    verified = []
    for key, row in sorted(expected.items(), key=lambda item: (item[0][1], int(item[0][2]))):
        algorithm, mode, nproc = key
        tour_path = TOUR_DIR / f"best_{algorithm}_{mode}_n{nproc}.tour"
        if not tour_path.exists():
            raise FileNotFoundError(f"missing best tour file: {tour_path}")
        verified.append(verify_one(tour_path, row, dist, len(coords)))

    summary_rows = [row for row in read_summary(SUMMARY_PATH) if row.get("record_type") == "summary"]
    best_length = min(item["csv_best_length"] for item in verified)
    best_mean = min((float(row["mean"]) for row in summary_rows), default=float("nan"))
    best_gap = (best_length - OFFICIAL_OPTIMUM) / OFFICIAL_OPTIMUM * 100.0
    mean_gap = (best_mean - OFFICIAL_OPTIMUM) / OFFICIAL_OPTIMUM * 100.0

    print("SCRATCH_TOUR_VERIFY_OK")
    print(f"verified_configs={len(verified)}")
    print(f"official_optimum={OFFICIAL_OPTIMUM}")
    print(f"version_b_best={best_length}")
    print(f"optimality_gap_pct={best_gap:.2f}")
    print(f"version_b_best_formal_mean={best_mean:.3f}")
    print(f"mean_gap_pct={mean_gap:.2f}")
    for item in verified:
        print(
            "{file}: algorithm={algorithm} mode={mode} nproc={nproc} seed={seed} "
            "cities={city_count} length={recalculated_length} closed_edge_checked={closed_edge_checked}".format(
                **item
            )
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SCRATCH_TOUR_VERIFY_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
