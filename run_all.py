from __future__ import annotations

from pathlib import Path
import time

from solve_agv_assignment import solve_agv_assignment, write_assignment
from solve_dynamic_partition import solve_dynamic_partition, write_assignment as write_partition
from solve_warehouse_layout import solve_warehouse_layout, write_layout


def main():
    total_start = time.perf_counter()

    data_dyn, dyn_result, z, loads, dyn_obj, dyn_time = solve_dynamic_partition()
    write_partition(Path("results/dynamic_partition.csv"), z)
    print(
        f"[dynamic] status={dyn_result.status} iter={dyn_result.iterations} "
        f"obj={dyn_obj:.3f} time={dyn_time:.3f}s"
    )

    data_agv, agv_result, assignments, station_load, agv_cost, agv_time = solve_agv_assignment()
    write_assignment(Path("results/agv_assignment.csv"), assignments)
    print(
        f"[agv] status={agv_result.status} iter={agv_result.iterations} "
        f"lp_obj={agv_result.objective:.3f} integer_cost={agv_cost:.3f} "
        f"time={agv_time:.3f}s"
    )

    data_layout, layout_result, selected, edges, min_dist, layout_time = solve_warehouse_layout()
    write_layout(Path("results/warehouse_layout.csv"), selected, data_layout.pallets)
    print(
        f"[layout] status={layout_result.status} outer={layout_result.outer_iterations} "
        f"selected={len(selected)} min_dist={min_dist} time={layout_time:.3f}s"
    )

    print(f"total_time={time.perf_counter() - total_start:.3f}s")


if __name__ == "__main__":
    main()
