from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from solve_agv_assignment import solve_agv_assignment
from solve_dynamic_partition import solve_dynamic_partition
from solve_warehouse_layout import solve_warehouse_layout
from warehouse_data import distance_matrix, load_data


WORKSPACE = ROOT / "outputs/manual-20260601-agv-textbook/presentations/agv-textbook-deck"
ASSET_DIR = WORKSPACE / "assets"


TYPE_LABELS = {
    "1": "路径",
    "2": "储位",
    "3": "充电桩",
    "4": "柱子",
    "5": "拣选工位",
    "6": "补货位",
    "7": "空托集放",
    "8": "空托输送",
}


def js_literal(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def main():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    raw = load_data(agv_sample_prob=None)

    node_counts = Counter(node_type for node_type, _, _ in raw.nodes)
    pallet_quantities = raw.pallet_quantities
    quantity_stats = {
        "total": float(np.sum(pallet_quantities)),
        "mean": float(np.mean(pallet_quantities)),
        "median": float(np.median(pallet_quantities)),
        "max": float(np.max(pallet_quantities)),
        "min": float(np.min(pallet_quantities)),
    }
    q_sorted = np.sort(pallet_quantities)
    quantity_bins = [
        {"label": "0-40", "count": int(np.sum((pallet_quantities > 0) & (pallet_quantities <= 40)))},
        {"label": "41-80", "count": int(np.sum((pallet_quantities > 40) & (pallet_quantities <= 80)))},
        {"label": "81-120", "count": int(np.sum((pallet_quantities > 80) & (pallet_quantities <= 120)))},
        {"label": "121+", "count": int(np.sum(pallet_quantities > 120))},
    ]

    dyn_data, dyn_result, z, station_loads, dyn_obj, dyn_time = solve_dynamic_partition()
    agv_data, agv_result, assignments, station_load, agv_cost, agv_time = solve_agv_assignment()
    layout_data, layout_result, selected, edges, min_dist, layout_time = solve_warehouse_layout()

    workstation_positions = dyn_data.workstations
    pallet_positions = dyn_data.pallets
    agv_positions = agv_data.agvs

    station_summary = [
        {
            "index": int(k),
            "x": int(workstation_positions[k][0]),
            "y": int(workstation_positions[k][1]),
            "load": float(station_loads[k]),
            "tasks": int(station_load[k]) if k < len(station_load) else 0,
        }
        for k in range(len(workstation_positions))
    ]
    dynamic_pallet_assignments = []
    for j, ((x, y), quantity) in enumerate(zip(pallet_positions, dyn_data.pallet_quantities)):
        dominant_station = int(np.argmax(z[j]))
        dynamic_pallet_assignments.append(
            {
                "pallet": int(j),
                "x": int(x),
                "y": int(y),
                "quantity": float(quantity),
                "station": dominant_station,
                "assigned_quantity": float(z[j, dominant_station]),
                "share": float(z[j, dominant_station] / max(quantity, 1.0)),
            }
        )

    assignment_rows = []
    for agv_index, pallet_index, workstation_index, cost in assignments:
        agv = agv_positions[agv_index]
        pallet = pallet_positions[pallet_index]
        workstation = workstation_positions[workstation_index]
        assignment_rows.append(
            {
                "agv": int(agv_index),
                "pallet": int(pallet_index),
                "workstation": int(workstation_index),
                "cost": float(cost),
                "agv_xy": [int(agv[0]), int(agv[1])],
                "pallet_xy": [int(pallet[0]), int(pallet[1])],
                "workstation_xy": [int(workstation[0]), int(workstation[1])],
            }
        )

    selected_positions = [
        {
            "pallet": int(idx),
            "x": int(layout_data.pallets[idx][0]),
            "y": int(layout_data.pallets[idx][1]),
            "quantity": float(layout_data.pallet_quantities[idx]),
        }
        for idx in selected
    ]

    selected_distances = distance_matrix(
        [(item["x"], item["y"]) for item in selected_positions],
        [(item["x"], item["y"]) for item in selected_positions],
    )
    pair_distances = [
        float(selected_distances[i, j])
        for i in range(len(selected_positions))
        for j in range(i + 1, len(selected_positions))
    ]

    map_nodes = [
        {"type": t, "x": int(x), "y": int(y)}
        for t, x, y in raw.nodes
    ]

    data = {
        "project": {
            "title": "AGV 仓储优化项目",
            "subtitle": "基于教材算法的任务分配、动态分区与布局选址独立实验",
            "date": "2026-06-01",
        },
        "input": {
            "map": {
                "ncols": int(raw.ncols),
                "nrows": int(raw.nrows),
                "nodes": map_nodes,
                "counts": [
                    {"type": key, "label": TYPE_LABELS.get(key, key), "count": int(node_counts[key])}
                    for key in sorted(node_counts)
                ],
            },
            "pallets": {
                "count": len(raw.pallets),
                "positions": [
                    {"x": int(x), "y": int(y), "quantity": float(q)}
                    for (x, y), q in zip(raw.pallets, raw.pallet_quantities)
                ],
                "quantity_stats": quantity_stats,
                "quantity_bins": quantity_bins,
                "top_quantities": [
                    {"rank": int(rank + 1), "quantity": float(value)}
                    for rank, value in enumerate(q_sorted[-8:][::-1])
                ],
            },
            "agvs_total": len(raw.agvs),
            "agvs_sampled": len(agv_positions),
            "workstations": {
                "count": len(raw.workstations),
                "positions": [
                    {"x": int(x), "y": int(y)}
                    for x, y in raw.workstations
                ],
            },
            "orders_rows": 675,
        },
        "results": {
            "dynamic": {
                "objective": float(dyn_obj),
                "iterations": int(dyn_result.iterations),
                "time": float(dyn_time),
                "primal_residual": float(dyn_result.primal_residual),
                "dual_residual": float(dyn_result.dual_residual),
                "gap": float(dyn_result.gap),
                "loads": station_summary,
                "pallet_assignments": dynamic_pallet_assignments,
                "min_load": float(np.min(station_loads)),
                "max_load": float(np.max(station_loads)),
            },
            "agv": {
                "lp_objective": float(agv_result.objective),
                "integer_cost": float(agv_cost),
                "iterations": int(agv_result.iterations),
                "time": float(agv_time),
                "assignments": assignment_rows,
                "station_load": [int(x) for x in station_load.tolist()],
            },
            "layout": {
                "selected": selected_positions,
                "conflict_edges": len(edges),
                "min_pair_distance": int(min_dist),
                "mean_pair_distance": float(np.mean(pair_distances)),
                "outer_iterations": int(layout_result.outer_iterations),
                "time": float(layout_time),
                "equality_violation": float(layout_result.equality_violation),
                "inequality_violation": float(layout_result.inequality_violation),
            },
            "total_time": float(dyn_time + agv_time + layout_time),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "algorithm": {
            "dynamic": "线性规划原始-对偶内点法（教材第 7 章）",
            "agv": "线性规划原始-对偶内点法 + 整数解恢复（教材第 7 章）",
            "layout": "二次罚函数法（教材第 7 章）+ 投影 BB 梯度法（教材第 6 章）+ 离散修复",
        },
    }

    json_path = ASSET_DIR / "deck-data.json"
    mjs_path = ASSET_DIR / "deck-data.mjs"
    json_path.write_text(js_literal(data) + "\n", encoding="utf-8")
    mjs_path.write_text(f"export const deckData = {js_literal(data)};\n", encoding="utf-8")
    print(json_path)
    print(mjs_path)


if __name__ == "__main__":
    main()
