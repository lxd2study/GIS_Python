from __future__ import annotations

import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "thesis-prep" / "materials" / "高级答辩.pptx"
SLIDES_DIR = ROOT / "output" / "ppt" / "web_relayout_v3" / "slides"
OUTPUT = ROOT / "output" / "ppt" / "基于Web的Landsat8遥感影像在线预处理系统-30页内容丰富统一配色版.pptx"
OPENABLE_OUTPUT = ROOT / "output" / "ppt" / "基于Web的Landsat8遥感影像在线预处理系统-30页内容丰富统一配色版-可打开版.pptx"
BACKUP = ROOT / "output" / "ppt" / "基于Web的Landsat8遥感影像在线预处理系统-30页内容丰富统一配色版-手写XML备份.pptx"

PPT_CX = 12192000
PPT_CY = 6858000

COPY_PARTS = [
    "ppt/theme/theme1.xml",
    "ppt/slideMasters/slideMaster1.xml",
    "ppt/slideMasters/_rels/slideMaster1.xml.rels",
    "ppt/slideLayouts/slideLayout1.xml",
    "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
    "ppt/slideLayouts/slideLayout2.xml",
    "ppt/slideLayouts/_rels/slideLayout2.xml.rels",
    "ppt/presProps.xml",
    "ppt/viewProps.xml",
    "ppt/tableStyles.xml",
]


def xml(text: str) -> bytes:
    return text.encode("utf-8")


def content_types(slide_count: int) -> str:
    slide_overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>
  <Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>
  <Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>
  {slide_overrides}
</Types>'''


def package_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def core_props() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    title = "基于Web的Landsat8遥感影像在线预处理系统-30页内容丰富统一配色版"
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape(title)}</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>'''


def app_props(slide_count: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft PowerPoint</Application>
  <PresentationFormat>Widescreen</PresentationFormat>
  <Slides>{slide_count}</Slides>
</Properties>'''


def template_default_text_style(template_zip: zipfile.ZipFile) -> str:
    presentation = template_zip.read("ppt/presentation.xml").decode("utf-8", errors="ignore")
    match = re.search(r"<p:defaultTextStyle>.*?</p:defaultTextStyle>", presentation, re.S)
    return match.group(0) if match else ""


def presentation_xml(slide_count: int, default_text_style: str) -> str:
    slide_ids = "\n".join(
        f'    <p:sldId id="{255 + i}" r:id="rId{i + 1}"/>'
        for i in range(1, slide_count + 1)
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst>
    <p:sldMasterId id="2147483648" r:id="rId1"/>
  </p:sldMasterIdLst>
  <p:sldIdLst>
{slide_ids}
  </p:sldIdLst>
  <p:sldSz cx="{PPT_CX}" cy="{PPT_CY}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  {default_text_style}
</p:presentation>'''


def presentation_rels(slide_count: int) -> str:
    slide_rels = "\n".join(
        f'  <Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, slide_count + 1)
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
{slide_rels}
  <Relationship Id="rId{slide_count + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>
  <Relationship Id="rId{slide_count + 3}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps" Target="viewProps.xml"/>
  <Relationship Id="rId{slide_count + 4}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>
</Relationships>'''


def slide_xml(index: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/>
          <a:ext cx="0" cy="0"/>
          <a:chOff x="0" y="0"/>
          <a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
      <p:pic>
        <p:nvPicPr>
          <p:cNvPr id="2" name="Slide {index}"/>
          <p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>
          <p:nvPr/>
        </p:nvPicPr>
        <p:blipFill>
          <a:blip r:embed="rId2"/>
          <a:stretch><a:fillRect/></a:stretch>
        </p:blipFill>
        <p:spPr>
          <a:xfrm>
            <a:off x="0" y="0"/>
            <a:ext cx="{PPT_CX}" cy="{PPT_CY}"/>
          </a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        </p:spPr>
      </p:pic>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>'''


def slide_rels(index: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout2.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{index}.png"/>
</Relationships>'''


def write_parts(z: zipfile.ZipFile, template_zip: zipfile.ZipFile, slide_images: Iterable[Path]) -> None:
    slide_images = list(slide_images)
    default_text_style = template_default_text_style(template_zip)

    z.writestr("[Content_Types].xml", xml(content_types(len(slide_images))))
    z.writestr("_rels/.rels", xml(package_rels()))
    z.writestr("docProps/core.xml", xml(core_props()))
    z.writestr("docProps/app.xml", xml(app_props(len(slide_images))))
    z.writestr("ppt/presentation.xml", xml(presentation_xml(len(slide_images), default_text_style)))
    z.writestr("ppt/_rels/presentation.xml.rels", xml(presentation_rels(len(slide_images))))

    for name in COPY_PARTS:
        z.writestr(name, template_zip.read(name))

    for i, image_path in enumerate(slide_images, start=1):
        z.writestr(f"ppt/slides/slide{i}.xml", xml(slide_xml(i)))
        z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", xml(slide_rels(i)))
        z.write(image_path, f"ppt/media/image{i}.png")


def rebuild() -> None:
    if not TEMPLATE.exists():
        raise FileNotFoundError(TEMPLATE)
    slide_images = sorted(SLIDES_DIR.glob("slide-*.png"))
    if len(slide_images) != 30:
        raise RuntimeError(f"Expected 30 slide images, found {len(slide_images)} in {SLIDES_DIR}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists() and not BACKUP.exists():
        shutil.copyfile(OUTPUT, BACKUP)

    for target in (OUTPUT, OPENABLE_OUTPUT):
        with zipfile.ZipFile(TEMPLATE, "r") as template_zip:
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
                write_parts(z, template_zip, slide_images)
        with zipfile.ZipFile(target, "r") as check:
            slide_parts = [
                name
                for name in check.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            ]
            media_parts = [name for name in check.namelist() if name.startswith("ppt/media/")]
            print(f"{target}: slides={len(slide_parts)} media={len(media_parts)} size={target.stat().st_size}")


if __name__ == "__main__":
    rebuild()
