from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linprog

from algorithms.admm_lp import solve_lp_admm
from algorithms.augmented_lagrangian import (
    solve_augmented_lagrangian,
    solve_lp_augmented_lagrangian,
)
from algorithms.primal_dual_lp import solve_lp_primal_dual
from solve_agv_assignment import (
    build_agv_assignment_lp,
    recover_integer_assignment,
)
from solve_dynamic_partition import build_dynamic_partition_lp
from solve_warehouse_layout import (
    build_conflict_edges,
    repair_layout,
    solve_warehouse_layout,
)
from warehouse_data import distance_matrix, load_data


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"


def _relative_equality_residual(A: np.ndarray, x: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(A @ x - b) / (1.0 + np.linalg.norm(b)))


def _nonnegative_violation(x: np.ndarray) -> float:
    return float(max(0.0, -float(np.min(x))))


def _row(**kwargs: Any) -> dict[str, Any]:
    return kwargs


def _format_row(row: dict[str, Any]) -> dict[str, Any]:
    formatted: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, float):
            formatted[key] = f"{value:.8g}"
        else:
            formatted[key] = value
    return formatted


def _linprog_dual_simplex(c: np.ndarray, A: np.ndarray, b: np.ndarray):
    start = time.perf_counter()
    result = linprog(
        c,
        A_eq=A,
        b_eq=b,
        bounds=(0.0, None),
        method="highs-ds",
        options={"presolve": True},
    )
    elapsed = time.perf_counter() - start
    return result, elapsed


def benchmark_task1(seed: int = 0) -> list[dict[str, Any]]:
    data, c, A, b, c1, c2, slices = build_agv_assignment_lp(seed=seed)
    i_count, j_count = c1.shape
    k_count = c2.shape[1]
    rows: list[dict[str, Any]] = []

    def summarize_lp(
        algorithm: str,
        chapter: str,
        status: str,
        x: np.ndarray,
        iterations: int,
        elapsed: float,
        *,
        primal_residual: float | None = None,
        dual_residual: float | None = None,
        gap: float | None = None,
        notes: str = "",
    ) -> None:
        x_part = x[slices["x"]].reshape(i_count, j_count)
        y_part = x[slices["y"]].reshape(j_count, k_count)
        assignments, station_load = recover_integer_assignment(x_part, y_part, c1, c2)
        integer_cost = float(sum(row[3] for row in assignments))
        rows.append(
            _row(
                task="task1_agv_assignment",
                algorithm=algorithm,
                textbook_chapter=chapter,
                status=status,
                objective=float(c @ x),
                recovered_objective=integer_cost,
                iterations=iterations,
                time_seconds=elapsed,
                equality_residual=_relative_equality_residual(A, x, b),
                nonnegative_violation=_nonnegative_violation(x),
                primal_residual=primal_residual if primal_residual is not None else "",
                dual_residual=dual_residual if dual_residual is not None else "",
                gap=gap if gap is not None else "",
                selected_or_routes=len(assignments),
                min_load=int(np.min(station_load)),
                max_load=int(np.max(station_load)),
                notes=notes,
            )
        )

    start = time.perf_counter()
    ipm = solve_lp_primal_dual(c, A, b, max_iter=90, tol=1e-7, regularization=1e-8)
    summarize_lp(
        "primal_dual_interior_point",
        "Chapter 7",
        ipm.status,
        ipm.x,
        ipm.iterations,
        time.perf_counter() - start,
        primal_residual=ipm.primal_residual,
        dual_residual=ipm.dual_residual,
        gap=ipm.gap,
        notes="self implemented",
    )

    simplex, elapsed = _linprog_dual_simplex(c, A, b)
    if simplex.x is not None:
        summarize_lp(
            "dual_simplex_highs",
            "linear programming simplex baseline",
            "optimal" if simplex.success else "failed",
            np.asarray(simplex.x, dtype=float),
            int(simplex.nit),
            elapsed,
            notes="SciPy HiGHS dual simplex",
        )

    upper = np.full_like(c, 3.0)
    start = time.perf_counter()
    admm = solve_lp_admm(c, A, b, rho=25.0, max_iter=1200, tol=2e-4, upper=upper)
    summarize_lp(
        "admm_affine_box",
        "Chapter 8",
        admm.status,
        admm.x,
        admm.iterations,
        time.perf_counter() - start,
        primal_residual=admm.primal_residual,
        dual_residual=admm.dual_residual,
        notes="self implemented first-order splitting",
    )

    return rows


