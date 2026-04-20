"""
将毕业设计论文 Markdown 转换为格式规范的 Word (.docx) 文件。

用法:
    python tools/md_to_docx.py docs/毕业设计论文_v1.md docs/毕业设计论文_v1.docx

功能:
- 标题1-4 → Word 标题样式（带自动编号兼容）
- 正文段落（含缩进）
- 有序/无序列表
- 表格（| 分隔符语法）
- 代码块（``` 围栏）
- 占位图注释行（[占位图 X-X]）→ 灰色占位框
- 粗体 **text** 内联渲染
- 公式行（含 $$ 或 \tag）→ 等宽段落保留
- 分隔线 --- → 段落分隔
- 页眉（学校/题目）与页脚（页码）
"""

import re
import sys
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


# ─────────────────────────── 辅助函数 ────────────────────────────

def set_font(run, name_cn="宋体", name_en="Times New Roman", size_pt=12, bold=False,
             italic=False, color=None):
    """同时设置中英文字体、字号、粗体、斜体、颜色。"""
    run.font.name = name_en
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color
    # 设置中文字体（东亚字体 rFonts）
    r = run._r
    rPr = r.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:eastAsia'), name_cn)
    rFonts.set(qn('w:ascii'), name_en)
    rFonts.set(qn('w:hAnsi'), name_en)
    existing = rPr.find(qn('w:rFonts'))
    if existing is not None:
        rPr.remove(existing)
    rPr.insert(0, rFonts)


def set_paragraph_format(para, first_indent_chars=2, space_before=0,
                          space_after=6, line_spacing_pt=None,
                          alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
    """设置段落格式：首行缩进、段前/后间距、行距、对齐。"""
    pf = para.paragraph_format
    pf.first_line_indent = Pt(12 * first_indent_chars)  # 12pt ≈ 一个字符宽度
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    if line_spacing_pt:
        pf.line_spacing = Pt(line_spacing_pt)
    pf.alignment = alignment


def add_heading(doc, text, level):
    """添加标题段落（Word 内置 Heading 样式）。"""
    style_map = {1: 'Heading 1', 2: 'Heading 2', 3: 'Heading 3', 4: 'Heading 4'}
    style = style_map.get(level, 'Heading 4')
    para = doc.add_paragraph(style=style)
    run = para.add_run(text)

    size_map = {1: 16, 2: 14, 3: 13, 4: 12}
    bold_map = {1: True, 2: True, 3: True, 4: True}
    font_map = {1: "黑体", 2: "黑体", 3: "黑体", 4: "宋体"}

    set_font(run, name_cn=font_map[level], name_en="Times New Roman",
             size_pt=size_map[level], bold=bold_map[level])

    pf = para.paragraph_format
    pf.first_line_indent = Pt(0)
    pf.space_before = Pt({1: 18, 2: 12, 3: 9, 4: 6}[level])
    pf.space_after = Pt({1: 12, 2: 9, 3: 6, 4: 4}[level])
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    return para


def add_body_paragraph(doc, text, first_indent=2):
    """添加正文段落（宋体/Times New Roman 12pt，首行缩进2字符）。"""
    para = doc.add_paragraph()
    _apply_inline(para, text, size_pt=12)
    set_paragraph_format(para, first_indent_chars=first_indent,
                         space_before=0, space_after=4, line_spacing_pt=20)
    return para


def add_caption(doc, text):
    """图/表标注行（居中，宋体10pt）。"""
    para = doc.add_paragraph()
    run = para.add_run(text)
    set_font(run, name_cn="宋体", name_en="Times New Roman", size_pt=10)
    para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_before = Pt(2)
    para.paragraph_format.space_after = Pt(8)
    para.paragraph_format.first_line_indent = Pt(0)
    return para


def add_placeholder_box(doc, caption_text):
    """插入灰色占位图框 + 图标注。"""
    # 占位段落（灰底、居中）
    para = doc.add_paragraph()
    run = para.add_run(f"[ {caption_text} ]")
    set_font(run, name_cn="黑体", name_en="Arial", size_pt=11,
             color=RGBColor(0x80, 0x80, 0x80))
    para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_before = Pt(6)
    para.paragraph_format.space_after = Pt(2)
    para.paragraph_format.first_line_indent = Pt(0)
    # 给段落加灰色底纹
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), 'EEEEEE')
    pPr.append(shd)
    return para


