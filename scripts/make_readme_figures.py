from __future__ import annotations

from pathlib import Path
import sys

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "figures"
RESULTS_DIR = ROOT / "results"
sys.path.insert(0, str(ROOT))

from warehouse_data import distance_matrix, load_data


COLORS = {
    "background": "#fbfbfd",
    "text": "#1d1d1f",
    "muted": "#6e6e73",
    "grid": "#e5e5ea",
    "edge": "#d2d2d7",
    "aisle": "#c7c7cc",
    "storage_node": "#d7ecff",
    "charger": "#ffd8a8",
    "connector": "#d1f2e2",
    "agv": "#007aff",
    "pallet": "#34c759",
    "pallet_light": "#c7f0d2",
    "workstation": "#ff3b30",
    "candidate": "#d7ecff",
    "selected": "#ff9f0a",
    "order": "#af52de",
    "route_pickup": "#007aff",
    "route_delivery": "#ff9f0a",
    "workload": "#30d158",
}

REGION_PALETTE = [
    "#007aff",
    "#34c759",
    "#ff9f0a",
    "#af52de",
    "#64d2ff",
    "#ff2d55",
    "#5856d6",
    "#ffd60a",
    "#a2845e",
    "#30d158",
    "#5e5ce6",
    "#ff375f",
    "#40c8e0",
    "#bf5af2",
    "#ffb340",
    "#32d74b",
    "#0a84ff",
    "#ac8e68",
]


def configure_style() -> None:
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
    plt.rcParams.update(
        {
            "axes.facecolor": COLORS["background"],
            "figure.facecolor": "#ffffff",
            "axes.edgecolor": COLORS["edge"],
            "axes.labelcolor": COLORS["text"],
            "axes.titlecolor": COLORS["text"],
            "xtick.color": COLORS["muted"],
            "ytick.color": COLORS["muted"],
            "axes.grid": True,
            "grid.color": COLORS["grid"],
            "grid.linewidth": 0.7,
            "grid.alpha": 0.8,
        }
    )


def setup_map_axis(ax: plt.Axes, data) -> None:
    ax.set_xlim(-1, data.ncols)
    ax.set_ylim(-1, data.nrows)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_xticks(np.arange(0, data.ncols + 1, 4))
    ax.set_yticks(np.arange(0, data.nrows + 1, 4))
    ax.spines[["top", "right"]].set_visible(False)


def scatter_nodes(ax: plt.Axes, data, *, alpha: float = 0.20) -> None:
    if not data.nodes:
        return
    nodes = np.asarray([(x, y) for _, x, y in data.nodes], dtype=float)
    types = np.asarray([node_type for node_type, _, _ in data.nodes])
    colors = {
        "1": COLORS["aisle"],
        "2": COLORS["storage_node"],
        "3": COLORS["charger"],
        "4": COLORS["connector"],
        "5": COLORS["workstation"],
    }
    labels = {
        "1": "通道节点",
        "2": "货位节点",
        "3": "充电桩",
        "4": "连接节点",
        "5": "工位",
    }
    for node_type in sorted(set(types)):
        mask = types == node_type
        ax.scatter(
            nodes[mask, 0],
            nodes[mask, 1],
            s=12,
            c=colors.get(node_type, COLORS["edge"]),
            alpha=alpha if node_type != "5" else 0.85,
            linewidths=0,
            label=labels.get(node_type, f"节点 {node_type}"),
        )


def add_metric(ax: plt.Axes, y: float, label: str, value: str, color: str) -> None:
    ax.text(
        0.08,
        y,
        value,
        transform=ax.transAxes,
        fontsize=24,
        fontweight="bold",
        color=color,
        va="center",
    )
    ax.text(
        0.08,
        y - 0.075,
        label,
        transform=ax.transAxes,
        fontsize=11,
        color=COLORS["muted"],
        va="center",
    )


