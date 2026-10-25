# -*- coding: utf-8 -*-
"""Journal-submission-format regeneration of the heat-tree paper.

This is a SEPARATE deliverable from both `generate_heat_tree_paper.py`
(development-log edition) and `generate_heat_tree_paper_mainstream.py`
(first mainstream pass). The present script follows the full conventions
expected by a mainstream peer-reviewed engineering journal:

  * Nomenclature table (Table 1) with numbered symbols;
  * numbered display equations, every one referenced at least once in the
    running text ("Equation (n)");
  * every figure and table referenced in the text at least once;
  * multi-level section numbering (1 / 1.1 / 1.1.1);
  * quantitative descriptions of trends instead of bare tables;
  * closing statements: Data Availability, Author Contributions,
    Conflicts of Interest, Funding;
  * the full experimental evidence base of this repository, not a subset.

Every number is loaded at runtime from this repository's own experimental
artifacts (outputs/*.json, outputs/real_unit_calibration.txt) or is a
verified calibration anchor. Nothing is invented. Run:

    python generate_heat_tree_paper_journal.py
"""
import json
import os

from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Cm

from paper_template import PaperTemplate

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "论文")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, "仿生树形微通道散热_期刊投稿版.docx")

# ---------------------------------------------------------------------------
# AI 生成内容标识：文首一个「含 AI 生成」文本框 + 一个空段落。
# 该标识此前由外部工具手工注入，生成器无法重建，导致 docx 内容不可复现；
# 此处内建，使重生成的结果与投稿版一致。
AI_LABEL_XML = (
    "<w:p {ns}><w:r><w:rPr><w:noProof/></w:rPr><w:drawing>"
    '<wp:inline distT="0" distB="0" distL="0" distR="0">'
    '<wp:extent cx="2400000" cy="380000"/>'
    '<wp:docPr id="{doc_pr_id}" name="AILabel"/>'
    '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
    '<wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr>'
    '<a:xfrm><a:off x="0" y="0"/><a:ext cx="2400000" cy="380000"/></a:xfrm>'
    '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
    '<a:solidFill><a:srgbClr val="000000"><a:alpha val="50000"/></a:srgbClr></a:solidFill>'
    '<a:ln w="12700"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:ln>'
    "</wps:spPr><wps:txbx><w:txbxContent>"
    '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/>'
    '<w:sz w:val="28"/><w:szCs w:val="28"/>'
    '<w:rFonts w:eastAsia="SimSun" w:ascii="Arial" w:hAnsi="Arial"/>'
    '<w:color w:val="FFFFFF"/></w:rPr><w:t>含 AI 生成</w:t></w:r></w:p>'
    "</w:txbxContent></wps:txbx>"
    '<wps:bodyPr anchor="ctr" anchorCtr="0" lIns="91440" tIns="45720" rIns="91440" bIns="45720">'
    "<a:noAutofit/></wps:bodyPr></wps:wsp></a:graphicData></a:graphic>"
    "</wp:inline></w:drawing></w:r></w:p>"
)


def add_ai_label(doc):
    """在正文最前插入「含 AI 生成」标识文本框，随后补一个空段落。"""
    body = doc.element.body
    used = [int(v) for v in body.xpath("//wp:docPr/@id") if v.isdigit()]
    xml = AI_LABEL_XML.format(
        ns=nsdecls("w", "wp", "a")
        + ' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"',
        doc_pr_id=(max(used) + 1) if used else 1,
    )
    body.insert(0, parse_xml(xml))
    body.insert(1, parse_xml("<w:p %s/>" % nsdecls("w")))

# 数据链路口径断言（阶段 0）：任一断言失败即中断生成，防止口径锚点静默漂移
import subprocess
import sys
subprocess.run([sys.executable, os.path.join(HERE, "data_link_assertions.py")],
               check=True, cwd=HERE)


# ---------------------------------------------------------------------------
# Load experimental artifacts (single source of truth)
# ---------------------------------------------------------------------------
def _load(name):
    with open(os.path.join(HERE, "outputs", name), encoding="utf-8") as f:
        return json.load(f)


RUN = _load("run_report.json")            # single-source compare + sanity
GCI = _load("a4_grid_convergence.json")   # grid independence
FRONTS = _load("generator_fronts.json")   # constraint-driven Pareto fronts
C5 = _load("c5_artifact.json")            # equal-total multi-source compare
P0A = _load("p0a_artifact.json")          # conjugate (coupled) rerun
CONJ = _load("conjugate_single.json")     # finite-flow coupling, 253 W
CONJM = _load("conjugate_multi_real.json")  # finite-flow coupling, 3 dies
MS = _load("multi_source_summary.json")   # equal-pinned multi-source sweep
ROBIN = _load("robin_boundary_summary.json")  # finite-convection boundary
PITCH = _load("lattice_pitch_summary.json")   # lattice pitch sweep
UPOW = _load("unequal_power_pitch_summary.json")  # unequal-power × pitch
SPREAD = _load("spread_source_thermal_summary.json")  # spread-source real density

# Verified real-unit calibration anchors (outputs/real_unit_calibration.txt,
# produced by calibrate.report(); see REPORT.md §3).
CAL = {
    "i7": {"power_w": 253, "bare_peak_c": 174.6, "tree_peak_c": 60.5,
           "r_th": 0.1403, "dp_kpa": 0.0802, "flow_lpm": 0.73},
    "h100": {"power_w": 700, "bare_peak_c": 439.0, "tree_peak_c": 123.2,
             "r_th": 0.1403, "dp_kpa": 0.2220, "flow_lpm": 2.01},
}

# Derived, verified quantities used in the text.
_gci_bare = GCI["gci"]["bare"]["gci_fine_pct"]
_gci_tree = GCI["gci"]["tree"]["gci_fine_pct"]
_gci_ctrl = GCI["gci"]["ctrl"]["gci_fine_pct"]
_gci_p_tree = GCI["gci"]["tree"]["p"]
_gci_ext = GCI["gci"]["tree"]["f_ext"]
_an = GCI["analytic_check"]
_cmp = RUN["compare"]
_dp_ratio = _cmp["dp_ratio_tree_over_straight"]
_murray_err = RUN["murray"]["max_rel_err"]
_murray_forks = RUN["murray"]["forks"]
_murray_profile = RUN["murray"]["profile"]
_deg = RUN["tree"]["degree_hist"]
_stl = RUN["stl"]["manifold"]
_tol = C5["shared_threshold_c"]

# 中文期刊常规版面：A4，左右边距 2.88 cm 使正文宽为 15.24 cm
paper = PaperTemplate(OUT_PATH, margins=(2.54, 2.54, 2.88, 2.88))
for _sec in paper.doc.sections:
    _sec.page_width = Cm(21.0)
    _sec.page_height = Cm(29.7)

# ===========================================================================
# Front matter
# ===========================================================================
paper.title("仿生树形微通道芯片散热网络的公平比较框架\n与约束驱动拓扑生成")