def benchmark_task2(alpha: float = 0.6) -> list[dict[str, Any]]:
    data, c, A, b, distances = build_dynamic_partition_lp(alpha=alpha)
    j_count, k_count = distances.shape
    z_count = j_count * k_count
    total_quantity = float(np.sum(data.pallet_quantities))
    rows: list[dict[str, Any]] = []

    def summarize_lp(
        algorithm: str,
        chapter: str,
        status: str,
        x: np.ndarray,
        iterations: int,
        elapsed: float,
        *,
        primal_residual: float | None = None,
        dual_residual: float | None = None,
        gap: float | None = None,
        notes: str = "",
    ) -> None:
        z_raw = x[:z_count].reshape(j_count, k_count)
        z_repaired = np.maximum(0.0, z_raw)
        loads = z_repaired.sum(axis=0)
        raw_transport_objective = float(c @ x)
        repaired_transport_objective = float(np.sum(distances * z_repaired))
        rows.append(
            _row(
                task="task2_dynamic_partition",
                algorithm=algorithm,
                textbook_chapter=chapter,
                status=status,
                objective=raw_transport_objective,
                recovered_objective=repaired_transport_objective,
                iterations=iterations,
                time_seconds=elapsed,
                equality_residual=_relative_equality_residual(A, x, b),
                nonnegative_violation=_nonnegative_violation(x),
                primal_residual=primal_residual if primal_residual is not None else "",
                dual_residual=dual_residual if dual_residual is not None else "",
                gap=gap if gap is not None else "",
                selected_or_routes=int(np.count_nonzero(z_repaired > 1e-5)),
                min_load=float(np.min(loads)),
                max_load=float(np.max(loads)),
                notes=notes,
            )
        )

    start = time.perf_counter()
    ipm = solve_lp_primal_dual(c, A, b, max_iter=80, tol=1e-7)
    summarize_lp(
        "primal_dual_interior_point",
        "Chapter 7",
        ipm.status,
        ipm.x,
        ipm.iterations,
        time.perf_counter() - start,
        primal_residual=ipm.primal_residual,
        dual_residual=ipm.dual_residual,
        gap=ipm.gap,
        notes="self implemented",
    )

    simplex, elapsed = _linprog_dual_simplex(c, A, b)
    if simplex.x is not None:
        summarize_lp(
            "dual_simplex_highs",
            "linear programming simplex baseline",
            "optimal" if simplex.success else "failed",
            np.asarray(simplex.x, dtype=float),
            int(simplex.nit),
            elapsed,
            notes="SciPy HiGHS dual simplex",
        )

    upper = np.full_like(c, total_quantity)
    start = time.perf_counter()
    admm = solve_lp_admm(c, A, b, rho=35.0, max_iter=1500, tol=2e-4, upper=upper)
    summarize_lp(
        "admm_affine_box",
        "Chapter 8",
        admm.status,
        admm.x,
        admm.iterations,
        time.perf_counter() - start,
        primal_residual=admm.primal_residual,
        dual_residual=admm.dual_residual,
        notes="self implemented first-order splitting",
    )

    start = time.perf_counter()
    alm = solve_lp_augmented_lagrangian(
        c,
        A,
        b,
        upper=upper,
        rho0=1.0,
        rho_multiplier=2.0,
        outer_iter=12,
        inner_iter=500,
        tol=2e-4,
        inner_solver="bb",
    )
    summarize_lp(
        "augmented_lagrangian_bb",
        "Chapter 7 + Chapter 6",
        alm.status,
        alm.x,
        alm.inner_iterations,
        time.perf_counter() - start,
        primal_residual=alm.equality_violation,
        notes=f"outer_iterations={alm.outer_iterations}; self implemented",
    )

    return rows


def _min_pair_distance(coords: list[tuple[int, int]], selected: list[int]) -> int:
    selected_coords = [coords[i] for i in selected]
    matrix = distance_matrix(selected_coords, selected_coords)
    return int(
        min(
            matrix[i, j]
            for i in range(len(selected_coords))
            for j in range(i + 1, len(selected_coords))
        )
    )


