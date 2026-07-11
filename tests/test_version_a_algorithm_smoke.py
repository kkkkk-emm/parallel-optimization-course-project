import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
VERIFIER = ROOT / "scripts" / "verify_version_a_tours.py"


def have_tool(name):
    return shutil.which(name) is not None


def mpi_compile_command(source: Path, output: Path):
    mpicc = shutil.which("mpicc")
    if mpicc:
        return [mpicc, "-std=c11", "-O2", "-Wall", "-Wextra", str(source), "-lm", "-o", str(output)]
    inc = os.environ.get("MSMPI_INC")
    lib = os.environ.get("MSMPI_LIB64")
    if have_tool("gcc") and inc and lib:
        return [
            "gcc",
            "-std=c11",
            "-O2",
            "-Wall",
            "-Wextra",
            f"-I{inc.rstrip(os.sep)}",
            str(source),
            f"-L{lib.rstrip(os.sep)}",
            "-lmsmpi",
            "-lm",
            "-o",
            str(output),
        ]
    return None


def write_tiny_tsp(path: Path):
    coords = [
        (0, 0),
        (10, 0),
        (20, 0),
        (20, 10),
        (20, 20),
        (10, 20),
        (0, 20),
        (0, 10),
    ]
    lines = [str(len(coords))]
    lines.extend(f"{idx} {x} {y}" for idx, (x, y) in enumerate(coords, start=1))
    lines.append("EOF")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_one_row(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as fp:
        rows = list(csv.DictReader(fp))
    assert len(rows) == 1
    return rows[0]


def run_checked(command, cwd=ROOT):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr + result.stdout
    return result


@pytest.mark.skipif(not have_tool("gcc"), reason="gcc is required for C smoke tests")
def test_serial_tiny_tsp_same_seed_regression_and_tour_verification(tmp_path):
    tsp = tmp_path / "tiny8.tsp"
    write_tiny_tsp(tsp)
    exe = tmp_path / "serial.exe"
    run_checked(["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", str(SRC / "tsp_serial_exp.c"), "-lm", "-o", str(exe)])

    csv1 = tmp_path / "serial1.csv"
    csv2 = tmp_path / "serial2.csv"
    tour_dir = tmp_path / "tours"
    tour_dir.mkdir()
    tour = tour_dir / "best_SERIAL_n1_seed777.tour"
    run_checked([str(exe), str(tsp), "20", "777", str(csv1), "8", str(tour)])
    run_checked([str(exe), str(tsp), "20", "777", str(csv2), "8"])

    row1 = read_one_row(csv1)
    row2 = read_one_row(csv2)
    assert row1["global_best"] == row2["global_best"]

    result = run_checked(
        [
            sys.executable,
            str(VERIFIER),
            "--data",
            str(tsp),
            "--results",
            str(csv1),
            "--tour-dir",
            str(tour_dir),
        ]
    )
    assert "VERSION_A_TOUR_VERIFY_OK" in result.stdout
    assert "verified_tours=1" in result.stdout


@pytest.mark.skipif(not have_tool("mpiexec"), reason="mpiexec is required for MPI smoke tests")
def test_mpi_tiny_tsp_migration_group_mapping_and_moving_rotation(tmp_path):
    if not have_tool("gcc") and not shutil.which("mpicc"):
        pytest.skip("a C compiler is required for MPI smoke tests")
    tsp = tmp_path / "tiny8.tsp"
    write_tiny_tsp(tsp)
    tour_dir = tmp_path / "tours"
    tour_dir.mkdir()

    programs = {
        "DEA": (SRC / "tsp_mpi_dea.c", tmp_path / "dea.exe"),
        "HDEA": (SRC / "tsp_mpi_hdea.c", tmp_path / "hdea.exe"),
        "MOVING_HDEA": (SRC / "tsp_mpi_moving_hdea.c", tmp_path / "moving.exe"),
    }
    for source, exe in programs.values():
        command = mpi_compile_command(source, exe)
        if command is None:
            pytest.skip("MPI compiler configuration is unavailable")
        run_checked(command)

    dea_csv = tmp_path / "dea.csv"
    hdea_csv = tmp_path / "hdea.csv"
    moving_csv = tmp_path / "moving.csv"
    dea_tour = tour_dir / "best_DEA_n4_seed888.tour"
    hdea_tour = tour_dir / "best_HDEA_n4_seed888.tour"
    moving_tour = tour_dir / "best_MOVING_HDEA_n4_seed888.tour"

    dea = run_checked(
        [
            "mpiexec",
            "-n",
            "4",
            str(programs["DEA"][1]),
            str(tsp),
            "4",
            "1",
            "888",
            str(dea_csv),
            "5",
            str(dea_tour),
            "--log-migration",
        ]
    )
    assert "migration generation" in dea.stdout

    hdea = run_checked(
        [
            "mpiexec",
            "-n",
            "4",
            str(programs["HDEA"][1]),
            str(tsp),
            "4",
            "1",
            "2",
            "2",
            "888",
            str(hdea_csv),
            "5",
            str(hdea_tour),
            "--verbose",
            "--log-migration",
        ]
    )
    assert "group_id=0 local_id=0" in hdea.stdout
    assert "global migration" in hdea.stdout

    moving = run_checked(
        [
            "mpiexec",
            "-n",
            "4",
            str(programs["MOVING_HDEA"][1]),
            str(tsp),
            "4",
            "1",
            "1",
            "2",
            "888",
            str(moving_csv),
            "5",
            str(moving_tour),
            "--log-migration",
        ]
    )
    assert "local migration plan" in moving.stdout
    assert "global moving colony" in moving.stdout

    combined = tmp_path / "mpi_results.csv"
    rows = [read_one_row(path) for path in [dea_csv, hdea_csv, moving_csv]]
    fieldnames = [
        "algorithm",
        "nproc",
        "maxGen",
        "migration_interval",
        "local_to_global_ratio",
        "num_groups",
        "base_seed",
        "global_best",
        "elapsed_sec",
    ]
    with combined.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "0") for key in fieldnames})

    result = run_checked(
        [
            sys.executable,
            str(VERIFIER),
            "--data",
            str(tsp),
            "--results",
            str(combined),
            "--tour-dir",
            str(tour_dir),
        ]
    )
    assert "VERSION_A_TOUR_VERIFY_OK" in result.stdout
    assert "verified_tours=3" in result.stdout
