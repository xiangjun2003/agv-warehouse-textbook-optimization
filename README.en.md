# AGV Warehouse Optimization Course Project

Language: [中文](README.md) | English

This repository contains a complete AGV warehouse optimization course project.
It uses local CSV data, automated model-building scripts, and
self-implemented textbook optimization algorithms to solve three base
warehouse optimization tasks: AGV assignment, dynamic partitioning, and
cache/transfer location selection. It also builds a realistic order-processing
scheduling experiment under one fixed initial demand batch.

The README follows the same narrative order as the presentation: background,
entities and data, base tasks and the realistic scheduling experiment,
modeling, textbook algorithm mapping, experiment setup, result analysis,
complete global modeling, and limitations.

## 1. Background, Entities, and Data

In an automated warehouse, AGVs move pallets through a grid of aisles and
nodes. Although this may look like simple point-to-point movement, AGV
dispatching and warehouse layout directly affect transport cost, order
processing speed, workstation waiting time, and local congestion.

This project can be understood as a small intelligent warehouse decision
system. Given a set of pallets, AGVs, and workstations, it answers three
base operational questions plus one integrated realistic scheduling question:

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
- **How many rounds and how much distance are needed to finish all goods?** If
  one demand batch is fixed at the initial time, each AGV can move once per
  round, and each workstation has limited processing capacity, then single
  dispatch distance is not enough. The system must also track workstation
  queues, cache inventory, and total completion rounds. This corresponds to
  the **realistic order-processing scheduling experiment**.

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

- **AGV**: an automated guided vehicle. In the figures, AGV coordinates are
  the initial vehicle positions before the dispatching batch starts, i.e. the
  `t0` state snapshot. They are not historical trajectory points or final
  positions after task completion. In Task 1, an AGV moves from this initial
  position to a pallet, picks it, and delivers it to a workstation.
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

$$
\mathrm{dist}(a,b)=|x_a-x_b|+|y_a-y_b|
$$

### Entity Legend and Visual Annotation Rules

All README figure legends now show only warehouse entities defined by this
project. Routes, color encodings, and constraint notes are described as visual
annotations instead of being mixed into the entity legend.

Entity legends use the following vocabulary:

| Entity | Color in figures | Explanation |
| --- | --- | --- |
| AGV | blue triangle | vehicle position or vehicle starting point |
| Pallet | green circle | existing pallet location; point size often represents quantity |
| Workstation | red square | picking, packing, processing, inspection, or temporary handling point |
| Candidate location | light-blue circle | candidate location in Task 3 |
| Cache/transfer point | orange diamond | final selected cache or transfer location in Task 3 |

Visual annotations are not entities:

- Task 1 uses blue dashed and orange solid lines only to explain the
  `AGV -> pallet` and `pallet -> workstation` route segments.
- Task 2 uses pallet colors to show each pallet's main serving workstation,
  which forms the dynamic workstation service area. A warehouse area is not a
  fixed physical marker, so it is not placed in the entity legend.
- Background map nodes such as aisles, storage nodes, charging nodes, and
  connection nodes show map structure only; they are not separate decision
  entities in this project.

### Dataset Details

The data are not generated on the fly. They are local warehouse CSV files under
`data/`. Each run reads these files, builds coordinates, quantities, AGV
positions, and demand context, and then constructs the optimization models.

| File | Fields | Scale | Real-world meaning | Role in the model |
| --- | --- | --- | --- | --- |
| `data/map.csv` | `Type`, `X`, `Y`, `All_Car`, `Free_Car` | 704 map nodes, warehouse size 32 x 22, including 18 workstation nodes with type `5` | warehouse grid, aisles, storage nodes, charging nodes, connection nodes, and workstations | reads warehouse nodes and workstation coordinates; supports Manhattan distance calculation for base tasks and the realistic scheduling experiment |
| `data/pallets.csv` | `{SKU:Amount} List`, `X`, `Y`, `Pallet ID` | 140 pallets, total pallet quantity 8478, single-pallet quantity range 26 to 192 | current pallet inventory and storage distribution | provides pallet coordinates, pallet quantities, and Task 3 candidate locations |
| `data/bots.csv` | `car_id`, `x`, `y`, `direction` | 50 AGV positions; the default experiment samples 12 AGVs for Task 1 | current vehicle state in the warehouse | provides AGV starting positions; direction is retained but not used by the current distance model |
| `data/orders.csv` | `Order ID`, `SKU`, `Required Amount`, `Order Received Time`, `Deadline Time` | 675 order records, 181 unique SKUs, total demand 8478 | demand context explaining why inventory needs to be moved and processed | the realistic scheduling experiment matches order demand to pallet inventory to form the initial demand batch |

