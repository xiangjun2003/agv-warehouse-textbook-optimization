from __future__ import annotations

import argparse
import ast
import csv
import time
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from algorithms.primal_dual_lp import LPResult, solve_lp_primal_dual
from solve_warehouse_layout import solve_warehouse_layout
from warehouse_data import DATA_DIR, distance_matrix, load_data


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"


COLORS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
    "node": "#E2E5EA",
    "agv": "#5477C4",
    "pallet_waiting": "#D8ECBD",
    "pallet_dispatch": "#71B436",
    "workstation": "#CC6F47",
    "cache": "#F0986E",
    "pickup": "#5477C4",
    "transfer": "#CC6F47",
    "final_delivery": "#BD569B",
}


@dataclass(frozen=True)
class Order:
    order_id: int
    sku: int
    amount: int


@dataclass
class PeriodResult:
    period: int
    active_pallets_before: int
    dispatched_pallets: int
    processed_quantity: float
    remaining_pallets_after: int
    remaining_quantity_after: float
    station_capacity: float
    agv_capacity: float
    station_count_used: int
    partition_status: str
    partition_iterations: int
    partition_objective: float
    assignment_status: str
    assignment_iterations: int
    assignment_cost: float
    min_station_processed: float
    max_station_processed: float


def _parse_sku_amounts(raw: str) -> dict[int, int]:
    parsed = ast.literal_eval("{" + raw + "}")
    return {int(sku): int(amount) for sku, amount in parsed.items()}


