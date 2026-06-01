from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "ppt" / "web_relayout_v2"
ASSET_DIR = OUT_DIR / "assets"
SLIDES_DIR = OUT_DIR / "slides"
HTML_PATH = OUT_DIR / "基于Web的Landsat8遥感影像在线预处理系统-30页网页设计稿.html"
INDEX_PATH = OUT_DIR / "index.html"
MANIFEST_PATH = OUT_DIR / "build-manifest.json"
PPTX_PATH = ROOT / "output" / "ppt" / "基于Web的Landsat8遥感影像在线预处理系统-30页网页设计稿重设计版.pptx"

PPT_CX = 12192000
PPT_CY = 6858000
CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]


RAW_ASSETS = {
    "single": ROOT / "docs/thesis-prep/materials/screenshots/ss-4-01-single-task-overview.png",
    "aoi": ROOT / "docs/thesis-prep/materials/screenshots/ss-4-02-single-task-aoi-config.png",
    "batch": ROOT / "docs/thesis-prep/materials/screenshots/ss-4-03-batch-canvas-overview.png",
    "search": ROOT / "output/doc/thesis_enrichment_assets/ss-4-05-imagery-search-page.png",
    "result_center": ROOT / "output/doc/thesis_enrichment_assets/ss-4-08-result-center-overview.png",
    "arch": ROOT / "output/doc/thesis_enrichment_assets/fig-3-01-architecture-enriched.png",
    "l1l2": ROOT / "output/doc/thesis_enrichment_assets/fig-2-02-l1-l2-comparison.png",
    "queue": ROOT / "output/doc/thesis_enrichment_assets/fig-4-04-batch-queue-status.png",
    "download_list": ROOT / "output/doc/thesis_enrichment_assets/fig-4-07-download-task-list.png",
    "preview": ROOT / "output/doc/thesis_enrichment_assets/fig-4-09-result-preview.png",
    "true_color": ROOT / "output/doc/thesis_enrichment_assets/fig-5-01-true-color.png",
    "ndvi": ROOT / "output/doc/thesis_enrichment_assets/fig-5-02-ndvi.png",
    "mask": ROOT / "output/doc/thesis_enrichment_assets/fig-5-03-mask.png",
    "mosaic": ROOT / "output/doc/thesis_enrichment_assets/fig-5-04-mosaic.png",
}