The data relationships are:

- `map.csv` describes warehouse space: where AGVs can move and where
  workstations are located.
- `pallets.csv` describes inventory state: where goods are stored and how much
  quantity each pallet contains.
- `bots.csv` describes fleet state: before dispatching starts, which AGVs can
  depart from which positions. Therefore, the blue triangles in Figures 1 and
  2 have the same meaning: initial AGV positions for the current batch.
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

The base tasks and realistic scheduling experiment use the data differently:

| Task | Data used | How the data enter the model |
| --- | --- | --- |
| Task 1 AGV assignment | `bots.csv`, `pallets.csv`, `map.csv` | AGV, pallet, and workstation coordinates define the two-stage route cost: `AGV -> pallet -> workstation` |
| Task 2 dynamic partitioning | `pallets.csv`, `map.csv` | pallet quantities are supply amounts, and pallet-workstation distances are unit assignment costs |
| Task 3 cache/transfer location selection | `pallets.csv`, `map.csv` | existing pallet/storage coordinates are candidate locations, and pallet-pallet distances define spatial conflict constraints |
| Realistic order-processing scheduling experiment | `orders.csv`, `pallets.csv`, `bots.csv`, `map.csv`, plus Task 2/3 outputs | matches demand to pallets and updates AGV positions, remaining quantities, workstation queues, and cache inventory by round |

The only randomness in the default experiment is AGV sampling for Task 1. It
represents the current dispatchable vehicle set. The warehouse map, pallet
locations, pallet quantities, and order records all come from fixed CSV files,
so the experiment is directly reproducible.

## 2. Project Content

The project contains three base optimization tasks and one integrated
realistic scheduling experiment:

1. **AGV assignment**: decide which AGV serves which pallet and which
   workstation receives it.
2. **Dynamic partitioning**: decide how much quantity from each pallet is
   assigned to each workstation, forming workstation service areas.
3. **Cache/transfer location selection**: choose important cache or transfer
   positions from candidate storage locations.
4. **Realistic order-processing scheduling experiment**: under one fixed initial demand batch,
   compare Task 1 only, Task 1 + cache, Task 1 + dynamic partitioning, and Task
   1 + dynamic partitioning + cache by completion rounds and AGV distance.

The first three tasks correspond to daily dispatching, area organization, and
layout planning. The realistic scheduling experiment puts these layers into
one process and measures how each layer changes total completion time and
travel distance.

## 3. Automated Modeling and Solving Workflow

The workflow is automated. Running `python run_all.py` solves the three base
tasks. Running `python solve_multi_period.py` builds the initial order demand
and executes the realistic order-processing scheduling experiment. All outputs
are written into `results/`.

```text
CSV data
  -> warehouse_data.py reads coordinates, quantities, AGVs, and workstations
  -> solve_*.py builds objective vectors and constraint matrices
  -> algorithms/*.py solves the models with textbook algorithms
  -> solve_multi_period.py combines Task 1/2/3 outputs and updates state by round
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
run_all.py                     one-click entry point for the three base tasks
run_algorithm_benchmarks.py    algorithm benchmark for Tasks 1/2/3
results/                       generated CSV outputs
scripts/make_readme_figures.py README figure generation script
solve_multi_period.py          realistic order-processing scheduling experiment
```

Default problem sizes:

| Task | Default size |
| --- | --- |
| Task 1 | 12 AGVs, 140 pallets, 18 workstations; 4498 LP variables and 450 equality constraints |
| Task 2 | 140 pallets and 18 workstations; 2538 LP variables and 158 equality constraints |
| Task 3 | select 10 locations from 140 candidates; 140 continuous relaxation variables and 2165 spatial conflict edges |
| Realistic order-processing scheduling experiment | 140 pallets, 675 orders, 24 AGVs, 18 workstations, and 10 cache points; four ablation settings generate 149 to 197 AGV routes and 10 to 20 rounds under default parameters |

## 4. Task 1: AGV Assignment

![Task 1 AGV assignment](figures/task1_agv_assignment.png)

### Meaning

Task 1 answers: **which AGV should move which pallet, and where should it be
sent?**

A result row can be read as:

```text
AGV i moves from its current position, picks pallet j, and delivers it to workstation k.
```

Here, "current position" means the AGV initial position at dispatching time
`t0`. The blue triangles are not vehicle trajectories; they are starting
positions read from `bots.csv`. Each blue dashed line is the pickup segment
from AGV to pallet, and each orange solid line is the delivery segment from
pallet to workstation. If an AGV's initial position is exactly the same as its
assigned pallet coordinate, the pickup distance is zero, so no visible blue
dashed line appears. This means the AGV is already at the pallet location, not
that it was left unassigned.

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

- `x_ij in {0,1}`: whether AGV `i` serves pallet `j`;
- `y_jk in {0,1}`: whether pallet `j` is delivered to workstation `k`.

Objective:

$$
\min\quad
\sum_{i,j} d(\mathrm{AGV}_i,\mathrm{pallet}_j)x_{ij}
+\sum_{j,k} d(\mathrm{pallet}_j,\mathrm{workstation}_k)y_{jk}
$$

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

$$
\begin{aligned}
\min\quad & c^\top x \\
\mathrm{s.t.}\quad & Ax=b,\\
& x\ge 0.
\end{aligned}
$$

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

`z_jk >= 0`: quantity from pallet `j` assigned to workstation `k`.

Parameters:

- `q_j`: total quantity of pallet `j`;
- `d_jk`: Manhattan distance from pallet `j` to workstation `k`.

Objective:

$$
\min \sum_{j,k} d_{jk}z_{jk}
$$

Main constraints:

- each pallet's quantity is fully assigned:

$$
\sum_k z_{jk}=q_j
$$

- each workstation receives at least a minimum workload:

$$
\sum_j z_{jk}\ge \alpha\frac{\sum_j q_j}{K}
$$

- all quantity flows are nonnegative:

$$
z_{jk}\ge 0
$$

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

`x_i in {0,1}`: whether candidate location `i` is selected.

Cardinality constraint:

$$
\sum_i x_i=10
$$

Spacing constraint:

$$
x_i+x_j\le 1,\quad \mathrm{if} \mathrm{dist}(i,j)\le 6
$$

If two candidate positions are too close, they cannot both be selected. A small
value term, approximated from pallet quantity, breaks ties in favor of more
representative positions.

### Textbook Algorithm

Task 3 uses two textbook algorithms plus an engineering repair step:

- **Chapter 7 quadratic penalty method** converts equality and inequality
  constraints into a penalized objective:

$$
\min_x\quad
f(x)+\frac{\rho}{2}
\left(
\|h(x)\|_2^2+\|\max(g(x),0)\|_2^2
\right)
$$

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

## 7. Realistic Order-Processing Scheduling Experiment

![Realistic order-processing scheduling comparison](figures/cache_distance_comparison.png)

![Realistic order-processing process with Task 1 + dynamic partitioning + cache](figures/multi_period_rolling_process.png)

The first three tasks are single-snapshot models. Task 1 answers which AGV
should serve which pallet, Task 2 assigns pallet quantities to workstation
service areas, and Task 3 selects cache/transfer locations. To show how these
layers work together, `solve_multi_period.py` runs a realistic
order-processing scheduling experiment under one fixed initial demand batch.

The business scenario is that all order demand is already present at time
`t=0`. The system does not keep releasing new work. AGVs move once per round
until all quantities have been processed by workstations. Each AGV carries at
most `agv_capacity` per round, and each workstation processes at most
`station_capacity` per round.

The ablation compares four settings so the independent effects of cache and
dynamic partitioning can be separated:

| Setting | Added decision layer | Operational meaning | AGV delivery endpoint |
| --- | --- | --- | --- |
| Task 1 only | AGV dispatching | choose AGV-pallet-workstation tasks by round-by-round distance | workstation |
| Task 1 + cache | dispatching + cache points | keep nearest-workstation service, but allow AGVs to use cache points | workstation; cache is only intermediate inventory |
| Task 1 + dynamic partitioning | dispatching + workstation service areas | Task 2 first assigns each pallet to a primary workstation | assigned workstation |
| Task 1 + dynamic partitioning + cache | dispatching + service areas + cache state | AGVs may deliver directly, move goods into cache, or replenish workstations from cache | workstation; cache is only intermediate inventory |

Here, cache points are not modeled as "goods no longer need workstations" or
as "delivery to cache means completion." They represent front-of-workstation
intermediate buffers. AGVs may first move small quantities from pallets into
cache, and AGVs may later move consolidated quantities from cache to the
assigned workstation. Goods are counted as completed only after they enter a
workstation queue and are processed under the workstation processing capacity.

The cache setting has three AGV route types:

- `pallet -> workstation`: direct delivery into the workstation queue;
- `pallet -> cache`: inbound cache replenishment, not yet completed;
- `cache -> workstation`: outbound cache delivery, performed by AGVs and
  included in AGV total travel distance.

Each round chooses between direct delivery and cache staging using the current
AGV positions, remaining quantities, cache inventory, and cache capacity. Cache
is preferred only when `pallet -> cache` plus the amortized downstream
`cache -> workstation` cost is cheaper than direct delivery.

The scheduling pipeline is:

```text
read orders.csv and pallets.csv to build the t=0 initial demand
  -> Setting A: round-by-round Task 1 dispatching only
  -> Setting B: Setting A + Task 3 cache points, without dynamic partitioning
  -> Setting C: Task 2 primary workstation assignment + round-by-round Task 1 dispatching
  -> Setting D: Setting C + Task 3 cache points with cache inventory updates
  -> compare completion rounds, AGV distance, and cache usage
```

Default data and parameters:

- 675 order records from `orders.csv` are treated as the initial batch;
- SKU demand is matched to 140 real pallets in `pallets.csv`, producing total
  demand 8478;
- 24 AGVs participate, each carrying at most 120 units per round;
- 18 workstations each process at most 80 units per round;
- Task 3 selects 10 cache points, each with default capacity 600.

The process figure shows the full 11-round process for the fourth
setting:

- blue triangles: AGV starting positions in the current round;
- light-green circles: pallets with remaining demand;
- dark-green circles: pallets picked in the current round;
- red-brown squares: workstations;
- orange diamonds: selected cache points;
- blue dashed lines: `AGV -> pallet` pickup legs;
- orange solid lines: AGV `pallet -> cache` delivery legs;
- pink dash-dot lines: AGV `cache -> workstation` outbound replenishment legs.

Outputs:

```text
results/multi_period_comparison.csv  four-setting ablation metrics: rounds, AGV distance, and cache savings
results/multi_period_summary.csv     processed quantity, remaining quantity, dispatch count, workstation use, and solver status by round
results/multi_period_routes.csv      transport/processing records with endpoints, quantity, and distance
results/multi_period_workload.csv    planned quantity and planned receiver by pallet and round
results/multi_period_partition.csv   Task 2 dynamic partitioning result under initial demand
results/cache_inventory.csv          cache inventory by round
figures/cache_distance_comparison.png four-setting ablation comparison figure
figures/multi_period_rolling_process.png realistic process figure for the cache setting
```

Run:

```bash
python solve_multi_period.py
```

## 8. Experiment Setup

Dependencies:

```text
numpy
scipy
matplotlib
pandas
networkx
```

Base-task entry point:

```bash
python run_all.py
```

Base-task and realistic-experiment entry points:

```bash
python solve_agv_assignment.py
python solve_dynamic_partition.py
python solve_warehouse_layout.py
python solve_multi_period.py
```

The algorithm benchmark for Tasks 1/2/3 can be run with:

```bash
python run_algorithm_benchmarks.py
```

README figures can be regenerated with:

```bash
python scripts/make_readme_figures.py
```

`scripts/make_readme_figures.py` regenerates the three single-snapshot README
figures. `solve_multi_period.py` generates the realistic process figure.

## 9. Textbook Chapter and Algorithm Mapping

| Task | Problem type | Textbook chapter | Algorithm | Code |
| --- | --- | --- | --- | --- |
| Task 1 AGV assignment | LP relaxation plus integer recovery | Chapter 7 | primal-dual interior-point method | `algorithms/primal_dual_lp.py` |
| Task 2 dynamic partitioning | linear programming | Chapter 7 | primal-dual interior-point method | `algorithms/primal_dual_lp.py` |
| Task 3 cache/transfer location selection | spatially constrained 0-1 selection via continuous relaxation | Chapter 7 + Chapter 6 | quadratic penalty + projected BB gradient + repair | `algorithms/quadratic_penalty.py`, `algorithms/projected_bb_gradient.py` |
| Realistic order-processing scheduling experiment | decomposed round-by-round completion under initial total demand | Chapter 7 + Chapter 6 | Task 1 dispatch LP + upper-balanced partition LP + primary-workstation repair + Task 3 cache selection + cache inventory updates by round | `solve_multi_period.py` |

The algorithm benchmark also uses:

| Algorithm | Textbook link | Code | Role |
| --- | --- | --- | --- |
| Augmented Lagrangian + projected BB | Chapter 7 + Chapter 6 | `algorithms/augmented_lagrangian.py` | approximate LP solving for Task 2 and constrained layout relaxation for Task 3 |
| ADMM | Chapter 8 | `algorithms/admm_lp.py` | splitting method for Task 1/2 LPs |
| Projected gradient | Chapter 6 | `algorithms/projected_gradient.py` | Task 3 penalty subproblems |
| Nesterov accelerated projected gradient | Chapter 8 | `algorithms/projected_gradient.py` | Task 3 penalty subproblems |
| HiGHS dual simplex | classical LP baseline | SciPy `linprog(method="highs-ds")` | library baseline for Task 1/2; simplex is not developed in detail in the textbook |

## 10. Results and Analysis

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

### Algorithm Benchmark For Tasks 1/2/3

Running `python run_algorithm_benchmarks.py` writes:

```text
results/algorithm_benchmark.csv
```

The benchmark compares algorithms on the same models. `objective` is evaluated
on the original continuous variables, while `recovered_objective` is the
executable route cost or repaired layout score. For Task 2, the recovered value
first repairs tiny negative flows to zero before computing interpretable
transport cost, so approximate infeasibility is not mixed with the reported
schedule cost. Smaller `equality_residual` means better constraint
satisfaction. ADMM and augmented Lagrangian are run under fixed iteration
budgets; a `max_iter` status therefore means an approximate solution, not a
certified optimum. Runtime varies slightly with machine load; the table reports
one measured run.

Task 1: AGV assignment.

| Algorithm | Status | LP objective | Recovered route cost | Iterations | Time | Equality residual | Interpretation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Primal-dual interior point | optimal | 131.000 | 131.000 | 13 | 0.281s | 4.81e-08 | self-implemented main solver; accurate and stable after integer recovery |
| HiGHS dual simplex | optimal | 131.000 | 131.000 | 568 | 0.024s | 0 | fast library LP baseline |
| ADMM | max_iter | 130.597 | 131.000 | 1200 | 3.253s | 2.31e-03 | still has feasibility residual, so its continuous objective is below the true optimum; recovery still gives route cost 131 |

Task 2: dynamic partitioning.

| Algorithm | Status | Objective | Nonzero flows | Iterations | Time | Equality residual | Interpretation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Primal-dual interior point | optimal | 79350.2 | 403 | 21 | 0.044s | 6.05e-08 | accurate high-precision LP solve |
| HiGHS dual simplex | optimal | 79350.2 | 151 | 309 | 0.007s | 7.82e-17 | reaches the same optimum and returns a sparser vertex solution |
| ADMM | max_iter | 83050.8 | 485 | 1500 | 0.427s | 5.95e-05 | nearly feasible but still above the optimum |
| Augmented Lagrangian + BB | max_iter | 81974.6 | 484 | 6000 | 1.180s | 7.26e-07 | better feasibility and objective than ADMM, but still not as accurate as IPM/simplex |

