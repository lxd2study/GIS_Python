"""Shared helpers for API route modules."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..utils.file_utils import detect_sensor_from_path, detect_sentinel2_band_name


COMPOSITE_DESCRIPTIONS = {
    "true_color": ("真彩色", "真实自然色彩 (Red-Green-Blue)", "自然地物识别，最接近人眼视觉"),
    "false_color": ("假彩色", "植被增强 (NIR-Red-Green)", "植被健康监测，植物呈红色"),
    "agriculture": ("农业监测", "农作物分析 (SWIR1-NIR-Blue)", "农作物类型识别，土壤湿度评估"),
    "urban": ("城市研究", "城市区域增强 (SWIR2-SWIR1-Red)", "建筑物识别，城市规划"),
    "natural_color": ("自然彩色", "自然色调 (Red-Green-Blue)", "与真彩色一致，更利于直观判读"),
    "swir": ("短波红外", "短波红外合成 (SWIR2-NIR-Green)", "水体识别，云雾穿透"),
    "ndvi": ("NDVI", "归一化植被指数 (NIR-Red)/(NIR+Red)", "植被覆盖度与健康状况分析"),
    "evi": ("EVI", "Enhanced Vegetation Index (NIR-Red-Blue)", "高生物量区域植被活力评估"),
    "savi": ("SAVI", "土壤调节植被指数，适合植被稀疏区域", "减少土壤背景影响的植被监测"),
    "msavi": ("MSAVI", "修正SAVI，自适应土壤调节", "植被覆盖度变化大的区域监测"),
    "arvi": ("ARVI", "抗大气植被指数，减少大气干扰", "有雾霾时的植被监测"),
    "rvi": ("RVI", "比值植被指数 NIR/Red", "简单快速的植被监测"),
    "ndwi": ("NDWI", "归一化水体指数 (Green-NIR)/(Green+NIR)", "水体与地表含水量识别"),
    "mndwi": ("MNDWI", "改进归一化水体指数 (Green-SWIR1)", "城市区域水体提取，抑制建筑物噪声"),
    "awei": ("AWEI", "自动水体提取指数，适合有阴影场景", "自动化水体提取与分类"),
    "wri": ("WRI", "水体比率指数 (Green+Red)/(NIR+SWIR1)", "浅水和浑浊水体识别"),
    "ndbi": ("NDBI", "归一化建筑指数 (SWIR1-NIR)/(SWIR1+NIR)", "建筑区与城市扩张识别"),
    "ibi": ("IBI", "综合建筑指数，结合NDBI/SAVI/MNDWI", "精确的城市建筑区提取"),
    "ndbai": ("NDBaI", "归一化裸地与建筑指数", "裸地和建筑区识别"),
    "ui": ("UI", "城市指数 (SWIR2-NIR)/(SWIR2+NIR)", "简单高效的城市区域识别"),
    "nbr": ("NBR", "归一化燃烧指数 (NIR-SWIR2)/(NIR+SWIR2)", "火灾监测与燃烧程度评估"),
    "bsi": ("BSI", "裸土指数，用于裸土识别", "土壤侵蚀监测，裸地提取"),
    "ndsi": ("NDSI", "归一化积雪指数 (Green-SWIR1)/(Green+SWIR1)", "雪盖监测，冰川变化分析"),
    "apgi": ("APGI", "Sentinel-2 大棚指数，使用 Coastal/Red/NIR/SWIR2", "塑料大棚提取与设施农业识别"),
}


def detect_upload_band_name(filename: str) -> Optional[str]:
    """Try to parse a Landsat band name from an uploaded filename."""
    upper_name = filename.upper()
    for band_idx in range(1, 12):
        if (
            f"_B{band_idx}." in upper_name
            or f"_B{band_idx}_" in upper_name
            or f"B{band_idx}." in upper_name
        ):
            return f"B{band_idx}"
    return None


def detect_upload_sentinel2_band_name(filename: str) -> Optional[str]:
    """Try to parse a Sentinel-2 band name from an uploaded filename."""
    return detect_sentinel2_band_name(filename)


def infer_product_level(name: str, filenames: Optional[List[str]] = None) -> str:
    """Infer product level from a scene name and optional file list."""
    normalized = (name or "").upper()
    if "SENTINEL" in normalized or "L2A" in normalized or normalized.startswith(("S2A", "S2B", "S2C")):
        return "L2A"
    if "_L2" in normalized or "L2SP" in normalized:
        return "L2"

    for filename in filenames or []:
        upper_name = filename.upper()
        if "L2A" in upper_name or detect_upload_sentinel2_band_name(filename):
            return "L2A"
        if any(token in upper_name for token in ("_SR_B", "_ST_B", "_L2", "L2SP", "SURFACE_REFLECTANCE")):
            return "L2"
    return "L1"


def infer_sensor(name: str, filenames: Optional[List[str]] = None) -> str:
    """Infer source sensor from a scene name and optional file list."""
    candidates = [name or "", *(filenames or [])]
    for candidate in candidates:
        sensor = detect_sensor_from_path(Path(candidate))
        if sensor:
            return sensor
    return "landsat"


def get_composite_description(comp_type: str) -> tuple[str, str, str]:
    """Return display metadata for a composite/index type."""
    return COMPOSITE_DESCRIPTIONS.get(
        comp_type,
        (comp_type, "自定义组合", "请结合业务场景使用"),
    )
