"""API route definitions."""

import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from osgeo import gdal, ogr, osr

from ..core.config import settings
from ..core.constants import BAND_INFO, COMPOSITE_MAP
from ..core.processor import Landsat8Processor
from ..core.models import (
    BatchSubmitRequest,
    GraphSubmitRequest,
    ImageryDownloadItem,
    ImageryDownloadTaskCreateRequest,
    ImagerySearchRequest,
    LandsatAuthRequest,
    LandsatDownloadDirRequest,
    LandsatDownloadTaskCreateRequest,
    LandsatProxyRequest,
    LandsatSearchRequest,
    TaskQueueItem,
)
from ..services.file_manager import FileManager
from ..services.progress import ProgressManager
from ..services.batch_manager import BatchJobManager
from ..services.landsat_download import LandsatDownloadService
from ..services.task_results import TaskResultService, write_task_manifest
from ..services.templates import ProcessingTemplates
from ..services.graph_executor import GraphExecutor
from ..utils.file_utils import collect_band_paths, find_scene_support_files, infer_available_product_levels
from ..utils.path_policy import PathAccessController, PathAccessError

logger = logging.getLogger(__name__)
RASTER_PREVIEW_EXTENSIONS = (".tif", ".tiff", ".img", ".png")
VECTOR_PREVIEW_EXTENSIONS = (".shp", ".geojson", ".json")
# 单次写入 1MB，避免大文件上传时把整个文件一次性读入内存。
UPLOAD_CHUNK_SIZE = 1024 * 1024
PATH_ACCESS = PathAccessController(settings.allowed_path_roots)

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


def _infer_product_level(name: str, filenames: Optional[List[str]] = None) -> str:
    normalized = (name or "").upper()
    if "_L2" in normalized or "L2SP" in normalized:
        return "L2"

    for filename in filenames or []:
        upper_name = filename.upper()
        if any(token in upper_name for token in ("_SR_B", "_ST_B", "_L2", "L2SP", "SURFACE_REFLECTANCE")):
            return "L2"
    return "L1"


