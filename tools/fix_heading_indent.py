from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt


ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "output" / "doc" / "基于Web的Landsat8遥感影像在线预处理系统-内容丰富版.docx"


def main() -> None:
    doc = Document(DOCX)
    changed = 0
    for paragraph in doc.paragraphs:
        if not paragraph.style.name.startswith("Heading"):
            continue
        text = paragraph.text.strip()
        if not text:
            continue
        pf = paragraph.paragraph_format
        if pf.first_line_indent is not None:
            changed += 1
        pf.first_line_indent = Pt(0)
        pf.left_indent = Pt(0)
        if paragraph.style.name == "Heading 1":
            pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    doc.save(DOCX)
    print(f"heading_indent_fixed={changed}")
    print(DOCX)


if __name__ == "__main__":
    main()