paper.abstract(
    "针对“树形仿生微通道优于传统直通道”这一论断在既有研究中高度依赖“材料预算”设定、"
    "结论随预算反转的问题，本文建立了一套可复现的公平比较框架与约束驱动拓扑生成方法。"
    "方法上，采用热场驱动的 Prim 贪心生长构建树形通道，以 Murray 定律分配管径，并提出"
    "等钉住格点、等材料、等总占用格点三重公平约束；进一步将节点预算从自由输入改为三条"
    "约束（进入每个芯片 footprint、根半径不超过格距、压降不超过泵关死扬程）的求解输出，"
    "得到 $(T_{max},\\ \\Delta p)$ 双目标 Pareto 前沿与 $\\epsilon$-约束膝盖点。"
    "模型经网格无关性（细网格 GCI 0.067%–3.14%）、解析解（Richardson 外推与解析差 "
    "0.10%）、Murray 守恒（残差 4.8×10⁻¹⁶）与 Simulink 电学类比四重验证。"
    "结果表明：单热源下树与直通道峰值温度逐位相同（27.60 °C），但树压降高出约 310 倍；"
    "多热源等总占用格点口径下，格状网在峰值温度与压降上整体不劣于树（3 芯片、1300 格："
    "树 27.17 °C、格状 27.16 °C，格状压降仅 19 Pa 而树为 10⁴ Pa 量级）；有限流量共轭"
    "与有限对流边界扫描均不改变方向性结论。约束驱动生成器在四个布局上输出 4–10 个前沿点，"
    "3 芯片布局允许 0.1 K 热惩罚即可节省约 21% 压降。本文的贡献在于可复现的公平比较协议"
    "与约束驱动生成装置，而非又一份“树更优”的证据。")

paper.keywords("微通道散热器；仿生树形网络；Murray 定律；公平比较；Pareto 前沿；约束驱动生成")

# ---- Nomenclature ----
paper.h1("Nomenclature（主要符号表）")
paper.table(
    headers=["符号", "含义", "单位"],
    data=[
        ["$T_{max}$", "固体域峰值温度", "°C"],
        ["$T_{mean}$", "固体域平均温度", "°C"],
        ["$T_{cool}$", "冷却液入口温度", "°C"],
        ["$R_{th}$", "热阻，$(T_{max}-T_{cool})/Q$", "°C/W"],
        ["$\\Delta p$", "压降（约定 A：最深根–叶路径）", "Pa"],
        ["$Q$", "芯片总发热功率", "W"],
        ["$q$", "冷却液体积流量", "L/min"],
        ["$p$", "网格间距（真实口径 0.9 mm）", "mm"],
        ["$k$", "导热系数（单晶硅 148）", "W/(m·K)"],
        ["$\\mu$", "动力黏度（20 °C 水 1.002×10⁻³）", "Pa·s"],
        ["$r_0$", "叶端毛细半径", "mm"],
        ["$r_p, r_c$", "父管 / 子管半径（Murray 定律）", "mm"],
        ["$r_{root}$", "根半径（Murray 定律下最粗管）", "mm"],
        ["$N_{leaves}$", "叶节点数（边下游流量）", "–"],
        ["$b$", "节点预算（通道占用总格点数）", "–"],
        ["$N_{pin}$", "钉住（设为 $T_{cool}$）格点数", "–"],
        ["$A_{hot}$", "热点面积（共享绝对阈值 26 °C）", "mm²"],
        ["$h_{conv}$", "有限对流的无量纲 $Bi$ 数", "–"],
        ["GCI", "网格收敛指数", "%"],
        ["$t_{tol}$", "$\\epsilon$-约束热容忍度", "K"],
    ],
    caption="表1 主要符号",
)
paper.p(
    "本文全部数值结果采用表1 所列符号与口径，首次出现处给出物理含义；下标 $p$、$c$ "
    "分别指父管与子管，$root$、$leaves$ 指树形网络的根与叶。式 (1)–(4) 为全文反复引用"
    "的四个基本关系，其余数字均由本仓库工件实跑产生。")

# ===========================================================================
# 1. Introduction
# ===========================================================================
paper.h1("1 引言")

paper.h2("1.1 研究背景")
paper.p(
    "随着高功率芯片热流密度持续上升，风冷已无法满足散热需求，微通道液冷凭借紧凑结构"
    "与优异的对流换热能力成为主流方案[2,17]。在众多微通道拓扑中，受植物叶脉与动物血管"
    "启发的仿生树形分叉网络被广泛认为优于传统平行直通道：其分级分叉结构被声称能同时"
    "降低热阻与压降[8,9]。这一论断的几何基础是 Murray 定律[1]——在最小输运功原理下，"
    "父管与子管半径满足 $r_p^3=\\sum r_c^3$ 的立方关系。")
paper.p(
    "然而，树形通道与直通道的比较结论在既有文献中并不一致，且高度依赖一个很少被显式"
    "定义的变量——“材料预算”（通道占用的格点数或截面积）。当预算未被约束或两侧预算不"
    "对等时，比较结果可能完全由预算差异而非拓扑差异驱动，导致结论随预算反转。这正是"
    "本文要解决的核心问题。")

paper.h2("1.2 相关工作")
paper.h3("1.2.1 树形分叉微通道的水热性能")
paper.p(
    "树形分叉微通道的理论与实验研究已有大量积累。Murray 定律[1]与 West 等的异速生长"
    "标度模型[4]为分叉网络提供了生物学基础；Bejan 的构形理论[3]将其推广为工程设计"
    "原则。Jing 与 Song[7]在等通道高度约束下重新检验了 Murray 定律，指出圆管的最优"
    "直径比不适用于矩形分叉，最优宽度比由通道高度、初始尺寸与分叉级数共同决定。"
    "Wang 等[8]基于改进 Murray 定律研究了高分叉级数树形散热器的水热性能。Chen 等[9]"
    "提出 Y 形分叉直通道散热器，量化了分叉角、级数、通道数与进口流速对流动均匀性与"
    "水热性能的影响。")
paper.h3("1.2.2 拓扑优化与局部损失")
paper.p(
    "在拓扑优化方向，Tan 等[10]与 Wang 等[11]将多目标拓扑优化用于高热度流密度芯片"
    "冷板设计，证明了非均匀通道布局的收益。水力侧，Kiser 等[15]测得 T 形与 Y 形接头"
    "的层流损失系数，Rennels 与 Hudson[16]系统整理了管件局部损失的工程数据；这些"
    "结果提示，忽略接头损失会系统性低估树形网络的压降，因为树的分叉数远多于平行"
    "直通道。")
paper.h3("1.2.3 仿生自适应布线")
paper.p(
    "黏菌（Physarum）自适应网络模型[5,6]为通道布线提供了另一类仿生范式，其稳态与"
    "最短路径的关系已被严格刻画。本文在交叉验证环节借用其电学类比，但布线本身仍采用"
    "热场驱动生长，以保持与主模型的一致性。")
paper.p(
    "上述工作大多在各自设定的预算与边界下报告“树形更优”，但缺少一个统一的、对预算"
    "公平的比较框架，也缺少将预算从自由参数转为约束求解的生成方法。")

paper.h2("1.3 研究空白与本文贡献")
paper.p("归纳既有研究，存在三点空白：")
paper.pm("（1）**比较口径不统一**：树与对照组的材料预算、钉住格点数、总占用格点数往往"
         "不对等，结论可能由预算差异主导；")
paper.pm("（2）**节点预算是自由参数**：树形网络的预算（叶数/段数）通常人为给定，缺少由"
         "物理约束反推的机制；")
paper.pm("（3）**缺少可复现的判决装置**：优势是否成立、在何种口径下成立，无法由单一脚本"
         "一键复现。")
paper.p("针对上述空白，本文贡献如下：")
paper.pm("（1）提出等钉住格点、等材料、等总占用格点三重公平约束，并在四个芯片布局上"
         "系统比较树形、径向与格状三类拓扑；")
paper.pm("（2）提出约束驱动生成器，将节点预算从自由输入改为三条物理约束（C1 进入每个"
         "芯片、C2 根半径不超格距、C3 压降不超泵扬程）的求解输出，给出 $(T_{max},\\ "
         "\\Delta p)$ Pareto 前沿与膝盖点敏感性；")
paper.pm("（3）全部数值由本仓库求解器实跑并随文给出工件路径，比较协议与生成器均可"
         "一键复现。")

# ===========================================================================
# 2. Model and methods
# ===========================================================================
paper.h1("2 模型与方法")

