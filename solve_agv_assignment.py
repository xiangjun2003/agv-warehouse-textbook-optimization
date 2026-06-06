from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np

from algorithms.primal_dual_lp import solve_lp_primal_dual
from warehouse_data import distance_matrix, load_data


def build_agv_assignment_lp(
    seed: int = 0,
    sample_prob: float = 0.6,
    max_agvs: int | None = 12,
):
    data = load_data(agv_sample_prob=sample_prob, seed=seed, max_agvs=max_agvs)
    agvs = data.agvs
    pallets = data.pallets
    workstations = data.workstations
    c_agv_pallet = distance_matrix(agvs, pallets)
    c_pallet_ws = distance_matrix(pallets, workstations)
    i_count, j_count = c_agv_pallet.shape
    _, k_count = c_pallet_ws.shape

    x_count = i_count * j_count
    y_count = j_count * k_count
    slack_x_count = j_count
    slack_y_count = j_count
    slack_w_count = k_count
    var_count = x_count + y_count + slack_x_count + slack_y_count + slack_w_count
    row_count = i_count + j_count + j_count + k_count + j_count

    x0 = 0
    y0 = x0 + x_count
    sx0 = y0 + y_count
    sy0 = sx0 + slack_x_count
    sw0 = sy0 + slack_y_count

    c = np.zeros(var_count)
    c[x0:y0] = c_agv_pallet.reshape(-1)
    c[y0:sx0] = c_pallet_ws.reshape(-1)
    A = np.zeros((row_count, var_count))
    b = np.zeros(row_count)

    row = 0
    for i in range(i_count):
        A[row, x0 + i * j_count : x0 + (i + 1) * j_count] = 1.0
        b[row] = 1.0
        row += 1

    for j in range(j_count):
        A[row, x0 + j : y0 : j_count] = 1.0
        A[row, sx0 + j] = 1.0
        b[row] = 1.0
        row += 1

    for j in range(j_count):
        A[row, y0 + j * k_count : y0 + (j + 1) * k_count] = 1.0
        A[row, sy0 + j] = 1.0
        b[row] = 1.0
        row += 1

    for k in range(k_count):
        A[row, y0 + k : sx0 : k_count] = 1.0
        A[row, sw0 + k] = 1.0
        b[row] = 3.0
        row += 1

    for j in range(j_count):
        A[row, x0 + j : y0 : j_count] = 1.0
        A[row, y0 + j * k_count : y0 + (j + 1) * k_count] = -1.0
        row += 1

    slices = {
        "x": slice(x0, y0),
        "y": slice(y0, sx0),
        "sx": slice(sx0, sy0),
        "sy": slice(sy0, sw0),
        "sw": slice(sw0, var_count),
    }
    return data, c, A, b, c_agv_pallet, c_pallet_ws, slices


def recover_integer_assignment(
    x_relaxed: np.ndarray,
    y_relaxed: np.ndarray,
    c_agv_pallet: np.ndarray,
    c_pallet_ws: np.ndarray,
):
    i_count, j_count = c_agv_pallet.shape
    k_count = c_pallet_ws.shape[1]
    used_pallets: set[int] = set()
    station_load = np.zeros(k_count, dtype=int)
    assignments: list[tuple[int, int, int, float]] = []

    agv_order = np.argsort(-np.max(x_relaxed, axis=1))
    for i in agv_order:
        pallet_order = np.lexsort((c_agv_pallet[i], -x_relaxed[i]))
        chosen_pallet = None
        for j in pallet_order:
            if int(j) not in used_pallets:
                chosen_pallet = int(j)
                break
        if chosen_pallet is None:
            raise RuntimeError("not enough unused pallets for AGV assignment")

        station_order = np.lexsort((c_pallet_ws[chosen_pallet], -y_relaxed[chosen_pallet]))
        chosen_station = None
        for k in station_order:
            if station_load[int(k)] < 3:
                chosen_station = int(k)
                break
        if chosen_station is None:
            raise RuntimeError("workstation capacity is insufficient")

        used_pallets.add(chosen_pallet)
        station_load[chosen_station] += 1
        cost = float(c_agv_pallet[i, chosen_pallet] + c_pallet_ws[chosen_pallet, chosen_station])
        assignments.append((int(i), chosen_pallet, chosen_station, cost))

    assignments.sort(key=lambda row: row[0])
    return assignments, station_load


def solve_agv_assignment(
    seed: int = 0,
    sample_prob: float = 0.6,
    max_agvs: int | None = 12,
    verbose: bool = False,
):
    data, c, A, b, c1, c2, slices = build_agv_assignment_lp(
        seed,
        sample_prob,
        max_agvs,
    )
    start = time.perf_counter()
    result = solve_lp_primal_dual(
        c,
        A,
        b,
        max_iter=90,
        tol=1e-7,
        regularization=1e-8,
        verbose=verbose,
    )
    elapsed = time.perf_counter() - start
    i_count, j_count = c1.shape
    k_count = c2.shape[1]
    x = result.x[slices["x"]].reshape(i_count, j_count)
    y = result.x[slices["y"]].reshape(j_count, k_count)
    assignments, station_load = recover_integer_assignment(x, y, c1, c2)
    integer_cost = float(sum(row[3] for row in assignments))
    return data, result, assignments, station_load, integer_cost, elapsed


def write_assignment(path: Path, assignments: list[tuple[int, int, int, float]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["agv_index", "pallet_index", "workstation_index", "cost"])
        for row in assignments:
            writer.writerow([row[0], row[1], row[2], f"{row[3]:.8f}"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sample-prob", type=float, default=0.6)
    parser.add_argument("--max-agvs", type=int, default=12)
    parser.add_argument("--output", default="results/agv_assignment.csv")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    data, result, assignments, station_load, integer_cost, elapsed = solve_agv_assignment(
        seed=args.seed,
        sample_prob=args.sample_prob,
        max_agvs=args.max_agvs,
        verbose=args.verbose,
    )
    write_assignment(Path(args.output), assignments)
    print("AGV assignment without COPT")
    print(
        f"agvs={len(data.agvs)} pallets={len(data.pallets)} "
        f"workstations={len(data.workstations)}"
    )
    print(
        f"status={result.status} iterations={result.iterations} "
        f"time={elapsed:.3f}s"
    )
    print(
        f"lp_objective={result.objective:.6f} "
        f"rounded_integer_cost={integer_cost:.6f}"
    )
    print(
        f"residuals: primal={result.primal_residual:.2e} "
        f"dual={result.dual_residual:.2e} gap={result.gap:.2e}"
    )
    print(f"station_load={station_load.tolist()}")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
