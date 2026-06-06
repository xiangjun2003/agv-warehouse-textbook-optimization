from __future__ import annotations

import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "outputs/manual-20260601-agv-textbook/presentations/agv-textbook-deck/assets/deck-data.json"
OUTPUT = ROOT / "deliverables/agv-warehouse-textbook-optimization-animated.html"
ALIAS_OUTPUT = ROOT / "deliverables/agv-warehouse-textbook-optimization-native.html"


C = {
    "blue": "#2276FF",
    "green": "#35A66A",
    "amber": "#E6A72A",
    "coral": "#F25E4B",
    "violet": "#6C5CE7",
    "ink": "#101418",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def mathify(value: object) -> str:
    """Escape text, then improve common inline optimization notation."""
    out = esc(value)
    out = re.sub(
        r"\b([A-Za-zΦ])_([A-Za-z0-9,ρ]+)",
        r'<span class="math">\1<sub>\2</sub></span>',
        out,
    )
    out = re.sub(
        r"\b(score)_([A-Za-z0-9]+)",
        r'<span class="math">\1<sub>\2</sub></span>',
        out,
    )
    out = re.sub(
        r"Σ_([A-Za-z0-9]+)",
        r'<span class="math">Σ<sub>\1</sub></span>',
        out,
    )
    out = out.replace("10^-7", '10<sup>-7</sup>')
    out = out.replace("ρ/2", '<span class="math">ρ</span>/2')
    return out


def kicker(label: str) -> str:
    return f'<div class="kicker reveal">{esc(label)}</div>'


def title_block(title: str, subtitle: str | None = None, *, wide: bool = False) -> str:
    cls = "title wide" if wide else "title"
    sub = f'<p class="subtitle reveal">{mathify(subtitle)}</p>' if subtitle else ""
    return f'<h1 class="{cls} reveal">{esc(title)}</h1>{sub}'


def footer(page: int) -> str:
    return (
        '<footer class="folio">'
        '<span>AGV 仓储优化课程项目 · 本地 CSV 数据 · Python 自实现算法</span>'
        f"<span>{page:02d}</span>"
        "</footer>"
    )


def metric(value: str, label: str, note: str, color: str = C["blue"]) -> str:
    return (
        '<div class="metric reveal">'
        f'<div class="metric-value" style="color:{color}">{esc(value)}</div>'
        f'<div class="metric-label">{esc(label)}</div>'
        f'<div class="metric-note">{esc(note)}</div>'
        "</div>"
    )


def note(head: str, body: str, color: str = C["blue"], *, cls: str = "") -> str:
    return (
        f'<div class="note-card reveal {cls}" style="--accent:{color}">'
        f"<h3>{esc(head)}</h3>"
        f"<p>{mathify(body)}</p>"
        "</div>"
    )


def formula(head: str, lines: list[str], color: str = C["blue"]) -> str:
    body = "".join(f"<p>{mathify(line)}</p>" for line in lines)
    return (
        f'<div class="formula reveal" style="--accent:{color}">'
        f"<h3>{esc(head)}</h3>"
        f"{body}"
        "</div>"
    )


def flow(steps: list[tuple[str, str, str]]) -> str:
    parts = []
    for head, body, color in steps:
        parts.append(
            f'<div class="flow-step reveal" style="--accent:{color}">'
            f"<h3>{esc(head)}</h3><p>{mathify(body)}</p>"
            "</div>"
        )
    return '<div class="flow">' + "".join(parts) + "</div>"


def map_box(mode: str, *, cls: str = "", legend: str = "") -> str:
    return f'<div class="warehouse-map reveal {cls}" data-map="{esc(mode)}">{legend}</div>'


def chart_box(kind: str, *, cls: str = "") -> str:
    return f'<div class="chart reveal {cls}" data-chart="{esc(kind)}"></div>'


def slide(page: int, body: str, *, dark: bool = False, extra_cls: str = "") -> str:
    classes = "slide dark" if dark else "slide"
    if extra_cls:
        classes += f" {extra_cls}"
    return f'<section class="{classes}" data-page="{page}"><div class="slide-inner">{body}{footer(page)}</div></section>'


def build_slides(data: dict) -> str:
    r = data["results"]
    input_data = data["input"]
    total_qty = round(input_data["pallets"]["quantity_stats"]["total"])
    total_nodes = sum(item["count"] for item in input_data["map"]["counts"])
    total_time = f"{r['total_time']:.2f}s"
    dyn_obj = f"{r['dynamic']['objective']:.0f}"
    agv_cost = f"{r['agv']['integer_cost']:.0f}"

    sections: list[str] = []

    sections.append(slide(1, f"""
      {kicker("COURSE PROJECT")}
      {title_block("自动化仓库 AGV 优化", "从现场实体到数学模型：任务分配、动态分区与重点缓存货位选择")}
      <div class="rule reveal"></div>
      <div class="metric-row compact">
        {metric("3", "实验任务", "调度 · 分区 · 布局", C["blue"])}
        {metric(str(input_data["pallets"]["count"]), "托盘记录", f"总货量 {total_qty}", C["green"])}
        {metric(total_time, "端到端求解", "一次完整运行", C["amber"])}
      </div>
      <div class="cover-map">{map_box("dark routes agvs candidates workstations")}</div>
      <div class="cover-note">{note("核心主张", "把仓库中的搬运、负载与布局问题转化成可复现实验，并用教材中的优化算法完成自动化求解。", C["blue"])}</div>
    """, dark=True))

    sections.append(slide(2, f"""
      {kicker("BACKGROUND")}
      {title_block("实验背景：自动化仓库要让货物流得更顺。", "仓库每天面对大量托盘搬运任务。AGV 能自动搬运，但如果任务、区域和布局安排不好，系统仍然会出现绕路、等待和局部拥堵。", wide=True)}
      {flow([
        ("入库区", "货物进入仓库，形成待存储或待处理托盘", C["blue"]),
        ("存储区", "托盘分布在仓库货位中，等待搬运", C["green"]),
        ("作业工位", "拣选、包装、加工、检验等操作发生的位置", C["amber"]),
        ("出库区", "处理完成的托盘被送往发运或暂存位置", C["coral"]),
      ])}
      <div class="wide-callout reveal">为什么需要优化：AGV 数量有限，托盘位置分散，工位负载会变化。模型要回答谁去搬、货量归谁处理、哪些位置适合作为重点缓存点。</div>
    """))

    sections.append(slide(3, f"""
      {kicker("WAREHOUSE ENTITIES")}
      {title_block("先把仓库现场的三个基础实体讲清楚。", "任务 1 和任务 2 都围绕 AGV、托盘、工位展开；理解它们之后，后面的模型变量才有现实含义。")}
      <div class="entity-grid">
        <div class="entity reveal" style="--accent:{C['blue']}"><div class="icon agv"></div><h3>AGV</h3><p>自动导引运输车，是仓库里的无人搬运资源。它负责从一个位置取托盘，再把托盘送到指定工位或区域。</p></div>
        <div class="entity reveal" style="--accent:{C['amber']}"><div class="icon pallet"></div><h3>托盘</h3><p>承载货物的标准化单元。一托盘可以代表一批原材料、零件、订单商品或待出库成品。</p></div>
        <div class="entity reveal" style="--accent:{C['green']}"><div class="icon station"></div><h3>工位</h3><p>仓库或生产线中的作业位置，可以是拣选、包装、加工、检验、出库或临时处理点。</p></div>
      </div>
    """))

    sections.append(slide(4, f"""
      {kicker("PROJECT GOAL")}
      {title_block("项目内容：把三个仓库决策变成三个优化问题。", "这不是单纯跑算法，而是把业务对象、距离、负载和空间约束逐步翻译成数学规划。", wide=True)}
      <div class="goal-grid">
        {note("谁去搬？", "AGV 任务分配：决定 AGV、托盘、工位之间的匹配关系。", C["blue"], cls="large")}
        {note("货量怎么分？", "动态分区：决定每个托盘货量主要由哪个工位处理。", C["green"], cls="large")}
        {note("重点货位怎么选？", "布局选址：从候选货位中选择重点缓存/中转货位。", C["coral"], cls="large")}
      </div>
      <div class="wide-callout reveal">实验目的：统一读取仓库数据，分别构造三个模型，再由自实现算法求解并输出可解释结果。</div>
    """))

    sections.append(slide(5, f"""
      {kicker("DATA")}
      {title_block("实验数据包含地图、托盘、AGV 与工位。", "坐标数据让我们可以计算曼哈顿距离；托盘货量让动态分区不只是按点位分配，而是按货物流量分配。")}
      <div class="split map-heavy">
        {map_box("type candidates agvs workstations", cls="large-map")}
        <div class="side-stack">
          <div class="metric-grid two">
            {metric(f"{input_data['map']['ncols']}×{input_data['map']['nrows']}", "仓库网格", f"{total_nodes} 个有效节点", C["blue"])}
            {metric(str(input_data["workstations"]["count"]), "工位数量", "地图中 type=5", C["green"])}
            {metric(str(input_data["agvs_sampled"]), "参与 AGV", f"来自 {input_data['agvs_total']} 条记录抽样", C["coral"])}
            {metric(str(input_data["pallets"]["count"]), "托盘数量", "含坐标与货量", C["amber"])}
          </div>
          {chart_box("quantityBins")}
        </div>
      </div>
    """))

    sections.append(slide(6, f"""
      {kicker("THREE QUESTIONS")}
      {title_block("三个问题对应仓库的三个决策层级。", None, wide=True)}
      <div class="lane-list reveal">
        <div class="lane"><span>任务 1</span><strong>运行调度</strong><p>今天哪辆 AGV 去搬哪个托盘</p><em>AGV、托盘、工位位置固定，决策是匹配关系</em></div>
        <div class="lane green"><span>任务 2</span><strong>区域划分</strong><p>托盘货量由哪个工位处理</p><em>托盘和工位固定，决策是货量流向与服务区域</em></div>
        <div class="lane coral"><span>任务 3</span><strong>布局选址</strong><p>哪些候选货位升级为重点缓存点</p><em>候选位置固定，决策是选中哪些位置</em></div>
      </div>
    """, dark=True))

    sections.append(slide(7, f"""
      {kicker("TASK 1 · MEANING")}
      {title_block("任务 1：AGV 任务分配解决“谁去搬”。", "已知 AGV、托盘、工位的位置后，系统要快速决定每辆 AGV 服务哪个托盘，并送往哪个工位。")}
      <div class="split">
        {map_box("routes agvs candidates workstations", cls="large-map")}
        <div class="side-stack">
          {note("现实解释", "一条分配结果可以读成：AGV i 从当前位置出发，到托盘 j 取货，再把它送到工位 k。", C["blue"])}
          {note("优化目标", "让所有被派出的 AGV 的总行驶距离尽量短，同时满足每辆 AGV 只接一个任务、工位容量有限等约束。", C["green"])}
          {note("为什么重要", "分配不好会产生空驶和绕路；分配合理能直接降低搬运时间，并提高工位供货稳定性。", C["amber"])}
        </div>
      </div>
    """))

    sections.append(slide(8, f"""
      {kicker("TASK 1 · MODEL")}
      {title_block("任务 1 的模型：把一次搬运拆成取货距离和送货距离。", "模型中同时包含 AGV 到托盘、托盘到工位两段距离。连续松弛用于求解，随后恢复为实际整数分配。")}
      <div class="formula-grid">
        {formula("决策变量", ["x_ij：AGV i 是否服务托盘 j", "y_jk：托盘 j 是否送到工位 k", "距离成本：d(i,j) + d(j,k)"], C["blue"])}
        {formula("目标与约束", ["min Σ d(AP) x_ij + Σ d(PW) y_jk", "d(AP)：AGV 到托盘距离；d(PW)：托盘到工位距离", "每辆 AGV 至多分配 1 个托盘；工位容量有限"], C["green"])}
      </div>
      <div class="wide-callout reveal">建模含义：变量不是抽象符号，而是在回答哪辆车取哪个托盘、这个托盘最终送到哪个工位。</div>
    """))

    sections.append(slide(9, f"""
      {kicker("TASK 1 · ALGORITHM")}
      {title_block("任务 1 使用线性规划原始-对偶内点法，再做整数恢复。", "教材中的内点法负责求连续松弛；恢复步骤把连续权重转成可执行的 AGV-托盘-工位三元组。", wide=True)}
      {flow([
        ("构造 LP", "距离矩阵、等式约束、非负变量", C["blue"]),
        ("内点迭代", "同时降低原始残差、对偶残差和互补间隙", C["green"]),
        ("整数恢复", "按松弛解权重和距离排序，生成实际分配", C["amber"]),
        ("可执行结果", "输出每辆 AGV 的托盘与工位", C["coral"]),
      ])}
      <div class="wide-callout reveal">内点法停止条件：max(原始可行性残差，对偶可行性残差，互补间隙) ≤ 10<sup>-7</sup>。</div>
    """))

    sections.append(slide(10, f"""
      {kicker("TASK 1 · RESULT")}
      {title_block("任务 1 的结果是一组可执行搬运安排。", "实验输出每辆 AGV 选中的托盘、目标工位和对应距离，既能看总目标值，也能追踪单条路线。")}
      <div class="split map-heavy">
        {map_box("routes agvs candidates workstations", cls="large-map")}
        <div class="side-stack">
          <div class="metric-grid two">
            {metric(agv_cost, "整数分配总距离", "AGV 取货 + 送货", C["blue"])}
            {metric(str(r["agv"]["iterations"]), "内点迭代次数", f"耗时 {r['agv']['time']:.3f}s", C["green"])}
          </div>
          <div class="table-card reveal" data-table="agvAssignments"></div>
        </div>
      </div>
    """))

    sections.append(slide(11, f"""
      {kicker("TASK 2 · MEANING")}
      {title_block("任务 2：动态分区解决“货量归谁处理”。", "这里不直接分配 AGV，而是把托盘上的货量分给不同工位，从而形成随数据变化的服务区域。")}
      <div class="split">
        {map_box("dynamic workstations", cls="large-map")}
        <div class="side-stack">
          {note("区别于任务 1", "任务 1 是车辆与任务匹配；任务 2 是货量与工位匹配。它更像仓库内部的作业区域划分。", C["green"])}
          {note("为什么叫动态", "区域不是固定房间，而是由模型根据托盘位置、货量和工位位置实时形成。数据变了，区域也会变。", C["blue"])}
          {note("优化目标", "距离不能太长，同时工位不能过度不均衡，至少要获得一定服务货量。", C["amber"])}
        </div>
      </div>
    """))

    sections.append(slide(12, f"""
      {kicker("TASK 2 · AREA")}
      {title_block("仓库区域不是预先画好的房间，而是工位的服务范围。", "如果某批托盘货量主要分给 W1，那么它们就构成 W1 的服务区域；多个工位的服务范围合起来就是动态分区。", wide=True)}
      <div class="split map-heavy">
        {map_box("dynamic workstations", cls="large-map")}
        <div class="side-stack">
          {chart_box("stationLegend")}
          {note("讲给听众的版本", "动态分区就是让每个工位负责一片“由托盘和货量组成的服务范围”。它不是地图上的墙，而是模型算出来的业务归属。", C["green"])}
        </div>
      </div>
    """))

    sections.append(slide(13, f"""
      {kicker("TASK 2 · MODEL")}
      {title_block("任务 2 的模型：把托盘货量作为流量分给工位。", "变量不再是 0-1 分配，而是“托盘 j 有多少货量分给工位 k”。这样能表达货量分配和负载约束。")}
      <div class="formula-grid">
        {formula("决策变量", ["z_jk：托盘 j 分给工位 k 的货量", "q_j：托盘 j 的总货量", "d_jk：托盘 j 到工位 k 的通道距离", "目标：min Σ d_jk z_jk"], C["green"])}
        {formula("约束含义", ["每个托盘的货量必须全部分完：Σ_k z_jk = q_j", "每个工位至少获得一定货量", "所有 z_jk 非负，避免无意义的负流量"], C["blue"])}
      </div>
      <div class="wide-callout reveal">实际意义：这个模型在距离成本和工位负载之间做权衡，不能只贪图最近距离，也不能让工位任务严重失衡。</div>
    """))

    sections.append(slide(14, f"""
      {kicker("TASK 2 · ALGORITHM")}
      {title_block("任务 2 仍然是线性规划，直接使用原始-对偶内点法。", "动态分区模型规模更像标准 LP：目标线性，约束线性，非负变量。内点法适合一次性处理大量 z_jk。", wide=True)}
      <div class="quad-grid">
        {note("原始问题", "A z = b, z ≥ 0，代表货量守恒和工位最低负载。", C["green"])}
        {note("对偶问题", "通过拉格朗日乘子刻画约束价格。", C["blue"])}
        {note("牛顿方向", "解正规方程，更新原始变量、对偶变量和松弛变量。", C["violet"])}
        {note("路径跟踪", "用中心化参数控制互补间隙逐步下降。", C["amber"])}
      </div>
      <div class="wide-callout reveal">输出：z 矩阵直接解释为“每个托盘货量流向每个工位的数量”。</div>
    """))

    sections.append(slide(15, f"""
      {kicker("TASK 2 · RESULT")}
      {title_block("任务 2 的结果显示每个工位获得了多少服务货量。", "同色托盘点表示它们主要归同一个工位服务；右侧柱状图展示工位负载。")}
      <div class="split map-heavy">
        {map_box("dynamic workstations", cls="large-map")}
        <div class="side-stack result-stack">
          {chart_box("loadBars")}
          <div class="metric-grid two">
            {metric(dyn_obj, "加权距离目标", "货量 × 距离", C["green"])}
            {metric(str(r["dynamic"]["iterations"]), "迭代次数", f"耗时 {r['dynamic']['time']:.3f}s", C["blue"])}
          </div>
        </div>
      </div>
    """))

    sections.append(slide(16, f"""
      {kicker("TASK 3 · MEANING")}
      {title_block("任务 3：重点缓存货位选择解决“哪些位置值得重点使用”。", "它不是决定当天某个托盘怎么搬，而是做布局层面的选址：从仓库中已有候选位置里，挑出一批重点缓存/中转货位。", wide=True)}
      <div class="split">
        <div class="side-stack">
          {note("候选位置固定", "模型不会凭空生成新坐标。仓库里已有一批可用候选货位，我们只决定哪些被选中。", C["blue"])}
          {note("选中结果不固定", "最终启用哪些重点缓存点，由货位价值、选中数量和间距约束共同决定。", C["coral"])}
        </div>
        {map_box("dark candidates selected workstations", cls="large-map")}
      </div>
    """, dark=True))

    sections.append(slide(17, f"""
      {kicker("TASK 3 · CANDIDATES")}
      {title_block("候选货位：可以被选为重点缓存点的备选位置。", "当前实验用托盘位置作为候选货位。它们代表仓库中已经存在、可以放置或周转托盘的位置。")}
      <div class="split">
        {map_box("candidates workstations", cls="large-map")}
        <div class="side-stack">
          {note("它们是已知数据", "候选货位的坐标来自 CSV，不是模型临时编造的位置。", C["blue"])}
          {note("它们还不是最终决策", "灰色点只是“可以选”。模型最后会从这些点中挑出固定数量的重点货位。", C["amber"])}
          {note("现实含义", "候选点可以理解为可放货、可缓存、可中转或适合提前补货的位置。", C["green"])}
        </div>
      </div>
    """))

    sections.append(slide(18, f"""
      {kicker("TASK 3 · SELECTED POINTS")}
      {title_block("重点缓存/中转货位：最终被选中的高价值位置。", "这些点不是普通存货点，而是更适合承担高频托盘、工位前补货、临时缓存或出库前暂存的空间节点。", wide=True)}
      <div class="split map-heavy">
        {map_box("candidates selected workstations", cls="large-map")}
        <div class="quad-grid small">
          {note("高频货物前置", "让常用托盘更靠近作业流线。", C["blue"])}
          {note("工位前补货", "减少工位等待，提升供货稳定性。", C["green"])}
          {note("临时缓存", "AGV 可先把托盘放到中转点。", C["amber"])}
          {note("出库前暂存", "将待发运托盘集中到合适位置。", C["coral"])}
        </div>
      </div>
    """))

    sections.append(slide(19, f"""
      {kicker("TASK 3 · DISTANCE")}
      {title_block("通道距离和间距约束让布局不挤在一起。", "AGV 通常沿仓库通道和网格移动，因此这里用曼哈顿距离近似行驶距离；两个重点货位太近时不能同时选中。", wide=True)}
      <div class="split">
        {map_box("candidates conflicts workstations", cls="large-map")}
        <div class="side-stack">
          {formula("曼哈顿距离", ["dist(a,b)=|x_a-x_b|+|y_a-y_b|", "适合近似网格通道中的 AGV 行驶距离"], C["blue"])}
          {formula("间距约束", ["如果 dist(i,j) ≤ 6，则 i 和 j 不能同时选", "红色连线表示部分“距离过近”的冲突关系"], C["coral"])}
        </div>
      </div>
    """))

    sections.append(slide(20, f"""
      {kicker("TASK 3 · MODEL")}
      {title_block("任务 3 的模型：从候选货位中选一组分布合理的重点点位。", "核心决策变量是 0-1 变量：某个候选货位选或不选。目标不是工位负载均衡，而是布局层面的点位选择。", wide=True)}
      <div class="formula-grid">
        {formula("决策变量与目标", ["x_i ∈ {0,1}：候选货位 i 是否被选中", "Σ_i x_i = 10：选出固定数量的重点点位", "优先选择价值更高的位置：max Σ score_i x_i", "score_i 在实验中由托盘货量等信息近似"], C["coral"])}
        {formula("空间约束", ["若候选点 i 与 j 距离过近，则 x_i + x_j ≤ 1", "这类约束称为冲突边约束", "作用：避免重点缓存点集中在同一小片区域"], C["blue"])}
      </div>
      <div class="wide-callout reveal">一句话解释：候选货位的位置已知，模型决定哪些位置被启用为重点缓存/中转货位。</div>
    """))

    sections.append(slide(21, f"""
      {kicker("ALGORITHM · PENALTY")}
      {title_block("二次罚函数法：把难处理的约束变成逐渐加重的惩罚。", "任务 3 有选中数量约束和间距约束。罚函数法先求一个连续松弛解，再逐步提高罚参数，让解越来越接近可行。", wide=True)}
      <div class="split">
        {formula("罚函数形式", ["Φ_ρ(x)=f(x)+ρ/2·||h(x)||²+ρ/2·||max(g(x),0)||²", "h(x)=0 表示选中数量等式约束", "g(x)≤0 表示距离冲突不等式约束"], C["violet"])}
        {flow([
          ("初始化", "给定连续变量 x 和罚参数 ρ", C["blue"]),
          ("解子问题", "最小化当前罚函数 Φ_ρ(x)", C["green"]),
          ("检查违反量", "等式和不等式违反量足够小则停止", C["amber"]),
          ("增大 ρ", "约束惩罚变强，继续外层迭代", C["coral"]),
        ])}
      </div>
    """))

    sections.append(slide(22, f"""
      {kicker("ALGORITHM · PROJECTED BB")}
      {title_block("投影 BB 梯度法：高效求解罚函数子问题。", "罚函数子问题仍要求变量保持在 0 到 1 之间。投影保证边界可行，BB 步长让梯度法比固定步长更快。", wide=True)}
      {flow([
        ("梯度方向", "根据当前罚函数计算 ∇Φ_ρ(x)", C["blue"]),
        ("BB 步长", "用前后两次迭代差分估计合适步长", C["green"]),
        ("投影", "把 x - α∇Φ 投影回 0≤x≤1", C["amber"]),
        ("线搜索", "若下降不足，缩小步长保证稳定", C["coral"]),
      ])}
      <div class="wide-callout reveal">为什么适合这里：任务 3 的连续松弛变量天然有盒约束 0≤xᵢ≤1，投影梯度法可以保持迭代始终在这个范围内。</div>
    """))

    sections.append(slide(23, f"""
      {kicker("TASK 3 · RESULT")}
      {title_block("任务 3 输出一组分散的重点缓存/中转货位。", "最终结果从候选货位中选出 10 个点，并满足最小间距要求；红色方块就是布局层面的启用点位。")}
      <div class="split map-heavy">
        {map_box("candidates selected workstations", cls="large-map")}
        <div class="side-stack">
          <div class="metric-grid two">
            {metric(str(len(r["layout"]["selected"])), "选中重点货位", "固定选择数量", C["coral"])}
            {metric(str(r["layout"]["min_pair_distance"]), "最小两两距离", "要求大于 6", C["blue"])}
            {metric(str(r["layout"]["conflict_edges"]), "冲突边数量", "候选点之间过近关系", C["amber"])}
            {metric(str(r["layout"]["outer_iterations"]), "罚函数外层迭代", f"耗时 {r['layout']['time']:.3f}s", C["green"])}
          </div>
          {note("结果解释", "这些点可以作为后续高频货物前置、工位前补货和 AGV 临时中转的重点位置。", C["ink"])}
        </div>
      </div>
    """))

    sections.append(slide(24, f"""
      {kicker("EXPERIMENT SETUP")}
      {title_block("实验设置：数据、模型、算法都已经自动化串联。", "仓库 CSV 被统一读取成坐标、货量和距离矩阵；三个求解脚本分别构造模型并调用对应算法。", wide=True)}
      <div class="split code-split">
        <pre class="code-card reveal">warehouse_data.py          读取地图、托盘、AGV、工位
solve_agv_assignment.py    构造并求解任务分配模型
solve_dynamic_partition.py 构造并求解动态分区模型
solve_warehouse_layout.py  构造并求解重点货位选择模型
algorithms/                教材算法的 Python 实现
run_all.py                 一键运行三个实验并输出结果</pre>
        <div class="side-stack">
          {note("环境", "Python 虚拟环境中安装 numpy、scipy、pandas、matplotlib 等常用科学计算库。", C["blue"])}
          {note("复现方式", "运行统一入口脚本，即可依次生成三个任务的模型、求解结果和 CSV 输出。", C["green"])}
        </div>
      </div>
    """))

    sections.append(slide(25, f"""
      {kicker("AUTOMATION")}
      {title_block("建模和求解流程是自动化的。", "实验并不是手工填矩阵，而是由代码从数据生成距离矩阵、目标向量、约束矩阵，再调用自实现算法。")}
      {flow([
        ("CSV 数据", "地图、托盘、AGV、工位", C["blue"]),
        ("特征计算", "曼哈顿距离、货量统计、冲突边", C["green"]),
        ("模型生成", "目标向量 c、约束矩阵 A、右端项 b", C["amber"]),
        ("算法求解", "内点法、罚函数法、投影 BB", C["violet"]),
        ("结果输出", "分配表、分区负载、重点货位", C["coral"]),
      ])}
      <div class="wide-callout reveal">自动化的好处：换一批仓库坐标或托盘货量后，不需要重新手推模型；代码会重新生成问题规模、距离矩阵和约束结构。</div>
    """))

    sections.append(slide(26, f"""
      {kicker("ALGORITHM MAP")}
      {title_block("算法选择与三个任务一一对应。", "线性规划问题交给原始-对偶内点法；带 0-1 选择和空间冲突的布局问题先连续松弛，再用罚函数与投影梯度处理。")}
      <div class="table-card wide reveal" data-table="algorithmMap"></div>
    """))

    sections.append(slide(27, f"""
      {kicker("ANALYSIS")}
      {title_block("综合分析：三个任务分别优化仓库运行的不同层面。", "它们不是互相重复，而是从当天调度、区域组织到长期布局逐层递进。", wide=True)}
      <div class="goal-grid">
        {note("任务 1", "降低单次搬运路线成本，适合解释 AGV 调度效率。", C["blue"], cls="large")}
        {note("任务 2", "平衡工位服务货量与距离，适合解释仓库区域组织。", C["green"], cls="large")}
        {note("任务 3", "选择分散的重点缓存点，适合解释布局设计与拥堵缓解。", C["coral"], cls="large")}
      </div>
      <div class="wide-callout reveal">结果口径：本实验关注独立建模与自实现算法的可复现闭环，每个数值结果都来自同一套数据读取、模型生成和求解流程。</div>
    """))

    sections.append(slide(28, f"""
      {kicker("CONCLUSION")}
      {title_block("项目总结：用优化建模连接仓库现场和算法实现。", "我们明确了实体含义，完成了三个模型的自动生成，并用教材算法实现求解。课程项目的重点不只是给出结果，而是解释结果为什么对应真实仓库决策。", wide=True)}
      <div class="summary-list reveal">
        <p>AGV 任务分配：回答谁去搬，减少搬运路线成本。</p>
        <p>动态分区：回答货量归谁处理，兼顾距离和工位负载。</p>
        <p>重点缓存货位选择：回答哪些位置值得重点使用，改善布局分散性。</p>
        <p>后续可扩展：加入电量、时间窗、拥堵避让、真实道路网络和多目标优化。</p>
      </div>
      <div class="summary-map">{map_box("dark selected routes agvs candidates workstations")}</div>
    """, dark=True))

    return "\n".join(sections)


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    slides_html = build_slides(data)
    data_json = json.dumps(data, ensure_ascii=False)

    template = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AGV 仓储优化 · 原生 HTML 动画演示稿</title>
  <style>
    :root {
      --stage-bg: #070A0F;
      --ink: #101418;
      --ink-2: #1D2630;
      --paper: #F7F8F5;
      --white: #FFFFFF;
      --line: #D6DDE3;
      --muted: #68717D;
      --blue: #2276FF;
      --green: #35A66A;
      --amber: #E6A72A;
      --coral: #F25E4B;
      --violet: #6C5CE7;
      --ease: cubic-bezier(.16, 1, .3, 1);
      --font: -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Noto Sans SC", Arial, sans-serif;
    }
    * { box-sizing: border-box; }
    html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; background: var(--stage-bg); font-family: var(--font); }
    body {
      color: var(--ink);
      background:
        linear-gradient(120deg, rgba(34,118,255,.16), transparent 28%),
        linear-gradient(240deg, rgba(242,94,75,.13), transparent 28%),
        var(--stage-bg);
    }
    .viewport { position: fixed; inset: 0; overflow: hidden; }
    .stage {
      position: absolute;
      width: 1920px;
      height: 1080px;
      left: 0;
      top: 0;
      transform-origin: 0 0;
      overflow: hidden;
      background: var(--paper);
      box-shadow: 0 50px 120px rgba(0,0,0,.38);
    }
    .slide {
      position: absolute;
      inset: 0;
      width: 1920px;
      height: 1080px;
      padding: 0;
      background: var(--paper);
      visibility: hidden;
      opacity: 0;
      pointer-events: none;
      transform: translate3d(46px, 0, -120px) rotateY(-5deg) scale(.965);
      filter: blur(8px);
      transition: opacity .45s var(--ease), transform .62s var(--ease), filter .45s var(--ease), visibility .45s step-end;
    }
    .slide.dark { background: #0B1118; color: var(--white); }
    .slide.active {
      visibility: visible;
      opacity: 1;
      pointer-events: auto;
      transform: translate3d(0,0,0) rotateY(0) scale(1);
      filter: blur(0);
      transition: opacity .45s var(--ease), transform .62s var(--ease), filter .45s var(--ease), visibility 0s;
      z-index: 4;
    }
    .slide-inner {
      position: absolute;
      inset: 0 auto auto 0;
      width: 1280px;
      height: 720px;
      padding: 52px 72px;
      transform: scale(1.5);
      transform-origin: 0 0;
    }
    .slide.exit-left {
      transform: translate3d(-46px,0,-140px) rotateY(5deg) scale(.955);
      opacity: 0;
      filter: blur(8px);
    }
    .slide::after {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background: linear-gradient(105deg, transparent 0%, rgba(255,255,255,.2) 38%, transparent 55%);
      opacity: 0;
      transform: translateX(-110%);
    }
    .slide.active::after { animation: sheen 1.05s .1s var(--ease) both; }
    .kicker { display: flex; align-items: center; gap: 12px; font-size: 12px; font-weight: 900; color: #59636F; letter-spacing: .04em; text-transform: uppercase; }
    .kicker::before { content: ""; width: 7px; height: 7px; background: currentColor; display: block; }
    .dark .kicker { color: #B7C2D0; }
    .title { margin: 26px 0 0; width: 900px; font-size: 40px; line-height: 1.14; font-weight: 950; letter-spacing: 0; }
    .title.wide { width: 1100px; }
    .subtitle { margin: 18px 0 0; width: 900px; font-size: 17px; line-height: 1.42; color: var(--muted); }
    .dark .subtitle { color: #B7C2D0; }
    .rule { width: 420px; height: 4px; background: var(--blue); margin-top: 34px; }
    .folio { position: absolute; left: 72px; right: 72px; bottom: 22px; display: flex; justify-content: space-between; color: #7C8794; font-size: 10px; }
    .folio::before { content: ""; position: absolute; left: 0; bottom: 26px; width: 300px; height: 1px; background: currentColor; opacity: .35; }
    .reveal { opacity: 0; transform: translateY(18px); transition: opacity .5s var(--ease), transform .5s var(--ease); }
    .active .reveal { opacity: 1; transform: translateY(0); }
    .active .reveal:nth-child(2) { transition-delay: .04s; }
    .active .reveal:nth-child(3) { transition-delay: .08s; }
    .active .reveal:nth-child(4) { transition-delay: .12s; }
    .active .reveal:nth-child(5) { transition-delay: .16s; }
    .active .reveal:nth-child(6) { transition-delay: .2s; }
    .metric-row { display: grid; grid-template-columns: repeat(3, 180px); gap: 50px; margin-top: 52px; }
    .metric-grid { display: grid; gap: 22px; }
    .metric-grid.two { grid-template-columns: 1fr 1fr; }
    .metric-value { font-size: 38px; line-height: 1; font-weight: 950; }
    .metric-label { margin-top: 9px; font-size: 14px; font-weight: 900; color: var(--ink); }
    .dark .metric-label { color: var(--white); }
    .metric-note { margin-top: 7px; color: var(--muted); font-size: 11px; line-height: 1.42; }
    .dark .metric-note { color: #9AA7B8; }
    .cover-map { position: absolute; right: 80px; top: 112px; width: 330px; height: 235px; }
    .cover-map .warehouse-map, .summary-map .warehouse-map { width: 100%; height: 100%; }
    .cover-note { position: absolute; right: 82px; top: 420px; width: 340px; }
    .split { display: grid; grid-template-columns: 560px 1fr; gap: 56px; align-items: start; margin-top: 36px; }
    .split.map-heavy { grid-template-columns: 600px 1fr; gap: 46px; }
    .split.code-split { grid-template-columns: 640px 1fr; }
    .side-stack { display: grid; gap: 20px; align-content: start; }
    .goal-grid, .entity-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 28px; margin-top: 68px; }
    .entity, .note-card, .formula, .flow-step, .wide-callout, .table-card, .code-card {
      background: rgba(255,255,255,.82);
      border: 1px solid var(--line);
      box-shadow: 0 8px 24px rgba(16,20,24,.05);
    }
    .dark .entity, .dark .note-card, .dark .formula, .dark .flow-step, .dark .wide-callout, .dark .table-card {
      background: rgba(21,27,34,.92);
      border-color: #2E3946;
      box-shadow: none;
    }
    .note-card, .formula { border-left: 5px solid var(--accent); padding: 18px 20px; }
    .note-card.large { min-height: 150px; }
    .note-card h3, .formula h3, .flow-step h3, .entity h3 { margin: 0; font-size: 17px; line-height: 1.25; font-weight: 950; }
    .note-card.large h3 { font-size: 24px; color: var(--accent); }
    .note-card p, .formula p, .flow-step p, .entity p { margin: 10px 0 0; color: var(--muted); font-size: 12.5px; line-height: 1.5; }
    .dark .note-card p, .dark .formula p, .dark .flow-step p, .dark .entity p { color: #B9C5D2; }
    .formula-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 60px; margin-top: 52px; }
    .formula { min-height: 200px; }
    .formula p { font-size: 15px; color: var(--ink-2); }
    .dark .formula p { color: #DCE5EE; }
    .math {
      font-family: "Times New Roman", "STIX Two Text", Georgia, serif;
      font-style: italic;
      font-weight: 700;
      letter-spacing: 0;
      white-space: nowrap;
    }
    .math sub, .math sup, sup {
      font-size: .68em;
      line-height: 0;
      position: relative;
    }
    .math sub { bottom: -.22em; }
    .math sup, sup { top: -.36em; }
    .flow { display: grid; grid-template-columns: repeat(4, 1fr); gap: 28px; margin-top: 74px; }
    .flow .flow-step { position: relative; overflow: hidden; border-top: 5px solid var(--accent); padding: 22px 18px; min-height: 104px; }
    .flow .flow-step::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 5px; background: var(--accent); transform: scaleX(0); transform-origin: 0 50%; }
    .active .flow .flow-step::before { animation: stepTrace .72s var(--ease) forwards; }
    .active .flow .flow-step:nth-child(2)::before { animation-delay: .12s; }
    .active .flow .flow-step:nth-child(3)::before { animation-delay: .24s; }
    .active .flow .flow-step:nth-child(4)::before { animation-delay: .36s; }
    .flow .flow-step:not(:last-child)::after { content: ""; position: absolute; right: -28px; top: 50%; width: 28px; height: 2px; background: #A9B3BE; transform: translateY(-50%); }
    .wide-callout { margin: 42px auto 0; width: 860px; padding: 18px 22px; border-left: 5px solid var(--ink); font-size: 18px; line-height: 1.45; font-weight: 800; color: var(--ink-2); }
    .dark .wide-callout { color: #E8EEF6; border-left-color: var(--blue); }
    .large-map { width: 100%; height: 350px; }
    .warehouse-map { position: relative; overflow: hidden; background: #F8FAFB; border: 1px solid var(--line); }
    .dark .warehouse-map, .warehouse-map.dark-map { background: #111820; border-color: #2E3946; }
    .map-cell, .map-dot, .map-square, .map-line { position: absolute; }
    .map-cell { border: .5px solid rgba(255,255,255,.7); opacity: .96; }
    .map-dot { border-radius: 50%; transform: scale(.65); opacity: 0; }
    .active .map-dot { animation: pop .42s var(--ease) forwards; }
    .map-square { transform: scale(.7); opacity: 0; }
    .active .map-square { animation: pop .42s var(--ease) forwards, pulse 2s ease-in-out infinite; }
    .map-line { height: 2px; transform-origin: 0 50%; opacity: 0; }
    .active .map-line { animation: lineDraw .7s .22s var(--ease) forwards; }
    .route-runner { position: absolute; width: 9px; height: 9px; margin: -4.5px 0 0 -4.5px; border-radius: 50%; background: var(--runner, #F25E4B); box-shadow: 0 0 0 4px rgba(242,94,75,.16), 0 0 18px rgba(242,94,75,.42); offset-distance: 0%; opacity: 0; }
    .active .route-runner { animation: runRoute 2.35s var(--ease) forwards; }
    .chart { min-height: 150px; }
    .bar-row { display: grid; grid-template-columns: 58px 1fr 60px; gap: 10px; align-items: center; margin: 10px 0; font-size: 11px; color: var(--muted); }
    .bar-track { height: 12px; background: #E1E6EA; position: relative; overflow: hidden; }
    .bar-fill { position: absolute; inset: 0 auto 0 0; width: var(--w); background: var(--color); transform: scaleX(0); transform-origin: 0 50%; transition: transform .7s var(--ease); }
    .active .bar-fill { transform: scaleX(1); }
    .loadbars .bar-row { grid-template-columns: 42px 1fr 58px; margin: 7px 0; }
    .station-legend { display: grid; gap: 10px; }
    .legend-item { display: flex; gap: 12px; align-items: center; color: var(--muted); font-size: 12px; }
    .legend-swatch { width: 12px; height: 12px; border-radius: 50%; }
    .quad-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 44px; }
    .quad-grid.small { margin-top: 16px; }
    .table-card { padding: 0; overflow: hidden; }
    .table-card.wide { margin-top: 60px; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th { background: var(--ink-2); color: var(--white); text-align: left; padding: 12px 14px; font-size: 11px; }
    td { padding: 11px 14px; border-top: 1px solid var(--line); color: var(--ink-2); }
    tr:nth-child(even) td { background: #F0F4F6; }
    .code-card { margin: 0; padding: 26px 28px; color: #DCE5EE; background: var(--ink-2); font: 16px/1.8 Menlo, Monaco, Consolas, monospace; white-space: pre-wrap; }
    .summary-list { margin-top: 52px; width: 790px; display: grid; gap: 22px; }
    .summary-list p { margin: 0; padding-left: 18px; border-left: 5px solid var(--blue); color: #E8EEF6; font-size: 17px; line-height: 1.4; }
    .summary-map { position: absolute; right: 118px; bottom: 126px; width: 260px; height: 190px; }
    .icon { width: 110px; height: 82px; margin: 28px 0 14px; position: relative; }
    .entity { padding: 20px 30px 28px; border-top: 6px solid var(--accent); min-height: 210px; }
    .entity h3 { font-size: 28px; color: var(--accent); }
    .icon.agv::before { content: ""; position: absolute; left: 0; top: 24px; width: 106px; height: 44px; background: #EAF1FF; border: 2px solid var(--blue); }
    .icon.agv::after { content: ""; position: absolute; left: 16px; top: 58px; width: 74px; height: 18px; border-radius: 999px; background: linear-gradient(90deg, var(--ink) 0 22px, transparent 22px 52px, var(--ink) 52px); }
    .icon.pallet::before { content: ""; position: absolute; left: 0; top: 52px; width: 112px; height: 12px; background: #8A5A2E; }
    .icon.pallet::after { content: ""; position: absolute; left: 6px; top: 20px; width: 98px; height: 32px; background: repeating-linear-gradient(90deg, var(--amber) 0 28px, transparent 28px 34px); }
    .icon.station::before { content: ""; position: absolute; left: 18px; top: 12px; width: 84px; height: 62px; background: #EAFBF1; border: 2px solid var(--green); }
    .icon.station::after { content: ""; position: absolute; left: 32px; top: 28px; width: 56px; height: 34px; background: repeating-linear-gradient(0deg, var(--green) 0 6px, transparent 6px 16px); }
    .lane-list { margin-top: 58px; display: grid; gap: 24px; }
    .lane { display: grid; grid-template-columns: 95px 150px 320px 1fr; gap: 28px; align-items: center; padding: 20px 28px; background: #19232D; border-left: 6px solid var(--blue); }
    .lane.green { border-left-color: var(--green); }
    .lane.coral { border-left-color: var(--coral); }
    .lane span { color: var(--blue); font-weight: 950; }
    .lane.green span { color: var(--green); }
    .lane.coral span { color: var(--coral); }
    .lane strong { font-size: 22px; }
    .lane p, .lane em { margin: 0; color: #D2DAE4; font-size: 15px; font-style: normal; }
    .lane em { color: #A9B4C2; }
    .hud { position: fixed; left: 22px; right: 22px; bottom: 18px; z-index: 50; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 14px; pointer-events: none; }
    .glass { background: rgba(11,17,24,.72); color: #E8EEF6; border: 1px solid rgba(255,255,255,.16); backdrop-filter: blur(18px); box-shadow: 0 18px 48px rgba(0,0,0,.22); }
    .hint { position: fixed; left: 22px; top: 18px; z-index: 55; padding: 10px 13px; border-radius: 999px; font-size: 12px; color: #DCE5EE; }
    .counter { justify-self: center; display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 999px; font-size: 13px; font-weight: 900; pointer-events: auto; }
    .counter button, .tools button, .thumb { border: 0; font: inherit; cursor: pointer; color: inherit; }
    .counter button { width: 28px; height: 28px; border-radius: 50%; background: rgba(255,255,255,.12); }
    .tools { justify-self: end; display: flex; gap: 9px; pointer-events: auto; }
    .tools button { padding: 10px 13px; border-radius: 12px; background: rgba(11,17,24,.72); border: 1px solid rgba(255,255,255,.16); font-size: 12px; font-weight: 900; }
    .speaker-note { justify-self: start; max-width: 520px; padding: 11px 14px; border-radius: 12px; color: #DCE5EE; font-size: 12px; line-height: 1.35; }
    .progress { position: fixed; left: 0; bottom: 0; width: 100%; height: 4px; background: rgba(255,255,255,.08); z-index: 60; }
    .progress span { display: block; height: 100%; width: 0; background: linear-gradient(90deg, var(--blue), var(--green), var(--amber), var(--coral)); transition: width .32s var(--ease); }
    .nav { position: fixed; inset: 0; z-index: 70; background: rgba(7,10,15,.85); backdrop-filter: blur(20px); opacity: 0; visibility: hidden; transition: opacity .24s var(--ease), visibility .24s step-end; display: grid; grid-template-columns: 310px 1fr; }
    .nav.open { opacity: 1; visibility: visible; transition: opacity .24s var(--ease), visibility 0s; }
    .nav-copy { padding: 44px 34px; color: var(--white); border-right: 1px solid rgba(255,255,255,.14); }
    .nav-copy h2 { margin: 0; font-size: 28px; line-height: 1.15; }
    .nav-copy p { color: #A9B4C2; line-height: 1.55; font-size: 13px; }
    .thumb-grid { padding: 34px; display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; overflow: auto; }
    .thumb { text-align: left; padding: 14px; border-radius: 14px; background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.12); transition: transform .22s var(--ease), border-color .22s var(--ease); }
    .thumb:hover, .thumb.current { transform: translateY(-2px); border-color: rgba(34,118,255,.8); }
    .thumb span { color: var(--blue); font-size: 11px; font-weight: 950; }
    .thumb strong { display: block; margin-top: 6px; color: var(--white); font-size: 14px; }
    .thumb em { display: block; margin-top: 4px; color: #9AA7B8; font-size: 12px; font-style: normal; }
    @keyframes sheen { 0% { opacity: 0; transform: translateX(-110%); } 20% { opacity: .5; } 100% { opacity: 0; transform: translateX(110%); } }
    @keyframes pop { to { opacity: 1; transform: scale(1); } }
    @keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(242,94,75,.45); } 50% { box-shadow: 0 0 0 8px rgba(242,94,75,0); } }
    @keyframes lineDraw { from { opacity: 0; transform: rotate(var(--angle)) scaleX(0); } to { opacity: 1; transform: rotate(var(--angle)) scaleX(1); } }
    @keyframes runRoute { 0% { opacity: 0; offset-distance: 0%; transform: scale(.7); } 8% { opacity: 1; } 82% { opacity: 1; offset-distance: 100%; transform: scale(1); } 100% { opacity: 0; offset-distance: 100%; transform: scale(.7); } }
    @keyframes stepTrace { to { transform: scaleX(1); } }
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; } }
  </style>
</head>
<body>
  <div class="viewport">
    <main class="stage" id="stage">
__SLIDES__
    </main>
  </div>
  <div class="hint glass">原生 HTML 绘制 · ← → 翻页 · M 目录 · F 全屏</div>
  <div class="hud">
    <div class="speaker-note glass" id="speakerNote"></div>
    <div class="counter glass"><button id="prevBtn">‹</button><span id="counter">01 / 28</span><button id="nextBtn">›</button></div>
    <div class="tools"><button id="menuBtn">目录</button><button id="fullBtn">全屏</button></div>
  </div>
  <div class="progress"><span id="progress"></span></div>
  <aside class="nav" id="nav">
    <div class="nav-copy"><h2>AGV 仓储优化<br>原生 HTML 演示稿</h2><p>地图、路线、柱状图、表格、模型框和流程图均由浏览器实时绘制。</p><p>按 M 打开或关闭目录。</p></div>
    <div class="thumb-grid" id="thumbGrid"></div>
  </aside>
  <script>
    const deckData = __DATA__;
    const stage = document.getElementById('stage');
    const slides = [...document.querySelectorAll('.slide')];
    const counter = document.getElementById('counter');
    const noteBox = document.getElementById('speakerNote');
    const progress = document.getElementById('progress');
    const nav = document.getElementById('nav');
    const thumbGrid = document.getElementById('thumbGrid');
    const pageNotes = [
      "项目封面：先说明这是仓储现场问题，不是孤立数学题。",
      "背景页：解释为什么 AGV、托盘、工位会带来调度压力。",
      "实体页：先让听众理解 AGV、托盘、工位。",
      "目标页：三个任务分别回答三个仓库决策。",
      "数据页：地图和货量是所有模型的共同输入。",
      "总览页：三个问题对应不同决策层级。",
      "任务 1：强调谁去搬。",
      "模型 1：解释 x 和 y 的现实含义。",
      "算法 1：内点法求松弛，恢复成可执行任务。",
      "结果 1：路线和表格可以逐条解释。",
      "任务 2：强调货量归谁处理。",
      "区域页：区域是工位服务范围，不是墙。",
      "模型 2：货量是连续流量。",
      "算法 2：标准线性规划内点法。",
      "结果 2：看工位负载和距离成本。",
      "任务 3：强调布局选址，不是当天搬运。",
      "候选货位：位置固定，是否启用待决策。",
      "重点货位：最终选中的缓存/中转点。",
      "距离页：曼哈顿距离和冲突边。",
      "模型 3：0-1 选择和空间约束。",
      "罚函数：把约束转成惩罚。",
      "投影 BB：处理 0 到 1 的盒约束。",
      "结果 3：选 10 个点且间距满足要求。",
      "实验设置：仓库结构和代码入口。",
      "自动化：CSV 到模型再到结果。",
      "算法对应：为什么这样配算法。",
      "综合分析：三个任务不是重复。",
      "总结：项目价值和可扩展方向。"
    ];
    const typeColors = {"1":"#D7DDE4","2":"#9BD4B5","3":"#F2C75E","4":"#3D4855","5":"#2276FF","6":"#C69BE8","7":"#F25E4B","8":"#65C9D5"};
    const stationColors = ["#2276FF","#35A66A","#E6A72A","#F25E4B","#6C5CE7","#2DB8C6"];
    let current = 0;

    function add(parent, cls, style = {}) {
      const el = document.createElement('div');
      if (cls) el.className = cls;
      Object.assign(el.style, style);
      parent.appendChild(el);
      return el;
    }
    function point(t, x, y) {
      return {
        x: t.ox + x * t.cell + t.cell / 2,
        y: t.oy + (t.rows - 1 - y) * t.cell + t.cell / 2
      };
    }
    function drawLine(parent, a, b, color, width = 2) {
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len = Math.sqrt(dx * dx + dy * dy);
      const angle = Math.atan2(dy, dx);
      add(parent, 'map-line', {
        left: `${a.x}px`,
        top: `${a.y}px`,
        width: `${len}px`,
        height: `${width}px`,
        background: color,
        '--angle': `${angle}rad`
      });
    }
    function lRoute(parent, t, a, b, color) {
      const pa = point(t, a[0], a[1]);
      const pb = point(t, b[0], b[1]);
      const mid = {x: pb.x, y: pa.y};
      drawLine(parent, pa, mid, color, 2.2);
      drawLine(parent, mid, pb, color, 2.2);
    }
    function routeRunner(parent, t, agv, pallet, workstation, delayMs) {
      const pa = point(t, agv[0], agv[1]);
      const pp = point(t, pallet[0], pallet[1]);
      const ps = point(t, workstation[0], workstation[1]);
      const midPickup = {x: pp.x, y: pa.y};
      const midDrop = {x: ps.x, y: pp.y};
      const path = `M ${pa.x} ${pa.y} L ${midPickup.x} ${midPickup.y} L ${pp.x} ${pp.y} L ${midDrop.x} ${midDrop.y} L ${ps.x} ${ps.y}`;
      add(parent, 'route-runner', {
        offsetPath: `path("${path}")`,
        animationDelay: `${delayMs}ms`
      });
    }
    function drawMap(el) {
      const mode = el.dataset.map || "";
      if (mode.includes('dark')) el.classList.add('dark-map');
      const map = deckData.input.map;
      const cell = Math.min((el.clientWidth - 20) / map.ncols, (el.clientHeight - 20) / map.nrows);
      const t = {cell, cols: map.ncols, rows: map.nrows, ox: (el.clientWidth - cell * map.ncols) / 2, oy: (el.clientHeight - cell * map.nrows) / 2};
      map.nodes.forEach((n) => {
        add(el, 'map-cell', {
          left: `${t.ox + n.x * cell}px`,
          top: `${t.oy + (map.nrows - 1 - n.y) * cell}px`,
          width: `${Math.max(1, cell - 1)}px`,
          height: `${Math.max(1, cell - 1)}px`,
          background: mode.includes('type') ? (typeColors[n.type] || '#CBD3DA') : (mode.includes('dark') ? '#26313D' : '#E4E9EE')
        });
      });
      if (mode.includes('conflicts')) {
        const p = deckData.input.pallets.positions;
        let drawn = 0;
        for (let i = 0; i < p.length && drawn < 52; i++) {
          for (let j = i + 1; j < p.length && drawn < 52; j++) {
            const dist = Math.abs(p[i].x - p[j].x) + Math.abs(p[i].y - p[j].y);
            if (dist <= 6) {
              drawLine(el, point(t, p[i].x, p[i].y), point(t, p[j].x, p[j].y), '#F25E4B', 1.1);
              drawn++;
            }
          }
        }
      }
      if (mode.includes('routes')) {
        deckData.results.agv.assignments.slice(0, 8).forEach((r, i) => {
          lRoute(el, t, r.agv_xy, r.pallet_xy, '#F25E4B');
          lRoute(el, t, r.pallet_xy, r.workstation_xy, '#E6A72A');
          routeRunner(el, t, r.agv_xy, r.pallet_xy, r.workstation_xy, 260 + i * 140);
        });
      }
      if (mode.includes('dynamic')) {
        (deckData.results.dynamic.pallet_assignments || []).forEach((p, i) => {
          const pt = point(t, p.x, p.y);
          add(el, 'map-dot', {
            left: `${pt.x - cell * .27}px`,
            top: `${pt.y - cell * .27}px`,
            width: `${cell * .54}px`,
            height: `${cell * .54}px`,
            background: stationColors[p.station % stationColors.length],
            border: '1px solid rgba(255,255,255,.85)',
            animationDelay: `${Math.min(i, 80) * 8}ms`
          });
        });
      }
      if (mode.includes('candidates')) {
        deckData.input.pallets.positions.forEach((p, i) => {
          const pt = point(t, p.x, p.y);
          add(el, 'map-dot', {
            left: `${pt.x - cell * .18}px`,
            top: `${pt.y - cell * .18}px`,
            width: `${cell * .36}px`,
            height: `${cell * .36}px`,
            background: mode.includes('dark') ? '#7C8794' : '#8F99A6',
            animationDelay: `${Math.min(i, 80) * 5}ms`
          });
        });
      }
      if (mode.includes('workstations')) {
        deckData.input.workstations.positions.forEach((p) => {
          const pt = point(t, p.x, p.y);
          add(el, 'map-square', {
            left: `${pt.x - cell * .43}px`,
            top: `${pt.y - cell * .43}px`,
            width: `${cell * .86}px`,
            height: `${cell * .86}px`,
            background: '#2276FF',
            border: '1px solid rgba(255,255,255,.9)',
            animationDelay: '80ms'
          });
        });
      }
      if (mode.includes('agvs')) {
        deckData.results.agv.assignments.forEach((r, i) => {
          const pt = point(t, r.agv_xy[0], r.agv_xy[1]);
          add(el, 'map-dot', {
            left: `${pt.x - cell * .35}px`,
            top: `${pt.y - cell * .35}px`,
            width: `${cell * .7}px`,
            height: `${cell * .7}px`,
            background: '#F25E4B',
            border: '1px solid rgba(255,255,255,.9)',
            animationDelay: `${100 + i * 20}ms`
          });
        });
      }
      if (mode.includes('selected')) {
        deckData.results.layout.selected.forEach((p, i) => {
          const pt = point(t, p.x, p.y);
          add(el, 'map-square', {
            left: `${pt.x - cell * .42}px`,
            top: `${pt.y - cell * .42}px`,
            width: `${cell * .84}px`,
            height: `${cell * .84}px`,
            background: '#F25E4B',
            border: '1px solid #fff',
            animationDelay: `${120 + i * 55}ms`
          });
        });
      }
    }
    function drawCharts() {
      document.querySelectorAll('[data-chart="quantityBins"]').forEach((el) => {
        const bins = deckData.input.pallets.quantity_bins;
        const max = Math.max(...bins.map((d) => d.count));
        el.innerHTML = '<h3>托盘货量分布</h3>';
        bins.forEach((d, i) => {
          const row = add(el, 'bar-row');
          row.innerHTML = `<span>${d.label}</span><div class="bar-track"><div class="bar-fill" style="--w:${d.count / max * 100}%;--color:${stationColors[i]}"></div></div><strong>${d.count}</strong>`;
        });
      });
      document.querySelectorAll('[data-chart="loadBars"]').forEach((el) => {
        const loads = deckData.results.dynamic.loads;
        const max = Math.max(...loads.map((d) => d.load));
        el.classList.add('loadbars');
        el.innerHTML = '<h3>工位负载</h3>';
        loads.forEach((d, i) => {
          const row = add(el, 'bar-row');
          row.innerHTML = `<span>W${d.index}</span><div class="bar-track"><div class="bar-fill" style="--w:${d.load / max * 100}%;--color:${stationColors[i % stationColors.length]}"></div></div><strong>${Math.round(d.load)}</strong>`;
        });
      });
      document.querySelectorAll('[data-chart="stationLegend"]').forEach((el) => {
        el.classList.add('station-legend');
        deckData.results.dynamic.loads.slice(0, 8).forEach((d, i) => {
          const item = add(el, 'legend-item');
          item.innerHTML = `<span class="legend-swatch" style="background:${stationColors[i % stationColors.length]}"></span><span>W${d.index} 服务货量 ${Math.round(d.load)}</span>`;
        });
      });
    }
    function drawTables() {
      document.querySelectorAll('[data-table="agvAssignments"]').forEach((el) => {
        const rows = deckData.results.agv.assignments.slice(0, 7);
        el.innerHTML = `<table><thead><tr><th>AGV</th><th>托盘</th><th>工位</th><th>距离</th></tr></thead><tbody>${rows.map(r => `<tr><td>${r.agv}</td><td>${r.pallet}</td><td>W${r.workstation}</td><td>${Math.round(r.cost)}</td></tr>`).join('')}</tbody></table>`;
      });
      document.querySelectorAll('[data-table="algorithmMap"]').forEach((el) => {
        const rows = [
          ["任务 1", "AGV 任务分配", "原始-对偶内点法 + 整数恢复", "线性目标和线性约束，最终需要可执行匹配"],
          ["任务 2", "动态分区", "原始-对偶内点法", "货量流向模型是标准线性规划"],
          ["任务 3", "重点缓存货位选择", "二次罚函数法 + 投影 BB 梯度法 + 离散修复", "先求连续松弛，再满足数量和间距约束"],
        ];
        el.innerHTML = `<table><thead><tr><th>任务</th><th>问题</th><th>算法</th><th>为什么合适</th></tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
      });
    }
    function buildThumbs() {
      thumbGrid.innerHTML = slides.map((s, i) => {
        const title = s.querySelector('.title')?.textContent || `第 ${i + 1} 页`;
        return `<button class="thumb" data-goto="${i}"><span>${String(i + 1).padStart(2,'0')}</span><strong>${title}</strong><em>${pageNotes[i]}</em></button>`;
      }).join('');
      thumbGrid.querySelectorAll('.thumb').forEach((btn) => btn.addEventListener('click', () => {
        show(Number(btn.dataset.goto));
        nav.classList.remove('open');
      }));
    }
    function scaleStage() {
      const scale = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
      stage.style.transform = `translate(${(window.innerWidth - 1920 * scale) / 2}px, ${(window.innerHeight - 1080 * scale) / 2}px) scale(${scale})`;
    }
    function show(index) {
      const next = Math.max(0, Math.min(index, slides.length - 1));
      slides.forEach((s, i) => {
        s.classList.remove('active', 'exit-left');
        if (i < next) s.classList.add('exit-left');
      });
      current = next;
      slides[current].classList.add('active');
      counter.textContent = `${String(current + 1).padStart(2,'0')} / ${String(slides.length).padStart(2,'0')}`;
      noteBox.textContent = pageNotes[current];
      progress.style.width = `${(current + 1) / slides.length * 100}%`;
      document.querySelectorAll('.thumb').forEach((t, i) => t.classList.toggle('current', i === current));
    }
    function toggleNav(force) {
      nav.classList.toggle('open', force ?? !nav.classList.contains('open'));
    }
    function toggleFullscreen() {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
      else document.exitFullscreen?.();
    }
    document.querySelectorAll('.warehouse-map').forEach(drawMap);
    drawCharts();
    drawTables();
    buildThumbs();
    scaleStage();
    window.addEventListener('resize', scaleStage);
    window.addEventListener('keydown', (e) => {
      if (['ArrowRight', 'PageDown', ' '].includes(e.key)) show(current + 1);
      if (['ArrowLeft', 'PageUp'].includes(e.key)) show(current - 1);
      if (e.key === 'Home') show(0);
      if (e.key === 'End') show(slides.length - 1);
      if (e.key.toLowerCase() === 'm') toggleNav();
      if (e.key.toLowerCase() === 'f') toggleFullscreen();
      if (e.key === 'Escape') toggleNav(false);
    });
    let lastWheel = 0;
    window.addEventListener('wheel', (e) => {
      if (nav.classList.contains('open')) return;
      const now = Date.now();
      if (now - lastWheel < 520 || Math.abs(e.deltaY) < 24) return;
      show(current + (e.deltaY > 0 ? 1 : -1));
      lastWheel = now;
    }, { passive: true });
    document.getElementById('prevBtn').addEventListener('click', () => show(current - 1));
    document.getElementById('nextBtn').addEventListener('click', () => show(current + 1));
    document.getElementById('menuBtn').addEventListener('click', () => toggleNav());
    document.getElementById('fullBtn').addEventListener('click', toggleFullscreen);
    show(0);
  </script>
</body>
</html>
"""

    html_out = template.replace("__SLIDES__", slides_html).replace("__DATA__", data_json)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html_out, encoding="utf-8")
    ALIAS_OUTPUT.write_text(html_out, encoding="utf-8")
    print(OUTPUT)
    print(ALIAS_OUTPUT)


if __name__ == "__main__":
    main()
