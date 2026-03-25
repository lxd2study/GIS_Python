"""波段合成操作模块"""

import os
import ast
import re
import tempfile
import numpy as np
from osgeo import gdal
from typing import Dict, List
from ..core.constants import COMPOSITE_MAP


def create_composite(band_paths: Dict[str, str],
                    output_path: str,
                    composite_type: str = 'true_color') -> str:
    """
    创建波段合成影像

    Args:
        band_paths: 波段路径字典 {'B1': path, 'B2': path, ...}
        output_path: 输出路径
        composite_type: 合成类型 ('true_color', 'false_color', 'ndvi', 'evi', 'ndwi', 'ndbi')

    Returns:
        输出文件路径
    """
    if composite_type not in COMPOSITE_MAP:
        raise Exception(f"不支持的合成类型: {composite_type}")

    bands_to_use = COMPOSITE_MAP[composite_type]

    # Special handling for indices
    index_types = (
        'ndvi', 'evi', 'ndwi', 'ndbi',
        'savi', 'msavi', 'arvi', 'rvi',
        'mndwi', 'awei', 'wri',
        'ibi', 'ndbai', 'ui',
        'nbr', 'bsi', 'ndsi'
    )

    if composite_type in index_types:
        index_creators = {
            'ndvi': create_ndvi,
            'evi': create_evi,
            'ndwi': create_ndwi,
            'ndbi': create_ndbi,
            'savi': create_savi,
            'msavi': create_msavi,
            'arvi': create_arvi,
            'rvi': create_rvi,
            'mndwi': create_mndwi,
            'awei': create_awei,
            'wri': create_wri,
            'ibi': create_ibi,
            'ndbai': create_ndbai,
            'ui': create_ui,
            'nbr': create_nbr,
            'bsi': create_bsi,
            'ndsi': create_ndsi,
        }
        return index_creators[composite_type](band_paths, output_path)

    reference_ds = None
    reflectance_bands = []
    combined_valid_mask = None

    for band_name in bands_to_use:
        if band_name not in band_paths:
            raise Exception(f"缺少波段: {band_name}")

        band_path = band_paths[band_name]
        if '_processed' not in band_path and '_clipped' not in band_path:
            raise Exception(f"波段 {band_name} 需要先进行预处理: {band_path}")

        ds = gdal.Open(band_path)
        if ds is None:
            raise Exception(f"无法打开已处理波段文件: {band_path}")

        if reference_ds is None:
            reference_ds = ds
            arr = _read_band_array(band_path)
        else:
            if ds.RasterXSize != reference_ds.RasterXSize or ds.RasterYSize != reference_ds.RasterYSize:
                arr = _read_band_array(band_path, reference_ds)
            else:
                arr = _read_band_array(band_path)
            ds = None

        valid_mask = np.isfinite(arr)
        if combined_valid_mask is None:
            combined_valid_mask = valid_mask.copy()
        else:
            combined_valid_mask &= valid_mask

        reflectance_bands.append(np.clip(np.nan_to_num(arr, nan=0.0), 0.0, 1.0))

    if len(reflectance_bands) != 3:
        raise Exception(f"需要3个波段来创建RGB合成，当前只有{len(reflectance_bands)}个波段")
    if reference_ds is None:
        raise Exception("参考数据集为空")

    # 对每个波段做 2%-98% 分位拉伸 + gamma 校正，输出视觉可读的 Byte 影像。
    # 遥感真彩色反射率通常在 0.02-0.3 之间，不做拉伸则在 uint16 中值极低，
    # 绝大多数查看器会显示为近全黑影像。
    NODATA_BYTE = 0
    GAMMA = 1.5  # Landsat 8 常用 Gamma 值，使地物色彩更自然

    # 边界像素检测：DN=0 的填充区经辐射定标+DOS裁剪后所有波段反射率恰好为 0，
    # 需将其标记为 NoData，否则拉伸后会显示为暗色边框（黑边）。
    border_mask = np.all([b <= 0 for b in reflectance_bands], axis=0)
    valid_display_mask = combined_valid_mask & ~border_mask

    display_bands = []
    for reflectance in reflectance_bands:
        valid_vals = reflectance[valid_display_mask]
        if valid_vals.size > 0:
            p2  = float(np.percentile(valid_vals, 2))
            p98 = float(np.percentile(valid_vals, 98))
        else:
            p2, p98 = 0.0, 1.0

        if p98 <= p2:
            p98 = p2 + 1e-6

        norm = (reflectance - p2) / (p98 - p2)
        norm = np.clip(norm, 0.0, 1.0)
        # Gamma 校正：提亮中间调
        norm = np.power(norm, 1.0 / GAMMA)
        byte_arr = np.round(norm * 254 + 1).astype(np.uint8)  # 1-255，保留 0 作 NoData
        byte_arr[~valid_display_mask] = NODATA_BYTE
        display_bands.append(byte_arr)

    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(
        output_path,
        reference_ds.RasterXSize,
        reference_ds.RasterYSize,
        3,
        gdal.GDT_Byte,
        options=['COMPRESS=LZW', 'PHOTOMETRIC=RGB']
    )
    if out_ds is None:
        reference_ds = None
        raise Exception(f"无法创建输出文件: {output_path}")

    out_ds.SetProjection(reference_ds.GetProjection())
    out_ds.SetGeoTransform(reference_ds.GetGeoTransform())

    color_interpretations = [gdal.GCI_RedBand, gdal.GCI_GreenBand, gdal.GCI_BlueBand]
    for i, byte_arr in enumerate(display_bands):
        out_band = out_ds.GetRasterBand(i + 1)
        out_band.WriteArray(byte_arr)
        out_band.SetNoDataValue(NODATA_BYTE)
        out_band.SetColorInterpretation(color_interpretations[i])
        out_band.FlushCache()

    out_ds.FlushCache()
    reference_ds = None
    out_ds = None
    return output_path