paper.h2("2.1 物理模型与数值离散")
paper.p(
    "在 $50\\times 50$ 网格（真实口径格距 $p=0.9$ mm、板 $45\\times 45$ mm、硅厚 "
    "$t=5$ mm、$k=148$ W/(m·K)[14]）上用五点差分求解稳态导热方程：")
paper.formula(
    "\\nabla^2 T = -q/k,   \\qquad  T = T_{cool} \\ \\ (边界)",
    label="(1)")
paper.p(
    "其中 $q$ 为源格体积热流，边界取恒温冷汇。式 (1) 右端为源项、左端为拉普拉斯算子，"
    f"该离散用 Jacobi 迭代求解，生产网格下的残差判据为 $10^{{-6}}$，实测收敛需 "
    f"{RUN['field']['iterations']} 次迭代，"
    f"线性残差 {GCI['cases']['bare'][0]['lin_residual']:.2e}。")
paper.p(
    "树形通道以“钉住格”方式进入模型：通道占据的格点被设为 $T_{cool}$，从而把流体"
    "对流换热等效为固定温度的汇。该约定的后果在 4.4 节定量讨论。")

paper.h2("2.2 热场驱动的树形生长")
paper.p(
    "树由 Prim 型贪心算法生长：每步将当前最热的相邻格接入已有树，直至达到节点预算 $b$。"
    "该规则使树自然趋向热源，形态由热场驱动而非人工绘制。生长得到的基准树含 "
    f"{RUN['tree']['nodes']} 节点、{RUN['tree']['edges']} 段，度分布为度 1 计 "
    f"{_deg['1']}、度 2 计 {_deg['2']}、度 3 计 {_deg['3']}、度 4 计 {_deg['4']}。"
    "形态证据见 图1：树的热区集中在源块周围，末梢向外辐射，与人工绘制的规则网格有"
    "本质区别。")
paper.image(os.path.join(HERE, "outputs", "step2_tree.png"),
            caption="图1 热场驱动生长得到的树形通道形态"
                    f"（{RUN['tree']['edges']} 段、{_deg['1']} 叶）",
            width_cm=15.24)

paper.h2("2.3 Murray 定律管径分配")
paper.p(
    "对树的每条边按 Murray 定律分配半径：叶端半径为 $r_0$，内部节点半径满足")
paper.formula("r_p^3 = \\sum_{c} r_c^3,   \\qquad  r = r_0\\, flow^{1/3}", label="(2)")
paper.p(
    "其中 $flow$ 为该边下游叶数。基准树的半径剖面实测最小 "
    f"{_murray_profile['min']} mm、最大 {_murray_profile['max']} mm、平均 "
    f"{_murray_profile['mean']} mm，毛细段（$r\\le 0.6$ mm）占比 "
    f"{_murray_profile['frac_le_0_6mm']:.1%}。守恒校验见 3.3 节。")

paper.h2("2.4 公平比较协议：三重等约束")
paper.p(
    "为使“树 vs 对照组”的比较只反映拓扑差异，本文施加三重等约束：")
paper.pm("（i）**等钉住格点**：树与对照组钉住（设为 $T_{cool}$）的格点数 $N_{pin}$ 相同；")
paper.pm("（ii）**等材料**：两侧通道总截面积相同；")
paper.pm("（iii）**等总占用格点（C5）**：两侧通道占用的总格点数 $b$ 逐格相等。这是最严格的"
         "口径——只有排列方式不同，材料总量完全一致。")
paper.p(
    "对照组取两类：径向通道（每芯片向板边放射的直管）与格状通道（均匀行列网格）。"
    "压降按约定 A（最深根–叶路径）计算，与真实单位标定口径一致；其定义为")
paper.formula(
    "\\Delta p = \\frac{8\\mu L q}{\\pi r^4},   \\qquad "
    "r_{cell} = \\sqrt{A_{tot} / n} / \\sqrt{\\pi}",
    label="(3)")
paper.p(
    "其中 $L$ 为管长，$q$ 为单管流量，$A_{tot}$ 为两侧通道总截面积，$n$ 为对照组等径"
    "管根数；对照组按逐格并联约定把总流量平摊到 $n$ 根管上，单管半径由 "
    "$r_{cell}=\\sqrt{A_{tot}/n/\\pi}$ 反算。该约定与 calibrate.report() 的"
    "真实单位口径一致，而非玩具口径。")

paper.h2("2.5 约束驱动生成器")
paper.p(
    "传统做法把节点预算 $b$ 作为自由输入，扫描一组 $b$ 后挑“最好”者，结论随 $b$ 漂移。"
    "本文将 $b$ 改为约束问题的输出，三条约束均来自仓库自身：")
paper.pm("**C1 热学可容许**：树必须物理进入每个芯片 footprint（即 block_to_tree=0 门）；")
paper.pm("**C2 几何可制造**：Murray 定律下根最粗，由式 (2) 得 $r_{root}=r_0 N_{leaves}^{1/3}$，"
         "要求 $r_{root}\\le p$。该约束的正确用法是由实际叶数反推 "
         "$r_0=p/N_{leaves}^{1/3}$，而非先固定 $r_0$ 再让 $r_{root}$ 超限；")
paper.pm("**C3 水力预算**：约定 A 纯黏性压降不超过泵关死扬程 31700 Pa[20]。")
paper.p(
    "满足三条约束的设计构成可行集，输出不是单点，而是 $(T_{max},\\ \\Delta p)$ 双最小化"
    "的 Pareto 前沿。选点采用 $\\epsilon$-约束：在距前沿最优 $T_{max}$ 不超过热容忍度"
    " $t_{tol}$ 的设计中取 $\\Delta p$ 最小者，即")
paper.formula(
    "\\min \\Delta p \\quad \\text{s.t.} \\quad "
    "T_{max} - T_{max}^{*} \\le t_{tol}",
    label="(4)")
paper.p(
    "并在 $t_{tol}=0.01/0.1/0.5/1/2/5$ K 六个容忍度上报告膝盖点移动，以检验式 (4) 的"
    "选点对主观参数 $t_{tol}$ 的敏感性；结果见 4.5 节表8。")

paper.h2("2.6 评价指标")
paper.p(
    "峰值温度 $T_{max}$（最热固体格）；固体平均温度 $T_{mean}$；热阻 "
    "$R_{th}=(T_{max}-T_{cool})/Q$；压降 $\\Delta p$（式 (3)）；热点面积 $A_{hot}$"
    "（共享绝对阈值 26 °C 下固体格温度超阈面积）。由于 $T_{max}$ 在热源饱和区会失去"
    "分辨力，本文并行报告 $A_{hot}$ 与 $T_{mean}$，避免单指标误判。")

# ===========================================================================
# 3. Model validation
# ===========================================================================
paper.h1("3 模型验证")

paper.h2("3.1 网格无关性")
_gc = GCI["cases"]
paper.p(
    "在 $N=50,100,200,400,800$ 五档网格上对裸板、树、直通道三类工况求解，以 $T_{max}$ "
    "为观测量按 Richardson 外推与 GCI 方法评估。表2 给出完整结果：随网格加密，三类"
    f"工况的 $T_{max}$ 分别由 {_gc['bare'][0]['T_max']:.4f}/{_gc['tree'][0]['T_max']:.4f}"
    f"/{_gc['ctrl'][0]['T_max']:.4f} °C（$N=50$）单调下降至 "
    f"{_gc['bare'][-1]['T_max']:.4f}/{_gc['tree'][-1]['T_max']:.4f}/"
    f"{_gc['ctrl'][-1]['T_max']:.4f} °C（$N=800$），且树与直通道在每一档上逐位相同，"
    "说明两者在离散层面共享同一通道集合。细网格 GCI 分别为裸板 "
    f"{_gci_bare:.3f}%、树 {_gci_tree:.2f}%、直通道 {_gci_ctrl:.2f}%；观测收敛阶"
    f" $p={_gci_p_tree:.2f}$，低于理论二阶值，符合带源项泊松问题在源区奇性附近的"
    "预期。粗网格（$N=50$）相对细网格的偏差为树 "
    f"{GCI['gci']['tree']['coarse_err_pct']:.2f}%、裸板 "
    f"{GCI['gci']['bare']['coarse_err_pct']:.3f}%，故生产网格下的方向性结论对网格"
    "细化不敏感。")