def add_code_block(doc, code_text):
    """添加代码块（Courier New 9pt，浅灰背景）。"""
    for line in code_text.split('\n'):
        para = doc.add_paragraph()
        run = para.add_run(line if line else ' ')
        run.font.name = 'Courier New'
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x1E, 0x1E, 0x1E)
        para.paragraph_format.first_line_indent = Pt(0)
        para.paragraph_format.left_indent = Cm(0.5)
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(0)
        # 浅灰背景
        pPr = para._p.get_or_add_pPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'F5F5F5')
        pPr.append(shd)


def add_formula_line(doc, text):
    """公式行：等宽字体居中显示。"""
    para = doc.add_paragraph()
    run = para.add_run(text.strip())
    run.font.name = 'Cambria Math'
    run.font.size = Pt(11)
    para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.first_line_indent = Pt(0)
    para.paragraph_format.space_before = Pt(4)
    para.paragraph_format.space_after = Pt(4)
    return para


def add_table(doc, header_row, data_rows):
    """插入带表头的表格（三线表风格）。"""
    col_count = len(header_row)
    table = doc.add_table(rows=1 + len(data_rows), cols=col_count)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # 表头
    hdr_cells = table.rows[0].cells
    for i, cell_text in enumerate(header_row):
        cell_text = cell_text.strip().strip('*')
        hdr_cells[i].text = ''
        run = hdr_cells[i].paragraphs[0].add_run(cell_text)
        set_font(run, name_cn="黑体", name_en="Times New Roman",
                 size_pt=10, bold=True)
        hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 数据行
    for row_idx, row_data in enumerate(data_rows):
        row_cells = table.rows[row_idx + 1].cells
        for col_idx, cell_text in enumerate(row_data):
            cell_text = cell_text.strip()
            row_cells[col_idx].text = ''
            run = row_cells[col_idx].paragraphs[0].add_run(cell_text)
            set_font(run, name_cn="宋体", name_en="Times New Roman", size_pt=9)
            row_cells[col_idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 表格上下加空行
    doc.add_paragraph()
    return table


def _apply_inline(para, text, size_pt=12, base_bold=False):
    """处理行内粗体 **text** 及普通文本，添加到段落。"""
    # 拆分 **bold** 片段
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = para.add_run(part[2:-2])
            set_font(run, name_cn="宋体", name_en="Times New Roman",
                     size_pt=size_pt, bold=True)
        else:
            if part:
                run = para.add_run(part)
                set_font(run, name_cn="宋体", name_en="Times New Roman",
                         size_pt=size_pt, bold=base_bold)


def add_list_item(doc, text, ordered=False, number=1, level=0):
    """添加列表项。"""
    para = doc.add_paragraph()
    indent_cm = 0.5 + level * 0.5
    if ordered:
        prefix = f"{number}. "
    else:
        prefix = "• "
    run_prefix = para.add_run(prefix)
    set_font(run_prefix, name_cn="宋体", name_en="Times New Roman", size_pt=11)
    _apply_inline(para, text, size_pt=11)
    para.paragraph_format.first_line_indent = Pt(0)
    para.paragraph_format.left_indent = Cm(indent_cm)
    para.paragraph_format.space_before = Pt(1)
    para.paragraph_format.space_after = Pt(1)
    return para


def add_page_number(doc):
    """在页脚中添加居中页码。"""
    section = doc.sections[0]
    footer = section.footer
    para = footer.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run()
    # 插入域代码 PAGE
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = 'PAGE'
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'end')
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'


def setup_page(doc):
    """设置A4页面、页边距。"""
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.5)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)


def add_title_page(doc, title, author, advisor, major, college, date):
    """生成封面页。"""
    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_paragraph()

    p_title = doc.add_paragraph()
    run = p_title.add_run(title)
    set_font(run, name_cn="黑体", name_en="Times New Roman", size_pt=18, bold=True)
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_after = Pt(36)
    p_title.paragraph_format.first_line_indent = Pt(0)

    for label, value in [
        ("学生姓名", author),
        ("指导教师", advisor),
        ("专业名称", major),
        ("所在学院", college),
        ("完成日期", date),
    ]:
        p = doc.add_paragraph()
        run_label = p.add_run(f"{label}：")
        set_font(run_label, name_cn="宋体", name_en="Times New Roman",
                 size_pt=14, bold=True)
        run_value = p.add_run(value)
        set_font(run_value, name_cn="宋体", name_en="Times New Roman",
                 size_pt=14, bold=False)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.first_line_indent = Pt(0)

    doc.add_page_break()