CODE_SNIPPETS = {
    "processor_branch": {
        "title": "L1/L2 分支与主入口",
        "source": "remote_sensing_tools/core/processor.py:848,878",
        "code": """
def process_band(self, band_path: str, band_name: str,
                apply_atm_correction: bool = True,
                atm_correction_method: str = 'DOS',
                product_level: str = 'L1') -> Tuple[np.ndarray, str]:
    normalized_level = self._normalize_product_level(product_level)
    if normalized_level == 'L2':
        return self._load_l2_surface_reflectance(band_path, band_name), 'L2_SCALE'

    dn = self._load_band_array(band_path)
    reflectance = self._compute_toa_reflectance(dn, band_name)
    del dn
    return self._apply_atmospheric_correction(
        reflectance,
        band_name,
        apply_atm_correction,
        atm_correction_method,
    )

def one_click_preprocess(self, band_paths: Dict[str, str], output_dir: str, ...):
    report = self._build_reporter(progress_callback)
    results = self._init_results()
    normalized_level = self._normalize_product_level(product_level)
    results['product_level'] = normalized_level
""",
    },
    "processor_atm": {
        "title": "6S 失败自动回退 DOS",
        "source": "remote_sensing_tools/core/processor.py:188",
        "code": """
def _apply_atmospheric_correction(self, reflectance: np.ndarray, band_name: str,
                                  apply_atm_correction: bool,
                                  atm_correction_method: str) -> Tuple[np.ndarray, str]:
    normalized_method = str(atm_correction_method or 'DOS').upper()
    if not apply_atm_correction or normalized_method in {'NONE', 'NO', 'SKIP', 'SKIPPED'}:
        return reflectance, 'NONE'

    if normalized_method != '6S':
        corrected = dark_object_subtraction(reflectance)
        return corrected, 'DOS'

    try:
        corrected = self.sixs_atmospheric_correction(reflectance, band_name)
        return corrected, '6S'
    except Exception:
        corrected = dark_object_subtraction(reflectance)
        return corrected, 'DOS(6S失败回退)'
""",
    },
    "graph_executor": {
        "title": "批量流程图转任务配置",
        "source": "remote_sensing_tools/services/graph_executor.py:16,108,194",
        "code": """
class GraphExecutor:
    def build_job_configs(self, nodes: List[Dict], edges: List[Dict]) -> Tuple[List[BatchJobConfig], List[str]]:
        output_node = self._find_node(nodes, "output")
        start_node = self._find_node(nodes, "datadir") or self._find_node(nodes, "input")
        forward_reachable = self._reachable_nodes(start_node["id"], edges)
        backward_reachable = self._reverse_reachable_nodes(output_node["id"], edges)
        active_node_ids = forward_reachable & backward_reachable
        sorted_ids = self._topological_sort(active_nodes, active_edges)
        ctx = self._extract_context(sorted_nodes, active_edges)
        scenes = self._collect_scenes(ctx)
        configs = [self._build_single_config(scene, ctx) for scene in scenes]
        return configs, []
""",
    },
    "atmospheric": {
        "title": "6S 封装与 DOS 暗目标法",
        "source": "remote_sensing_tools/operations/atmospheric.py:140,480,522",
        "code": """
class SixSAtmosphericCorrector:
    def compute_coefficients(self) -> SixSCoefficients:
        self._sixs_model = self._setup_sixs_model()
        self._sixs_model.run()
        self._coefficients = self._extract_coefficients(self._sixs_model)
        return self._coefficients

def dark_object_subtraction(reflectance: np.ndarray, percentile: float = 1.0) -> np.ndarray:
    sampled = flat[::step]
    sampled = sampled[np.isfinite(sampled) & (sampled > 0)]
    dark_value = np.float32(np.percentile(sampled, percentile))
    np.subtract(corrected, dark_value, out=corrected)

def cloud_mask_from_qa(qa_band_path: str, confidence_threshold: str = 'medium') -> np.ndarray:
    qa_fields = decode_qa_pixel_bits(qa)
    cloud_mask = np.logical_or.reduce((qa_fields["fill"], qa_fields["cloud"], qa_fields["cloud_shadow"]))
""",
    },
    "synthesis": {
        "title": "合成图与自定义指数",
        "source": "remote_sensing_tools/operations/synthesis.py:63,564,593,1012",
        "code": """
def create_composite(band_paths: Dict[str, str], output_path: str, composite_type: str = 'true_color') -> str:
    bands_to_use = _resolve_composite_bands(composite_type, band_paths)
    if composite_type in index_types:
        return index_creators[composite_type](band_paths, output_path)

def create_custom_index(band_paths: Dict[str, str], output_path: str, formula: str) -> str:
    band_names = _extract_band_names(formula)
    expr = ast.parse(formula, mode='eval')
    result = _eval_formula(expr, band_arrays)

def create_ndvi(...):
    return _normalized_difference_index(..., 'NDVI')

def create_apgi(...):
    if not _is_sentinel2_band_set(band_paths):
        raise Exception("APGI 仅支持 Sentinel-2 L2A 波段")
""",
    },
    "task_results": {
        "title": "结果清单与结果中心",
        "source": "remote_sensing_tools/services/task_results.py:131,210,257",
        "code": """
def build_result_artifacts(result: Optional[Any], output_dir: str, *, include_manifest: bool = False) -> List[ResultArtifactItem]:
    for label, path_value in (result_dict.get("processed_bands") or {}).items():
        add_result_artifact(path_value, category="processed", label=str(label))

def write_task_manifest(...):
    manifest_path = output_path / MANIFEST_FILENAME
    artifacts = build_result_artifacts(result, str(output_path), include_manifest=False)

class TaskResultService:
    def list_result_tasks(self) -> List[ResultTaskItem]:
        merged: Dict[str, ResultTaskItem] = {}
""",
    },
    "path_policy": {
        "title": "路径白名单控制",
        "source": "remote_sensing_tools/utils/path_policy.py:23,70,137",
        "code": """
class PathAccessController:
    def is_allowed(self, raw_path) -> bool:
        candidate = self._resolve_path(raw_path)
        return any(self._is_relative_to(candidate, root) for root in self.allowed_roots)

    def require_directory(self, raw_path, *, access_label: str = "访问目录", must_exist: bool = True, allow_create: bool = False) -> Path:
        self._check_allowed(candidate, path_text, access_label)

    def validate_batch_job_config(self, config: BatchJobConfig) -> BatchJobConfig:
        updates = {"output_dir": str(self.require_directory(config.output_dir, must_exist=False, allow_create=True))}
""",
    },
    "api_client": {
        "title": "前端 API 统一调用",
        "source": "frontend-vue/src/utils/apiClient.js:8",
        "code": """
export function buildApiUrl(apiBase, path) {
  const normalizedPath = String(path || '')
  return `${normalizeApiBase(apiBase)}${normalizedPath.startsWith('/') ? normalizedPath : `/${normalizedPath}`}`
}

export async function apiRequest(apiBase, path, options = {}) {
  const response = await fetch(buildApiUrl(apiBase, path), options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(parseApiErrorDetail(data.detail || data.message || `HTTP ${response.status}`))
  }
  return data
}
""",
    },
    "download_service": {
        "title": "影像检索与后台下载",
        "source": "remote_sensing_tools/services/landsat_download.py:45,265,990",
        "code": """
class LandsatDownloadService:
    PRODUCT_CONFIGS = {
        "landsat": {"products": {"L2": {...}, "L1": {...}}},
        "sentinel-2": {"products": {"L2A": {...}}},
    }

    def list_collections(self, sensor: Optional[str] = None) -> Dict:
        return {"collections": collections, "sensors": sensors, "download_dir": str(self.download_dir)}

    async def _download_in_background(self, task_id: str) -> None:
        async with self._download_semaphore:
            target_dir = self._build_server_target_dir(task_download_root, task)
            target_path = target_dir / task["filename"]
""",
    },
}