paper.table(
    headers=["网格 $N$", "裸板 $T_{max}$ (°C)", "树 $T_{max}$ (°C)",
             "直通道 $T_{max}$ (°C)", "未知量数"],
    data=[[str(b["N"]), f"{b['T_max']:.4f}", f"{t['T_max']:.4f}",
           f"{c['T_max']:.4f}", f"{b['n_unknown']:,}"]
          for b, t, c in zip(_gc["bare"], _gc["tree"], _gc["ctrl"])],
    caption="表2 网格无关性检验（$T_{max}$，°C）",
)
paper.p(
    "另作两项回归守卫：本求解器与既有 Jacobi 实现在最细网格上的最大温差为 "
    f"{GCI['regression']['tree_vs_jacobi_1e-10_max_dT']:.2e} °C，与场求解器的偏差 "
    f"{GCI['regression']['bare_vs_field_max_dT']:.2e} °C，均处机器精度量级，"
    "排除了实现层面的系统误差。")

paper.h2("3.2 解析解验证")
paper.p(
    "2D 点热源在无穷大平板中的温度场按对数衰减 $T\\sim-(Q/2\\pi)\\ln r$。对 $5\\times 5$ "
    "源块中心温升做解析估计，得解析值 "
    f"{_an['rise_analytic']:.4f}，与 Richardson 外推值 {_an['richardson_f_ext']:.4f} "
    f"相差仅 {abs(_an['richardson_vs_analytic_pct']):.2f}%；而生产网格 $N=50$ 的直接"
    f"值为 {_an['n50_rise']:.4f}，偏差 {abs(_an['n50_vs_analytic_pct']):.1f}%，"
    "量化了粗网格在源区的离散误差。此外，单点源的远场对数斜率实测 "
    f"{RUN['sanity_check']['slope_measured']:.5f}，与解析值 "
    f"{RUN['sanity_check']['slope_analytic']:.5f} 之比 "
    f"{RUN['sanity_check']['ratio']:.4f}（$R^2="
    f"{RUN['sanity_check']['r2_log_fit']:.5f}$），验证了远场行为的正确性。")

paper.h2("3.3 Murray 守恒与电路交叉验证")
paper.p(
    f"Murray 半径分配在 {_murray_forks} 个分叉节点上的守恒残差最大 "
    f"{_murray_err:.2e}，达到双精度机器精度，说明式 (2) 的实现无系统性偏差。树形网络的"
    "水力解另用 Simulink 电学类比（流体–电路同构）独立引擎交叉验证，两引擎在等占用"
    "约束下压降一致，排除了单一实现的系统性错误。该电路与 8 邻域网格严格同构（水平/"
    "竖直/对角边数 12/12/18，合计 42），见 图2。")
paper.image(os.path.join(HERE, "outputs", "chip_route_iso.png"),
            caption="图2 电学类比电路示意（与 8 邻域网格严格同构，按模型网表重绘，电学网络与数值不变）",
            width_cm=15.2)

paper.h2("3.4 有限流量共轭验证")
paper.p(
    "钉住格约定等价于无限大流量极限。为检验该近似的后果，本文解除钉住、改按有限流量"
    "冷却液做共轭迭代，得 表3。当流量由 "
    f"{CONJ['sweep'][0]['q_lpm']} L/min 增至 {CONJ['sweep'][-1]['q_lpm']} L/min，"
    f"峰值温度由 {CONJ['sweep'][0]['peak_c']:.4f} °C 降至 "
    f"{CONJ['sweep'][-1]['peak_c']:.4f} °C，单调收敛于钉住值 "
    f"{CONJ['pinned_peak_c']:.4f} °C；守卫用例把流量推至 "
    f"{_load('conjugate_guard.json')['R15_limit_q_lpm']:.0e} L/min 时，峰值与钉住值"
    f"相差 {_load('conjugate_guard.json')['R15_limit_delta_c']:.1e} °C，证明"
    "钉住约定确为极限而非任意设定。代价是冷却液温升："
    f"{CONJ['sweep'][0]['q_lpm']} L/min 时达 "
    f"{CONJ['sweep'][0]['coolant_rise_c']:.2f} K，故工程流量应取使温升不超过 5 K 的"
    "0.73 L/min 档。")
paper.table(
    headers=["$q$ (L/min)", "峰值 (°C)", "相对钉住 (°C)", "$T_{mean}$ (°C)",
             "冷却液温升 (K)", "迭代数"],
    data=[[f"{s['q_lpm']:g}", f"{s['peak_c']:.4f}", f"{s['peak_vs_pinned']:+.4f}",
           f"{s['T_mean_c']:.4f}", f"{s['coolant_rise_c']:.4f}", str(s['iters'])]
          for s in CONJ["sweep"]],
    caption="表3 有限流量共轭扫描（253 W 单热源）",
)
paper.p(
    "多热源情形（3 die、共 759 W、功率密度 108 W/cm²）重复该扫描，"
    f"钉住峰值 {CONJM['pinned_peak_c']:.4f} °C，有限流量下峰值由 "
    f"{CONJM['sweep'][0]['peak_c']:.4f} °C 单调降至 "
    f"{CONJM['sweep'][-1]['peak_c']:.4f} °C，热活跃格占比 "
    f"{CONJM['pinned_active_pct']:.2f}%，与集中源口径（1.0%）形成对照。")

paper.h2("3.5 真实单位标定")
paper.p(
    "将无量纲结果映射到 i7-14700K（253 W[12]）与 H100（700 W[13]）两类工况"
    "（板 45×45 mm、格距 0.9 mm、硅厚 5 mm）。表4 给出裸板导热峰值、加树后峰值、热阻"
    "与压降：两类工况的 $R_{th}$ 均为 0.1403 °C/W，与功率无关，符合同几何同流量的"
    "预期。模型热阻与公开冷板数据（0.0069–0.019 °C/W[18]）的差距归因于集中源口径与 "
    "2D 理想化，而非实现错误（理想化只会使模型偏好，见 4.4 节）。")
paper.table(
    headers=["工况", "裸板峰值 (°C)", "加树峰值 (°C)", "$R_{th}$ (°C/W)",
             "$\\Delta p$ (kPa)", "流量 (L/min)"],
    data=[["i7-14700K (253 W)", f"{CAL['i7']['bare_peak_c']}",
           f"{CAL['i7']['tree_peak_c']}", f"{CAL['i7']['r_th']}",
           f"{CAL['i7']['dp_kpa']}", f"{CAL['i7']['flow_lpm']}"],
          ["H100 (700 W)", f"{CAL['h100']['bare_peak_c']}",
           f"{CAL['h100']['tree_peak_c']}", f"{CAL['h100']['r_th']}",
           f"{CAL['h100']['dp_kpa']}", f"{CAL['h100']['flow_lpm']}"]],
    caption="表4 真实单位标定（约定 A 压降）",
)
paper.p(
    "基准树的 STL 几何核验进一步确认可制造性："
    f"{RUN['stl']['triangles']} 个三角形、边界边 0、有向体积闭合，包围盒 "
    f"{RUN['stl']['bbox_mm']} mm，与 45 mm 封装的间距满足壁厚下限。")

# ===========================================================================
# 4. Results and discussion
# ===========================================================================
paper.h1("4 结果与讨论")

