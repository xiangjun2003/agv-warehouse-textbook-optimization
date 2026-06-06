# AGV Warehouse Optimization without COPT

This repository contains the no-COPT implementation of the AGV warehouse
optimization course project. It reproduces the three project tasks with local
CSV data and textbook-style Python algorithms.

## Tasks

1. **AGV assignment**: assign AGVs to pallets and pallets to workstations while
   minimizing pickup and delivery distance.
2. **Dynamic partition**: split pallet quantities across workstation areas while
   balancing distance cost and workstation load.
3. **Warehouse layout**: select important candidate storage/cache positions
   under spacing constraints.

## Algorithms

- `algorithms/primal_dual_lp.py`: primal-dual interior-point method for linear
  programming.
- `algorithms/projected_bb_gradient.py`: projected Barzilai-Borwein gradient
  method for box-constrained subproblems.
- `algorithms/quadratic_penalty.py`: quadratic penalty method for constrained
  optimization.

## Reproduce

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_all_no_copt.py
```

Outputs are written to `results/`.

## Repository Contents

- `data/`: local warehouse CSV data.
- `algorithms/`: self-implemented textbook algorithms.
- `solve_*.py`: task-specific model builders and solvers.
- `run_all_no_copt.py`: one-click reproduction entry point.
- `results/`: reproduced CSV outputs.
- `deliverables/`: final presentation artifacts.

The original COPT notebooks and local reference PDFs are intentionally excluded
from the GitHub repository.

