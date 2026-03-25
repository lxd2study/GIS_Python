"""API route definitions."""

import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from ..core.config import settings
from ..core.constants import BAND_INFO, COMPOSITE_MAP
from ..core.processor import Landsat8Processor
from ..core.models import (
    BatchSubmitRequest,
    GraphSubmitRequest,
    LandsatAuthRequest,
    LandsatDownloadTaskCreateRequest,
    LandsatSearchRequest,
    TaskQueueItem,
)
from ..services.file_manager import FileManager
from ..services.progress import ProgressManager
from ..services.batch_manager import BatchJobManager
from ..services.landsat_download import LandsatDownloadService
from ..services.templates import ProcessingTemplates
from ..services.graph_executor import GraphExecutor

logger = logging.getLogger(__name__)
RASTER_PREVIEW_EXTENSIONS = (".tif", ".tiff", ".img", ".png")
# 单次写入 1MB，避免大文件上传时把整个文件一次性读入内存。
UPLOAD_CHUNK_SIZE = 1024 * 1024

COMPOSITE_DESCRIPTIONS = {
    # RGB合成
    "true_color": ("真彩色", "真实自然色彩 (Red-Green-Blue)", "自然地物识别，最接近人眼视觉"),
    "false_color": ("假彩色", "植被增强 (NIR-Red-Green)", "植被健康监测，植物呈红色"),
    "agriculture": ("农业监测", "农作物分析 (SWIR1-NIR-Blue)", "农作物类型识别，土壤湿度评估"),
    "urban": ("城市研究", "城市区域增强 (SWIR2-SWIR1-Red)", "建筑物识别，城市规划"),
    "natural_color": ("自然彩色", "自然色调 (Red-Green-Blue)", "与真彩色一致，更利于直观判读"),
    "swir": ("短波红外", "短波红外合成 (SWIR2-NIR-Green)", "水体识别，云雾穿透"),

    # 植被指数
    "ndvi": ("NDVI", "归一化植被指数 (NIR-Red)/(NIR+Red)", "植被覆盖度与健康状况分析"),
    "evi": ("EVI", "Enhanced Vegetation Index (NIR-Red-Blue)", "高生物量区域植被活力评估"),
    "savi": ("SAVI", "土壤调节植被指数，适合植被稀疏区域", "减少土壤背景影响的植被监测"),
    "msavi": ("MSAVI", "修正SAVI，自适应土壤调节", "植被覆盖度变化大的区域监测"),
    "arvi": ("ARVI", "抗大气植被指数，减少大气干扰", "有雾霾时的植被监测"),
    "rvi": ("RVI", "比值植被指数 NIR/Red", "简单快速的植被监测"),

    # 水体指数
    "ndwi": ("NDWI", "归一化水体指数 (Green-NIR)/(Green+NIR)", "水体与地表含水量识别"),
    "mndwi": ("MNDWI", "改进归一化水体指数 (Green-SWIR1)", "城市区域水体提取，抑制建筑物噪声"),
    "awei": ("AWEI", "自动水体提取指数，适合有阴影场景", "自动化水体提取与分类"),
    "wri": ("WRI", "水体比率指数 (Green+Red)/(NIR+SWIR1)", "浅水和浑浊水体识别"),

    # 建筑/城市指数
    "ndbi": ("NDBI", "归一化建筑指数 (SWIR1-NIR)/(SWIR1+NIR)", "建筑区与城市扩张识别"),
    "ibi": ("IBI", "综合建筑指数，结合NDBI/SAVI/MNDWI", "精确的城市建筑区提取"),
    "ndbai": ("NDBaI", "归一化裸地与建筑指数", "裸地和建筑区识别"),
    "ui": ("UI", "城市指数 (SWIR2-NIR)/(SWIR2+NIR)", "简单高效的城市区域识别"),

    # 其他指数
    "nbr": ("NBR", "归一化燃烧指数 (NIR-SWIR2)/(NIR+SWIR2)", "火灾监测与燃烧程度评估"),
    "bsi": ("BSI", "裸土指数，用于裸土识别", "土壤侵蚀监测，裸地提取"),
    "ndsi": ("NDSI", "归一化积雪指数 (Green-SWIR1)/(Green+SWIR1)", "雪盖监测，冰川变化分析"),
}