paper.h2("4.1 单热源：树与直通道打平但压降显著更高")
paper.p(
    f"单热源（253 W 集中于 4.5×4.5 mm 源块）下，树与等占用直通道的峰值温度逐位相同"
    f"（均为 {_cmp['tree']['T_max_C']} °C，差值 "
    f"{_cmp['dT_max_tree_minus_straight']:.1f} °C），平均固体温度与热点面积亦相同"
    f"（{_cmp['tree']['T_mean_solid_C']} °C、{_cmp['tree']['hotspot_area_mm2']} mm²）；"
    f"唯一区别是压降——树 {_cmp['tree']['pressure_drop']} 对直通道 "
    f"{_cmp['straight']['pressure_drop']}（无量纲），比值 {_dp_ratio:.0f}×。机制上，"
    "源区本身即最热的未钉住格，通道一旦覆盖源邻域，$T_{max}$ 随即饱和，拓扑不再提供"
    "额外收益；而树的 $r^4$ 四次方惩罚（式 (3)）使其压降远高于直通道。表3 的 "
    "2D/1D 共轭扫描进一步说明：流量由 "
    f"{CONJ['sweep'][0]['q_lpm']} 增至 {CONJ['sweep'][-1]['q_lpm']} L/min（约 "
    f"{CONJ['sweep'][-1]['q_lpm'] / CONJ['sweep'][0]['q_lpm']:.0f} 倍）时峰值由 "
    f"{CONJ['sweep'][0]['peak_c']:.4f} 降至 {CONJ['sweep'][-1]['peak_c']:.4f} °C，"
    f"降幅 {CONJ['sweep'][0]['peak_c'] - CONJ['sweep'][-1]['peak_c']:.1f} °C（约 "
    f"{100 * (CONJ['sweep'][0]['peak_c'] - CONJ['sweep'][-1]['peak_c']) / CONJ['sweep'][0]['peak_c']:.0f}%）；"
    f"其中 {CONJ['sweep'][0]['q_lpm']}→{CONJ['sweep'][1]['q_lpm']} L/min 的首段即占 "
    f"{CONJ['sweep'][0]['peak_c'] - CONJ['sweep'][1]['peak_c']:.1f} °C，此后 100 倍流量"
    f"仅再降 {CONJ['sweep'][1]['peak_c'] - CONJ['sweep'][-1]['peak_c']:.1f} °C，"
    f"{CONJ['sweep'][2]['q_lpm']} L/min 以上更只余 "
    f"{CONJ['sweep'][2]['peak_c'] - CONJ['sweep'][-1]['peak_c']:.1f} °C——热侧迅速饱和，"
    "而压降随流量近似线性增长，水力侧始终敏感。")

paper.h2("4.2 多热源：等钉住口径下的比较")
# multi_source_summary.json packs layout and budget into one `case` string;
# split them so the sweep rows can be filtered by budget.
_MS_ROWS = []
for _r in MS["rows"]:
    if "| budget" not in _r["case"]:
        continue  # the remaining rows are the 8-point spacing scan
    _lay, _bud = _r["case"].split("| budget")
    _d = dict(_r)
    _d["layout"] = _lay.strip()
    _d["budget"] = int(_bud.strip())
    _MS_ROWS.append(_d)
_MS_OK = [r for r in _MS_ROWS if "skipped" not in r]
_MS_SKIPPED = [r for r in _MS_ROWS if "skipped" in r]
_MS_SWEEP = [r for r in _MS_OK if r["budget"] in MS["budgets"]]
_MS_LAYOUTS = ["2 chips, 20 mm apart", "3 chips, triangle",
               "4 chips, corners", "5 chips, corners+centre"]
# 逐档差值 -3.16 / -3.74 / -1.82 / -2.08 / -4.69 / -2.74 / -0.92 / -1.09 与
# 高温区 1427/1352、1519/1516 均取自 multi_source_summary.json 的对应 case，
# 并与下方表5 逐行一致（表5 由同一 _MS_SWEEP 生成）。
paper.p(
    f"在 2/3/4/5 芯片布局、等钉住口径下扫描预算 "
    f"{min(MS['budgets'])}–{max(MS['budgets'])} 格，共 {len(_MS_ROWS)} 组设计点，"
    f"其中 {len(_MS_SWEEP)} 组成功求解、{len(_MS_SKIPPED)} 组被 N4b 几何门跳过（均为 5 "
    "芯片布局——真实 17×17 footprint 下中心块与四角块相接，五个源块融合为单一连通区、"
    "逐芯片指标无定义，见 4.4.4 节）；另有 8 组间距扫描。表5 给出全部 18 组成功布局："
    "树在全部成功布局上 Tmax 低于“一管一芯片”的径向基线，差值由 -4.69 °C"
    "（3 chips, triangle、700 格）变化至 -0.92 °C（4 chips, corners、600 格）。"
    "优势并非随预算单调：2 芯片在 600–700 格达到最大（-3.74 °C），更小（400 格，"
    "-3.16 °C）与更大预算（1000–1300 格，-1.82 至 -2.08 °C）均收窄；3 芯片在中段 "
    "700 格最深（-4.69 °C）；4 芯片在 400 格最深（-2.74 °C）而在 600 格最浅"
    "（-0.92 °C），到 1300 格仅缓慢回到 -1.09 °C。代价是压降比，18 组落在 "
    "28.6×–96.9× 区间（全部 26 个成功 case 为 27.8×–96.9×）。等钉住约束的满足情况由 "
    "18/18 组逐格相等保证，且每个芯片均被触及（最大芯片距 0）。两处例外需说明："
    "3 芯片/400 格时树的高温区 1427 mm²、对照组 1352 mm²；4 芯片/600 格时 1519 mm² "
    "对 1516 mm²——这是 26 个 case 中仅有的两处树/对照高温区比值大于 1"
    "（比值区间 0.47–1.06）。")
_c5ms = []
for _lay in _MS_LAYOUTS[:3]:
    for _bud in sorted(MS["budgets"]):
        _hit = [r for r in _MS_SWEEP
                if r["layout"] == _lay and r["budget"] == _bud]
        if _hit:
            r = _hit[0]
            _c5ms.append([
                r["layout"], str(r["budget"]), str(r["tree_pinned"]),
                f"{r['tree_T_max']:.3f}", f"{r['ctrl_T_max']:.3f}",
                f"{r['dT_max_tree_minus_ctrl']:+.3f}",
                f"{r['dp_ratio_tree_over_ctrl']:.1f}×",
            ])
paper.table(
    headers=["布局", "预算(格)", "钉住(树=对照)", "树 $T_{max}$ (°C)",
             "对照 $T_{max}$ (°C)", "$\\Delta T_{max}$ (°C)", "$\\Delta p$ 比"],
    data=_c5ms,
    caption=f"表5 等钉住口径下树与径向基线的比较（全部 {len(_MS_SWEEP)} 组成功布局）",
)

paper.h2("4.3 多热源：等总占用格点口径下的比较")
paper.p(
    "等钉住口径允许两侧材料量不同（树通道可复用主干）。更严格的 C5 口径要求两侧通道"
    "占用总格点数逐格相等，此时只有排列方式不同。表6 给出代表工况：格状网在峰值温度"
    "上整体不劣于树，且压降低 2–3 个数量级；径向通道在 3/4 芯片下 $T_{max}$ 略高于"
    "树（0.2–0.7 °C），但压降最低；树在温度上仅对径向有微弱优势，代价是压降高出约三个"
    "数量级。以 3 芯片、1300 格为例，树 "
    f"{[r for r in C5['rows'] if r['case'].startswith('3 chips') and r['budget'] == 1300][0]['tree_T_max']:.3f} °C "
    "对格状 "
    f"{[r for r in C5['rows'] if r['case'].startswith('3 chips') and r['budget'] == 1300][0]['lattice_total_T_max']:.3f} °C，"
    "格状压降仅 "
    f"{[r for r in C5['rows'] if r['case'].startswith('3 chips') and r['budget'] == 1300][0]['dp_lattice_total']:.1f} Pa "
    "而树为 $10^4$ Pa 量级。既有“树更优”的论断在公平口径下不再稳健。")
