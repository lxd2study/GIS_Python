from __future__ import annotations

import math
import os
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "ppt"
SLIDE_DIR = OUT_DIR / "slides"
PPTX_PATH = OUT_DIR / "基于Web的Landsat8遥感影像在线预处理系统-答辩PPT.pptx"

W, H = 1920, 1080
PPT_CX, PPT_CY = 12192000, 6858000

COLORS = {
    "bg": "#07151f",
    "bg2": "#0a2430",
    "panel": "#102c3a",
    "panel2": "#123847",
    "line": "#2f7182",
    "text": "#f5fbff",
    "muted": "#b7cbd3",
    "accent": "#2fd0b5",
    "accent2": "#5aa9ff",
    "warm": "#f3c969",
    "danger": "#ef8072",
    "white": "#ffffff",
}


def font_path() -> str:
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for item in candidates:
        if Path(item).exists():
            return item
    return ""


FONT = font_path()


def f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    if bold:
        for candidate in [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size=size)
    return ImageFont.truetype(FONT, size=size) if FONT else ImageFont.load_default()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def draw_gradient(draw: ImageDraw.ImageDraw) -> None:
    c1 = hex_to_rgb(COLORS["bg"])
    c2 = hex_to_rgb(COLORS["bg2"])
    for y in range(H):
        t = y / H
        row = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
        draw.line([(0, y), (W, y)], fill=row)


def base_slide(title: str | None = None, section: str | None = None) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)
    draw_gradient(draw)
    draw.ellipse((-260, -220, 520, 520), fill="#0b4250")
    draw.ellipse((1440, 660, 2220, 1420), fill="#0c374c")
    blur = img.filter(ImageFilter.GaussianBlur(38))
    img.paste(blur)
    draw = ImageDraw.Draw(img)
    draw.line((110, 88, 1810, 88), fill=COLORS["line"], width=2)
    if section:
        pill(draw, 110, 48, 280, 82, section, COLORS["accent"], "#06171d", 22)
    if title:
        draw.text((110, 118), title, fill=COLORS["text"], font=f(50, True))
    return img, draw


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        current = ""
        units = para.split(" ") if " " in para else list(para)
        sep = " " if " " in para else ""
        for unit in units:
            trial = unit if not current else current + sep + unit
            if draw.textlength(trial, font=font) <= max_w:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = unit
        if current:
            lines.append(current)
    return lines


def multiline(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str = COLORS["text"],
    max_w: int = 800,
    line_gap: int = 12,
) -> int:
    x, y = xy
    for line in wrap_text(draw, text, font, max_w):
        draw.text((x, y), line, fill=fill, font=font)
        _, h = text_size(draw, line, font)
        y += h + line_gap
    return y


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str | None = None, width: int = 2, r: int = 24) -> None:
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def pill(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, text: str, fill: str, text_fill: str, size: int = 24) -> None:
    draw.rounded_rectangle((x1, y1, x2, y2), radius=(y2 - y1) // 2, fill=fill)
    font = f(size, True)
    tw, th = text_size(draw, text, font)
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2 - 2), text, fill=text_fill, font=font)


def bullets(draw: ImageDraw.ImageDraw, x: int, y: int, items: list[str], max_w: int = 700, size: int = 30, color: str = COLORS["text"]) -> int:
    font = f(size)
    for item in items:
        draw.ellipse((x, y + 8, x + 12, y + 20), fill=COLORS["accent"])
        y = multiline(draw, (x + 30, y), item, font, color, max_w, 10) + 12
    return y


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], fill: str = COLORS["accent2"], width: int = 5) -> None:
    draw.line((start, end), fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    length = 22
    spread = 0.55
    p1 = (end[0] - length * math.cos(angle - spread), end[1] - length * math.sin(angle - spread))
    p2 = (end[0] - length * math.cos(angle + spread), end[1] - length * math.sin(angle + spread))
    draw.polygon([end, p1, p2], fill=fill)


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, body: str, accent: str = COLORS["accent"]) -> None:
    rounded(draw, box, COLORS["panel"], COLORS["line"], 2, 26)
    x1, y1, x2, _ = box
    draw.rectangle((x1, y1, x1 + 9, box[3]), fill=accent)
    draw.text((x1 + 30, y1 + 24), title, fill=COLORS["white"], font=f(30, True))
    multiline(draw, (x1 + 30, y1 + 74), body, f(23), COLORS["muted"], x2 - x1 - 64, 8)


