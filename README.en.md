# AGV Warehouse Optimization Course Project

Language: [中文](README.md) | English

This repository contains a complete AGV warehouse optimization course project.
It uses local CSV data, automated model-building scripts, and
self-implemented textbook optimization algorithms to solve three warehouse
decision tasks: AGV assignment, dynamic partitioning, and cache/transfer
location selection.

The README follows the same narrative order as the presentation: background,
entities and data, task meaning, modeling, textbook algorithm mapping,
experiment setup, and result analysis.

## 1. Background, Entities, and Data

In an automated warehouse, AGVs move pallets through a grid of aisles and
nodes. Although this may look like simple point-to-point movement, AGV
dispatching and warehouse layout directly affect transport cost, order
processing speed, workstation waiting time, and local congestion.

This project can be understood as a small intelligent warehouse decision
system. Given a set of pallets, AGVs, and workstations, it answers three
connected operational questions:

- **Who should move the current batch of pallets?** For example, during a
  shipping peak, 12 AGVs may be parked at different locations. Randomly
  assigning vehicles can create unnecessary empty travel across the warehouse,
  while optimized assignment sends nearby AGVs to more suitable pallets. This
  corresponds to **Task 1: AGV assignment**.
- **Which workstation should process which quantities?** If every pallet is
  assigned only to its nearest workstation, one workstation may become
  overloaded while others remain idle. Dynamic partitioning balances transport
  distance and workstation workload. This corresponds to **Task 2: dynamic
  partitioning**.
- **Which locations should be used as cache or transfer points?** High-frequency
  replenishment, pre-shipping staging, and workstation-side buffers need useful
  locations. If those locations are too concentrated, AGVs may queue and block
  local aisles. This corresponds to **Task 3: cache/transfer location
  selection**.

The practical value of the project is to convert warehouse operations into
computable, reproducible, and explainable optimization models:

- **lower transport cost** by reducing empty travel, detours, battery usage,
  equipment wear, and manual intervention;
- **higher operating efficiency** by shortening pickup and delivery paths;
- **more stable workstation workload** by avoiding overloaded and idle stations;
- **lower congestion risk** by spacing important cache/transfer locations;
- **better management decisions** by explaining why vehicles, areas, and
  locations are chosen.

![Background and data overview](figures/background_data_overview.png)

The project uses the following warehouse entities:

- **AGV**: an automated guided vehicle. In Task 1, an AGV moves from its
  current position to a pallet, picks it, and delivers it to a workstation.
- **Pallet**: a standardized load unit. `pallets.csv` gives each pallet's
  coordinate, pallet ID, and SKU quantities. The model aggregates SKU
  quantities into a total pallet quantity.
- **Workstation**: a processing point such as picking, packing, inspection, or
  temporary handling. Nodes with type `5` in `map.csv` are read as
  workstations.
- **Warehouse area**: in Task 2, an area is not a fixed room. It is the service
  range formed by assigning pallet quantities to workstations.
- **Candidate storage/cache position**: in Task 3, candidate positions are
  existing pallet/storage coordinates that may be selected as important cache
  or transfer locations.
- **Aisle/key node**: road nodes, storage nodes, charging nodes, connection
  nodes, and workstations describe the warehouse grid. The current models use
  Manhattan distance as a grid-travel approximation.

Distance is defined as:

```text
dist(a, b) = |x_a - x_b| + |y_a - y_b|
```

### Visual Color Rules

All README figures use a consistent visual language:

| Meaning | Color in figures | Explanation |
| --- | --- | --- |
| AGV | blue triangle | vehicle position or vehicle starting point |
| Pallet | green circle | existing pallet location; point size often represents quantity |
| Workstation | red square | picking, packing, processing, inspection, or temporary handling point |
| Candidate location | light-blue circle | candidate location in Task 3 |
| Selected cache/transfer location | orange diamond | final selected location in Task 3 |
| Pickup/delivery route | blue dashed line / orange solid line | AGV-to-pallet and pallet-to-workstation distance in Task 1 |

Task 2 uses an additional fixed categorical palette to show which workstation
mainly serves each pallet. The workstation markers remain red, and the workload
bars remain green.

### Dataset Details

The data are not generated on the fly. They are local warehouse CSV files under
`data/`. Each run reads these files, builds coordinates, quantities, AGV
positions, and demand context, and then constructs the optimization models.