def benchmark_task3(seed: int = 0) -> list[dict[str, Any]]:
    choose_count = 10
    min_distance = 6
    data = load_data(agv_sample_prob=None)
    pallets = data.pallets
    quantities = data.pallet_quantities
    edges = build_conflict_edges(pallets, min_distance)
    edge_i = np.asarray([i for i, _ in edges], dtype=int)
    edge_j = np.asarray([j for _, j in edges], dtype=int)
    scores = quantities / max(float(np.max(quantities)), 1.0)
    tie_break_weight = 1e-3
    rows: list[dict[str, Any]] = []

    def layout_row(
        algorithm: str,
        chapter: str,
        status: str,
        relaxed: np.ndarray,
        selected: list[int],
        iterations: int,
        elapsed: float,
        equality_violation: float,
        inequality_violation: float,
        notes: str,
    ) -> None:
        min_pair = _min_pair_distance(pallets, selected)
        selected_score = float(scores[selected].sum())
        rows.append(
            _row(
                task="task3_cache_location",
                algorithm=algorithm,
                textbook_chapter=chapter,
                status=status,
                objective=-tie_break_weight * float(scores @ relaxed),
                recovered_objective=selected_score,
                iterations=iterations,
                time_seconds=elapsed,
                equality_residual=equality_violation,
                nonnegative_violation=_nonnegative_violation(relaxed),
                primal_residual=equality_violation,
                dual_residual="",
                gap="",
                selected_or_routes=len(selected),
                min_load=min_pair,
                max_load="",
                notes=notes,
            )
        )

    for inner_solver, label, chapter in [
        ("bb", "quadratic_penalty_projected_bb", "Chapter 7 + Chapter 6"),
        ("pg", "quadratic_penalty_projected_gradient", "Chapter 7 + Chapter 6"),
        ("nesterov", "quadratic_penalty_nesterov", "Chapter 7 + Chapter 8"),
    ]:
        data_i, result, selected, _, _, elapsed = solve_warehouse_layout(
            choose_count=choose_count,
            min_distance=min_distance,
            seed=seed,
            inner_solver=inner_solver,
        )
        inner_iterations = int(
            sum(item.get("inner_iterations", 0.0) for item in result.history)
        )
        layout_row(
            label,
            chapter,
            result.status,
            result.x,
            selected,
            inner_iterations,
            elapsed,
            result.equality_violation,
            result.inequality_violation,
            f"outer_iterations={result.outer_iterations}; selected_min_distance>{min_distance}",
        )

    rng = np.random.default_rng(seed)
    x0 = np.full(len(pallets), choose_count / len(pallets), dtype=float) + 0.02 * rng.random(len(pallets))
    x0 = np.clip(x0, 0.0, 1.0)

    def objective_grad(x: np.ndarray) -> tuple[float, np.ndarray]:
        return -tie_break_weight * float(scores @ x), -tie_break_weight * scores

    def residuals(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        h = np.asarray([float(np.sum(x) - choose_count)])
        g = x[edge_i] + x[edge_j] - 1.0 if edges else np.zeros(0)
        return h, g

    def jacobian_transpose(x: np.ndarray, h_weight: np.ndarray, g_weight: np.ndarray) -> np.ndarray:
        grad = np.full(len(pallets), h_weight[0], dtype=float)
        if edges:
            np.add.at(grad, edge_i, g_weight)
            np.add.at(grad, edge_j, g_weight)
        return grad

    start = time.perf_counter()
    alm = solve_augmented_lagrangian(
        objective_grad,
        residuals,
        jacobian_transpose,
        x0,
        lower=0.0,
        upper=1.0,
        rho0=5.0,
        rho_multiplier=2.0,
        outer_iter=10,
        inner_iter=1000,
        tol=1e-5,
        inner_solver="bb",
    )
    selected = repair_layout(
        alm.x,
        edges,
        choose_count=choose_count,
        scores=scores,
        seed=seed,
    )
    layout_row(
        "augmented_lagrangian_projected_bb",
        "Chapter 7 + Chapter 6",
        alm.status,
        alm.x,
        selected,
        alm.inner_iterations,
        time.perf_counter() - start,
        alm.equality_violation,
        alm.inequality_violation,
        f"outer_iterations={alm.outer_iterations}; selected_min_distance>{min_distance}",
    )

    return rows


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "task",
        "algorithm",
        "textbook_chapter",
        "status",
        "objective",
        "recovered_objective",
        "iterations",
        "time_seconds",
        "equality_residual",
        "nonnegative_violation",
        "primal_residual",
        "dual_residual",
        "gap",
        "selected_or_routes",
        "min_load",
        "max_load",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(_format_row(row))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/algorithm_benchmark.csv")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    rows.extend(benchmark_task1(seed=args.seed))
    rows.extend(benchmark_task2())
    rows.extend(benchmark_task3(seed=args.seed))
    write_rows(Path(args.output), rows)
    print("Algorithm benchmark")
    print(f"rows={len(rows)} wrote {args.output}")
    for row in rows:
        print(
            f"[{row['task']}] {row['algorithm']} status={row['status']} "
            f"obj={float(row['objective']):.6g} iter={row['iterations']} "
            f"time={float(row['time_seconds']):.3f}s"
        )


if __name__ == "__main__":
    main()
