from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Dict, List
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw

import make_defense_web_relayout_ppt as base


ROOT = base.ROOT
OUT_DIR = ROOT / "output" / "ppt" / "web_relayout_v3"
ASSET_DIR = OUT_DIR / "assets"
SLIDES_DIR = OUT_DIR / "slides"
HTML_PATH = OUT_DIR / "基于Web的Landsat8遥感影像在线预处理系统-30页内容丰富统一配色版.html"
INDEX_PATH = OUT_DIR / "index.html"
MANIFEST_PATH = OUT_DIR / "build-manifest.json"
PPTX_PATH = ROOT / "output" / "ppt" / "基于Web的Landsat8遥感影像在线预处理系统-30页内容丰富统一配色版.pptx"
CONTACT_SHEET = OUT_DIR / "contact-sheet.png"


base.OUT_DIR = OUT_DIR
base.ASSET_DIR = ASSET_DIR
base.SLIDES_DIR = SLIDES_DIR
base.HTML_PATH = HTML_PATH
base.INDEX_PATH = INDEX_PATH
base.MANIFEST_PATH = MANIFEST_PATH
base.PPTX_PATH = PPTX_PATH

base.RAW_ASSETS.update(
    {
        "research_framework": ROOT / "output/doc/thesis_generated_figures/fig-1-02-research-framework.png",
        "preprocess_flow": ROOT / "output/doc/thesis_generated_figures/fig-2-01-preprocess-flow.png",
        "tech_relationship": ROOT / "output/doc/thesis_generated_figures/fig-2-03-tech-relationship.png",
        "use_case": ROOT / "output/doc/thesis_generated_figures/fig-2-04-use-case.png",
        "user_flow": ROOT / "output/doc/thesis_generated_figures/fig-2-05-user-flow.png",
        "module_structure": ROOT / "output/doc/thesis_generated_figures/fig-3-02-module-structure.png",
        "single_flow": ROOT / "output/doc/thesis_generated_figures/fig-3-03-single-flow.png",
        "batch_flow": ROOT / "output/doc/thesis_generated_figures/fig-3-04-batch-flow.png",
        "download_flow": ROOT / "output/doc/thesis_generated_figures/fig-3-05-download-flow.png",
        "result_flow": ROOT / "output/doc/thesis_generated_figures/fig-3-06-result-flow.png",
        "l1l2_logic": ROOT / "output/doc/thesis_generated_figures/fig-4-10-l1-l2-logic.png",
        "mosaic_flow": ROOT / "output/doc/thesis_generated_figures/fig-4-11-mosaic-flow.png",
    }
)