def add_screenshot(img: Image.Image, draw: ImageDraw.ImageDraw, path: Path, box: tuple[int, int, int, int]) -> None:
    if not path.exists():
        rounded(draw, box, "#0e2a36", COLORS["line"], 2, 28)
        multiline(draw, (box[0] + 40, box[1] + 40), "截图文件暂未找到", f(30, True), COLORS["muted"], box[2] - box[0] - 80)
        return
    screenshot = Image.open(path).convert("RGB")
    target_w = box[2] - box[0]
    target_h = box[3] - box[1]
    screenshot = ImageOps.contain(screenshot, (target_w, target_h))
    canvas = Image.new("RGB", (target_w, target_h), "#06151c")
    ox = (target_w - screenshot.width) // 2
    oy = (target_h - screenshot.height) // 2
    canvas.paste(screenshot, (ox, oy))
    mask = Image.new("L", (target_w, target_h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, target_w, target_h), radius=26, fill=255)
    img.paste(canvas, (box[0], box[1]), mask)
    draw.rounded_rectangle(box, radius=26, outline=COLORS["line"], width=3)


def save_slide(img: Image.Image, idx: int) -> Path:
    SLIDE_DIR.mkdir(parents=True, exist_ok=True)
    path = SLIDE_DIR / f"slide-{idx:02d}.png"
    img.save(path, quality=95)
    return path


def slide_1() -> Image.Image:
    img, draw = base_slide()
    pill(draw, 110, 88, 330, 132, "毕业设计答辩", COLORS["accent"], "#06171d", 26)
    multiline(draw, (110, 245), "基于 Web 的 Landsat 8 遥感影像在线预处理系统", f(70, True), COLORS["white"], 1280, 18)
    draw.text((114, 505), "Remote Sensing Image Online Preprocessing Platform", fill=COLORS["muted"], font=f(30))
    card(draw, (110, 690, 690, 900), "课题定位", "面向 Landsat 8/9 的本地化 Web 预处理平台，覆盖取数、处理、批量编排与结果管理。", COLORS["accent"])
    card(draw, (750, 690, 1330, 900), "技术路线", "FastAPI + Vue 3 + GDAL + NumPy + Py6S + OpenLayers + Vue Flow。", COLORS["accent2"])
    draw.text((1420, 760), "答辩人：李旭东", fill=COLORS["text"], font=f(34, True))
    draw.text((1420, 820), "项目版本：v3.0.0", fill=COLORS["muted"], font=f(26))
    draw.text((1420, 865), "2026 年 5 月", fill=COLORS["muted"], font=f(26))
    return img


def slide_2() -> Image.Image:
    img, draw = base_slide("研究背景与问题", "01")
    card(draw, (115, 240, 555, 520), "遥感预处理不可省", "原始影像直接分析会受到辐射误差、大气影响、云污染和空间范围不统一等因素影响。", COLORS["warm"])
    card(draw, (615, 240, 1055, 520), "传统工具链分散", "桌面软件与脚本流程常需反复切换，批量处理、参数复用和结果追踪效率较低。", COLORS["accent2"])
    card(draw, (1115, 240, 1555, 520), "工程化闭环不足", "从在线检索、下载、预处理到结果预览的链路缺少统一工作台承载。", COLORS["accent"])
    rounded(draw, (290, 670, 1630, 850), "#0e303b", COLORS["line"], 2, 34)
    draw.text((350, 715), "课题目标", fill=COLORS["accent"], font=f(36, True))
    multiline(draw, (540, 705), "构建一个本地部署的 Web 平台，将 Landsat 8/9 影像获取、参数配置、预处理执行、批量编排和结果管理组织为连续可用的工作流程。", f(34, True), COLORS["white"], 1000, 12)
    return img