def draw_background_overview() -> None:
    data = load_data(agv_sample_prob=0.6, seed=0, max_agvs=12)
    orders = pd.read_csv(ROOT / "data/orders.csv")

    fig = plt.figure(figsize=(15.5, 8.8), dpi=160)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 0.85], wspace=0.16)
    ax_map = fig.add_subplot(gs[0, 0])
    ax_info = fig.add_subplot(gs[0, 1])

    scatter_nodes(ax_map, data, alpha=0.18)
    pallets = np.asarray(data.pallets)
    workstations = np.asarray(data.workstations)
    agvs = np.asarray(data.agvs)
    ax_map.scatter(
        pallets[:, 0],
        pallets[:, 1],
        s=np.clip(data.pallet_quantities / 2, 18, 90),
        c=COLORS["pallet"],
        alpha=0.72,
        edgecolors="white",
        linewidths=0.6,
        label="托盘",
    )
    ax_map.scatter(
        workstations[:, 0],
        workstations[:, 1],
        s=150,
        c=COLORS["workstation"],
        marker="s",
        edgecolors="white",
        linewidths=1.0,
        label="工位",
    )
    ax_map.scatter(
        agvs[:, 0],
        agvs[:, 1],
        s=150,
        c=COLORS["agv"],
        marker="^",
        edgecolors="white",
        linewidths=1.0,
        label="AGV",
    )
    setup_map_axis(ax_map, data)
    ax_map.set_title("仓库网格、AGV、托盘与工位", fontsize=17, fontweight="bold", pad=12)
    ax_map.legend(loc="upper left", frameon=True, facecolor="white", framealpha=0.95)

    ax_info.axis("off")
    ax_info.set_title("实验数据总览", loc="left", fontsize=17, fontweight="bold", pad=12)
    add_metric(ax_info, 0.86, "地图节点（通道/货位/工位等）", f"{len(data.nodes)}", COLORS["text"])
    add_metric(ax_info, 0.70, "托盘候选位置", f"{len(data.pallets)}", COLORS["pallet"])
    add_metric(ax_info, 0.54, "实验采样 AGV", f"{len(data.agvs)}", COLORS["agv"])
    add_metric(ax_info, 0.38, "工位", f"{len(data.workstations)}", COLORS["workstation"])
    add_metric(ax_info, 0.22, "订单记录（业务需求背景）", f"{len(orders)}", COLORS["order"])
    ax_info.text(
        0.08,
        0.08,
        f"托盘总货量：{int(data.pallet_quantities.sum())}  |  "
        f"仓库尺寸：{data.ncols} x {data.nrows}",
        transform=ax_info.transAxes,
        fontsize=12,
        color=COLORS["muted"],
    )

    fig.suptitle("AGV 仓储优化：实体与数据", fontsize=24, fontweight="bold", y=0.985)
    fig.savefig(FIG_DIR / "background_data_overview.png", bbox_inches="tight")
    plt.close(fig)


def draw_task1_assignment() -> None:
    data = load_data(agv_sample_prob=0.6, seed=0, max_agvs=12)
    assignments = pd.read_csv(RESULTS_DIR / "agv_assignment.csv")

    fig, ax = plt.subplots(figsize=(14.5, 8.5), dpi=160)
    scatter_nodes(ax, data, alpha=0.13)
    pallets = np.asarray(data.pallets)
    workstations = np.asarray(data.workstations)
    agvs = np.asarray(data.agvs)
    ax.scatter(pallets[:, 0], pallets[:, 1], s=20, c=COLORS["pallet_light"], alpha=0.75, label="未选托盘")
    ax.scatter(workstations[:, 0], workstations[:, 1], s=130, c=COLORS["workstation"], marker="s", edgecolors="white", label="工位")
    ax.scatter(agvs[:, 0], agvs[:, 1], s=130, c=COLORS["agv"], marker="^", edgecolors="white", label="AGV")

    shown = assignments.head(10)
    for row in shown.itertuples(index=False):
        agv = agvs[int(row.agv_index)]
        pallet = pallets[int(row.pallet_index)]
        workstation = workstations[int(row.workstation_index)]
        ax.plot(
            [agv[0], pallet[0]],
            [agv[1], pallet[1]],
            color=COLORS["route_pickup"],
            linewidth=2.2,
            linestyle="--",
            alpha=0.72,
        )
        ax.plot(
            [pallet[0], workstation[0]],
            [pallet[1], workstation[1]],
            color=COLORS["route_delivery"],
            linewidth=2.2,
            alpha=0.82,
        )
        ax.scatter([pallet[0]], [pallet[1]], s=90, c=COLORS["pallet"], edgecolors="white", linewidths=0.9)

    setup_map_axis(ax, data)
    ax.set_title("任务 1：AGV -> 托盘 -> 工位 的搬运分配", fontsize=18, fontweight="bold", pad=12)
    ax.text(
        0.02,
        0.02,
        f"展示前 {len(shown)} 条路线；虚线为取货距离，实线为送达距离；全部 {len(assignments)} 条分配写入 results/agv_assignment.csv",
        transform=ax.transAxes,
        fontsize=11,
        color=COLORS["text"],
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "white", "edgecolor": COLORS["edge"], "alpha": 0.94},
    )
    ax.plot([], [], color=COLORS["route_pickup"], linestyle="--", linewidth=2.2, label="取货路径")
    ax.plot([], [], color=COLORS["route_delivery"], linewidth=2.2, label="送达路径")
    ax.legend(loc="upper left", frameon=True, facecolor="white", framealpha=0.95)
    fig.savefig(FIG_DIR / "task1_agv_assignment.png", bbox_inches="tight")
    plt.close(fig)