SLIDES: List[Dict] = [
    {
        "no": "01",
        "type": "cover",
        "eyebrow": "毕业设计答辩 / Remote Sensing Workbench",
        "title": "基于 Web 的 Landsat 8 遥感影像在线预处理系统",
        "subtitle": "面向本地部署、教学实验和小规模科研处理的一体化 Web 工作台",
        "meta": ["答辩人：李旭东", "项目版本：v3.0.0", "2026 年 5 月"],
        "facts": ["L1/L2 双链路", "Vue 3 + FastAPI", "GDAL / NumPy / Py6S", "STAC 检索下载"],
    },
    {
        "no": "02",
        "type": "roadmap",
        "eyebrow": "答辩路线",
        "title": "本次答辩围绕“为什么做、怎么设计、如何实现、结果怎样”展开",
        "lead": "主线不是单一算法展示，而是把遥感取数、预处理、批量执行和结果管理组织成可演示、可复用的工程闭环。",
        "items": [
            ["01", "课题背景", "遥感预处理的必要性与传统流程痛点"],
            ["02", "需求目标", "功能需求、边界控制与交付范围"],
            ["03", "总体设计", "前后端分离、五层架构与文件组织"],
            ["04", "系统实现", "L1/L2、质量控制、图执行器与结果中心"],
            ["05", "界面展示", "单景、批量、下载、结果管理真实页面"],
            ["06", "测试结论", "功能验证、典型输出与不足改进"],
        ],
    },
    {
        "no": "03",
        "type": "dense_cards",
        "eyebrow": "背景 01",
        "title": "遥感影像预处理是后续专题分析的基础环节",
        "lead": "原始影像中的 DN 值、云污染和空间范围差异会直接影响合成、指数提取与镶嵌结果，因此预处理不是可有可无的前置步骤。",
        "cards": [
            ["辐射与大气影响", "DN 值不能直接代表地物真实反射特征，需要辐射定标与大气校正建立可比较的物理量。"],
            ["质量污染", "云、云影、雪、卷云和饱和像元会污染指数计算，必须用 QA_PIXEL 与 QA_RADSAT 做质量控制。"],
            ["空间与批量一致性", "多景数据常需要统一裁剪、同类合成和结果归档，否则难以支撑连续化分析。"],
        ],
        "callout": "应用场景：农业监测、水体识别、城市扩张、生态环境评估。",
    },
    {
        "no": "04",
        "type": "compare",
        "eyebrow": "背景 02",
        "title": "传统桌面式流程的主要问题在于割裂，而不是单个软件不能处理",
        "left_title": "传统流程",
        "left": ["外部平台检索下载", "桌面软件/脚本反复切换", "参数配置难复用", "结果散落在多级目录", "批量处理依赖人工维护"],
        "right_title": "本系统目标流程",
        "right": ["Web 统一入口", "AOI、参数、任务状态集中管理", "流程图表达批量逻辑", "manifest 记录结果清单", "结果中心统一预览与下载"],
        "summary": "把多工具协作变成一个可追踪的任务链，是本课题的工程价值。",
    },
    {
        "no": "05",
        "type": "requirements",
        "eyebrow": "目标与需求",
        "title": "系统建设目标被拆成四类功能需求与三类工程约束",
        "functional": [
            ["单景预处理", "支持本地上传或服务端场景目录输入，配置 L1/L2、裁剪、云掩膜、合成和指数。"],
            ["批量流程编排", "用 Vue Flow 节点画布描述处理链，后端转换为场景级任务配置。"],
            ["在线检索下载", "基于 STAC 检索 Landsat 与 Sentinel-2，支持 AOI 和场景名检索。"],
            ["结果资产管理", "扫描历史输出和 task_manifest.json，按产物类型分类展示。"],
        ],
        "nonfunctional": [
            ["本地部署", "适配 Windows 本地 Python、Node.js、GDAL 环境。"],
            ["可维护", "前后端分离，处理器、服务和工具模块职责分开。"],
            ["安全可控", "路径白名单限制本地目录访问，避免任意文件读写。"],
        ],
    },
    {
        "no": "06",
        "type": "scope",
        "eyebrow": "系统边界",
        "title": "课题边界保持克制：主处理链聚焦 Landsat 8/9，下载模块适度扩展",
        "rows": [
            ["主处理对象", "Landsat 8/9 L1 与 L2", "保证论文与源码事实一致"],
            ["扩展能力", "Sentinel-2 L2A 下载与 APGI 示例", "体现接口和结果能力可扩展"],
            ["部署方式", "本地 Web 服务 + 浏览器工作台", "适合教学演示与小规模实验"],
            ["数据组织", "文件系统 + manifest", "避免引入超出课题规模的数据库复杂度"],
        ],
        "notes": ["不宣称覆盖所有传感器。", "不把下载检索能力等同于全流程多源处理平台。", "强调工程闭环和可演示性。"],
    },
    {
        "no": "07",
        "type": "image_analysis",
        "eyebrow": "总体架构",
        "title": "系统采用前后端分离架构，按表现、接口、服务、算法、文件五层组织",
        "image": "arch",
        "points": [
            ["表现层", "Vue 3 工作台负责页面交互、AOI 地图、流程画布和结果预览。"],
            ["接口层", "FastAPI 接收处理参数、批量任务、下载请求和结果访问请求。"],
            ["服务层", "图执行器、下载服务、任务结果服务把业务流程串起来。"],
            ["算法层", "Landsat8Processor 调用 GDAL、NumPy、Py6S 和合成指数模块。"],
        ],
    },
    {
        "no": "08",
        "type": "stack",
        "eyebrow": "技术选型",
        "title": "技术栈选择围绕“浏览器交互 + 本地高性能栅格处理”展开",
        "groups": [
            ["前端", "Vue 3 / Vite / OpenLayers / Vue Flow", "负责工作台交互、地图 AOI、节点式流程和状态轮询。"],
            ["后端", "FastAPI / Uvicorn / Pydantic", "提供异步任务、下载检索、结果访问与路径校验接口。"],
            ["处理", "GDAL / NumPy / Py6S", "完成波段读取、反射率换算、大气校正、栅格裁剪和指数计算。"],
            ["数据", "STAC / Planetary Computer / 本地文件系统", "连接在线影像资源，并通过输出目录和清单组织结果。"],
        ],
    },
    {
        "no": "09",
        "type": "module_matrix",
        "eyebrow": "模块划分",
        "title": "五个功能模块共同构成从数据到结果的闭环",
        "rows": [
            ["单景预处理", "波段、MTL、QA、裁剪参数", "L1/L2 分支、质量掩膜、合成、指数", "处理波段、合成图、质量摘要"],
            ["批量处理", "数据目录、节点流程图、优先级", "图结构解析、队列执行、失败重试", "批次状态、场景结果、镶嵌结果"],
            ["影像下载", "AOI、场景名、时间范围、资产选择", "STAC 查询、认证、后台下载", "归档文件与下载任务记录"],
            ["结果中心", "输出目录、任务清单", "扫描、分类、预览、压缩下载", "历史任务列表与产物分类"],
            ["指数说明", "指数类型选择", "公式与应用说明展示", "帮助用户理解分析含义"],
        ],
    },
    {
        "no": "10",
        "type": "flow_detail",
        "eyebrow": "业务流程 01",
        "title": "单景预处理流程从输入识别开始，到结果清单写入结束",
        "image": "single_flow",
        "steps": [
            ["输入识别", "上传波段、MTL、QA，或从服务端场景目录自动读取支持文件。"],
            ["参数提交", "前端提交产品级别、AOI、云掩膜、大气校正、合成和指数配置。"],
            ["异步执行", "后端创建任务，处理器按 L1/L2 分支运行并更新进度。"],
            ["结果回收", "输出处理波段、合成图、质量摘要和 task_manifest.json。"],
        ],
    },
    {
        "no": "11",
        "type": "image_analysis",
        "eyebrow": "业务流程 02",
        "title": "L1 与 L2 双链路避免重复处理，也保留完整教学展示路径",
        "image": "l1l2",
        "points": [
            ["L1 链路", "DN -> 辐射亮度/TOA 反射率 -> DOS 或 6S 大气校正 -> 分析产品。"],
            ["L2 链路", "直接按官方缩放系数 0.0000275 和偏移量 -0.2 生成表面反射率。"],
            ["设计意义", "既能展示完整预处理理论，也能支持使用官方反射率产品快速进入指数分析。"],
            ["源码依据", "核心分支位于 Landsat8Processor.process_band() 与 one_click_preprocess()。"],
        ],
    },
    {
        "no": "12",
        "type": "dense_cards",
        "eyebrow": "质量控制",
        "title": "系统不是简单生成一张图，而是把质量掩膜和回退策略纳入处理链",
        "lead": "毕业设计里最容易被问到的是可靠性：当输入有云、质量波段或 6S 环境缺失时，系统是否还能给出可解释结果。",
        "cards": [
            ["QA_PIXEL 掩膜", "识别云、云影、雪、卷云等质量问题，减少污染像元对指数计算的影响。"],
            ["QA_RADSAT 饱和", "识别饱和像元，补充反射率结果的质量解释。"],
            ["6S 回退 DOS", "优先尝试物理模型；依赖缺失或执行失败时回退经验模型，避免任务中断。"],
        ],
        "callout": "质量控制让结果“可解释”，回退机制让任务“可完成”。",
    },
    {
        "no": "13",
        "type": "flow_detail",
        "eyebrow": "批量处理",
        "title": "批量模块把前端流程图转换成可执行任务队列",
        "image": "batch_flow",
        "steps": [
            ["场景扫描", "读取目录下的多景数据和产品级别信息。"],
            ["流程校验", "检查 input 到 output 是否连通，并按拓扑顺序提取有效节点。"],
            ["配置生成", "将节点和连线转换为每个场景的 BatchJobConfig。"],
            ["队列执行", "按优先级进入 worker，支持失败重试、暂停、恢复和取消。"],
        ],
    },
    {
        "no": "14",
        "type": "image_analysis",
        "eyebrow": "在线取数",
        "title": "下载检索模块把外部影像资源接入本地预处理工作台",
        "image": "download_flow",
        "points": [
            ["检索方式", "支持 AOI 框选、矢量导入、时间范围、传感器和场景名检索。"],
            ["数据来源", "通过 STAC 查询 Landsat 与 Sentinel-2 数据集合。"],
            ["下载模式", "支持浏览器直接下载，也支持服务端下载队列与失败重试。"],
            ["归档策略", "按日期、传感器、产品级别和场景 ID 写入 output/landsat_downloads。"],
        ],
    },
    {
        "no": "15",
        "type": "result_system",
        "eyebrow": "结果管理",
        "title": "结果中心解决“文件生成了，但不好找、不好解释”的问题",
        "image": "result_flow",
        "tree": ["output/", "  single-task/", "    task_manifest.json", "    B*_processed.tif", "    true_color.tif", "    ndvi.tif", "    cloud_mask.tif"],
        "points": [
            ["manifest 清单", "记录任务类型、标题、输出目录、完成时间、摘要和产物分类。"],
            ["分类展示", "按 processed、composite、mask、metadata 组织结果。"],
            ["再访问能力", "支持历史任务扫描、单文件下载、目录压缩下载和栅格预览。"],
        ],
    },
    {
        "no": "16",
        "type": "screenshot",
        "eyebrow": "界面 01",
        "title": "单景任务页把输入、参数、监控和预览收在同一工作面",
        "image": "single",
        "points": ["左侧负责数据与参数配置。", "中部显示任务监控和步骤进度。", "右侧承接结果预览和下载入口。"],
        "caption": "这页适合现场演示：选择产品级别、设置输出目录、提交任务、查看进度。",
    },
    {
        "no": "17",
        "type": "screenshot",
        "eyebrow": "界面 02",
        "title": "AOI 可视化配置让裁剪参数不再只是一串坐标",
        "image": "aoi",
        "points": ["支持地图框选与矢量导入。", "前端会提示 ROI 与影像覆盖关系。", "裁剪范围随任务参数提交到后端。"],
        "caption": "空间交互是 Web 化相较命令行脚本最直观的改进。",
    },
    {
        "no": "18",
        "type": "screenshot",
        "eyebrow": "界面 03",
        "title": "批量流程画布把重复处理逻辑从“口头说明”变成“可见流程”",
        "image": "batch",
        "points": ["节点表达处理步骤。", "连线表达依赖顺序。", "输出路径、场景选择和队列状态可在同一页检查。"],
        "caption": "答辩时可强调：前端画布不是装饰，而是后端图执行器的输入。",
    },
    {
        "no": "19",
        "type": "screenshot",
        "eyebrow": "界面 04",
        "title": "影像检索页覆盖 AOI、条件、场景列表和资产选择",
        "image": "search",
        "points": ["AOI 检索与场景名检索并存。", "可切换 Landsat / Sentinel-2 与产品级别。", "资产下载后可进入本地处理目录。"],
        "caption": "取数能力让系统从“处理工具”变成“数据入口 + 处理入口”。",
    },
    {
        "no": "20",
        "type": "screenshot",
        "eyebrow": "界面 05",
        "title": "结果资产中心把历史输出重新组织成可浏览对象",
        "image": "result_center",
        "points": ["扫描当前任务和历史 manifest。", "区分处理波段、合成结果、掩膜与元数据。", "支持下载、压缩和栅格预览。"],
        "caption": "这部分直接回应传统流程中结果散落、难回溯的问题。",
    },
    {
        "no": "21",
        "type": "code",
        "eyebrow": "关键实现 01",
        "title": "处理器主入口按产品级别切换 L1/L2 策略",
        "snippet": "processor_branch",
        "notes": ["先标准化 product_level，避免前端传值差异影响后端逻辑。", "L2 直接进入 surface reflectance 缩放，减少重复辐射/大气处理。", "L1 则走 DN 读取、反射率换算和大气校正链。"],
    },
    {
        "no": "22",
        "type": "code",
        "eyebrow": "关键实现 02",
        "title": "6S 失败时回退 DOS，保证任务链不中断",
        "snippet": "processor_atm",
        "notes": ["优先调用 6S 精确模型，满足精细化校正场景。", "异常被捕获后进入 DOS，适应本地环境依赖不完整的现实情况。", "回退策略让演示和教学环境更稳。"],
    },
    {
        "no": "23",
        "type": "code",
        "eyebrow": "关键实现 03",
        "title": "图执行器把前端流程图转换为 BatchJobConfig",
        "snippet": "graph_executor",
        "notes": ["从 output 节点反向找可达节点，避免无关节点进入执行链。", "拓扑排序保证节点依赖顺序正确。", "每个场景生成独立 job config，支撑队列化执行。"],
    },
    {
        "no": "24",
        "type": "code",
        "eyebrow": "关键实现 04",
        "title": "合成与指数模块同时支持预设产品和自定义公式",
        "snippet": "synthesis",
        "notes": ["预设真彩色、假彩色、城市、农业和短波红外等常用合成。", "NDVI、APGI 等指数通过独立函数承载。", "自定义公式为后续扩展留出入口。"],
    },
    {
        "no": "25",
        "type": "code",
        "eyebrow": "关键实现 05",
        "title": "结果中心依赖 manifest 与 artifact 分类组织历史结果",
        "snippet": "task_results",
        "notes": ["任务完成后写入 task_manifest.json。", "结果产物被归类为 processed、composite、mask、metadata 等类型。", "结果中心无需数据库即可扫描历史输出。"],
    },
    {
        "no": "26",
        "type": "code",
        "eyebrow": "关键实现 06",
        "title": "路径白名单控制本地文件访问边界",
        "snippet": "path_policy",
        "notes": ["系统支持目录扫描、文件上传、下载和预览，因此路径控制必须前置。", "只允许访问约定根目录下的资源。", "这是本地 Web 化系统避免任意文件访问的关键保护。"],
    },
    {
        "no": "27",
        "type": "code",
        "eyebrow": "关键实现 07",
        "title": "下载服务负责 STAC 接入、资产选择与后台下载任务",
        "snippet": "download_service",
        "notes": ["服务封装 Landsat / Sentinel-2 集合检索。", "下载任务支持后台执行、重试和归档。", "让在线取数与本地处理目录衔接起来。"],
    },
    {
        "no": "28",
        "type": "testing",
        "eyebrow": "测试验证",
        "title": "测试重点覆盖功能链路、界面联调和结果检查",
        "methods": [
            ["功能验证", "检查接口、处理能力、任务状态和下载任务是否符合预期。"],
            ["界面联调", "验证前端参数提交、状态轮询、AOI 配置和结果预览是否连贯。"],
            ["结果检查", "检查输出目录是否生成处理波段、合成图、指数图和 manifest。"],
        ],
        "rows": [
            ["单景预处理", "上传 L1/L2 数据并提交异步任务", "返回 job_id 并生成结果"],
            ["批量处理", "提交流程图并执行多景任务", "生成批次状态与场景级结果"],
            ["多景镶嵌", "启用 mosaic 节点处理多景场景", "输出镶嵌波段与合成结果"],
            ["在线下载", "基于 AOI 或场景名检索并下载资产", "返回场景列表并生成下载文件"],
            ["结果中心", "扫描历史结果并预览下载", "正确分类并支持压缩下载"],
        ],
        "callout": "开发阶段记录：辐射定标模块曾完成 13 项单元测试并全部通过。",
    },
    {
        "no": "29",
        "type": "result_gallery",
        "eyebrow": "典型成果",
        "title": "系统已能够输出合成图、指数图、质量掩膜和多景镶嵌结果",
        "images": [
            ["true_color", "真彩色合成", "验证波段顺序和 RGB 输出"],
            ["ndvi", "NDVI 指数", "体现专题指数计算能力"],
            ["mask", "云掩膜", "说明质量控制参与分析链"],
            ["mosaic", "镶嵌结果", "体现多景批量整合能力"],
        ],
        "summary": "结果链路从“单景处理”延伸到“合成/指数”和“多景镶嵌”，同时通过结果中心完成归档和再访问。",
    },
    {
        "no": "30",
        "type": "closing",
        "eyebrow": "总结与展望",
        "title": "本项目的价值在于把遥感预处理做成可用、可追踪、可演示的工程闭环",
        "columns": [
            ["完成工作", ["单景预处理、批量流程、在线检索下载、结果资产中心。", "Landsat 8/9 L1/L2 双链路与 QA 质量控制。", "基于 manifest 的历史结果聚合。"]],
            ["主要亮点", ["前端 AOI 与流程画布提升交互表达。", "图执行器把可视流程转为后端任务。", "路径白名单与回退策略增强本地部署可控性。"]],
            ["不足改进", ["主预处理链仍聚焦 Landsat 8/9。", "批量任务状态持久化能力可继续增强。", "后续可扩展更多传感器和自动化测试。"]],
        ],
        "thanks": "谢谢各位老师，敬请批评指正",
    },
]


