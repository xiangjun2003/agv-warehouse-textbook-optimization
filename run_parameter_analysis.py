from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Any

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from algorithms.admm_lp import solve_lp_admm
from algorithms.augmented_lagrangian import solve_lp_augmented_lagrangian
from algorithms.quadratic_penalty import solve_quadratic_penalty
from solve_agv_assignment import build_agv_assignment_lp, recover_integer_assignment
from solve_dynamic_partition import build_dynamic_partition_lp
from solve_warehouse_layout import build_conflict_edges, repair_layout
from warehouse_data import distance_matrix, load_data


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"

COLORS = {
    "text": "#1d1d1f",
    "muted": "#6e6e73",
    "grid": "#e5e5ea",
    "edge": "#d2d2d7",
    "blue": "#007aff",
    "green": "#34c759",
    "orange": "#ff9f0a",
    "purple": "#af52de",
}


def _relative_equality_residual(A: np.ndarray, x: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(A @ x - b) / (1.0 + np.linalg.norm(b)))


def _nonnegative_violation(x: np.ndarray) -> float:
    return float(max(0.0, -float(np.min(x))))


def _clean_delta(value: float, tol: float = 1e-6) -> float:
    return 0.0 if abs(value) <= tol else float(value)


def _row(**kwargs: Any) -> dict[str, Any]:
    return kwargs


def _format_row(row: dict[str, Any]) -> dict[str, Any]:
    formatted: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, float):
            formatted[key] = f"{value:.8g}" if np.isfinite(value) else ""
        else:
            formatted[key] = value
    return formatted


def load_references(path: Path) -> dict[str, float]:
    references = {
        "task1_cost": 131.0,
        "task2_cost": 79350.2,
        "task3_score": 5.1979167,
    }
    if not path.exists():
        return references
    with path.open(newline="", encoding="utf-8") as csvfile:
        for row in csv.DictReader(csvfile):
            task = row.get("task")
            algorithm = row.get("algorithm")
            if task == "task1_agv_assignment" and algorithm == "primal_dual_interior_point":
                references["task1_cost"] = float(row["recovered_objective"])
            elif task == "task2_dynamic_partition" and algorithm == "primal_dual_interior_point":
                references["task2_cost"] = float(row["recovered_objective"])
            elif task == "task3_cache_location" and algorithm == "quadratic_penalty_projected_bb":
                references["task3_score"] = float(row["recovered_objective"])
    return references


def sweep_task1_admm(refs: dict[str, float], seed: int) -> list[dict[str, Any]]:
    _, c, A, b, c1, c2, slices = build_agv_assignment_lp(seed=seed)
    i_count, j_count = c1.shape
    k_count = c2.shape[1]
    upper = np.full_like(c, 3.0)
    rows: list[dict[str, Any]] = []
    for rho in [5.0, 10.0, 25.0, 50.0, 100.0]:
        start = time.perf_counter()
        result = solve_lp_admm(c, A, b, rho=rho, max_iter=1200, tol=2e-4, upper=upper)
        elapsed = time.perf_counter() - start
        x_part = result.x[slices["x"]].reshape(i_count, j_count)
        y_part = result.x[slices["y"]].reshape(j_count, k_count)
        assignments, station_load = recover_integer_assignment(x_part, y_part, c1, c2)
        route_cost = float(sum(row[3] for row in assignments))
        rows.append(
            _row(
                experiment="task1_admm_rho",
                task="task1_agv_assignment",
                algorithm="admm_affine_box",
                textbook_chapter="Chapter 8",
                parameter="rho",
                parameter_value=rho,
                status=result.status,
                objective=float(c @ result.x),
                recovered_objective=route_cost,
                metric_direction="minimize",
                delta_from_reference=_clean_delta(route_cost - refs["task1_cost"]),
                iterations=result.iterations,
                outer_iterations="",
                time_seconds=elapsed,
                equality_residual=_relative_equality_residual(A, result.x, b),
                inequality_violation="",
                nonnegative_violation=_nonnegative_violation(result.x),
                primal_residual=result.primal_residual,
                dual_residual=result.dual_residual,
                selected_or_routes=len(assignments),
                min_load=int(np.min(station_load)),
                max_load=int(np.max(station_load)),
                notes="rho controls ADMM penalty balance",
            )
        )
    return rows