def draw_task2_partition() -> None:
    data = load_data(agv_sample_prob=None)
    z_df = pd.read_csv(RESULTS_DIR / "dynamic_partition.csv")
    dominant = z_df.sort_values("quantity").groupby("pallet_index").tail(1)
    loads = z_df.groupby("workstation_index", as_index=False)["quantity"].sum()
    pallets = np.asarray(data.pallets)
    workstations = np.asarray(data.workstations)

    station_for_pallet = np.full(len(pallets), -1, dtype=int)
    for row in dominant.itertuples(index=False):
        station_for_pallet[int(row.pallet_index)] = int(row.workstation_index)

    fig = plt.figure(figsize=(15.5, 8.8), dpi=160)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.28, 0.72], wspace=0.18)
    ax_map = fig.add_subplot(gs[0, 0])
    ax_bar = fig.add_subplot(gs[0, 1])
    scatter_nodes(ax_map, data, alpha=0.10)

    colors = [
        REGION_PALETTE[idx % len(REGION_PALETTE)] if idx >= 0 else COLORS["aisle"]
        for idx in station_for_pallet
    ]
    sizes = np.clip(data.pallet_quantities / 1.6, 24, 120)
    ax_map.scatter(pallets[:, 0], pallets[:, 1], s=sizes, c=colors, alpha=0.78, edgecolors="white", linewidths=0.5)
    ax_map.scatter(workstations[:, 0], workstations[:, 1], s=150, c=COLORS["workstation"], marker="s", edgecolors="white", linewidths=1.0, label="工位")
    for idx, (x, y) in enumerate(data.workstations):
        ax_map.text(x + 0.24, y + 0.24, str(idx), fontsize=8, color=COLORS["text"], weight="bold")
    setup_map_axis(ax_map, data)
    ax_map.set_title("任务 2：托盘货量按主服务工位形成动态分区", fontsize=18, fontweight="bold", pad=12)
    ax_map.legend(loc="upper left", frameon=True, facecolor="white", framealpha=0.95)

    loads = loads.sort_values("workstation_index")
    ax_bar.barh(loads["workstation_index"].astype(str), loads["quantity"], color=COLORS["workload"], alpha=0.82)
    ax_bar.set_title("各工位获得货量", fontsize=15, fontweight="bold", pad=10)
    ax_bar.set_xlabel("Quantity")
    ax_bar.set_ylabel("Workstation")
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.invert_yaxis()
    ax_bar.text(
        0.02,
        -0.10,
        "颜色表示托盘主要分配给哪个工位；柱状图用于观察负载水平。",
        transform=ax_bar.transAxes,
        fontsize=10.5,
        color=COLORS["muted"],
    )

    fig.savefig(FIG_DIR / "task2_dynamic_partition.png", bbox_inches="tight")
    plt.close(fig)


def draw_task3_layout() -> None:
    data = load_data(agv_sample_prob=None)
    selected_df = pd.read_csv(RESULTS_DIR / "warehouse_layout.csv")
    pallets = np.asarray(data.pallets)
    selected_idx = selected_df["pallet_index"].astype(int).to_numpy()
    selected = pallets[selected_idx]
    selected_dist = distance_matrix(selected, selected)
    min_pair = min(
        selected_dist[i, j]
        for i in range(len(selected_idx))
        for j in range(i + 1, len(selected_idx))
    )

    fig = plt.figure(figsize=(15.5, 8.8), dpi=160)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 0.65], wspace=0.16)
    ax_map = fig.add_subplot(gs[0, 0])
    ax_table = fig.add_subplot(gs[0, 1])
    scatter_nodes(ax_map, data, alpha=0.10)
    ax_map.scatter(pallets[:, 0], pallets[:, 1], s=34, c=COLORS["candidate"], alpha=0.78, label="候选货位")
    ax_map.scatter(
        selected[:, 0],
        selected[:, 1],
        s=180,
        c=COLORS["selected"],
        edgecolors=COLORS["text"],
        linewidths=1.2,
        marker="D",
        label="选中重点位置",
    )
    radius = 6
    for x, y in selected:
        diamond_x = [x, x + radius, x, x - radius, x]
        diamond_y = [y + radius, y, y - radius, y, y + radius]
        ax_map.plot(diamond_x, diamond_y, color=COLORS["selected"], alpha=0.24, linewidth=1.2)
    setup_map_axis(ax_map, data)
    ax_map.set_title("任务 3：从候选货位中选择分散的重点缓存/中转位置", fontsize=18, fontweight="bold", pad=12)
    ax_map.legend(loc="upper left", frameon=True, facecolor="white", framealpha=0.95)

    ax_table.axis("off")
    ax_table.set_title("选中结果", loc="left", fontsize=17, fontweight="bold", pad=12)
    ax_table.text(
        0.02,
        0.90,
        f"选中数量：{len(selected_idx)}\n最小曼哈顿距离：{int(min_pair)}\n约束要求：距离 > 6",
        transform=ax_table.transAxes,
        fontsize=14,
        color=COLORS["text"],
        linespacing=1.7,
    )
    rows = [
        [int(row.pallet_index), int(row.x), int(row.y)]
        for row in selected_df.itertuples(index=False)
    ]
    table = ax_table.table(
        cellText=rows,
        colLabels=["pallet", "x", "y"],
        cellLoc="center",
        colLoc="center",
        loc="center",
        bbox=[0.02, 0.08, 0.82, 0.66],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for cell in table.get_celld().values():
        cell.set_edgecolor(COLORS["grid"])
        cell.set_linewidth(0.6)

    fig.savefig(FIG_DIR / "task3_warehouse_layout.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    configure_style()
    draw_background_overview()
    draw_task1_assignment()
    draw_task2_partition()
    draw_task3_layout()
    print(f"wrote figures to {FIG_DIR}")


if __name__ == "__main__":
    main()