BAND_NAME_RE = re.compile(r'^B(?:[1-9]|1[0-1])$')
ALLOWED_FUNCTIONS = {
    'abs': np.abs,
    'sqrt': np.sqrt,
    'log': np.log,
    'exp': np.exp,
    'clip': np.clip
}


def _get_processed_band_path(band_paths: Dict[str, str], band_name: str) -> str:
    if band_name not in band_paths:
        raise Exception(f"Missing band: {band_name}")

    band_path = band_paths[band_name]
    if '_processed' not in band_path and '_clipped' not in band_path:
        raise Exception(f"Band {band_name} must be preprocessed: {band_path}")

    return band_path


def _read_band_array(band_path: str, reference_ds: gdal.Dataset = None) -> np.ndarray:
    dataset = gdal.Open(band_path)
    if dataset is None:
        raise Exception(f"Unable to open band file: {band_path}")

    band = dataset.GetRasterBand(1)
    nodata = band.GetNoDataValue()

    if reference_ds and (
        dataset.RasterXSize != reference_ds.RasterXSize
        or dataset.RasterYSize != reference_ds.RasterYSize
    ):
        warp_kwargs = {
            'format': 'MEM',
            'width': reference_ds.RasterXSize,
            'height': reference_ds.RasterYSize,
            'resampleAlg': gdal.GRA_Bilinear,
        }
        if nodata is not None:
            warp_kwargs['srcNodata'] = nodata
            warp_kwargs['dstNodata'] = nodata

        resampled = gdal.Warp('', dataset, **warp_kwargs)
        if resampled is None:
            raise Exception(f"Failed to resample band: {band_path}")
        resampled_band = resampled.GetRasterBand(1)
        band_array = resampled_band.ReadAsArray().astype(np.float32)
        nodata = resampled_band.GetNoDataValue()
        mask = resampled_band.GetMaskBand().ReadAsArray()
        resampled = None
    else:
        band_array = band.ReadAsArray().astype(np.float32)
        mask = band.GetMaskBand().ReadAsArray()

    dataset = None

    if band_array.ndim > 2:
        band_array = band_array[0]

    if mask is not None:
        band_array = np.where(mask == 0, np.nan, band_array)
    if nodata is not None:
        band_array = np.where(band_array == nodata, np.nan, band_array)

    return band_array