Task 3: cache/transfer location selection.

| Algorithm | Status | Relaxed objective | Layout score | Iterations | Time | Selected | Min distance | Interpretation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Quadratic penalty + projected BB | optimal | -0.003164 | 5.198 | 2400 | 0.136s | 10 | 7 | default solver; fast and produces a feasible repaired layout |
| Quadratic penalty + projected gradient | optimal | -0.003166 | 5.198 | 2400 | 0.259s | 10 | 7 | same repaired layout quality, but slower than BB |
| Quadratic penalty + Nesterov | optimal | -0.003171 | 5.198 | 2400 | 0.327s | 10 | 7 | acceleration does not help much here because projection and penalties dominate |
| Augmented Lagrangian + projected BB | optimal | -0.004074 | 3.667 | 2000 | 0.092s | 10 | 7 | satisfies continuous constraints well, but repair gives a lower-scoring discrete layout |

Overall, Tasks 1/2 show that interior-point and simplex methods are the most
suitable high-accuracy LP solvers. ADMM and augmented Lagrangian are useful
lightweight approximations, but need more iterations to approach the optimum.
For Task 3, quadratic penalty with projected BB gives the best balance between
speed and repaired discrete solution quality, so it remains the default.

A typical `python solve_multi_period.py` run prints:

```text
Realistic order-processing scheduling experiment
scenarios=4 route_records=1151 time~1.4s
[task1_only] rounds=19 agv_routes=149 agv_distance=2899.000 processed=8478.000 cached=0.000
[task1_cache] rounds=20 agv_routes=197 agv_distance=2226.000 processed=8478.000 cached=5086.000
[task1_partition] rounds=10 agv_routes=149 agv_distance=3322.000 processed=8478.000 cached=0.000
[task1_partition_cache] rounds=11 agv_routes=177 agv_distance=3060.000 processed=8478.000 cached=2806.000
cache-only agv-distance saving vs task1=673.000 (23.21%)
cache agv-distance saving vs partition=262.000 (7.89%)
```

The realistic scheduling result shows that all demand is fixed at the initial time. With the
default parameters, each workstation can process only 80 units per round. Task
1 alone sends goods to nearby workstations and keeps AGV distance at 2899, but
its workload is concentrated: the heaviest workstation processes 1448 units,
so completion increases to 19 rounds. Adding cache alone reduces AGV distance
to 2226, saving 673 versus Task 1 alone (23.21%), but inbound and outbound
cache trips consume AGV rounds and the workstation load remains concentrated,
so completion is 20 rounds. Adding dynamic partitioning imposes an upper
workload balance on workstations: the heaviest workstation load drops to about
541 units, so completion decreases to 10 rounds. Adding both dynamic
partitioning and cache creates 28 additional `cache -> workstation` AGV
outbound routes and finishes in 11 rounds; AGV distance drops to 3060, saving
262 versus the partition setting (7.89%).

This result shows that cache points do not automatically reduce both distance
and time. Their value is to replace some long small-batch direct deliveries
with short inbound cache replenishment and batched outbound replenishment. The
tradeoff is that outbound cache delivery also consumes AGV capacity and rounds.
Dynamic partitioning mainly improves workstation load rhythm and completion
time. In short, cache is more distance-oriented, while partitioning is more
throughput-oriented.

Together, the task experiments and the realistic scheduling ablation show how
one warehouse dataset can be turned into different optimization models across
dispatching, service-area organization, and layout planning.

## 11. Current Round-by-Round Heuristic and Complete Global Model

### What the Current Implementation Solves

`solve_multi_period.py` uses a **decomposed round-by-round heuristic**, not a
single-shot global optimum for the full cross-round problem. The procedure is:

1. Read `orders.csv` and `pallets.csv` at the initial time and construct total
   demand of `8478` units.