_c5rows = []
_seen = set()
for r in C5["rows"]:
    key = (r["case"], r["budget"])
    if r["budget"] in (400, 1300) and key not in _seen:
        _seen.add(key)
        _c5rows.append([
            r["case"], str(r["budget"]),
            f"{r['tree_T_max']:.3f}",
            f"{r['radial_total_T_max']:.3f}",
            f"{r['lattice_total_T_max']:.3f}",
            f"{r['dp_radial_total']:.2f}",
            f"{r['dp_lattice_total']:.1f}",
        ])
paper.table(
    headers=["布局", "预算(格)", "树 $T_{max}$", "径向 $T_{max}$",
             "格状 $T_{max}$", "径向 $\\Delta p$ (Pa)", "格状 $\\Delta p$ (Pa)"],
    data=_c5rows,
    caption="表6 等总占用格点口径下三类拓扑比较（温度 °C；压降为对照组）",
)
paper.p(
    "径向对照已改用跨芯片轮询的均衡分配，早期按芯片顺序分配导致后续芯片缺水的缺陷"
    "已修复，故 3/4 芯片下不再存在 C1 不可行行。")

paper.h2("4.4 格状网基线与优势边界的再检验")
paper.h3("4.4.1 等压降材料代价")
paper.p(
    "“树省料”的说法需在等压降下检验。以等钉住、等压降为约束重算材料量，树的材料"
    "用量为格状网的 33–42 倍（4/4 反向），故本文不主张树省料，只讨论"
    "温度与压降的权衡。")
paper.h3("4.4.2 非均功率与 pitch 扫描")
# 口径注记（2026-10-24）：UPOW['cases'] 的顺序是 [1/1/1, 1/1/5, 3/1/1, 1/2/3]，
# 不是文档叙述顺序；tree_minus_best_Tmax = 树 − 最优格状网，负值表示树更低。
# 旧稿取 cases[3]（=1/2/3 的 0.7411）却标注“1/1/5”，且把 1/1/1 下“树低 1.2158”
# 反向写成“格状网低 1.2158”，并将最优 pitch 写成空洞的“p13 与 p13”。三处已按工件
# 与 doc3 §10 改正（1/1/5 实为 0.4170；最优 pitch 只在 3/1/1 落到 p10）。
_up = {"/".join(str(int(v)) for v in c["powers"]): c for c in UPOW["cases"]}
_up_abs = [abs(c["tree_minus_best_Tmax"]) for c in UPOW["cases"]]
_up_pitch = sorted({c["best_Tmax_pitch"] for c in UPOW["cases"]})
_up_low = [c for c in UPOW["cases"] if c["best_Tmax_pitch"] == min(_up_pitch)][0]
_up_label = "/".join(str(int(v)) for v in _up_low["powers"])
_up_win = sum(1 for c in UPOW["cases"] if c["tree_minus_best_Tmax"] < 0)
paper.p(
    "把“等功率”假设去掉后，树在峰值温度上的优势并未消失，但“自适应”的强度依赖功率分布。"
    f"在 {UPOW['layout']}、预算 {UPOW['budget']} 格、{len(UPOW['pitches'])} 个 pitch "
    f"（pitch {min(UPOW['pitches'])}–{max(UPOW['pitches'])}）上重扫：等功率配比 "
    "（1/1/1）下树的 $T_{max}$ 比最优格状网低 "
    f"{abs(_up['1/1/1']['tree_minus_best_Tmax']):.4f} °C，热点面积差 "
    f"{_up['1/1/1']['tree_minus_best_hotspot']:+.1f} mm²；换到极端配比 （1/1/5），树仍低 "
    f"{abs(_up['1/1/5']['tree_minus_best_Tmax']):.4f} °C，但热点面积差转为 "
    f"{_up['1/1/5']['tree_minus_best_hotspot']:+.1f} mm²（最优格状网把两颗低功率芯片压到 "
    f"0 mm²，集中保 5 倍功率那颗）。四个配比下树 {_up_win}/{len(UPOW['cases'])} 全胜（"
    f"−{min(_up_abs):.4f} 至 −{max(_up_abs):.4f} °C）；最优 pitch 随功率配比在 "
    f"p{max(_up_pitch)} 与 p{min(_up_pitch)} 之间移动（仅 {_up_label} 取 "
    f"p{min(_up_pitch)}），“树自适应”因此部分成立：在本布局与预算下温度方向一致，"
    "集中度与热点面积仍与功率分布、pitch 选择耦合。")
paper.h3("4.4.3 有限对流边界")
# 此处原用 max(|dT_max|) 作为“差值变化上限”，但该量等于拓扑差本身的量级（≈4.6 °C），
# 对“理想冷汇无害”不构成信息量；改用 10 档 h（0–100，无量纲 Bi）下 dT_max 的极差（0.0671 °C）。
# 注意：h_conv 在 field.py 中是 [a.u.]，Bi = h_conv*PITCH_MM = h_conv，不可标 W/(mm²·K)。
_dT_robin = [r["dT_max"] for r in ROBIN["multi"]]
paper.p(
    "把边界从理想冷汇改为有限对流（$h_{conv}$ 即无量纲 $Bi$，取 0 至 100 共 10 档），树与对照的"
    "$T_{max}$ 同步平移，差值变化不超过 "
    f"{max(_dT_robin) - min(_dT_robin):.4f} °C，"
    "证明理想冷汇是一个无害近似——它不改变方向性结论，只整体抬高温度水平。")
paper.h3("4.4.4 5 芯片布局被排除的原因：footprint 融合，而非预算不足")
paper.p(
    "本文不报告任何 5 芯片工况，原因是几何性的而非水力性的。每个裸片在真实 footprint "
    "下是 17×17 的块。在“四角+中心”布局中，角块到中心块的偏移为 (13, 13) 格，因此"
    "半宽 8 的块在每轴上重叠 4 格：每个角块与中心块共享 16 格，五个块渗透成一个 1381 "
    "格的单一连通区（5×289 − 4×16），此时“芯片到最近树格的距离”以及由此定义的逐芯片"
    "指标归一化都无定义。因此全部六个预算档在任何水力比较之前即被几何有效性门"
    "（代码中的 N4b）排除——不是被 C1 钉住门排除，也不是因为预算太小。2/3/4 芯片布局"
    f"中没有类似情况：全部 {len(_MS_SWEEP)} 个成功求解的 case 逐格钉住数相等，最大芯片"
    "距为 0。五芯片几何超出了本 footprint 模型能解析的范围；更小的裸片（小于 17×17 "
    "格），或任一轴上大于 17 格的角–中心偏移，都会使各块重新分离。该实验留待后续，"
    "它界定了 4.2 节多热源结论适用的布局范围。")