def _write_float_raster(output_path: str, reference_ds: gdal.Dataset,
                        data: np.ndarray, nodata_value: float = -999) -> str:
    if reference_ds is None:
        raise Exception("Reference dataset is required")

    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(
        output_path,
        reference_ds.RasterXSize,
        reference_ds.RasterYSize,
        1,
        gdal.GDT_Float32,
        options=['COMPRESS=LZW']
    )

    if out_ds is None:
        raise Exception(f"Unable to create output file: {output_path}")

    out_ds.SetProjection(reference_ds.GetProjection())
    out_ds.SetGeoTransform(reference_ds.GetGeoTransform())

    if data.shape != (reference_ds.RasterYSize, reference_ds.RasterXSize):
        fd_in, temp_input = tempfile.mkstemp(suffix='.tif')
        fd_out, temp_output = tempfile.mkstemp(suffix='.tif')
        os.close(fd_in)
        os.close(fd_out)

        temp_driver = gdal.GetDriverByName('GTiff')
        temp_ds = temp_driver.Create(temp_input, data.shape[1], data.shape[0], 1, gdal.GDT_Float32)
        temp_ds.GetRasterBand(1).WriteArray(data)
        temp_ds = None

        gdal.Warp(
            temp_output,
            temp_input,
            xSize=reference_ds.RasterXSize,
            ySize=reference_ds.RasterYSize,
            resampleAlg=gdal.GRA_Bilinear
        )

        resampled_ds = gdal.Open(temp_output)
        data = resampled_ds.ReadAsArray()
        resampled_ds = None

        try:
            os.remove(temp_input)
            os.remove(temp_output)
        except OSError:
            pass

    out_band = out_ds.GetRasterBand(1)
    out_band.WriteArray(data)
    out_band.SetColorInterpretation(gdal.GCI_GrayIndex)
    out_band.SetNoDataValue(nodata_value)
    out_band.ComputeStatistics(False)
    out_band.FlushCache()
    out_ds.FlushCache()
    out_ds = None

    return output_path


def _normalized_difference_index(band_paths: Dict[str, str], output_path: str,
                                 band_a: str, band_b: str, label: str) -> str:
    band_a_path = _get_processed_band_path(band_paths, band_a)
    band_b_path = _get_processed_band_path(band_paths, band_b)

    reference_ds = gdal.Open(band_a_path)
    if reference_ds is None:
        raise Exception(f"Unable to open reference band for {label}")

    band_a_data = _read_band_array(band_a_path, reference_ds)
    band_b_data = _read_band_array(band_b_path, reference_ds)

    with np.errstate(divide='ignore', invalid='ignore'):
        denom = band_a_data + band_b_data
        denom = np.where(denom == 0, np.nan, denom)
        index = (band_a_data - band_b_data) / denom

    index = np.clip(index, -1, 1)
    index = np.where(np.isfinite(index), index, -999)

    output_path = _write_float_raster(output_path, reference_ds, index, nodata_value=-999)
    reference_ds = None
    return output_path


def create_ndwi(band_paths: Dict[str, str], output_path: str) -> str:
    return _normalized_difference_index(band_paths, output_path, 'B3', 'B5', 'NDWI')


def create_ndbi(band_paths: Dict[str, str], output_path: str) -> str:
    return _normalized_difference_index(band_paths, output_path, 'B6', 'B5', 'NDBI')


def create_evi(band_paths: Dict[str, str], output_path: str) -> str:
    nir_path = _get_processed_band_path(band_paths, 'B5')
    red_path = _get_processed_band_path(band_paths, 'B4')
    blue_path = _get_processed_band_path(band_paths, 'B2')

    reference_ds = gdal.Open(nir_path)
    if reference_ds is None:
        raise Exception("Unable to open reference band for EVI")

    nir = _read_band_array(nir_path, reference_ds)
    red = _read_band_array(red_path, reference_ds)
    blue = _read_band_array(blue_path, reference_ds)

    with np.errstate(divide='ignore', invalid='ignore'):
        denom = nir + 6.0 * red - 7.5 * blue + 1.0
        denom = np.where(denom == 0, np.nan, denom)
        evi = 2.5 * (nir - red) / denom

    evi = np.where(np.isfinite(evi), evi, -999)
    output_path = _write_float_raster(output_path, reference_ds, evi, nodata_value=-999)
    reference_ds = None
    return output_path


def _extract_band_names(formula: str) -> List[str]:
    try:
        expr = ast.parse(formula, mode='eval')
    except SyntaxError as exc:
        raise Exception(f"Invalid formula: {exc.msg}")

    band_names = set()
    for node in ast.walk(expr):
        if isinstance(node, ast.Name):
            name = node.id
            if name in ALLOWED_FUNCTIONS:
                continue
            band_name = name.upper()
            if BAND_NAME_RE.match(band_name):
                band_names.add(band_name)
            else:
                raise Exception(f"Unsupported symbol in formula: {name}")
        if isinstance(node, (ast.Attribute, ast.Subscript, ast.Lambda)):
            raise Exception("Unsupported syntax in formula")

    if not band_names:
        raise Exception("Formula must reference at least one band")

    return sorted(band_names)