def sweep_task2_admm(refs: dict[str, float], alpha: float) -> list[dict[str, Any]]:
    data, c, A, b, distances = build_dynamic_partition_lp(alpha=alpha)
    j_count, k_count = distances.shape
    z_count = j_count * k_count
    upper = np.full_like(c, float(np.sum(data.pallet_quantities)))
    rows: list[dict[str, Any]] = []
    for rho in [10.0, 20.0, 35.0, 70.0, 120.0]:
        start = time.perf_counter()
        result = solve_lp_admm(c, A, b, rho=rho, max_iter=1500, tol=2e-4, upper=upper)
        elapsed = time.perf_counter() - start
        z = np.maximum(0.0, result.x[:z_count].reshape(j_count, k_count))
        loads = z.sum(axis=0)
        recovered = float(np.sum(distances * z))
        rows.append(
            _row(
                experiment="task2_admm_rho",
                task="task2_dynamic_partition",
                algorithm="admm_affine_box",
                textbook_chapter="Chapter 8",
                parameter="rho",
                parameter_value=rho,
                status=result.status,
                objective=float(c @ result.x),
                recovered_objective=recovered,
                metric_direction="minimize",
                delta_from_reference=_clean_delta(recovered - refs["task2_cost"]),
                iterations=result.iterations,
                outer_iterations="",
                time_seconds=elapsed,
                equality_residual=_relative_equality_residual(A, result.x, b),
                inequality_violation="",
                nonnegative_violation=_nonnegative_violation(result.x),
                primal_residual=result.primal_residual,
                dual_residual=result.dual_residual,
                selected_or_routes=int(np.count_nonzero(z > 1e-5)),
                min_load=float(np.min(loads)),
                max_load=float(np.max(loads)),
                notes="rho controls ADMM penalty balance",
            )
        )
    return rows


def sweep_task2_augmented_lagrangian(
    refs: dict[str, float],
    alpha: float,
) -> list[dict[str, Any]]:
    data, c, A, b, distances = build_dynamic_partition_lp(alpha=alpha)
    j_count, k_count = distances.shape
    z_count = j_count * k_count
    upper = np.full_like(c, float(np.sum(data.pallet_quantities)))
    rows: list[dict[str, Any]] = []
    for rho0 in [0.25, 0.5, 1.0, 2.0, 4.0]:
        start = time.perf_counter()
        result = solve_lp_augmented_lagrangian(
            c,
            A,
            b,
            upper=upper,
            rho0=rho0,
            rho_multiplier=2.0,
            outer_iter=12,
            inner_iter=500,
            tol=2e-4,
            inner_solver="bb",
        )
        elapsed = time.perf_counter() - start
        z = np.maximum(0.0, result.x[:z_count].reshape(j_count, k_count))
        loads = z.sum(axis=0)
        recovered = float(np.sum(distances * z))
        rows.append(
            _row(
                experiment="task2_alm_rho0",
                task="task2_dynamic_partition",
                algorithm="augmented_lagrangian_bb",
                textbook_chapter="Chapter 7 + Chapter 6",
                parameter="rho0",
                parameter_value=rho0,
                status=result.status,
                objective=float(c @ result.x),
                recovered_objective=recovered,
                metric_direction="minimize",
                delta_from_reference=_clean_delta(recovered - refs["task2_cost"]),
                iterations=result.inner_iterations,
                outer_iterations=result.outer_iterations,
                time_seconds=elapsed,
                equality_residual=result.equality_violation,
                inequality_violation=result.inequality_violation,
                nonnegative_violation=_nonnegative_violation(result.x),
                primal_residual=result.equality_violation,
                dual_residual="",
                selected_or_routes=int(np.count_nonzero(z > 1e-5)),
                min_load=float(np.min(loads)),
                max_load=float(np.max(loads)),
                notes="rho_multiplier fixed at 2.0",
            )
        )
    return rows


def _layout_problem(seed: int, choose_count: int, min_distance: int):
    data = load_data(agv_sample_prob=None)
    pallets = data.pallets
    quantities = data.pallet_quantities
    n = len(pallets)
    edges = build_conflict_edges(pallets, min_distance)
    edge_i = np.asarray([i for i, _ in edges], dtype=int)
    edge_j = np.asarray([j for _, j in edges], dtype=int)
    scores = quantities / max(float(np.max(quantities)), 1.0)

    rng = np.random.default_rng(seed)
    x0 = np.full(n, choose_count / n, dtype=float) + 0.02 * rng.random(n)
    x0 = np.clip(x0, 0.0, 1.0)
    tie_break_weight = 1e-3

    def objective_grad(x: np.ndarray):
        return -tie_break_weight * float(scores @ x), -tie_break_weight * scores

    def residuals(x: np.ndarray):
        h = np.asarray([float(np.sum(x) - choose_count)])
        g = x[edge_i] + x[edge_j] - 1.0 if edges else np.zeros(0)
        return h, g

    def jacobian_transpose(x: np.ndarray, h_weight: np.ndarray, g_weight: np.ndarray):
        grad = np.full(n, h_weight[0], dtype=float)
        if edges:
            np.add.at(grad, edge_i, g_weight)
            np.add.at(grad, edge_j, g_weight)
        return grad

    return data, edges, scores, x0, objective_grad, residuals, jacobian_transpose


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