2. If dynamic partitioning is enabled, solve Task 2 once at `t=0` and repair
   the relaxed flow into one primary workstation per pallet.
3. If cache is enabled, fix the 10 cache points selected by Task 3.
4. At each round, use remaining quantities, AGV positions, cache inventory,
   and workstation queues to greedily generate at most 24 candidate transport
   tasks.
5. For those selected tasks, solve a Task-1-style AGV-task LP relaxation that
   minimizes current-round pickup and delivery distance.
6. Update AGV positions, pallet remaining quantities, cache inventory, and
   workstation queues. Workstations process queues at `80 units/round`.
7. Repeat until pallet remaining quantity, cache inventory, and workstation
   queue are all zero.

Step 4 is greedy: candidates are sorted by route type, estimated cost, and load
fullness. Step 5 optimizes only the current round assignment and does not look
ahead. The algorithm therefore produces executable schedules quickly, but it
does not guarantee global optimality.

### Complete Global Optimization Model

A rigorous single-shot formulation can be written as a mixed-integer program
that jointly models dynamic partitioning, cache use, and multi-round AGV
scheduling.

Sets and parameters:

- `P`: pallets, `|P| = 140`;
- `S`: workstations, `|S| = 18`;
- `C0`: candidate cache positions, up to 140 pallet/storage coordinates;
- `m = 10`: number of selected cache points;
- `A`: AGVs, `|A| = 24`;
- `T`: planning rounds, for example `T = 20` covers all current ablation settings;
- `q_p`: demand quantity on pallet `p`;
- `Q = 120`: AGV capacity per route;
- `H = 80`: workstation processing capacity per round;
- `B = 600`: cache capacity;
- `d(i,j)`: Manhattan distance between nodes `i` and `j`.

Main decision variables:

- `u_ps in {0,1}`: pallet `p` is served by workstation `s`;
- `v_c in {0,1}`: candidate cache point `c` is selected;
- `x^D_apst in {0,1}`: AGV `a` transports pallet `p` directly to workstation `s` at round `t`;
- `x^I_apct in {0,1}`: AGV `a` transports pallet `p` to cache `c` at round `t`;
- `x^O_acst in {0,1}`: AGV `a` transports from cache `c` to workstation `s` at round `t`;
- `g^D_apst, g^I_apct, g^O_acst >= 0`: transported quantities;
- `R_pt >= 0`: remaining quantity on pallet `p` after round `t`;
- `I_ct >= 0`: inventory at cache `c` after round `t`;
- `L_st >= 0`: workstation queue after round `t`;
- `h_st >= 0`: quantity processed by workstation `s` at round `t`;
- `F_t in {0,1}`: all demand has finished by the end of round `t`.

A lexicographic objective can first minimize completion time, then minimize AGV
distance:

$$
\min\quad
M\sum_{t\in T}(1-F_t)+D_{\mathrm{AGV}}
$$

Here `M` is a large weight. `AGV_Total_Distance` includes empty travel from the
previous round endpoint to the next pickup point and loaded travel from pickup
to dropoff. Exact AGV position continuity requires additional transition
variables between routes in consecutive rounds.

Core constraints:

Each pallet has one primary workstation:

$$
\sum_{s\in S}u_{ps}=1,\quad \forall p\in P
$$

Workstation load balancing:

$$
\sum_{p\in P}q_pu_{ps}
\le
\alpha\frac{\sum_{p\in P}q_p}{|S|},
\quad \forall s\in S
$$

Cache count and spacing:

$$
\sum_{c\in C_0}v_c=m
$$

