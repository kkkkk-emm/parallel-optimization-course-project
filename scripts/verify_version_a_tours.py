import argparse
import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_tsp(path):
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError(f"{path} is empty")
    city_count = int(lines[0].strip().split()[0])
    coords = []
    for raw in lines[1:]:
        text = raw.strip()
        if not text or text.upper() == "EOF":
            continue
        parts = text.split()
        if len(parts) < 3:
            continue
        coords.append((float(parts[1]), float(parts[2])))
        if len(coords) == city_count:
            break
    if len(coords) != city_count:
        raise ValueError(f"{path}: expected {city_count} coordinates, got {len(coords)}")
    return coords


def build_dist(coords):
    dist = []
    for x1, y1 in coords:
        row = []
        for x2, y2 in coords:
            dx = x1 - x2
            dy = y1 - y2
            row.append(int(math.sqrt(dx * dx + dy * dy) + 0.5))
        dist.append(row)
    return dist


def read_results(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as fp:
        rows = list(csv.DictReader(fp))
    by_key = {}
    for row in rows:
        key = (row["algorithm"], int(row["nproc"]), int(row["base_seed"]))
        by_key[key] = float(row["global_best"])
    return by_key


def read_tour_file(path):
    metadata = {}
    tour_values = []
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        text = raw.strip()
        if not text:
            continue
        if text.startswith("#"):
            body = text[1:].strip()
            if "=" in body:
                key, value = body.split("=", 1)
                metadata[key.strip()] = value.strip()
            continue
        tour_values.extend(int(part) for part in text.split())
    return metadata, tour_values


def closed_tour_length(tour_zero_based, dist):
    total = 0
    for idx, city in enumerate(tour_zero_based):
        nxt = tour_zero_based[(idx + 1) % len(tour_zero_based)]
        total += dist[city][nxt]
    return total


def parse_key(metadata, path):
    try:
        return (
            metadata["algorithm"],
            int(metadata["nproc"]),
            int(metadata["seed"]),
        )
    except KeyError as exc:
        raise ValueError(f"{path.name}: missing metadata {exc.args[0]}") from exc


def verify_one(path, result_by_key, dist, city_count):
    metadata, tour_one_based = read_tour_file(path)
    if len(tour_one_based) != city_count:
        raise ValueError(f"{path.name}: expected {city_count} cities, got {len(tour_one_based)}")
    if sorted(tour_one_based) != list(range(1, city_count + 1)):
        raise ValueError(f"{path.name}: tour is not a permutation of 1..{city_count}")
    key = parse_key(metadata, path)
    if key not in result_by_key:
        raise ValueError(f"{path.name}: no matching result row for {key}")
    expected = int(round(result_by_key[key]))
    if "best_length" in metadata:
        meta_length = int(round(float(metadata["best_length"])))
        if meta_length != expected:
            raise ValueError(f"{path.name}: metadata best_length {meta_length} != result {expected}")
    tour_zero_based = [city - 1 for city in tour_one_based]
    recalculated = closed_tour_length(tour_zero_based, dist)
    if recalculated != expected:
        raise ValueError(f"{path.name}: recalculated {recalculated} != result {expected}")
    return {
        "file": path.name,
        "algorithm": key[0],
        "nproc": key[1],
        "seed": key[2],
        "best_length": expected,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Verify saved Version A best tour files.")
    parser.add_argument("--data", default=str(ROOT / "data" / "pcb442.tsp"))
    parser.add_argument("--results", default=str(ROOT / "results" / "final_experiment_results.csv"))
    parser.add_argument("--tour-dir", default=str(ROOT / "results" / "version_a_best_tours"))
    return parser.parse_args()


def main():
    args = parse_args()
    tour_dir = Path(args.tour_dir)
    if not tour_dir.exists():
        raise FileNotFoundError(f"missing tour directory: {tour_dir}")
    coords = read_tsp(args.data)
    dist = build_dist(coords)
    result_by_key = read_results(args.results)
    tour_files = sorted(tour_dir.glob("best_*.tour"))
    if not tour_files:
        raise FileNotFoundError(f"no best_*.tour files in {tour_dir}")
    verified = [verify_one(path, result_by_key, dist, len(coords)) for path in tour_files]
    print("VERSION_A_TOUR_VERIFY_OK")
    print(f"verified_tours={len(verified)}")
    print(f"best_verified_length={min(item['best_length'] for item in verified)}")
    for item in verified:
        print(
            "{file}: algorithm={algorithm} nproc={nproc} seed={seed} best_length={best_length}".format(
                **item
            )
        )


if __name__ == "__main__":
    main()
