# -*- coding: utf-8 -*-
"""
国赛论文通用模板引擎
====================
用法:
    from paper_template import PaperTemplate

    paper = PaperTemplate(output_path='论文.docx')

    # 标题
    paper.title('论文标题')

    # 摘要
    paper.abstract('摘要正文，支持 $公式$ 混排')
    paper.keywords('关键词1；关键词2')

    # 章节
    paper.h1('1 问题重述')
    paper.p('纯文本段落')
    paper.pm('支持 $x_{ij}$ 混排的段落')

    # 公式（居中）
    paper.formula('Z = C_{start} + C_{energy}')

    # 三线表
    paper.table(
        headers=['符号', '说明', '单位'],
        data=[('$n$', '节点数', '个'), ('$d_{ij}$', '距离', 'km')],
        italic_cols={0}  # 哪些列需要斜体，默认第0列
    )

    # 图片
    paper.image('path/to/fig.png', caption='图1 收敛曲线')

    # 参考文献
    paper.reference('[1] 作者. 书名[M]. 出版社, 年份.')

    # 保存
    paper.save()

格式说明:
    - $...$ 包裹的内容自动渲染为斜体 Times New Roman
    - 下标: $x_{ij}$ 或 $x_ij$ 都支持
    - 上标: $Z^*$ 或 $Z^{*}$ 都支持
    - LaTeX 符号: $\\Delta$, $\\to$, $\\alpha$ 等自动转 Unicode
    - 纯数字在公式中自动保持正体（如 $500$）
"""

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import re
import os


# ============================================================
#  LaTeX 符号 → Unicode 映射表（按需扩展）
# ============================================================
_LATEX_SYMBOLS = {
    # 希腊字母
    r'\Delta': '\u0394', r'\alpha': '\u03B1', r'\beta': '\u03B2',
    r'\gamma': '\u03B3', r'\theta': '\u03B8', r'\lambda': '\u03BB',
    r'\mu': '\u03BC', r'\sigma': '\u03C3', r'\pi': '\u03C0',
    r'\omega': '\u03C9', r'\Omega': '\u03A9', r'\phi': '\u03C6',
    r'\epsilon': '\u03B5', r'\delta': '\u03B4', r'\eta': '\u03B7',
    r'\kappa': '\u03BA', r'\rho': '\u03C1', r'\tau': '\u03C4',
    r'\chi': '\u03C7', r'\psi': '\u03C8', r'\zeta': '\u03B6',
    # 运算符
    r'\to': '\u2192', r'\rightarrow': '\u2192', r'\leftarrow': '\u2190',
    r'\Rightarrow': '\u21D2', r'\Leftarrow': '\u21D0', r'\infty': '\u221E', r'\sum': '\u2211',
    r'\prod': '\u220F', r'\pm': '\u00B1', r'\times': '\u00D7',
    r'\cdot': '\u00B7', r'\leq': '\u2264', r'\geq': '\u2265',
    r'\neq': '\u2260', r'\approx': '\u2248', r'\in': '\u2208',
    r'\forall': '\u2200', r'\exists': '\u2203', r'\partial': '\u2202',
    r'\nabla': '\u2207', r'\int': '\u222B', r'\cup': '\u222A',
    r'\cap': '\u2229', r'\subset': '\u2282', r'\supset': '\u2283',
    r'\subseteq': '\u2286', r'\supseteq': '\u2287',
    # 括号和分隔符
    r'\{': '{', r'\}': '}', r'\langle': '\u27E8', r'\rangle': '\u27E9',
    # 其他
    r'\cdots': '\u22EF', r'\ldots': '\u2026', r'\vdots': '\u22EE',
    r'\ddots': '\u22F1', r'\mid': '\u2223', r'\parallel': '\u2225',
    r'\neg': '\u00AC', r'\lnot': '\u00AC', r'\land': '\u2227',
    r'\lor': '\u2228', r'\oplus': '\u2295', r'\otimes': '\u2297',
    r'\circ': '\u2218', r'\star': '\u2605', r'\bullet': '\u2022',
    r'\sqrt': '\u221A', r'\angle': '\u2220', r'\degree': '\u00B0',
    r'\perp': '\u22A5', r'\sim': '\u223C', r'\equiv': '\u2261',
    r'\prime': '\u2032', r'\propto': '\u221D',
    # 范数双竖线与不等号短写（须排在 \geq / \leq 之后，避免前缀吞并）
    r'\|': '\u2016', r'\ge': '\u2265', r'\le': '\u2264',
}