def _find_first_matching_file(scene_path: Path, patterns: List[str]) -> Optional[str]:
    for pattern in patterns:
        matches = list(scene_path.glob(pattern))
        if matches:
            return str(matches[0])
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
        "product_level": result.get("product_level"),
        "processing_mode": result.get("processing_mode"),
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
    qa_radsat_band: Optional[UploadFile],
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

    qa_radsat_path = None
    if qa_radsat_band:
        qa_radsat_extension = Path(qa_radsat_band.filename or "").suffix or ".tif"
        qa_radsat_path = await _save_optional_upload(
            qa_radsat_band,
            os.path.join(temp_dir, f"QA_RADSAT{qa_radsat_extension}"),
        )

    shapefile_path = file_manager.save_shapefiles(clip_shapefile, shape_dir) if clip_shapefile else None
    extent_list = file_manager.parse_extent(clip_extent)
    composite_list = file_manager.parse_composites(create_composites)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    return {
        "band_paths": band_paths,
        "mtl_path": mtl_path,
        "qa_path": qa_path,
        "qa_radsat_path": qa_radsat_path,
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
    task = progress_manager.get_progress(job_id)
    if task:
        title = (
            str((result.get("metadata") or {}).get("scene_id") or "").strip()
            or Path(output_dir).name
        )
        try:
            write_task_manifest(
                task_type="single",
                title=title,
                output_dir=output_dir,
                result=result,
                job_id=job_id,
                batch_id=None,
                created_at=task.created_at,
                completed_at=task.updated_at,
                summary=result.get("summary") or {},
            )
        except Exception as exc:
            logger.warning("写入单任务结果清单失败，不影响任务成功状态: %s", exc, exc_info=True)


def _run_async_preprocess_job(
    *,
    progress_manager: ProgressManager,
    file_manager: FileManager,
    job_id: str,
    band_paths: Dict[str, str],
    output_dir: str,
    mtl_path: Optional[str],
    qa_path: Optional[str],
    qa_radsat_path: Optional[str],
    extent_list: Optional[List[float]],
    shapefile_path: Optional[str],
    composite_list: Optional[List[str]],
    apply_cloud_mask: bool,
    atm_correction_method: str,
    product_level: str,
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
            qa_radsat_band_path=qa_radsat_path,
            atm_correction_method=atm_correction_method,
            product_level=product_level,
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
    return {
        "current": "",
        "parent": "",
        "directories": PATH_ACCESS.allowed_roots_payload(),
        "files": [],
    }


def _normalize_suffix_filters(raw_value: Optional[str]) -> List[str]:
    if not raw_value:
        return []
    suffixes = []
    for item in str(raw_value).split(","):
        value = item.strip().lower()
        if not value:
            continue
        if not value.startswith("."):
            value = f".{value}"
        suffixes.append(value)
    return sorted(set(suffixes))


def _list_directory_entries(
    current: Path,
    *,
    include_files: bool = False,
    allowed_suffixes: Optional[List[str]] = None,
) -> Dict[str, List[Dict[str, str]]]:
    directories = []
    files = []
    suffix_filters = {suffix.lower() for suffix in (allowed_suffixes or [])}
    with os.scandir(current) as it:
        for entry in it:
            if entry.is_dir(follow_symlinks=False):
                resolved = Path(entry.path).resolve(strict=False)
                if not PATH_ACCESS.is_allowed(resolved):
                    continue
                directories.append({"name": entry.name, "path": str(resolved)})
                continue

            if not include_files or not entry.is_file(follow_symlinks=False):
                continue

            resolved = Path(entry.path).resolve(strict=False)
            if not PATH_ACCESS.is_allowed(resolved):
                continue
            if suffix_filters and resolved.suffix.lower() not in suffix_filters:
                continue
            files.append({"name": entry.name, "path": str(resolved)})

    directories.sort(key=lambda item: item["name"].lower())
    files.sort(key=lambda item: item["name"].lower())
    return {"directories": directories, "files": files}


def _raise_path_access_http_error(exc: PathAccessError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


def _optional_allowed_file(path_value: Optional[str], access_label: str) -> Optional[str]:
    if not path_value:
        return None

    try:
        return str(PATH_ACCESS.require_file(path_value, access_label=access_label))
    except PathAccessError as exc:
        logger.warning("忽略非法路径 %s: %s", path_value, exc)
        return None


def _detect_vector_upload_kind(files: List[UploadFile]) -> str:
    suffixes = {Path(upload.filename or "").suffix.lower() for upload in files if upload.filename}
    if any(suffix in {".geojson", ".json"} for suffix in suffixes):
        return "geojson"
    if ".shp" in suffixes:
        return "shapefile"
    raise ValueError("请上传 .geojson/.json，或包含 .shp 的 Shapefile 配套文件")


def _transform_geometry_to_wgs84(geometry: ogr.Geometry, source_srs: Optional[osr.SpatialReference]) -> ogr.Geometry:
    cloned = geometry.Clone()
    if source_srs is None:
        return cloned

    target_srs = osr.SpatialReference()
    target_srs.ImportFromEPSG(4326)
    if source_srs.IsSame(target_srs):
        return cloned

    source = source_srs.Clone()
    axis_order = getattr(osr, "OAMS_TRADITIONAL_GIS_ORDER", None)
    if axis_order is not None and hasattr(source, "SetAxisMappingStrategy") and hasattr(target_srs, "SetAxisMappingStrategy"):
        if hasattr(source, "GetAxisMappingStrategy") and source.GetAxisMappingStrategy() != axis_order:
            source.SetAxisMappingStrategy(axis_order)
        target_srs.SetAxisMappingStrategy(axis_order)

    try:
        transform = osr.CoordinateTransformation(source, target_srs)
        cloned.Transform(transform)
    except Exception as exc:
        raise ValueError(f"矢量坐标转换到 EPSG:4326 失败: {exc}") from exc
    return cloned


def _vector_dataset_payload(vector_path: str, *, label: str) -> Dict:
    previous_restore_shx = gdal.GetThreadLocalConfigOption("SHAPE_RESTORE_SHX")
    gdal.SetThreadLocalConfigOption("SHAPE_RESTORE_SHX", "YES")
    try:
        datasource = ogr.Open(vector_path)
    finally:
        gdal.SetThreadLocalConfigOption("SHAPE_RESTORE_SHX", previous_restore_shx)

    if datasource is None:
        raise ValueError(
            "无法解析矢量文件，请检查 GeoJSON 或 Shapefile 是否完整。"
            "Shapefile 缺少 .shx 时系统会自动尝试恢复，若仍失败请重新导出并补齐配套文件。"
        )

    layer = datasource.GetLayer(0)
    if layer is None:
        raise ValueError("矢量文件中未找到可用图层")

    source_srs = layer.GetSpatialRef()
    features = []
    min_x = min_y = max_x = max_y = None
    layer.ResetReading()

    for feature in layer:
        geometry = feature.GetGeometryRef()
        if geometry is None or geometry.IsEmpty():
            continue

        geometry_wgs84 = _transform_geometry_to_wgs84(geometry, source_srs)
        envelope = geometry_wgs84.GetEnvelope()
        x_min, x_max, y_min, y_max = envelope[0], envelope[1], envelope[2], envelope[3]
        min_x = x_min if min_x is None else min(min_x, x_min)
        max_x = x_max if max_x is None else max(max_x, x_max)
        min_y = y_min if min_y is None else min(min_y, y_min)
        max_y = y_max if max_y is None else max(max_y, y_max)

        features.append(
            {
                "type": "Feature",
                "properties": dict(feature.items()),
                "geometry": json.loads(geometry_wgs84.ExportToJson()),
            }
        )

    if not features or None in {min_x, min_y, max_x, max_y}:
        raise ValueError("矢量文件中没有可用几何，无法生成选区")

    return {
        "label": label,
        "feature_count": len(features),
        "bbox": [round(min_x, 6), round(min_y, 6), round(max_x, 6), round(max_y, 6)],
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
        },
    }


def _resolve_raster_preview_target(path_value: str, product_level: Optional[str] = None) -> Path:
    target_path = Path(path_value)
    if target_path.suffix.lower() in RASTER_PREVIEW_EXTENSIONS:
        return PATH_ACCESS.require_file(
            path_value,
            access_label="读取栅格覆盖范围",
            allowed_suffixes=RASTER_PREVIEW_EXTENSIONS,
        )

    target_dir = PATH_ACCESS.require_directory(path_value, access_label="读取场景目录")
    band_paths = collect_band_paths(target_dir, product_level=product_level)
    preferred_band = next((band_paths.get(band) for band in ("B4", "B3", "B2", "B5") if band_paths.get(band)), None)
    raster_path = preferred_band or next(iter(sorted(band_paths.values())))
    return PATH_ACCESS.require_file(
        raster_path,
        access_label="读取场景代表波段",
        allowed_suffixes=RASTER_PREVIEW_EXTENSIONS,
    )


def _raster_dataset_payload(raster_path: str, *, label: str) -> Dict:
    dataset = gdal.Open(raster_path)
    if dataset is None:
        raise ValueError(f"无法打开栅格文件: {raster_path}")

    width = dataset.RasterXSize
    height = dataset.RasterYSize
    geo_transform = dataset.GetGeoTransform(can_return_null=True)
    if geo_transform is None:
        dataset = None
        raise ValueError("栅格缺少地理参考信息，无法生成覆盖范围")

    source_srs = None
    projection = dataset.GetProjection()
    if projection:
        source_srs = osr.SpatialReference()
        source_srs.ImportFromWkt(projection)

    def _pixel_to_geo(pixel_x: float, pixel_y: float) -> List[float]:
        x = geo_transform[0] + pixel_x * geo_transform[1] + pixel_y * geo_transform[2]
        y = geo_transform[3] + pixel_x * geo_transform[4] + pixel_y * geo_transform[5]
        return [x, y]

    corners = [
        _pixel_to_geo(0, 0),
        _pixel_to_geo(width, 0),
        _pixel_to_geo(width, height),
        _pixel_to_geo(0, height),
        _pixel_to_geo(0, 0),
    ]
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for x_coord, y_coord in corners:
        ring.AddPoint(float(x_coord), float(y_coord))
    polygon = ogr.Geometry(ogr.wkbPolygon)
    polygon.AddGeometry(ring)
    polygon_wgs84 = _transform_geometry_to_wgs84(polygon, source_srs)
    min_x, max_x, min_y, max_y = polygon_wgs84.GetEnvelope()
    payload = {
        "label": label,
        "bbox": [round(min_x, 6), round(min_y, 6), round(max_x, 6), round(max_y, 6)],
        "geojson": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "label": label,
                        "width": width,
                        "height": height,
                    },
                    "geometry": json.loads(polygon_wgs84.ExportToJson()),
                }
            ],
        },
        "width": width,
        "height": height,
    }
    dataset = None
    polygon = None
    polygon_wgs84 = None
    ring = None
    return payload