SLIDES = [
    {"no": "01", "type": "cover", "eyebrow": "Graduation Defense Archive", "title": "基于 Web 的 Landsat 8 遥感影像在线预处理系统", "subtitle": "Remote Sensing Image Online Preprocessing Platform", "meta": ["答辩人：李旭东", "项目版本：v3.0.0", "2026 年 5 月"]},
    {"no": "02", "type": "section", "eyebrow": "Part I", "title": "课题背景", "subtitle": "从问题定义进入工程方案"},
    {"no": "03", "type": "statement", "eyebrow": "背景 01", "title": "原始遥感影像不能直接拿来做分析", "bullets": ["辐射误差、大气影响、云污染会直接扭曲结果。", "资源调查、农业监测、水体识别都依赖稳定预处理链。", "研究重点不只是算一个指数，而是把整个流程做成可用系统。"]},
    {"no": "04", "type": "statement", "eyebrow": "背景 02", "title": "传统桌面流程碎片化，难以批量复用", "bullets": ["软件切换频繁，参数难复用。", "多景影像重复处理成本高。", "结果散落在文件夹，回溯和展示都不方便。"]},
    {"no": "05", "type": "diagram_loop", "eyebrow": "目标", "title": "本课题的目标是构建本地部署的 Web 化工作台", "items": ["在线取数", "单景处理", "批量编排", "结果归档"]},
    {"no": "06", "type": "section", "eyebrow": "Part II", "title": "系统设计", "subtitle": "从架构、流程、模块划分展开"},
    {"no": "07", "type": "architecture", "eyebrow": "架构 01", "title": "系统总体架构采用前后端分离与分层处理", "image": "arch"},
    {"no": "08", "type": "layer_cards", "eyebrow": "架构 02", "title": "五层职责划分让界面、服务、算法与文件系统边界清晰", "cards": [["表现层", "Vue 3 工作台、AOI 地图、结果中心"], ["接口层", "FastAPI 路由、任务状态、文件下载"], ["服务层", "批量管理、图执行器、下载队列"], ["算法层", "GDAL / NumPy / Py6S / 指数计算"], ["文件层", "data / output / temp / cache / manifest"]]},
    {"no": "09", "type": "process_chain", "eyebrow": "流程 01", "title": "单景处理链从输入文件到结果输出形成闭环", "steps": ["波段 / MTL / QA 输入", "L1/L2 分支判断", "辐射与大气处理", "质量掩膜与裁剪", "合成与指数输出", "结果清单写入"]},
    {"no": "10", "type": "image_note", "eyebrow": "流程 02", "title": "L1 与 L2 双链路是系统处理策略的核心差异", "image": "l1l2", "notes": ["L1 走辐射定标与大气校正链。", "L2 按官方缩放系数直接生成表面反射率。", "这种设计兼顾原始产品和分析型产品。"]},
    {"no": "11", "type": "feature_grid", "eyebrow": "模块 01", "title": "系统围绕四个主工作面组织功能", "cards": [["单景预处理", "上传波段、配置参数、查看结果。"], ["批量处理", "节点式流程编排与队列执行。"], ["在线检索下载", "STAC 检索、资产选择、后台下载。"], ["结果资产中心", "统一扫描任务产物和历史清单。"]]},
    {"no": "12", "type": "section", "eyebrow": "Part III", "title": "界面与交互", "subtitle": "真实工作台截图是最有说服力的证据"},
    {"no": "13", "type": "screenshot_focus", "eyebrow": "界面 01", "title": "单景任务配置页整合输入、监控与预览三块面板", "image": "single", "bullets": ["输入数据、输出目录、ROI 与合成项集中在同一屏。", "任务监控和影像预览并排，适合调参与检查结果。"]},
    {"no": "14", "type": "screenshot_focus", "eyebrow": "界面 02", "title": "AOI 可视化裁剪降低空间参数配置门槛", "image": "aoi", "bullets": ["支持地图绘制与矢量导入。", "把裁剪参数直接和后端处理链联动。"]},
    {"no": "15", "type": "screenshot_focus", "eyebrow": "界面 03", "title": "批量流程画布把重复处理步骤显式化", "image": "batch", "bullets": ["节点、连线、输出路径一眼可见。", "适合展示拓扑依赖和批量执行逻辑。"]},
    {"no": "16", "type": "screenshot_focus", "eyebrow": "界面 04", "title": "在线检索页负责把外部数据接入本地处理链", "image": "search", "bullets": ["AOI、时间范围、传感器和资产选择集成在同一页。", "检索不是终点，而是整条闭环的入口。"]},
    {"no": "17", "type": "screenshot_focus", "eyebrow": "界面 05", "title": "结果资产中心把处理产物从文件夹提升为可检索资产", "image": "result_center", "bullets": ["自动扫描当前任务和历史任务目录。", "按 processed / composite / mask / metadata 分类展示。"]},
    {"no": "18", "type": "section", "eyebrow": "Part IV", "title": "关键实现", "subtitle": "这一部分用真实代码片段说明系统怎么做"},
    {"no": "19", "type": "code", "eyebrow": "代码 01", "title": "处理器主入口按产品级别切换 L1/L2 策略", "snippet": "processor_branch"},
    {"no": "20", "type": "code", "eyebrow": "代码 02", "title": "6S 模型失败时自动回退 DOS，保证任务不中断", "snippet": "processor_atm"},
    {"no": "21", "type": "code", "eyebrow": "代码 03", "title": "图执行器把前端流程图转换为 BatchJobConfig 列表", "snippet": "graph_executor"},
    {"no": "22", "type": "code", "eyebrow": "代码 04", "title": "大气校正模块同时保留物理模型和经验模型", "snippet": "atmospheric"},
    {"no": "23", "type": "code", "eyebrow": "代码 05", "title": "合成模块支持预设指数与自定义公式扩展", "snippet": "synthesis"},
    {"no": "24", "type": "code", "eyebrow": "代码 06", "title": "结果中心依赖 manifest 和统一 artifact 分类", "snippet": "task_results"},
    {"no": "25", "type": "code", "eyebrow": "代码 07", "title": "路径白名单控制保证本地文件访问边界清晰", "snippet": "path_policy"},
    {"no": "26", "type": "code", "eyebrow": "代码 08", "title": "前端统一 API 封装让请求和错误处理口径一致", "snippet": "api_client"},
    {"no": "27", "type": "code", "eyebrow": "代码 09", "title": "影像检索与后台下载服务负责 STAC 接入与断点式重试", "snippet": "download_service"},
    {"no": "28", "type": "section", "eyebrow": "Part V", "title": "结果与结论", "subtitle": "用真实输出、验证项和改进方向收束"},
    {"no": "29", "type": "result_gallery", "eyebrow": "成果 01", "title": "系统已形成合成图、指数图、掩膜与镶嵌结果输出", "images": [["true_color", "真彩色"], ["ndvi", "NDVI"], ["mask", "云掩膜"], ["mosaic", "镶嵌结果"]]},
    {"no": "30", "type": "closing_summary", "eyebrow": "答辩总结", "title": "工程化集成是本项目的真正价值", "left": ["把取数、预处理、批量编排、结果中心做成闭环。", "关键亮点在于 L1/L2 双链路、图执行器、manifest 结果清单和路径安全。"] , "right": ["当前主链仍聚焦 Landsat 8/9。", "后续可扩展更多传感器、增强持久化与自动化测试。"], "closing": "谢谢各位老师，敬请批评指正"},
]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def copy_assets() -> Dict[str, str]:
    ensure_dir(ASSET_DIR)
    copied = {}
    for key, src in RAW_ASSETS.items():
        if not src.exists():
            continue
        target = ASSET_DIR / f"{key}{src.suffix.lower()}"
        shutil.copyfile(src, target)
        copied[key] = f"assets/{target.name}"
    return copied