def read_pallet_inventory(path: Path = DATA_DIR / "pallets.csv"):
    pallet_ids: list[int] = []
    coords: list[tuple[int, int]] = []
    inventories: list[dict[int, int]] = []
    with path.open(newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            inventories.append(_parse_sku_amounts(row[0]))
            coords.append((int(row[1]), int(row[2])))
            pallet_ids.append(int(row[3]))
    quantities = np.asarray([sum(inv.values()) for inv in inventories], dtype=float)
    return pallet_ids, coords, inventories, quantities


def read_orders(path: Path = DATA_DIR / "orders.csv") -> list[Order]:
    orders: list[Order] = []
    with path.open(newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            orders.append(Order(int(row[0]), int(row[1]), int(row[2])))
    orders.sort(key=lambda order: order.order_id)
    return orders


def build_sku_index(inventories: list[dict[int, int]]) -> dict[int, list[int]]:
    sku_to_pallets: dict[int, list[int]] = {}
    for pallet_index, inventory in enumerate(inventories):
        for sku, amount in inventory.items():
            if amount > 0:
                sku_to_pallets.setdefault(sku, []).append(pallet_index)
    return sku_to_pallets


def allocate_initial_demand(
    orders: list[Order],
    available_inventory: list[dict[int, int]],
    sku_to_pallets: dict[int, list[int]],
) -> tuple[np.ndarray, float]:
    demand = np.zeros(len(available_inventory), dtype=float)
    unmet = 0.0
    for order in orders:
        amount_left = float(order.amount)
        candidates = sku_to_pallets.get(order.sku, [])
        candidates = sorted(
            candidates,
            key=lambda idx: (-available_inventory[idx].get(order.sku, 0), idx),
        )
        for pallet_index in candidates:
            if amount_left <= 1e-9:
                break
            available = float(available_inventory[pallet_index].get(order.sku, 0))
            if available <= 0:
                continue
            take = min(available, amount_left)
            available_inventory[pallet_index][order.sku] = int(round(available - take))
            demand[pallet_index] += take
            amount_left -= take
        unmet += max(0.0, amount_left)
    return demand, unmet


def best_cache_paths(
    pallet_positions: list[tuple[int, int]],
    cache_positions: list[tuple[int, int]],
    workstations: list[tuple[int, int]],
) -> tuple[np.ndarray, np.ndarray]:
    pallet_cache = distance_matrix(pallet_positions, cache_positions)
    cache_workstation = distance_matrix(cache_positions, workstations)
    candidate_costs = pallet_cache[:, :, None] + cache_workstation[None, :, :]
    best_cache_indices = np.argmin(candidate_costs, axis=1)
    service_costs = np.min(candidate_costs, axis=1)
    return service_costs, best_cache_indices


def solve_round_processing_plan(
    quantities: np.ndarray,
    service_costs: np.ndarray,
    *,
    station_capacity: float,
    agv_total_capacity: float,
    leftover_penalty: float = 10_000.0,
    verbose: bool = False,
) -> tuple[LPResult, np.ndarray, np.ndarray, float]:
    pallet_count, station_count = service_costs.shape
    flow_count = pallet_count * station_count
    leftover_count = pallet_count
    station_slack_count = station_count
    total_slack_count = 1
    leftover0 = flow_count
    station_slack0 = leftover0 + leftover_count
    total_slack0 = station_slack0 + station_slack_count
    var_count = total_slack0 + total_slack_count
    row_count = pallet_count + station_count + 1

    c = np.zeros(var_count)
    c[:flow_count] = service_costs.reshape(-1)
    c[leftover0:station_slack0] = leftover_penalty

    A = np.zeros((row_count, var_count))
    b = np.zeros(row_count)
    row = 0
    for pallet_index in range(pallet_count):
        start = pallet_index * station_count
        A[row, start : start + station_count] = 1.0
        A[row, leftover0 + pallet_index] = 1.0
        b[row] = quantities[pallet_index]
        row += 1

    for station_index in range(station_count):
        A[row, station_index:flow_count:station_count] = 1.0
        A[row, station_slack0 + station_index] = 1.0
        b[row] = station_capacity
        row += 1

    A[row, :flow_count] = 1.0
    A[row, total_slack0] = 1.0
    b[row] = agv_total_capacity

    result = solve_lp_primal_dual(
        c,
        A,
        b,
        max_iter=220,
        tol=1e-5,
        regularization=1e-8,
        verbose=verbose,
    )
    flows = result.x[:flow_count].reshape(pallet_count, station_count)
    station_loads = flows.sum(axis=0)
    objective = float(np.sum(service_costs * flows))
    return result, flows, station_loads, objective


def select_round_tasks(
    quantities: np.ndarray,
    planned_flows: np.ndarray,
    service_costs: np.ndarray,
    best_cache_indices: np.ndarray,
    *,
    agv_capacity: float,
    station_capacity: float,
    max_tasks: int,
) -> list[dict[str, float | int]]:
    station_count = planned_flows.shape[1]
    station_remaining = np.full(station_count, station_capacity, dtype=float)
    selected: list[dict[str, float | int]] = []
    selected_pallets: set[int] = set()

    candidate_rows: list[tuple[float, float, int, int]] = []
    for pallet_index in range(planned_flows.shape[0]):
        for station_index in range(station_count):
            planned = float(planned_flows[pallet_index, station_index])
            if planned > 1e-6:
                cost = float(service_costs[pallet_index, station_index])
                candidate_rows.append((-planned, cost, pallet_index, station_index))
    candidate_rows.sort()

    def try_add(pallet_index: int, station_index: int) -> bool:
        if len(selected) >= max_tasks:
            return False
        if pallet_index in selected_pallets:
            return False
        if quantities[pallet_index] <= 1e-8:
            return False
        if station_remaining[station_index] <= 1e-8:
            return False
        process_quantity = min(
            float(quantities[pallet_index]),
            agv_capacity,
            float(station_remaining[station_index]),
        )
        if process_quantity <= 1e-8:
            return False
        selected.append(
            {
                "local_pallet_index": pallet_index,
                "workstation_index": station_index,
                "cache_index": int(best_cache_indices[pallet_index, station_index]),
                "process_quantity": process_quantity,
            }
        )
        selected_pallets.add(pallet_index)
        station_remaining[station_index] -= process_quantity
        return True

    for _, _, pallet_index, station_index in candidate_rows:
        try_add(pallet_index, station_index)
        if len(selected) >= max_tasks:
            return selected

    remaining_pallets = np.argsort(-quantities)
    for raw_pallet_index in remaining_pallets:
        pallet_index = int(raw_pallet_index)
        if pallet_index in selected_pallets or quantities[pallet_index] <= 1e-8:
            continue
        for raw_station_index in np.argsort(service_costs[pallet_index]):
            if try_add(pallet_index, int(raw_station_index)):
                break
        if len(selected) >= max_tasks:
            break
    return selected


def solve_round_assignment(
    agv_positions: list[tuple[int, int]],
    pallet_positions: list[tuple[int, int]],
    tasks: list[dict[str, float | int]],
    cache_positions: list[tuple[int, int]],
    workstations: list[tuple[int, int]],
    *,
    verbose: bool = False,
) -> tuple[LPResult, list[dict[str, float | int]], float]:
    if not tasks:
        raise ValueError("round assignment requires at least one task")

    task_pallet_positions = [
        pallet_positions[int(task["local_pallet_index"])] for task in tasks
    ]
    full_agv_pallet = distance_matrix(agv_positions, task_pallet_positions)
    task_count = len(tasks)
    agv_count = min(len(agv_positions), task_count)
    chosen_agv_indices = np.argsort(np.min(full_agv_pallet, axis=1))[:agv_count]
    agvs = [agv_positions[int(idx)] for idx in chosen_agv_indices]

    agv_pallet = distance_matrix(agvs, task_pallet_positions)
    service = np.zeros(task_count, dtype=float)
    for task_index, task in enumerate(tasks):
        pallet = task_pallet_positions[task_index]
        cache = cache_positions[int(task["cache_index"])]
        workstation = workstations[int(task["workstation_index"])]
        service[task_index] = (
            distance_matrix([pallet], [cache])[0, 0]
            + distance_matrix([cache], [workstation])[0, 0]
        )
    costs = agv_pallet + service[None, :]

    x_count = agv_count * task_count
    slack_count = task_count
    var_count = x_count + slack_count
    row_count = agv_count + task_count
    c = np.zeros(var_count)
    c[:x_count] = costs.reshape(-1)
    A = np.zeros((row_count, var_count))
    b = np.zeros(row_count)

    row = 0
    for agv_index in range(agv_count):
        start = agv_index * task_count
        A[row, start : start + task_count] = 1.0
        b[row] = 1.0
        row += 1
    for task_index in range(task_count):
        A[row, task_index:x_count:task_count] = 1.0
        A[row, x_count + task_index] = 1.0
        b[row] = 1.0
        row += 1

    result = solve_lp_primal_dual(
        c,
        A,
        b,
        max_iter=80,
        tol=1e-7,
        regularization=1e-8,
        verbose=verbose,
    )
    relaxed = result.x[:x_count].reshape(agv_count, task_count)

    assignments: list[dict[str, float | int]] = []
    used_tasks: set[int] = set()
    agv_order = np.argsort(-np.max(relaxed, axis=1))
    for local_agv_index in agv_order:
        task_order = np.lexsort((costs[local_agv_index], -relaxed[local_agv_index]))
        chosen_task = None
        for raw_task_index in task_order:
            task_index = int(raw_task_index)
            if task_index not in used_tasks:
                chosen_task = task_index
                break
        if chosen_task is None:
            continue
        used_tasks.add(chosen_task)
        task = tasks[chosen_task]
        pickup = float(agv_pallet[local_agv_index, chosen_task])
        pallet = task_pallet_positions[chosen_task]
        cache = cache_positions[int(task["cache_index"])]
        workstation = workstations[int(task["workstation_index"])]
        transfer = float(distance_matrix([pallet], [cache])[0, 0])
        final_delivery = float(distance_matrix([cache], [workstation])[0, 0])
        assignments.append(
            {
                **task,
                "agv_index": int(chosen_agv_indices[local_agv_index]),
                "pickup_distance": pickup,
                "transfer_distance": transfer,
                "cache_to_workstation_distance": final_delivery,
                "route_cost": pickup + transfer + final_delivery,
            }
        )

    assignments.sort(key=lambda row_data: int(row_data["agv_index"]))
    return result, assignments, float(sum(row["route_cost"] for row in assignments))


def _shortened_segment(
    start: np.ndarray,
    end: np.ndarray,
    *,
    start_gap: float = 0.28,
    end_gap: float = 0.28,
) -> tuple[np.ndarray, np.ndarray]:
    delta = end.astype(float) - start.astype(float)
    length = float(np.linalg.norm(delta))
    if length <= start_gap + end_gap + 1e-9:
        return start.astype(float), end.astype(float)
    direction = delta / length
    return start.astype(float) + start_gap * direction, end.astype(float) - end_gap * direction


def _configure_plot_style() -> None:
    try:
        import matplotlib.font_manager as fm

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
    except Exception:
        pass
    plt.rcParams.update(
        {
            "figure.facecolor": COLORS["surface"],
            "axes.facecolor": COLORS["panel"],
            "axes.edgecolor": COLORS["axis"],
            "axes.labelcolor": COLORS["ink"],
            "axes.titlecolor": COLORS["ink"],
            "axes.titleweight": "bold",
            "font.size": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "xtick.color": COLORS["muted"],
            "ytick.color": COLORS["muted"],
            "axes.grid": True,
            "grid.color": COLORS["grid"],
            "grid.linewidth": 0.55,
            "grid.alpha": 0.7,
        }
    )


def plot_multi_period(
    *,
    data,
    period_snapshots: list[dict[str, object]],
    selected_cache_indices: list[int],
    output: Path,
) -> None:
    _configure_plot_style()
    output.parent.mkdir(parents=True, exist_ok=True)

    columns = 3
    rows = int(np.ceil(len(period_snapshots) / columns))
    fig_height = 2.75 + rows * 3.25
    fig, axes = plt.subplots(rows, columns, figsize=(18.5, fig_height), dpi=170)
    axes = np.asarray(axes).ravel()
    nodes = np.asarray([(x, y) for _, x, y in data.nodes], dtype=float)
    workstations = np.asarray(data.workstations, dtype=float)
    cache_points = np.asarray([data.pallets[idx] for idx in selected_cache_indices], dtype=float)

    for ax, snapshot in zip(axes, period_snapshots):
        ax.scatter(
            nodes[:, 0],
            nodes[:, 1],
            s=8,
            c=COLORS["node"],
            alpha=0.42,
            linewidths=0,
            zorder=0,
        )
        ax.scatter(
            cache_points[:, 0],
            cache_points[:, 1],
            s=80,
            c=COLORS["cache"],
            marker="D",
            edgecolors=COLORS["ink"],
            linewidths=0.65,
            alpha=0.92,
            zorder=4,
        )

        active_indices = np.asarray(snapshot["active_indices"], dtype=int)
        dispatched_indices = np.asarray(snapshot["dispatched_indices"], dtype=int)
        pending_quantities = np.asarray(snapshot["pending_quantities"], dtype=float)
        agv_starts = np.asarray(snapshot["agv_starts"], dtype=float)
        routes = snapshot["routes"]

        active_points = np.asarray([data.pallets[int(idx)] for idx in active_indices], dtype=float)
        if len(active_points) > 0:
            sizes = np.clip(pending_quantities / 1.9, 22, 110)
            ax.scatter(
                active_points[:, 0],
                active_points[:, 1],
                s=sizes,
                c=COLORS["pallet_waiting"],
                edgecolors=COLORS["panel"],
                linewidths=0.45,
                alpha=0.80,
                zorder=2,
            )

        for route in routes:
            agv = np.asarray((route["start_x"], route["start_y"]), dtype=float)
            pallet = np.asarray((route["pallet_x"], route["pallet_y"]), dtype=float)
            cache = np.asarray((route["cache_x"], route["cache_y"]), dtype=float)
            workstation = np.asarray((route["workstation_x"], route["workstation_y"]), dtype=float)
            p1, p2 = _shortened_segment(agv, pallet, start_gap=0.30, end_gap=0.34)
            t1, t2 = _shortened_segment(pallet, cache, start_gap=0.34, end_gap=0.36)
            d1, d2 = _shortened_segment(cache, workstation, start_gap=0.36, end_gap=0.36)
            ax.plot(
                [p1[0], p2[0]],
                [p1[1], p2[1]],
                color=COLORS["pickup"],
                linewidth=1.35,
                linestyle="--",
                alpha=0.72,
                zorder=1,
            )
            ax.plot(
                [t1[0], t2[0]],
                [t1[1], t2[1]],
                color=COLORS["transfer"],
                linewidth=1.35,
                alpha=0.74,
                zorder=1,
            )
            ax.plot(
                [d1[0], d2[0]],
                [d1[1], d2[1]],
                color=COLORS["final_delivery"],
                linewidth=1.35,
                linestyle="-.",
                alpha=0.74,
                zorder=1,
            )

        if len(dispatched_indices) > 0:
            dispatched_points = np.asarray([data.pallets[int(idx)] for idx in dispatched_indices], dtype=float)
            ax.scatter(
                dispatched_points[:, 0],
                dispatched_points[:, 1],
                s=92,
                c=COLORS["pallet_dispatch"],
                edgecolors=COLORS["ink"],
                linewidths=0.65,
                zorder=5,
            )

        ax.scatter(
            workstations[:, 0],
            workstations[:, 1],
            s=74,
            c=COLORS["workstation"],
            marker="s",
            edgecolors=COLORS["panel"],
            linewidths=0.55,
            zorder=6,
        )
        ax.scatter(
            agv_starts[:, 0],
            agv_starts[:, 1],
            s=84,
            c=COLORS["agv"],
            marker="^",
            edgecolors=COLORS["panel"],
            linewidths=0.55,
            zorder=7,
        )

        ax.set_xlim(-1, data.ncols)
        ax.set_ylim(-1, data.nrows)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xticks(np.arange(0, data.ncols + 1, 8))
        ax.set_yticks(np.arange(0, data.nrows + 1, 6))
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlabel("X", fontsize=9.5, fontweight="semibold")
        ax.set_ylabel("Y", fontsize=9.5, fontweight="semibold")
        ax.set_title(
            (
                f"轮次 {snapshot['period']} | 处理 {snapshot['processed_quantity']:.0f} 件 | "
                f"剩余 {snapshot['remaining_quantity_after']:.0f} 件\n"
                f"待处理托盘 {len(active_indices)} | 派车 {len(routes)} 辆"
            ),
            fontsize=11.4,
            fontweight="bold",
            pad=8,
        )

    for ax in axes[len(period_snapshots) :]:
        ax.axis("off")

    legend_handles = [
        Line2D([0], [0], marker="^", color="none", markerfacecolor=COLORS["agv"], markeredgecolor=COLORS["panel"], markersize=8, label="AGV 当前轮起点"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["pallet_waiting"], markeredgecolor=COLORS["axis"], markersize=8, label="剩余待处理托盘"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["pallet_dispatch"], markeredgecolor=COLORS["ink"], markersize=8, label="本轮处理托盘"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor=COLORS["workstation"], markeredgecolor=COLORS["panel"], markersize=8, label="工位"),
        Line2D([0], [0], marker="D", color="none", markerfacecolor=COLORS["cache"], markeredgecolor=COLORS["ink"], markersize=8, label="缓存/中转点"),
        Line2D([0], [0], color=COLORS["pickup"], linestyle="--", linewidth=2.0, label="AGV 到托盘"),
        Line2D([0], [0], color=COLORS["transfer"], linewidth=2.0, label="托盘到中转点"),
        Line2D([0], [0], color=COLORS["final_delivery"], linestyle="-.", linewidth=2.0, label="中转点到工位"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.018),
        ncol=4,
        frameon=True,
        facecolor=COLORS["panel"],
        edgecolor=COLORS["axis"],
        framealpha=0.98,
        prop={"size": 10, "weight": "semibold"},
        handlelength=2.0,
        columnspacing=1.0,
    )
    fig.suptitle(
        f"初始总需求下的 AGV 滚动处理过程：全部 {len(period_snapshots)} 轮",
        fontsize=27,
        fontweight="bold",
        color=COLORS["ink"],
        y=0.992,
    )
    fig.text(
        0.5,
        0.972,
        (
            "所有订单需求在 t=0 给定；每轮 AGV 各执行一次，"
            "工位有处理速度上限，循环直到剩余货量为 0。"
        ),
        ha="center",
        va="top",
        fontsize=12.2,
        fontweight="semibold",
        color=COLORS["muted"],
    )
    fig.subplots_adjust(left=0.045, right=0.99, top=0.94, bottom=0.055, wspace=0.13, hspace=0.42)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def write_summary(path: Path, summaries: list[PeriodResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([field for field in PeriodResult.__dataclass_fields__])
        for summary in summaries:
            writer.writerow([getattr(summary, field) for field in PeriodResult.__dataclass_fields__])


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def solve_multi_period(
    *,
    seed: int = 0,
    sample_prob: float = 0.6,
    max_agvs: int = 12,
    agv_capacity: float = 80.0,
    station_capacity: float = 160.0,
    choose_count: int = 10,
    min_distance: int = 6,
    max_rounds: int = 200,
    output_dir: Path = RESULTS_DIR,
    figure_path: Path = FIGURES_DIR / "multi_period_rolling_process.png",
    verbose: bool = False,
) -> tuple[list[PeriodResult], list[dict[str, object]], list[dict[str, object]], float]:
    start = time.perf_counter()
    data = load_data(agv_sample_prob=sample_prob, seed=seed, max_agvs=max_agvs)
    pallet_ids, pallet_coords, initial_inventory, _ = read_pallet_inventory()
    orders = read_orders()
    sku_to_pallets = build_sku_index(initial_inventory)
    demand, unmet = allocate_initial_demand(
        orders,
        [dict(inventory) for inventory in initial_inventory],
        sku_to_pallets,
    )
    if unmet > 1e-6:
        raise RuntimeError(f"initial demand has unmet quantity {unmet:.6f}")
    pending = demand.astype(float)
    agv_positions = [tuple(position) for position in data.agvs]

    _, _, selected_cache_indices, _, _, _ = solve_warehouse_layout(
        choose_count=choose_count,
        min_distance=min_distance,
        seed=seed,
        verbose=False,
    )
    selected_cache_positions = [pallet_coords[int(idx)] for idx in selected_cache_indices]

    summaries: list[PeriodResult] = []
    route_rows: list[dict[str, object]] = []
    workload_rows: list[dict[str, object]] = []
    period_snapshots: list[dict[str, object]] = []

    period = 0
    while float(np.sum(pending)) > 1e-8 and period < max_rounds:
        period += 1
        active_indices = np.flatnonzero(pending > 1e-8)
        active_positions = [pallet_coords[int(idx)] for idx in active_indices]
        active_quantities = pending[active_indices].copy()
        service_costs, best_cache_indices = best_cache_paths(
            active_positions,
            selected_cache_positions,
            data.workstations,
        )
        plan_result, planned_flows, station_loads, partition_objective = solve_round_processing_plan(
            active_quantities,
            service_costs,
            station_capacity=station_capacity,
            agv_total_capacity=max_agvs * agv_capacity,
            verbose=verbose,
        )
        tasks = select_round_tasks(
            active_quantities,
            planned_flows,
            service_costs,
            best_cache_indices,
            agv_capacity=agv_capacity,
            station_capacity=station_capacity,
            max_tasks=max_agvs,
        )
        if not tasks:
            raise RuntimeError("no feasible task selected; check capacities")

        assignment_result, assignments, assignment_cost = solve_round_assignment(
            agv_positions,
            active_positions,
            tasks,
            selected_cache_positions,
            data.workstations,
            verbose=verbose,
        )

        dispatched_global: list[int] = []
        route_snapshot_rows: list[dict[str, object]] = []
        next_agv_positions = list(agv_positions)
        actual_station_loads = np.zeros(len(data.workstations), dtype=float)
        processed_quantity = 0.0

        selected_local = {int(row["local_pallet_index"]) for row in assignments}
        for local_index, global_index in enumerate(active_indices):
            local_cache_index = int(best_cache_indices[local_index, int(np.argmax(planned_flows[local_index]))])
            cache_global_index = int(selected_cache_indices[local_cache_index])
            cache_x, cache_y = selected_cache_positions[local_cache_index]
            workload_rows.append(
                {
                    "period": period,
                    "pallet_index": int(global_index),
                    "pallet_id": pallet_ids[int(global_index)],
                    "x": pallet_coords[int(global_index)][0],
                    "y": pallet_coords[int(global_index)][1],
                    "pending_quantity_before_round": f"{pending[int(global_index)]:.8f}",
                    "planned_quantity_this_round": f"{float(np.sum(planned_flows[local_index])):.8f}",
                    "planned_main_workstation_index": int(np.argmax(planned_flows[local_index])),
                    "planned_main_cache_pallet_index": cache_global_index,
                    "planned_main_cache_x": cache_x,
                    "planned_main_cache_y": cache_y,
                    "dispatched": int(local_index in selected_local),
                }
            )

        for assignment in assignments:
            agv_index = int(assignment["agv_index"])
            local_pallet_index = int(assignment["local_pallet_index"])
            global_pallet_index = int(active_indices[local_pallet_index])
            station_index = int(assignment["workstation_index"])
            local_cache_index = int(assignment["cache_index"])
            cache_global_index = int(selected_cache_indices[local_cache_index])
            start_x, start_y = agv_positions[agv_index]
            pallet_x, pallet_y = pallet_coords[global_pallet_index]
            cache_x, cache_y = selected_cache_positions[local_cache_index]
            workstation_x, workstation_y = data.workstations[station_index]
            process_quantity = min(
                float(assignment["process_quantity"]),
                float(pending[global_pallet_index]),
            )
            pending[global_pallet_index] -= process_quantity
            processed_quantity += process_quantity
            actual_station_loads[station_index] += process_quantity
            route_row = {
                "period": period,
                "agv_index": agv_index,
                "start_x": start_x,
                "start_y": start_y,
                "pallet_index": global_pallet_index,
                "pallet_id": pallet_ids[global_pallet_index],
                "pallet_x": pallet_x,
                "pallet_y": pallet_y,
                "processed_quantity": f"{process_quantity:.8f}",
                "remaining_quantity_after_route": f"{pending[global_pallet_index]:.8f}",
                "cache_pallet_index": cache_global_index,
                "cache_x": cache_x,
                "cache_y": cache_y,
                "workstation_index": station_index,
                "workstation_x": workstation_x,
                "workstation_y": workstation_y,
                "pickup_distance": f"{float(assignment['pickup_distance']):.8f}",
                "transfer_distance": f"{float(assignment['transfer_distance']):.8f}",
                "cache_to_workstation_distance": f"{float(assignment['cache_to_workstation_distance']):.8f}",
                "route_cost": f"{float(assignment['route_cost']):.8f}",
            }
            route_rows.append(route_row)
            route_snapshot_rows.append(
                {
                    **route_row,
                    "processed_quantity": process_quantity,
                    "pickup_distance": float(assignment["pickup_distance"]),
                    "transfer_distance": float(assignment["transfer_distance"]),
                    "cache_to_workstation_distance": float(assignment["cache_to_workstation_distance"]),
                    "route_cost": float(assignment["route_cost"]),
                }
            )
            dispatched_global.append(global_pallet_index)
            next_agv_positions[agv_index] = (workstation_x, workstation_y)

        pending = np.maximum(pending, 0.0)
        remaining_indices = np.flatnonzero(pending > 1e-8)
        nonzero_station_loads = actual_station_loads[actual_station_loads > 1e-8]
        summary = PeriodResult(
            period=period,
            active_pallets_before=int(len(active_indices)),
            dispatched_pallets=int(len(dispatched_global)),
            processed_quantity=float(processed_quantity),
            remaining_pallets_after=int(len(remaining_indices)),
            remaining_quantity_after=float(np.sum(pending)),
            station_capacity=float(station_capacity),
            agv_capacity=float(agv_capacity),
            station_count_used=int(np.count_nonzero(actual_station_loads > 1e-8)),
            partition_status=plan_result.status,
            partition_iterations=plan_result.iterations,
            partition_objective=partition_objective,
            assignment_status=assignment_result.status,
            assignment_iterations=assignment_result.iterations,
            assignment_cost=assignment_cost,
            min_station_processed=float(np.min(nonzero_station_loads)) if len(nonzero_station_loads) else 0.0,
            max_station_processed=float(np.max(nonzero_station_loads)) if len(nonzero_station_loads) else 0.0,
        )
        summaries.append(summary)
        period_snapshots.append(
            {
                "period": period,
                "active_indices": active_indices.copy(),
                "pending_quantities": active_quantities.copy(),
                "dispatched_indices": np.asarray(dispatched_global, dtype=int),
                "routes": route_snapshot_rows,
                "agv_starts": np.asarray(agv_positions, dtype=float),
                "processed_quantity": processed_quantity,
                "remaining_pallets_after": summary.remaining_pallets_after,
                "remaining_quantity_after": summary.remaining_quantity_after,
            }
        )
        agv_positions = next_agv_positions

    if float(np.sum(pending)) > 1e-8:
        raise RuntimeError(
            f"reached max_rounds={max_rounds} with {float(np.sum(pending)):.6f} quantity remaining"
        )

    write_summary(output_dir / "multi_period_summary.csv", summaries)
    write_rows(
        output_dir / "multi_period_routes.csv",
        [
            "period",
            "agv_index",
            "start_x",
            "start_y",
            "pallet_index",
            "pallet_id",
            "pallet_x",
            "pallet_y",
            "processed_quantity",
            "remaining_quantity_after_route",
            "cache_pallet_index",
            "cache_x",
            "cache_y",
            "workstation_index",
            "workstation_x",
            "workstation_y",
            "pickup_distance",
            "transfer_distance",
            "cache_to_workstation_distance",
            "route_cost",
        ],
        route_rows,
    )
    write_rows(
        output_dir / "multi_period_workload.csv",
        [
            "period",
            "pallet_index",
            "pallet_id",
            "x",
            "y",
            "pending_quantity_before_round",
            "planned_quantity_this_round",
            "planned_main_workstation_index",
            "planned_main_cache_pallet_index",
            "planned_main_cache_x",
            "planned_main_cache_y",
            "dispatched",
        ],
        workload_rows,
    )
    plot_multi_period(
        data=data,
        period_snapshots=period_snapshots,
        selected_cache_indices=selected_cache_indices,
        output=figure_path,
    )
    elapsed = time.perf_counter() - start
    return summaries, route_rows, workload_rows, elapsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sample-prob", type=float, default=0.6)
    parser.add_argument("--max-agvs", type=int, default=12)
    parser.add_argument("--agv-capacity", type=float, default=80.0)
    parser.add_argument("--station-capacity", type=float, default=160.0)
    parser.add_argument("--choose-count", type=int, default=10)
    parser.add_argument("--min-distance", type=int, default=6)
    parser.add_argument("--max-rounds", type=int, default=200)
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--figure", default="figures/multi_period_rolling_process.png")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    summaries, route_rows, _, elapsed = solve_multi_period(
        seed=args.seed,
        sample_prob=args.sample_prob,
        max_agvs=args.max_agvs,
        agv_capacity=args.agv_capacity,
        station_capacity=args.station_capacity,
        choose_count=args.choose_count,
        min_distance=args.min_distance,
        max_rounds=args.max_rounds,
        output_dir=Path(args.output_dir),
        figure_path=Path(args.figure),
        verbose=args.verbose,
    )
    total_processed = sum(summary.processed_quantity for summary in summaries)
    print("Multi-period rolling completion optimization")
    print(
        f"rounds={len(summaries)} routes={len(route_rows)} "
        f"processed={total_processed:.3f} time={elapsed:.3f}s"
    )
    for summary in summaries:
        print(
            f"[r={summary.period}] active={summary.active_pallets_before} "
            f"dispatched={summary.dispatched_pallets} "
            f"processed={summary.processed_quantity:.1f} "
            f"remaining={summary.remaining_quantity_after:.1f} "
            f"stations={summary.station_count_used} "
            f"partition={summary.partition_status}/{summary.partition_iterations} "
            f"assignment={summary.assignment_status}/{summary.assignment_iterations}"
        )
    print(f"wrote {Path(args.output_dir) / 'multi_period_summary.csv'}")
    print(f"wrote {Path(args.output_dir) / 'multi_period_routes.csv'}")
    print(f"wrote {Path(args.output_dir) / 'multi_period_workload.csv'}")
    print(f"wrote {Path(args.figure)}")


if __name__ == "__main__":
    main()
