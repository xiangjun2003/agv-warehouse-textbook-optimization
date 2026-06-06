from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "outputs/manual-20260601-agv-textbook/presentations/agv-textbook-deck"
DATA_PATH = WORKSPACE / "assets/deck-data.json"
VIEWPORT_CSS = ROOT / "outputs/frontend-slides-skill/viewport-base.css"
OUTPUT = ROOT / "deliverables/agv-warehouse-textbook-optimization.html"


def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    viewport_css = VIEWPORT_CSS.read_text(encoding="utf-8")
    r = data["results"]

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AGV 仓储优化：教材算法独立实验</title>
  <style>
    :root {
      --stage-bg: #070b10;
      --ink: #0b0f14;
      --ink-2: #161c24;
      --paper: #f6f2ea;
      --paper-2: #ece5d8;
      --white: #ffffff;
      --blue: #3ba7ff;
      --green: #68d391;
      --amber: #f6c85f;
      --coral: #ff6b5f;
      --muted: #65707d;
      --rule: #d8d0c4;
      --ease: cubic-bezier(.16, 1, .3, 1);
      --font: -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Noto Sans SC", Arial, sans-serif;
    }

__VIEWPORT_CSS__

    * { box-sizing: border-box; }
    body { font-family: var(--font); color: var(--ink); }
    .slide { padding: 76px 108px; background: var(--paper); }
    .slide.dark { background: #080d13; color: var(--white); }
    .kicker { display: flex; align-items: center; gap: 14px; font-size: 16px; font-weight: 800; color: #56616e; letter-spacing: .08em; text-transform: uppercase; }
    .kicker::before { content: ""; width: 10px; height: 10px; background: var(--blue); display: inline-block; }
    .dark .kicker { color: #aeb8c4; }
    h1, h2, h3, p { margin: 0; }
    h1 { margin-top: 48px; max-width: 1060px; font-size: 106px; line-height: .94; font-weight: 900; letter-spacing: 0; }
    h2 { margin-top: 28px; max-width: 1260px; font-size: 62px; line-height: 1.08; font-weight: 900; letter-spacing: 0; }
    h3 { font-size: 28px; font-weight: 900; }
    .subtitle { margin-top: 22px; max-width: 1200px; font-size: 27px; line-height: 1.42; color: var(--muted); }
    .dark .subtitle { color: #b8c2ce; }
    .rule { width: 560px; height: 4px; margin-top: 54px; background: var(--blue); }
    .folio { position: absolute; left: 108px; right: 108px; bottom: 48px; display: flex; justify-content: space-between; color: #80776a; font-size: 15px; }
    .dark .folio { color: #768292; }
    .folio::before { content: ""; position: absolute; left: 0; bottom: 34px; width: 460px; height: 1px; background: currentColor; opacity: .35; }
    .reveal { opacity: 0; transform: translateY(24px); transition: opacity .6s var(--ease), transform .6s var(--ease); }
    .visible .reveal { opacity: 1; transform: translateY(0); }
    .visible .reveal:nth-child(2) { transition-delay: .06s; }
    .visible .reveal:nth-child(3) { transition-delay: .12s; }
    .visible .reveal:nth-child(4) { transition-delay: .18s; }
    .metric-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 58px; margin-top: 70px; width: 1300px; }
    .metric .value { font-size: 56px; line-height: 1; font-weight: 900; }
    .metric .label { margin-top: 10px; font-size: 20px; font-weight: 900; }
    .metric .note { margin-top: 8px; font-size: 16px; color: #687382; line-height: 1.45; }
    .dark .metric .note { color: #94a1b2; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 72px; align-items: center; margin-top: 60px; }
    .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 38px; margin-top: 70px; }
    .panel { background: rgba(255,255,255,.78); border: 1px solid var(--rule); padding: 28px 32px; }
    .dark .panel { background: rgba(17,24,39,.92); border-color: #334155; color: #e8eef6; }
    .panel p { margin-top: 14px; color: #596675; font-size: 20px; line-height: 1.48; }
    .dark .panel p { color: #b9c2ce; }
    .accent-coral { border-top: 7px solid var(--coral); }
    .accent-blue { border-top: 7px solid var(--blue); }
    .accent-green { border-top: 7px solid var(--green); }
    .accent-amber { border-top: 7px solid var(--amber); }
    .callout { border-left: 6px solid var(--blue); }
    .lane { height: 106px; display: grid; grid-template-columns: 100px 300px 1fr 180px; align-items: center; padding: 0 34px; background: rgba(255,255,255,.72); border-top: 1px solid #dfd7ca; }
    .lane:nth-child(even) { background: var(--paper-2); }
    .lane .num { font-size: 28px; font-weight: 900; color: var(--blue); }
    .lane .name { font-size: 29px; font-weight: 900; }
    .lane .desc { font-size: 21px; color: #52606f; }
    .lane .tag { font-size: 18px; font-weight: 900; text-align: right; }
    .pipeline { display: grid; grid-template-columns: repeat(5, 1fr); gap: 34px; margin-top: 118px; }
    .step { position: relative; min-height: 150px; text-align: center; background: #fff; border: 1px solid var(--rule); padding: 34px 24px; }
    .step:not(:last-child)::after { content: ""; position: absolute; right: -31px; top: 72px; width: 26px; height: 4px; background: var(--blue); }
    .step p { margin-top: 14px; color: #617080; font-size: 17px; line-height: 1.4; }
    .map { position: relative; background: #151d27; border: 1px solid #334155; box-shadow: 0 18px 50px rgba(0,0,0,.18); }
    .cell { position: absolute; border: 1px solid rgba(0,0,0,.16); }
    .pallet-dot, .agv-dot { position: absolute; border-radius: 50%; }
    .selected-cell { position: absolute; border: 2px solid #fff; background: var(--coral); }
    .route-line { position: absolute; transform-origin: 0 0; height: 4px; }
    .bars { display: grid; gap: 17px; }
    .bar-row { display: grid; grid-template-columns: 120px 1fr 92px; gap: 18px; align-items: center; font-size: 17px; color: #5c6673; }
    .bar-track { height: 18px; background: #ddd6ca; position: relative; }
    .bar-fill { position: absolute; inset: 0 auto 0 0; }
    .load-chart { position: relative; width: 970px; height: 350px; border-bottom: 2px solid #bfb6a8; }
    .load-bar { position: absolute; bottom: 0; width: 32px; background: var(--blue); }
    .load-bar.low { background: var(--amber); }
    .equation { background: #fff; border: 1px solid var(--rule); padding: 32px 38px; font-size: 26px; line-height: 1.65; font-weight: 800; }
    .equation small { display: block; margin-top: 18px; color: #4b5563; font-size: 20px; line-height: 1.55; font-weight: 500; }
    .dark .equation { background: #111827; border-color: #334155; }
    .dark .equation small { color: #c5ced8; }
    .table { width: 100%; border-collapse: collapse; margin-top: 72px; font-size: 22px; }
    .table th { color: #9ca3af; font-size: 17px; text-align: left; padding-bottom: 18px; }
    .table td { border-top: 1px solid #2e3844; padding: 27px 20px 27px 0; }
    .deck-controls { color: #d5dce6; font: 600 13px/1 var(--font); background: rgba(8,13,19,.72); padding: 10px 16px; border: 1px solid rgba(255,255,255,.12); backdrop-filter: blur(12px); }
    .progress { position: fixed; left: 0; bottom: 0; height: 4px; width: 100%; background: rgba(255,255,255,.12); z-index: 1001; }
    .progress span { display: block; height: 100%; width: 0; background: var(--blue); transition: width .3s ease; }
  </style>
</head>
<body>
  <div class="deck-viewport">
    <main class="deck-stage" id="deckStage">
      <section class="slide dark active">
        <div class="kicker reveal">Textbook Optimization</div>
        <h1 class="reveal">AGV 仓储优化</h1>
        <p class="subtitle reveal">基于教材算法完成任务分配、动态分区与布局选址的独立实验。</p>
        <div class="rule reveal"></div>
        <div class="metric-row reveal" style="grid-template-columns:repeat(3,220px);">
          <div class="metric"><div class="value" style="color:var(--blue)">3</div><div class="label">优化问题</div><div class="note">分配 / 分区 / 布局</div></div>
          <div class="metric"><div class="value" style="color:var(--green)">140</div><div class="label">托盘</div><div class="note">含 SKU 与坐标</div></div>
          <div class="metric"><div class="value" style="color:var(--amber)">__TOTAL_TIME__</div><div class="label">端到端运行</div><div class="note">本机一次求解</div></div>
        </div>
        <div class="map reveal" data-map="base" style="position:absolute;right:175px;top:140px;width:460px;height:315px;"></div>
        <div class="panel callout reveal" style="position:absolute;right:175px;top:604px;width:430px;"><h3>项目主张</h3><p>从数据、建模到求解形成闭环，让每个结果都能追溯到模型和算法。</p></div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>01</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Experiment Background</div>
        <h2 class="reveal">我们研究的是自动化仓库里的 AGV 搬运决策。</h2>
        <p class="subtitle reveal">托盘在储位中分布，AGV 负责取货并送到拣选工位；距离、工位负载和空间间隔会共同影响吞吐。</p>
        <div class="grid-3 reveal">
          <div class="panel accent-coral"><h3>调度压力</h3><p>空闲 AGV 数量有限，需要快速决定取哪个托盘、送到哪个工位。</p></div>
          <div class="panel accent-blue"><h3>负载压力</h3><p>工位不能只接近处托盘，否则局部工位会过载、远端区域闲置。</p></div>
          <div class="panel accent-green"><h3>空间压力</h3><p>候选点太近会增加拥挤风险，需要保持布局分散。</p></div>
        </div>
        <div class="panel callout reveal" style="margin:72px auto 0;width:1180px;font-size:28px;font-weight:900;">课程实验的目标：把运营语言翻译成数学规划，再用教材算法得到可解释、可重复的计算结果。</div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>02</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Data Landscape</div>
        <h2 class="reveal">数据规模不大，但足够覆盖真实仓库的空间约束。</h2>
        <p class="subtitle reveal">地图、托盘、AGV 和工位来自原始 CSV；订单表存在，但当前实验聚焦空间调度与布局。</p>
        <div class="metric-row reveal">
          <div class="metric"><div class="value" style="color:var(--blue)">32×22</div><div class="label">仓库网格</div><div class="note">节点类型来自 map.csv</div></div>
          <div class="metric"><div class="value" style="color:var(--green)">140</div><div class="label">托盘</div><div class="note">总货量约 8478</div></div>
          <div class="metric"><div class="value" style="color:var(--coral)">50</div><div class="label">AGV 记录</div><div class="note">默认抽样 12 辆可用</div></div>
          <div class="metric"><div class="value" style="color:var(--amber)">18</div><div class="label">拣选工位</div><div class="note">每站最多接 3 个任务</div></div>
        </div>
        <div class="grid-2 reveal" style="align-items:start;margin-top:64px;">
          <div class="bars" id="nodeBars"></div>
          <div class="bars" id="qtyBars"></div>
        </div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>03</span></footer>
      </section>

      <section class="slide dark">
        <div class="kicker reveal">Warehouse Geometry</div>
        <h2 class="reveal">32×22 网格把“距离”变成可计算的运营成本。</h2>
        <p class="subtitle reveal">所有模型都使用曼哈顿距离：AGV 到托盘、托盘到工位、托盘之间的间隔。</p>
        <div class="map reveal" data-map="pallets" style="width:980px;height:500px;margin:62px 0 0 30px;"></div>
        <div class="panel callout reveal" style="position:absolute;right:165px;top:560px;width:420px;"><h3>可视化目的</h3><p>把节点类型、托盘和工位放在同一张空间证据图里，让实验设置先被看懂。</p></div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>04</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Experiment Purpose</div>
        <h2 class="reveal">三个实验分别对应仓库里的三种实际管理动作。</h2>
        <p class="subtitle reveal">不是单纯跑模型，而是回答调度、负载和布局三个层面的运营问题。</p>
        <div class="reveal" style="margin-top:78px;">
          <div class="lane"><div class="num">01</div><div class="name">AGV 任务分配</div><div class="desc">当一批小车空闲时，怎么派车取托盘并送到工位？</div><div class="tag" style="color:var(--coral)">减少行驶距离</div></div>
          <div class="lane"><div class="num">02</div><div class="name">动态分区</div><div class="desc">托盘货量如何分摊给工位，既近又不过度偏载？</div><div class="tag" style="color:var(--blue)">平衡工位负载</div></div>
          <div class="lane"><div class="num">03</div><div class="name">仓库布局</div><div class="desc">从候选托盘位置中选 10 个，如何避免过近拥挤？</div><div class="tag" style="color:var(--green)">保证空间分散</div></div>
        </div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>05</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Automated Modeling</div>
        <h2 class="reveal">建模已自动化：CSV 进入脚本，矩阵和约束自动生成。</h2>
        <p class="subtitle reveal">代码从数据规模直接构造目标函数、等式和不等式；换数据后重新生成模型。</p>
        <div class="pipeline reveal">
          <div class="step"><h3>输入数据</h3><p>map / pallets / bots</p></div>
          <div class="step"><h3>空间计算</h3><p>曼哈顿距离矩阵</p></div>
          <div class="step"><h3>模型构造</h3><p>变量、约束、目标</p></div>
          <div class="step"><h3>教材算法</h3><p>内点法 / 罚函数 / BB</p></div>
          <div class="step"><h3>结果输出</h3><p>CSV + 可视化</p></div>
        </div>
        <div class="panel callout reveal" style="margin:90px auto 0;width:1260px;font-size:24px;">自动化建模的价值：换一批 AGV、换一个工位容量或托盘数量时，脚本重新生成模型，而不是重写数学规划。</div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>06</span></footer>
      </section>

      <section class="slide dark">
        <div class="kicker reveal">Problem 01 · AGV Assignment</div>
        <h2 class="reveal">问题一：哪辆 AGV 去取哪个托盘，再送到哪个工位？</h2>
        <p class="subtitle reveal">这对应仓库某一时刻的派车决策；可视化中红线是 AGV 到托盘，黄线是托盘到工位。</p>
        <div class="map reveal" data-map="routes" style="width:760px;height:510px;margin:58px 0 0 120px;"></div>
        <div class="metric reveal" style="position:absolute;left:1140px;top:540px;"><div class="value" style="color:var(--coral)">12</div><div class="label">可用 AGV</div><div class="note">固定 seed 后可重复</div></div>
        <div class="metric reveal" style="position:absolute;left:1430px;top:540px;"><div class="value" style="color:var(--amber)">__AGV_COST__</div><div class="label">整数成本</div><div class="note">满足工位容量</div></div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>07</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Model 01 · AGV Assignment</div>
        <h2 class="reveal">AGV 分配：把“派车-取货-送站”写成一个线性规划。</h2>
        <p class="subtitle reveal">一次任务链拆成两个距离成本：AGV 到托盘、托盘到拣选工位。</p>
        <div class="grid-2 reveal">
          <div>
            <div class="panel accent-coral"><h3>变量</h3><p>xᵢⱼ 表示 AGV i 是否服务托盘 j；yⱼₖ 表示托盘 j 是否送到工位 k。</p></div>
            <div class="panel accent-blue" style="margin-top:28px;"><h3>约束</h3><p>每辆 AGV 至多接一个任务；托盘选择与送站一致；每个工位不能超过容量。</p></div>
          </div>
          <div class="equation">
            min Σ d(AP)ᵢⱼ xᵢⱼ + Σ d(PW)ⱼₖ yⱼₖ
            <small>s.t. Σⱼxᵢⱼ≤1；Σᵢxᵢⱼ=Σₖyⱼₖ；Σⱼyⱼₖ≤capₖ；x,y≥0。求解 LP 后按最小增量成本恢复整数任务。</small>
          </div>
        </div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>08</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Problem 02 · Dynamic Partition</div>
        <h2 class="reveal">问题二：托盘货量如何分给工位，既近又不过度偏载？</h2>
        <p class="subtitle reveal">每个托盘货量全部分配；每个工位至少承担平均负载的 60%；目标是距离加权成本最小。</p>
        <div class="grid-2 reveal">
          <div><div style="font-size:18px;color:#5c6673;margin-bottom:16px;">工位负载</div><div class="load-chart" id="loadChart"></div></div>
          <div>
            <div class="metric"><div class="value" style="color:var(--blue)">__DYN_OBJ__</div><div class="label">距离成本</div><div class="note">货量 × 曼哈顿距离</div></div>
            <div class="metric" style="margin-top:70px;"><div class="value" style="color:var(--green)">__DYN_ITER__</div><div class="label">内点迭代</div><div class="note">残差与 gap 均达标</div></div>
            <div class="panel callout" style="margin-top:70px;"><p>连续 LP 的解直接给出工位负载结构，能观察平衡约束是否生效。</p></div>
          </div>
        </div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>09</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Model 02 · Dynamic Partition</div>
        <h2 class="reveal">动态分区：把托盘货量分配给工位，同时避免工位太空。</h2>
        <p class="subtitle reveal">它允许货量连续分摊，因此天然是线性规划。</p>
        <div class="grid-2 reveal">
          <div class="panel accent-blue"><h3>变量 zⱼₖ</h3><p>托盘 j 的多少货量分配给工位 k。距离越远，分配成本越高；负载下限防止只让近处工位工作。</p></div>
          <div class="equation">
            min Σ dⱼₖ zⱼₖ
            <small>s.t. Σₖzⱼₖ=qⱼ；Σⱼzⱼₖ≥0.6·Q/K；zⱼₖ≥0。加入松弛变量后转成标准形式 LP。</small>
          </div>
        </div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>10</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Problem 03 · Warehouse Layout</div>
        <h2 class="reveal">问题三：从候选位置中选 10 个，并保持足够空间间隔。</h2>
        <p class="subtitle reveal">这是离散可行性问题；目标是找到两两距离大于 6 的一组分散候选点。</p>
        <div class="map reveal" data-map="selected" style="width:820px;height:480px;margin:62px 0 0 250px;"></div>
        <div class="metric reveal" style="position:absolute;left:1320px;top:420px;"><div class="value" style="color:var(--coral)">10</div><div class="label">选中位置</div><div class="note">来自 140 个托盘候选</div></div>
        <div class="metric reveal" style="position:absolute;left:1320px;top:580px;"><div class="value" style="color:var(--green)">__MIN_DIST__</div><div class="label">最小间距</div><div class="note">满足要求 > 6</div></div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>11</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Model 03 · Warehouse Layout</div>
        <h2 class="reveal">布局选址：难点在 0/1 选择和两两距离冲突。</h2>
        <p class="subtitle reveal">若候选点 i 与 j 的曼哈顿距离 ≤ 6，就加入冲突集合 E，二者不能同时选。</p>
        <div class="grid-2 reveal">
          <div>
            <div class="panel accent-green"><h3>变量</h3><p>wⱼ∈{0,1} 表示候选托盘位置 j 是否被选中；实验要求 Σwⱼ=10。</p></div>
            <div class="panel accent-coral" style="margin-top:28px;"><h3>冲突</h3><p>对每一条冲突边 (i,j)∈E，添加 wᵢ+wⱼ≤1，防止近距离点同时入选。</p></div>
          </div>
          <div class="equation">
            find w
            <small>s.t. Σⱼwⱼ=10；wᵢ+wⱼ≤1, (i,j)∈E；wⱼ∈{0,1}。先做连续松弛，再离散修复。</small>
          </div>
        </div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>12</span></footer>
      </section>

      <section class="slide dark">
        <div class="kicker reveal">Algorithm · Primal-Dual LP</div>
        <h2 class="reveal">原始-对偶内点法：沿中心路径同时修正可行性和最优性。</h2>
        <p class="subtitle reveal">用于 AGV 分配和动态分区，因为二者都能整理为标准形式线性规划。</p>
        <div class="grid-2 reveal">
          <div class="equation">min cᵀx<br/>s.t. Ax=b, x≥0<small>对偶条件：Aᵀy+s=c, s≥0；互补条件：XSe=μe。</small></div>
          <div class="panel callout"><h3>每轮迭代</h3><p>计算原始残差、对偶残差和 gap；解 KKT 牛顿方程；选择保持 x,s>0 的步长；缩小 μ 直到收敛。</p></div>
        </div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>13</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Algorithm · Quadratic Penalty</div>
        <h2 class="reveal">二次罚函数法：把约束变成逐渐加重的惩罚。</h2>
        <p class="subtitle reveal">用于布局选址的连续松弛：先允许 w 在 [0,1] 内变化，再通过罚项逼近约束。</p>
        <div class="equation reveal" style="text-align:center;margin-top:72px;">Φρ(w)=f(w)+ρ/2·||h(w)||²+ρ/2·||max(0,g(w))||²</div>
        <div class="grid-3 reveal">
          <div class="panel accent-blue"><h3>h(w)=Σw-10</h3><p>保证选中数量为 10。</p></div>
          <div class="panel accent-coral"><h3>gᵢⱼ(w)=wᵢ+wⱼ-1</h3><p>惩罚冲突位置同时被选。</p></div>
          <div class="panel accent-green"><h3>ρ 逐步增大</h3><p>先找方向，再越来越强调可行性。</p></div>
        </div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>14</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Algorithm · Projected BB Gradient</div>
        <h2 class="reveal">投影 BB 梯度法：用谱步长加速盒约束子问题。</h2>
        <p class="subtitle reveal">它负责求解罚函数内层问题，并配合离散修复把连续解变回可行的 0/1 选择。</p>
        <div class="grid-2 reveal">
          <div class="equation">w⁺=P[0,1](w-α∇Φρ(w))<small>BB 步长：α₁=sᵀs/sᵀy，α₂=sᵀy/yᵀy。投影保证每轮仍在盒约束内。</small></div>
          <div class="panel accent-green"><h3>离散修复</h3><p>按连续解大小排序；依次选择不冲突的位置；若数量不足再贪心补点；最后校验数量和最小距离。</p></div>
        </div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>15</span></footer>
      </section>

      <section class="slide dark">
        <div class="kicker reveal">Results & Analysis</div>
        <h2 class="reveal">当前规模下，自实现算法在一秒内完成三项任务。</h2>
        <p class="subtitle reveal">重点不只是速度，而是能解释模型、算法和结果之间的关系。</p>
        <table class="table reveal">
          <thead><tr><th>问题</th><th>方法</th><th>核心结果</th><th>迭代</th><th>耗时</th><th>结论</th></tr></thead>
          <tbody>
            <tr><td><strong>动态分区</strong></td><td>LP</td><td style="color:var(--blue)">__DYN_OBJ__</td><td>__DYN_ITER__ 次</td><td>__DYN_TIME__</td><td>工位负载满足下限</td></tr>
            <tr><td><strong>AGV 分配</strong></td><td>LP + 恢复</td><td style="color:var(--amber)">__AGV_COST__</td><td>__AGV_ITER__ 次</td><td>__AGV_TIME__</td><td>满足任务和工位容量</td></tr>
            <tr><td><strong>仓库布局</strong></td><td>罚函数 + BB</td><td style="color:var(--green)">10 点</td><td>__LAYOUT_ITER__ 轮</td><td>__LAYOUT_TIME__</td><td>最小间距 __MIN_DIST__ > 6</td></tr>
          </tbody>
        </table>
        <div class="metric reveal" style="position:absolute;left:120px;bottom:120px;"><div class="value" style="color:var(--blue)">__TOTAL_TIME__</div><div class="label">三项求解合计</div><div class="note">不含演示稿生成</div></div>
        <div class="panel callout reveal" style="position:absolute;right:170px;bottom:122px;width:560px;">课程项目定位：把实际含义、数学模型、教材算法和结果解释连成闭环。</div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>16</span></footer>
      </section>

      <section class="slide">
        <div class="kicker reveal">Closing</div>
        <h2 class="reveal">最终交付不是三段代码，而是一套可重复的优化工作流。</h2>
        <div class="rule reveal"></div>
        <div class="grid-2 reveal" style="align-items:start;margin-top:74px;">
          <div class="panel accent-blue"><h3>已经完成</h3><p>环境、数据读取、自动建模、教材算法求解、CSV 输出、PPT 与 HTML 演示稿。</p></div>
          <div class="panel accent-coral"><h3>后续扩展</h3><p>把订单表纳入需求约束；加入 AGV 时间窗、路径冲突和多批次滚动调度。</p></div>
        </div>
        <footer class="folio"><span>本地 CSV + 自实现求解脚本</span><span>17</span></footer>
      </section>
    </main>
  </div>
  <div class="deck-controls" id="deckControls">1 / 17 · ← → 翻页</div>
  <div class="progress"><span id="progressBar"></span></div>

  <script>
    const deckData = __DECK_DATA__;
    const typeColors = { "1":"#3a4450", "2":"#68d391", "3":"#f6c85f", "4":"#111827", "5":"#3ba7ff", "6":"#f2a0c5", "7":"#ff6b5f", "8":"#77e7f7" };

    function add(parent, cls, style) {
      const el = document.createElement('div');
      if (cls) el.className = cls;
      if (style) Object.assign(el.style, style);
      parent.appendChild(el);
      return el;
    }

    function renderMap(el, mode) {
      el.innerHTML = '';
      const map = deckData.input.map;
      const cell = Math.min(el.clientWidth / map.ncols, el.clientHeight / map.nrows);
      const ox = (el.clientWidth - cell * map.ncols) / 2;
      const oy = (el.clientHeight - cell * map.nrows) / 2;
      map.nodes.forEach(n => {
        add(el, 'cell', {
          left: `${ox + n.x * cell}px`,
          top: `${oy + (map.nrows - 1 - n.y) * cell}px`,
          width: `${Math.max(2, cell - 1)}px`,
          height: `${Math.max(2, cell - 1)}px`,
          background: typeColors[n.type] || '#3ba7ff'
        });
      });
      if (mode === 'pallets') {
        deckData.input.pallets.positions.forEach(p => add(el, 'pallet-dot', {
          left: `${ox + p.x * cell + cell * .25}px`,
          top: `${oy + (map.nrows - 1 - p.y) * cell + cell * .25}px`,
          width: `${cell * .5}px`,
          height: `${cell * .5}px`,
          background: '#f6f2ea'
        }));
      }
      if (mode === 'selected') {
        deckData.results.layout.selected.forEach(p => add(el, 'selected-cell', {
          left: `${ox + p.x * cell + cell * .08}px`,
          top: `${oy + (map.nrows - 1 - p.y) * cell + cell * .08}px`,
          width: `${cell * .84}px`,
          height: `${cell * .84}px`
        }));
      }
      if (mode === 'routes') {
        deckData.results.agv.assignments.slice(0, 8).forEach(r => {
          drawRoute(el, ox, oy, cell, map.nrows, r.agv_xy, r.pallet_xy, '#ff6b5f');
          drawRoute(el, ox, oy, cell, map.nrows, r.pallet_xy, r.workstation_xy, '#f6c85f');
          add(el, 'agv-dot', {
            left: `${ox + r.agv_xy[0] * cell + cell * .16}px`,
            top: `${oy + (map.nrows - 1 - r.agv_xy[1]) * cell + cell * .16}px`,
            width: `${cell * .68}px`,
            height: `${cell * .68}px`,
            background: '#ff6b5f'
          });
        });
      }
    }

    function drawRoute(el, ox, oy, cell, nrows, a, b, color) {
      const ax = ox + a[0] * cell + cell / 2;
      const ay = oy + (nrows - 1 - a[1]) * cell + cell / 2;
      const bx = ox + b[0] * cell + cell / 2;
      const by = oy + (nrows - 1 - b[1]) * cell + cell / 2;
      add(el, 'route-line', { left: `${Math.min(ax, bx)}px`, top: `${ay - 2}px`, width: `${Math.abs(bx - ax) + 4}px`, background: color });
      add(el, 'route-line', { left: `${bx - 2}px`, top: `${Math.min(ay, by)}px`, width: '4px', height: `${Math.abs(by - ay) + 4}px`, background: color });
    }

    function renderBars() {
      const nodeBars = document.getElementById('nodeBars');
      if (nodeBars) {
        const max = Math.max(...deckData.input.map.counts.map(d => d.count));
        deckData.input.map.counts.forEach(d => {
          const row = add(nodeBars, 'bar-row');
          row.innerHTML = `<span>${d.label}</span><div class="bar-track"><div class="bar-fill" style="width:${d.count / max * 100}%;background:${typeColors[d.type]}"></div></div><span>${d.count}</span>`;
        });
      }
      const qtyBars = document.getElementById('qtyBars');
      if (qtyBars) {
        const max = Math.max(...deckData.input.pallets.quantity_bins.map(d => d.count));
        deckData.input.pallets.quantity_bins.forEach(d => {
          const row = add(qtyBars, 'bar-row');
          row.innerHTML = `<span>${d.label}</span><div class="bar-track"><div class="bar-fill" style="width:${d.count / max * 100}%;background:#68d391"></div></div><span>${d.count} 托盘</span>`;
        });
      }
      const loadChart = document.getElementById('loadChart');
      if (loadChart) {
        const loads = deckData.results.dynamic.loads;
        const max = Math.max(...loads.map(d => d.load));
        loads.forEach((d, i) => add(loadChart, `load-bar ${d.load < 300 ? 'low' : ''}`, {
          left: `${i * 52}px`,
          height: `${d.load / max * 330}px`
        }));
      }
    }

    class SlidePresentation {
      constructor() {
        this.slides = [...document.querySelectorAll('.slide')];
        this.currentSlide = 0;
        this.stage = document.getElementById('deckStage');
        this.controls = document.getElementById('deckControls');
        this.progress = document.getElementById('progressBar');
        this.setupScale();
        this.setupNavigation();
        this.showSlide(0);
      }
      setupScale() {
        const scale = () => {
          const factor = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
          this.stage.style.transform = `translate(${(window.innerWidth - 1920 * factor) / 2}px, ${(window.innerHeight - 1080 * factor) / 2}px) scale(${factor})`;
        };
        scale();
        window.addEventListener('resize', scale);
      }
      setupNavigation() {
        window.addEventListener('keydown', e => {
          if (['ArrowRight', 'PageDown', ' '].includes(e.key)) this.showSlide(this.currentSlide + 1);
          if (['ArrowLeft', 'PageUp'].includes(e.key)) this.showSlide(this.currentSlide - 1);
          if (e.key === 'Home') this.showSlide(0);
          if (e.key === 'End') this.showSlide(this.slides.length - 1);
        });
        let lastWheel = 0;
        window.addEventListener('wheel', e => {
          const now = Date.now();
          if (now - lastWheel < 550 || Math.abs(e.deltaY) < 30) return;
          this.showSlide(this.currentSlide + (e.deltaY > 0 ? 1 : -1));
          lastWheel = now;
        }, { passive: true });
      }
      showSlide(index) {
        this.currentSlide = Math.max(0, Math.min(index, this.slides.length - 1));
        this.slides.forEach((slide, i) => {
          slide.classList.toggle('active', i === this.currentSlide);
          slide.classList.toggle('visible', i === this.currentSlide);
        });
        this.controls.textContent = `${this.currentSlide + 1} / ${this.slides.length} · ← → 翻页`;
        this.progress.style.width = `${(this.currentSlide + 1) / this.slides.length * 100}%`;
      }
    }

    document.querySelectorAll('[data-map]').forEach(el => renderMap(el, el.dataset.map));
    renderBars();
    new SlidePresentation();
  </script>
</body>
</html>
"""

    replacements = {
        "__VIEWPORT_CSS__": viewport_css,
        "__DECK_DATA__": json.dumps(data, ensure_ascii=False),
        "__TOTAL_TIME__": f"{r['total_time']:.2f}s",
        "__DYN_TIME__": f"{r['dynamic']['time']:.3f}s",
        "__AGV_TIME__": f"{r['agv']['time']:.3f}s",
        "__LAYOUT_TIME__": f"{r['layout']['time']:.3f}s",
        "__DYN_ITER__": str(r["dynamic"]["iterations"]),
        "__AGV_ITER__": str(r["agv"]["iterations"]),
        "__LAYOUT_ITER__": str(r["layout"]["outer_iterations"]),
        "__DYN_OBJ__": f"{r['dynamic']['objective']:.1f}",
        "__AGV_COST__": f"{r['agv']['integer_cost']:.0f}",
        "__MIN_DIST__": str(r["layout"]["min_pair_distance"]),
    }
    for key, value in replacements.items():
        html = html.replace(key, value)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