def _convert_latex_commands(text):
    """预处理LaTeX带参数命令（在符号替换前执行）"""
    import re
    # \hat{X} → X + 组合帽子符号
    text = re.sub(r'\\hat\{([^}]+)\}', lambda m: m.group(1) + '\u0302', text)
    # \tilde{X} → X + 组合波浪号
    text = re.sub(r'\\tilde\{([^}]+)\}', lambda m: m.group(1) + '\u0303', text)
    # \bar{X} → X + 组合上划线
    text = re.sub(r'\\bar\{([^}]+)\}', lambda m: m.group(1) + '\u0304', text)
    # \vec{X} → X + 组合箭头
    text = re.sub(r'\\vec\{([^}]+)\}', lambda m: m.group(1) + '\u20D7', text)
    # \dot{X} → X + 单点上标点
    text = re.sub(r'\\dot\{([^}]+)\}', lambda m: m.group(1) + '\u0307', text)
    # \ddot{X} → X + 双点上标点
    text = re.sub(r'\\ddot\{([^}]+)\}', lambda m: m.group(1) + '\u0308', text)
    # \frac{a}{b} → a/b
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1/\2', text)
    # 间距/空白命令
    text = text.replace(r'\,', '\u2009')      # 细空格
    text = text.replace(r'\;', '\u2005')      # 四分空格
    text = text.replace(r'\quad', '\u2003')   # 全角空格
    text = text.replace(r'\qquad', '\u2003\u2003')
    # \ln → ln
    text = text.replace(r'\ln', 'ln')
    # \sqrt{...} → √(...)
    text = re.sub(r'\\sqrt\{([^}]+)\}', r'√(\1)', text)
    # \min → min (普通文本)
    text = text.replace(r'\min', 'min')
    # \max → max
    text = text.replace(r'\max', 'max')
    # \log → log
    text = text.replace(r'\log', 'log')
    # \exp → exp
    text = text.replace(r'\exp', 'exp')
    # \sin, \cos, \tan
    text = text.replace(r'\sin', 'sin')
    text = text.replace(r'\cos', 'cos')
    text = text.replace(r'\tan', 'tan')
    # \lim → lim
    text = text.replace(r'\lim', 'lim')
    # \text{...} → 内容
    text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)
    # \mathrm{...} → 内容
    text = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', text)
    # \mathbf{...} → 内容
    text = re.sub(r'\\mathbf\{([^}]+)\}', r'\1', text)
    return text


def _convert_latex_symbols(text):
    text = _convert_latex_commands(text)
    for latex, uni in _LATEX_SYMBOLS.items():
        text = text.replace(latex, uni)
    return text


def _set_font(run, name='宋体', size=10.5, bold=False, italic=False):
    """设置字体：中文用 name，西文自动分离为 Times New Roman（修复 #8）
    宋体/黑体仅作用于 w:eastAsia；w:ascii 与 w:hAnsi 用西文字体，
    保证英文与数字显示为 Times New Roman 而非中文字体的西文字形。
    """
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), name)
    western = 'Times New Roman' if name in ('宋体', '黑体') else name
    rFonts.set(qn('w:ascii'), western)
    rFonts.set(qn('w:hAnsi'), western)


