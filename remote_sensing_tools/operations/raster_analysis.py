"""Raster post-processing utilities."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import numpy as np
from osgeo import gdal, osr


COMPARISON_LABELS = {
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "eq": "==",
    "between": "between",
    "outside": "outside",
}

BINARY_NODATA = 255
MU_PER_M2 = 1.0 / 666.6666666667


def _normalize_comparison(comparison: str) -> str:
    aliases = {
        ">": "gt",
        ">=": "gte",
        "<": "lt",
        "<=": "lte",
        "=": "eq",
        "==": "eq",
    }
    normalized = str(comparison or "gte").strip().lower()
    normalized = aliases.get(normalized, normalized)
    if normalized not in COMPARISON_LABELS:
        raise ValueError(f"不支持的二值化比较方式: {comparison}")
    return normalized


def _comparison_mask(
    values: np.ndarray,
    comparison: str,
    threshold: float,
    upper_threshold: Optional[float],
) -> np.ndarray:
    if comparison == "gt":
        return values > threshold
    if comparison == "gte":
        return values >= threshold
    if comparison == "lt":
        return values < threshold
    if comparison == "lte":
        return values <= threshold
    if comparison == "eq":
        return values == threshold

    if upper_threshold is None:
        raise ValueError("between/outside 比较方式必须提供上限阈值")
    if upper_threshold < threshold:
        raise ValueError("上限阈值不能小于下限阈值")

    if comparison == "between":
        return (values >= threshold) & (values <= upper_threshold)
    if comparison == "outside":
        return (values < threshold) | (values > upper_threshold)

    raise ValueError(f"不支持的二值化比较方式: {comparison}")


def _spatial_ref(dataset: gdal.Dataset) -> Optional[osr.SpatialReference]:
    projection = dataset.GetProjection()
    if not projection:
        return None

    srs = osr.SpatialReference()
    if srs.ImportFromWkt(projection) != 0:
        return None
    return srs


def _pixel_area_info(
    dataset: gdal.Dataset,
) -> Tuple[Dict[str, object], Optional[Callable[[int, int], np.ndarray]], Optional[float]]:
    geo_transform = dataset.GetGeoTransform(can_return_null=True)
    if geo_transform is None:
        return {
            "area_method": "pixel_count_only",
            "area_unit": "pixel",
            "pixel_area_m2": None,
            "pixel_area_raster_units": None,
        }, None, None

    pixel_area_raster_units = abs(
        geo_transform[1] * geo_transform[5] - geo_transform[2] * geo_transform[4]
    )
    srs = _spatial_ref(dataset)

    if srs and srs.IsGeographic() and abs(geo_transform[2]) < 1e-12 and abs(geo_transform[4]) < 1e-12:
        radius = srs.GetSemiMajor() or 6378137.0
        lon_width = abs(math.radians(geo_transform[1]))

        def row_area_m2(yoff: int, rows: int) -> np.ndarray:
            row_indices = np.arange(yoff, yoff + rows, dtype=np.float64)
            lat_top = geo_transform[3] + row_indices * geo_transform[5]
            lat_bottom = lat_top + geo_transform[5]
            return (
                radius
                * radius
                * lon_width
                * np.abs(np.sin(np.radians(lat_top)) - np.sin(np.radians(lat_bottom)))
            )

        return {
            "area_method": "geographic_spherical_row_area",
            "area_unit": "square_metre",
            "pixel_area_m2": None,
            "pixel_area_raster_units": pixel_area_raster_units,
        }, row_area_m2, None

    if srs and srs.IsProjected():
        linear_units = srs.GetLinearUnits() or 1.0
        pixel_area_m2 = pixel_area_raster_units * linear_units * linear_units
        return {
            "area_method": "projected_geotransform",
            "area_unit": "square_metre",
            "pixel_area_m2": pixel_area_m2,
            "pixel_area_raster_units": pixel_area_raster_units,
        }, None, pixel_area_m2

    return {
        "area_method": "raster_geotransform_units",
        "area_unit": "raster_square_unit",
        "pixel_area_m2": None,
        "pixel_area_raster_units": pixel_area_raster_units,
    }, None, None


def _safe_default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_binary.tif")


def binarize_raster(
    input_path: str,
    output_path: Optional[str] = None,
    *,
    threshold: float,
    comparison: str = "gte",
    upper_threshold: Optional[float] = None,
    target_value: int = 1,
    background_value: int = 0,
    nodata_value: int = BINARY_NODATA,
) -> Dict[str, object]:
    """Create a binary raster and return pixel/area statistics."""
    comparison = _normalize_comparison(comparison)
    input_file = Path(input_path)
    output_file = Path(output_path) if output_path else _safe_default_output_path(input_file)
    if input_file.resolve(strict=False) == output_file.resolve(strict=False):
        raise ValueError("二值化输出路径不能覆盖输入文件")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if target_value == nodata_value or background_value == nodata_value:
        raise ValueError("目标值和背景值不能等于 NoData 值")
    if not (0 <= target_value <= 254 and 0 <= background_value <= 254 and 0 <= nodata_value <= 255):
        raise ValueError("二值化输出值必须在 Byte 范围内")

    dataset = gdal.Open(str(input_file))
    if dataset is None:
        raise ValueError(f"无法打开栅格文件: {input_file}")

    band = dataset.GetRasterBand(1)
    width = dataset.RasterXSize
    height = dataset.RasterYSize
    source_nodata = band.GetNoDataValue()
    mask_band = band.GetMaskBand()
    area_info, row_area_m2, constant_pixel_area_m2 = _pixel_area_info(dataset)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(
        str(output_file),
        width,
        height,
        1,
        gdal.GDT_Byte,
        options=["COMPRESS=LZW"],
    )
    if out_ds is None:
        dataset = None
        raise ValueError(f"无法创建二值化输出文件: {output_file}")

    out_ds.SetProjection(dataset.GetProjection())
    geo_transform = dataset.GetGeoTransform(can_return_null=True)
    if geo_transform is not None:
        out_ds.SetGeoTransform(geo_transform)

    out_band = out_ds.GetRasterBand(1)
    out_band.SetNoDataValue(nodata_value)
    out_band.SetColorInterpretation(gdal.GCI_GrayIndex)

    block_x, block_y = band.GetBlockSize()
    if block_x <= 0:
        block_x = min(width, 512)
    if block_y <= 1:
        block_y = min(height, 512)

    total_pixels = int(width * height)
    valid_pixels = 0
    target_pixels = 0
    target_area_m2 = 0.0
    valid_area_m2 = 0.0

    for yoff in range(0, height, block_y):
        ysize = min(block_y, height - yoff)
        block_row_area = row_area_m2(yoff, ysize) if row_area_m2 else None

        for xoff in range(0, width, block_x):
            xsize = min(block_x, width - xoff)
            values = band.ReadAsArray(xoff, yoff, xsize, ysize).astype(np.float32, copy=False)
            valid_mask = np.isfinite(values)

            if source_nodata is not None:
                valid_mask &= values != source_nodata
            if mask_band is not None:
                source_mask = mask_band.ReadAsArray(xoff, yoff, xsize, ysize)
                valid_mask &= source_mask != 0

            binary_mask = valid_mask & _comparison_mask(values, comparison, threshold, upper_threshold)

            output = np.full((ysize, xsize), nodata_value, dtype=np.uint8)
            output[valid_mask] = background_value
            output[binary_mask] = target_value
            out_band.WriteArray(output, xoff, yoff)

            block_valid_pixels = int(np.count_nonzero(valid_mask))
            block_target_pixels = int(np.count_nonzero(binary_mask))
            valid_pixels += block_valid_pixels
            target_pixels += block_target_pixels

            if constant_pixel_area_m2 is not None:
                target_area_m2 += block_target_pixels * constant_pixel_area_m2
                valid_area_m2 += block_valid_pixels * constant_pixel_area_m2
            elif block_row_area is not None:
                row_targets = np.count_nonzero(binary_mask, axis=1).astype(np.float64)
                row_valid = np.count_nonzero(valid_mask, axis=1).astype(np.float64)
                target_area_m2 += float(np.dot(row_targets, block_row_area))
                valid_area_m2 += float(np.dot(row_valid, block_row_area))

    out_band.FlushCache()
    out_ds.FlushCache()
    out_ds = None
    dataset = None

    background_pixels = valid_pixels - target_pixels
    nodata_pixels = total_pixels - valid_pixels
    target_ratio = target_pixels / valid_pixels if valid_pixels else 0.0

    stats = {
        "total_pixels": total_pixels,
        "valid_pixels": valid_pixels,
        "target_pixels": target_pixels,
        "background_pixels": background_pixels,
        "nodata_pixels": nodata_pixels,
        "target_ratio": target_ratio,
        "target_area_m2": target_area_m2 if area_info["area_unit"] == "square_metre" else None,
        "target_area_ha": target_area_m2 / 10000.0 if area_info["area_unit"] == "square_metre" else None,
        "target_area_km2": target_area_m2 / 1_000_000.0 if area_info["area_unit"] == "square_metre" else None,
        "target_area_mu": target_area_m2 * MU_PER_M2 if area_info["area_unit"] == "square_metre" else None,
        "valid_area_m2": valid_area_m2 if area_info["area_unit"] == "square_metre" else None,
        **area_info,
    }

    return {
        "status": "success",
        "input_path": str(input_file.resolve(strict=False)),
        "output_path": str(output_file.resolve(strict=False)),
        "width": width,
        "height": height,
        "threshold": threshold,
        "upper_threshold": upper_threshold,
        "comparison": comparison,
        "comparison_label": COMPARISON_LABELS[comparison],
        "target_value": target_value,
        "background_value": background_value,
        "nodata_value": nodata_value,
        "stats": stats,
    }