def sweep_task3_penalty(refs: dict[str, float], seed: int) -> list[dict[str, Any]]:
    choose_count = 10
    min_distance = 6
    (
        data,
        edges,
        scores,
        x0,
        objective_grad,
        residuals,
        jacobian_transpose,
    ) = _layout_problem(seed, choose_count, min_distance)
    configs = [
        ("rho0", 1.0, 1.0, 8.0),
        ("rho0", 3.0, 3.0, 8.0),
        ("rho0", 10.0, 10.0, 8.0),
        ("rho0", 30.0, 30.0, 8.0),
        ("rho_multiplier", 2.0, 10.0, 2.0),
        ("rho_multiplier", 4.0, 10.0, 4.0),
        ("rho_multiplier", 8.0, 10.0, 8.0),
        ("rho_multiplier", 12.0, 10.0, 12.0),
    ]
    rows: list[dict[str, Any]] = []
    for parameter, parameter_value, rho0, rho_multiplier in configs:
        start = time.perf_counter()
        result = solve_quadratic_penalty(
            objective_grad,
            residuals,
            jacobian_transpose,
            x0,
            lower=0.0,
            upper=1.0,
            rho0=rho0,
            rho_multiplier=rho_multiplier,
            outer_iter=7,
            inner_iter=1200,
            inner_solver="bb",
            tol=1e-5,
        )
        elapsed = time.perf_counter() - start
        try:
            selected = repair_layout(
                result.x,
                edges,
                choose_count=choose_count,
                scores=scores,
                seed=seed,
            )
            selected_score = float(scores[selected].sum())
            selected_count = len(selected)
            min_pair = _min_pair_distance(data.pallets, selected)
            notes = f"rho0={rho0:g}; rho_multiplier={rho_multiplier:g}"
        except RuntimeError as exc:
            selected_score = float("nan")
            selected_count = 0
            min_pair = ""
            notes = f"repair_failed={exc}; rho0={rho0:g}; rho_multiplier={rho_multiplier:g}"
        rows.append(
            _row(
                experiment=f"task3_penalty_{parameter}",
                task="task3_cache_location",
                algorithm="quadratic_penalty_projected_bb",
                textbook_chapter="Chapter 7 + Chapter 6",
                parameter=parameter,
                parameter_value=parameter_value,
                status=result.status,
                objective=result.objective,
                recovered_objective=selected_score,
                metric_direction="maximize",
                delta_from_reference=_clean_delta(selected_score - refs["task3_score"]),
                iterations=int(sum(item.get("inner_iterations", 0.0) for item in result.history)),
                outer_iterations=result.outer_iterations,
                time_seconds=elapsed,
                equality_residual=result.equality_violation,
                inequality_violation=result.inequality_violation,
                nonnegative_violation=_nonnegative_violation(result.x),
                primal_residual=result.equality_violation,
                dual_residual="",
                selected_or_routes=selected_count,
                min_load=min_pair,
                max_load="",
                notes=notes,
            )
        )
    return rows


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "experiment",
        "task",
        "algorithm",
        "textbook_chapter",
        "parameter",
        "parameter_value",
        "status",
        "objective",
        "recovered_objective",
        "metric_direction",
        "delta_from_reference",
        "iterations",
        "outer_iterations",
        "time_seconds",
        "equality_residual",
        "inequality_violation",
        "nonnegative_violation",
        "primal_residual",
        "dual_residual",
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


def configure_plot_style() -> None:
    font_candidates = [
        "PingFang SC",
        "Heiti SC",
        "STHeiti",
        "Arial Unicode MS",
        "Noto Sans CJK SC",
        "Microsoft YaHei",
        "SimHei",
    ]
    installed = {font.name for font in fm.fontManager.ttflist}
    for name in font_candidates:
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams.update(
        {
            "figure.facecolor": "#ffffff",
            "axes.facecolor": "#fbfbfd",
            "axes.edgecolor": COLORS["edge"],
            "axes.labelcolor": COLORS["text"],
            "axes.titlecolor": COLORS["text"],
            "axes.titleweight": "bold",
            "font.size": 11,
            "xtick.color": COLORS["muted"],
            "ytick.color": COLORS["muted"],
            "axes.grid": True,
            "grid.color": COLORS["grid"],
            "grid.linewidth": 0.7,
            "grid.alpha": 0.8,
        }
    )