def _render_formula(para, formula, font_size=10.5):
    """渲染公式内容（已去掉$），支持下标/上标/数字正体"""
    formula = _convert_latex_symbols(formula)
    i, buf = 0, ''

    def _is_num(s):
        c = s.replace(',', '').replace('.', '').replace('%', '').strip()
        return bool(c) and all(ch in '0123456789' for ch in c)

    def flush():
        nonlocal buf
        if buf:
            run = para.add_run(buf)
            _set_font(run, 'Times New Roman', font_size, italic=not _is_num(buf))
            buf = ''

    while i < len(formula):
        ch = formula[i]
        if ch == '_' and i + 1 < len(formula) and formula[i + 1] == '{':
            flush()
            j = formula.index('}', i + 2)
            run = para.add_run(formula[i + 2:j])
            _set_font(run, 'Times New Roman', font_size - 2, italic=True)
            vp = run._element.get_or_add_rPr()
            va = OxmlElement('w:vertAlign')
            va.set(qn('w:val'), 'subscript')
            vp.append(va)
            i = j + 1
        elif ch == '_' and i + 1 < len(formula) and formula[i + 1] not in '{_':
            flush()
            j = i + 1
            while j < len(formula) and (formula[j].isalpha() or formula[j].isdigit()):
                j += 1
            sub = formula[i + 1:j]
            if sub:
                run = para.add_run(sub)
                _set_font(run, 'Times New Roman', font_size - 2, italic=True)
                vp = run._element.get_or_add_rPr()
                va = OxmlElement('w:vertAlign')
                va.set(qn('w:val'), 'subscript')
                vp.append(va)
                i = j
            else:
                buf += ch; i += 1
        elif ch == '^' and i + 1 < len(formula) and formula[i + 1] == '{':
            flush()
            j = formula.index('}', i + 2)
            run = para.add_run(formula[i + 2:j])
            _set_font(run, 'Times New Roman', font_size - 2, italic=True)
            vp = run._element.get_or_add_rPr()
            va = OxmlElement('w:vertAlign')
            va.set(qn('w:val'), 'superscript')
            vp.append(va)
            i = j + 1
        elif ch == '^' and i + 1 < len(formula) and formula[i + 1] not in '{_':
            flush()
            run = para.add_run(formula[i + 1])
            _set_font(run, 'Times New Roman', font_size - 2, italic=True)
            vp = run._element.get_or_add_rPr()
            va = OxmlElement('w:vertAlign')
            va.set(qn('w:val'), 'superscript')
            vp.append(va)
            i += 2
        elif ch == '\\' and i + 1 < len(formula) and formula[i + 1] in '_%&#$':
            # 转义字符：\_ 输出字面下划线（不触发下标），\% 输出百分号等
            buf += formula[i + 1]; i += 2
        elif ch == '\\' and i + 1 < len(formula) and formula[i + 1] == ' ':
            buf += '\u00A0'; i += 2
        elif ch == '\\' and i + 1 < len(formula):
            buf += ch; i += 1
        else:
            buf += ch; i += 1
    flush()


def _add_mixed(para, text, font_name='宋体', font_size=10.5):
    """混合格式：$$...$$ / $...$ 公式，`...` 等宽代码，**...** 加粗，其余正体"""
    bold = False
    for part in re.split(r'(\$\$[^$]+\$\$|\$[^$]+\$|`[^`]+`|\*\*)', text):
        if not part:
            continue
        if part == '**':
            bold = not bold
            continue
        if part.startswith('$$') and part.endswith('$$') and len(part) > 4:
            n0 = len(para.runs)
            _render_formula(para, part[2:-2], font_size)
            if bold:
                for r in para.runs[n0:]:
                    r.font.bold = True
        elif part.startswith('$') and part.endswith('$') and len(part) > 2:
            n0 = len(para.runs)
            _render_formula(para, part[1:-1], font_size)
            if bold:
                for r in para.runs[n0:]:
                    r.font.bold = True
        elif part.startswith('`') and part.endswith('`') and len(part) > 2:
            run = para.add_run(part[1:-1])
            _set_font(run, 'Consolas', font_size, bold=bold)
        else:
            run = para.add_run(part)
            _set_font(run, font_name, font_size, bold=bold)