def slide_3() -> Image.Image:
    img, draw = base_slide("研究内容与系统边界", "02")
    xs = [160, 500, 840, 1180, 1520]
    titles = ["数据输入", "预处理", "批量编排", "结果管理", "在线取数"]
    desc = ["上传/目录扫描\nMTL 与 QA 解析", "L1/L2 分支\n校正、裁剪、合成", "Vue Flow 画布\n拓扑解析与队列", "结果清单\n预览与下载", "STAC 检索\n服务端归档"]
    for i, x in enumerate(xs):
        rounded(draw, (x - 110, 300, x + 150, 500), COLORS["panel"], COLORS["line"], 2, 24)
        draw.text((x - 70, 330), titles[i], fill=COLORS["white"], font=f(31, True))
        multiline(draw, (x - 70, 390), desc[i], f(23), COLORS["muted"], 190, 8)
        if i < len(xs) - 1:
            arrow(draw, (x + 160, 400), (xs[i + 1] - 130, 400), COLORS["accent2"], 4)
    rounded(draw, (190, 670, 1730, 850), "#0d2a36", COLORS["line"], 2, 28)
    draw.text((250, 710), "统一口径", fill=COLORS["accent"], font=f(32, True))
    bullets(draw, 460, 700, [
        "主处理链：Landsat 8/9 L1 与 L2 预处理",
        "扩展能力：Landsat 7、Sentinel-2 在线检索下载",
        "不夸大为多源通用平台，不虚构数据库或分布式调度能力",
    ], 1100, 29)
    return img


def slide_4() -> Image.Image:
    img, draw = base_slide("功能模块设计", "03")
    data = [
        ("单景预处理", "上传波段、MTL、QA；异步任务；L1/L2 双链路；结果预览。", COLORS["accent"]),
        ("批量处理", "节点式流程画布；图结构解析；优先级队列；暂停、恢复、重试。", COLORS["accent2"]),
        ("影像检索下载", "AOI/场景名检索；资产勾选；浏览器下载与服务端下载队列。", COLORS["warm"]),
        ("结果资产中心", "当前任务与历史清单聚合；文件分类；栅格预览；压缩下载。", "#9bdb7b"),
        ("指数信息辅助", "展示常见遥感指数公式、用途和适用场景，辅助用户理解参数。", "#c690ff"),
    ]
    for i, item in enumerate(data):
        row = i // 2
        col = i % 2
        x = 160 + col * 820
        y = 235 + row * 250
        if i == 4:
            x = 570
        card(draw, (x, y, x + 690, y + 190), item[0], item[1], item[2])
    return img


def slide_5() -> Image.Image:
    img, draw = base_slide("总体架构与技术路线", "04")
    layers = [
        ("表现层", "Vue 3 工作台 / AOI 地图 / 批量画布 / 结果中心", COLORS["accent"]),
        ("接口层", "FastAPI 路由：任务提交、状态查询、文件扫描、下载预览", COLORS["accent2"]),
        ("服务层", "BatchJobManager / GraphExecutor / DownloadService / TaskResultService", COLORS["warm"]),
        ("核心处理层", "Landsat8Processor + 辐射定标 / 大气校正 / 裁剪 / 合成 / 指数", "#9bdb7b"),
        ("文件与工具层", "data / output / temp / cache + 路径白名单 + task_manifest.json", "#c690ff"),
    ]
    y = 220
    for name, body, color in layers:
        rounded(draw, (230, y, 1690, y + 118), COLORS["panel"], color, 3, 22)
        draw.text((280, y + 34), name, fill=color, font=f(34, True))
        draw.text((520, y + 38), body, fill=COLORS["text"], font=f(27))
        y += 142
    for ay in [340, 482, 624, 766]:
        arrow(draw, (960, ay), (960, ay + 75), COLORS["line"], 4)
    return img


def slide_6() -> Image.Image:
    img, draw = base_slide("核心处理流程：L1/L2 双链路", "05")
    rounded(draw, (130, 220, 1790, 850), "#0d2a36", COLORS["line"], 2, 30)
    nodes = [
        ((210, 470, 440, 570), "影像输入\n波段/MTL/QA", COLORS["accent"]),
        ((560, 330, 850, 450), "L1 产品链\nDN -> 辐射亮度 -> TOA", COLORS["accent2"]),
        ((560, 600, 850, 720), "L2 产品链\n官方缩放系数 -> 表面反射率", COLORS["warm"]),
        ((1010, 330, 1300, 450), "大气校正\n6S / DOS 回退", COLORS["accent2"]),
        ((1010, 600, 1300, 720), "直接分析\n跳过重复校正", COLORS["warm"]),
        ((1460, 470, 1690, 570), "输出结果\n合成/指数/预览", COLORS["accent"]),
    ]
    for box, label, color in nodes:
        rounded(draw, box, COLORS["panel"], color, 3, 24)
        multiline(draw, (box[0] + 28, box[1] + 24), label, f(27, True), COLORS["white"], box[2] - box[0] - 56, 8)
    arrow(draw, (440, 520), (560, 390), COLORS["accent2"], 5)
    arrow(draw, (440, 520), (560, 660), COLORS["warm"], 5)
    arrow(draw, (850, 390), (1010, 390), COLORS["accent2"], 5)
    arrow(draw, (850, 660), (1010, 660), COLORS["warm"], 5)
    arrow(draw, (1300, 390), (1460, 520), COLORS["accent"], 5)
    arrow(draw, (1300, 660), (1460, 520), COLORS["accent"], 5)
    bullets(draw, 260, 900, ["质量控制贯穿流程：QA_PIXEL 云/阴影/雪/卷云掩膜 + QA_RADSAT 饱和像元掩膜。"], 1400, 30)
    return img