def items(values: List[str]) -> str:
    return "".join(f"<li>{escape(v)}</li>" for v in values)


def image_tag(assets: Dict[str, str], key: str, alt: str) -> str:
    path = assets.get(key)
    if not path:
        return f"<div class='missing'><strong>{escape(alt)}</strong><span>素材缺失</span></div>"
    return f"<img src='{escape(path)}' alt='{escape(alt)}' loading='eager'>"


def render_cards(cards: List[List[str]]) -> str:
    return "".join(
        f"<article><strong>{escape(title)}</strong><p>{escape(body)}</p></article>"
        for title, body in cards
    )


def code_block(snippet_key: str) -> str:
    snippet = base.CODE_SNIPPETS[snippet_key]
    code = textwrap.dedent(snippet["code"]).strip("\n")
    return (
        "<div class='code-card'>"
        f"<div class='code-head'><strong>{escape(snippet['title'])}</strong><span>{escape(snippet['source'])}</span></div>"
        f"<pre><code>{escape(code)}</code></pre>"
        "</div>"
    )


def header(slide: Dict) -> str:
    return (
        "<div class='topline'>"
        f"<span>{escape(slide['eyebrow'])}</span>"
        f"<b>{escape(slide['no'])}</b>"
        "</div>"
    )


def render_slide(slide: Dict, assets: Dict[str, str]) -> str:
    t = slide["type"]
    no = slide["no"]
    title = escape(slide["title"])

    if t == "cover":
        meta = "".join(f"<span>{escape(x)}</span>" for x in slide["meta"])
        facts = "".join(f"<span>{escape(x)}</span>" for x in slide["facts"])
        return f"""
<section class="slide cover" id="slide-{no}">
  <div class="slide-no">{no}</div>
  <div class="cover-copy">
    <div class="eyebrow-pill">{escape(slide['eyebrow'])}</div>
    <h1>{title}</h1>
    <p>{escape(slide['subtitle'])}</p>
    <div class="fact-row">{facts}</div>
  </div>
  <div class="orbital-board">
    <div class="orbit-line"></div>
    <div class="tile t1">L1/L2</div>
    <div class="tile t2">QA</div>
    <div class="tile t3">STAC</div>
    <div class="tile t4">GDAL</div>
    <div class="scan-panel">
      <span></span><span></span><span></span><span></span>
      <strong>Remote Sensing<br>Workbench</strong>
    </div>
  </div>
  <div class="meta-row">{meta}</div>
</section>"""

    if t == "roadmap":
        cards = "".join(
            f"<article><span>{num}</span><strong>{escape(name)}</strong><p>{escape(desc)}</p></article>"
            for num, name, desc in slide["items"]
        )
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <div class="intro-grid">
    <div>
      <h2>{title}</h2>
      <p class="lead">{escape(slide['lead'])}</p>
    </div>
    <div class="route-mark">30<br><small>Slides</small></div>
  </div>
  <div class="roadmap-grid">{cards}</div>
