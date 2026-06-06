from __future__ import annotations

import ast
import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"


@dataclass(frozen=True)
class WarehouseData:
    nodes: list[tuple[str, int, int]]
    ncols: int
    nrows: int
    workstations: list[tuple[int, int]]
    pallets: list[tuple[int, int]]
    pallet_quantities: np.ndarray
    agvs: list[tuple[int, int]]


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def distance_matrix(
    left: Iterable[tuple[int, int]],
    right: Iterable[tuple[int, int]],
) -> np.ndarray:
    left_arr = np.asarray(list(left), dtype=float)
    right_arr = np.asarray(list(right), dtype=float)
    return np.abs(left_arr[:, None, :] - right_arr[None, :, :]).sum(axis=2)


def read_map(path: Path = DATA_DIR / "map.csv"):
    nodes: list[tuple[str, int, int]] = []
    workstations: list[tuple[int, int]] = []
    ncols = 0
    nrows = 0
    with path.open(newline="", encoding="gbk") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if not row:
                continue
            if row[0].startswith("*"):
                ncols = int(row[1])
                nrows = int(row[2])
                continue
            if row[0].startswith("#"):
                continue
            node_type = row[0]
            x = int(row[1])
            y = int(row[2])
            nodes.append((node_type, x, y))
            if node_type == "5":
                workstations.append((x, y))
    return nodes, ncols, nrows, workstations


def _parse_sku_quantity(raw: str) -> int:
    # The CSV stores values such as "104151:9,840211:35".
    parsed = ast.literal_eval("{" + raw + "}")
    return int(sum(parsed.values()))


def read_pallets(path: Path = DATA_DIR / "pallets.csv"):
    pallets: list[tuple[int, int]] = []
    quantities: list[int] = []
    with path.open(newline="", encoding="gbk") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            pallets.append((int(row[1]), int(row[2])))
            quantities.append(_parse_sku_quantity(row[0]))
    return pallets, np.asarray(quantities, dtype=float)


def read_agvs(
    path: Path = DATA_DIR / "bots.csv",
    *,
    ncols: int,
    nrows: int,
    sample_prob: float | None = 0.6,
    seed: int | None = 0,
    max_count: int | None = None,
):
    rng = random.Random(seed)
    agvs: list[tuple[int, int]] = []
    with path.open(newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if len(row) < 5 or row[0].startswith("#"):
                continue
            if sample_prob is not None and rng.random() >= sample_prob:
                continue
            x = int(row[2])
            y = int(row[3])
            if 0 <= x < ncols and 0 <= y < nrows:
                agvs.append((x, y))
                if max_count is not None and len(agvs) >= max_count:
                    break
    return agvs


def load_data(
    *,
    agv_sample_prob: float | None = 0.6,
    seed: int | None = 0,
    max_agvs: int | None = None,
):
    nodes, ncols, nrows, workstations = read_map()
    pallets, quantities = read_pallets()
    agvs = read_agvs(
        ncols=ncols,
        nrows=nrows,
        sample_prob=agv_sample_prob,
        seed=seed,
        max_count=max_agvs,
    )
    return WarehouseData(
        nodes=nodes,
        ncols=ncols,
        nrows=nrows,
        workstations=workstations,
        pallets=pallets,
        pallet_quantities=quantities,
        agvs=agvs,
    )