def html_code_block(snippet_key: str) -> str:
    snippet = CODE_SNIPPETS[snippet_key]
    code = textwrap.dedent(snippet["code"]).strip("\n")
    return (
        f'<div class="code-card">'
        f'<div class="code-card-head"><strong>{snippet["title"]}</strong><span>{snippet["source"]}</span></div>'
        f'<pre><code>{escape(code)}</code></pre></div>'
    )


def image_tag(assets: Dict[str, str], key: str, alt: str) -> str:
    path = assets.get(key)
    if not path:
        return f'<div class="missing">{escape(alt)}<span>素材缺失</span></div>'
    return f'<img src="{escape(path)}" alt="{escape(alt)}" loading="lazy">'


def bullets(items: List[str]) -> str:
    return "".join(f"<li>{escape(item)}</li>" for item in items)


def render_slide(slide: Dict, assets: Dict[str, str]) -> str:
    t = slide["type"]
    if t == "cover":
        meta = "".join(f"<span>{escape(item)}</span>" for item in slide["meta"])
        return f"""
<section class="slide cover" id="slide-{slide['no']}">
  <div class="slide-index">{slide['no']}</div>
  <div class="eyebrow">{escape(slide['eyebrow'])}</div>
  <div class="cover-grid">
    <div class="cover-copy">
      <h1>{escape(slide['title'])}</h1>
      <p>{escape(slide['subtitle'])}</p>
      <div class="cover-tags">
        <span>Web Workbench</span><span>L1/L2</span><span>QA Mask</span><span>Batch Graph</span>
      </div>
    </div>
    <div class="hero-panel">
      <div class="hero-grid"></div>
      <div class="hero-ellipse"></div>
      <div class="hero-chip chip-a">L1/L2</div>
      <div class="hero-chip chip-b">QA</div>
      <div class="hero-chip chip-c">STAC</div>
    </div>
  </div>
  <div class="meta-row">{meta}</div>
</section>"""
    if t == "section":
        return f"""
<section class="slide section-break" id="slide-{slide['no']}">
  <div class="section-frame">
    <span>{escape(slide['eyebrow'])}</span>
    <h2>{escape(slide['title'])}</h2>
    <p>{escape(slide['subtitle'])}</p>
  </div>
</section>"""
    if t == "statement":
        return f"""
<section class="slide paper" id="slide-{slide['no']}">
  <div class="head"><span class="eyebrow">{escape(slide['eyebrow'])}</span><b>{slide['no']}</b></div>
  <h2>{escape(slide['title'])}</h2>
  <ul class="bullet-list">{bullets(slide['bullets'])}</ul>
</section>"""
    if t == "diagram_loop":
        items = "".join(f"<span>{escape(item)}</span>" for item in slide["items"])
        return f"""
<section class="slide paper" id="slide-{slide['no']}">
  <div class="head"><span class="eyebrow">{escape(slide['eyebrow'])}</span><b>{slide['no']}</b></div>
  <h2>{escape(slide['title'])}</h2>
  <div class="loop-board">
    <div class="loop-core">Remote Sensing<br>Workbench</div>
    {items}
  </div>
</section>"""
    if t == "architecture":
        return f"""
<section class="slide paper" id="slide-{slide['no']}">
  <div class="head"><span class="eyebrow">{escape(slide['eyebrow'])}</span><b>{slide['no']}</b></div>
  <h2>{escape(slide['title'])}</h2>
  <figure class="hero-image">{image_tag(assets, slide['image'], slide['title'])}</figure>
</section>"""
    if t == "layer_cards":
        cards = "".join(f"<article><strong>{escape(a)}</strong><p>{escape(b)}</p></article>" for a, b in slide["cards"])
        return f"""
<section class="slide paper" id="slide-{slide['no']}">
  <div class="head"><span class="eyebrow">{escape(slide['eyebrow'])}</span><b>{slide['no']}</b></div>
  <h2>{escape(slide['title'])}</h2>
  <div class="card-grid five">{cards}</div>
</section>"""
    if t == "process_chain":
        steps = "".join(f"<div class='chain-step'><span>{i+1:02d}</span><p>{escape(step)}</p></div>" for i, step in enumerate(slide["steps"]))
        return f"""
<section class="slide dark-sheet" id="slide-{slide['no']}">
  <div class="head"><span class="eyebrow">{escape(slide['eyebrow'])}</span><b>{slide['no']}</b></div>
  <h2>{escape(slide['title'])}</h2>
  <div class="chain-grid">{steps}</div>
</section>"""
    if t == "image_note":
        notes = "".join(f"<li>{escape(item)}</li>" for item in slide["notes"])
        return f"""
<section class="slide paper" id="slide-{slide['no']}">
  <div class="head"><span class="eyebrow">{escape(slide['eyebrow'])}</span><b>{slide['no']}</b></div>
  <h2>{escape(slide['title'])}</h2>
  <div class="split-frame">
    <figure>{image_tag(assets, slide['image'], slide['title'])}</figure>
    <ul class="bullet-list">{notes}</ul>
  </div>
</section>"""
    if t == "feature_grid":
        cards = "".join(f"<article><strong>{escape(a)}</strong><p>{escape(b)}</p></article>" for a, b in slide["cards"])
        return f"""
<section class="slide paper" id="slide-{slide['no']}">
  <div class="head"><span class="eyebrow">{escape(slide['eyebrow'])}</span><b>{slide['no']}</b></div>
  <h2>{escape(slide['title'])}</h2>
  <div class="card-grid four">{cards}</div>
</section>"""
    if t == "screenshot_focus":
        return f"""
<section class="slide paper" id="slide-{slide['no']}">
  <div class="head"><span class="eyebrow">{escape(slide['eyebrow'])}</span><b>{slide['no']}</b></div>
  <h2>{escape(slide['title'])}</h2>
  <div class="split-frame large-shot">
    <figure>{image_tag(assets, slide['image'], slide['title'])}</figure>
    <ul class="bullet-list">{bullets(slide['bullets'])}</ul>
  </div>
</section>"""
    if t == "code":
        return f"""
<section class="slide code-slide" id="slide-{slide['no']}">
  <div class="head"><span class="eyebrow">{escape(slide['eyebrow'])}</span><b>{slide['no']}</b></div>
  <h2>{escape(slide['title'])}</h2>
  {html_code_block(slide['snippet'])}
</section>"""
    if t == "result_gallery":
        gallery = "".join(
            f"<figure>{image_tag(assets, key, label)}<figcaption>{escape(label)}</figcaption></figure>"
            for key, label in slide["images"]
        )
        return f"""
<section class="slide paper" id="slide-{slide['no']}">
  <div class="head"><span class="eyebrow">{escape(slide['eyebrow'])}</span><b>{slide['no']}</b></div>
  <h2>{escape(slide['title'])}</h2>
  <div class="gallery-grid">{gallery}</div>
</section>"""
    if t == "closing_summary":
        left = "".join(f"<li>{escape(item)}</li>" for item in slide["left"])
        right = "".join(f"<li>{escape(item)}</li>" for item in slide["right"])
        return f"""
<section class="slide closing-sheet" id="slide-{slide['no']}">
  <div class="head"><span class="eyebrow">{escape(slide['eyebrow'])}</span><b>{slide['no']}</b></div>
  <h2>{escape(slide['title'])}</h2>
  <div class="closing-columns">
    <article><strong>已完成工作</strong><ul>{left}</ul></article>
    <article><strong>不足与改进</strong><ul>{right}</ul></article>
  </div>
  <div class="closing-bar">{escape(slide['closing'])}</div>
</section>"""
    raise ValueError(f"Unknown slide type: {t}")