def slide_7() -> Image.Image:
    img, draw = base_slide("单景预处理模块实现", "06")
    shot = ROOT / "docs" / "thesis-prep" / "materials" / "screenshots" / "ss-4-01-single-task-overview.png"
    add_screenshot(img, draw, shot, (110, 240, 1085, 885))
    draw.text((1160, 250), "实现要点", fill=COLORS["accent"], font=f(38, True))
    bullets(draw, 1160, 320, [
        "支持本地上传与服务端场景目录两种输入方式",
        "异步任务提交，前端轮询进度并展示阶段状态",
        "L1 走完整预处理链，L2 直接缩放为表面反射率",
        "输出处理波段、合成图、指数图、质量摘要和预览信息",
    ], 610, 30)
    return img


def slide_8() -> Image.Image:
    img, draw = base_slide("AOI 配置与空间裁剪", "07")
    shot = ROOT / "docs" / "thesis-prep" / "materials" / "screenshots" / "ss-4-02-single-task-aoi-config.png"
    add_screenshot(img, draw, shot, (110, 230, 1160, 900))
    card(draw, (1225, 275, 1745, 465), "空间交互", "使用 OpenLayers 支持矩形框选、范围显示和矢量导入，降低 bbox/shp 参数配置门槛。", COLORS["accent2"])
    card(draw, (1225, 515, 1745, 705), "处理联动", "AOI 参数与裁剪、合成、指数任务统一提交，保证界面配置与后端处理链一致。", COLORS["accent"])
    card(draw, (1225, 755, 1745, 905), "安全控制", "后端通过路径白名单约束本地目录访问，避免任意路径读写风险。", COLORS["warm"])
    return img


def slide_9() -> Image.Image:
    img, draw = base_slide("批量处理与流程编排", "08")
    shot = ROOT / "docs" / "thesis-prep" / "materials" / "screenshots" / "ss-4-03-batch-canvas-overview.png"
    add_screenshot(img, draw, shot, (735, 230, 1810, 900))
    draw.text((110, 245), "批量模块价值", fill=COLORS["accent"], font=f(38, True))
    bullets(draw, 110, 320, [
        "把重复处理步骤抽象为节点画布，流程依赖更直观",
        "后端对图结构做连通性检查与拓扑排序",
        "按场景生成 BatchJobConfig 并进入优先级队列",
        "支持任务状态追踪、失败重试、暂停恢复与取消",
    ], 560, 30)
    return img


def slide_10() -> Image.Image:
    img, draw = base_slide("在线检索下载与结果资产中心", "09")
    left_steps = [
        ("AOI/场景名", "空间范围或官方场景号"),
        ("STAC 检索", "Landsat / Sentinel-2 集合"),
        ("资产选择", "波段、MTL、QA 文件"),
        ("下载归档", "日期/传感器/产品级别/场景"),
    ]
    x = 140
    for i, (title, body) in enumerate(left_steps):
        y = 250 + i * 150
        rounded(draw, (x, y, x + 420, y + 90), COLORS["panel"], COLORS["accent2"], 2, 20)
        draw.text((x + 28, y + 18), title, fill=COLORS["white"], font=f(28, True))
        draw.text((x + 28, y + 54), body, fill=COLORS["muted"], font=f(21))
        if i < len(left_steps) - 1:
            arrow(draw, (x + 210, y + 90), (x + 210, y + 145), COLORS["accent2"], 4)
    rounded(draw, (720, 260, 1720, 820), "#0d2a36", COLORS["line"], 2, 28)
    draw.text((780, 315), "结果资产中心", fill=COLORS["accent"], font=f(40, True))
    bullets(draw, 790, 400, [
        "扫描当前任务与历史 task_manifest.json，形成统一任务列表",
        "按 processed / composite / mask / metadata / extra 分类结果文件",
        "支持单文件下载、目录压缩下载和 GeoTIFF 栅格预览",
        "让处理结果从“文件夹堆积”变成可回访、可展示的资产",
    ], 820, 31)
    return img