| File | Fields | Scale | Real-world meaning | Role in the model |
| --- | --- | --- | --- | --- |
| `data/map.csv` | `Type`, `X`, `Y`, `All_Car`, `Free_Car` | 704 map nodes, warehouse size 32 x 22, including 18 workstation nodes with type `5` | warehouse grid, aisles, storage nodes, charging nodes, connection nodes, and workstations | reads warehouse nodes and workstation coordinates; supports Manhattan distance calculation |
| `data/pallets.csv` | `{SKU:Amount} List`, `X`, `Y`, `Pallet ID` | 140 pallets, total pallet quantity 8478, single-pallet quantity range 26 to 192 | current pallet inventory and storage distribution | provides pallet coordinates, pallet quantities, and Task 3 candidate locations |
| `data/bots.csv` | `car_id`, `x`, `y`, `direction` | 50 AGV positions; the default experiment samples 12 AGVs for Task 1 | current vehicle state in the warehouse | provides AGV starting positions; direction is retained but not used by the current distance model |
| `data/orders.csv` | `Order ID`, `SKU`, `Required Amount`, `Order Received Time`, `Deadline Time` | 675 order records, 181 unique SKUs, total demand 8478 | demand context explaining why inventory needs to be moved and processed | current models optimize from pallet inventory and coordinates; orders can support later order-level dispatching |

The data relationships are:

- `map.csv` describes warehouse space: where AGVs can move and where
  workstations are located.
- `pallets.csv` describes inventory state: where goods are stored and how much
  quantity each pallet contains.
- `bots.csv` describes fleet state: which AGVs can depart from which positions.
- `orders.csv` describes demand context. Its total demand is 8478, matching the
  total pallet quantity of 8478, so it explains the business scale of the
  current inventory/demand batch.

Data preprocessing includes:

- skipping comment and description rows in CSV files;
- parsing the `"SKU:quantity,SKU:quantity"` string in `pallets.csv` into a
  dictionary and aggregating each pallet's total quantity `q(j)`;
- reading nodes with type `5` in `map.csv` as workstation coordinates;
- keeping `map.csv` node types `1/2/3/4/6/7/8` as background or raw map nodes
  rather than separate decision entities; therefore labels such as "node 6/7/8"
  are no longer shown in the figure legends;
- reading AGV coordinates from `bots.csv` and sampling 12 AGVs with a fixed
  seed for a reproducible dispatching batch;
- building AGV-pallet, pallet-workstation, and pallet-pallet distance matrices.

The three tasks use the data differently:

| Task | Data used | How the data enter the model |
| --- | --- | --- |
| Task 1 AGV assignment | `bots.csv`, `pallets.csv`, `map.csv` | AGV, pallet, and workstation coordinates define the two-stage route cost: `AGV -> pallet -> workstation` |
| Task 2 dynamic partitioning | `pallets.csv`, `map.csv` | pallet quantities are supply amounts, and pallet-workstation distances are unit assignment costs |
| Task 3 cache/transfer location selection | `pallets.csv`, `map.csv` | existing pallet/storage coordinates are candidate locations, and pallet-pallet distances define spatial conflict constraints |

The only randomness in the default experiment is AGV sampling for Task 1. It
represents the current dispatchable vehicle set. The warehouse map, pallet
locations, pallet quantities, and order records all come from fixed CSV files,
so the experiment is directly reproducible.

## 2. Project Content

The project contains three optimization tasks:

1. **AGV assignment**: decide which AGV serves which pallet and which
   workstation receives it.
2. **Dynamic partitioning**: decide how much quantity from each pallet is
   assigned to each workstation, forming workstation service areas.
3. **Cache/transfer location selection**: choose important cache or transfer
   positions from candidate storage locations.

These tasks correspond to three warehouse decision levels: daily dispatching,
area organization, and layout planning.

## 3. Automated Modeling and Solving Workflow

The workflow is automated. Running `python run_all.py` reads the data, builds
distance matrices, constructs objective vectors and constraint matrices, calls
the textbook algorithms, and writes results into `results/`.

```text
CSV data
  -> warehouse_data.py reads coordinates, quantities, AGVs, and workstations
  -> solve_*.py builds objective vectors and constraint matrices
  -> algorithms/*.py solves the models with textbook algorithms
  -> results/*.csv stores experiment outputs
```

