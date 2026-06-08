from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np

from algorithms.quadratic_penalty import solve_quadratic_penalty
from warehouse_data import distance_matrix, load_data


def build_conflict_edges(pallets: list[tuple[int, int]], min_distance: int):
    distances = distance_matrix(pallets, pallets)
    edges: list[tuple[int, int]] = []
    for i in range(len(pallets)):
        for j in range(i + 1, len(pallets)):
            if distances[i, j] <= min_distance:
                edges.append((i, j))
    return edges


def repair_layout(
    relaxed: np.ndarray,
    edges: list[tuple[int, int]],
    *,
    choose_count: int,
    scores: np.ndarray,
    seed: int = 0,
):
    n = relaxed.size
    conflicts = [set() for _ in range(n)]
    for i, j in edges:
        conflicts[i].add(j)
        conflicts[j].add(i)

    def greedy(order: np.ndarray | list[int]) -> list[int]:
        chosen: list[int] = []
        chosen_set: set[int] = set()
        for raw_idx in order:
            idx = int(raw_idx)
            if all(idx not in conflicts[old] for old in chosen_set):
                chosen.append(idx)
                chosen_set.add(idx)
                if len(chosen) == choose_count:
                    return sorted(chosen)
        return sorted(chosen)

    degree = np.asarray([len(neighbors) for neighbors in conflicts], dtype=float)
    priority = relaxed + 0.05 * scores - 0.002 * degree
    deterministic_orders = [
        np.argsort(-priority),
        np.argsort(-relaxed),
        np.argsort(-scores),
        np.argsort(degree),
    ]
    best: list[int] = []
    for order in deterministic_orders:
        chosen = greedy(order)
        if len(chosen) == choose_count:
            return chosen
        if len(chosen) > len(best):
            best = chosen

    rng = np.random.default_rng(seed)
    base = np.argsort(-priority)
    for _ in range(3000):
        noise = 0.3 * rng.standard_normal(n)
        order = base[np.argsort(-(priority[base] + noise[base]))]
        chosen = greedy(order)
        if len(chosen) == choose_count:
            return chosen
        if len(chosen) > len(best):
            best = chosen

    ordered = list(map(int, np.argsort(-priority)))
    search_nodes = 0
    search_limit = 200_000

    def dfs(candidates: list[int], chosen: list[int]) -> list[int] | None:
        nonlocal search_nodes
        search_nodes += 1
        if search_nodes > search_limit:
            return None
        if len(chosen) == choose_count:
            return sorted(chosen)
        if len(chosen) + len(candidates) < choose_count:
            return None
        for pos, vertex in enumerate(candidates):
            if any(vertex in conflicts[old] for old in chosen):
                continue
            next_candidates = [
                cand
                for cand in candidates[pos + 1 :]
                if cand not in conflicts[vertex]
            ]
            found = dfs(next_candidates, chosen + [vertex])
            if found is not None:
                return found
        return None

    found = dfs(ordered, [])
    if found is not None:
        return found
    raise RuntimeError(
        "failed to repair relaxed layout into a feasible 0-1 layout; "
        f"best greedy solution selected {len(best)} pallets"
    )


def solve_warehouse_layout(
    choose_count: int = 10,
    min_distance: int = 6,
    seed: int = 0,
    inner_solver: str = "bb",
    verbose: bool = False,
):
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

    # The base layout model has many equivalent feasible solutions. A tiny
    # score term only breaks ties among feasible layouts.
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

    start = time.perf_counter()
    result = solve_quadratic_penalty(
        objective_grad,
        residuals,
        jacobian_transpose,
        x0,
        lower=0.0,
        upper=1.0,
        rho0=10.0,
        rho_multiplier=8.0,
        outer_iter=7,
        inner_iter=1200,
        inner_solver=inner_solver,
        tol=1e-5,
        verbose=verbose,
    )
    selected = repair_layout(
        result.x,
        edges,
        choose_count=choose_count,
        scores=scores,
        seed=seed,
    )
    elapsed = time.perf_counter() - start
    min_pair_distance = min(
        distance_matrix([pallets[i] for i in selected], [pallets[j] for j in selected])[
            a, b
        ]
        for a in range(len(selected))
        for b in range(a + 1, len(selected))
    )
    return data, result, selected, edges, int(min_pair_distance), elapsed


def write_layout(path: Path, selected: list[int], pallets: list[tuple[int, int]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["pallet_index", "x", "y"])
        for idx in selected:
            x, y = pallets[idx]
            writer.writerow([idx, x, y])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--choose-count", type=int, default=10)
    parser.add_argument("--min-distance", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--inner-solver", choices=["bb", "pg", "nesterov"], default="bb")
    parser.add_argument("--output", default="results/warehouse_layout.csv")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    data, result, selected, edges, min_pair_distance, elapsed = solve_warehouse_layout(
        choose_count=args.choose_count,
        min_distance=args.min_distance,
        seed=args.seed,
        inner_solver=args.inner_solver,
        verbose=args.verbose,
    )
    write_layout(Path(args.output), selected, data.pallets)
    print("Warehouse layout")
    print(f"pallets={len(data.pallets)} conflict_edges={len(edges)}")
    print(
        f"status={result.status} outer_iterations={result.outer_iterations} "
        f"time={elapsed:.3f}s"
    )
    print(
        f"selected={selected} min_pair_distance={min_pair_distance} "
        f"required>{args.min_distance}"
    )
    print(
        f"penalty violations: equality={result.equality_violation:.2e} "
        f"inequality={result.inequality_violation:.2e}"
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