def slide_11() -> Image.Image:
    img, draw = base_slide("关键技术与实现亮点", "10")
    highlights = [
        ("双链路预处理", "L1 完整校正链与 L2 表面反射率直用链并存，符合不同产品特性。", COLORS["accent"]),
        ("质量控制机制", "QA_PIXEL 与 QA_RADSAT 组合生成质量掩膜，并返回有效像元比例。", COLORS["accent2"]),
        ("图流程执行器", "Vue Flow 图结构经校验、可达分析和拓扑排序后转换为批量作业。", COLORS["warm"]),
        ("工程保护设计", "6S 失败回退 DOS、下载失败重试、路径白名单和结果清单提升可用性。", "#9bdb7b"),
    ]
    for i, item in enumerate(highlights):
        x = 145 + (i % 2) * 835
        y = 265 + (i // 2) * 285
        card(draw, (x, y, x + 690, y + 215), item[0], item[1], item[2])
    rounded(draw, (360, 880, 1560, 960), "#0d2a36", COLORS["line"], 2, 22)
    draw.text((415, 904), "答辩表达重点：本项目亮点在“遥感处理链工程化集成 + 可视化批量编排 + 结果闭环管理”。", fill=COLORS["white"], font=f(30, True))
    return img


def slide_12() -> Image.Image:
    img, draw = base_slide("测试与运行效果", "11")
    headers = ["测试项", "验证内容", "结果"]
    rows = [
        ["单景预处理", "L1/L2 分支、裁剪、合成、指数、状态轮询", "符合预期"],
        ["批量处理", "流程图校验、队列执行、失败重试、镶嵌", "符合预期"],
        ["检索下载", "AOI/场景名检索、资产选择、下载归档", "符合预期"],
        ["结果中心", "历史扫描、分类展示、预览与压缩下载", "符合预期"],
    ]
    x0, y0 = 150, 260
    widths = [330, 890, 280]
    row_h = 92
    for i, head in enumerate(headers):
        x = x0 + sum(widths[:i])
        rounded(draw, (x, y0, x + widths[i], y0 + row_h), "#174354", COLORS["line"], 2, 8)
        draw.text((x + 28, y0 + 28), head, fill=COLORS["white"], font=f(28, True))
    for r, row in enumerate(rows):
        y = y0 + row_h * (r + 1)
        for i, value in enumerate(row):
            x = x0 + sum(widths[:i])
            rounded(draw, (x, y, x + widths[i], y + row_h), COLORS["panel"], COLORS["line"], 1, 8)
            fill = COLORS["accent"] if i == 2 else COLORS["text"]
            multiline(draw, (x + 28, y + 24), value, f(25, True if i != 1 else False), fill, widths[i] - 56, 5)
    bullets(draw, 180, 820, [
        "测试重点为功能闭环与工程可用性，不编造算法精度提升比例。",
        "已形成处理后波段、合成图、指数图、多景镶嵌结果和任务清单等典型输出。"
    ], 1450, 31)
    return img


def slide_13() -> Image.Image:
    img, draw = base_slide("总结与展望", "12")
    card(draw, (150, 245, 890, 505), "已完成工作", "实现单景预处理、批量处理、影像检索下载、结果资产中心等核心模块，形成从取数到结果管理的 Web 化闭环。", COLORS["accent"])
    card(draw, (1030, 245, 1770, 505), "系统特点", "统一工作台、L1/L2 双链路、节点式批量编排、质量控制、结果清单与路径安全控制。", COLORS["accent2"])
    card(draw, (150, 610, 890, 870), "当前不足", "主处理链仍以 Landsat 8/9 为主，任务状态持久化能力有限，最终测试截图和量化材料仍可补充。", COLORS["warm"])
    card(draw, (1030, 610, 1770, 870), "后续改进", "扩展更多传感器主链、增强结果统计分析、完善任务持久化、补充自动化测试和部署文档。", "#9bdb7b")
    return img


def slide_14() -> Image.Image:
    img, draw = base_slide()
    draw.text((690, 360), "谢谢各位老师", fill=COLORS["white"], font=f(82, True))
    draw.text((765, 485), "敬请批评指正", fill=COLORS["accent"], font=f(48, True))
    rounded(draw, (560, 650, 1360, 770), "#0d2a36", COLORS["line"], 2, 30)
    draw.text((700, 687), "Q & A", fill=COLORS["white"], font=f(52, True))
    return img


def make_pptx(slide_paths: list[Path]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rels = []
    with zipfile.ZipFile(PPTX_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types(len(slide_paths)))
        z.writestr("_rels/.rels", package_rels())
        z.writestr("docProps/core.xml", core_props())
        z.writestr("docProps/app.xml", app_props(len(slide_paths)))
        z.writestr("ppt/presentation.xml", presentation_xml(len(slide_paths)))
        z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slide_paths)))
        z.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels())
        z.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels())
        z.writestr("ppt/theme/theme1.xml", theme_xml())
        for i, path in enumerate(slide_paths, 1):
            z.write(path, f"ppt/media/image{i}.png")
            z.writestr(f"ppt/slides/slide{i}.xml", slide_xml(i))
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide_rels(i))