Repository structure:

```text
data/                         local warehouse CSV data
figures/                      figures used in this README
algorithms/                   self-implemented textbook algorithms
warehouse_data.py              data loading and distance matrix construction
solve_agv_assignment.py        Task 1 model builder and solver
solve_dynamic_partition.py     Task 2 model builder and solver
solve_warehouse_layout.py      Task 3 model builder and solver
run_all.py                     one-click reproduction entry point
results/                       generated CSV outputs
scripts/make_readme_figures.py README figure generation script
```

Default problem sizes:

| Task | Default size |
| --- | --- |
| Task 1 | 12 AGVs, 140 pallets, 18 workstations; 4498 LP variables and 450 equality constraints |
| Task 2 | 140 pallets and 18 workstations; 2538 LP variables and 158 equality constraints |
| Task 3 | select 10 locations from 140 candidates; 140 continuous relaxation variables and 2165 spatial conflict edges |

## 4. Task 1: AGV Assignment

![Task 1 AGV assignment](figures/task1_agv_assignment.png)

### Meaning

Task 1 answers: **which AGV should move which pallet, and where should it be
sent?**

A result row can be read as:

```text
AGV i moves from its current position, picks pallet j, and delivers it to workstation k.
```

Poor assignment causes empty travel, detours, and workstation waiting. A good
assignment reduces pickup and delivery distance for the current dispatching
batch.

### Model

One movement is split into two distance components:

```text
AGV -> pallet
pallet -> workstation
```

Decision variables:

```text
x(i,j): whether AGV i serves pallet j
y(j,k): whether pallet j is delivered to workstation k
```

Objective:

```text
min sum d(AGV_i, pallet_j) x(i,j)
  + sum d(pallet_j, workstation_k) y(j,k)
```

Main constraints:

- each sampled AGV receives one transport task;
- each pallet is picked by at most one AGV;
- pickup and delivery decisions must be consistent;
- each workstation has a receiving-capacity limit.

### Textbook Algorithm

Task 1 is formulated as a linear-programming relaxation and solved with the
**Chapter 7 primal-dual interior-point method for linear programming**. The
implementation is in `algorithms/primal_dual_lp.py`.

The solver handles:

```text
min c^T x
s.t. A x = b, x >= 0
```

It maintains primal variables `x`, dual variables `y`, and slacks `s`, and uses
Newton directions to reduce primal residual, dual residual, and complementarity
gap. After solving the relaxation, `solve_agv_assignment.py` recovers an
executable integer AGV-pallet-workstation assignment.

### Output

`results/agv_assignment.csv`:

```text
agv_index,pallet_index,workstation_index,cost
```

The `cost` is the Manhattan distance from AGV to pallet plus pallet to
workstation.

## 5. Task 2: Dynamic Partitioning

![Task 2 dynamic partitioning](figures/task2_dynamic_partition.png)

### Meaning

Task 2 answers: **which workstation should process each pallet's quantity?**

This is different from Task 1. Task 1 matches vehicles to transport jobs; Task
2 assigns pallet quantities to workstation service ranges.

The practical meaning is that service areas are generated by the model instead
of being fixed in advance. The model considers pallet location, pallet
quantity, and workstation location, while also keeping each workstation above a
minimum workload level.

### Model

Decision variable:

```text
z(j,k): quantity from pallet j assigned to workstation k
```

Parameters:

```text
q(j): total quantity of pallet j
d(j,k): Manhattan distance from pallet j to workstation k
```

Objective:

```text
min sum d(j,k) z(j,k)
```

Main constraints:

- each pallet's quantity is fully assigned: `sum_k z(j,k) = q(j)`;
- each workstation receives at least a minimum workload:
  `sum_j z(j,k) >= alpha * total_quantity / K`;
- all quantity flows are nonnegative: `z(j,k) >= 0`.

### Textbook Algorithm

Task 2 is a standard linear program and is solved directly with the **Chapter 7
primal-dual interior-point method**. The implementation is also
`algorithms/primal_dual_lp.py`.

No integer recovery is needed because `z(j,k)` is a continuous quantity flow.
The solution directly tells how much quantity from each pallet is assigned to
each workstation.

### Output

`results/dynamic_partition.csv`:

```text
pallet_index,workstation_index,quantity
```