def _eval_formula(node: ast.AST, variables: Dict[str, np.ndarray]):
    if isinstance(node, ast.Expression):
        return _eval_formula(node.body, variables)
    if isinstance(node, ast.BinOp):
        left = _eval_formula(node.left, variables)
        right = _eval_formula(node.right, variables)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise Exception("Unsupported operator in formula")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_formula(node.operand, variables)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise Exception("Unsupported unary operator in formula")
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise Exception("Unsupported constant in formula")
    if isinstance(node, ast.Num):  # Python <3.8 compatibility
        return float(node.n)
    if isinstance(node, ast.Name):
        name = node.id
        if name in ALLOWED_FUNCTIONS:
            raise Exception(f"Function '{name}' must be called")
        band_name = name.upper()
        if band_name in variables:
            return variables[band_name]
        raise Exception(f"Unknown symbol in formula: {name}")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise Exception("Unsupported function call in formula")
        func_name = node.func.id
        if func_name not in ALLOWED_FUNCTIONS:
            raise Exception(f"Unsupported function: {func_name}")
        func = ALLOWED_FUNCTIONS[func_name]
        args = [_eval_formula(arg, variables) for arg in node.args]
        kwargs = {kw.arg: _eval_formula(kw.value, variables) for kw in node.keywords}
        return func(*args, **kwargs)

    raise Exception("Unsupported expression element in formula")


def create_custom_index(band_paths: Dict[str, str], output_path: str, formula: str) -> str:
    if not formula or not formula.strip():
        raise Exception("Custom formula is empty")

    band_names = _extract_band_names(formula)
    reference_path = _get_processed_band_path(band_paths, band_names[0])

    reference_ds = gdal.Open(reference_path)
    if reference_ds is None:
        raise Exception("Unable to open reference band for custom index")

    band_arrays = {}
    for band_name in band_names:
        band_path = _get_processed_band_path(band_paths, band_name)
        band_arrays[band_name] = _read_band_array(band_path, reference_ds)

    expr = ast.parse(formula, mode='eval')
    with np.errstate(divide='ignore', invalid='ignore'):
        result = _eval_formula(expr, band_arrays)

    if np.isscalar(result):
        raise Exception("Custom formula must produce an array result")

    result = np.where(np.isfinite(result), result, -999)
    output_path = _write_float_raster(output_path, reference_ds, result, nodata_value=-999)
    reference_ds = None
    return output_path


def create_ndvi(band_paths: Dict[str, str], output_path: str) -> str:
    """创建NDVI (归一化植被指数) -- NDVI = (NIR - Red) / (NIR + Red)"""
    return _normalized_difference_index(band_paths, output_path, 'B5', 'B4', 'NDVI')


# ============================================================================
# 新增遥感指数函数（v3.0扩展）
# ============================================================================

def create_savi(band_paths: Dict[str, str], output_path: str, L: float = 0.5) -> str:
    """
    创建SAVI (土壤调节植被指数)

    SAVI = ((NIR - Red) / (NIR + Red + L)) * (1 + L)
    L: 土壤亮度校正因子，默认0.5（植被覆盖度中等）
       L=0: 高植被覆盖 (等同于NDVI)
       L=0.5: 中等植被覆盖
       L=1: 低植被覆盖

    用途：在植被稀疏、土壤背景影响大的区域，SAVI比NDVI更准确
    """
    nir_path = _get_processed_band_path(band_paths, 'B5')
    red_path = _get_processed_band_path(band_paths, 'B4')

    reference_ds = gdal.Open(nir_path)
    if reference_ds is None:
        raise Exception("Unable to open reference band for SAVI")

    nir = _read_band_array(nir_path, reference_ds)
    red = _read_band_array(red_path, reference_ds)

    with np.errstate(divide='ignore', invalid='ignore'):
        denom = nir + red + L
        denom = np.where(denom == 0, np.nan, denom)
        savi = ((nir - red) / denom) * (1 + L)

    savi = np.clip(savi, -1, 1)
    savi = np.where(np.isfinite(savi), savi, -999)

    output_path = _write_float_raster(output_path, reference_ds, savi, nodata_value=-999)
    reference_ds = None
    return output_path