def _detect_upload_band_name(filename: str) -> Optional[str]:
    """Try to parse Landsat band name from an uploaded filename."""
    upper_name = filename.upper()
    for band_idx in range(1, 12):
        if (
            f"_B{band_idx}." in upper_name
            or f"_B{band_idx}_" in upper_name
            or f"B{band_idx}." in upper_name
        ):
            return f"B{band_idx}"
    return None


async def _save_upload(upload: UploadFile, target_path: str) -> None:
    """Persist an UploadFile to disk in chunks."""
    with open(target_path, "wb") as file_obj:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            file_obj.write(chunk)


async def _save_band_uploads(bands: List[UploadFile], target_dir: str) -> Dict[str, str]:
    """Save uploaded band files and return a {band_name: file_path} mapping."""
    band_paths: Dict[str, str] = {}
    for band_file in bands:
        filename = band_file.filename or ""
        band_name = _detect_upload_band_name(filename)
        if not band_name:
            logger.warning("无法识别波段编号，已跳过: %s", filename)
            continue

        extension = Path(filename).suffix or ".tif"
        target_path = os.path.join(target_dir, f"{band_name}{extension}")
        # 这里保留原始扩展名，避免影响后续 GDAL 按格式读取。
        await _save_upload(band_file, target_path)
        band_paths[band_name] = target_path

    return band_paths


def _build_summary(
    result: Dict,
    output_dir: str,
    apply_cloud_mask: bool,
    qa_path: Optional[str],
    is_clipped: bool,
) -> Dict:
    """Build response summary block."""
    return {
        "total_bands_processed": len(result.get("processed_bands", {})),
        "composites_created": len(result.get("composites", {})),
        "cloud_mask_applied": apply_cloud_mask and qa_path is not None,
        "clipped": is_clipped,
        "output_directory": os.path.normpath(output_dir),
    }


def _get_composite_description(comp_type: str) -> tuple[str, str, str]:
    return COMPOSITE_DESCRIPTIONS.get(
        comp_type,
        (comp_type, "自定义组合", "请结合业务场景使用"),
    )


async def _save_optional_upload(upload: Optional[UploadFile], target_path: str) -> Optional[str]:
    """Save an optional upload and return the saved path."""
    if not upload:
        return None

    await _save_upload(upload, target_path)
    return target_path


def _cleanup_failed_preprocess_setup(
    file_manager: FileManager,
    progress_manager: ProgressManager,
    temp_dir: str,
    job_id: str,
) -> None:
    file_manager.cleanup_temp_dir(temp_dir)
    progress_manager.remove_progress(job_id)


async def _prepare_async_preprocess_inputs(
    *,
    job_id: str,
    bands: List[UploadFile],
    mtl_file: Optional[UploadFile],
    qa_band: Optional[UploadFile],
    output_dir: str,
    clip_extent: Optional[str],
    clip_shapefile: Optional[List[UploadFile]],
    create_composites: Optional[str],
    temp_dir: str,
    band_dir: str,
    shape_dir: str,
    file_manager: FileManager,
    progress_manager: ProgressManager,
) -> Dict:
    band_paths = await _save_band_uploads(bands, band_dir)
    if not band_paths:
        raise HTTPException(
            status_code=400,
            detail="未识别到有效波段文件，请确保文件名中含有 B1-B11 标识",
        )

    progress_manager.update_progress(
        job_id,
        status="processing",
        step_id="upload",
        step_status="completed",
        progress=10,
        detail=f"已保存 {len(band_paths)} 个波段文件",
    )

    mtl_path = await _save_optional_upload(mtl_file, os.path.join(temp_dir, "MTL.txt"))

    qa_path = None
    if qa_band:
        qa_extension = Path(qa_band.filename or "").suffix or ".tif"
        qa_path = await _save_optional_upload(qa_band, os.path.join(temp_dir, f"BQA{qa_extension}"))

    shapefile_path = file_manager.save_shapefiles(clip_shapefile, shape_dir) if clip_shapefile else None
    extent_list = file_manager.parse_extent(clip_extent)
    composite_list = file_manager.parse_composites(create_composites)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    return {
        "band_paths": band_paths,
        "mtl_path": mtl_path,
        "qa_path": qa_path,
        "shapefile_path": shapefile_path,
        "extent_list": extent_list,
        "composite_list": composite_list,
    }