</section>"""

    if t == "dense_cards":
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <p class="lead wide">{escape(slide['lead'])}</p>
  <div class="dense-card-grid">{render_cards(slide['cards'])}</div>
  <div class="callout">{escape(slide['callout'])}</div>
</section>"""

    if t == "compare":
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="compare-grid">
    <article class="compare-card muted"><strong>{escape(slide['left_title'])}</strong><ul>{items(slide['left'])}</ul></article>
    <article class="compare-card accent"><strong>{escape(slide['right_title'])}</strong><ul>{items(slide['right'])}</ul></article>
  </div>
  <div class="callout">{escape(slide['summary'])}</div>
</section>"""

    if t == "requirements":
        functional = render_cards(slide["functional"])
        nonfunctional = render_cards(slide["nonfunctional"])
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="requirements-grid">
    <section><h3>功能需求</h3><div class="mini-cards">{functional}</div></section>
    <section><h3>工程约束</h3><div class="mini-cards">{nonfunctional}</div></section>
  </div>
</section>"""

    if t == "scope":
        rows = "".join(
            f"<tr><td>{escape(a)}</td><td>{escape(b)}</td><td>{escape(c)}</td></tr>"
            for a, b, c in slide["rows"]
        )
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="scope-grid">
    <table><thead><tr><th>边界项</th><th>范围</th><th>设计原因</th></tr></thead><tbody>{rows}</tbody></table>
    <aside><strong>答辩表述边界</strong><ul>{items(slide['notes'])}</ul></aside>
  </div>
