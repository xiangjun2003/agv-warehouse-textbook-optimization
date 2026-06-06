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
    released_orders: int
    released_quantity: float
    active_pallets: int
    dispatched_pallets: int
    backlog_pallets: int
    backlog_quantity_after: float
    partition_status: str
    partition_iterations: int
    partition_objective: float
    assignment_status: str
    assignment_iterations: int
    assignment_cost: float
    min_station_load: float
    max_station_load: float


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


def split_orders(orders: list[Order], periods: int) -> list[list[Order]]:
    quotient, remainder = divmod(len(orders), periods)
    waves: list[list[Order]] = []
    start = 0
    for period in range(periods):
        stop = start + quotient + (1 if period < remainder else 0)
        waves.append(orders[start:stop])
        start = stop
    return waves


def build_sku_index(inventories: list[dict[int, int]]) -> dict[int, list[int]]:
    sku_to_pallets: dict[int, list[int]] = {}
    for pallet_index, inventory in enumerate(inventories):
        for sku, amount in inventory.items():
            if amount > 0:
                sku_to_pallets.setdefault(sku, []).append(pallet_index)
    return sku_to_pallets


def allocate_wave(
    orders: list[Order],
    available_inventory: list[dict[int, int]],
    sku_to_pallets: dict[int, list[int]],
) -> tuple[np.ndarray, float]:
    released = np.zeros(len(available_inventory), dtype=float)
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
            released[pallet_index] += take
            amount_left -= take
        unmet += max(0.0, amount_left)
    return released, unmet


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


def solve_period_partition(
    quantities: np.ndarray,
    service_costs: np.ndarray,
    *,
    alpha: float,
    verbose: bool = False,
) -> tuple[LPResult, np.ndarray, np.ndarray, float]:
    pallet_count, station_count = service_costs.shape
    flow_count = pallet_count * station_count
    var_count = flow_count + station_count
    row_count = pallet_count + station_count

    c = np.zeros(var_count)
    c[:flow_count] = service_costs.reshape(-1)
    A = np.zeros((row_count, var_count))
    b = np.zeros(row_count)

    for pallet_index in range(pallet_count):
        start = pallet_index * station_count
        A[pallet_index, start : start + station_count] = 1.0
        b[pallet_index] = quantities[pallet_index]

    total_quantity = float(np.sum(quantities))
    min_station_load = alpha * total_quantity / station_count
    for station_index in range(station_count):
        row = pallet_count + station_index
        A[row, station_index:flow_count:station_count] = 1.0
        A[row, flow_count + station_index] = -1.0
        b[row] = min_station_load

    result = solve_lp_primal_dual(
        c,
        A,
        b,
        max_iter=180,
        tol=5e-6,
        regularization=1e-8,
        verbose=verbose,
    )
    flows = result.x[:flow_count].reshape(pallet_count, station_count)
    loads = flows.sum(axis=0)
    objective = float(np.sum(service_costs * flows))
    return result, flows, loads, objective