def _update_async_progress(progress_manager: ProgressManager, job_id: str, payload: Dict) -> None:
    progress_manager.update_progress(
        job_id,
        step_id=payload.get("step"),
        step_status=payload.get("status"),
        progress=payload.get("progress"),
        detail=payload.get("detail"),
    )


def _complete_async_preprocess(
    progress_manager: ProgressManager,
    job_id: str,
    result: Dict,
    output_dir: str,
    apply_cloud_mask: bool,
    qa_path: Optional[str],
    extent_list: Optional[List[float]],
    shapefile_path: Optional[str],
) -> None:
    result["summary"] = _build_summary(
        result=result,
        output_dir=output_dir,
        apply_cloud_mask=apply_cloud_mask,
        qa_path=qa_path,
        is_clipped=extent_list is not None or shapefile_path is not None,
    )
    progress_manager.update_progress(
        job_id,
        status="success",
        step_id="finalize",
        step_status="completed",
        progress=100,
        detail="处理完成",
        result=result,
    )


def _run_async_preprocess_job(
    *,
    progress_manager: ProgressManager,
    file_manager: FileManager,
    job_id: str,
    band_paths: Dict[str, str],
    output_dir: str,
    mtl_path: Optional[str],
    qa_path: Optional[str],
    extent_list: Optional[List[float]],
    shapefile_path: Optional[str],
    composite_list: Optional[List[str]],
    apply_cloud_mask: bool,
    atm_correction_method: str,
    custom_formula: Optional[str],
    custom_name: Optional[str],
    cleanup_temp_dir: Optional[str],
) -> None:
    processor = Landsat8Processor()

    try:
        result = processor.one_click_preprocess(
            band_paths=band_paths,
            output_dir=output_dir,
            mtl_path=mtl_path,
            clip_extent=extent_list,
            clip_shapefile=shapefile_path,
            create_composites=composite_list,
            apply_cloud_mask=apply_cloud_mask and qa_path is not None,
            qa_band_path=qa_path,
            atm_correction_method=atm_correction_method,
            custom_index_formula=custom_formula,
            custom_index_name=custom_name,
            progress_callback=lambda payload: _update_async_progress(progress_manager, job_id, payload),
        )

        if result.get("status") == "error":
            raise RuntimeError(result.get("error", "未知错误"))

        _complete_async_preprocess(
            progress_manager,
            job_id,
            result,
            output_dir,
            apply_cloud_mask,
            qa_path,
            extent_list,
            shapefile_path,
        )
    except Exception as exc:
        logger.error("异步预处理失败: %s", exc, exc_info=True)
        progress_manager.update_progress(
            job_id,
            status="error",
            step_id="finalize",
            step_status="exception",
            progress=100,
            detail=f"处理失败: {exc}",
            error=str(exc),
        )
    finally:
        if cleanup_temp_dir:
            file_manager.cleanup_temp_dir(cleanup_temp_dir)


def _launch_async_preprocess(**kwargs) -> None:
    threading.Thread(target=_run_async_preprocess_job, kwargs=kwargs, daemon=True).start()


def _list_root_directories() -> Dict:
    roots = []
    if os.name == "nt":
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                roots.append({"name": drive, "path": drive})
    else:
        roots.append({"name": "/", "path": "/"})

    cwd = str(Path.cwd())
    if cwd not in {item["path"] for item in roots}:
        roots.insert(0, {"name": "当前工作目录", "path": cwd})

    return {
        "current": "",
        "parent": "",
        "directories": roots,
    }


def _list_directory_entries(current: Path) -> List[Dict[str, str]]:
    directories = []
    with os.scandir(current) as it:
        for entry in it:
            if entry.is_dir(follow_symlinks=False):
                directories.append({"name": entry.name, "path": entry.path})

    directories.sort(key=lambda item: item["name"].lower())
    return directories