</section>"""

    if t == "image_analysis":
        cards = render_cards(slide["points"])
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="image-analysis">
    <figure>{image_tag(assets, slide['image'], slide['title'])}</figure>
    <div class="analysis-cards">{cards}</div>
  </div>
</section>"""

    if t == "stack":
        groups = "".join(
            f"<article><span>{escape(name)}</span><strong>{escape(tech)}</strong><p>{escape(desc)}</p></article>"
            for name, tech, desc in slide["groups"]
        )
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="stack-grid">{groups}</div>
</section>"""

    if t == "module_matrix":
        rows = "".join(
            f"<tr><td>{escape(a)}</td><td>{escape(b)}</td><td>{escape(c)}</td><td>{escape(d)}</td></tr>"
            for a, b, c, d in slide["rows"]
        )
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <table class="matrix"><thead><tr><th>模块</th><th>输入</th><th>处理内容</th><th>输出</th></tr></thead><tbody>{rows}</tbody></table>
</section>"""

    if t == "flow_detail":
        steps = render_cards(slide["steps"])
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="flow-grid">
    <figure>{image_tag(assets, slide['image'], slide['title'])}</figure>
    <div class="analysis-cards compact">{steps}</div>
  </div>
</section>"""

    if t == "result_system":
        tree = "".join(f"<span>{escape(x)}</span>" for x in slide["tree"])
        points = render_cards(slide["points"])
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="result-grid">
    <figure>{image_tag(assets, slide['image'], slide['title'])}</figure>
    <div class="file-tree">{tree}</div>
    <div class="analysis-cards">{points}</div>
  </div>
</section>"""

    if t == "screenshot":
        chips = "".join(f"<span>{escape(p)}</span>" for p in slide["points"])
        return f"""
<section class="slide page screenshot-page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="screenshot-grid">
    <figure>{image_tag(assets, slide['image'], slide['title'])}</figure>
    <aside><div class="chip-list">{chips}</div><p>{escape(slide['caption'])}</p></aside>
  </div>
</section>"""

    if t == "code":
        notes = "".join(f"<li>{escape(x)}</li>" for x in slide["notes"])
        return f"""
<section class="slide code-page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="code-layout">
    {code_block(slide['snippet'])}
    <aside><strong>实现解读</strong><ul>{notes}</ul></aside>
  </div>
</section>"""

    if t == "testing":
        methods = render_cards(slide["methods"])
        rows = "".join(
            f"<tr><td>{escape(a)}</td><td>{escape(b)}</td><td>{escape(c)}</td></tr>"
            for a, b, c in slide["rows"]
        )
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="test-methods">{methods}</div>
  <table class="matrix small"><thead><tr><th>测试项</th><th>测试内容</th><th>通过标志</th></tr></thead><tbody>{rows}</tbody></table>
  <div class="callout">{escape(slide['callout'])}</div>
</section>"""

    if t == "result_gallery":
        gallery = "".join(
            f"<figure>{image_tag(assets, key, name)}<figcaption><strong>{escape(name)}</strong><span>{escape(desc)}</span></figcaption></figure>"
            for key, name, desc in slide["images"]
        )
        return f"""
<section class="slide page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="gallery-grid">{gallery}</div>
  <div class="callout">{escape(slide['summary'])}</div>
</section>"""

    if t == "closing":
        columns = "".join(
            f"<article><strong>{escape(name)}</strong><ul>{items(vals)}</ul></article>"
            for name, vals in slide["columns"]
        )
        return f"""
<section class="slide closing-page" id="slide-{no}">
  {header(slide)}
  <h2>{title}</h2>
  <div class="closing-grid">{columns}</div>
  <div class="thanks">{escape(slide['thanks'])}</div>