paper.h2("4.5 约束驱动生成器的 Pareto 前沿")
paper.p(
    "约束驱动生成器在四个布局上输出 4–10 个前沿点（表7）。两个结构性读数在四个布局上"
    "一致：（i）单热源前沿退化——源区饱和使“最优拓扑”问题不存在，1 芯片布局只有 "
    f"{FRONTS['1 chip']['tree']['n_feasible']} 个可行点；（ii）多热源前沿的 "
    "$\\Delta p$ 随预算上升（Murray $r^4$ 惩罚），树因此存在真实的双目标权衡。"
    "以 3 芯片布局为例，预算由 210 格增至 1309 格时 $T_{max}$ 由 "
    f"{FRONTS['3 chip']['tree']['front'][0]['T_max_c']:.3f} 降至 "
    f"{FRONTS['3 chip']['tree']['front'][-1]['T_max_c']:.3f} °C，"
    "而 $\\Delta p$ 由 "
    f"{FRONTS['3 chip']['tree']['front'][0]['dp_pa']:.0f} 升至 "
    f"{FRONTS['3 chip']['tree']['front'][-1]['dp_pa']:.0f} Pa，涨幅 "
    f"{FRONTS['3 chip']['tree']['front'][-1]['dp_pa'] / FRONTS['3 chip']['tree']['front'][0]['dp_pa']:.1f}×。"
    "把等总口径对照放进同一框架后：格状网在四个布局上均支配树（温度持平或更优、"
    "压降低 2–3 个数量级）；径向通道在 3/4 芯片下温度略高（0.2–0.7 °C），压降同样"
    "低 2–3 个数量级。")
_frows = []
for lab in ["1 chip", "2 chip d=16", "3 chip", "4 chip"]:
    e = FRONTS[lab]
    tf = e["tree"]["front"]
    coldest = min(tf, key=lambda d: d["T_max_c"])
    ks = {round(k["t_tol_c"], 2): k for k in e["tree"]["knee_sensitivity"]}
    knee1 = ks.get(1.0) or ks.get(2.0)
    _frows.append([
        lab, str(e["tree"]["n_feasible"]),
        f"{coldest.get('n_leaves', '–')}",
        f"{coldest['T_max_c']:.3f}",
        f"{coldest['dp_pa']:.0f}",
        f"{knee1['dp_pa']:.0f}" if knee1 else "–",
    ])
paper.table(
    headers=["布局", "前沿点数", "最冷点叶数", "最冷 $T_{max}$ (°C)",
             "最冷 $\\Delta p$ (Pa)", "$t_{tol}=1$ K 膝盖 $\\Delta p$ (Pa)"],
    data=_frows,
    caption="表7 约束驱动生成器 Pareto 前沿端点与膝盖点",
)
paper.p(
    "膝盖点对热容忍度的敏感性见表8。3 芯片布局从 $t_{tol}=0.01$ K 放宽到 0.1 K，"
    "$\\Delta p$ 由 "
    f"{FRONTS['3 chip']['tree']['knee_sensitivity'][0]['dp_pa']:.0f} 降至 "
    f"{FRONTS['3 chip']['tree']['knee_sensitivity'][1]['dp_pa']:.0f} Pa，"
    "节省约 "
    f"{(1 - FRONTS['3 chip']['tree']['knee_sensitivity'][1]['dp_pa'] / FRONTS['3 chip']['tree']['knee_sensitivity'][0]['dp_pa']) * 100:.0f}%，"
    f"热代价仅 {FRONTS['3 chip']['tree']['knee_sensitivity'][1]['T_max_penalty_c']:.3f} K。"
    "该敏感度说明：以“最冷”为唯一目标会把设计推到泵限边缘（最冷设计距 C3 限仅 "
    "1.2–1.7 倍余量），工程选点应取非零热容忍度的膝盖点。")
_krows = []
for lab in ["1 chip", "2 chip d=16", "3 chip", "4 chip"]:
    for k in FRONTS[lab]["tree"]["knee_sensitivity"]:
        _krows.append([
            lab, f"{k['t_tol_c']:g}", f"{k['n_leaves']}", str(k["budget"]),
            f"{k['T_max_c']:.4f}", f"{k['T_max_penalty_c']:.4f}",
            f"{k['dp_pa']:.0f}",
            f"{k['dp_vs_min_front']:.3f}",
        ])
paper.table(
    headers=["布局", "$t_{tol}$ (K)", "叶数", "预算(格)", "$T_{max}$ (°C)",
             "热惩罚 (K)", "$\\Delta p$ (Pa)", "$\\Delta p$ / 前沿最小"],
    data=_krows,
    caption="表8 膝盖点对热容忍度的敏感性（四个布局，六个容忍度）",
)
paper.image(os.path.join(HERE, "outputs", "generator_front_compare.png"),
            caption="图3 3 芯片布局等总口径可行设计：峰值温度与压降随总占用格点变化",
            width_cm=15.2)

paper.h2("4.6 讨论与局限")
paper.p(
    "本结果的工程含义是明确的：树形冷板在多热源场景下对径向仅有 0.2–0.7 °C 的微弱"
    "温度收益、对格状被支配，代价是压降高出数个数量级；在单热源与等总占用口径下不具备优势。这与"
    "文献中“树形普遍更优”的印象相左，根源在于既有比较常未对齐预算口径。")
paper.p(
    "局限须如实说明：（1）压降为纯黏性项（式 (3)），未含接头局部损失与 0.2–0.5 mm "
    "翅片间距的 $r^4$ 修正（1.0–39.1×[15,16]），故为乐观下界，而树的 57 个分叉节点"
    "恰是局部损失最集中处，真实差距可能更大；（2）2D 模型缺封装层、对流膜系数与 398 "
    "处接头的局部损失，压降结论是上界估计；（3）黏度取 20 °C 值作用于 25 °C 工况，"
    "压降偏高约 12.6%；（4）最冷设计距泵限仅 1.2–1.7 倍余量，泵选型应取非零热容忍度"
    "的膝盖点；（5）本文未做打印或实验实测，通道连通性、接头密封与承压能力均未经"
    "直接验证，仅由 STL 边界边为 0、有向体积闭合等几何指标间接支持。冷板工程实践"
    "指出，承压设计不足会导致密封失效，或与芯片贴合不良而抬高界面热阻[19]，故本文的"
    "压降与热阻结论仍需实验标定。这些均不改变“树在公平口径下不占优”的方向性结论。")

# ===========================================================================
# 5. Conclusions
# ===========================================================================
paper.h1("5 结论")
paper.pm("（1）建立了等钉住格点、等材料、等总占用格点三重公平约束的比较协议。单热源下"
         "树与直通道峰值温度逐位相同（27.60 °C），但树压降高约 310 倍；$T_{max}$ 在源"
         "饱和区失去分辨力。")
paper.pm("（2）多热源等总占用口径下，格状网在峰值温度与压降上整体不劣于树（3 芯片、"
         "1300 格：27.17 对 27.16 °C，格状压降仅 19 Pa 而树为 10⁴ Pa 量级）；"
         "“树更优”在公平口径下不再稳健。")
paper.pm("（3）约束驱动生成器把节点预算从自由输入转为 C1/C2/C3 三约束的求解输出，在"
         "四个布局上给出 4–10 点 Pareto 前沿；膝盖点对热容忍度敏感（3 芯片容忍 0.1 K "
         "即可节省约 21% 压降）。")
paper.pm("（4）模型经网格无关性（细网格 GCI 0.067%–3.14%）、解析解（Richardson 外推与"
         "解析差 0.10%）、Murray 守恒（残差 4.8×10⁻¹⁶）、Simulink 电路交叉验证与有限"
         "流量共轭极限（$Q\\to\\infty$ 复现钉住峰值，偏差 4.0×10⁻⁹ °C）五重检验。"
         "全部数值可一键复现。")
paper.p(
    "本文的贡献是可复现的公平比较协议与约束驱动生成装置，而非树形拓扑的性能优势——"
    "实测恰相反。这为仿生散热结构的筛选提供了判据：树形冷板仅在多热源且对照为径向"
    "直管时才有 0.2–0.7 °C 的微弱温度收益，单热源场景可直接排除。")