$$
v_c+v_{c'}\le 1,
\quad \mathrm{if} \mathrm{dist}(c,c')\le 6
$$

Each AGV executes at most one route per round:

$$
\sum_{p,s}x^D_{apst}
+\sum_{p,c}x^I_{apct}
+\sum_{c,s}x^O_{acst}
\le 1,
\quad \forall a,t
$$

AGV capacity:

$$
\begin{aligned}
g^D_{apst}&\le Qx^D_{apst},\\
g^I_{apct}&\le Qx^I_{apct},\\
g^O_{acst}&\le Qx^O_{acst}.
\end{aligned}
$$

Pallet remaining quantity:

$$
R_{p,t}
=R_{p,t-1}
-\sum_{a,s}g^D_{apst}
-\sum_{a,c}g^I_{apct}
$$

Cache inventory:

$$
I_{c,t}
=I_{c,t-1}
+\sum_{a,p}g^I_{apct}
-\sum_{a,s}g^O_{acst}
$$

$$
0\le I_{c,t}\le Bv_c
$$

Workstation queue:

$$
L_{s,t}
=L_{s,t-1}
+\sum_{a,p}g^D_{apst}
+\sum_{a,c}g^O_{acst}
-h_{st}
$$

$$
0\le h_{st}\le H
$$

Completion:

$$
F_t=1\Rightarrow
\sum_p R_{p,t}+\sum_c I_{c,t}+\sum_s L_{s,t}=0
$$

Additional feasibility constraints are required so that a pallet can only be
served by its assigned workstation, and cache routes can only use selected
cache points that serve the relevant workstation.

### Model Scale

If Task 2 partitioning and Task 3 cache points are fixed, and the model only
schedules precomputed transport batches, the current data have:

- pallets: 140;
- AGVs: 24;
- planning rounds: 20;
- actual AGV transport batches: 149 to 197;
- simple assignment binaries:

$$
24\times197\times20\approx94{,}560
$$

However, exact AGV position continuity needs route transition variables:

$$
24\times19\times197^2
\approx17{,}700{,}000
$$

binary transition variables.

If partitioning and direct/cache route choices are solved jointly while the 10
cache points selected by Task 3 are fixed, the action set already includes:

- pallet to workstation: `140 x 18 = 2520`;
- pallet to cache: `140 x 10 = 1400`;
- cache to workstation: `10 x 18 = 180`;
- total: about `4100` route actions.

The `AGV-action-round` binaries alone are then:

$$
24\times4{,}100\times20
\approx1{,}968{,}000
$$

binary variables.

If cache location selection is also placed in the same model, the cache set is
not 10 selected points but up to 140 candidate storage locations. Then:

- pallet to candidate cache: `140 x 140 = 19600`;
- cache to workstation: `140 x 18 = 2520`;
- route actions alone exceed `24000`;
- `AGV-action-round` binaries:

$$
24\times24{,}640\times20
\approx11{,}827{,}200
$$

Strict route-transition modeling would push the scale far beyond this. For the
course project, the decomposed round-by-round heuristic is therefore a practical
choice: it gives up global optimality guarantees in exchange for fast runtime,
clear interpretation, and implementation with textbook-style algorithms.

## 12. Limitations

The current experiment has several limitations:

- **No global optimality guarantee**: the realistic scheduling experiment uses a round-by-round heuristic and
  may not achieve the minimum possible rounds or distance.
- **Time and distance are simplified**: one AGV can execute at most one route
  per round. Distance affects total travel distance, but a longer route does
  not consume multiple rounds.
- **No traffic conflict modeling**: Manhattan distance approximates grid
  travel. Aisle conflicts, congestion, passing, queueing, and traffic rules
  are not explicitly simulated.
- **No battery or charging constraints**: AGV battery, charger occupancy,
  maintenance, and breakdowns are not modeled.
- **Orders are aggregated**: SKU demand is matched to pallet inventory and
  treated as one initial demand batch. Order deadlines, priorities, and
  SKU-level picking compatibility are not modeled.
- **Cache modeling is simplified**: cache points are selected from existing
  pallet/storage positions with fixed capacity 600. Construction cost,
  operator effort, service radius, and cache congestion are not modeled.
- **Dynamic partitioning is solved only at `t=0`**: workstation service areas
  are not recalculated as queues and inventories change.
- **Limited sensitivity analysis**: AGV count, AGV capacity, workstation
  capacity, cache capacity, and cache count can all change the conclusion.

## 13. Reproduce

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_all.py
python solve_multi_period.py
```

Presentation deliverables, exploratory notebooks, local reference PDFs,
virtual environments, and intermediate generated artifacts are intentionally
excluded from the GitHub repository. The repository keeps the code, CSV data,
figures, and generated results needed for the course project.