def solve_period_assignment(
    agv_positions: list[tuple[int, int]],
    pallet_positions: list[tuple[int, int]],
    station_indices: np.ndarray,
    cache_positions: list[tuple[int, int]],
    service_costs: np.ndarray,
    best_cache_indices: np.ndarray,
    workstations: list[tuple[int, int]],
    *,
    verbose: bool = False,
) -> tuple[LPResult, list[dict[str, float | int]], float]:
    if not pallet_positions:
        raise ValueError("period assignment requires at least one active pallet")

    all_agvs = list(agv_positions)
    full_agv_pallet = distance_matrix(all_agvs, pallet_positions)
    agv_count = min(len(all_agvs), len(pallet_positions))
    chosen_agv_indices = np.argsort(np.min(full_agv_pallet, axis=1))[:agv_count]
    agvs = [all_agvs[int(idx)] for idx in chosen_agv_indices]

    agv_pallet = distance_matrix(agvs, pallet_positions)
    fixed_service = service_costs[np.arange(len(pallet_positions)), station_indices]
    costs = agv_pallet + fixed_service[None, :]

    x_count = agv_count * len(pallet_positions)
    slack_count = len(pallet_positions)
    var_count = x_count + slack_count
    row_count = agv_count + len(pallet_positions)
    c = np.zeros(var_count)
    c[:x_count] = costs.reshape(-1)
    A = np.zeros((row_count, var_count))
    b = np.zeros(row_count)

    row = 0
    for agv_index in range(agv_count):
        start = agv_index * len(pallet_positions)
        A[row, start : start + len(pallet_positions)] = 1.0
        b[row] = 1.0
        row += 1
    for pallet_index in range(len(pallet_positions)):
        A[row, pallet_index:x_count:len(pallet_positions)] = 1.0
        A[row, x_count + pallet_index] = 1.0
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
    relaxed = result.x[:x_count].reshape(agv_count, len(pallet_positions))

    assignments: list[dict[str, float | int]] = []
    used_pallets: set[int] = set()
    agv_order = np.argsort(-np.max(relaxed, axis=1))
    for local_agv_index in agv_order:
        pallet_order = np.lexsort((costs[local_agv_index], -relaxed[local_agv_index]))
        chosen_pallet = None
        for raw_pallet_index in pallet_order:
            pallet_index = int(raw_pallet_index)
            if pallet_index not in used_pallets:
                chosen_pallet = pallet_index
                break
        if chosen_pallet is None:
            continue
        used_pallets.add(chosen_pallet)
        station_index = int(station_indices[chosen_pallet])
        cache_index = int(best_cache_indices[chosen_pallet, station_index])
        pickup = float(agv_pallet[local_agv_index, chosen_pallet])
        transfer = float(distance_matrix([pallet_positions[chosen_pallet]], [cache_positions[cache_index]])[0, 0])
        final_delivery = float(distance_matrix([cache_positions[cache_index]], [workstations[station_index]])[0, 0])
        assignments.append(
            {
                "agv_index": int(chosen_agv_indices[local_agv_index]),
                "local_pallet_index": chosen_pallet,
                "cache_index": cache_index,
                "workstation_index": station_index,
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
    pallet_ids: list[int],
    output: Path,
) -> None:
    _configure_plot_style()
    output.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 3, figsize=(18.5, 11.2), dpi=170)
    axes = axes.ravel()
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
        if len(cache_points) > 0:
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
                f"时刻 {snapshot['period']} | 释放 {snapshot['released_orders']} 单 | "
                f"派车 {len(routes)} 辆\n"
                f"待处理托盘 {len(active_indices)} | "
                f"积压 {snapshot['backlog_pallets']} 托盘 / "
                f"{snapshot['backlog_quantity_after']:.0f} 件"
            ),
            fontsize=12.7,
            fontweight="bold",
            pad=8,
        )

    legend_handles = [
        Line2D([0], [0], marker="^", color="none", markerfacecolor=COLORS["agv"], markeredgecolor=COLORS["panel"], markersize=8, label="AGV 当前时刻起点"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["pallet_waiting"], markeredgecolor=COLORS["axis"], markersize=8, label="待处理托盘任务"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["pallet_dispatch"], markeredgecolor=COLORS["ink"], markersize=8, label="本时刻派车处理托盘"),
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
        "6 个滚动时刻的 AGV 仓储调度过程",
        fontsize=27,
        fontweight="bold",
        color=COLORS["ink"],
        y=0.986,
    )
    fig.text(
        0.5,
        0.952,
        (
            "订单按 Order ID 切分为 6 个连续波次；先用布局模型选中转点，"
            "每个时刻再做经中转点的工位负载分配和 AGV 派车。"
        ),
        ha="center",
        va="top",
        fontsize=12.2,
        fontweight="semibold",
        color=COLORS["muted"],
    )
    fig.subplots_adjust(left=0.045, right=0.99, top=0.91, bottom=0.13, wspace=0.13, hspace=0.22)
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
    periods: int = 6,
    seed: int = 0,
    sample_prob: float = 0.6,
    max_agvs: int = 12,
    alpha: float = 0.6,
    choose_count: int = 10,
    min_distance: int = 6,
    output_dir: Path = RESULTS_DIR,
    figure_path: Path = FIGURES_DIR / "multi_period_rolling_process.png",
    verbose: bool = False,
) -> tuple[list[PeriodResult], list[dict[str, object]], list[dict[str, object]], float]:
    start = time.perf_counter()
    data = load_data(agv_sample_prob=sample_prob, seed=seed, max_agvs=max_agvs)
    pallet_ids, pallet_coords, initial_inventory, _ = read_pallet_inventory()
    orders = read_orders()
    waves = split_orders(orders, periods)
    sku_to_pallets = build_sku_index(initial_inventory)
    available_inventory = [dict(inventory) for inventory in initial_inventory]
    pending = np.zeros(len(pallet_ids), dtype=float)
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

    for period, wave in enumerate(waves, start=1):
        released, unmet = allocate_wave(wave, available_inventory, sku_to_pallets)
        if unmet > 1e-6:
            raise RuntimeError(f"period {period} has unmet released demand {unmet:.6f}")
        pending += released
        active_indices = np.flatnonzero(pending > 1e-8)
        if len(active_indices) == 0:
            continue

        active_positions = [pallet_coords[int(idx)] for idx in active_indices]
        active_quantities = pending[active_indices]
        service_costs, best_cache_indices = best_cache_paths(
            active_positions,
            selected_cache_positions,
            data.workstations,
        )
        partition_result, flows, loads, partition_objective = solve_period_partition(
            active_quantities,
            service_costs,
            alpha=alpha,
            verbose=verbose,
        )
        main_station = np.argmax(flows, axis=1).astype(int)

        assignment_result, assignments, assignment_cost = solve_period_assignment(
            agv_positions,
            active_positions,
            main_station,
            selected_cache_positions,
            service_costs,
            best_cache_indices,
            data.workstations,
            verbose=verbose,
        )

        dispatched_global: list[int] = []
        route_snapshot_rows: list[dict[str, object]] = []
        next_agv_positions = list(agv_positions)
        dispatched_local = {int(row["local_pallet_index"]) for row in assignments}

        for local_index, global_index in enumerate(active_indices):
            local_cache_index = int(best_cache_indices[local_index, main_station[local_index]])
            cache_global_index = int(selected_cache_indices[local_cache_index])
            cache_x, cache_y = selected_cache_positions[local_cache_index]
            workload_rows.append(
                {
                    "period": period,
                    "pallet_index": int(global_index),
                    "pallet_id": pallet_ids[int(global_index)],
                    "x": pallet_coords[int(global_index)][0],
                    "y": pallet_coords[int(global_index)][1],
                    "pending_quantity_before_dispatch": f"{pending[int(global_index)]:.8f}",
                    "main_workstation_index": int(main_station[local_index]),
                    "main_cache_pallet_index": cache_global_index,
                    "main_cache_x": cache_x,
                    "main_cache_y": cache_y,
                    "dispatched": int(local_index in dispatched_local),
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
            request_quantity = float(pending[global_pallet_index])
            route_row = {
                "period": period,
                "agv_index": agv_index,
                "start_x": start_x,
                "start_y": start_y,
                "pallet_index": global_pallet_index,
                "pallet_id": pallet_ids[global_pallet_index],
                "pallet_x": pallet_x,
                "pallet_y": pallet_y,
                "request_quantity": f"{request_quantity:.8f}",
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
                    "request_quantity": request_quantity,
                    "pickup_distance": float(assignment["pickup_distance"]),
                    "transfer_distance": float(assignment["transfer_distance"]),
                    "cache_to_workstation_distance": float(assignment["cache_to_workstation_distance"]),
                    "route_cost": float(assignment["route_cost"]),
                }
            )
            dispatched_global.append(global_pallet_index)
            pending[global_pallet_index] = 0.0
            next_agv_positions[agv_index] = (workstation_x, workstation_y)

        backlog_indices = np.flatnonzero(pending > 1e-8)
        summary = PeriodResult(
            period=period,
            released_orders=len(wave),
            released_quantity=float(np.sum(released)),
            active_pallets=int(len(active_indices)),
            dispatched_pallets=int(len(dispatched_global)),
            backlog_pallets=int(len(backlog_indices)),
            backlog_quantity_after=float(np.sum(pending)),
            partition_status=partition_result.status,
            partition_iterations=partition_result.iterations,
            partition_objective=partition_objective,
            assignment_status=assignment_result.status,
            assignment_iterations=assignment_result.iterations,
            assignment_cost=assignment_cost,
            min_station_load=float(np.min(loads)),
            max_station_load=float(np.max(loads)),
        )
        summaries.append(summary)
        period_snapshots.append(
            {
                "period": period,
                "released_orders": len(wave),
                "active_indices": active_indices.copy(),
                "pending_quantities": active_quantities.copy(),
                "dispatched_indices": np.asarray(dispatched_global, dtype=int),
                "routes": route_snapshot_rows,
                "agv_starts": np.asarray(agv_positions, dtype=float),
                "backlog_pallets": summary.backlog_pallets,
                "backlog_quantity_after": summary.backlog_quantity_after,
            }
        )
        agv_positions = next_agv_positions

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
            "request_quantity",
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
            "pending_quantity_before_dispatch",
            "main_workstation_index",
            "main_cache_pallet_index",
            "main_cache_x",
            "main_cache_y",
            "dispatched",
        ],
        workload_rows,
    )
    plot_multi_period(
        data=data,
        period_snapshots=period_snapshots,
        selected_cache_indices=selected_cache_indices,
        pallet_ids=pallet_ids,
        output=figure_path,
    )
    elapsed = time.perf_counter() - start
    return summaries, route_rows, workload_rows, elapsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--periods", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sample-prob", type=float, default=0.6)
    parser.add_argument("--max-agvs", type=int, default=12)
    parser.add_argument("--alpha", type=float, default=0.6)
    parser.add_argument("--choose-count", type=int, default=10)
    parser.add_argument("--min-distance", type=int, default=6)
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--figure", default="figures/multi_period_rolling_process.png")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    summaries, route_rows, _, elapsed = solve_multi_period(
        periods=args.periods,
        seed=args.seed,
        sample_prob=args.sample_prob,
        max_agvs=args.max_agvs,
        alpha=args.alpha,
        choose_count=args.choose_count,
        min_distance=args.min_distance,
        output_dir=Path(args.output_dir),
        figure_path=Path(args.figure),
        verbose=args.verbose,
    )
    print("Multi-period rolling optimization")
    print(f"periods={len(summaries)} routes={len(route_rows)} time={elapsed:.3f}s")
    for summary in summaries:
        print(
            f"[t={summary.period}] orders={summary.released_orders} "
            f"active={summary.active_pallets} dispatched={summary.dispatched_pallets} "
            f"backlog={summary.backlog_pallets} "
            f"partition={summary.partition_status}/{summary.partition_iterations} "
            f"assignment={summary.assignment_status}/{summary.assignment_iterations} "
            f"cost={summary.assignment_cost:.3f}"
        )
    print(f"wrote {Path(args.output_dir) / 'multi_period_summary.csv'}")
    print(f"wrote {Path(args.output_dir) / 'multi_period_routes.csv'}")
    print(f"wrote {Path(args.output_dir) / 'multi_period_workload.csv'}")
    print(f"wrote {Path(args.figure)}")


if __name__ == "__main__":
    main()
