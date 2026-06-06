from __future__ import annotations

import argparse
import ast
import csv
import time
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
    "inbound": "#CC6F47",
    "outbound": "#BD569B",
    "direct": "#804126",
}


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


def read_orders(path: Path = DATA_DIR / "orders.csv"):
    orders: list[tuple[int, int, int]] = []
    with path.open(newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            orders.append((int(row[0]), int(row[1]), int(row[2])))
    orders.sort(key=lambda row: row[0])
    return orders


def build_sku_index(inventories: list[dict[int, int]]) -> dict[int, list[int]]:
    sku_to_pallets: dict[int, list[int]] = {}
    for pallet_index, inventory in enumerate(inventories):
        for sku, amount in inventory.items():
            if amount > 0:
                sku_to_pallets.setdefault(sku, []).append(pallet_index)
    return sku_to_pallets


def allocate_initial_demand(
    orders: list[tuple[int, int, int]],
    available_inventory: list[dict[int, int]],
    sku_to_pallets: dict[int, list[int]],
) -> tuple[np.ndarray, float]:
    demand = np.zeros(len(available_inventory), dtype=float)
    unmet = 0.0
    for _, sku, amount in orders:
        amount_left = float(amount)
        candidates = sku_to_pallets.get(sku, [])
        candidates = sorted(
            candidates,
            key=lambda idx: (-available_inventory[idx].get(sku, 0), idx),
        )
        for pallet_index in candidates:
            if amount_left <= 1e-9:
                break
            available = float(available_inventory[pallet_index].get(sku, 0))
            if available <= 0:
                continue
            take = min(available, amount_left)
            available_inventory[pallet_index][sku] = int(round(available - take))
            demand[pallet_index] += take
            amount_left -= take
        unmet += max(0.0, amount_left)
    return demand, unmet


def capacity_vector(capacity: float | np.ndarray, count: int) -> np.ndarray:
    if np.isscalar(capacity):
        return np.full(count, float(capacity), dtype=float)
    vector = np.asarray(capacity, dtype=float).reshape(-1)
    if vector.size != count:
        raise ValueError(f"capacity vector length {vector.size} != {count}")
    return vector.copy()


def solve_flow_plan(
    quantities: np.ndarray,
    costs: np.ndarray,
    *,
    receiver_capacities: float | np.ndarray,
    total_capacity: float,
    leftover_penalty: float = 10_000.0,
    verbose: bool = False,
) -> tuple[LPResult, np.ndarray, np.ndarray, float]:
    source_count, receiver_count = costs.shape
    receiver_caps = capacity_vector(receiver_capacities, receiver_count)
    flow_count = source_count * receiver_count
    leftover_count = source_count
    receiver_slack_count = receiver_count
    total_slack_count = 1
    leftover0 = flow_count
    receiver_slack0 = leftover0 + leftover_count
    total_slack0 = receiver_slack0 + receiver_slack_count
    var_count = total_slack0 + total_slack_count
    row_count = source_count + receiver_count + 1

    c = np.zeros(var_count)
    c[:flow_count] = costs.reshape(-1)
    c[leftover0:receiver_slack0] = leftover_penalty

    A = np.zeros((row_count, var_count))
    b = np.zeros(row_count)
    row = 0
    for source_index in range(source_count):
        start = source_index * receiver_count
        A[row, start : start + receiver_count] = 1.0
        A[row, leftover0 + source_index] = 1.0
        b[row] = quantities[source_index]
        row += 1

    for receiver_index in range(receiver_count):
        A[row, receiver_index:flow_count:receiver_count] = 1.0
        A[row, receiver_slack0 + receiver_index] = 1.0
        b[row] = receiver_caps[receiver_index]
        row += 1

    A[row, :flow_count] = 1.0
    A[row, total_slack0] = 1.0
    b[row] = total_capacity

    result = solve_lp_primal_dual(
        c,
        A,
        b,
        max_iter=220,
        tol=1e-5,
        regularization=1e-8,
        verbose=verbose,
    )
    flows = result.x[:flow_count].reshape(source_count, receiver_count)
    receiver_loads = flows.sum(axis=0)
    objective = float(np.sum(costs * flows))
    return result, flows, receiver_loads, objective


def solve_balanced_partition_plan(
    quantities: np.ndarray,
    costs: np.ndarray,
    *,
    alpha: float = 1.15,
    verbose: bool = False,
) -> tuple[LPResult, np.ndarray, np.ndarray, np.ndarray, float]:
    source_count, station_count = costs.shape
    flow_count = source_count * station_count
    surplus_count = station_count
    var_count = flow_count + surplus_count
    row_count = source_count + station_count

    c = np.zeros(var_count)
    c[:flow_count] = costs.reshape(-1)
    A = np.zeros((row_count, var_count))
    b = np.zeros(row_count)

    row = 0
    for source_index in range(source_count):
        start = source_index * station_count
        A[row, start : start + station_count] = 1.0
        b[row] = quantities[source_index]
        row += 1

    total_quantity = float(np.sum(quantities))
    max_station_load = alpha * total_quantity / station_count
    for station_index in range(station_count):
        A[row, station_index:flow_count:station_count] = 1.0
        A[row, flow_count + station_index] = 1.0
        b[row] = max_station_load
        row += 1

    result = solve_lp_primal_dual(
        c,
        A,
        b,
        max_iter=120,
        tol=1e-6,
        regularization=1e-8,
        verbose=verbose,
    )
    flows = result.x[:flow_count].reshape(source_count, station_count)
    station_loads = flows.sum(axis=0)
    primary_stations = np.argmax(flows, axis=1).astype(int)
    objective = float(np.sum(costs * flows))
    return result, flows, primary_stations, station_loads, objective


def restrict_costs_to_primary_stations(
    costs: np.ndarray,
    active_indices: np.ndarray,
    primary_stations: np.ndarray | None,
    *,
    forbidden_cost: float = 1_000_000.0,
) -> np.ndarray:
    if primary_stations is None:
        return costs.copy()
    restricted = np.full_like(costs, forbidden_cost, dtype=float)
    for local_index, global_index in enumerate(active_indices):
        station = int(primary_stations[int(global_index)])
        restricted[local_index, station] = costs[local_index, station]
    return restricted


def select_flow_tasks(
    quantities: np.ndarray,
    planned_flows: np.ndarray,
    costs: np.ndarray,
    *,
    receiver_capacities: float | np.ndarray,
    max_tasks: int,
    agv_capacity: float,
    unique_source: bool,
    max_allowed_cost: float | None = None,
) -> list[dict[str, float | int]]:
    receiver_count = planned_flows.shape[1]
    receiver_remaining = capacity_vector(receiver_capacities, receiver_count)
    source_remaining = quantities.astype(float).copy()
    selected_sources: set[int] = set()
    selected: list[dict[str, float | int]] = []

    candidates: list[tuple[float, float, int, int]] = []
    for source_index in range(planned_flows.shape[0]):
        for receiver_index in range(receiver_count):
            planned = float(planned_flows[source_index, receiver_index])
            if max_allowed_cost is not None and float(costs[source_index, receiver_index]) >= max_allowed_cost:
                continue
            if planned > 1e-6:
                candidates.append((-planned, float(costs[source_index, receiver_index]), source_index, receiver_index))
    candidates.sort()

    def try_add(source_index: int, receiver_index: int) -> bool:
        if len(selected) >= max_tasks:
            return False
        if unique_source and source_index in selected_sources:
            return False
        if source_remaining[source_index] <= 1e-8:
            return False
        if receiver_remaining[receiver_index] <= 1e-8:
            return False
        quantity = min(
            float(source_remaining[source_index]),
            float(receiver_remaining[receiver_index]),
            float(agv_capacity),
        )
        if quantity <= 1e-8:
            return False
        selected.append(
            {
                "source_index": int(source_index),
                "receiver_index": int(receiver_index),
                "quantity": quantity,
            }
        )
        source_remaining[source_index] -= quantity
        receiver_remaining[receiver_index] -= quantity
        selected_sources.add(source_index)
        return True

    for _, _, source_index, receiver_index in candidates:
        try_add(source_index, receiver_index)
        if len(selected) >= max_tasks:
            return selected

    for raw_source_index in np.argsort(-source_remaining):
        source_index = int(raw_source_index)
        if source_remaining[source_index] <= 1e-8:
            continue
        if unique_source and source_index in selected_sources:
            continue
        for raw_receiver_index in np.argsort(costs[source_index]):
            if max_allowed_cost is not None and float(costs[source_index, int(raw_receiver_index)]) >= max_allowed_cost:
                continue
            if try_add(source_index, int(raw_receiver_index)):
                break
        if len(selected) >= max_tasks:
            break
    return selected


def solve_task_assignment(
    agv_positions: list[tuple[int, int]],
    tasks: list[dict[str, object]],
    *,
    verbose: bool = False,
) -> tuple[LPResult, list[dict[str, object]], float]:
    if not tasks:
        raise ValueError("assignment requires at least one task")

    pickup_positions = [task["pickup"] for task in tasks]
    drop_positions = [task["drop"] for task in tasks]
    agv_count = min(len(agv_positions), len(tasks))
    full_pickup = distance_matrix(agv_positions, pickup_positions)
    chosen_agv_indices = np.argsort(np.min(full_pickup, axis=1))[:agv_count]
    chosen_agvs = [agv_positions[int(idx)] for idx in chosen_agv_indices]

    pickup_cost = distance_matrix(chosen_agvs, pickup_positions)
    delivery_cost = distance_matrix(pickup_positions, drop_positions).diagonal()
    costs = pickup_cost + delivery_cost[None, :]

    x_count = agv_count * len(tasks)
    slack_count = len(tasks)
    var_count = x_count + slack_count
    row_count = agv_count + len(tasks)
    c = np.zeros(var_count)
    c[:x_count] = costs.reshape(-1)
    A = np.zeros((row_count, var_count))
    b = np.zeros(row_count)

    row = 0
    for agv_index in range(agv_count):
        start = agv_index * len(tasks)
        A[row, start : start + len(tasks)] = 1.0
        b[row] = 1.0
        row += 1
    for task_index in range(len(tasks)):
        A[row, task_index:x_count:len(tasks)] = 1.0
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
    relaxed = result.x[:x_count].reshape(agv_count, len(tasks))

    assignments: list[dict[str, object]] = []
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
        task = dict(tasks[chosen_task])
        pickup_distance = float(pickup_cost[local_agv_index, chosen_task])
        delivery_distance = float(delivery_cost[chosen_task])
        task.update(
            {
                "agv_index": int(chosen_agv_indices[local_agv_index]),
                "start": chosen_agvs[local_agv_index],
                "pickup_distance": pickup_distance,
                "delivery_distance": delivery_distance,
                "route_cost": pickup_distance + delivery_distance,
            }
        )
        assignments.append(task)

    assignments.sort(key=lambda row: int(row["agv_index"]))
    return result, assignments, float(sum(float(row["route_cost"]) for row in assignments))


def _task_row(
    *,
    scenario: str,
    period: int,
    assignment: dict[str, object],
    pallet_ids: list[int],
    cache_global_indices: list[int],
) -> dict[str, object]:
    pickup_x, pickup_y = assignment["pickup"]
    drop_x, drop_y = assignment["drop"]
    start_x, start_y = assignment.get("start", assignment["pickup"])
    pallet_index = assignment.get("pallet_index")
    cache_index = assignment.get("cache_index")
    workstation_index = assignment.get("workstation_index")
    agv_index = assignment.get("agv_index")
    return {
        "scenario": scenario,
        "period": period,
        "transport_mode": assignment.get("transport_mode", "agv"),
        "route_type": assignment["route_type"],
        "agv_index": "" if agv_index in (None, "") else int(agv_index),
        "start_x": start_x,
        "start_y": start_y,
        "pickup_x": pickup_x,
        "pickup_y": pickup_y,
        "drop_x": drop_x,
        "drop_y": drop_y,
        "pallet_index": "" if pallet_index is None else int(pallet_index),
        "pallet_id": "" if pallet_index is None else pallet_ids[int(pallet_index)],
        "cache_pallet_index": "" if cache_index is None else int(cache_global_indices[int(cache_index)]),
        "workstation_index": "" if workstation_index is None else int(workstation_index),
        "quantity": f"{float(assignment['quantity']):.8f}",
        "processed_quantity": f"{float(assignment.get('processed_quantity', 0.0)):.8f}",
        "moved_to_cache_quantity": f"{float(assignment.get('moved_to_cache_quantity', 0.0)):.8f}",
        "pickup_distance": f"{float(assignment['pickup_distance']):.8f}",
        "delivery_distance": f"{float(assignment['delivery_distance']):.8f}",
        "route_cost": f"{float(assignment['route_cost']):.8f}",
    }


def _snapshot_route(assignment: dict[str, object]) -> dict[str, object]:
    start_x, start_y = assignment.get("start", assignment["pickup"])
    pickup_x, pickup_y = assignment["pickup"]
    drop_x, drop_y = assignment["drop"]
    return {
        "transport_mode": assignment.get("transport_mode", "agv"),
        "route_type": assignment["route_type"],
        "start_x": start_x,
        "start_y": start_y,
        "pickup_x": pickup_x,
        "pickup_y": pickup_y,
        "drop_x": drop_x,
        "drop_y": drop_y,
        "pallet_index": assignment.get("pallet_index"),
        "quantity": float(assignment["quantity"]),
    }


def _snapshot_route_from_row(row: dict[str, object]) -> dict[str, object]:
    pallet_raw = row.get("pallet_index", "")
    return {
        "transport_mode": row.get("transport_mode", "agv"),
        "route_type": row["route_type"],
        "start_x": float(row["start_x"]),
        "start_y": float(row["start_y"]),
        "pickup_x": float(row["pickup_x"]),
        "pickup_y": float(row["pickup_y"]),
        "drop_x": float(row["drop_x"]),
        "drop_y": float(row["drop_y"]),
        "pallet_index": None if pallet_raw in ("", None) else int(pallet_raw),
        "quantity": float(row["quantity"]),
    }


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> float:
    return float(abs(a[0] - b[0]) + abs(a[1] - b[1]))


def build_nearest_allocation(demand: np.ndarray, costs: np.ndarray) -> np.ndarray:
    allocation = np.zeros_like(costs, dtype=float)
    nearest = np.argmin(costs, axis=1)
    for pallet_index, quantity in enumerate(demand):
        if quantity > 1e-8:
            allocation[pallet_index, int(nearest[pallet_index])] = float(quantity)
    return allocation


def repair_partition_to_primary_allocation(
    demand: np.ndarray,
    costs: np.ndarray,
    relaxed_flows: np.ndarray,
    *,
    alpha: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    station_count = costs.shape[1]
    max_station_load = float(alpha) * float(np.sum(demand)) / station_count
    allocation = np.zeros_like(costs, dtype=float)
    station_loads = np.zeros(station_count, dtype=float)
    primary = np.full(costs.shape[0], -1, dtype=int)
    pallet_order = np.argsort(-demand)

    for raw_pallet_index in pallet_order:
        pallet_index = int(raw_pallet_index)
        quantity = float(demand[pallet_index])
        if quantity <= 1e-8:
            continue
        station_order = np.lexsort((costs[pallet_index], -relaxed_flows[pallet_index]))
        chosen_station = None
        for raw_station in station_order:
            station = int(raw_station)
            if station_loads[station] + quantity <= max_station_load + 1e-8:
                chosen_station = station
                break
        if chosen_station is None:
            overload = np.maximum(0.0, station_loads + quantity - max_station_load)
            chosen_station = int(np.lexsort((costs[pallet_index], overload))[0])
        allocation[pallet_index, chosen_station] = quantity
        station_loads[chosen_station] += quantity
        primary[pallet_index] = chosen_station
    return allocation, primary, station_loads


def build_transport_lanes(
    *,
    allocation: np.ndarray,
    pallet_coords: list[tuple[int, int]],
    workstations: list[tuple[int, int]],
    cache_positions: list[tuple[int, int]] | None = None,
    use_cache: bool = False,
) -> tuple[list[dict[str, object]], np.ndarray]:
    lanes: list[dict[str, object]] = []
    cache_service_stations = np.asarray([], dtype=int)
    if cache_positions:
        cache_service_stations = np.argmin(distance_matrix(cache_positions, workstations), axis=1).astype(int)
        pallet_cache_distances = distance_matrix(pallet_coords, cache_positions)
    else:
        pallet_cache_distances = np.empty((len(pallet_coords), 0), dtype=float)
    pallet_station_distances = distance_matrix(pallet_coords, workstations)

    for pallet_index in range(allocation.shape[0]):
        for station_index in range(allocation.shape[1]):
            quantity = float(allocation[pallet_index, station_index])
            if quantity <= 1e-6:
                continue
            direct_drop = workstations[station_index]
            direct_delivery_distance = _manhattan(pallet_coords[pallet_index], direct_drop)
            cache_index = None
            cache_drop = None
            cache_delivery_distance = None
            cache_to_station_distance = None
            if use_cache and len(cache_service_stations) > 0:
                candidate_caches = np.flatnonzero(cache_service_stations == station_index)
                if len(candidate_caches) > 0:
                    best_cache = int(candidate_caches[np.argmin(pallet_cache_distances[pallet_index, candidate_caches])])
                    cache_index = best_cache
                    cache_drop = cache_positions[best_cache]  # type: ignore[index]
                    cache_delivery_distance = float(pallet_cache_distances[pallet_index, best_cache])
                    cache_to_station_distance = _manhattan(cache_drop, workstations[station_index])
            lanes.append(
                {
                    "lane_id": len(lanes),
                    "pallet_index": int(pallet_index),
                    "station_index": int(station_index),
                    "cache_index": cache_index,
                    "cache_drop": cache_drop,
                    "cache_delivery_distance": cache_delivery_distance,
                    "cache_to_station_distance": cache_to_station_distance,
                    "remaining": quantity,
                    "pickup": pallet_coords[pallet_index],
                    "drop": direct_drop,
                    "direct_drop": direct_drop,
                    "direct_delivery_distance": direct_delivery_distance,
                    "delivery_distance": direct_delivery_distance,
                }
            )
    return lanes, cache_service_stations


def select_transport_tasks(
    lanes: list[dict[str, object]],
    *,
    max_tasks: int,
    agv_capacity: float,
    cache_inventory: np.ndarray | None = None,
    cache_capacity: float = 0.0,
    cache_positions: list[tuple[int, int]] | None = None,
    cache_service_stations: np.ndarray | None = None,
    workstations: list[tuple[int, int]] | None = None,
    use_cache: bool = False,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    serial = 0
    inventory = np.asarray(cache_inventory if cache_inventory is not None else [], dtype=float)
    cache_points = cache_positions or []
    remaining_lane_quantity = sum(float(lane["remaining"]) for lane in lanes)

    def add_candidate(**candidate: object) -> None:
        nonlocal serial
        candidate["serial"] = serial
        serial += 1
        candidates.append(candidate)

    if use_cache and len(inventory) > 0 and cache_service_stations is not None and workstations is not None:
        final_flush = remaining_lane_quantity <= 1e-8
        for cache_index, cached_quantity in enumerate(inventory):
            if cached_quantity <= 1e-8:
                continue
            station_index = int(cache_service_stations[cache_index])
            quantity = min(float(agv_capacity), float(cached_quantity))
            distance = _manhattan(cache_points[cache_index], workstations[station_index])
            load_factor = max(quantity / float(agv_capacity), 0.25)
            add_candidate(
                priority=0 if final_flush or quantity >= 0.85 * float(agv_capacity) else 2,
                score=distance / load_factor,
                transport_mode="agv",
                route_type="cache_to_workstation",
                lane_id=None,
                pallet_index=None,
                cache_index=int(cache_index),
                workstation_index=station_index,
                quantity=quantity,
                processed_quantity=0.0,
                moved_to_cache_quantity=0.0,
                pickup=cache_points[cache_index],
                drop=workstations[station_index],
            )

    for lane in lanes:
        remaining = float(lane["remaining"])
        chunk_index = 0
        while remaining > 1e-8 and chunk_index < max_tasks:
            quantity = min(float(agv_capacity), remaining)
            direct_distance = float(lane.get("direct_delivery_distance", lane["delivery_distance"]))
            direct_priority = 1

            cache_index = lane.get("cache_index")
            if use_cache and cache_index is not None and lane.get("cache_drop") is not None:
                inbound_distance = float(lane["cache_delivery_distance"])
                outbound_distance = float(lane["cache_to_station_distance"])
                amortized_cache_cost = inbound_distance + outbound_distance * min(1.0, quantity / float(agv_capacity))
                if amortized_cache_cost + 1e-9 < direct_distance:
                    direct_priority = 3
                    add_candidate(
                        priority=1,
                        score=amortized_cache_cost,
                        transport_mode="agv",
                        route_type="pallet_to_cache",
                        lane_id=int(lane["lane_id"]),
                        pallet_index=int(lane["pallet_index"]),
                        cache_index=int(cache_index),
                        workstation_index=int(lane["station_index"]),
                        quantity=quantity,
                        processed_quantity=0.0,
                        moved_to_cache_quantity=quantity,
                        pickup=lane["pickup"],
                        drop=lane["cache_drop"],
                    )

            add_candidate(
                priority=direct_priority,
                score=direct_distance,
                transport_mode="agv",
                route_type="direct",
                lane_id=int(lane["lane_id"]),
                pallet_index=int(lane["pallet_index"]),
                cache_index=None,
                workstation_index=int(lane["station_index"]),
                quantity=quantity,
                processed_quantity=0.0,
                moved_to_cache_quantity=0.0,
                pickup=lane["pickup"],
                drop=lane["direct_drop"],
            )
            remaining -= quantity
            chunk_index += 1

    candidates.sort(
        key=lambda row: (
            int(row["priority"]),
            float(row["score"]),
            -float(row["quantity"]),
            int(row["serial"]),
        )
    )

    selected: list[dict[str, object]] = []
    lane_reserved: dict[int, float] = {}
    cache_in_reserved = np.zeros(len(inventory), dtype=float)
    cache_out_reserved = np.zeros(len(inventory), dtype=float)
    lanes_by_id = {int(lane["lane_id"]): lane for lane in lanes}

    for candidate in candidates:
        if len(selected) >= max_tasks:
            break
        route_type = str(candidate["route_type"])
        quantity = float(candidate["quantity"])

        if route_type == "cache_to_workstation":
            cache_index = int(candidate["cache_index"])
            available = float(inventory[cache_index] - cache_out_reserved[cache_index])
            quantity = min(quantity, available)
            if quantity <= 1e-8:
                continue
            cache_out_reserved[cache_index] += quantity
        else:
            lane_id = int(candidate["lane_id"])
            lane = lanes_by_id[lane_id]
            available = float(lane["remaining"]) - lane_reserved.get(lane_id, 0.0)
            quantity = min(quantity, available)
            if route_type == "pallet_to_cache":
                cache_index = int(candidate["cache_index"])
                free_space = float(cache_capacity) - float(inventory[cache_index]) - cache_in_reserved[cache_index]
                quantity = min(quantity, max(0.0, free_space))
                if quantity <= 1e-8:
                    continue
                cache_in_reserved[cache_index] += quantity
            if quantity <= 1e-8:
                continue
            lane_reserved[lane_id] = lane_reserved.get(lane_id, 0.0) + quantity

        task = {
            key: value
            for key, value in candidate.items()
            if key not in {"priority", "score", "serial"}
        }
        task["quantity"] = quantity
        if route_type == "pallet_to_cache":
            task["moved_to_cache_quantity"] = quantity
        selected.append(task)

    tasks: list[dict[str, object]] = []
    for candidate in selected:
        tasks.append(dict(candidate))
    return tasks


def process_station_available(
    *,
    scenario_name: str,
    period: int,
    data,
    station_queues: np.ndarray,
    cache_inventory: np.ndarray,
    cache_positions: list[tuple[int, int]],
    cache_service_stations: np.ndarray,
    station_capacity: float,
    pallet_ids: list[int],
    cache_global_indices: list[int],
) -> tuple[list[dict[str, object]], float, np.ndarray]:
    rows: list[dict[str, object]] = []
    processed_by_station = np.zeros(len(data.workstations), dtype=float)
    processed_total = 0.0
    for station in range(len(data.workstations)):
        remaining_capacity = float(station_capacity)
        if station_queues[station] > 1e-8:
            quantity = min(float(station_queues[station]), remaining_capacity)
            station_queues[station] -= quantity
            remaining_capacity -= quantity
            processed_total += quantity
            processed_by_station[station] += quantity
            rows.append(
                _task_row(
                    scenario=scenario_name,
                    period=period,
                    assignment={
                        "transport_mode": "station_process",
                        "route_type": "workstation_process",
                        "agv_index": "",
                        "pallet_index": None,
                        "cache_index": None,
                        "workstation_index": station,
                        "quantity": quantity,
                        "processed_quantity": quantity,
                        "moved_to_cache_quantity": 0.0,
                        "start": data.workstations[station],
                        "pickup": data.workstations[station],
                        "drop": data.workstations[station],
                        "pickup_distance": 0.0,
                        "delivery_distance": 0.0,
                        "route_cost": 0.0,
                    },
                    pallet_ids=pallet_ids,
                    cache_global_indices=cache_global_indices,
                )
            )
    return rows, processed_total, processed_by_station


def simulate_transport_processing_scenario(
    *,
    scenario_name: str,
    data,
    pallet_ids: list[int],
    lanes: list[dict[str, object]],
    initial_agv_positions: list[tuple[int, int]],
    cache_global_indices: list[int],
    cache_positions: list[tuple[int, int]],
    cache_service_stations: np.ndarray,
    max_agvs: int,
    agv_capacity: float,
    station_capacity: float,
    cache_capacity: float,
    max_rounds: int,
    verbose: bool = False,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    agv_positions = list(initial_agv_positions)
    station_queues = np.zeros(len(data.workstations), dtype=float)
    cache_inventory = np.zeros(len(cache_positions), dtype=float)
    summaries: list[dict[str, object]] = []
    routes: list[dict[str, object]] = []
    workloads: list[dict[str, object]] = []
    snapshots: list[dict[str, object]] = []
    cache_rows: list[dict[str, object]] = []

    period = 0
    while (
        sum(float(lane["remaining"]) for lane in lanes)
        + float(np.sum(station_queues))
        + float(np.sum(cache_inventory))
    ) > 1e-8 and period < max_rounds:
        period += 1
        active_lanes = [lane for lane in lanes if float(lane["remaining"]) > 1e-8]
        active_indices = np.asarray(sorted({int(lane["pallet_index"]) for lane in active_lanes}), dtype=int)
        pending_quantities = np.asarray(
            [
                sum(float(lane["remaining"]) for lane in active_lanes if int(lane["pallet_index"]) == int(pallet_index))
                for pallet_index in active_indices
            ],
            dtype=float,
        )
        cache_before = cache_inventory.copy()
        tasks = select_transport_tasks(
            lanes,
            max_tasks=max_agvs,
            agv_capacity=agv_capacity,
            cache_inventory=cache_inventory,
            cache_capacity=cache_capacity,
            cache_positions=cache_positions,
            cache_service_stations=cache_service_stations,
            workstations=data.workstations,
            use_cache=len(cache_positions) > 0,
        )

        assignments: list[dict[str, object]] = []
        assignment_status = "skipped"
        assignment_iter = 0
        round_distance = 0.0
        if tasks:
            assignment_result, assignments, round_distance = solve_task_assignment(
                agv_positions,
                tasks,
                verbose=verbose,
            )
            assignment_status = assignment_result.status
            assignment_iter = assignment_result.iterations

        next_agv_positions = list(agv_positions)
        dispatched_global: list[int] = []
        moved_to_cache = 0.0
        direct_delivered = 0.0
        cache_delivered = 0.0
        for assignment in assignments:
            route_type = str(assignment["route_type"])
            station = int(assignment["workstation_index"])
            quantity = float(assignment["quantity"])

            if route_type in {"direct", "pallet_to_cache"}:
                lane_id = int(assignment["lane_id"])
                lane = lanes[lane_id]
                quantity = min(quantity, float(lane["remaining"]))
            elif route_type == "cache_to_workstation":
                cache_index = int(assignment["cache_index"])
                quantity = min(quantity, float(cache_inventory[cache_index]))
            else:
                continue

            if quantity <= 1e-8:
                continue
            assignment["quantity"] = quantity

            if route_type == "pallet_to_cache":
                cache_index = int(assignment["cache_index"])
                free_space = max(0.0, float(cache_capacity) - float(cache_inventory[cache_index]))
                quantity = min(quantity, free_space)
                if quantity <= 1e-8:
                    continue
                assignment["quantity"] = quantity
                cache_inventory[cache_index] += quantity
                assignment["moved_to_cache_quantity"] = quantity
                moved_to_cache += quantity
                lane["remaining"] = float(lane["remaining"]) - quantity
            elif route_type == "cache_to_workstation":
                cache_index = int(assignment["cache_index"])
                cache_inventory[cache_index] -= quantity
                station_queues[station] += quantity
                assignment["moved_to_cache_quantity"] = 0.0
                cache_delivered += quantity
            else:
                station_queues[station] += quantity
                assignment["moved_to_cache_quantity"] = 0.0
                direct_delivered += quantity
                lane["remaining"] = float(lane["remaining"]) - quantity

            next_agv_positions[int(assignment["agv_index"])] = assignment["drop"]
            if assignment.get("pallet_index") is not None:
                dispatched_global.append(int(assignment["pallet_index"]))
            routes.append(
                _task_row(
                    scenario=scenario_name,
                    period=period,
                    assignment=assignment,
                    pallet_ids=pallet_ids,
                    cache_global_indices=cache_global_indices,
                )
            )
            if assignment.get("pallet_index") is not None:
                workloads.append(
                    {
                        "scenario": scenario_name,
                        "period": period,
                        "pallet_index": int(assignment["pallet_index"]),
                        "pallet_id": pallet_ids[int(assignment["pallet_index"])],
                        "pending_quantity_before_round": "",
                        "planned_quantity_this_round": f"{quantity:.8f}",
                        "planned_receiver_type": "cache" if route_type == "pallet_to_cache" else "workstation",
                        "planned_receiver_index": int(assignment["cache_index"]) if route_type == "pallet_to_cache" else station,
                        "dispatched": 1,
                    }
                )

        process_rows, processed, actual_station_loads = process_station_available(
            scenario_name=scenario_name,
            period=period,
            data=data,
            station_queues=station_queues,
            cache_inventory=cache_inventory,
            cache_positions=cache_positions,
            cache_service_stations=cache_service_stations,
            station_capacity=station_capacity,
            pallet_ids=pallet_ids,
            cache_global_indices=cache_global_indices,
        )
        routes.extend(process_rows)
        remaining_quantity = sum(float(lane["remaining"]) for lane in lanes)
        remaining_indices = {
            int(lane["pallet_index"])
            for lane in lanes
            if float(lane["remaining"]) > 1e-8
        }
        nonzero_station = actual_station_loads[actual_station_loads > 1e-8]
        summaries.append(
            {
                "scenario": scenario_name,
                "period": period,
                "active_pallets_before": int(len(active_indices)),
                "dispatched_routes": int(len(assignments)),
                "direct_routes": int(sum(1 for row in assignments if row["route_type"] == "direct")),
                "inbound_routes": int(sum(1 for row in assignments if row["route_type"] == "pallet_to_cache")),
                "outbound_routes": int(sum(1 for row in assignments if row["route_type"] == "cache_to_workstation")),
                "processed_quantity": float(processed),
                "direct_delivered_quantity": float(direct_delivered),
                "cache_delivered_quantity": float(cache_delivered),
                "moved_to_cache_quantity": float(moved_to_cache),
                "remaining_pallets_after": int(len(remaining_indices)),
                "remaining_quantity_after": float(remaining_quantity),
                "station_queue_after": float(np.sum(station_queues)),
                "cache_quantity_after": float(np.sum(cache_inventory)),
                "station_count_used": int(np.count_nonzero(actual_station_loads > 1e-8)),
                "min_station_processed": float(np.min(nonzero_station)) if len(nonzero_station) else 0.0,
                "max_station_processed": float(np.max(nonzero_station)) if len(nonzero_station) else 0.0,
                "plan_status": "heuristic",
                "plan_iterations": 0,
                "assignment_status": assignment_status,
                "assignment_iterations": int(assignment_iter),
                "plan_objective": 0.0,
                "round_distance": float(round_distance),
            }
        )
        snapshots.append(
            {
                "scenario": scenario_name,
                "period": period,
                "active_indices": active_indices.copy(),
                "pending_quantities": pending_quantities.copy(),
                "dispatched_indices": np.asarray(dispatched_global, dtype=int),
                "routes": [_snapshot_route(row) for row in assignments]
                + [_snapshot_route_from_row(row) for row in process_rows],
                "agv_starts": np.asarray(agv_positions, dtype=float),
                "processed_quantity": processed,
                "remaining_quantity_after": float(remaining_quantity),
                "cache_quantity_after": float(np.sum(cache_inventory)),
            }
        )
        for cache_index, value in enumerate(cache_inventory):
            cache_rows.append(
                {
                    "period": period,
                    "cache_index": cache_index,
                    "cache_pallet_index": cache_global_indices[cache_index],
                    "cache_x": cache_positions[cache_index][0],
                    "cache_y": cache_positions[cache_index][1],
                    "service_workstation_index": int(cache_service_stations[cache_index]) if len(cache_service_stations) else "",
                    "inventory_before": f"{cache_before[cache_index]:.8f}",
                    "inventory_after": f"{value:.8f}",
                }
            )
        agv_positions = next_agv_positions

    if (
        sum(float(lane["remaining"]) for lane in lanes)
        + float(np.sum(station_queues))
        + float(np.sum(cache_inventory))
    ) > 1e-8:
        raise RuntimeError(f"{scenario_name} reached max_rounds before completion")
    return summaries, routes, workloads, snapshots, cache_rows


def summarize_comparison(summary_rows: list[dict[str, object]], route_rows: list[dict[str, object]]):
    scenario_order = {
        "task1_only": 0,
        "task1_partition": 1,
        "task1_partition_cache": 2,
    }
    scenarios = sorted(
        {str(row["scenario"]) for row in summary_rows},
        key=lambda name: (scenario_order.get(name, 99), name),
    )
    comparison: list[dict[str, object]] = []
    for scenario in scenarios:
        scenario_summaries = [row for row in summary_rows if row["scenario"] == scenario]
        scenario_routes = [row for row in route_rows if row["scenario"] == scenario]
        agv_routes = [row for row in scenario_routes if row.get("transport_mode", "agv") == "agv"]
        cache_outbound_routes = [row for row in agv_routes if row.get("route_type") == "cache_to_workstation"]
        process_routes = [row for row in scenario_routes if row.get("route_type") == "workstation_process"]
        total_agv_distance = sum(float(row["route_cost"]) for row in agv_routes)
        processed = sum(float(row["processed_quantity"]) for row in scenario_routes)
        moved_to_cache = sum(float(row["moved_to_cache_quantity"]) for row in scenario_routes)
        comparison.append(
            {
                "scenario": scenario,
                "rounds": len(scenario_summaries),
                "routes": len(scenario_routes),
                "agv_routes": len(agv_routes),
                "cache_outbound_routes": len(cache_outbound_routes),
                "station_process_routes": len(process_routes),
                "total_agv_distance": total_agv_distance,
                "processed_quantity": processed,
                "moved_to_cache_quantity": moved_to_cache,
                "final_remaining_quantity": scenario_summaries[-1]["remaining_quantity_after"],
                "final_cache_quantity": scenario_summaries[-1]["cache_quantity_after"],
            }
        )
    by_name = {row["scenario"]: row for row in comparison}
    if "task1_only" in by_name:
        base = float(by_name["task1_only"]["total_agv_distance"])
        for row in comparison:
            saved = base - float(row["total_agv_distance"])
            row["agv_distance_saved_vs_task1_only"] = saved if row["scenario"] != "task1_only" else 0.0
            row["agv_distance_saved_pct_vs_task1_only"] = saved / base if row["scenario"] != "task1_only" and base else 0.0
            row["round_delta_vs_task1_only"] = int(row["rounds"]) - int(by_name["task1_only"]["rounds"])
    if "task1_partition" in by_name and "task1_partition_cache" in by_name:
        partition_distance = float(by_name["task1_partition"]["total_agv_distance"])
        cache_row = by_name["task1_partition_cache"]
        cache_saved = partition_distance - float(cache_row["total_agv_distance"])
        cache_row["agv_distance_saved_vs_partition"] = cache_saved
        cache_row["agv_distance_saved_pct_vs_partition"] = cache_saved / partition_distance if partition_distance else 0.0
        cache_row["round_delta_vs_partition"] = int(cache_row["rounds"]) - int(by_name["task1_partition"]["rounds"])
    return comparison


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


def plot_route_maps(
    *,
    data,
    snapshots: list[dict[str, object]],
    selected_cache_indices: list[int],
    output: Path,
) -> None:
    _configure_plot_style()
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = 3
    rows = int(np.ceil(len(snapshots) / columns))
    fig_height = 3.35 + rows * 3.35
    fig, axes = plt.subplots(rows, columns, figsize=(18.5, fig_height), dpi=170)
    axes = np.asarray(axes).ravel()
    nodes = np.asarray([(x, y) for _, x, y in data.nodes], dtype=float)
    workstations = np.asarray(data.workstations, dtype=float)
    cache_points = np.asarray([data.pallets[idx] for idx in selected_cache_indices], dtype=float)

    for ax, snapshot in zip(axes, snapshots):
        ax.scatter(nodes[:, 0], nodes[:, 1], s=8, c=COLORS["node"], alpha=0.42, linewidths=0, zorder=0)
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
        pending_quantities = np.asarray(snapshot["pending_quantities"], dtype=float)
        active_points = np.asarray([data.pallets[int(idx)] for idx in active_indices], dtype=float)
        if len(active_points) > 0:
            ax.scatter(
                active_points[:, 0],
                active_points[:, 1],
                s=np.clip(pending_quantities / 1.9, 22, 110),
                c=COLORS["pallet_waiting"],
                edgecolors=COLORS["panel"],
                linewidths=0.45,
                alpha=0.80,
                zorder=2,
            )

        for route in snapshot["routes"]:
            start = np.asarray((route["start_x"], route["start_y"]), dtype=float)
            pickup = np.asarray((route["pickup_x"], route["pickup_y"]), dtype=float)
            drop = np.asarray((route["drop_x"], route["drop_y"]), dtype=float)
            first_start, first_end = _shortened_segment(start, pickup, start_gap=0.30, end_gap=0.34)
            second_start, second_end = _shortened_segment(pickup, drop, start_gap=0.34, end_gap=0.36)
            ax.plot(
                [first_start[0], first_end[0]],
                [first_start[1], first_end[1]],
                color=COLORS["pickup"],
                linewidth=1.25,
                linestyle="--",
                alpha=0.72,
                zorder=1,
            )
            route_type = str(route["route_type"])
            transport_mode = str(route.get("transport_mode", "agv"))
            if route_type == "pallet_to_cache":
                color, style = COLORS["inbound"], "-"
            elif route_type == "cache_to_workstation":
                color, style = COLORS["outbound"], "-."
            else:
                color, style = COLORS["direct"], "-"
            ax.plot(
                [second_start[0], second_end[0]],
                [second_start[1], second_end[1]],
                color=color,
                linewidth=1.25,
                linestyle=style,
                alpha=0.74,
                zorder=1,
            )

        dispatched_indices = [
            int(route["pallet_index"])
            for route in snapshot["routes"]
            if route.get("pallet_index") is not None
        ]
        if dispatched_indices:
            dispatched_points = np.asarray([data.pallets[idx] for idx in dispatched_indices], dtype=float)
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
        agv_starts = np.asarray(snapshot["agv_starts"], dtype=float)
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
                f"缓存库存 {snapshot.get('cache_quantity_after', 0.0):.0f} 件 | 路线 {len(snapshot['routes'])} 条"
            ),
            fontsize=11.0,
            fontweight="bold",
            pad=8,
        )

    for ax in axes[len(snapshots) :]:
        ax.axis("off")

    handles = [
        Line2D([0], [0], marker="^", color="none", markerfacecolor=COLORS["agv"], markeredgecolor=COLORS["panel"], markersize=8, label="AGV 起点"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["pallet_waiting"], markeredgecolor=COLORS["axis"], markersize=8, label="剩余托盘"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["pallet_dispatch"], markeredgecolor=COLORS["ink"], markersize=8, label="本轮取货托盘"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor=COLORS["workstation"], markeredgecolor=COLORS["panel"], markersize=8, label="工位"),
        Line2D([0], [0], marker="D", color="none", markerfacecolor=COLORS["cache"], markeredgecolor=COLORS["ink"], markersize=8, label="缓存点"),
        Line2D([0], [0], color=COLORS["pickup"], linestyle="--", linewidth=2.0, label="AGV 到取货点"),
        Line2D([0], [0], color=COLORS["inbound"], linewidth=2.0, label="托盘到缓存"),
        Line2D([0], [0], color=COLORS["outbound"], linestyle="-.", linewidth=2.0, label="AGV 缓存到工位"),
    ]
    fig.legend(
        handles=handles,
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
        f"任务1+动态分区+缓存：全部 {len(snapshots)} 轮滚动处理过程",
        fontsize=27,
        fontweight="bold",
        color=COLORS["ink"],
        y=0.986,
    )
    fig.text(
        0.5,
        0.955,
        "AGV 可选择直送、先入缓存或从缓存补给工位；只有进入工位队列后才按处理速度计入完成。",
        ha="center",
        va="top",
        fontsize=12.2,
        fontweight="semibold",
        color=COLORS["muted"],
    )
    fig.subplots_adjust(left=0.045, right=0.99, top=0.875, bottom=0.07, wspace=0.13, hspace=0.42)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def plot_comparison(comparison_rows: list[dict[str, object]], output: Path) -> None:
    _configure_plot_style()
    output.parent.mkdir(parents=True, exist_ok=True)
    label_map = {
        "task1_only": "仅任务1",
        "task1_partition": "任务1+动态分区",
        "task1_partition_cache": "任务1+动态分区+缓存",
    }
    labels = [label_map.get(str(row["scenario"]), str(row["scenario"])) for row in comparison_rows]
    distances = [float(row["total_agv_distance"]) for row in comparison_rows]
    rounds = [float(row["rounds"]) for row in comparison_rows]
    colors = [COLORS["direct"], COLORS["agv"], COLORS["cache"]]

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.2), dpi=170)
    axes[0].bar(labels, distances, color=colors[: len(labels)], edgecolor=COLORS["ink"], linewidth=0.8)
    axes[0].set_title("AGV 总行驶距离", fontsize=15, fontweight="bold")
    axes[0].set_ylabel("Manhattan distance")
    axes[1].bar(labels, rounds, color=colors[: len(labels)], edgecolor=COLORS["ink"], linewidth=0.8)
    axes[1].set_title("完成全部需求所需轮数", fontsize=15, fontweight="bold")
    axes[1].set_ylabel("Rounds")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y")
        ax.tick_params(axis="x", labelrotation=10)
    fig.suptitle("滚动处理消融实验：任务层逐步加入后的结果比较", fontsize=21, fontweight="bold", y=0.98)
    fig.subplots_adjust(top=0.82, bottom=0.16, left=0.08, right=0.98, wspace=0.28)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def write_rows(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def solve_multi_period(
    *,
    seed: int = 0,
    sample_prob: float = 0.6,
    max_agvs: int = 24,
    agv_capacity: float = 120.0,
    station_capacity: float = 160.0,
    cache_capacity: float = 600.0,
    balance_alpha: float = 1.15,
    choose_count: int = 10,
    min_distance: int = 6,
    max_rounds: int = 240,
    output_dir: Path = RESULTS_DIR,
    route_figure_path: Path = FIGURES_DIR / "multi_period_rolling_process.png",
    comparison_figure_path: Path = FIGURES_DIR / "cache_distance_comparison.png",
    verbose: bool = False,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], float]:
    start = time.perf_counter()
    data = load_data(agv_sample_prob=sample_prob, seed=seed, max_agvs=max_agvs)
    pallet_ids, pallet_coords, initial_inventory, _ = read_pallet_inventory()
    orders = read_orders()
    demand, unmet = allocate_initial_demand(
        orders,
        [dict(inventory) for inventory in initial_inventory],
        build_sku_index(initial_inventory),
    )
    if unmet > 1e-6:
        raise RuntimeError(f"initial demand has unmet quantity {unmet:.6f}")
    initial_agv_positions = [tuple(position) for position in data.agvs]

    _, _, selected_cache_indices, _, _, _ = solve_warehouse_layout(
        choose_count=choose_count,
        min_distance=min_distance,
        seed=seed,
        verbose=False,
    )
    selected_cache_positions = [pallet_coords[int(idx)] for idx in selected_cache_indices]
    partition_costs = distance_matrix(pallet_coords, data.workstations)
    partition_result, partition_flows, primary_stations, partition_loads, partition_objective = solve_balanced_partition_plan(
        demand,
        partition_costs,
        alpha=balance_alpha,
        verbose=verbose,
    )
    partition_allocation, primary_stations, partition_loads = repair_partition_to_primary_allocation(
        demand,
        partition_costs,
        partition_flows,
        alpha=balance_alpha,
    )
    partition_rows: list[dict[str, object]] = []
    for pallet_index in range(partition_allocation.shape[0]):
        for station_index in range(partition_allocation.shape[1]):
            quantity = float(partition_allocation[pallet_index, station_index])
            if quantity > 1e-5:
                partition_rows.append(
                    {
                        "pallet_index": pallet_index,
                        "pallet_id": pallet_ids[pallet_index],
                        "workstation_index": station_index,
                        "quantity": f"{quantity:.8f}",
                        "primary_station": int(primary_stations[pallet_index]),
                    }
                )

    task1_allocation = build_nearest_allocation(demand, partition_costs)
    task1_lanes, empty_cache_services = build_transport_lanes(
        allocation=task1_allocation,
        pallet_coords=pallet_coords,
        workstations=data.workstations,
        cache_positions=[],
        use_cache=False,
    )
    partition_lanes, _ = build_transport_lanes(
        allocation=partition_allocation,
        pallet_coords=pallet_coords,
        workstations=data.workstations,
        cache_positions=[],
        use_cache=False,
    )
    cache_lanes, cache_service_stations = build_transport_lanes(
        allocation=partition_allocation,
        pallet_coords=pallet_coords,
        workstations=data.workstations,
        cache_positions=selected_cache_positions,
        use_cache=True,
    )

    task1_summary, task1_routes, task1_workload, _task1_snapshots, _ = simulate_transport_processing_scenario(
        scenario_name="task1_only",
        data=data,
        pallet_ids=pallet_ids,
        lanes=task1_lanes,
        initial_agv_positions=initial_agv_positions,
        cache_global_indices=[],
        cache_positions=[],
        cache_service_stations=empty_cache_services,
        max_agvs=max_agvs,
        agv_capacity=agv_capacity,
        station_capacity=station_capacity,
        cache_capacity=cache_capacity,
        max_rounds=max_rounds,
        verbose=verbose,
    )
    partition_summary, partition_routes, partition_workload, _partition_snapshots, _ = simulate_transport_processing_scenario(
        scenario_name="task1_partition",
        data=data,
        pallet_ids=pallet_ids,
        lanes=partition_lanes,
        initial_agv_positions=initial_agv_positions,
        cache_global_indices=[],
        cache_positions=[],
        cache_service_stations=empty_cache_services,
        max_agvs=max_agvs,
        agv_capacity=agv_capacity,
        station_capacity=station_capacity,
        cache_capacity=cache_capacity,
        max_rounds=max_rounds,
        verbose=verbose,
    )
    cache_summary, cache_routes, cache_workload, cache_snapshots, cache_inventory = simulate_transport_processing_scenario(
        scenario_name="task1_partition_cache",
        data=data,
        pallet_ids=pallet_ids,
        lanes=cache_lanes,
        initial_agv_positions=initial_agv_positions,
        cache_global_indices=[int(idx) for idx in selected_cache_indices],
        cache_positions=selected_cache_positions,
        cache_service_stations=cache_service_stations,
        max_agvs=max_agvs,
        agv_capacity=agv_capacity,
        station_capacity=station_capacity,
        cache_capacity=cache_capacity,
        max_rounds=max_rounds,
        verbose=verbose,
    )

    summary_rows = task1_summary + partition_summary + cache_summary
    route_rows = task1_routes + partition_routes + cache_routes
    workload_rows = task1_workload + partition_workload + cache_workload
    comparison_rows = summarize_comparison(summary_rows, route_rows)

    write_rows(output_dir / "multi_period_summary.csv", summary_rows)
    write_rows(output_dir / "multi_period_routes.csv", route_rows)
    write_rows(output_dir / "multi_period_workload.csv", workload_rows)
    write_rows(output_dir / "cache_inventory.csv", cache_inventory)
    write_rows(output_dir / "multi_period_partition.csv", partition_rows)
    write_rows(output_dir / "multi_period_comparison.csv", comparison_rows)
    plot_route_maps(
        data=data,
        snapshots=cache_snapshots,
        selected_cache_indices=selected_cache_indices,
        output=route_figure_path,
    )
    plot_comparison(comparison_rows, comparison_figure_path)

    elapsed = time.perf_counter() - start
    return summary_rows, route_rows, comparison_rows, elapsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sample-prob", type=float, default=0.6)
    parser.add_argument("--max-agvs", type=int, default=24)
    parser.add_argument("--agv-capacity", type=float, default=120.0)
    parser.add_argument("--station-capacity", type=float, default=160.0)
    parser.add_argument("--cache-capacity", type=float, default=600.0)
    parser.add_argument("--balance-alpha", type=float, default=1.15)
    parser.add_argument("--choose-count", type=int, default=10)
    parser.add_argument("--min-distance", type=int, default=6)
    parser.add_argument("--max-rounds", type=int, default=240)
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--route-figure", default="figures/multi_period_rolling_process.png")
    parser.add_argument("--comparison-figure", default="figures/cache_distance_comparison.png")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    summary_rows, route_rows, comparison_rows, elapsed = solve_multi_period(
        seed=args.seed,
        sample_prob=args.sample_prob,
        max_agvs=args.max_agvs,
        agv_capacity=args.agv_capacity,
        station_capacity=args.station_capacity,
        cache_capacity=args.cache_capacity,
        balance_alpha=args.balance_alpha,
        choose_count=args.choose_count,
        min_distance=args.min_distance,
        max_rounds=args.max_rounds,
        output_dir=Path(args.output_dir),
        route_figure_path=Path(args.route_figure),
        comparison_figure_path=Path(args.comparison_figure),
        verbose=args.verbose,
    )
    print("Rolling ablation optimization")
    print(f"scenarios={len(comparison_rows)} route_records={len(route_rows)} time={elapsed:.3f}s")
    for row in comparison_rows:
        print(
            f"[{row['scenario']}] rounds={row['rounds']} "
            f"agv_routes={row.get('agv_routes', row['routes'])} "
            f"agv_distance={float(row['total_agv_distance']):.3f} "
            f"processed={float(row['processed_quantity']):.3f} "
            f"cached={float(row['moved_to_cache_quantity']):.3f}"
        )
    if any(row["scenario"] == "task1_partition_cache" for row in comparison_rows):
        cache_result = next(row for row in comparison_rows if row["scenario"] == "task1_partition_cache")
        print(
            "cache agv-distance saving vs partition="
            f"{float(cache_result.get('agv_distance_saved_vs_partition', 0.0)):.3f} "
            f"({100 * float(cache_result.get('agv_distance_saved_pct_vs_partition', 0.0)):.2f}%)"
        )
    print(f"wrote {Path(args.output_dir) / 'multi_period_comparison.csv'}")
    print(f"wrote {Path(args.route_figure)}")
    print(f"wrote {Path(args.comparison_figure)}")


if __name__ == "__main__":
    main()