Summing `quantity` by workstation gives the workstation workload.

## 6. Task 3: Cache/Transfer Location Selection

![Task 3 warehouse layout selection](figures/task3_warehouse_layout.png)

### Meaning

Task 3 answers: **which locations should become important cache or transfer
positions?**

In Tasks 1 and 2, pallet positions are fixed inputs. In Task 3, candidate
positions still come from existing warehouse coordinates, but the selected
important positions are decision variables.

This is a layout-level selection problem. The experiment selects 10 positions
from 140 candidate storage locations for high-frequency temporary storage,
workstation replenishment, AGV transfer, or pre-shipping staging. The selected
locations must not be overly concentrated, otherwise they can create local
congestion.

### Model

Decision variable:

```text
x(i) in {0, 1}: whether candidate location i is selected
```

Cardinality constraint:

```text
sum_i x(i) = 10
```

Spacing constraint:

```text
x(i) + x(j) <= 1, if dist(i,j) <= 6
```

If two candidate positions are too close, they cannot both be selected. A small
value term, approximated from pallet quantity, breaks ties in favor of more
representative positions.

### Textbook Algorithm

Task 3 uses two textbook algorithms plus an engineering repair step:

- **Chapter 7 quadratic penalty method** converts equality and inequality
  constraints into a penalized objective:

```text
min f(x) + rho/2 * (||h(x)||^2 + ||max(g(x), 0)||^2)
```

- **Chapter 6 projected Barzilai-Borwein gradient method** solves each
  penalized subproblem under the box constraint `0 <= x <= 1`. The method takes
  a gradient step, projects back into the feasible box, and uses BB step sizes
  for faster iteration.
- A **discrete repair step** in `solve_warehouse_layout.py` converts the
  relaxed continuous solution into a feasible 0-1 set that satisfies the count
  and spacing constraints.

### Output

`results/warehouse_layout.csv`:

```text
pallet_index,x,y
```

Each row is one selected cache/transfer location. The default result selects 10
positions, with a minimum pairwise Manhattan distance of 7, satisfying the
`dist > 6` spacing requirement.

## 7. Experiment Setup

Dependencies:

```text
numpy
scipy
matplotlib
pandas
networkx
```

Main entry point:

```bash
python run_all.py
```

Individual task entry points:

```bash
python solve_agv_assignment.py
python solve_dynamic_partition.py
python solve_warehouse_layout.py
```

README figures can be regenerated with:

```bash
python scripts/make_readme_figures.py
```

## 8. Textbook Chapter and Algorithm Mapping

| Task | Problem type | Textbook chapter | Algorithm | Code |
| --- | --- | --- | --- | --- |
| Task 1 AGV assignment | LP relaxation plus integer recovery | Chapter 7 | primal-dual interior-point method | `algorithms/primal_dual_lp.py` |
| Task 2 dynamic partitioning | linear programming | Chapter 7 | primal-dual interior-point method | `algorithms/primal_dual_lp.py` |
| Task 3 cache/transfer location selection | spatially constrained 0-1 selection via continuous relaxation | Chapter 7 + Chapter 6 | quadratic penalty + projected BB gradient + repair | `algorithms/quadratic_penalty.py`, `algorithms/projected_bb_gradient.py` |

## 9. Results and Analysis

A typical `python run_all.py` run prints:

```text
[dynamic] status=optimal iter=21 obj=79350.200
[agv] status=optimal iter=13 lp_obj=131.000 integer_cost=131.000
[layout] status=optimal outer=2 selected=10 min_dist=7
```

Interpretation:

- **Task 1** outputs 12 executable transport assignments with total integer
  route cost 131.
- **Task 2** outputs 403 nonzero quantity flows with total distance-weighted
  cost 79350.2, while keeping each workstation above the minimum workload.
- **Task 3** outputs 10 selected cache/transfer positions with minimum pairwise
  distance 7, satisfying the spacing requirement.

Together, the three experiments show how one warehouse dataset can be turned
into different optimization models across dispatching, service-area
organization, and layout planning.

## 10. Reproduce

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_all.py
```

Presentation deliverables, exploratory notebooks, local reference PDFs,
virtual environments, and intermediate generated artifacts are intentionally
excluded from the GitHub repository. The repository keeps the code, CSV data,
figures, and generated results needed for the course project.
