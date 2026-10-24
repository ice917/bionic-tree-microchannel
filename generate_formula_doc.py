# -*- coding: utf-8 -*-
"""生成《论文公式推导与影响因素系统梳理》Word 文档（docx，替代 markdown 版）。

公式统一用 Unicode 数学符号（希腊字母、上标 ²³⁴⁵⁶、下标 ₀₁₂ 等），
不依赖 LaTeX，直接在 Word 中可读。
"""
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

doc = Document()

# 默认样式
normal = doc.styles['Normal']
normal.font.name = 'Times New Roman'
normal.font.size = Pt(10.5)
normal._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')


def _set(run, cn='宋体', en='Times New Roman', size=None, bold=None, color=None, italic=None):
    run.font.name = en
    run._element.rPr.rFonts.set(qn('w:eastAsia'), cn)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color


def h1(text):
    p = doc.add_heading(level=1)
    r = p.add_run(text)
    _set(r, cn='微软雅黑', size=16, bold=True, color=RGBColor(0x1F, 0x3B, 0x63))
    return p


def h2(text):
    p = doc.add_heading(level=2)
    r = p.add_run(text)
    _set(r, cn='微软雅黑', size=13, bold=True, color=RGBColor(0x1F, 0x3B, 0x63))
    return p


def h3(text):
    p = doc.add_heading(level=3)
    r = p.add_run(text)
    _set(r, cn='微软雅黑', size=11.5, bold=True, color=RGBColor(0x2E, 0x4E, 0x7E))
    return p