# ─────────────────────────── 主解析逻辑 ────────────────────────────

def parse_table_line(line):
    """解析 | a | b | c | 格式的表格行，返回单元格列表。"""
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|'):
        line = line[:-1]
    return [cell.strip() for cell in line.split('|')]


def is_table_separator(line):
    """判断是否是表格分隔行（|:---|:---:|...）。"""
    stripped = line.strip().replace(' ', '')
    return bool(re.match(r'^[|\-:]+$', stripped)) and '|' in stripped and '-' in stripped


def convert_md_to_docx(md_path: str, docx_path: str):
    doc = Document()
    setup_page(doc)
    add_page_number(doc)

    lines = Path(md_path).read_text(encoding='utf-8').splitlines()

    # 状态机
    in_code_block = False
    code_lang = ''
    code_lines = []
    in_table = False
    table_header = []
    table_data_rows = []
    ordered_counters = {}   # indent_level -> count
    skip_cover_meta = True  # 跳过封面 | | | 表格

    # 封面元信息（从 MD 文件顶部的 | | | 表格中读取）
    cover_info = {
        "题目": "基于Web的Landsat 8遥感影像在线预处理系统设计与实现",
        "学生姓名": "李旭东",
        "指导教师": "（待填写）",
        "专业名称": "（待填写）",
        "所在学院": "（待填写）",
        "完成日期": "2026年4月",
    }

    # 生成封面
    add_title_page(
        doc,
        title=cover_info["题目"],
        author=cover_info["学生姓名"],
        advisor=cover_info["指导教师"],
        major=cover_info["专业名称"],
        college=cover_info["所在学院"],
        date=cover_info["完成日期"],
    )

    i = 0
    while i < len(lines):
        line = lines[i]
        raw = line

        # ── 代码块 ──────────────────────────────────────
        if line.strip().startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_lang = line.strip()[3:].strip()
                code_lines = []
            else:
                in_code_block = False
                add_code_block(doc, '\n'.join(code_lines))
                doc.add_paragraph()  # 代码块后空行
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # ── 跳过封面信息区的 | | | 元表格 ───────────────
        if skip_cover_meta and re.match(r'^\|.*\|.*\|', line):
            # 封面元表格结束标志：出现第一个正式 # 标题后停止跳过
            i += 1
            continue

        # ── 标题 ─────────────────────────────────────────
        heading_match = re.match(r'^(#{1,4})\s+(.*)', line)
        if heading_match:
            skip_cover_meta = False
            # 如果正在收集表格，先输出
            if in_table and table_header:
                add_table(doc, table_header, table_data_rows)
                in_table = False; table_header = []; table_data_rows = []

            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()

            # 目录标题直接跳过（Word 可自动生成目录）
            if text.strip() in ('目  录', '目录'):
                # 插入提示语
                p = doc.add_paragraph()
                run = p.add_run('（此处请在 Word 中通过"引用 → 目录"自动生成目录）')
                set_font(run, name_cn="宋体", name_en="Times New Roman",
                         size_pt=10, color=RGBColor(0x80, 0x80, 0x80))
                p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.first_line_indent = Pt(0)
                doc.add_page_break()
                i += 1
                continue

            # 摘要/Abstract/参考文献/附录 等视为 Heading 1
            if level == 1 and text in ('摘  要', '摘要', 'Abstract', '参考文献', '附录'):
                add_heading(doc, text, 1)
                if text in ('摘  要', '摘要', 'Abstract'):
                    pass  # 不分页
                else:
                    pass
            elif level == 1:
                doc.add_page_break()
                add_heading(doc, text, level)
            else:
                add_heading(doc, text, level)
            i += 1
            continue

        # ── 分隔线 ───────────────────────────────────────
        if re.match(r'^---+\s*$', line.strip()):
            # 如果正在收集表格，先输出
            if in_table and table_header:
                add_table(doc, table_header, table_data_rows)
                in_table = False; table_header = []; table_data_rows = []
            i += 1
            continue

        # ── 表格行 ───────────────────────────────────────
        if re.match(r'^\|', line.strip()):
            if is_table_separator(line):
                i += 1
                continue
            cells = parse_table_line(line)
            if not in_table:
                # 第一行是表头
                in_table = True
                table_header = cells
                table_data_rows = []
            else:
                table_data_rows.append(cells)
            i += 1
            continue
        else:
            # 非表格行：如果之前在收集表格，先提交
            if in_table and table_header:
                add_table(doc, table_header, table_data_rows)
                in_table = False; table_header = []; table_data_rows = []

        stripped = line.strip()

        # ── 空行 ─────────────────────────────────────────
        if not stripped:
            i += 1
            continue

        # ── 占位图注释块 ─────────────────────────────────
        # 格式: **[占位图 X-X]** 或 [占位图 X-X]
        ph_match = re.match(r'.*\[占位图\s+([^\]]+)\]', stripped)
        if ph_match:
            caption_id = ph_match.group(1)
            # 向后找 > *图X-X 说明行*
            caption_text = f"占位图 {caption_id}"
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                desc_match = re.match(r'>\s*\*?(图\d+-\d+.*?)\*?', lines[j].strip())
                if desc_match:
                    caption_text = desc_match.group(1).strip().rstrip('）').strip()
                    i = j + 1
                else:
                    i += 1
            else:
                i += 1
            add_placeholder_box(doc, caption_text)
            add_caption(doc, f"（占位：{caption_text}）")
            continue

        # 跳过 > *图... 行（已被占位图处理消耗）
        if re.match(r'^>\s*\*?图\d+-\d+', stripped):
            i += 1
            continue

        # ── blockquote 说明行（非图注） ────────────────────
        if stripped.startswith('>'):
            text_content = stripped.lstrip('> ').strip().strip('*')
            p = doc.add_paragraph()
            run = p.add_run(text_content)
            set_font(run, name_cn="宋体", name_en="Times New Roman",
                     size_pt=10, color=RGBColor(0x55, 0x55, 0x55))
            p.paragraph_format.left_indent = Cm(1.0)
            p.paragraph_format.first_line_indent = Pt(0)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            i += 1
            continue

        # ── 公式行（含 $$ 或 \tag 或 $$...$$） ──────────────
        if '$$' in stripped or r'\tag' in stripped or re.match(r'^\$\$', stripped):
            add_formula_line(doc, stripped)
            i += 1
            continue

        # ── 有序列表 ─────────────────────────────────────
        ol_match = re.match(r'^(\s*)(\d+)\.\s+(.*)', line)
        if ol_match:
            indent = len(ol_match.group(1)) // 2
            number = int(ol_match.group(2))
            text_content = ol_match.group(3)
            add_list_item(doc, text_content, ordered=True,
                          number=number, level=indent)
            i += 1
            continue

        # ── 无序列表（- 或 * 开头，非表格分隔） ──────────────
        ul_match = re.match(r'^(\s*)[-*]\s+(.*)', line)
        if ul_match:
            indent = len(ul_match.group(1)) // 2
            text_content = ul_match.group(2)
            # 跳过纯 --- 或 * 的分隔行（已在上面处理）
            add_list_item(doc, text_content, ordered=False, level=indent)
            i += 1
            continue

        # ── 表格标题行（**表X-X ...**） ───────────────────
        table_title_match = re.match(r'^\*\*(表\d+-\d+[^*]*)\*\*', stripped)
        if table_title_match:
            add_caption(doc, table_title_match.group(1))
            i += 1
            continue

        # ── 诚信声明分页 ─────────────────────────────────
        if '诚信声明' in stripped and stripped.startswith('#'):
            doc.add_page_break()

        # ── 普通正文段落 ─────────────────────────────────
        # 判断是否是摘要/关键词行（无缩进）
        no_indent_prefixes = ('**关键词', '**Keywords', 'Co-Authored',
                              '作者签名', '\\*热红外')
        is_no_indent = any(stripped.startswith(p) for p in no_indent_prefixes)
        first_indent = 0 if is_no_indent else 2

        add_body_paragraph(doc, stripped, first_indent=first_indent)
        i += 1

    # 收尾：若表格还未提交
    if in_table and table_header:
        add_table(doc, table_header, table_data_rows)

    doc.save(docx_path)
    print(f"[OK] 已生成: {docx_path}")


# ─────────────────────────── 入口 ────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) >= 3:
        src = sys.argv[1]
        dst = sys.argv[2]
    else:
        # 默认路径
        base = Path(__file__).parent.parent
        src = str(base / 'docs' / '毕业设计论文_v1.md')
        dst = str(base / 'docs' / '毕业设计论文_v1.docx')

    print(f"源文件 : {src}")
    print(f"目标文件: {dst}")
    convert_md_to_docx(src, dst)
