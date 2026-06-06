# No-COPT Optimization Implementation

This folder now includes a reproducible implementation of the warehouse
optimization project without COPT.

## Algorithms

- `algorithms/primal_dual_lp.py`
  - Chapter 7 linear-programming primal-dual interior-point method.
  - Used by `solve_dynamic_partition.py` and `solve_agv_assignment.py`.

- `algorithms/projected_bb_gradient.py`
  - Chapter 6 Barzilai-Borwein gradient method with box projection.
  - Used as the inner solver for warehouse layout.

- `algorithms/quadratic_penalty.py`
  - Chapter 7 quadratic penalty method.
  - Used by `solve_warehouse_layout.py`.

## Run

```bash
source .venv/bin/activate
python run_all_no_copt.py
```

You can also run each task separately:

```bash
python solve_dynamic_partition.py
python solve_agv_assignment.py
python solve_warehouse_layout.py
```

The scripts write CSV outputs under `results/`.