def create_msavi(band_paths: Dict[str, str], output_path: str) -> str:
    """
    创建MSAVI (修正土壤调节植被指数)

    MSAVI = (2*NIR + 1 - sqrt((2*NIR + 1)^2 - 8*(NIR - Red))) / 2

    相比SAVI，MSAVI不需要人工设定L参数，可自适应土壤背景
    用途：植被覆盖度变化大的区域，比SAVI和NDVI更稳健
    """
    nir_path = _get_processed_band_path(band_paths, 'B5')
    red_path = _get_processed_band_path(band_paths, 'B4')

    reference_ds = gdal.Open(nir_path)
    if reference_ds is None:
        raise Exception("Unable to open reference band for MSAVI")

    nir = _read_band_array(nir_path, reference_ds)
    red = _read_band_array(red_path, reference_ds)

    with np.errstate(divide='ignore', invalid='ignore'):
        term1 = 2 * nir + 1
        term2 = np.sqrt(term1**2 - 8 * (nir - red))
        msavi = (term1 - term2) / 2

    msavi = np.clip(msavi, -1, 1)
    msavi = np.where(np.isfinite(msavi), msavi, -999)

    output_path = _write_float_raster(output_path, reference_ds, msavi, nodata_value=-999)
    reference_ds = None
    return output_path


def create_arvi(band_paths: Dict[str, str], output_path: str, gamma: float = 1.0) -> str:
    """
    创建ARVI (抗大气植被指数)

    ARVI = (NIR - (2*Red - Blue)) / (NIR + (2*Red - Blue))
    gamma: 大气校正参数，默认1.0

    用途：大气效应明显的区域（薄雾、气溶胶），比NDVI更抗干扰
    """
    nir_path = _get_processed_band_path(band_paths, 'B5')
    red_path = _get_processed_band_path(band_paths, 'B4')
    blue_path = _get_processed_band_path(band_paths, 'B2')

    reference_ds = gdal.Open(nir_path)
    if reference_ds is None:
        raise Exception("Unable to open reference band for ARVI")

    nir = _read_band_array(nir_path, reference_ds)
    red = _read_band_array(red_path, reference_ds)
    blue = _read_band_array(blue_path, reference_ds)

    with np.errstate(divide='ignore', invalid='ignore'):
        rb = gamma * (red - blue)
        denom = nir + (2 * red - blue)
        denom = np.where(denom == 0, np.nan, denom)
        arvi = (nir - rb) / denom

    arvi = np.clip(arvi, -1, 1)
    arvi = np.where(np.isfinite(arvi), arvi, -999)

    output_path = _write_float_raster(output_path, reference_ds, arvi, nodata_value=-999)
    reference_ds = None
    return output_path


def create_rvi(band_paths: Dict[str, str], output_path: str) -> str:
    """
    创建RVI (比值植被指数)

    RVI = NIR / Red

    用途：植被监测，简单直观，但对土壤背景敏感
    注意：无归一化，值域为[0, +∞)
    """
    nir_path = _get_processed_band_path(band_paths, 'B5')
    red_path = _get_processed_band_path(band_paths, 'B4')

    reference_ds = gdal.Open(nir_path)
    if reference_ds is None:
        raise Exception("Unable to open reference band for RVI")

    nir = _read_band_array(nir_path, reference_ds)
    red = _read_band_array(red_path, reference_ds)

    with np.errstate(divide='ignore', invalid='ignore'):
        red = np.where(red == 0, np.nan, red)
        rvi = nir / red

    rvi = np.clip(rvi, 0, 30)  # 限制极值
    rvi = np.where(np.isfinite(rvi), rvi, -999)

    output_path = _write_float_raster(output_path, reference_ds, rvi, nodata_value=-999)
    reference_ds = None
    return output_path


def create_mndwi(band_paths: Dict[str, str], output_path: str) -> str:
    """
    创建MNDWI (改进归一化水体指数)

    MNDWI = (Green - SWIR1) / (Green + SWIR1)

    相比NDWI，MNDWI使用SWIR1代替NIR，更能抑制建筑物噪声
    用途：城市区域水体提取，比NDWI更准确
    """
    return _normalized_difference_index(band_paths, output_path, 'B3', 'B6', 'MNDWI')