</section>"""

    raise ValueError(f"unknown slide type: {t}")


def build_html(assets: Dict[str, str]) -> str:
    nav = "".join(f"<a href='#slide-{s['no']}'>{s['no']}</a>" for s in SLIDES)
    slides = "\n".join(render_slide(slide, assets) for slide in SLIDES)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>基于Web的Landsat8遥感影像在线预处理系统 - 内容丰富统一配色版</title>
  <style>
    :root {{
      --navy: #071923;
      --navy-2: #0d2633;
      --panel: #123241;
      --panel-2: #173b49;
      --paper: #f2efe6;
      --paper-2: #e7e2d5;
      --ink: #102534;
      --muted: #60717a;
      --line: rgba(16, 37, 52, .16);
      --teal: #1aa39a;
      --teal-2: #85ded7;
      --amber: #d99037;
      --coral: #c9583f;
      --white: #f8fbf8;
      --mono: "Cascadia Mono", "Consolas", monospace;
      --body: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #d8ddd7;
      color: var(--ink);
      font-family: var(--body);
    }}
    .nav {{
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 10px 18px;
      background: rgba(242,239,230,.92);
      border-bottom: 1px solid rgba(16,37,52,.14);
      overflow-x: auto;
    }}
    .nav::before {{ content: "答辩网页设计稿 / 30 Slides"; font-weight: 800; margin-right: 8px; color: var(--navy); white-space: nowrap; }}
    .nav a {{
      min-width: 34px;
      height: 30px;
      display: grid;
      place-items: center;
      border: 1px solid rgba(16,37,52,.16);
      border-radius: 8px;
      background: rgba(255,255,255,.62);
      color: var(--navy);
      font-size: 12px;
      font-weight: 800;
      text-decoration: none;
    }}
    .deck {{
      display: grid;
      gap: 28px;
      justify-items: center;
      padding: 28px;
    }}
    .slide {{
      position: relative;
      width: min(1360px, calc(100vw - 56px));
      aspect-ratio: 16 / 9;
      overflow: hidden;
      border: 1px solid rgba(7,25,35,.12);
      box-shadow: 0 28px 70px rgba(7,25,35,.18);
    }}
    html.capture-mode,
    html.capture-mode body {{
      width: 1600px;
      height: 900px;
      overflow: hidden;
      background: var(--paper);
    }}
    html.capture-mode .nav {{ display: none; }}
    html.capture-mode .deck {{ display: block; width: 1600px; height: 900px; padding: 0; }}
    html.capture-mode .slide {{ width: 1600px; height: 900px; aspect-ratio: auto; border: 0; box-shadow: none; }}
    .page, .screenshot-page {{
      padding: 52px 62px;
      background:
        linear-gradient(90deg, rgba(16,37,52,.055) 1px, transparent 1px),
        linear-gradient(180deg, rgba(16,37,52,.045) 1px, transparent 1px),
        var(--paper);
      background-size: 48px 48px;
    }}
    .page::after, .screenshot-page::after {{
      content: "";
      position: absolute;
      inset: auto 0 0 0;
      height: 10px;
      background: linear-gradient(90deg, var(--teal), var(--amber), var(--coral));
    }}
    .cover, .code-page, .closing-page {{
      padding: 58px 68px;
      color: var(--white);
      background:
        linear-gradient(90deg, rgba(133,222,215,.075) 1px, transparent 1px),
        linear-gradient(180deg, rgba(133,222,215,.06) 1px, transparent 1px),
        linear-gradient(135deg, var(--navy), var(--navy-2));
      background-size: 48px 48px, 48px 48px, auto;
    }}
    .slide-no {{
      position: absolute;
      top: 50px;
      right: 62px;
      font-size: 78px;
      font-weight: 900;
      color: rgba(248,251,248,.08);
    }}
    .topline {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 28px;
    }}
    .topline span, .eyebrow-pill {{
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      padding: 0 14px;
      border-radius: 8px;
      background: rgba(26,163,154,.16);
      border: 1px solid rgba(26,163,154,.28);
      color: var(--teal);
      font-size: 14px;
      font-weight: 900;
    }}
    .code-page .topline span, .closing-page .topline span, .cover .eyebrow-pill {{
      color: var(--teal-2);
      background: rgba(26,163,154,.16);
      border-color: rgba(133,222,215,.28);
    }}
    .topline b {{
      font-size: 58px;
      color: rgba(16,37,52,.14);
      line-height: 1;
    }}
    .code-page .topline b, .closing-page .topline b {{ color: rgba(248,251,248,.1); }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{
      width: 880px;
      margin-top: 108px;
      font-size: 70px;
      line-height: 1.08;
      font-weight: 900;
    }}
    h2 {{
      max-width: 1300px;
      font-size: 42px;
      line-height: 1.22;
      font-weight: 900;
      color: var(--navy);
    }}
    .code-page h2, .closing-page h2 {{ color: var(--white); }}
    h3 {{ font-size: 24px; color: var(--navy); }}
    .lead {{
      margin-top: 18px;
      font-size: 23px;
      line-height: 1.65;
      color: var(--muted);
      font-weight: 600;
    }}
    .lead.wide {{ max-width: 1280px; }}
    .cover-copy p {{
      width: 820px;
      margin-top: 22px;
      font-size: 25px;
      line-height: 1.5;
      color: rgba(248,251,248,.82);
    }}
    .fact-row, .meta-row {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .fact-row {{ margin-top: 38px; width: 760px; }}
    .fact-row span, .meta-row span {{
      border: 1px solid rgba(133,222,215,.34);
      background: rgba(248,251,248,.08);
      border-radius: 8px;
      padding: 12px 16px;
      font-weight: 900;
    }}
    .meta-row {{
      position: absolute;
      left: 68px;
      right: 68px;
      bottom: 34px;
      justify-content: space-between;
      color: rgba(248,251,248,.86);
    }}
    .orbital-board {{
      position: absolute;
      right: 68px;
      top: 190px;
      width: 440px;
      height: 410px;
      border: 1px solid rgba(133,222,215,.32);
      border-radius: 18px;
      background:
        linear-gradient(90deg, rgba(133,222,215,.1) 1px, transparent 1px),
        linear-gradient(180deg, rgba(133,222,215,.1) 1px, transparent 1px),
        rgba(18,50,65,.82);
      background-size: 42px 42px;
      transform: rotate(-4deg);
    }}
    .orbit-line {{
      position: absolute;
      inset: 68px 44px;
      border: 3px solid rgba(133,222,215,.72);
      border-radius: 50%;
      transform: rotate(-12deg);
    }}
    .tile {{
      position: absolute;
      padding: 11px 15px;
      border-radius: 8px;
      border: 1px solid rgba(255,255,255,.24);
      background: rgba(255,255,255,.11);
      font-weight: 900;
      transform: rotate(4deg);
    }}
    .t1 {{ left: 34px; top: 42px; }}
    .t2 {{ right: 44px; top: 142px; }}
    .t3 {{ left: 140px; bottom: 42px; }}
    .t4 {{ right: 76px; bottom: 84px; }}
    .scan-panel {{
      position: absolute;
      left: 154px;
      top: 152px;
      width: 142px;
      height: 106px;
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      padding: 12px;
      background: rgba(7,25,35,.72);
      border: 1px solid rgba(133,222,215,.24);
      border-radius: 12px;
      transform: rotate(4deg);
    }}
    .scan-panel span {{ background: linear-gradient(135deg, var(--teal), var(--amber)); border-radius: 4px; opacity: .66; }}
    .scan-panel strong {{ grid-column: 1 / -1; font-size: 12px; line-height: 1.2; }}
    .intro-grid {{
      display: grid;
      grid-template-columns: 1fr 230px;
      gap: 44px;
      align-items: start;
    }}
    .route-mark {{
      height: 190px;
      display: grid;
      place-items: center;
      border-radius: 20px;
      color: var(--white);
      background: linear-gradient(135deg, var(--navy), var(--panel-2));
      font-size: 76px;
      font-weight: 900;
      text-align: center;
    }}
    .route-mark small {{ display: block; font-size: 20px; color: var(--teal-2); }}
    .roadmap-grid {{
      margin-top: 34px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
    }}
    .roadmap-grid article, .dense-card-grid article, .mini-cards article, .analysis-cards article, .stack-grid article, .compare-card, .closing-grid article {{
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255,255,255,.62);
      padding: 22px;
    }}
    .roadmap-grid span, .stack-grid span {{
      color: var(--amber);
      font-weight: 900;
      font-size: 18px;
    }}
    .roadmap-grid strong, .dense-card-grid strong, .mini-cards strong, .analysis-cards strong, .compare-card strong, .closing-grid strong {{
      display: block;
      margin: 8px 0 10px;
      font-size: 22px;
      color: var(--navy);
    }}
    .roadmap-grid p, .dense-card-grid p, .mini-cards p, .analysis-cards p, .stack-grid p, .compare-card li, .closing-grid li {{
      font-size: 17px;
      line-height: 1.55;
      color: #40525b;
    }}
    .dense-card-grid {{
      margin-top: 28px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
    }}
    .callout {{
      margin-top: 24px;
      padding: 18px 22px;
      border-left: 8px solid var(--amber);
      background: rgba(217,144,55,.14);
      border-radius: 10px;
      color: var(--navy);
      font-size: 22px;
      line-height: 1.45;
      font-weight: 800;
    }}
    .compare-grid {{
      margin-top: 32px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
    }}
    .compare-card strong {{ font-size: 28px; }}
    .compare-card ul, .closing-grid ul, .code-layout aside ul {{ margin: 14px 0 0; padding-left: 24px; }}
    .compare-card li {{ margin: 12px 0; font-size: 21px; }}
    .compare-card.accent {{ background: rgba(26,163,154,.12); border-color: rgba(26,163,154,.3); }}
    .compare-card.muted {{ background: rgba(201,88,63,.08); border-color: rgba(201,88,63,.22); }}
    .requirements-grid {{
      margin-top: 28px;
      display: grid;
      grid-template-columns: 1.25fr .9fr;
      gap: 26px;
    }}
    .mini-cards {{
      margin-top: 16px;
      display: grid;
      gap: 14px;
    }}
    .mini-cards article {{ padding: 16px 18px; }}
    .mini-cards strong {{ font-size: 20px; margin: 0 0 8px; }}
    .mini-cards p {{ font-size: 16px; }}
    .scope-grid {{
      margin-top: 30px;
      display: grid;
      grid-template-columns: 1.25fr .55fr;
      gap: 24px;
      align-items: stretch;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 12px;
      background: rgba(255,255,255,.66);
      box-shadow: inset 0 0 0 1px var(--line);
    }}
    th {{
      background: var(--navy);
      color: var(--white);
      font-size: 17px;
      text-align: left;
      padding: 15px 16px;
    }}
    td {{
      border-top: 1px solid rgba(16,37,52,.12);
      padding: 15px 16px;
      font-size: 17px;
      line-height: 1.45;
      color: #263d49;
      vertical-align: top;
    }}
    td:first-child {{ font-weight: 900; color: var(--navy); }}
    .scope-grid aside {{
      padding: 24px;
      border-radius: 12px;
      color: var(--white);
      background: var(--panel);
    }}
    .scope-grid aside strong {{ font-size: 24px; color: var(--teal-2); }}
    .scope-grid aside li {{ margin: 16px 0; font-size: 19px; line-height: 1.5; }}
    .image-analysis, .flow-grid, .screenshot-grid {{
      margin-top: 26px;
      display: grid;
      grid-template-columns: 1.08fr .9fr;
      gap: 24px;
      align-items: stretch;
    }}
    figure {{
      margin: 0;
      border: 1px solid rgba(16,37,52,.14);
      border-radius: 12px;
      background: rgba(255,255,255,.7);
      overflow: hidden;
    }}
    figure img {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }}
    .image-analysis figure, .flow-grid figure {{ height: 520px; padding: 18px; }}
    .analysis-cards {{
      display: grid;
      gap: 14px;
    }}
    .analysis-cards article {{ padding: 18px; }}
    .analysis-cards strong {{ margin: 0 0 8px; font-size: 20px; color: var(--teal); }}
    .analysis-cards p {{ font-size: 16px; }}
    .analysis-cards.compact article {{ padding: 16px; }}
    .stack-grid {{
      margin-top: 34px;
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 22px;
    }}
    .stack-grid article {{
      min-height: 150px;
      padding: 24px;
      border-radius: 12px;
      background: var(--panel);
      color: var(--white);
      border: 1px solid rgba(133,222,215,.22);
    }}
    .stack-grid strong {{ display: block; margin: 12px 0; color: var(--white); font-size: 28px; }}
    .stack-grid p {{ color: rgba(248,251,248,.76); font-size: 18px; line-height: 1.55; }}
    .matrix {{
      margin-top: 28px;
      font-size: 16px;
    }}
    .matrix.small td, .matrix.small th {{ padding: 11px 14px; font-size: 15px; }}
    .result-grid {{
      margin-top: 24px;
      display: grid;
      grid-template-columns: .95fr .55fr .7fr;
      gap: 18px;
    }}
    .result-grid figure {{ height: 500px; padding: 16px; }}
    .file-tree {{
      padding: 22px;
      border-radius: 12px;
      color: var(--teal-2);
      background: var(--navy);
      font-family: var(--mono);
      font-size: 18px;
      line-height: 1.75;
    }}
    .file-tree span {{ display: block; white-space: pre; }}
    .screenshot-grid {{
      grid-template-columns: 1.1fr .58fr;
    }}
    .screenshot-grid figure {{ height: 545px; padding: 12px; }}
    .screenshot-grid aside {{
      border-radius: 14px;
      padding: 24px;
      background: var(--panel);
      color: var(--white);
    }}
    .chip-list {{
      display: grid;
      gap: 12px;
    }}
    .chip-list span {{
      display: block;
      padding: 14px 16px;
      border-radius: 9px;
      background: rgba(133,222,215,.12);
      border: 1px solid rgba(133,222,215,.24);
      color: var(--teal-2);
      font-size: 19px;
      font-weight: 900;
      line-height: 1.4;
    }}
    .screenshot-grid aside p {{
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid rgba(248,251,248,.14);
      font-size: 20px;
      line-height: 1.55;
      color: rgba(248,251,248,.84);
    }}
    .code-layout {{
      margin-top: 22px;
      display: grid;
      grid-template-columns: 1fr 360px;
      gap: 22px;
      align-items: stretch;
    }}
    .code-card {{
      border: 1px solid rgba(133,222,215,.24);
      border-radius: 12px;
      background: rgba(2,13,19,.64);
      overflow: hidden;
    }}
    .code-head {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      padding: 14px 18px;
      border-bottom: 1px solid rgba(133,222,215,.18);
      color: var(--teal-2);
      font-size: 14px;
    }}
    .code-head span {{ color: rgba(248,251,248,.62); font-family: var(--mono); text-align: right; }}
    pre {{
      margin: 0;
      padding: 18px 20px 22px;
      white-space: pre-wrap;
      color: #e7fbf9;
      font-family: var(--mono);
      font-size: 12.5px;
      line-height: 1.55;
    }}
    .code-layout aside {{
      padding: 24px;
      border: 1px solid rgba(133,222,215,.24);
      border-radius: 12px;
      background: rgba(18,50,65,.82);
    }}
    .code-layout aside strong {{
      display: block;
      color: var(--teal-2);
      font-size: 25px;
      margin-bottom: 14px;
    }}
    .code-layout aside li {{
      margin: 14px 0;
      font-size: 18px;
      line-height: 1.55;
      color: rgba(248,251,248,.84);
    }}
    .test-methods {{
      margin-top: 26px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
    }}
    .test-methods article {{
      padding: 18px;
      border-radius: 12px;
      background: rgba(255,255,255,.66);
      border: 1px solid var(--line);
    }}
    .test-methods strong {{ display: block; color: var(--teal); font-size: 20px; margin-bottom: 8px; }}
    .test-methods p {{ color: #40525b; line-height: 1.45; font-size: 15px; }}
    .gallery-grid {{
      margin-top: 26px;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
    }}
    .gallery-grid figure {{
      height: 390px;
      display: grid;
      grid-template-rows: 1fr 92px;
      padding: 12px;
    }}
    .gallery-grid img {{ height: 100%; }}
    .gallery-grid figcaption {{
      display: grid;
      gap: 4px;
      align-content: center;
      padding: 10px 4px 0;
      text-align: center;
    }}
    .gallery-grid strong {{ color: var(--navy); font-size: 20px; }}
    .gallery-grid span {{ color: var(--muted); font-size: 14px; line-height: 1.35; }}
    .closing-grid {{
      margin-top: 36px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 22px;
    }}
    .closing-grid article {{
      min-height: 320px;
      background: rgba(248,251,248,.08);
      border-color: rgba(133,222,215,.22);
    }}
    .closing-grid strong {{ color: var(--teal-2); font-size: 27px; }}
    .closing-grid li {{ color: rgba(248,251,248,.82); font-size: 19px; margin: 14px 0; }}
    .thanks {{
      margin-top: 34px;
      padding: 22px;
      text-align: center;
      border-radius: 12px;
      background: rgba(26,163,154,.16);
      color: var(--white);
      font-size: 29px;
      font-weight: 900;
    }}
    .missing {{
      height: 100%;
      display: grid;
      place-items: center;
      color: var(--muted);
      background: rgba(255,255,255,.55);
    }}
    .missing span {{ display: block; margin-top: 8px; color: var(--coral); }}
  </style>
</head>
<body>
  <nav class="nav">{nav}</nav>
  <main class="deck">{slides}</main>
  <script>
    (() => {{
      const params = new URLSearchParams(window.location.search);
      const capture = params.get("capture");
      if (!capture) return;
      document.documentElement.classList.add("capture-mode");
      const targetId = "slide-" + capture;
      document.querySelectorAll(".slide").forEach((slide) => {{
        if (slide.id !== targetId) slide.remove();
      }});
    }})();
  </script>
</body>
</html>"""


def write_html(assets: Dict[str, str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = build_html(assets)
    HTML_PATH.write_text(html, encoding="utf-8")
    INDEX_PATH.write_text(html, encoding="utf-8")


def make_contact_sheet(slide_images: List[Path]) -> None:
    tw, th = 320, 180
    pad, label_h = 18, 28
    cols = 5
    rows = (len(slide_images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + label_h + pad) + pad), (232, 230, 219))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(slide_images):
        x = pad + (idx % cols) * (tw + pad)
        y = pad + (idx // cols) * (th + label_h + pad)
        draw.text((x, y), path.stem, fill=(7, 25, 35))
        img = Image.open(path).convert("RGB").resize((tw, th))
        sheet.paste(img, (x, y + label_h))
    sheet.save(CONTACT_SHEET)


def main() -> None:
    base.SLIDES = SLIDES
    assets = base.copy_assets()
    write_html(assets)
    slide_images = base.render_html_to_png()
    base.build_pptx(slide_images)
    base.write_manifest(assets, slide_images)
    make_contact_sheet(slide_images)
    print(HTML_PATH)
    print(PPTX_PATH)
    print(CONTACT_SHEET)


if __name__ == "__main__":
    main()