def build_html(assets: Dict[str, str]) -> str:
    nav = "".join(
        f"<a href='#slide-{slide['no']}'><span>{slide['no']}</span>{escape(slide['eyebrow'])}</a>"
        for slide in SLIDES
    )
    slides_html = "\n".join(render_slide(slide, assets) for slide in SLIDES)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>基于Web的Landsat8遥感影像在线预处理系统 - 30页网页设计稿</title>
  <style>
    :root {{
      --paper: #f2f0e9;
      --paper-deep: #e7e0d2;
      --ink: #112536;
      --muted: #5a696c;
      --line: #cdc4b2;
      --teal: #107b76;
      --teal-soft: #d8efe9;
      --orange: #d2792c;
      --blue: #1d5a9c;
      --night: #081a24;
      --night-2: #102936;
      --mono: "Cascadia Mono", "Consolas", monospace;
      --display: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
      --body: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at 20% 10%, rgba(16,123,118,.12), transparent 22%),
        radial-gradient(circle at 80% 20%, rgba(210,121,44,.12), transparent 18%),
        #dde2de;
      color: var(--ink);
      font-family: var(--body);
    }}
    .nav {{
      position: sticky;
      top: 0;
      z-index: 30;
      display: flex;
      gap: 10px;
      align-items: center;
      padding: 12px 18px;
      background: rgba(242,240,233,.92);
      border-bottom: 1px solid rgba(17,37,54,.12);
      backdrop-filter: blur(12px);
      overflow-x: auto;
      white-space: nowrap;
    }}
    .nav strong {{ font-size: 15px; }}
    .nav a {{
      display: inline-flex;
      gap: 6px;
      align-items: center;
      min-height: 34px;
      padding: 0 11px;
      border: 1px solid rgba(17,37,54,.14);
      border-radius: 8px;
      background: rgba(255,255,255,.72);
      color: var(--ink);
      text-decoration: none;
      font-size: 13px;
    }}
    .nav a span {{ color: var(--teal); font-weight: 800; }}
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
      border: 1px solid rgba(17,37,54,.1);
      box-shadow: 0 22px 64px rgba(17,37,54,.14);
    }}
    html.capture-mode,
    html.capture-mode body {{
      width: 1600px;
      height: 900px;
      margin: 0;
      overflow: hidden;
      background: var(--paper);
    }}
    html.capture-mode .nav {{
      display: none;
    }}
    html.capture-mode .deck {{
      display: block;
      width: 1600px;
      height: 900px;
      padding: 0;
      margin: 0;
    }}
    html.capture-mode .slide {{
      width: 1600px;
      height: 900px;
      aspect-ratio: auto;
      border: 0;
      box-shadow: none;
    }}
    .paper {{
      background:
        linear-gradient(90deg, rgba(17,37,54,.04) 1px, transparent 1px),
        linear-gradient(180deg, rgba(16,123,118,.035) 1px, transparent 1px),
        var(--paper);
      background-size: 44px 44px;
      padding: 54px 62px;
    }}
    .cover {{
      background:
        radial-gradient(circle at 72% 24%, rgba(29,90,156,.35), transparent 24%),
        linear-gradient(135deg, rgba(8,26,36,.96), rgba(8,26,36,.78)),
        var(--night);
      color: #f6f7f3;
      padding: 58px 70px 44px;
    }}
    .section-break {{
      background:
        linear-gradient(135deg, rgba(8,26,36,.92), rgba(16,41,54,.84)),
        var(--night);
      color: #f8f5ef;
      display: grid;
      place-items: center;
      padding: 70px;
    }}
    .dark-sheet {{
      background:
        radial-gradient(circle at 80% 15%, rgba(16,123,118,.20), transparent 24%),
        linear-gradient(120deg, rgba(29,90,156,.18), transparent 42%),
        var(--night);
      color: #eef5f6;
      padding: 54px 62px;
    }}
    .code-slide {{
      background:
        linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px),
        linear-gradient(180deg, rgba(255,255,255,.04) 1px, transparent 1px),
        linear-gradient(135deg, #0e1e29, #122733);
      background-size: 36px 36px;
      color: #eff7f9;
      padding: 54px 62px;
    }}
    .closing-sheet {{
      background:
        linear-gradient(135deg, rgba(8,26,36,.95), rgba(16,41,54,.88)),
        var(--night);
      color: #eef5f6;
      padding: 54px 62px;
    }}
    .slide-index {{
      position: absolute;
      right: 70px;
      top: 48px;
      font-family: var(--display);
      font-size: 86px;
      color: rgba(255,255,255,.08);
      letter-spacing: 0;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      padding: 0 12px;
      border-radius: 8px;
      background: var(--teal-soft);
      color: var(--teal);
      font-size: 14px;
      font-weight: 800;
    }}
    .cover .eyebrow,
    .dark-sheet .eyebrow,
    .code-slide .eyebrow,
    .closing-sheet .eyebrow {{
      background: rgba(16,123,118,.18);
      border: 1px solid rgba(16,123,118,.35);
      color: #74d7d0;
    }}
    .head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 18px;
    }}
    .head b {{
      font-family: var(--display);
      font-size: 54px;
      color: rgba(17,37,54,.18);
      letter-spacing: 0;
    }}
    .dark-sheet .head b,
    .code-slide .head b,
    .closing-sheet .head b {{
      color: rgba(255,255,255,.12);
    }}
    h1, h2, h3, p, ul {{ margin: 0; }}
    h1 {{
      max-width: 760px;
      font-size: 86px;
      line-height: .95;
      letter-spacing: 0;
      margin-top: 28px;
    }}
    h2 {{
      max-width: 1020px;
      font-size: 44px;
      line-height: 1.12;
      letter-spacing: 0;
    }}
    .cover-copy p {{
      margin-top: 22px;
      font-size: 21px;
      color: #bdd3d7;
    }}
    .cover-grid {{
      display: grid;
      grid-template-columns: 1fr 460px;
      gap: 48px;
      margin-top: 18px;
      align-items: center;
      height: calc(100% - 120px);
    }}
    .cover-tags {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      max-width: 520px;
      margin-top: 56px;
    }}
    .cover-tags span {{
      padding: 14px 16px;
      border: 1px solid rgba(116,215,208,.35);
      border-radius: 8px;
      background: rgba(255,255,255,.06);
      font-size: 18px;
      font-weight: 700;
    }}
    .hero-panel {{
      position: relative;
      height: 430px;
      border: 1px solid rgba(116,215,208,.35);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(16,123,118,.18), transparent 34%),
        linear-gradient(315deg, rgba(29,90,156,.22), transparent 44%),
        #0f2731;
      overflow: hidden;
    }}
    .hero-grid {{
      position: absolute;
      inset: 24px;
      background:
        linear-gradient(90deg, rgba(255,255,255,.1) 1px, transparent 1px),
        linear-gradient(180deg, rgba(255,255,255,.1) 1px, transparent 1px);
      background-size: 38px 38px;
      transform: rotate(-9deg);
    }}
    .hero-ellipse {{
      position: absolute;
      left: 40px;
      right: 54px;
      top: 76px;
      bottom: 72px;
      border: 2px solid rgba(116,215,208,.6);
      border-radius: 50%;
      transform: rotate(-16deg);
    }}
    .hero-chip {{
      position: absolute;
      min-width: 72px;
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px solid rgba(255,255,255,.18);
      background: rgba(255,255,255,.1);
      font-family: var(--body);
      font-size: 17px;
      font-weight: 900;
      text-align: center;
    }}
    .chip-a {{ left: 34px; top: 42px; }}
    .chip-b {{ right: 42px; top: 134px; }}
    .chip-c {{ left: 132px; bottom: 44px; }}
    .meta-row {{
      position: absolute;
      left: 70px;
      right: 70px;
      bottom: 30px;
      display: flex;
      justify-content: space-between;
      color: #d8e7ea;
      font-size: 17px;
    }}
    .section-frame {{
      width: 78%;
      padding: 54px 58px;
      border: 1px solid rgba(255,255,255,.2);
      border-radius: 8px;
      background: rgba(255,255,255,.04);
      text-align: left;
    }}
    .section-frame span {{
      display: inline-block;
      color: #74d7d0;
      font-family: var(--display);
      font-size: 30px;
      letter-spacing: .05em;
    }}
    .section-frame h2 {{
      margin-top: 16px;
      font-size: 72px;
      max-width: none;
    }}
    .section-frame p {{
      margin-top: 18px;
      font-size: 24px;
      color: #d6e2e4;
    }}
    .bullet-list {{
      display: grid;
      gap: 18px;
      margin-top: 42px;
      padding: 0;
      list-style: none;
      max-width: 980px;
    }}
    .bullet-list li {{
      position: relative;
      padding-left: 28px;
      font-size: 26px;
      line-height: 1.42;
    }}
    .bullet-list li::before {{
      content: "";
      position: absolute;
      left: 0;
      top: 16px;
      width: 11px;
      height: 11px;
      border-radius: 8px;
      background: var(--teal);
    }}
    .dark-sheet .bullet-list li::before,
    .closing-sheet .bullet-list li::before {{
      background: #74d7d0;
    }}
    .loop-board {{
      position: relative;
      margin: 36px auto 0;
      width: 74%;
      height: 430px;
      border: 1px solid rgba(17,37,54,.14);
      border-radius: 8px;
      background: rgba(255,255,255,.72);
    }}
    .loop-core {{
      position: absolute;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%);
      width: 230px;
      height: 118px;
      display: grid;
      place-items: center;
      border-radius: 8px;
      background: #122d3a;
      color: #fff;
      text-align: center;
      font-size: 28px;
      font-weight: 800;
      line-height: 1.2;
    }}
    .loop-board span {{
      position: absolute;
      width: 170px;
      height: 74px;
      display: grid;
      place-items: center;
      border-radius: 8px;
      border: 1px solid rgba(16,123,118,.24);
      background: #eaf5f2;
      color: var(--teal);
      font-size: 22px;
      font-weight: 800;
    }}
    .loop-board span:nth-of-type(1) {{ left: 60px; top: 60px; }}
    .loop-board span:nth-of-type(2) {{ right: 60px; top: 60px; }}
    .loop-board span:nth-of-type(3) {{ right: 60px; bottom: 60px; }}
    .loop-board span:nth-of-type(4) {{ left: 60px; bottom: 60px; }}
    .hero-image {{
      margin: 34px auto 0;
      width: 92%;
      height: 500px;
      padding: 18px;
      border: 1px solid rgba(17,37,54,.12);
      border-radius: 8px;
      background: rgba(255,255,255,.78);
    }}
    img {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
      border-radius: 6px;
    }}
    .card-grid {{
      display: grid;
      gap: 16px;
      margin-top: 34px;
    }}
    .card-grid.five {{ grid-template-columns: repeat(5, minmax(0, 1fr)); }}
    .card-grid.four {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
    .card-grid article {{
      min-height: 240px;
      padding: 22px 18px;
      border: 1px solid rgba(17,37,54,.12);
      border-top: 6px solid var(--teal);
      border-radius: 8px;
      background: rgba(255,255,255,.78);
    }}
    .card-grid article:nth-child(2) {{ border-top-color: var(--blue); }}
    .card-grid article:nth-child(3) {{ border-top-color: var(--orange); }}
    .card-grid article:nth-child(4) {{ border-top-color: #4b875f; }}
    .card-grid article:nth-child(5) {{ border-top-color: #7564a7; }}
    .card-grid strong {{
      display: block;
      font-size: 24px;
      line-height: 1.25;
    }}
    .card-grid p {{
      margin-top: 16px;
      color: var(--muted);
      font-size: 18px;
      line-height: 1.48;
    }}
    .chain-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin-top: 36px;
    }}
    .chain-step {{
      min-height: 150px;
      padding: 18px;
      border: 1px solid rgba(116,215,208,.24);
      border-radius: 8px;
      background: rgba(255,255,255,.06);
    }}
    .chain-step span {{
      font-family: var(--display);
      font-size: 30px;
      color: #74d7d0;
      letter-spacing: .03em;
    }}
    .chain-step p {{
      margin-top: 16px;
      font-size: 22px;
      line-height: 1.4;
    }}
    .split-frame {{
      display: grid;
      grid-template-columns: 1.15fr .85fr;
      gap: 30px;
      align-items: start;
      margin-top: 30px;
    }}
    .split-frame.large-shot {{
      grid-template-columns: 1.2fr .8fr;
    }}
    .split-frame figure {{
      margin: 0;
      height: 465px;
      padding: 14px;
      border: 1px solid rgba(17,37,54,.12);
      border-radius: 8px;
      background: rgba(255,255,255,.78);
    }}
    .split-frame.large-shot figure {{
      height: 520px;
    }}
    .code-card {{
      margin-top: 28px;
      border: 1px solid rgba(116,215,208,.18);
      border-radius: 8px;
      background: rgba(3,10,15,.48);
      overflow: hidden;
    }}
    .code-card-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 20px;
      padding: 16px 20px;
      border-bottom: 1px solid rgba(116,215,208,.16);
      background: rgba(255,255,255,.03);
    }}
    .code-card-head strong {{
      font-size: 20px;
      color: #fff;
    }}
    .code-card-head span {{
      color: #84c8d1;
      font-size: 12px;
      font-family: var(--mono);
    }}
    pre {{
      margin: 0;
      padding: 18px 20px 22px;
      overflow: hidden;
      font-family: var(--mono);
      font-size: 14px;
      line-height: 1.55;
      color: #e6f0f2;
      white-space: pre-wrap;
    }}
    .gallery-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      margin-top: 30px;
    }}
    .gallery-grid figure {{
      margin: 0;
      height: 244px;
      padding: 10px;
      border: 1px solid rgba(17,37,54,.12);
      border-radius: 8px;
      background: rgba(255,255,255,.78);
    }}
    .gallery-grid img {{
      height: 196px;
    }}
    figcaption {{
      margin-top: 10px;
      font-size: 16px;
      font-weight: 700;
      color: var(--muted);
      text-align: center;
    }}
    .closing-columns {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      margin-top: 32px;
    }}
    .closing-columns article {{
      min-height: 340px;
      padding: 22px 22px 24px;
      border: 1px solid rgba(255,255,255,.12);
      border-radius: 8px;
      background: rgba(255,255,255,.05);
    }}
    .closing-columns strong {{
      display: block;
      color: #74d7d0;
      font-size: 24px;
    }}
    .closing-columns ul {{
      display: grid;
      gap: 14px;
      margin: 22px 0 0;
      padding-left: 22px;
      font-size: 22px;
      line-height: 1.42;
    }}
    .closing-bar {{
      margin-top: 22px;
      min-height: 66px;
      display: grid;
      place-items: center;
      border-radius: 8px;
      background: #13303b;
      color: #fff;
      font-size: 28px;
      font-weight: 800;
      text-align: center;
    }}
    .missing {{
      width: 100%;
      height: 100%;
      display: grid;
      place-items: center;
      border: 1px dashed rgba(17,37,54,.25);
      border-radius: 6px;
      color: var(--muted);
      text-align: center;
      font-size: 18px;
      background: rgba(255,255,255,.7);
    }}
    .missing span {{
      display: block;
      margin-top: 8px;
      font-size: 14px;
    }}
    @media print {{
      body {{ background: #fff; }}
      .nav {{ display: none; }}
      .deck {{ padding: 0; gap: 0; }}
      .slide {{
        width: 100vw;
        height: 100vh;
        border: 0;
        box-shadow: none;
        page-break-after: always;
      }}
    }}
  </style>
</head>
<body>
  <nav class="nav"><strong>答辩网页设计稿 / 30 Slides</strong>{nav}</nav>
  <main class="deck">
    {slides_html}
  </main>
  <script>
    (() => {{
      const params = new URLSearchParams(window.location.search);
      const capture = params.get("capture");
      if (!capture) return;

      document.documentElement.classList.add("capture-mode");
      const targetId = "slide-" + capture;
      document.querySelectorAll(".slide").forEach((slide) => {{
        if (slide.id !== targetId) {{
          slide.remove();
        }}
      }});
    }})();
  </script>
</body>
</html>"""


def write_html(assets: Dict[str, str]) -> None:
    ensure_dir(OUT_DIR)
    html = build_html(assets)
    HTML_PATH.write_text(html, encoding="utf-8")
    INDEX_PATH.write_text(html, encoding="utf-8")


def find_browser() -> Path:
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate

    for command in ("chrome", "chrome.exe", "msedge", "msedge.exe"):
        resolved = shutil.which(command)
        if resolved:
            return Path(resolved)

    raise FileNotFoundError("未找到可用于 HTML 截图的 Chrome 或 Edge 浏览器")


def render_html_to_png() -> List[Path]:
    ensure_dir(SLIDES_DIR)
    browser = find_browser()
    profile_dir = OUT_DIR / "chrome-profile"
    ensure_dir(profile_dir)
    html_uri = HTML_PATH.resolve().as_uri()
    slide_images = []

    for i in range(1, len(SLIDES) + 1):
        no = f"{i:02d}"
        out = SLIDES_DIR / f"slide-{no}.png"
        if out.exists():
            out.unlink()
        subprocess.run(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--allow-file-access-from-files",
                "--window-size=1600,900",
                f"--user-data-dir={profile_dir}",
                f"--screenshot={out}",
                f"{html_uri}?capture={no}",
            ],
            check=True,
            cwd=str(ROOT),
        )
        slide_images.append(out)

    return slide_images


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
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>基于Web的Landsat8遥感影像在线预处理系统-30页网页设计稿重设计版</dc:title>
<dc:creator>Codex</dc:creator>
<cp:lastModifiedBy>Codex</cp:lastModifiedBy>
<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
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
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
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
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Archive Defense Theme">
<a:themeElements><a:clrScheme name="Archive"><a:dk1><a:srgbClr val="112536"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="081A24"/></a:dk2><a:lt2><a:srgbClr val="F2F0E9"/></a:lt2><a:accent1><a:srgbClr val="107B76"/></a:accent1><a:accent2><a:srgbClr val="1D5A9C"/></a:accent2><a:accent3><a:srgbClr val="D2792C"/></a:accent3><a:accent4><a:srgbClr val="4B875F"/></a:accent4><a:accent5><a:srgbClr val="7564A7"/></a:accent5><a:accent6><a:srgbClr val="CFC0A8"/></a:accent6><a:hlink><a:srgbClr val="1D5A9C"/></a:hlink><a:folHlink><a:srgbClr val="7564A7"/></a:folHlink></a:clrScheme><a:fontScheme name="Archive"><a:majorFont><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Microsoft YaHei"/></a:majorFont><a:minorFont><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Microsoft YaHei"/></a:minorFont></a:fontScheme><a:fmtScheme name="Archive"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>'''


def build_pptx(slide_images: List[Path]) -> None:
    PPTX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(PPTX_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types(len(slide_images)))
        z.writestr("_rels/.rels", package_rels())
        z.writestr("docProps/core.xml", core_props())
        z.writestr("docProps/app.xml", app_props(len(slide_images)))
        z.writestr("ppt/presentation.xml", presentation_xml(len(slide_images)))
        z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slide_images)))
        z.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels())
        z.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels())
        z.writestr("ppt/theme/theme1.xml", theme_xml())
        for i, path in enumerate(slide_images, 1):
            z.write(path, f"ppt/media/image{i}.png")
            z.writestr(f"ppt/slides/slide{i}.xml", slide_xml(i))
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide_rels(i))


def write_manifest(assets: Dict[str, str], slide_images: List[Path]) -> None:
    manifest = {
        "html": str(HTML_PATH),
        "index": str(INDEX_PATH),
        "pptx": str(PPTX_PATH),
        "slide_count": len(SLIDES),
        "slides_dir": str(SLIDES_DIR),
        "slide_previews": [str(path) for path in slide_images],
        "assets": assets,
        "code_snippet_count": sum(1 for slide in SLIDES if slide["type"] == "code"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    assets = copy_assets()
    write_html(assets)
    slide_images = render_html_to_png()
    build_pptx(slide_images)
    write_manifest(assets, slide_images)
    print(HTML_PATH)
    print(PPTX_PATH)


if __name__ == "__main__":
    main()
