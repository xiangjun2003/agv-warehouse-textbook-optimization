from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np

from algorithms.primal_dual_lp import solve_lp_primal_dual
from warehouse_data import distance_matrix, load_data


def build_dynamic_partition_lp(alpha: float = 0.6):
    data = load_data(agv_sample_prob=None)
    pallets = data.pallets
    workstations = data.workstations
    quantities = data.pallet_quantities
    distances = distance_matrix(pallets, workstations)
    j_count, k_count = distances.shape
    z_count = j_count * k_count
    surplus_count = k_count
    var_count = z_count + surplus_count
    row_count = j_count + k_count

    c = np.zeros(var_count)
    c[:z_count] = distances.reshape(-1)
    A = np.zeros((row_count, var_count))
    b = np.zeros(row_count)

    for j in range(j_count):
        A[j, j * k_count : (j + 1) * k_count] = 1.0
        b[j] = quantities[j]

    total_quantity = float(np.sum(quantities))
    min_station_load = alpha * total_quantity / k_count
    for k in range(k_count):
        row = j_count + k
        A[row, k:z_count:k_count] = 1.0
        A[row, z_count + k] = -1.0
        b[row] = min_station_load

    return data, c, A, b, distances


def solve_dynamic_partition(alpha: float = 0.6, verbose: bool = False):
    data, c, A, b, distances = build_dynamic_partition_lp(alpha)
    start = time.perf_counter()
    result = solve_lp_primal_dual(
        c,
        A,
        b,
        max_iter=80,
        tol=1e-7,
        verbose=verbose,
    )
    elapsed = time.perf_counter() - start
    j_count, k_count = distances.shape
    z = result.x[: j_count * k_count].reshape(j_count, k_count)
    loads = z.sum(axis=0)
    objective = float(np.sum(distances * z))
    return data, result, z, loads, objective, elapsed


def write_assignment(path: Path, z: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["pallet_index", "workstation_index", "quantity"])
        for j in range(z.shape[0]):
            for k in range(z.shape[1]):
                if z[j, k] > 1e-5:
                    writer.writerow([j, k, f"{z[j, k]:.8f}"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--alpha", type=float, default=0.6)
    parser.add_argument("--output", default="results/dynamic_partition.csv")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    data, result, z, loads, objective, elapsed = solve_dynamic_partition(
        alpha=args.alpha,
        verbose=args.verbose,
    )
    write_assignment(Path(args.output), z)
    print("Dynamic partition without COPT")
    print(f"pallets={len(data.pallets)} workstations={len(data.workstations)}")
    print(
        f"status={result.status} iterations={result.iterations} "
        f"time={elapsed:.3f}s"
    )
    print(
        f"objective={objective:.6f} min_load={loads.min():.6f} "
        f"max_load={loads.max():.6f}"
    )
    print(
        f"residuals: primal={result.primal_residual:.2e} "
        f"dual={result.dual_residual:.2e} gap={result.gap:.2e}"
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