def create_awei(band_paths: Dict[str, str], output_path: str, use_shadow: bool = False) -> str:
    """
    创建AWEI (自动水体提取指数)

    AWEI_nsh (无阴影) = 4*(Green - SWIR1) - (0.25*NIR + 2.75*SWIR2)
    AWEI_sh (含阴影) = Blue + 2.5*Green - 1.5*(NIR + SWIR1) - 0.25*SWIR2

    用途：自动化水体提取，特别适合有阴影的复杂场景
    """
    green_path = _get_processed_band_path(band_paths, 'B3')
    swir1_path = _get_processed_band_path(band_paths, 'B6')

    reference_ds = gdal.Open(green_path)
    if reference_ds is None:
        raise Exception("Unable to open reference band for AWEI")

    green = _read_band_array(green_path, reference_ds)
    swir1 = _read_band_array(swir1_path, reference_ds)

    if use_shadow:
        # AWEI_sh
        blue_path = _get_processed_band_path(band_paths, 'B2')
        nir_path = _get_processed_band_path(band_paths, 'B5')
        swir2_path = _get_processed_band_path(band_paths, 'B7')

        blue = _read_band_array(blue_path, reference_ds)
        nir = _read_band_array(nir_path, reference_ds)
        swir2 = _read_band_array(swir2_path, reference_ds)

        awei = blue + 2.5 * green - 1.5 * (nir + swir1) - 0.25 * swir2
    else:
        # AWEI_nsh
        nir_path = _get_processed_band_path(band_paths, 'B5')
        swir2_path = _get_processed_band_path(band_paths, 'B7')

        nir = _read_band_array(nir_path, reference_ds)
        swir2 = _read_band_array(swir2_path, reference_ds)

        awei = 4 * (green - swir1) - (0.25 * nir + 2.75 * swir2)

    awei = np.where(np.isfinite(awei), awei, -999)

    output_path = _write_float_raster(output_path, reference_ds, awei, nodata_value=-999)
    reference_ds = None
    return output_path


def create_wri(band_paths: Dict[str, str], output_path: str) -> str:
    """
    创建WRI (水体比率指数)

    WRI = (Green + Red) / (NIR + SWIR1)

    用途：水体识别，对浅水和浑浊水体效果好
    """
    green_path = _get_processed_band_path(band_paths, 'B3')
    red_path = _get_processed_band_path(band_paths, 'B4')
    nir_path = _get_processed_band_path(band_paths, 'B5')
    swir1_path = _get_processed_band_path(band_paths, 'B6')

    reference_ds = gdal.Open(green_path)
    if reference_ds is None:
        raise Exception("Unable to open reference band for WRI")

    green = _read_band_array(green_path, reference_ds)
    red = _read_band_array(red_path, reference_ds)
    nir = _read_band_array(nir_path, reference_ds)
    swir1 = _read_band_array(swir1_path, reference_ds)

    with np.errstate(divide='ignore', invalid='ignore'):
        denom = nir + swir1
        denom = np.where(denom == 0, np.nan, denom)
        wri = (green + red) / denom

    wri = np.clip(wri, 0, 10)
    wri = np.where(np.isfinite(wri), wri, -999)

    output_path = _write_float_raster(output_path, reference_ds, wri, nodata_value=-999)
    reference_ds = None
    return output_path


def create_ibi(band_paths: Dict[str, str], output_path: str) -> str:
    """
    创建IBI (综合建筑指数)

    IBI = (NDBI - (SAVI + MNDWI)/2) / (NDBI + (SAVI + MNDWI)/2)

    综合建筑指数，结合NDBI、SAVI、MNDWI
    用途：城市建筑区提取，比单一NDBI更准确
    """
    # 先计算NDBI
    swir1_path = _get_processed_band_path(band_paths, 'B6')
    nir_path = _get_processed_band_path(band_paths, 'B5')
    red_path = _get_processed_band_path(band_paths, 'B4')
    green_path = _get_processed_band_path(band_paths, 'B3')

    reference_ds = gdal.Open(swir1_path)
    if reference_ds is None:
        raise Exception("Unable to open reference band for IBI")

    swir1 = _read_band_array(swir1_path, reference_ds)
    nir = _read_band_array(nir_path, reference_ds)
    red = _read_band_array(red_path, reference_ds)
    green = _read_band_array(green_path, reference_ds)

    # 计算NDBI
    with np.errstate(divide='ignore', invalid='ignore'):
        ndbi_denom = swir1 + nir
        ndbi_denom = np.where(ndbi_denom == 0, np.nan, ndbi_denom)
        ndbi = (swir1 - nir) / ndbi_denom

    # 计算SAVI (简化版，L=0.5)
    with np.errstate(divide='ignore', invalid='ignore'):
        savi_denom = nir + red + 0.5
        savi_denom = np.where(savi_denom == 0, np.nan, savi_denom)
        savi = ((nir - red) / savi_denom) * 1.5

    # 计算MNDWI
    with np.errstate(divide='ignore', invalid='ignore'):
        mndwi_denom = green + swir1
        mndwi_denom = np.where(mndwi_denom == 0, np.nan, mndwi_denom)
        mndwi = (green - swir1) / mndwi_denom

    # 计算IBI
    with np.errstate(divide='ignore', invalid='ignore'):
        term = (savi + mndwi) / 2
        ibi_denom = ndbi + term
        ibi_denom = np.where(ibi_denom == 0, np.nan, ibi_denom)
        ibi = (ndbi - term) / ibi_denom

    ibi = np.clip(ibi, -1, 1)
    ibi = np.where(np.isfinite(ibi), ibi, -999)

    output_path = _write_float_raster(output_path, reference_ds, ibi, nodata_value=-999)
    reference_ds = None
    return output_path