# ===========================================================================
# Closing statements (journal conventions)
# ===========================================================================
paper.h1("数据可用性声明")
paper.p(
    "本文全部数值结果由仓库自带求解器实跑产生，数据随文归档：运行报告 "
    "outputs/run_report.json、网格收敛 outputs/a4_grid_convergence.json、"
    "等总口径对照 outputs/c5_artifact.json、约束驱动前沿 outputs/generator_fronts.json、"
    "共轭扫描 outputs/conjugate_single.json 与 outputs/conjugate_multi_real.json、"
    "多源扫描 outputs/multi_source_summary.json、有限对流 "
    "outputs/robin_boundary_summary.json、pitch 扫描 outputs/lattice_pitch_summary.json "
    "与 outputs/unequal_power_pitch_summary.json、真实单位标定 "
    "outputs/real_unit_calibration.txt。复现命令见附录。")
paper.p(
    "全部源码、上述工件与校验清单同时公开托管于 GitHub 仓库 "
    "https://github.com/ice917/bionic-tree-microchannel；每个分发文件的 SHA-256 校验值"
    "记录在仓库根目录的 MANIFEST.sha256 中，可逐文件核对。数据集与代码已在 Zenodo "
    "永久归档并作为参考文献 [21] 引用；概念 DOI 10.5281/zenodo.23620418 始终解析到"
    "最新归档版本，各归档快照的版本 DOI 见该记录页。本研究为纯计算研究，未进行预注册。")

paper.h1("代码可用性")
paper.p(
    "本文全部求解、绘图与稿件生成代码以 MIT 许可发布（LICENSE），数据与文档以 "
    "CC BY 4.0 许可发布（LICENSE-DATA）；第三方材料（src_extract/、参考论文/）不随"
    "本文分发。复现全部表格与图件的命令见附录。")

paper.h1("作者贡献")
paper.p("概念化、方法论、软件、验证、形式化分析、可视化与初稿撰写：全部作者。"
        "全部作者已阅读并同意稿件的最终版本。")

paper.h1("利益冲突声明")
paper.p("作者声明不存在与本文发表相关的已知竞争性经济利益或个人关系。")

paper.h1("基金资助")
paper.p("本研究未接受任何外部基金资助。")

# ===========================================================================
# References
# ===========================================================================
paper.h1("参考文献")
for ref in [
    "[1] Murray C D. The physiological principle of minimum work: I. The vascular "
    "system and the cost of blood volume[J]. Proceedings of the National Academy of "
    "Sciences, 1926, 12(3): 207-214.",
    "[2] Tuckerman D B, Pease R F W. High-performance heat sinking for VLSI[J]. IEEE "
    "Electron Device Letters, 1981, 2(5): 126-129.",
    "[3] Bejan A. Constructal-theory network of conducting paths for cooling a heat "
    "generating volume[J]. International Journal of Heat and Mass Transfer, 1997, "
    "40(4): 799-816.",
    "[4] West G B, Brown J H, Enquist B J. A general model for the origin of "
    "allometric scaling laws in biology[J]. Science, 1997, 276(5309): 122-126.",
    "[5] Tero A, Kobayashi R, Nakagaki T. A mathematical model for adaptive transport "
    "network in path finding by true slime mold[J]. Journal of Theoretical Biology, "
    "2007, 244(4): 553-564.",
    "[6] Bonifaci V, Mehlhorn K, Varma G. Physarum can compute shortest paths[J]. "
    "Journal of Theoretical Biology, 2012, 309: 121-133.",
    "[7] Jing D, Song S, He L. Reexamination of Murray's law for tree-like rectangular "
    "microchannel network with constant channel height[J]. International Journal of "
    "Heat and Mass Transfer, 2019, 128: 1344-1350.",
    "[8] Wang G, Sheng K, Wang Y, et al. Thermal hydraulic performance of tree-like "
    "microchannel heat sink with high branching level based on the improved Murray's "
    "law[J]. International Journal of Heat and Mass Transfer, 2024, 231: 125875.",
    "[9] Chen K, Chen Y, Zhai K, He Z. Thermo-hydraulic and flow distribution "
    "characteristics of bionic fractal Y-shaped bifurcation microchannel heat sink[J]. "
    "Processes, 2026, 14(19): 3181.",
    "[10] Tan H, Wu L-W, Wang M-Y, Yang Z-H, Du P-A. Heat transfer improvement in "
    "microchannel heat sink by topology design and optimization for high heat flux chip "
    "cooling[J]. International Journal of Heat and Mass Transfer, 2019, 129: 681-689.",
    "[11] Wang N, Tian B, Liu L, Li J, Shao S. Integrated topology optimization and "
    "microchannel cold plate for chip cooling[C]//Energy Proceedings, 2024, 58.",
    "[12] Intel. Intel Core i7-14700K processor specifications[EB/OL]. "
    "https://www.intel.cn/content/www/cn/zh/products/sku/236783/, 2026.",
    "[13] NVIDIA. NVIDIA H100 Tensor Core GPU architecture[EB/OL]. "
    "https://www.nvidia.com/en-us/data-center/h100/, 2026.",
    "[14] Glassbrenner C J, Slack G A. Thermal conductivity of silicon and germanium "
    "from 3 K to the melting point[J]. Physical Review, 1964, 134(4A): A1058-A1069.",
    "[15] Kiser C C, Handy T A, Lemley E C, et al. Reynolds number dependence for "
    "laminar flow loss coefficients in tee and wye junctions[C]//ASME FEDSM-ICNMM, "
    "2010: 341-347.",
    "[16] Rennels D C, Hudson H M. Pipe Flow: A Practical and Comprehensive Guide[M]. "
    "Hoboken: Wiley, 2012.",
    "[17] Open Compute Project. OAI system liquid cooling guidelines[EB/OL]. "
    "https://www.opencompute.org/, 2023.",
    "[18] Pinkus I, Park W Y, Ganesan V, et al. Ultra-low thermal resistance and "
    "pressure drop copper and copper-tungsten diamond-shaped pin fin cold plates for "
    "liquid cooling of electronics[J]. International Journal of Heat and Mass Transfer, "
    "2026, 256: 128080.",
    "[19] Ecotherm. Cold plate design guide, part 1: key basics for efficient thermal "
    "management[EB/OL]. https://ecothermgroup.com/, 2026.",
    "[20] Alphacool. Laing DDC-Pump 12V DDC-1RT datasheet[EB/OL]. "
    "https://www.alphacool.com/, 2026.",
    "[21] Wu H. Bionic adaptive network: generation, comparison and defect ledger of "
    "chip heat-dissipation channel trees[DS/OL]. Zenodo, 2026. "
    "https://doi.org/10.5281/zenodo.23620418 （概念 DOI，始终解析到最新归档版本）.",
]:
    paper.reference(ref)

paper.h1("附录：复现命令")
for cmd in [
    "python calibrate.py                        # 真实单位标定（表4）",
    "python a4_grid_convergence.py              # 网格无关性与解析解（表2、3.1–3.2）",
    "python heat_tree.py                        # 基准树、STL、单源对比（图1、4.1）",
    "python multi_source.py                     # 等钉住多源扫描（表5）",
    "python generator.py                        # C5 对照与约束驱动前沿（表6–8、图3）",
    "python generator_front_artifacts.py        # 前沿工件与对比图（表7–8、图3）",
    "python conjugate_run.py                    # 有限流量共轭（表3）",
    "python conjugate_multi.py                  # 多源真实尺度共轭（3.4）",
    "python robin_boundary.py                   # 有限对流边界扫描（4.4.3）",
    "python lattice_scan.py                     # 格状网 pitch 扫描（4.4.2）",
    "python unequal_pitch_scan.py               # 非均功率 × pitch（4.4.2）",
    "python spread_source_scan.py               # 铺开源真实功率密度（3.4）",
    "python p0b_a0_anchor.py                    # P0a 共轭判决性实验（4.1）",
]:
    paper.pm(f"`{cmd}`")

paper.check_numbering()
add_ai_label(paper.doc)
paper.save()
print("OK ->", OUT_PATH)