# ============================================================
#  论文模板类
# ============================================================
class PaperTemplate:
    """国赛论文通用模板

    参数:
        output_path: 输出文件路径
        margins: 页面边距 (top, bottom, left, right) 单位cm，默认国赛标准
    """

    def __init__(self, output_path, margins=(2.54, 2.54, 3.17, 3.17)):
        self.doc = Document()
        self.output_path = output_path
        for sec in self.doc.sections:
            sec.top_margin = Cm(margins[0])
            sec.bottom_margin = Cm(margins[1])
            sec.left_margin = Cm(margins[2])
            sec.right_margin = Cm(margins[3])
        self._add_page_number()
        self._fig_count = 0
        self._table_count = 0

    def _add_page_number(self):
        """页脚中部插入 PAGE 域页码（修复 #1，从1开始连续编号）"""
        for sec in self.doc.sections:
            footer = sec.footer
            p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            fld_begin = OxmlElement('w:fldChar')
            fld_begin.set(qn('w:fldCharType'), 'begin')
            instr = OxmlElement('w:instrText')
            instr.set(qn('xml:space'), 'preserve')
            instr.text = 'PAGE'
            fld_end = OxmlElement('w:fldChar')
            fld_end.set(qn('w:fldCharType'), 'end')
            run._element.append(fld_begin)
            run._element.append(instr)
            run._element.append(fld_end)
            run.font.size = Pt(9)
            run.font.name = 'Times New Roman'

    # ---- 标题 ----
    def title(self, text):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        _set_font(r, '黑体', 22, bold=True)
        p.paragraph_format.space_after = Pt(20)

    # ---- 摘要 ----
    def abstract(self, text):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run('摘  要')
        _set_font(r, '黑体', 14, bold=True)
        p.paragraph_format.space_after = Pt(12)
        self.pm(text)

    def keywords(self, text):
        p = self.doc.add_paragraph()
        r = p.add_run('关键词：')
        _set_font(r, '黑体', 10.5, bold=True)
        r2 = p.add_run(text)
        _set_font(r2, '宋体', 10.5)
        p.paragraph_format.space_before = Pt(12)

    # ---- 标题层级 ----
    def h1(self, text):
        """一级标题：黑体 15pt 居中"""
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_mixed(p, text, '黑体', 15)
        for r in p.runs:
            r.font.bold = True
        p.paragraph_format.space_before = Pt(24)
        p.paragraph_format.space_after = Pt(12)

    def h2(self, text):
        """二级标题：黑体 12pt 左对齐"""
        p = self.doc.add_paragraph()
        _add_mixed(p, text, '黑体', 12)
        for r in p.runs:
            r.font.bold = True
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)

    def h3(self, text):
        """三级标题：黑体 10.5pt 左对齐"""
        p = self.doc.add_paragraph()
        _add_mixed(p, text, '黑体', 10.5)
        for r in p.runs:
            r.font.bold = True
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(3)

    # ---- 正文 ----
    def p(self, text, indent=True):
        """纯文本段落（宋体 10.5pt），同时支持 $...$ 公式混排"""
        p = self.doc.add_paragraph()
        _add_mixed(p, text, '宋体', 10.5)
        p.paragraph_format.line_spacing = 1.5
        if indent:
            p.paragraph_format.first_line_indent = Cm(0.74)

    def pm(self, text, indent=True):
        """混合格式段落（支持 $公式$ 斜体）"""
        p = self.doc.add_paragraph()
        _add_mixed(p, text)
        p.paragraph_format.line_spacing = 1.5
        if indent:
            p.paragraph_format.first_line_indent = Cm(0.74)

    # ---- 公式 ----
    def formula(self, text, label=None):
        """居中公式（整段作为公式渲染）

        参数:
            text: 公式内容，如 'Z = C_{start} + C_{energy}'
            label: 公式编号，如 '(1)'，显示在右侧
        """
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # 公式编号右对齐制表位（修复 #4：右边距 21-6.34=14.66cm 处）
        p.paragraph_format.tab_stops.add_tab_stop(Cm(14.66), WD_TAB_ALIGNMENT.RIGHT)
        # 整段都作为公式处理（不需要$包裹），走 _render_formula
        _render_formula(p, text, font_size=11)
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(6)
        if label:
            run = p.add_run(f'\t{label}')
            _set_font(run, 'Times New Roman', 10.5)

    # ---- 三线表 ----
    def table(self, headers, data, italic_cols=None, caption=None):
        """三线表

        参数:
            headers: 表头列表，如 ['符号', '说明', '单位']
            data: 数据列表，每行一个 tuple
            italic_cols: 需要斜体的列索引集合，默认 {0}（第0列）
            caption: 表标题，如 '表1 符号说明'
        """
        if italic_cols is None:
            italic_cols = {0}

        if caption:
            p = self.doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _add_mixed(p, caption, '黑体', 10.5)
            for r in p.runs:
                r.font.bold = True
            p.paragraph_format.space_after = Pt(6)

        tbl = self.doc.add_table(rows=1 + len(data), cols=len(headers))

        # 边框设置
        tblPr = tbl._tbl.tblPr if tbl._tbl.tblPr is not None else OxmlElement('w:tblPr')
        borders = OxmlElement('w:tblBorders')
        for name, sz in [('top', '12'), ('bottom', '12')]:
            b = OxmlElement(f'w:{name}')
            b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), sz)
            b.set(qn('w:space'), '0'); b.set(qn('w:color'), '000000')
            borders.append(b)
        for name in ['left', 'right', 'insideH', 'insideV']:
            b = OxmlElement(f'w:{name}')
            b.set(qn('w:val'), 'none'); b.set(qn('w:sz'), '0')
            b.set(qn('w:space'), '0'); b.set(qn('w:color'), '000000')
            borders.append(b)
        tblPr.append(borders)

        # 表头
        for i, h in enumerate(headers):
            cell = tbl.rows[0].cells[i]
            cell.text = ''
            pa = cell.paragraphs[0]
            pa.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _add_mixed(pa, h, '黑体', 10.5)
            for r in pa.runs:
                r.font.bold = True
            tcPr = cell._tc.get_or_add_tcPr()
            tcB = OxmlElement('w:tcBorders')
            bb = OxmlElement('w:bottom')
            bb.set(qn('w:val'), 'single'); bb.set(qn('w:sz'), '4')
            bb.set(qn('w:space'), '0'); bb.set(qn('w:color'), '000000')
            tcB.append(bb); tcPr.append(tcB)

        # 数据行
        for ri, row in enumerate(data, 1):
            for ci, txt in enumerate(row):
                cell = tbl.rows[ri].cells[ci]
                cell.text = ''
                pa = cell.paragraphs[0]
                if ci == 0:
                    pa.alignment = WD_ALIGN_PARAGRAPH.LEFT
                elif ci == len(headers) - 1:
                    pa.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                else:
                    pa.alignment = WD_ALIGN_PARAGRAPH.CENTER
                has_cn = any('\u4e00' <= ch <= '\u9fff' for ch in txt)
                has_formula = '$' in txt
                if ci in italic_cols or has_formula:
                    # 包含 $...$ 公式或需要斜体的列，统一使用混合格式渲染
                    font_name = '宋体' if has_cn else 'Times New Roman'
                    _add_mixed(pa, txt, font_name, 10.5)
                elif has_cn:
                    _add_mixed(pa, txt, '宋体', 10.5)
                else:
                    _add_mixed(pa, txt, 'Times New Roman', 10.5)
        return tbl

    # ---- 图片 ----
    def image(self, path, caption=None, width_cm=None):
        """插入图片

        参数:
            path: 图片文件路径
            caption: 图标题，如 '图1 收敛曲线'
            width_cm: 图片宽度（cm），不传则自适应
        """
        if not os.path.exists(path):
            print(f'[警告] 图片不存在: {path}')
            return
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        pic = run.add_picture(path)
        if width_cm:
            from docx.shared import Emu
            # 必须设在 InlineShape 上：python-docx 的 Run 无 width 属性，
            # 赋值到 run 会静默丢失，导致图宽恒等于「像素/文件内dpi」。
            pic.width = Emu(int(width_cm * 360000))
        p.paragraph_format.space_after = Pt(6)
        if caption:
            cp = self.doc.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _add_mixed(cp, caption, '黑体', 10.5)
            cp.paragraph_format.space_after = Pt(12)

    # ---- 参考文献 ----
    def reference(self, text):
        p = self.doc.add_paragraph()
        r = p.add_run(text)
        _set_font(r, '宋体', 9)
        p.paragraph_format.line_spacing = 1.25

    # ---- 编号自检 ----
    def check_numbering(self):
        """检查图/表编号：独立段落题注作为编号来源（连续性/唯一性），
        正文引用单独核对其存在性。避免把"如图1所示"误计为编号。
        """
        cap_fig, cap_tbl = [], []
        paras = list(self.doc.paragraphs)
        for t in self.doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    paras.extend(cell.paragraphs)
        full_text = '\n'.join(p_.text for p_ in paras)
        for p_ in paras:
            t = p_.text.strip()
            m = re.match(r'^图(\d+)\s', t)
            if m:
                cap_fig.append(int(m.group(1)))
            m = re.match(r'^表(\d+)\s', t)
            if m:
                cap_tbl.append(int(m.group(1)))
        for label, caps in [('图', cap_fig), ('表', cap_tbl)]:
            if not caps:
                print(f'[自检] 未发现{label}题注')
                continue
            missing = set(range(min(caps), max(caps) + 1)) - set(caps)
            if missing:
                print(f'[警告] {label}编号缺失: {sorted(missing)}')
            dups = sorted({n for n in caps if caps.count(n) > 1})
            if dups:
                print(f'[警告] {label}题注重复: {dups}')
            unref = [n for n in caps
                     if len(re.findall(label + str(n) + r'(?!\d)', full_text)) < 2]
            if unref:
                print(f'[警告] {label}{unref} 在正文中未被引用（孤图孤表，一票降档）')
        print('[自检] 图题注:', sorted(cap_fig), '表题注:', sorted(cap_tbl))

    # ---- 保存 ----
    def save(self):
        os.makedirs(os.path.dirname(self.output_path) or '.', exist_ok=True)
        self.doc.save(self.output_path)
        print(f'论文已保存至: {self.output_path}')
        return self.output_path