def setup_routes(
    app: FastAPI,
    progress_manager: ProgressManager,
    file_manager: FileManager,
    batch_manager: BatchJobManager = None,
    landsat_download_service: Optional[LandsatDownloadService] = None,
) -> None:
    """Register all HTTP routes."""

    if batch_manager is None:
        batch_manager = BatchJobManager(max_workers=settings.MAX_WORKERS)
    if landsat_download_service is None:
        landsat_download_service = LandsatDownloadService()

    @app.get("/")
    def root_info() -> Dict:
        return {
            "service": "Remote Sensing Tools API",
            "version": "3.0.0",
            "docs": "/docs",
            "health": "/health",
            "frontend_project": "frontend-vue (Vue3 + Vite)",
            "usage": "可通过 frontend-vue 前端项目调用 API，或通过 /docs 调用 API",
            "core_endpoints": [
                "/preprocess_landsat8_async",
                "/preprocess_landsat8_status/{job_id}",
                "/composite_types",
                "/band_info",
                "/preview_raster",
                "/filesystem/list_dirs",
            ],
            "batch_endpoints": [
                "/batch/templates",
                "/batch/submit",
                "/batch/list",
                "/batch/{batch_id}/status",
                "/batch/job/{job_id}/status",
                "/batch/job/{job_id}/pause",
                "/batch/job/{job_id}/resume",
                "/batch/job/{job_id}/cancel",
            ],
            "landsat_download_endpoints": [
                "/landsat/collections",
                "/landsat/search",
                "/landsat/auth/status",
                "/landsat/auth/earthdata",
                "/landsat/proxy_download",
                "/landsat/download",
                "/landsat/download_tasks",
            ],
        }

    @app.get("/health")
    def health_check() -> Dict:
        return {
            "status": "healthy",
            "service": "remote-sensing-tools",
            "version": "3.0.0",
        }

    @app.get("/landsat/collections")
    def landsat_collections() -> Dict:
        return landsat_download_service.list_collections()

    @app.get("/landsat/auth/status")
    def landsat_auth_status() -> Dict:
        return landsat_download_service.get_auth_status()

    @app.post("/landsat/auth/earthdata")
    async def landsat_set_earthdata(request: LandsatAuthRequest) -> Dict:
        try:
            return await landsat_download_service.configure_earthdata(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        except Exception as exc:
            logger.error("EarthData 认证失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"认证失败: {exc}")

    @app.post("/landsat/search")
    async def landsat_search(request: LandsatSearchRequest) -> Dict:
        try:
            return await landsat_download_service.search(request)
        except Exception as exc:
            logger.error("Landsat 搜索失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"搜索失败: {exc}")

    @app.get("/landsat/sign")
    async def landsat_sign(url: str) -> Dict:
        try:
            return await landsat_download_service.sign_url(url)
        except Exception as exc:
            logger.error("Landsat URL 签名失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"签名失败: {exc}")

    @app.get("/landsat/proxy_download")
    async def landsat_proxy_download(url: str, filename: str = "landsat_asset.bin"):
        try:
            return await landsat_download_service.create_proxy_download_response(url, filename)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        except Exception as exc:
            logger.error("Landsat 代理下载失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"代理下载失败: {exc}")

    @app.post("/landsat/download")
    async def landsat_create_download(request: LandsatDownloadTaskCreateRequest) -> Dict:
        try:
            return await landsat_download_service.create_download_tasks(request)
        except Exception as exc:
            logger.error("创建 Landsat 下载任务失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"创建下载任务失败: {exc}")

    @app.get("/landsat/download_tasks")
    def landsat_list_download_tasks() -> Dict:
        return landsat_download_service.list_download_tasks()

    @app.get("/landsat/download_tasks/{task_id}")
    def landsat_get_download_task(task_id: str) -> Dict:
        task = landsat_download_service.get_download_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"下载任务不存在: {task_id}")
        return task

    @app.delete("/landsat/download_tasks/completed")
    def landsat_clear_completed_download_tasks() -> Dict:
        return landsat_download_service.clear_completed_tasks()

    @app.delete("/landsat/download_tasks/{task_id}")
    def landsat_cancel_download_task(task_id: str) -> Dict:
        try:
            return landsat_download_service.cancel_download_task(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"下载任务不存在: {task_id}")

    @app.get("/landsat/download_tasks/{task_id}/file")
    async def landsat_download_task_file(task_id: str):
        try:
            return await landsat_download_service.build_task_file_response(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"下载任务不存在: {task_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"文件不存在: {exc}")
        except Exception as exc:
            logger.error("读取 Landsat 下载结果失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"读取下载结果失败: {exc}")

    @app.get("/composite_types")
    def get_composite_types() -> Dict:
        return {
            "composite_types": [
                {
                    "type": comp_type,
                    "name": info[0],
                    "bands": bands,
                    "description": info[1],
                    "use_case": info[2],
                }
                for comp_type, bands in COMPOSITE_MAP.items()
                for info in [_get_composite_description(comp_type)]
            ]
        }

    @app.get("/band_info")
    def get_band_info() -> Dict:
        return BAND_INFO

    @app.get("/filesystem/list_dirs")
    def list_directories(path: Optional[str] = None) -> Dict:
        """List directories for UI path picker (local deployment)."""
        if path is None or not path.strip():
            return _list_root_directories()

        target = Path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail=f"路径不存在: {path}")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail=f"不是目录: {path}")

        try:
            current = target.resolve()
        except Exception:
            current = target

        try:
            directories = _list_directory_entries(current)
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"无权限访问目录: {current}")
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"读取目录失败: {exc}")

        parent = str(current.parent) if current.parent != current else ""

        return {
            "current": str(current),
            "parent": parent,
            "directories": directories,
        }

    @app.get("/filesystem/scan_scenes")
    def scan_scenes(path: str) -> Dict:
        """扫描目录下的遥感影像场景（每个子目录 = 一个场景），检测 shp/ 文件夹"""
        target = Path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail=f"路径不存在: {path}")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail=f"不是目录: {path}")
        scenes = []
        try:
            with os.scandir(target) as it:
                for entry in it:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    scene_path = Path(entry.path)
                    shp_dir = scene_path / "shp"
                    has_shp = False
                    shp_file = None
                    if shp_dir.exists() and shp_dir.is_dir():
                        shp_files = list(shp_dir.glob("*.shp"))
                        if shp_files:
                            has_shp = True
                            shp_file = str(shp_files[0])
                    # 自动检测 MTL 元数据文件
                    mtl_files = list(scene_path.glob("*MTL*.txt"))
                    mtl_file = str(mtl_files[0]) if mtl_files else None
                    scenes.append({
                        "name": entry.name,
                        "path": str(scene_path),
                        "has_shp": has_shp,
                        "shp_file": shp_file,
                        "mtl_file": mtl_file,
                    })
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"无权限访问目录: {target}")
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"读取目录失败: {exc}")
        scenes.sort(key=lambda s: s["name"].lower())
        return {"scenes": scenes, "total": len(scenes), "root": str(target)}

    @app.post("/preview_raster")
    async def preview_raster(
        file_path: str = Form(..., description="待预览的栅格/合成影像路径"),
        max_size: int = Form(512, description="最大预览边长像素"),
    ) -> Dict:
        if not file_path.lower().endswith(RASTER_PREVIEW_EXTENSIONS):
            raise HTTPException(status_code=400, detail="仅支持 .tif/.tiff/.img/.png 文件")

        try:
            preview = Landsat8Processor().build_preview_base64(file_path, max_size=max_size)
            return {"status": "success", "preview": preview}
        except Exception as exc:
            logger.error("预览栅格失败: %s", exc)
            raise HTTPException(status_code=500, detail=f"预览失败: {exc}")

    @app.get("/preprocess_landsat8_status/{job_id}")
    def preprocess_landsat8_status(job_id: str):
        task = progress_manager.get_progress(job_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在或已超时")
        return task

    @app.post("/preprocess_landsat8_async")
    async def preprocess_landsat8_async(
        bands: List[UploadFile] = File(..., description="Landsat 8 波段文件列表"),
        mtl_file: Optional[UploadFile] = File(None, description="MTL元数据文件"),
        qa_band: Optional[UploadFile] = File(None, description="QA波段文件"),
        output_dir: str = Form(..., description="输出目录路径"),
        clip_extent: Optional[str] = Form(None, description="裁剪范围：xmin,ymin,xmax,ymax"),
        clip_shapefile: Optional[List[UploadFile]] = File(None, description="裁剪矢量文件"),
        create_composites: Optional[str] = Form(None, description="合成类型，如 true_color,false_color"),
        custom_formula: Optional[str] = Form(None, description="自定义指数公式"),
        custom_name: Optional[str] = Form(None, description="自定义指数名称"),
        apply_cloud_mask: bool = Form(False, description="是否应用云掩膜"),
        atm_correction_method: str = Form("DOS", description="大气校正方法: DOS 或 6S"),
    ) -> Dict:
        if not bands:
            raise HTTPException(status_code=400, detail="必须上传至少一个波段文件")

        job_id = str(uuid.uuid4())
        progress_manager.init_progress(job_id)

        temp_dir = file_manager.create_temp_dir(prefix=f"landsat8_{job_id}_")
        band_dir = os.path.join(temp_dir, "bands")
        shape_dir = os.path.join(temp_dir, "shapefile")
        os.makedirs(band_dir, exist_ok=True)
        os.makedirs(shape_dir, exist_ok=True)

        try:
            preprocess_inputs = await _prepare_async_preprocess_inputs(
                job_id=job_id,
                bands=bands,
                mtl_file=mtl_file,
                qa_band=qa_band,
                output_dir=output_dir,
                clip_extent=clip_extent,
                clip_shapefile=clip_shapefile,
                create_composites=create_composites,
                temp_dir=temp_dir,
                band_dir=band_dir,
                shape_dir=shape_dir,
                file_manager=file_manager,
                progress_manager=progress_manager,
            )
        except HTTPException:
            _cleanup_failed_preprocess_setup(file_manager, progress_manager, temp_dir, job_id)
            raise
        except ValueError as exc:
            _cleanup_failed_preprocess_setup(file_manager, progress_manager, temp_dir, job_id)
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            _cleanup_failed_preprocess_setup(file_manager, progress_manager, temp_dir, job_id)
            logger.error("预处理任务初始化失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"任务初始化失败: {exc}")

        _launch_async_preprocess(
            progress_manager=progress_manager,
            file_manager=file_manager,
            job_id=job_id,
            band_paths=preprocess_inputs["band_paths"],
            output_dir=output_dir,
            mtl_path=preprocess_inputs["mtl_path"],
            qa_path=preprocess_inputs["qa_path"],
            extent_list=preprocess_inputs["extent_list"],
            shapefile_path=preprocess_inputs["shapefile_path"],
            composite_list=preprocess_inputs["composite_list"],
            apply_cloud_mask=apply_cloud_mask,
            atm_correction_method=atm_correction_method,
            custom_formula=custom_formula,
            custom_name=custom_name,
            cleanup_temp_dir=temp_dir,
        )
        return {"job_id": job_id, "status": "processing"}

    # ============== 批量处理 API ==============

    @app.get("/batch/templates")
    def list_processing_templates() -> Dict:
        """列出所有预设处理流程模板"""
        return {"templates": ProcessingTemplates.list_templates()}

    @app.post("/batch/submit_graph")
    def submit_graph_jobs(request: GraphSubmitRequest) -> Dict:
        """基于节点图提交批量任务（图结构驱动执行顺序）

        前端将 Vue Flow 的 nodes + edges 序列化后发送，
        后端拓扑排序后确定各场景的执行步骤并生成 BatchJobConfig。
        """
        try:
            executor = GraphExecutor()
            nodes = [n.model_dump() for n in request.nodes]
            edges = [e.model_dump() for e in request.edges]
            configs, errors = executor.build_job_configs(nodes, edges)

            if errors:
                raise HTTPException(status_code=400, detail="; ".join(errors))
            if not configs:
                raise HTTPException(status_code=400, detail="未生成任何任务配置，请检查画布")

            processed_configs = [ProcessingTemplates.apply_template(c) for c in configs]
            batch_id = batch_manager.submit_batch(
                batch_name=request.batch_name,
                jobs_config=processed_configs,
                priority=request.priority,
                max_retries=request.max_retries if request.auto_retry else 0,
            )
            return {
                "batch_id": batch_id,
                "batch_name": request.batch_name,
                "total_jobs": len(configs),
                "status": "submitted",
                "message": f"成功提交 {len(configs)} 个任务到批量处理队列",
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("图任务提交失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"图任务提交失败: {exc}")

    @app.post("/batch/submit")
    def submit_batch_jobs(request: BatchSubmitRequest) -> Dict:
        """提交批量处理任务

        Args:
            request: 批量提交请求

        Returns:
            batch_id 和提交状态
        """
        try:
            processed_configs = [
                ProcessingTemplates.apply_template(job_config)
                for job_config in request.jobs
            ]
            batch_id = batch_manager.submit_batch(
                batch_name=request.batch_name,
                jobs_config=processed_configs,
                priority=request.priority,
                max_retries=request.max_retries if request.auto_retry else 0,
            )

            return {
                "batch_id": batch_id,
                "batch_name": request.batch_name,
                "total_jobs": len(request.jobs),
                "status": "submitted",
                "message": f"成功提交 {len(request.jobs)} 个任务到批量处理队列",
            }

        except Exception as exc:
            logger.error("批量任务提交失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"批量任务提交失败: {exc}")

    @app.get("/batch/list")
    def list_batches() -> Dict:
        """列出所有批次"""
        batches = batch_manager.list_batches()
        return {"batches": batches, "total": len(batches)}

    @app.get("/batch/{batch_id}/status")
    def get_batch_status(batch_id: str) -> Dict:
        """获取批次状态

        Args:
            batch_id: 批次ID

        Returns:
            批次详细状态
        """
        status = batch_manager.get_batch_status(batch_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"批次不存在: {batch_id}")

        return status.model_dump()

    @app.get("/batch/job/{job_id}/status")
    def get_job_status(job_id: str) -> Dict:
        """获取单个任务状态

        Args:
            job_id: 任务ID

        Returns:
            任务详细状态
        """
        job = batch_manager.get_job_status(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"任务不存在: {job_id}")

        return job.model_dump()

    @app.post("/batch/job/{job_id}/pause")
    def pause_job(job_id: str) -> Dict:
        """暂停任务

        Args:
            job_id: 任务ID

        Returns:
            操作结果
        """
        success = batch_manager.pause_job(job_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="无法暂停任务（任务可能不存在或已在运行中）",
            )

        return {"job_id": job_id, "status": "paused", "message": "任务已暂停"}

    @app.post("/batch/job/{job_id}/resume")
    def resume_job(job_id: str) -> Dict:
        """恢复任务

        Args:
            job_id: 任务ID

        Returns:
            操作结果
        """
        success = batch_manager.resume_job(job_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="无法恢复任务（任务可能不存在或未暂停）",
            )

        return {"job_id": job_id, "status": "resumed", "message": "任务已恢复"}

    @app.post("/batch/job/{job_id}/cancel")
    def cancel_job(job_id: str) -> Dict:
        """取消任务

        Args:
            job_id: 任务ID

        Returns:
            操作结果
        """
        success = batch_manager.cancel_job(job_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="无法取消任务（任务可能不存在或已在运行中）",
            )

        return {"job_id": job_id, "status": "cancelled", "message": "任务已取消"}

    @app.get("/tasks/queue")
    def get_tasks_queue() -> Dict:
        """获取所有任务队列状态（扁平化）"""
        jobs = []
        with batch_manager.lock:
            all_jobs = list(batch_manager.jobs.values())
        for job in all_jobs:
            jobs.append(TaskQueueItem(
                job_id=job.job_id,
                batch_id=job.batch_id,
                scene_name=job.config.scene_name,
                status=job.status,
                progress=job.progress,
                priority=job.priority,
                created_at=job.created_at,
                started_at=job.started_at,
            ).model_dump())
        jobs.sort(key=lambda j: j["created_at"], reverse=True)
        running = sum(1 for j in jobs if j["status"] == "running")
        queued = sum(1 for j in jobs if j["status"] in ("queued", "pending"))
        completed = sum(1 for j in jobs if j["status"] == "success")
        failed = sum(1 for j in jobs if j["status"] == "failed")
        return {
            "jobs": jobs,
            "total": len(jobs),
            "running": running,
            "queued": queued,
            "completed": completed,
            "failed": failed,
        }