def plot_rows(rows: list[dict[str, Any]], path: Path) -> None:
    configure_plot_style()
    df = pd.DataFrame(rows)
    fig, axes = plt.subplots(2, 2, figsize=(15.5, 9.2), dpi=160)
    fig.suptitle("算法参数敏感性分析", fontsize=20, fontweight="bold", color=COLORS["text"])

    task1 = df[df["experiment"] == "task1_admm_rho"].sort_values("parameter_value")
    ax = axes[0, 0]
    ax.plot(task1["parameter_value"], task1["equality_residual"], marker="o", linewidth=2.8, color=COLORS["blue"])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title("任务1：ADMM rho 与可行性")
    ax.set_xlabel("rho")
    ax.set_ylabel("等式残差")
    ax2 = ax.twinx()
    ax2.plot(task1["parameter_value"], task1["recovered_objective"], marker="s", linewidth=2.2, color=COLORS["orange"])
    ax2.set_ylabel("恢复路线成本")
    ax2.tick_params(axis="y", colors=COLORS["orange"])

    task2 = df[df["experiment"] == "task2_admm_rho"].sort_values("parameter_value")
    ax = axes[0, 1]
    ax.plot(task2["parameter_value"], task2["delta_from_reference"], marker="o", linewidth=2.8, color=COLORS["green"])
    ax.set_xscale("log")
    ax.set_title("任务2：ADMM rho 与目标差距")
    ax.set_xlabel("rho")
    ax.set_ylabel("运输成本 - 基准最优值")
    ax2 = ax.twinx()
    ax2.plot(task2["parameter_value"], task2["equality_residual"], marker="s", linewidth=2.2, color=COLORS["purple"])
    ax2.set_yscale("log")
    ax2.set_ylabel("等式残差")
    ax2.tick_params(axis="y", colors=COLORS["purple"])

    alm = df[df["experiment"] == "task2_alm_rho0"].sort_values("parameter_value")
    ax = axes[1, 0]
    ax.plot(alm["parameter_value"], alm["delta_from_reference"], marker="o", linewidth=2.8, color=COLORS["green"])
    ax.set_xscale("log")
    ax.set_title("任务2：增广拉格朗日 rho0")
    ax.set_xlabel("rho0")
    ax.set_ylabel("运输成本 - 基准最优值")
    ax2 = ax.twinx()
    ax2.plot(alm["parameter_value"], alm["equality_residual"], marker="s", linewidth=2.2, color=COLORS["purple"])
    ax2.set_yscale("log")
    ax2.set_ylabel("等式违反")
    ax2.tick_params(axis="y", colors=COLORS["purple"])

    layout = df[df["task"] == "task3_cache_location"].copy()
    layout["label"] = layout.apply(
        lambda row: (
            f"mult={float(row['parameter_value']):g}"
            if row["parameter"] == "rho_multiplier"
            else f"rho0={float(row['parameter_value']):g}"
        ),
        axis=1,
    )
    ax = axes[1, 1]
    x_pos = np.arange(len(layout))
    ax.bar(x_pos, layout["recovered_objective"], color=COLORS["orange"], alpha=0.86)
    ax.set_title("任务3：罚函数参数与选址得分")
    ax.set_ylabel("修复后选址得分")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(layout["label"], rotation=32, ha="right")
    ax2 = ax.twinx()
    ax2.plot(x_pos, layout["equality_residual"], marker="o", linewidth=2.2, color=COLORS["blue"])
    ax2.set_yscale("log")
    ax2.set_ylabel("等式违反")
    ax2.tick_params(axis="y", colors=COLORS["blue"])

    for axis in axes.ravel():
        axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(rect=[0, 0.01, 1, 0.95])
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/algorithm_parameter_sweep.csv")
    parser.add_argument("--figure", default="figures/algorithm_parameter_sweep.png")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--alpha", type=float, default=0.6)
    args = parser.parse_args()

    refs = load_references(RESULTS_DIR / "algorithm_benchmark.csv")
    rows: list[dict[str, Any]] = []
    rows.extend(sweep_task1_admm(refs, seed=args.seed))
    rows.extend(sweep_task2_admm(refs, alpha=args.alpha))
    rows.extend(sweep_task2_augmented_lagrangian(refs, alpha=args.alpha))
    rows.extend(sweep_task3_penalty(refs, seed=args.seed))
    write_rows(Path(args.output), rows)
    plot_rows(rows, Path(args.figure))

    print("Algorithm parameter analysis")
    print(f"rows={len(rows)} wrote {args.output}")
    print(f"figure wrote {args.figure}")
    for row in rows:
        print(
            f"[{row['experiment']}] {row['parameter']}={float(row['parameter_value']):g} "
            f"status={row['status']} recovered={float(row['recovered_objective']):.6g} "
            f"delta={float(row['delta_from_reference']):.6g} "
            f"iter={row['iterations']} time={float(row['time_seconds']):.3f}s"
        )


if __name__ == "__main__":
    main()
