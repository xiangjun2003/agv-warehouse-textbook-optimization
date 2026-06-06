# AGV Warehouse Optimization without COPT

This repository is the reproducible no-COPT version of an AGV warehouse
optimization course project. It follows the same narrative order as the
presentation deck: warehouse background, task meaning, modeling, textbook
algorithms, experiment setup, and result analysis.

## 1. Background

Modern warehouses use AGVs, or automated guided vehicles, to move pallets
between storage positions and workstations. Even when AGVs can move
automatically, the system still needs optimization:

- AGVs are limited resources.
- Pallets are scattered across warehouse coordinates.
- Workstations need stable supply and balanced workload.
- Cache or transfer locations should not be overly concentrated.

The project turns these operational questions into optimization models that
can be generated and solved automatically from local CSV data.

## 2. Warehouse Entities

- **AGV**: an automated vehicle that moves from its current position to a
  pallet and then delivers the pallet to a workstation or area.
- **Pallet**: a standardized load unit carrying one or more SKUs. In this
  project, each pallet has a coordinate and a total quantity.
- **Workstation**: a processing point such as picking, packing, inspection, or
  temporary handling.
- **Warehouse area**: in Task 2, an area is not a fixed room. It is the service
  range formed by assigning pallet quantities to workstations.
- **Candidate storage/cache position**: in Task 3, candidate locations are
  existing pallet/storage coordinates that may be selected as important cache
  or transfer points.

Distances are approximated by Manhattan distance because AGVs usually move on a
warehouse grid:

```text
dist(a, b) = |x_a - x_b| + |y_a - y_b|
```

## 3. Project Content

The project contains three optimization tasks:

1. **AGV assignment**: decide which AGV serves which pallet and which
   workstation receives it.
2. **Dynamic partition**: decide how much quantity from each pallet is assigned
   to each workstation.
3. **Warehouse layout selection**: choose important cache or transfer positions
   from candidate pallet/storage locations.

These tasks cover three levels of warehouse decision-making: daily dispatching,
workload-area organization, and layout-level cache selection.

## 4. Task 1: AGV Assignment

### Meaning

Task 1 answers: **who should move which pallet, and where should it be sent?**

A result row can be read as:

```text
AGV i picks pallet j and sends it to workstation k.
```

### Model

The model separates one transport job into pickup distance and delivery
distance.

Decision variables:

```text
x(i,j): whether AGV i serves pallet j
y(j,k): whether pallet j is sent to workstation k
```

Objective:

```text
min sum d(AP) x(i,j) + sum d(PW) y(j,k)
```

where `d(AP)` is the AGV-to-pallet distance, and `d(PW)` is the
pallet-to-workstation distance.

The model also enforces constraints such as one task per AGV, consistency
between pickup and delivery, and workstation capacity.

### Algorithm

The linear-programming relaxation is solved by the self-implemented
primal-dual interior-point method in `algorithms/primal_dual_lp.py`. A recovery
step then converts the relaxed solution into executable integer assignments.

### Output

`results/agv_assignment.csv` contains:

```text
agv_index,pallet_index,workstation_index,cost
```

## 5. Task 2: Dynamic Partition

### Meaning

Task 2 answers: **which workstation should process each pallet's quantity?**

Unlike Task 1, this is not vehicle-task matching. It is a quantity-flow model:
a pallet's quantity can be distributed to workstation service areas.

### Model

Decision variable:

```text
z(j,k): quantity from pallet j assigned to workstation k
```

Parameters:

```text
q(j): total quantity of pallet j
d(j,k): distance from pallet j to workstation k
```

Objective:

```text
min sum d(j,k) z(j,k)
```

Main constraints:

- each pallet's quantity must be fully assigned;
- each workstation must receive at least a minimum workload;
- all quantity flows are nonnegative.

### Algorithm

This is a standard linear program, so it is solved directly by the
self-implemented primal-dual interior-point method.

### Output

`results/dynamic_partition.csv` contains:

```text
pallet_index,workstation_index,quantity
```

## 6. Task 3: Warehouse Layout Selection

### Meaning

Task 3 answers: **which existing candidate locations should become important
cache or transfer positions?**

This is a layout-level decision. It is not deciding where a single pallet moves
today; it selects a set of useful positions for high-frequency storage,
workstation replenishment, temporary AGV transfer, or pre-shipping staging.

### Model

Decision variable:

```text
x(i) in {0, 1}: whether candidate position i is selected
```

The experiment selects a fixed number of positions:

```text
sum x(i) = 10
```

Spacing constraints prevent selected positions from being too close:

```text
x(i) + x(j) <= 1, if dist(i,j) <= 6
```

A small score term prefers higher-value positions. In the current experiment,
the score is approximated from pallet quantity.

### Algorithm

Task 3 is handled by:

- `algorithms/quadratic_penalty.py`: quadratic penalty method for equality and
  inequality constraints;
- `algorithms/projected_bb_gradient.py`: projected Barzilai-Borwein gradient
  method for the box-constrained continuous relaxation;
- a discrete repair step in `solve_warehouse_layout.py` that converts the
  relaxed solution into a feasible 0-1 layout.

### Output

`results/warehouse_layout.csv` contains:

```text
pallet_index,x,y
```

## 7. Experiment Setup

Repository structure:

```text
data/                    local warehouse CSV data
algorithms/              self-implemented textbook algorithms
warehouse_data.py         CSV reading and distance matrix construction
solve_agv_assignment.py   Task 1 model builder and solver
solve_dynamic_partition.py Task 2 model builder and solver
solve_warehouse_layout.py Task 3 model builder and solver
run_all_no_copt.py        one-click reproduction entry point
results/                 generated CSV outputs
scripts/                 presentation-data and HTML-deck helper scripts
```

The workflow is automated:

```text
CSV data -> distance matrices -> model matrices -> textbook algorithms -> CSV results
```

## 8. Algorithm-Task Mapping

| Task | Problem Type | Algorithm |
| --- | --- | --- |
| Task 1 AGV assignment | linear-programming relaxation plus integer recovery | primal-dual interior-point method |
| Task 2 dynamic partition | linear programming | primal-dual interior-point method |
| Task 3 layout selection | constrained 0-1 selection via continuous relaxation | quadratic penalty + projected BB gradient + repair |

## 9. Result Summary

Running `python run_all_no_copt.py` reproduces the three tasks. A typical run
produces:

```text
[dynamic] status=optimal obj=79350.200
[agv] status=optimal integer_cost=131.000
[layout] status=optimal selected=10 min_dist=7
```

The results show three different optimization layers:

- Task 1 reduces transport distance for executable AGV routes.
- Task 2 balances workstation service load while controlling distance cost.
- Task 3 selects spatially separated cache or transfer positions for layout
  planning.

## 10. Reproduce

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_all_no_copt.py
```

You can also run each task separately:

```bash
python solve_agv_assignment.py
python solve_dynamic_partition.py
python solve_warehouse_layout.py
```

Presentation deliverables, original COPT notebooks, local reference PDFs,
virtual environments, and intermediate generated artifacts are intentionally
excluded from the GitHub repository.