def create_ndbai(band_paths: Dict[str, str], output_path: str) -> str:
    """
    创建NDBaI (归一化裸地与建筑指数)

    NDBaI = (SWIR1 - TIR) / (SWIR1 + TIR)

    注意：需要热红外波段B10或B11，如果没有则使用SWIR2代替
    用途：裸地和建筑区识别
    """
    swir1_path = _get_processed_band_path(band_paths, 'B6')

    # B10/B11 是热红外波段，不经过辐射定标预处理，_get_processed_band_path 无法找到其处理后路径
    # 因此始终使用 SWIR2（B7）作为 TIR 代替波段
    tir_band = 'B7'

    return _normalized_difference_index(band_paths, output_path, 'B6', tir_band, 'NDBaI')


def create_ui(band_paths: Dict[str, str], output_path: str) -> str:
    """
    创建UI (城市指数)

    UI = (SWIR2 - NIR) / (SWIR2 + NIR)

    用途：城市区域识别，简单高效
    """
    return _normalized_difference_index(band_paths, output_path, 'B7', 'B5', 'UI')


def create_nbr(band_paths: Dict[str, str], output_path: str) -> str:
    """
    创建NBR (归一化燃烧指数)

    NBR = (NIR - SWIR2) / (NIR + SWIR2)

    用途：火灾监测、燃烧程度评估
    通过对比火灾前后NBR值，可计算dNBR评估火灾严重程度
    """
    return _normalized_difference_index(band_paths, output_path, 'B5', 'B7', 'NBR')


def create_bsi(band_paths: Dict[str, str], output_path: str) -> str:
    """
    创建BSI (裸土指数)

    BSI = ((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))

    用途：裸土识别、土壤侵蚀监测
    """
    swir1_path = _get_processed_band_path(band_paths, 'B6')
    red_path = _get_processed_band_path(band_paths, 'B4')
    nir_path = _get_processed_band_path(band_paths, 'B5')
    blue_path = _get_processed_band_path(band_paths, 'B2')

    reference_ds = gdal.Open(swir1_path)
    if reference_ds is None:
        raise Exception("Unable to open reference band for BSI")

    swir1 = _read_band_array(swir1_path, reference_ds)
    red = _read_band_array(red_path, reference_ds)
    nir = _read_band_array(nir_path, reference_ds)
    blue = _read_band_array(blue_path, reference_ds)

    with np.errstate(divide='ignore', invalid='ignore'):
        term1 = swir1 + red
        term2 = nir + blue
        denom = term1 + term2
        denom = np.where(denom == 0, np.nan, denom)
        bsi = (term1 - term2) / denom

    bsi = np.clip(bsi, -1, 1)
    bsi = np.where(np.isfinite(bsi), bsi, -999)

    output_path = _write_float_raster(output_path, reference_ds, bsi, nodata_value=-999)
    reference_ds = None
    return output_path


def create_ndsi(band_paths: Dict[str, str], output_path: str) -> str:
    """
    创建NDSI (归一化积雪指数)

    NDSI = (Green - SWIR1) / (Green + SWIR1)

    用途：雪盖监测、冰川变化分析
    NDSI > 0.4 通常表示积雪
    """
    return _normalized_difference_index(band_paths, output_path, 'B3', 'B6', 'NDSI')