def para(text, bold=False, italic=False, color=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    _set(r, size=10.5, bold=bold, italic=italic, color=color)
    return p


def formula(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    _set(r, en='Cambria Math', size=11)
    return p


def bullet(text, bold_prefix=None):
    p = doc.add_paragraph(style='List Bullet')
    if bold_prefix:
        r1 = p.add_run(bold_prefix)
        _set(r1, size=10.5, bold=True)
    r = p.add_run(text)
    _set(r, size=10.5)
    return p


def note(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    _set(r, size=9.5, italic=True, color=RGBColor(0x8A, 0x3B, 0x00))
    return p


# ============================================================ 标题
h1('仿生树形微通道散热论文 —— 公式推导与影响因素系统梳理')
para('本文档目的：把论文的全部公式（含推导）、全部实验的影响因素（按重要性分级）系统性整理出来，回答一个核心问题——这篇论文究竟在干什么。', italic=True)

# ============================================================ §0
h2('0. 论文在干什么（一句话）')
para('文献普遍声称「树形仿生微通道优于直通道」，但这个结论高度依赖「材料预算」的设定、结论会随预算反转。本文不提供「树更优」的新证据，而是造一台一键可复现的裁决装置：在明确口径下，树的优势是否成立、在哪里成立、代价多少。')

# ============================================================ §1
h2('1. 核心逻辑链（三模块闭环）')
para('① 口径约束（三重公平：等钉住 / 等材料 / 等总占用） →  ② 热场驱动生长（热传导场 + Prim 贪心 + Murray 立方管径） →  ③ 约束选择（C1 进入芯片 / C2 根半径 / C3 压降 → Pareto 前沿 + ε 膝盖点）')
para('任何「树更优」的论断，都可以在这个框架内被复现或被证伪。')

# ============================================================ §2
h2('2. 全部公式与完整推导')

h3('2.1 Eq.(1) 稳态热传导方程　∇²T = −q/k')
para('物理来源：傅里叶定律 + 能量守恒。', italic=True)
para('第 1 步 傅里叶定律：', bold=True)
formula('q⃗ = −k∇T')
para('第 2 步 稳态能量守恒（净流出热 = 内热源产生热），散度定理：', bold=True)
formula('∇·q⃗ = q_源')
para('第 3 步 代入，k 取常数：', bold=True)
formula('∇²T = −q_源/k')
para('第 4 步 二维直角坐标展开：', bold=True)
formula('∂²T/∂x² + ∂²T/∂y² = −q_源/k')
para('第 5 步 五点差分（步长 h，格点 (i,j)），二阶中心差分：', bold=True)
formula('∂²T/∂x²|ᵢⱼ = (Tᵢ₊₁ⱼ − 2Tᵢⱼ + Tᵢ₋₁ⱼ)/h² + O(h²)')
para('代入得五点格式与迭代式：', bold=True)
formula('Tᵢⱼ = (Tᵢ₊₁ⱼ + Tᵢ₋₁ⱼ + Tᵢⱼ₊₁ + Tᵢⱼ₋₁ + q_源·h²/k) / 4')
para('第 6 步 Jacobi 迭代求解，残差判据 10⁻⁶（论文实测 4513 次收敛）。', bold=True)

h3('2.2 Eq.(2) Murray 定律　r_p³ = Σ r_c³')
para('物理来源：最小功原理（泵功 + 体积维护代价最小化）。', italic=True)
para('第 1 步 单根管代价函数。泵功 = 流量 × 压降，压降用 Poiseuille（Eq.(3)）代入：', bold=True)
formula('W_pump = Q·Δp = Q·8μLQ/(πr⁴) = 8μLQ²/(πr⁴)')
para('体积维护代价（λ 为拉格朗日乘子）：', bold=True)
formula('W_vol = λ·πr²L')
para('第 2 步 总代价对 r 最小化：', bold=True)
formula('E(r) = 8μLQ²/(πr⁴) + λπr²L')
formula('dE/dr = −32μLQ²/(πr⁵) + 2λπLr = 0')
para('第 3 步 化简：', bold=True)
formula('Q = (π/4)·√(λ/μ)·r³   ⇒   Q ∝ r³')
para('第 4 步 分叉点质量守恒：', bold=True)
formula('Q_p = Σ Q_c   ⇒   r_p³ = Σ r_c³')
para('第 5 步 论文用法 r = r0·flow^(1/3)：因 Q ∝ 下游叶数 flow，且 Q ∝ r³，故 r ∝ flow^(1/3)，叶端（flow=1）半径记为 r0。', bold=True)

h3('2.3 Eq.(3) Poiseuille 定律　Δp = 8μLQ/(πr⁴)')
para('物理来源：圆柱坐标 Navier–Stokes 方程轴对称层流解。', italic=True)
para('第 1 步 假设：半径 R 圆管，不可压缩牛顿流体，稳态充分发展层流 u(r)。', bold=True)
para('第 2 步 轴向 N-S 简化（惯性项为零），压降梯度恒定 dp/dz = −Δp/L：', bold=True)
formula('(1/r)·d/dr(r·du/dr) = −Δp/(μL)')
para('第 3 步 第一次积分（r=0 处 du/dr 有限 → C₁=0）：', bold=True)
formula('du/dr = −Δp·r/(2μL)')
para('第 4 步 第二次积分（无滑移 r=R 处 u=0），抛物线速度分布：', bold=True)
formula('u(r) = Δp(R² − r²)/(4μL)')
para('第 5 步 体积流量：', bold=True)
formula('Q = ∫₀ᴿ u(r)·2πr dr = πΔpR⁴/(8μL)')
para('第 6 步 整理（半径记作 r）：', bold=True)
formula('Δp = 8μLQ/(πr⁴)')

h3('2.4 Eq.(4) ε-约束选点')
para('这是优化方法（非物理推导）。双目标 min (Δp, T_max) 冲突，ε-约束法把一个目标转成约束：', italic=True)
formula('min Δp    s.t.    T_max − T_max* ≤ t_tol')
para('T_max* 是前沿最冷设计的峰值温度，t_tol 是允许的热学劣化容忍度。遍历 t_tol ∈ {0.01, 0.1, 0.5, 1, 2, 5} K 得到膝盖点轨迹。')

h3('2.5 三个派生关系式')
para('① C2 根半径（根管下游叶数 = N_leaves，代入 r = r0·flow^(1/3)）：', bold=True)
formula('r_root = r0 · N_leaves^(1/3)')
para('② 叶端半径上限（约束 r_root ≤ p 取等号）：', bold=True)
formula('r0 ≤ p / N_leaves^(1/3)')
para('③ 对照组单管半径反算（等材料，总截面积 A_tot 均分 n 根等径管）：', bold=True)
formula('r_cell = √(A_tot/n) / √π')

h3('2.6 「设而不求」框架的公式')
para('背景：接头损失系数 K 在层流微通道 Re<150 区间无可靠标定，且树段 L/D≈1 处于入口效应主导区，Poiseuille 假设本身失效。因此不「求」K 的精确单点值，而「设」一个 K 家族，改「求」结论对 K 不确定性的稳健性边界。', italic=True)

para('2.6.1 接头局部损失基本式（动压头形式）：', bold=True)
formula('Δp_junction = K · ρv²/2,   v = Q/(πr²)')

para('2.6.2 K 家族（四个模型，下界 → 上界）：', bold=True)
bullet('K = 0（纯黏性下界，无接头）', bold_prefix='J0：')
bullet('K = 0.62 − 0.98s + 0.36s²，s = q_main/q_par（湍流外推下界，已登记误用）', bold_prefix='J1：')
bullet('K = 1.8（中间参考）', bold_prefix='J2：')
bullet('K = min(max(1.8·2300/Re, 1), 300)（层流插值上界）', bold_prefix='J3：')
note('J1 的三处误用：漏第 4 项 0.03(ṁ₂/ṁ₁)⁶、自变量倒置（原式 ṁ₁/ṁ₂=1/s）、超出湍流适用区。')

para('2.6.3 Kiser CFD 标定关系（说明「为什么不求」）：', bold=True)
formula('K = C/Re_d,   有效区间 Re_d ∈ [1,100]（最大偏差 30%）')
para('本树 Re 252.5–2438.3 已越出拟合区，故固定 K 网格不严谨。')

para('2.6.4 β —— 协议 v5 核心自变量（接头/黏性强度比）：', bold=True)
formula('β = KρQ/(16πμL)')
para('严格推导（β 的物理含义）——β 恰好是接头损失与黏性损失之比：', italic=True)
formula('β = Δp_junction/Δp_viscous = [KρQ²/(2π²r⁴)] / [8μLQ/(πr⁴)] = KρQ/(16πμL)')

para('2.6.5 含接头损失的 Murray 定律推广（变分 → 幂律被打破）：', bold=True)
para('第 1 步 单管总压降：', bold=True)
formula('Δp = 8μLQ/(πr⁴) + KρQ²/(2π²r⁴)')
para('第 2 步 泵功：', bold=True)
formula('W = Q·Δp = 8μLQ²/(πr⁴) + KρQ³/(2π²r⁴)')
para('第 3 步 变分（含体积代价 λπr²L）：', bold=True)
formula('dE/dr = −32μLQ²/(πr⁵) − 2KρQ³/(π²r⁵) + 2λπLr = 0')
formula('⇒  r⁶ = (16μLQ²/π + KρQ³/π²)/(λπL)')
para('第 4 步 关键结论：右边含 Q² 与 Q³ 两项混合，说明含接头损失后 Q ∝ r^α 的单一幂律被打破——Murray 定律的「指数」概念本身失效，这正是「设而不求」要把问题从「求 K」转向「求 β 边界」的根本原因。', bold=True)

para('2.6.6 α_local —— 有效分叉指数（严格推导，替换原 α_eff）：', bold=True)
para('严格推导（对称二分叉 + 常数 K 接头损失的最小功变分）：', italic=True)
para('父管（Q₀，r₀）→ 两个相同子管（Q₀/2，r₁），代价 = 泵功 + 体积维护代价：')
formula('E = 8μLQ₀²/(πr₀⁴) + KρQ₀³/(2π²r₀⁴) + 4μLQ₀²/(πr₁⁴) + KρQ₀³/(8π²r₁⁴) + λπL(r₀² + 2r₁²)')
para('∂E/∂r₀ = 0 与 ∂E/∂r₁ = 0，代入 β = KρQ₀/(16πμL)：')
formula('r₀⁶/r₁⁶ = 4(1+β)/(1+β/2)')
para('由 Murray 关系 r₀/r₁ = 2^(1/α) 反推局部有效指数：')
formula('α_local = 6·ln2 / ln[4(1+β)/(1+β/2)]')
para('边界行为：', bold=True)
bullet('β → 0：r₀⁶/r₁⁶ → 4，即 r₀/r₁ = 2^(1/3)，α → 3（精确恢复 Murray 指数）')
bullet('β → ∞：r₀⁶/r₁⁶ → 8，即 r₀/r₁ = 2^(1/2)，α → 2（纯接头主导极限）')
para('等价简洁式（单管局部对数导数，与上述一致）：', bold=True)
formula('α_local = 6(1+β)/(2+3β)')
bullet('β → 0：α = 6/2 = 3')
bullet('β → ∞：α = 6β/(3β) = 2（单调下降，dα/dβ = −6/(2+3β)² < 0）')
note('废弃说明（重要）：原仓库预登记的 α_eff = 3/(1+β/(4(1+β)))（β→∞ 极限 12/5 = 2.4）经严格变分推导与文献查证无法得到支撑——常数 K 接头损失的标准变分 β→∞ 极限为 2，层流 K∝1/Re 极限为 2.5，均非 2.4；文献亦无该闭合式出处，2.4 疑似为「落在生物实测区间 2.0–2.75」而构造的中间值。故本文档以严格推导的 α_local 替换之，α_eff 降级为「待验证猜想」，不得写入论文。')

para('2.6.7 配套判据（协议 v5）：', bold=True)
bullet('α*(β) 必须单调下降，非单调即实现有 bug', bold_prefix='C4′ ')
bullet('β=0 时 α* 必须回到 3.00 ± 0.05（Murray 回归不变式）', bold_prefix='C5′ ')
bullet('J1/J2/J3 × 伪分叉计/不计 共 6 种组合下，「树 vs 对照」方向必须同号，不同号则结论强制 CONDITIONAL', bold_prefix='C6′ ')

# ============================================================ §3
h2('3. 所有实验的影响因素（按重要性分级）')

h3('3.1 实验清单（§5）')
table = doc.add_table(rows=1, cols=4)
table.style = 'Light Grid Accent 1'
table.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr = table.rows[0].cells
for i, t in enumerate(['编号', '实验', '操纵的变量', '核心结论']):
    hdr[i].text = t
    for p in hdr[i].paragraphs:
        for r in p.runs:
            _set(r, size=9.5, bold=True)
rows_data = [
    ('§5.2', '单热源对比', '拓扑（树 vs 直通道）、等占用', 'T_max 逐位相同，树压降高 310×'),
    ('§5.3', '多热源等钉住', '拓扑（树 vs 径向）、预算、布局', '树比径向低 0.90–4.63°C，压降比最高 122.1×'),
    ('§5.4', '多热源等总占用（C5）', '拓扑（树 vs 径向 vs 格状）、最严口径', '格状不劣于树，压降低 2–3 数量级'),
    ('§5.5.1', '等压降材料代价', '公平口径（等压降）', '树材料是格状几倍到两数量级'),
    ('§5.5.2', '非均匀功率+节距', '功率比、节距 pitch', '树自适应性有条件'),
    ('§5.5.3', '有限对流边界', 'hconv', '方向不变'),
    ('§5.5.4', '5 芯片布局为何剔除', '源块几何（17×17/芯片）', '角块与中心块重叠，融成 1381 格，N4b 门排除'),
    ('§5.6', '约束驱动生成器', 'C1/C2/C3、ttol', '4–10 前沿点，0.1K 省 21% 压降'),
    ('Fig.4', '间距扫描（regime map）', '热源间距 d=6–30mm', '树对径向优势随间距衰减'),
]
for row in rows_data:
    cells = table.add_row().cells
    for i, val in enumerate(row):
        cells[i].text = val
        for p in cells[i].paragraphs:
            for r in p.runs:
                _set(r, size=9)

h3('3.2 影响因素分级')
para('分级标准：按「是否改变结论方向」划分——一级改变方向/决定结论是否成立，二级改变优势幅度或适用域边界，三级仅做稳健性验证。', italic=True)

para('一级因素（决定结论方向，反转级）：', bold=True, color=RGBColor(0xB0, 0x00, 0x00))
bullet('对照拓扑类型（直通道 / 径向 / 格状）——树 vs 径向「全胜」，树 vs 格状「全劣」，方向随对照反转。')
bullet('公平口径（等钉住 / 等材料 / 等总占用）——从「树优」（等钉住）反转到「树劣」（等总占用 C5）。')
bullet('热源数量（单 / 多）——单热源树无任何优势（源区饱和），多热源才有讨论空间。')

para('二级因素（改变优势幅度 / 适用域边界）：', bold=True, color=RGBColor(0xC0, 0x60, 0x00))
bullet('材料预算 b（节点预算 400–1300）——树优势随预算漂移，是全文最核心的「未受控自由参数」。')
bullet('热源间距 d（6–30mm）——树对径向优势随间距增大而衰减（regime map 的适用域）。')
bullet('功率分布（均匀 / 非均匀 1:2:3 等）——树的自适应性不是稳健结论，是有条件的。')
bullet('芯片布局（2/3/4/5）——5 芯片在预算不足时 C1 门拒绝（树无法进入全部 footprint）。')
bullet('泵扬程约束 C3——决定可行集边界，最冷设计距泵极限仅 1.2–1.7×。')

para('三级因素（稳健性验证，不改变方向）：', bold=True, color=RGBColor(0x00, 0x60, 0x00))
bullet('边界条件（理想定温汇 / 有限对流 hconv）——只抬升整体温度水平，不改变方向。')
bullet('流量（钉住 / 有限流量共轭）——钉住是 Q→∞ 极限，有限流量不改变方向。')
bullet('接头损失 K——只会进一步拉大树 vs 对照的压降差距（强化负结论）。')
bullet('网格分辨率——数值正确性验证，不影响方向。')
bullet('冷却液物性（黏度取 20°C、温度口径）——引入约 12.6% 压降偏差，不影响方向。')

h3('3.3 影响因素 → 结论方向的映射（核心洞察）')
para('结论「树优」是否成立？')
bullet('对照 = 径向 且 口径 = 等钉住      →  树优（但代价是压降高 1–2 数量级）')
bullet('对照 = 径向 且 口径 = 等总占用 C5 →  树仅微优（0.2–0.7°C），压降高 3 个数量级')
bullet('对照 = 格状 且 口径 = 等总占用    →  树被支配（温度持平或更差，压降低 3 个数量级）')
bullet('热源 = 单热源                     →  树无优势（源区饱和，拓扑无优化空间）')

# ============================================================ §4
h2('4. 系统结论：论文究竟在干什么')
bullet('它不是一篇「树更优」的论文，而是一篇「树什么时候更优、以及代价是多少」的裁决装置论文。')
bullet('它的可交付物是两个方法贡献：三重公平比较协议（解决「预算驱动的结论反转」）+ 约束驱动生成器（把预算从自由参数改成约束求解）。')
bullet('它的全部核心结论都是「条件化」的：树优不优，取决于「对照类型 + 公平口径 + 热源数量」这三个一级因素，而不是树本身。')
bullet('它的硬伤不是公式（公式都是现成的物理定律），而是：① 叙事停留在「负结果」，没有把「有效适用域」升维成正面 impact；② 英文版与中文版结构分叉（「设而不求 + 协议 v5」只在中文版）；③ α_eff 的 2.4 极限无推导支撑（已替换为 α_local = 6(1+β)/(2+3β)）；④ 3D 图已做但「未来工作」文字仍说没做。')

para('')
para('本文档由公式推导 + 影响因素系统梳理生成，作为理解论文全貌与后续补强重投的基准参考。', italic=True, color=RGBColor(0x80, 0x80, 0x80))

# ============================================================ 保存
out = r'd:\解释token\heat_tree\论文公式推导与影响因素系统梳理.docx'
doc.save(out)
print('已生成：', out)