def content_types(n: int) -> str:
    slides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, n + 1)
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
{slides}
</Types>'''


def package_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def core_props() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>基于Web的Landsat8遥感影像在线预处理系统-答辩PPT</dc:title>
<dc:creator>Codex</dc:creator>
<cp:lastModifiedBy>Codex</cp:lastModifiedBy>
<dcterms:created xsi:type="dcterms:W3CDTF">2026-05-21T00:00:00Z</dcterms:created>
<dcterms:modified xsi:type="dcterms:W3CDTF">2026-05-21T00:00:00Z</dcterms:modified>
</cp:coreProperties>'''


def app_props(n: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>Microsoft PowerPoint</Application><PresentationFormat>Widescreen</PresentationFormat><Slides>{n}</Slides>
</Properties>'''


def presentation_xml(n: int) -> str:
    ids = "".join(f'<p:sldId id="{255 + i}" r:id="rId{i}"/>' for i in range(1, n + 1))
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId{n + 1}"/></p:sldMasterIdLst>
<p:sldIdLst>{ids}</p:sldIdLst>
<p:sldSz cx="{PPT_CX}" cy="{PPT_CY}" type="wide"/><p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>'''


def presentation_rels(n: int) -> str:
    slide_rels = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, n + 1)
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{slide_rels}
<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
<Relationship Id="rId{n + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>'''


def slide_xml(i: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
<p:pic><p:nvPicPr><p:cNvPr id="2" name="Slide {i}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{PPT_CX}" cy="{PPT_CY}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>
</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>'''


def slide_rels(i: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{i}.png"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>'''


def slide_master_xml() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>'''


def slide_master_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>'''


def slide_layout_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>'''


def slide_layout_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>'''


def theme_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Defense Theme">
<a:themeElements><a:clrScheme name="Defense"><a:dk1><a:srgbClr val="07151F"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="0A2430"/></a:dk2><a:lt2><a:srgbClr val="F5FBFF"/></a:lt2><a:accent1><a:srgbClr val="2FD0B5"/></a:accent1><a:accent2><a:srgbClr val="5AA9FF"/></a:accent2><a:accent3><a:srgbClr val="F3C969"/></a:accent3><a:accent4><a:srgbClr val="9BDB7B"/></a:accent4><a:accent5><a:srgbClr val="C690FF"/></a:accent5><a:accent6><a:srgbClr val="EF8072"/></a:accent6><a:hlink><a:srgbClr val="5AA9FF"/></a:hlink><a:folHlink><a:srgbClr val="C690FF"/></a:folHlink></a:clrScheme><a:fontScheme name="Defense"><a:majorFont><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Microsoft YaHei"/></a:majorFont><a:minorFont><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Microsoft YaHei"/></a:minorFont></a:fontScheme><a:fmtScheme name="Defense"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>'''


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slide_funcs = [
        slide_1, slide_2, slide_3, slide_4, slide_5, slide_6, slide_7,
        slide_8, slide_9, slide_10, slide_11, slide_12, slide_13, slide_14,
    ]
    slide_paths = [save_slide(fn(), idx) for idx, fn in enumerate(slide_funcs, 1)]
    make_pptx(slide_paths)
    print(PPTX_PATH)


if __name__ == "__main__":
    main()