async def _parse_vector_upload(files: List[UploadFile], file_manager: FileManager) -> Dict:
    if not files:
        raise ValueError("请至少上传一个矢量文件")

    upload_kind = _detect_vector_upload_kind(files)
    temp_dir = file_manager.create_temp_dir(prefix="imagery_aoi_")
    try:
        if upload_kind == "geojson":
            geojson_file = next(
                (upload for upload in files if Path(upload.filename or "").suffix.lower() in {".geojson", ".json"}),
                None,
            )
            if geojson_file is None:
                raise ValueError("未找到 GeoJSON 文件")
            target_path = os.path.join(temp_dir, geojson_file.filename or "aoi.geojson")
            await _save_upload(geojson_file, target_path)
            payload = _vector_dataset_payload(target_path, label=geojson_file.filename or "AOI GeoJSON")
            payload["source_type"] = "geojson"
            return payload

        shape_path = file_manager.save_shapefiles(files, temp_dir)
        if not shape_path:
            raise ValueError("Shapefile 解析需要至少包含 .shp 文件")
        payload = _vector_dataset_payload(shape_path, label=Path(shape_path).name)
        payload["source_type"] = "shapefile"
        return payload
    finally:
        file_manager.cleanup_temp_dir(temp_dir)


def _landsat_collection_payload(collection: Dict) -> Dict:
    payload = dict(collection)
    payload["level"] = collection.get("product")
    return payload


def _landsat_scene_payload(scene: Dict) -> Dict:
    payload = dict(scene)
    payload["level"] = scene.get("product")
    return payload


def _landsat_task_payload(task: Dict) -> Dict:
    payload = dict(task)
    payload["level"] = task.get("product")
    return payload


def _build_imagery_search_request_from_landsat(request: LandsatSearchRequest) -> ImagerySearchRequest:
    inferred_sensor = LandsatDownloadService._normalize_sensor(explicit_sensor=request.sensor)
    if str(request.search_mode or "").strip().lower() == "scene_name":
        scene_sensor = LandsatDownloadService._normalize_sensor(scene_id=request.scene_name_query or "")
        if inferred_sensor == "landsat" and scene_sensor == "landsat-7":
            inferred_sensor = scene_sensor
    return ImagerySearchRequest(
        sensor=inferred_sensor,
        product=request.level,
        search_mode=request.search_mode,
        scene_name_query=request.scene_name_query,
        bbox=request.bbox,
        start_date=request.start_date,
        end_date=request.end_date,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit,
    )


def _build_imagery_download_request_from_landsat(
    request: LandsatDownloadTaskCreateRequest,
) -> ImageryDownloadTaskCreateRequest:
    items = [
        ImageryDownloadItem(
            sensor=LandsatDownloadService._normalize_sensor(
                scene_id=item.scene_id,
                filename=item.filename,
                url=item.url,
            ),
            product=item.level,
            scene_id=item.scene_id,
            band=item.band,
            filename=item.filename,
            url=item.url,
        )
        for item in request.items
    ]
    return ImageryDownloadTaskCreateRequest(items=items, mode=request.mode)


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
    task_result_service = TaskResultService(
        progress_manager=progress_manager,
        batch_manager=batch_manager,
        path_access=PATH_ACCESS,
    )

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
            "imagery_download_endpoints": [
                "/imagery/collections",
                "/imagery/search",
                "/imagery/aoi/parse",
                "/imagery/auth/status",
                "/imagery/auth/earthdata",
                "/imagery/proxy/status",
                "/imagery/proxy",
                "/imagery/download_dir",
                "/imagery/proxy_download",
                "/imagery/download",
                "/imagery/download_tasks",
            ],
            "landsat_download_compat_endpoints": [
                "/landsat/collections",
                "/landsat/search",
                "/landsat/auth/status",
                "/landsat/auth/earthdata",
                "/landsat/proxy/status",
                "/landsat/proxy",
                "/landsat/download_dir",
                "/landsat/proxy_download",
                "/landsat/download",
                "/landsat/download_tasks",
            ],
            "result_endpoints": [
                "/results/tasks",
                "/results/download/file",
                "/results/download/archive",
            ],
        }

    @app.get("/health")
    def health_check() -> Dict:
        return {
            "status": "healthy",
            "service": "remote-sensing-tools",
            "version": "3.0.0",
        }

    def _download_dir_payload() -> Dict:
        payload = landsat_download_service.get_download_dir_status()
        payload["allowed_download_roots"] = PATH_ACCESS.allowed_roots_payload()
        return payload

    def _require_landsat_default_download_prefix(target_dir: Optional[Path]) -> Optional[Path]:
        if target_dir is None:
            return None
        default_dir = landsat_download_service.get_default_download_dir().resolve(strict=False)
        candidate = Path(target_dir).resolve(strict=False)
        candidate_text = os.path.normcase(str(candidate))
        default_text = os.path.normcase(str(default_dir))
        if candidate_text != default_text and not candidate_text.startswith(default_text + os.sep):
            raise PathAccessError(
                f"服务端下载目录必须位于固定前缀 {default_dir} 下",
                status_code=400,
            )
        return candidate

    @app.get("/imagery/collections")
    def imagery_collections() -> Dict:
        payload = landsat_download_service.list_collections()
        payload.update(_download_dir_payload())
        return payload

    @app.get("/imagery/auth/status")
    def imagery_auth_status() -> Dict:
        return landsat_download_service.get_auth_status()

    @app.get("/imagery/proxy/status")
    def imagery_proxy_status() -> Dict:
        return landsat_download_service.get_proxy_status()

    @app.post("/imagery/auth/earthdata")
    async def imagery_set_earthdata(request: LandsatAuthRequest) -> Dict:
        try:
            return await landsat_download_service.configure_earthdata(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        except ConnectionError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        except Exception as exc:
            logger.error("EarthData 认证失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"认证失败: {exc}")

    @app.post("/imagery/proxy")
    def imagery_set_proxy(request: LandsatProxyRequest) -> Dict:
        try:
            return landsat_download_service.configure_proxy(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("影像下载代理配置失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"代理配置失败: {exc}")

    @app.get("/imagery/download_dir")
    def imagery_download_dir_status() -> Dict:
        return _download_dir_payload()

    @app.post("/imagery/download_dir")
    def imagery_set_download_dir(request: LandsatDownloadDirRequest) -> Dict:
        raw_download_dir = request.download_dir.strip()
        try:
            target_dir = None
            if raw_download_dir:
                target_dir = PATH_ACCESS.require_directory(
                    raw_download_dir,
                    access_label="写入影像下载目录",
                    must_exist=False,
                    allow_create=True,
                )
                target_dir = _require_landsat_default_download_prefix(target_dir)
            payload = landsat_download_service.configure_download_dir(target_dir)
            payload["allowed_download_roots"] = PATH_ACCESS.allowed_roots_payload()
            return payload
        except PathAccessError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("影像下载目录配置失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"下载目录配置失败: {exc}")

    @app.post("/imagery/search")
    async def imagery_search(request: ImagerySearchRequest) -> Dict:
        try:
            return await landsat_download_service.search(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("影像搜索失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"搜索失败: {exc}")

    @app.post("/imagery/aoi/parse")
    async def imagery_parse_aoi(files: List[UploadFile] = File(..., description="GeoJSON 或 Shapefile 配套文件")) -> Dict:
        try:
            return await _parse_vector_upload(files, file_manager)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("解析 AOI 矢量文件失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"解析 AOI 失败: {exc}")

    @app.get("/imagery/proxy_download")
    async def imagery_proxy_download(url: str, filename: str = "imagery_asset.bin"):
        try:
            return await landsat_download_service.create_proxy_download_response(url, filename)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        except Exception as exc:
            logger.error("影像代理下载失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"代理下载失败: {exc}")

    @app.post("/imagery/download")
    async def imagery_create_download(request: ImageryDownloadTaskCreateRequest) -> Dict:
        try:
            return await landsat_download_service.create_download_tasks(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("创建影像下载任务失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"创建下载任务失败: {exc}")

    @app.get("/imagery/download_tasks")
    def imagery_list_download_tasks() -> Dict:
        return landsat_download_service.list_download_tasks()

    @app.get("/imagery/download_tasks/{task_id}")
    def imagery_get_download_task(task_id: str) -> Dict:
        task = landsat_download_service.get_download_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"下载任务不存在: {task_id}")
        return task

    @app.delete("/imagery/download_tasks/completed")
    def imagery_clear_completed_download_tasks() -> Dict:
        return landsat_download_service.clear_completed_tasks()

    @app.delete("/imagery/download_tasks/{task_id}")
    def imagery_cancel_download_task(task_id: str) -> Dict:
        try:
            return landsat_download_service.cancel_download_task(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"下载任务不存在: {task_id}")

    @app.get("/imagery/download_tasks/{task_id}/file")
    async def imagery_download_task_file(task_id: str):
        try:
            return await landsat_download_service.build_task_file_response(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"下载任务不存在: {task_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"文件不存在: {exc}")
        except Exception as exc:
            logger.error("读取影像下载结果失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"读取下载结果失败: {exc}")

    @app.get("/landsat/collections")
    def landsat_collections() -> Dict:
        payload = landsat_download_service.list_collections()
        payload["collections"] = [
            collection
            for collection in payload["collections"]
            if collection.get("sensor") in {"landsat", "landsat-7"}
        ]
        payload["sensors"] = [
            sensor
            for sensor in payload["sensors"]
            if sensor.get("sensor") in {"landsat", "landsat-7"}
        ]
        payload.update(_download_dir_payload())
        payload["collections"] = [_landsat_collection_payload(collection) for collection in payload["collections"]]
        return payload

    @app.get("/landsat/auth/status")
    def landsat_auth_status() -> Dict:
        return landsat_download_service.get_auth_status()

    @app.get("/landsat/proxy/status")
    def landsat_proxy_status() -> Dict:
        return landsat_download_service.get_proxy_status()

    @app.post("/landsat/auth/earthdata")
    async def landsat_set_earthdata(request: LandsatAuthRequest) -> Dict:
        try:
            return await landsat_download_service.configure_earthdata(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        except ConnectionError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        except Exception as exc:
            logger.error("EarthData 认证失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"认证失败: {exc}")

    @app.post("/landsat/proxy")
    def landsat_set_proxy(request: LandsatProxyRequest) -> Dict:
        try:
            return landsat_download_service.configure_proxy(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("Landsat 代理配置失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"代理配置失败: {exc}")

    @app.get("/landsat/download_dir")
    def landsat_download_dir_status() -> Dict:
        return _download_dir_payload()

    @app.post("/landsat/download_dir")
    def landsat_set_download_dir(request: LandsatDownloadDirRequest) -> Dict:
        raw_download_dir = request.download_dir.strip()
        try:
            target_dir = None
            if raw_download_dir:
                target_dir = PATH_ACCESS.require_directory(
                    raw_download_dir,
                    access_label="写入 Landsat 下载目录",
                    must_exist=False,
                    allow_create=True,
                )
                target_dir = _require_landsat_default_download_prefix(target_dir)
            payload = landsat_download_service.configure_download_dir(target_dir)
            payload["allowed_download_roots"] = PATH_ACCESS.allowed_roots_payload()
            return payload
        except PathAccessError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("Landsat 下载目录配置失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"下载目录配置失败: {exc}")

    @app.post("/landsat/search")
    async def landsat_search(request: LandsatSearchRequest) -> Dict:
        try:
            result = await landsat_download_service.search(_build_imagery_search_request_from_landsat(request))
            result["items"] = [_landsat_scene_payload(item) for item in result["items"]]
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
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
            imagery_request = _build_imagery_download_request_from_landsat(request)
            return await landsat_download_service.create_download_tasks(imagery_request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("创建 Landsat 下载任务失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"创建下载任务失败: {exc}")

    @app.get("/landsat/download_tasks")
    def landsat_list_download_tasks() -> Dict:
        payload = landsat_download_service.list_download_tasks(sensor="landsat")
        payload["tasks"] = [_landsat_task_payload(task) for task in payload["tasks"]]
        return payload

    @app.get("/landsat/download_tasks/{task_id}")
    def landsat_get_download_task(task_id: str) -> Dict:
        task = landsat_download_service.get_download_task(task_id, sensor="landsat")
        if not task:
            raise HTTPException(status_code=404, detail=f"下载任务不存在: {task_id}")
        return _landsat_task_payload(task)

    @app.delete("/landsat/download_tasks/completed")
    def landsat_clear_completed_download_tasks() -> Dict:
        return landsat_download_service.clear_completed_tasks(sensor="landsat")

    @app.delete("/landsat/download_tasks/{task_id}")
    def landsat_cancel_download_task(task_id: str) -> Dict:
        try:
            return landsat_download_service.cancel_download_task(task_id, sensor="landsat")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"下载任务不存在: {task_id}")

    @app.get("/landsat/download_tasks/{task_id}/file")
    async def landsat_download_task_file(task_id: str):
        try:
            return await landsat_download_service.build_task_file_response(task_id, sensor="landsat")
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
    def list_directories(
        path: Optional[str] = None,
        include_files: bool = False,
        allowed_suffixes: Optional[str] = None,
    ) -> Dict:
        """List directories for UI path picker (local deployment)."""
        suffix_filters = _normalize_suffix_filters(allowed_suffixes)
        if path is None or not path.strip():
            payload = _list_root_directories()
            payload["files"] = []
            return payload

        try:
            current = PATH_ACCESS.require_directory(path, access_label="浏览目录")
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)

        try:
            entries = _list_directory_entries(
                current,
                include_files=include_files,
                allowed_suffixes=suffix_filters,
            )
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"无权限访问目录: {current}")
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"读取目录失败: {exc}")

        parent = ""
        if current.parent != current and PATH_ACCESS.is_allowed(current.parent):
            parent = str(current.parent.resolve(strict=False))

        return {
            "current": str(current),
            "parent": parent,
            "directories": entries["directories"],
            "files": entries["files"],
        }

    @app.post("/filesystem/vector_preview")
    def preview_vector_file(path: str = Form(..., description="本地矢量文件路径")) -> Dict:
        """读取本地 GeoJSON / Shapefile，并返回 bbox + geojson 预览信息。"""
        try:
            vector_path = PATH_ACCESS.require_file(
                path,
                access_label="预览矢量文件",
                allowed_suffixes=VECTOR_PREVIEW_EXTENSIONS,
            )
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)

        try:
            payload = _vector_dataset_payload(str(vector_path), label=vector_path.name)
            payload["source_type"] = "filesystem"
            payload["path"] = str(vector_path)
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("预览本地矢量文件失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"预览矢量文件失败: {exc}")

    @app.post("/filesystem/raster_footprint")
    def preview_raster_footprint(
        path: str = Form(..., description="本地栅格文件或场景目录路径"),
        product_level: Optional[str] = Form(None, description="场景目录产品级别，可选 L1/L2"),
    ) -> Dict:
        """读取本地栅格或场景目录，返回覆盖范围 bbox + geojson。"""
        try:
            raster_path = _resolve_raster_preview_target(path, product_level=product_level)
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        try:
            payload = _raster_dataset_payload(str(raster_path), label=raster_path.name)
            payload["source_type"] = "filesystem"
            payload["path"] = str(Path(path).resolve(strict=False))
            payload["raster_path"] = str(raster_path)
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("预览本地栅格覆盖范围失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"预览栅格覆盖范围失败: {exc}")

    @app.post("/imagery/raster_footprint")
    async def imagery_parse_raster_footprint(raster: UploadFile = File(..., description="本地上传的栅格文件")) -> Dict:
        """读取浏览器上传的栅格文件，并返回覆盖范围 bbox + geojson。"""
        suffix = Path(raster.filename or "").suffix.lower()
        if suffix not in RASTER_PREVIEW_EXTENSIONS:
            raise HTTPException(status_code=400, detail="请上传 .tif/.tiff/.img/.png 栅格文件")

        file_manager = FileManager()
        temp_dir = file_manager.create_temp_dir(prefix="imagery_footprint_")
        try:
            target_path = os.path.join(temp_dir, raster.filename or f"footprint{suffix or '.tif'}")
            await _save_upload(raster, target_path)
            payload = _raster_dataset_payload(target_path, label=raster.filename or Path(target_path).name)
            payload["source_type"] = "upload"
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("解析上传栅格覆盖范围失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"解析栅格覆盖范围失败: {exc}")
        finally:
            file_manager.cleanup_temp_dir(temp_dir)

    @app.get("/filesystem/scan_scenes")
    def scan_scenes(path: str) -> Dict:
        """扫描目录下的遥感影像场景（每个子目录 = 一个场景），检测 shp/ 文件夹"""
        try:
            target = PATH_ACCESS.require_directory(path, access_label="扫描目录")
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)

        scenes = []
        try:
            with os.scandir(target) as it:
                for entry in it:
                    if not entry.is_dir(follow_symlinks=False):
                        continue

                    scene_path = Path(entry.path).resolve(strict=False)
                    if not PATH_ACCESS.is_allowed(scene_path):
                        continue

                    shp_dir = scene_path / "shp"
                    has_shp = False
                    shp_file = None
                    if shp_dir.exists() and shp_dir.is_dir():
                        for shp_candidate in shp_dir.glob("*.shp"):
                            normalized_shp = _optional_allowed_file(
                                str(shp_candidate),
                                access_label="读取场景裁剪矢量文件",
                            )
                            if normalized_shp:
                                has_shp = True
                                shp_file = normalized_shp
                                break
                    available_product_levels = infer_available_product_levels(scene_path)
                    if available_product_levels:
                        product_level = "L2" if "L2" in available_product_levels else available_product_levels[0]
                    else:
                        filenames = [child.name for child in scene_path.iterdir() if child.is_file()]
                        product_level = _infer_product_level(entry.name, filenames)
                        available_product_levels = [product_level]

                    product_files = {
                        level: {
                            key: _optional_allowed_file(
                                value,
                                access_label=f"读取场景 {level} 辅助文件",
                            )
                            for key, value in find_scene_support_files(scene_path, product_level=level).items()
                        }
                        for level in available_product_levels
                    }
                    scene_files = product_files.get(product_level, {})
                    footprint_bbox = None
                    footprint_raster_path = None
                    try:
                        representative_raster = _resolve_raster_preview_target(str(scene_path), product_level=product_level)
                        footprint_payload = _raster_dataset_payload(str(representative_raster), label=entry.name)
                        footprint_bbox = footprint_payload.get("bbox")
                        footprint_raster_path = str(representative_raster)
                    except Exception as exc:
                        logger.warning("场景 %s 覆盖范围读取失败: %s", scene_path, exc)

                    scenes.append({
                        "id": str(scene_path),
                        "name": entry.name,
                        "path": str(scene_path),
                        "has_shp": has_shp,
                        "shp_file": shp_file,
                        "mtl_file": scene_files.get("mtl_file"),
                        "qa_band": scene_files.get("qa_band"),
                        "qa_radsat_band": scene_files.get("qa_radsat_band"),
                        "product_level": product_level,
                        "available_product_levels": available_product_levels,
                        "product_files": product_files,
                        "footprint_bbox": footprint_bbox,
                        "footprint_raster_path": footprint_raster_path,
                    })
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"无权限访问目录: {target}")
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"读取目录失败: {exc}")
        scenes.sort(key=lambda s: (s["name"].lower(), s["path"].lower()))
        return {"scenes": scenes, "total": len(scenes), "root": str(target)}

    @app.post("/preview_raster")
    async def preview_raster(
        file_path: str = Form(..., description="待预览的栅格/合成影像路径"),
        max_size: int = Form(512, description="最大预览边长像素"),
    ) -> Dict:
        try:
            raster_path = PATH_ACCESS.require_file(
                file_path,
                access_label="预览栅格",
                allowed_suffixes=RASTER_PREVIEW_EXTENSIONS,
            )
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)

        try:
            preview = Landsat8Processor().build_preview_base64(str(raster_path), max_size=max_size)
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

    @app.get("/results/tasks")
    def list_result_tasks() -> Dict:
        tasks = task_result_service.list_result_tasks()
        return {"tasks": [task.model_dump() for task in tasks], "count": len(tasks)}

    @app.get("/results/download/file")
    def download_result_file(file_path: str):
        try:
            return task_result_service.build_file_response(file_path)
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"文件不存在: {exc}")

    @app.get("/results/download/archive")
    def download_result_archive(output_dir: str):
        try:
            return task_result_service.build_archive_response(output_dir)
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"文件不存在: {exc}")

    @app.post("/filesystem/preprocess_landsat8_async")
    async def preprocess_landsat8_from_filesystem_async(
        scene_path: str = Form(..., description="服务端场景目录路径"),
        output_dir: str = Form(..., description="输出目录路径"),
        clip_extent: Optional[str] = Form(None, description="裁剪范围：xmin,ymin,xmax,ymax"),
        clip_shapefile: Optional[List[UploadFile]] = File(None, description="裁剪矢量文件"),
        create_composites: Optional[str] = Form(None, description="合成类型，如 true_color,false_color"),
        custom_formula: Optional[str] = Form(None, description="自定义指数公式"),
        custom_name: Optional[str] = Form(None, description="自定义指数名称"),
        apply_cloud_mask: bool = Form(False, description="是否应用云掩膜"),
        atm_correction_method: str = Form("DOS", description="大气校正方法: DOS 或 6S"),
        product_level: str = Form("L1", description="输入产品级别: L1 或 L2"),
    ) -> Dict:
        normalized_level = str(product_level or "L1").strip().upper()
        if normalized_level not in {"L1", "L2"}:
            raise HTTPException(status_code=400, detail="product_level 仅支持 L1 或 L2")

        try:
            scene_dir = PATH_ACCESS.require_directory(
                scene_path,
                access_label="读取在线资源场景目录",
            )
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)

        try:
            output_dir = str(
                PATH_ACCESS.require_directory(
                    output_dir,
                    access_label="写入输出目录",
                    must_exist=False,
                    allow_create=True,
                )
            )
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)

        job_id = str(uuid.uuid4())
        progress_manager.init_progress(job_id)

        temp_dir: Optional[str] = None
        try:
            band_paths = collect_band_paths(scene_dir, product_level=normalized_level)
            band_paths = {
                band_name: str(
                    PATH_ACCESS.require_file(
                        band_path,
                        access_label="读取在线资源波段文件",
                    )
                )
                for band_name, band_path in band_paths.items()
            }

            support_files = find_scene_support_files(scene_dir, product_level=normalized_level)
            mtl_path = _optional_allowed_file(
                support_files.get("mtl_file"),
                access_label="读取在线资源 MTL 文件",
            )
            qa_path = _optional_allowed_file(
                support_files.get("qa_band"),
                access_label="读取在线资源 QA 文件",
            )
            qa_radsat_path = _optional_allowed_file(
                support_files.get("qa_radsat_band"),
                access_label="读取在线资源 QA_RADSAT 文件",
            )

            shapefile_path = None
            if clip_shapefile:
                temp_dir = file_manager.create_temp_dir(prefix=f"landsat8_scene_{job_id}_")
                shape_dir = os.path.join(temp_dir, "shapefile")
                os.makedirs(shape_dir, exist_ok=True)
                shapefile_path = file_manager.save_shapefiles(clip_shapefile, shape_dir)

            extent_list = file_manager.parse_extent(clip_extent)
            composite_list = file_manager.parse_composites(create_composites)
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            progress_manager.update_progress(
                job_id,
                status="processing",
                step_id="upload",
                step_status="completed",
                progress=10,
                detail=f"已加载在线场景: {scene_dir.name}",
            )
        except ValueError as exc:
            if temp_dir:
                file_manager.cleanup_temp_dir(temp_dir)
            progress_manager.remove_progress(job_id)
            raise HTTPException(status_code=400, detail=str(exc))
        except HTTPException:
            if temp_dir:
                file_manager.cleanup_temp_dir(temp_dir)
            progress_manager.remove_progress(job_id)
            raise
        except PathAccessError as exc:
            if temp_dir:
                file_manager.cleanup_temp_dir(temp_dir)
            progress_manager.remove_progress(job_id)
            _raise_path_access_http_error(exc)
        except Exception as exc:
            if temp_dir:
                file_manager.cleanup_temp_dir(temp_dir)
            progress_manager.remove_progress(job_id)
            logger.error("在线资源预处理任务初始化失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"任务初始化失败: {exc}")

        _launch_async_preprocess(
            progress_manager=progress_manager,
            file_manager=file_manager,
            job_id=job_id,
            band_paths=band_paths,
            output_dir=output_dir,
            mtl_path=mtl_path,
            qa_path=qa_path,
            qa_radsat_path=qa_radsat_path,
            extent_list=extent_list,
            shapefile_path=shapefile_path,
            composite_list=composite_list,
            apply_cloud_mask=apply_cloud_mask,
            atm_correction_method=atm_correction_method,
            product_level=normalized_level,
            custom_formula=custom_formula,
            custom_name=custom_name,
            cleanup_temp_dir=temp_dir,
        )
        return {"job_id": job_id, "status": "processing"}

    @app.post("/preprocess_landsat8_async")
    async def preprocess_landsat8_async(
        bands: List[UploadFile] = File(..., description="Landsat 8 波段文件列表"),
        mtl_file: Optional[UploadFile] = File(None, description="MTL元数据文件"),
        qa_band: Optional[UploadFile] = File(None, description="QA波段文件"),
        qa_radsat_band: Optional[UploadFile] = File(None, description="QA_RADSAT 波段文件"),
        output_dir: str = Form(..., description="输出目录路径"),
        clip_extent: Optional[str] = Form(None, description="裁剪范围：xmin,ymin,xmax,ymax"),
        clip_shapefile: Optional[List[UploadFile]] = File(None, description="裁剪矢量文件"),
        create_composites: Optional[str] = Form(None, description="合成类型，如 true_color,false_color"),
        custom_formula: Optional[str] = Form(None, description="自定义指数公式"),
        custom_name: Optional[str] = Form(None, description="自定义指数名称"),
        apply_cloud_mask: bool = Form(False, description="是否应用云掩膜"),
        atm_correction_method: str = Form("DOS", description="大气校正方法: DOS 或 6S"),
        product_level: str = Form("L1", description="输入产品级别: L1 或 L2"),
    ) -> Dict:
        if not bands:
            raise HTTPException(status_code=400, detail="必须上传至少一个波段文件")

        try:
            output_dir = str(
                PATH_ACCESS.require_directory(
                    output_dir,
                    access_label="写入输出目录",
                    must_exist=False,
                    allow_create=True,
                )
            )
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)

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
                qa_radsat_band=qa_radsat_band,
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
            qa_radsat_path=preprocess_inputs["qa_radsat_path"],
            extent_list=preprocess_inputs["extent_list"],
            shapefile_path=preprocess_inputs["shapefile_path"],
            composite_list=preprocess_inputs["composite_list"],
            apply_cloud_mask=apply_cloud_mask,
            atm_correction_method=atm_correction_method,
            product_level=product_level,
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
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)
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

        except PathAccessError as exc:
            _raise_path_access_http_error(exc)
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
