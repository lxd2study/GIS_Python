"""Landsat 8 影像处理器核心模块"""

import os
import re
import base64
import logging
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from osgeo import gdal
from typing import Dict, List, Tuple, Optional, Callable

logger = logging.getLogger(__name__)
PROCESSED_BAND_NODATA = -9999.0

# 启用GDAL异常处理
gdal.UseExceptions()
warnings.filterwarnings('ignore', category=FutureWarning)

from .constants import (
    RADIANCE_MULT, RADIANCE_ADD, ESUN, COMPOSITE_MAP, SIXS_PARAMETERS,
    SUPPORTED_OPTICAL_BANDS, THERMAL_BANDS
)
from .config import settings
from ..operations.radiometric import dn_to_radiance, radiance_to_reflectance
from ..operations.atmospheric import dark_object_subtraction, cloud_mask_from_qa, sixs_atmospheric_correction
from ..operations.geometric import clip_raster
from ..operations.synthesis import create_composite, create_custom_index


class Landsat8Processor:
    """Landsat 8 影像处理器"""

    def __init__(self):
        """初始化处理器"""
        gdal.AllRegister()
        self.metadata = {
            'sun_elevation': 45.0,
            'date_acquired': None,
            'earth_sun_distance': None,
        }
        # 使用常量中的参数
        self.RADIANCE_MULT = RADIANCE_MULT.copy()
        self.RADIANCE_ADD = RADIANCE_ADD.copy()
        self.ESUN = ESUN.copy()
        self.REFLECTANCE_MULT = {}
        self.REFLECTANCE_ADD = {}

    @staticmethod
    def _safe_join(output_dir: str, filename: str) -> str:
        """以操作系统友好的分隔符拼接路径。"""
        return str(Path(output_dir) / filename)

    @staticmethod
    def _sanitize_index_name(name: Optional[str], fallback: str = 'custom_index') -> str:
        if not name:
            return fallback

        safe = re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_')
        if not safe:
            return fallback

        return safe.lower()

    @staticmethod
    def _build_reporter(progress_callback: Optional[Callable[[Dict], None]]) -> Callable[[str, str, Optional[int], str], None]:
        def report(step_id: str, detail: str, progress: Optional[int] = None, status: str = 'active'):
            if progress_callback:
                progress_callback({
                    'step': step_id,
                    'detail': detail,
                    'progress': progress,
                    'status': status,
                })

        return report

    @staticmethod
    def _init_results() -> Dict:
        return {
            'status': 'success',
            'processed_bands': {},
            'composites': {},
            'cloud_mask': None,
            'metadata': {},
            'atm_correction_method': None,
        }

    @staticmethod
    def _log_array_stats(label: str, array: np.ndarray) -> None:
        valid = array[np.isfinite(array)]
        if valid.size == 0:
            logger.debug("%s统计: 无有效像元", label)
            return

        logger.debug(
            "%s统计: min=%.6f, max=%.6f, mean=%.6f",
            label,
            float(valid.min()),
            float(valid.max()),
            float(valid.mean()),
        )

    @staticmethod
    def _load_band_array(band_path: str) -> np.ndarray:
        dataset = gdal.Open(band_path)
        if dataset is None:
            raise Exception(f"无法打开波段文件: {band_path}")

        dn = dataset.ReadAsArray()
        dataset = None

        if dn.size == 0:
            raise Exception(f"波段文件为空: {band_path}")

        return dn

    @staticmethod
    def _log_reflectance_quality(band_name: str, reflectance: np.ndarray) -> None:
        valid = reflectance[np.isfinite(reflectance)]
        if valid.size == 0:
            logger.warning("波段 %s 无有效反射率像元", band_name)
            return

        reflectance_min = float(valid.min())
        reflectance_max = float(valid.max())
        reflectance_mean = float(valid.mean())
        logger.debug(
            "波段 %s 保存前统计: min=%.6f, max=%.6f, mean=%.6f",
            band_name,
            reflectance_min,
            reflectance_max,
            reflectance_mean,
        )

        if reflectance_min < -0.1 or reflectance_max > 1.5:
            logger.warning("波段 %s 反射率超出合理范围[-0.1, 1.5]", band_name)

        negative_ratio = float(np.sum(valid < 0) / valid.size * 100)
        if negative_ratio > 5:
            logger.warning("波段 %s 有 %.2f%% 的负值", band_name, negative_ratio)

    def _compute_toa_reflectance(self, dn: np.ndarray, band_name: str) -> np.ndarray:
        self._log_array_stats(f"波段 {band_name} DN", dn)

        reflectance = self.dn_to_toa_reflectance_by_mtl(dn, band_name)
        if reflectance is not None:
            logger.info("波段 %s 使用 MTL 反射率系数计算 TOA 反射率", band_name)
            self._log_array_stats(f"波段 {band_name} TOA反射率", reflectance)
            return reflectance

        radiance = self.dn_to_radiance(dn, band_name)
        self._log_array_stats(f"波段 {band_name} 辐射亮度", radiance)
        reflectance = self.radiance_to_reflectance(radiance, band_name)
        self._log_array_stats(f"波段 {band_name} 反射率", reflectance)
        return reflectance

    def _apply_atmospheric_correction(
        self,
        reflectance: np.ndarray,
        band_name: str,
        apply_atm_correction: bool,
        atm_correction_method: str,
    ) -> Tuple[np.ndarray, str]:
        if not apply_atm_correction:
            return reflectance, 'NONE'

        if atm_correction_method.upper() != '6S':
            logger.info("波段 %s: 使用 DOS (暗目标法) 进行大气校正", band_name)
            corrected = dark_object_subtraction(reflectance)
            logger.info("波段 %s DOS大气校正完成", band_name)
            self._log_array_stats(f"波段 {band_name} DOS校正后", corrected)
            return corrected, 'DOS'

        try:
            logger.info("波段 %s: 开始使用 6S 模型进行大气校正", band_name)
            corrected = self.sixs_atmospheric_correction(reflectance, band_name)
            logger.info("波段 %s 6S大气校正成功", band_name)
            self._log_array_stats(f"波段 {band_name} 6S校正后", corrected)
            return corrected, '6S'
        except Exception as exc:
            logger.warning("波段 %s: 6S大气校正失败,回退到DOS方法", band_name)
            logger.warning("失败原因: %s", str(exc))
            corrected = dark_object_subtraction(reflectance)
            logger.info("波段 %s DOS大气校正完成", band_name)
            self._log_array_stats(f"波段 {band_name} DOS校正后", corrected)
            return corrected, 'DOS(6S失败回退)'

    def read_mtl_file(self, mtl_path: str) -> Dict:
        """
        读取 Landsat 8 MTL 元数据文件

        Args:
            mtl_path: MTL文件路径

        Returns:
            包含元数据的字典
        """
        metadata = {}
        try:
            with open(mtl_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('\"')
                        metadata[key] = value

            # 提取关键参数
            self.metadata = {
                'scene_id': metadata.get('LANDSAT_SCENE_ID', ''),
                'date_acquired': metadata.get('DATE_ACQUIRED', ''),
                'sun_elevation': float(metadata.get('SUN_ELEVATION', 45.0)),
                'sun_azimuth': float(metadata.get('SUN_AZIMUTH', 135.0)),
                'cloud_cover': float(metadata.get('CLOUD_COVER', 0.0)),
                'earth_sun_distance': float(metadata.get('EARTH_SUN_DISTANCE', 1.0)),
            }

            # 提取各波段的辐射定标参数和反射率参数
            bands_found = 0
            refl_bands_found = 0
            for i in range(1, 12):
                band = f'B{i}'
                mult_key = f'RADIANCE_MULT_BAND_{i}'
                add_key = f'RADIANCE_ADD_BAND_{i}'
                refl_mult_key = f'REFLECTANCE_MULT_BAND_{i}'
                refl_add_key = f'REFLECTANCE_ADD_BAND_{i}'

                if mult_key in metadata:
                    self.RADIANCE_MULT[band] = float(metadata[mult_key])
                    bands_found += 1
                if add_key in metadata:
                    self.RADIANCE_ADD[band] = float(metadata[add_key])
                if refl_mult_key in metadata:
                    self.REFLECTANCE_MULT[band] = float(metadata[refl_mult_key])
                    refl_bands_found += 1
                if refl_add_key in metadata:
                    self.REFLECTANCE_ADD[band] = float(metadata[refl_add_key])

            logger.info("从MTL文件中读取了 %d 个波段的辐射定标参数", bands_found)
            logger.info("从MTL文件中读取了 %d 个波段的反射率参数", refl_bands_found)
            logger.info("太阳高度角: %s°", self.metadata.get('sun_elevation'))
            logger.info("日地距离: %s AU", self.metadata.get('earth_sun_distance'))
            logger.info("观测日期: %s", self.metadata.get('date_acquired'))
            logger.info("云覆盖率: %s%%", self.metadata.get('cloud_cover'))
            logger.debug("B4参数: MULT=%s, ADD=%s", self.RADIANCE_MULT.get('B4'), self.RADIANCE_ADD.get('B4'))
            logger.debug("B3参数: MULT=%s, ADD=%s", self.RADIANCE_MULT.get('B3'), self.RADIANCE_ADD.get('B3'))
            logger.debug("B2参数: MULT=%s, ADD=%s", self.RADIANCE_MULT.get('B2'), self.RADIANCE_ADD.get('B2'))

            return self.metadata

        except Exception as e:
            raise Exception(f"读取MTL文件失败: {str(e)}")

    def dn_to_toa_reflectance_by_mtl(self, dn_array: np.ndarray, band_name: str) -> Optional[np.ndarray]:
        """使用 MTL 反射率系数直接从 DN 计算 TOA 反射率。"""
        if band_name not in self.REFLECTANCE_MULT or band_name not in self.REFLECTANCE_ADD:
            return None

        sun_elevation = float(self.metadata.get('sun_elevation', 45.0))
        sin_sun = np.sin(np.deg2rad(sun_elevation))
        if sin_sun <= 0:
            sin_sun = np.sin(np.deg2rad(45.0))

        m_rho = self.REFLECTANCE_MULT[band_name]
        a_rho = self.REFLECTANCE_ADD[band_name]
        reflectance = (m_rho * dn_array.astype(np.float32) + a_rho) / sin_sun
        return np.clip(reflectance, -0.1, 2.0)

    def dn_to_radiance(self, dn_array: np.ndarray, band_name: str) -> np.ndarray:
        """
        DN值转辐射亮度

        使用operations.radiometric模块的函数
        """
        return dn_to_radiance(dn_array, band_name, self.RADIANCE_MULT, self.RADIANCE_ADD)

    def radiance_to_reflectance(self, radiance: np.ndarray, band_name: str,
                               sun_elevation: float = None) -> np.ndarray:
        """
        辐射亮度转地表反射率 (TOA反射率)

        使用operations.radiometric模块的函数
        """
        if sun_elevation is None:
            sun_elevation = self.metadata.get('sun_elevation', 45.0)

        # 获取日地距离和观测日期
        earth_sun_distance = self.metadata.get('earth_sun_distance', None)
        date_acquired = self.metadata.get('date_acquired', None)

        return radiance_to_reflectance(
            radiance, band_name, self.ESUN, sun_elevation,
            earth_sun_distance=earth_sun_distance,
            date_acquired=date_acquired
        )

    def sixs_atmospheric_correction(self, reflectance: np.ndarray,
                                    band_name: str,
                                    view_zenith: float = 0.0,
                                    view_azimuth: float = 0.0,
                                    atmospheric_profile: int = None,
                                    aerosol_profile: int = None,
                                    visibility: float = None,
                                    aot550: float = None,
                                    altitude: float = None) -> np.ndarray:
        """
        6S模型大气校正

        Args:
            reflectance: TOA反射率数组
            band_name: 波段名称
            view_zenith: 观测天顶角(度), 默认0
            view_azimuth: 观测方位角(度), 默认0
            atmospheric_profile: 大气模型, 默认使用SIXS_PARAMETERS中的配置
            aerosol_profile: 气溶胶模型, 默认使用SIXS_PARAMETERS中的配置
            visibility: 能见度(km), 默认使用SIXS_PARAMETERS中的配置
            aot550: 550nm气溶胶光学厚度, 默认使用SIXS_PARAMETERS中的配置
            altitude: 目标高度(km), 默认使用SIXS_PARAMETERS中的配置

        Returns:
            大气校正后的地表反射率数组
        """
        # 获取元数据
        sun_elevation = self.metadata.get('sun_elevation', 45.0)
        sun_zenith = 90.0 - sun_elevation
        sun_azimuth = self.metadata.get('sun_azimuth', 135.0)
        date = self.metadata.get('date_acquired', None)

        # 使用默认参数
        if atmospheric_profile is None:
            atmospheric_profile = SIXS_PARAMETERS['atmospheric_profile']
        if aerosol_profile is None:
            aerosol_profile = SIXS_PARAMETERS['aerosol_profile']
        if visibility is None:
            visibility = SIXS_PARAMETERS['visibility']
        if aot550 is None:
            aot550 = SIXS_PARAMETERS['aot550']
        if altitude is None:
            altitude = SIXS_PARAMETERS['altitude']

        return sixs_atmospheric_correction(
            reflectance=reflectance,
            band_name=band_name,
            sun_zenith=sun_zenith,
            sun_azimuth=sun_azimuth,
            view_zenith=view_zenith,
            view_azimuth=view_azimuth,
            date=date,
            wavelengths=SIXS_PARAMETERS['wavelengths'],
            atmospheric_profile=atmospheric_profile,
            aerosol_profile=aerosol_profile,
            visibility=visibility,
            aot550=aot550,
            altitude=altitude
        )

    def _load_metadata_for_preprocess(self, mtl_path: Optional[str], results: Dict, report: Callable) -> None:
        if mtl_path and os.path.exists(mtl_path):
            logger.info("正在读取MTL文件: %s", mtl_path)
            self.read_mtl_file(mtl_path)
            results['metadata'] = self.metadata
            logger.info("MTL元数据读取完成:")
            logger.info("  - 场景ID: %s", self.metadata.get('scene_id', 'N/A'))
            logger.info("  - 观测日期: %s", self.metadata.get('date_acquired', 'N/A'))
            logger.info("  - 太阳高度角: %s°", self.metadata.get('sun_elevation', 'N/A'))
            logger.info("  - 日地距离: %s AU", self.metadata.get('earth_sun_distance', 'N/A'))
            logger.info("  - 云覆盖率: %s%%", self.metadata.get('cloud_cover', 'N/A'))
            report('metadata', '已读取MTL元数据', progress=25, status='completed')
            return

        logger.warning("未找到MTL文件，使用默认参数")
        logger.warning("  - 太阳高度角: 45.0° (默认)")
        logger.warning("  - 日地距离: 1.0 AU (默认)")
        logger.warning("  注意: 这可能导致反射率计算精度降低")
        report('metadata', '未提供MTL，使用默认参数', progress=20, status='completed')

    @staticmethod
    def _save_cloud_mask(cloud_mask: np.ndarray, reference_band_path: str, qa_band_path: str, cloud_mask_path: str) -> np.ndarray:
        ref_ds = gdal.Open(reference_band_path)
        if ref_ds is None:
            raise Exception(f"无法打开参考波段文件: {reference_band_path}")

        driver = gdal.GetDriverByName('GTiff')
        mask_ds = driver.Create(
            cloud_mask_path,
            ref_ds.RasterXSize,
            ref_ds.RasterYSize,
            1,
            gdal.GDT_Byte,
        )
        mask_ds.SetProjection(ref_ds.GetProjection())
        mask_ds.SetGeoTransform(ref_ds.GetGeoTransform())

        if cloud_mask.shape != (ref_ds.RasterYSize, ref_ds.RasterXSize):
            original_mask_ds = gdal.Open(qa_band_path)
            if original_mask_ds is None:
                raise Exception(f"无法打开QA波段文件: {qa_band_path}")

            gdal.Warp(mask_ds, original_mask_ds, resampleAlg=gdal.GRA_NearestNeighbour)
            cloud_mask = mask_ds.ReadAsArray()
            original_mask_ds = None
        else:
            mask_ds.GetRasterBand(1).WriteArray(cloud_mask)

        mask_ds = None
        ref_ds = None
        return cloud_mask

    def _prepare_cloud_mask(
        self,
        band_paths: Dict[str, str],
        output_dir: str,
        apply_cloud_mask: bool,
        qa_band_path: Optional[str],
        report: Callable,
    ) -> Tuple[Optional[np.ndarray], Optional[str]]:
        if not (apply_cloud_mask and qa_band_path and os.path.exists(qa_band_path)):
            report('cloud_mask', '未启用云掩膜或未提供QA文件', progress=35, status='completed')
            return None, None

        try:
            report('cloud_mask', '正在提取云掩膜', progress=35, status='active')
            cloud_mask = cloud_mask_from_qa(qa_band_path)
            reference_band_path = next((path for path in band_paths.values() if os.path.exists(path)), None)
            if reference_band_path is None:
                raise Exception("未找到可用于生成云掩膜的参考波段")

            cloud_mask_path = self._safe_join(output_dir, 'cloud_mask.tif')
            cloud_mask = self._save_cloud_mask(cloud_mask, reference_band_path, qa_band_path, cloud_mask_path)
            report('cloud_mask', '云掩膜处理完成', progress=45, status='completed')
            return cloud_mask, cloud_mask_path
        except Exception as exc:
            logger.warning("云掩膜处理失败，跳过云掩膜: %s", str(exc))
            report('cloud_mask', '云掩膜处理失败，已跳过', progress=45, status='exception')
            return None, None

    @staticmethod
    def _filter_bands_to_process(band_paths: Dict[str, str]) -> Tuple[List[Tuple[str, str]], List[str]]:
        bands_to_process: List[Tuple[str, str]] = []
        skipped_bands: List[str] = []

        for band_name, band_path in band_paths.items():
            if not os.path.exists(band_path):
                continue

            if band_name in THERMAL_BANDS:
                logger.warning("跳过波段 %s (热红外波段)", band_name)
                logger.warning("  原因: 热红外波段测量地物自身热辐射，不适用于反射率处理")
                skipped_bands.append(band_name)
                continue

            bands_to_process.append((band_name, band_path))

        return bands_to_process, skipped_bands

    @staticmethod
    def _apply_cloud_mask_to_reflectance(
        reflectance: np.ndarray,
        cloud_mask: Optional[np.ndarray],
        band_name: str,
    ) -> np.ndarray:
        if cloud_mask is None:
            return reflectance

        if cloud_mask.shape != reflectance.shape:
            logger.warning("波段 %s 与云掩膜尺寸不匹配，跳过云掩膜处理", band_name)
            return reflectance

        reflectance[cloud_mask == 1] = 0
        return reflectance

    @staticmethod
    def _write_processed_band(output_band_path: str, reference_band_path: str, reflectance: np.ndarray) -> None:
        ref_ds = gdal.Open(reference_band_path)
        if ref_ds is None:
            raise Exception(f"无法打开参考波段文件: {reference_band_path}")

        # 处理结果中的无效区域统一写成显式 NoData，避免裁剪边缘显示成黑边。
        reflectance_to_write = np.where(
            np.isfinite(reflectance),
            reflectance,
            PROCESSED_BAND_NODATA,
        ).astype(np.float32)

        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(
            output_band_path,
            ref_ds.RasterXSize,
            ref_ds.RasterYSize,
            1,
            gdal.GDT_Float32,
            options=['COMPRESS=LZW'],
        )
        out_ds.SetProjection(ref_ds.GetProjection())
        out_ds.SetGeoTransform(ref_ds.GetGeoTransform())
        out_band = out_ds.GetRasterBand(1)
        out_band.WriteArray(reflectance_to_write)
        out_band.SetNoDataValue(PROCESSED_BAND_NODATA)

        ref_ds = None
        out_ds = None

    def _clip_output_if_needed(
        self,
        output_band_path: str,
        output_dir: str,
        band_name: str,
        clip_extent: Optional[List[float]],
        clip_shapefile: Optional[str],
    ) -> str:
        if not (clip_extent or clip_shapefile):
            return output_band_path

        clipped_path = self._safe_join(output_dir, f'{band_name}_clipped.tif')
        clip_raster(
            output_band_path,
            clipped_path,
            extent=clip_extent,
            shapefile=clip_shapefile,
        )
        return clipped_path

    def _process_single_band(
        self,
        band_info: Tuple[str, str],
        output_dir: str,
        cloud_mask: Optional[np.ndarray],
        clip_extent: Optional[List[float]],
        clip_shapefile: Optional[str],
        atm_correction_method: str,
    ) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        band_name, band_path = band_info

        try:
            if band_name not in SUPPORTED_OPTICAL_BANDS:
                logger.warning("波段 %s 不在标准处理列表中，将尝试处理", band_name)

            reflectance, actual_method = self.process_band(
                band_path,
                band_name,
                apply_atm_correction=True,
                atm_correction_method=atm_correction_method,
            )
            reflectance = self._apply_cloud_mask_to_reflectance(reflectance, cloud_mask, band_name)
            self._log_reflectance_quality(band_name, reflectance)

            output_band_path = self._safe_join(output_dir, f'{band_name}_processed.tif')
            self._write_processed_band(output_band_path, band_path, reflectance)
            final_path = self._clip_output_if_needed(
                output_band_path,
                output_dir,
                band_name,
                clip_extent,
                clip_shapefile,
            )
            return band_name, final_path, actual_method, None
        except Exception as exc:
            return band_name, None, None, str(exc)

    def _process_bands_parallel(
        self,
        bands_to_process: List[Tuple[str, str]],
        output_dir: str,
        cloud_mask: Optional[np.ndarray],
        clip_extent: Optional[List[float]],
        clip_shapefile: Optional[str],
        atm_correction_method: str,
        report: Callable,
    ) -> Tuple[Dict[str, str], Dict[str, str], int]:
        processed_count = 0
        total_bands = max(len(bands_to_process), 1)
        progress_lock = threading.Lock()
        band_results: Dict[str, str] = {}
        band_correction_methods: Dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as executor:
            future_to_band = {
                executor.submit(
                    self._process_single_band,
                    band_info,
                    output_dir,
                    cloud_mask,
                    clip_extent,
                    clip_shapefile,
                    atm_correction_method,
                ): band_info[0]
                for band_info in bands_to_process
            }

            for future in as_completed(future_to_band):
                band_name = future_to_band[future]
                try:
                    band_name, output_path, actual_method, error = future.result()
                except Exception as exc:
                    logger.error("波段 %s 处理异常: %s", band_name, str(exc))
                    continue

                if error:
                    logger.error("波段 %s 处理失败: %s", band_name, error)
                    continue

                band_results[band_name] = output_path
                band_correction_methods[band_name] = actual_method

                with progress_lock:
                    processed_count += 1
                    band_progress = 50 + int(30 * processed_count / total_bands)

                report(
                    'bands',
                    f"已处理波段 {band_name} ({processed_count}/{len(bands_to_process)})",
                    progress=band_progress,
                    status='active',
                )

        return band_results, band_correction_methods, processed_count

    @staticmethod
    def _summarize_correction_methods(
        band_correction_methods: Dict[str, str],
        processed_count: int,
        skipped_bands: List[str],
    ) -> Optional[str]:
        if not band_correction_methods:
            return None

        method_counts: Dict[str, int] = {}
        for method in band_correction_methods.values():
            method_counts[method] = method_counts.get(method, 0) + 1

        main_method = max(method_counts, key=method_counts.get)
        if len(method_counts) > 1:
            main_method = f"{main_method}(混合)"

        logger.info("波段处理完成")
        logger.info("处理统计:")
        logger.info("  - 成功处理: %d 个波段", processed_count)
        if skipped_bands:
            logger.info("  - 跳过: %d 个波段 (%s)", len(skipped_bands), ', '.join(skipped_bands))
        logger.info("大气校正方法汇总:")
        for method, count in method_counts.items():
            logger.info("  - %s: %d 个波段", method, count)
        logger.info("主要校正方法: %s", main_method)

        return main_method

    def _resolve_custom_index_key(self, composites: Dict[str, str], custom_index_name: Optional[str]) -> str:
        custom_key = self._sanitize_index_name(custom_index_name)
        base_key = custom_key
        counter = 1
        while custom_key in composites or custom_key in COMPOSITE_MAP:
            custom_key = f"{base_key}_{counter}"
            counter += 1
        return custom_key

    def _create_requested_composites(
        self,
        processed_bands: Dict[str, str],
        output_dir: str,
        create_composites: Optional[List[str]],
        custom_index_formula: Optional[str],
        custom_index_name: Optional[str],
    ) -> Dict[str, str]:
        composites: Dict[str, str] = {}

        for composite_type in create_composites or []:
            composite_path = self._safe_join(output_dir, f'{composite_type}.tif')
            create_composite(
                processed_bands,
                composite_path,
                composite_type=composite_type,
            )
            composites[composite_type] = composite_path

        if custom_index_formula and custom_index_formula.strip():
            custom_key = self._resolve_custom_index_key(composites, custom_index_name)
            custom_path = self._safe_join(output_dir, f'{custom_key}.tif')
            create_custom_index(processed_bands, custom_path, custom_index_formula.strip())
            composites[custom_key] = custom_path

        return composites

    def process_band(self, band_path: str, band_name: str,
                    apply_atm_correction: bool = True,
                    atm_correction_method: str = 'DOS') -> Tuple[np.ndarray, str]:
        """
        处理单个波段: DN -> 辐射亮度 -> 反射率 -> 大气校正

        Args:
            band_path: 波段文件路径
            band_name: 波段名称
            apply_atm_correction: 是否应用大气校正
            atm_correction_method: 大气校正方法 ('DOS' 或 '6S')

        Returns:
            (处理后的反射率数组, 实际使用的校正方法)
        """
        dn = self._load_band_array(band_path)
        reflectance = self._compute_toa_reflectance(dn, band_name)
        return self._apply_atmospheric_correction(
            reflectance,
            band_name,
            apply_atm_correction,
            atm_correction_method,
        )

    def one_click_preprocess(self,
                            band_paths: Dict[str, str],
                            output_dir: str,
                            mtl_path: str = None,
                            clip_extent: List[float] = None,
                            clip_shapefile: str = None,
                            create_composites: List[str] = None,
                            apply_cloud_mask: bool = False,
                            qa_band_path: str = None,
                            atm_correction_method: str = 'DOS',
                            custom_index_formula: Optional[str] = None,
                            custom_index_name: Optional[str] = None,
                            progress_callback: Optional[Callable[[Dict], None]] = None) -> Dict:
        """
        一键预处理主函数

        Args:
            band_paths: 波段路径字典
            output_dir: 输出目录
            mtl_path: MTL元数据文件路径
            clip_extent: 裁剪范围 [xmin, ymin, xmax, ymax]
            clip_shapefile: 裁剪矢量文件路径
            create_composites: 要创建的合成影像类型列表
            apply_cloud_mask: 是否应用云掩膜
            qa_band_path: QA波段文件路径
            atm_correction_method: 大气校正方法 ('DOS' 或 '6S')
            custom_index_formula: 自定义指数公式
            custom_index_name: 自定义指数名称
            progress_callback: 进度回调函数

        Returns:
            处理结果字典
        """
        report = self._build_reporter(progress_callback)
        results = self._init_results()

        try:
            os.makedirs(output_dir, exist_ok=True)
            report('prepare_output', '•', progress=15, status='completed')

            self._load_metadata_for_preprocess(mtl_path, results, report)
            cloud_mask, cloud_mask_path = self._prepare_cloud_mask(
                band_paths,
                output_dir,
                apply_cloud_mask,
                qa_band_path,
                report,
            )
            results['cloud_mask'] = cloud_mask_path

            report('bands', '开始处理波段', progress=50, status='active')
            logger.info("开始处理 %d 个波段", len(band_paths))
            logger.info("请求的大气校正方法: %s", atm_correction_method)
            logger.info("支持的光学波段: %s", ', '.join(SUPPORTED_OPTICAL_BANDS))
            logger.info("并行工作线程数: %d", settings.MAX_WORKERS)

            bands_to_process, skipped_bands = self._filter_bands_to_process(band_paths)
            band_results, band_correction_methods, processed_count = self._process_bands_parallel(
                bands_to_process,
                output_dir,
                cloud_mask,
                clip_extent,
                clip_shapefile,
                atm_correction_method,
                report,
            )
            results['processed_bands'] = band_results
            results['atm_correction_method'] = self._summarize_correction_methods(
                band_correction_methods,
                processed_count,
                skipped_bands,
            )

            if skipped_bands:
                results['skipped_bands'] = skipped_bands

            if clip_extent or clip_shapefile:
                report('clip', '影像裁剪完成', progress=82, status='completed')
            else:
                report('clip', '无裁剪任务，跳过', progress=80, status='completed')

            if create_composites or (custom_index_formula and custom_index_formula.strip()):
                report('composite', '正在生成合成影像', progress=88, status='active')
                results['composites'] = self._create_requested_composites(
                    results['processed_bands'],
                    output_dir,
                    create_composites,
                    custom_index_formula,
                    custom_index_name,
                )
                report('composite', '合成影像生成完成', progress=96, status='completed')
            else:
                report('composite', '未选择合成影像，跳过', progress=90, status='completed')

            report('finalize', '处理完成，结果已写入输出目录', progress=100, status='completed')
            return results

        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
            report('finalize', f"处理失败: {str(e)}", progress=100, status='exception')
            return results

    def build_preview_base64(self, raster_path: str, max_size: int = 512) -> Dict:
        """
        生成栅格的预览图（base64 PNG）

        Args:
            raster_path: 栅格文件路径
            max_size: 最大预览尺寸（像素）

        Returns:
            包含base64编码PNG、宽度、高度和波段数的字典
        """
        if not os.path.exists(raster_path):
            raise Exception(f"文件不存在: {raster_path}")

        ds = gdal.Open(raster_path)
        if ds is None:
            raise Exception(f"无法打开文件: {raster_path}")

        width, height, bands = ds.RasterXSize, ds.RasterYSize, ds.RasterCount
        source_ds = ds

        # 限制预览尺寸，避免前端过大
        if max(width, height) > max_size:
            scale = max_size / max(width, height)
            target_x = max(1, int(width * scale))
            target_y = max(1, int(height * scale))
            source_ds = gdal.Translate(
                '',
                ds,
                format='MEM',
                width=target_x,
                height=target_y,
                resampleAlg=gdal.GRA_Bilinear
            )

        alpha_band_index = None
        display_band_indexes = []
        for band_index in range(1, source_ds.RasterCount + 1):
            color_interp = source_ds.GetRasterBand(band_index).GetColorInterpretation()
            if color_interp == gdal.GCI_AlphaBand:
                alpha_band_index = band_index
                continue
            display_band_indexes.append(band_index)

        if not display_band_indexes:
            display_band_indexes = [1]

        display_band_indexes = display_band_indexes[:3]
        valid_mask = None
        if alpha_band_index is not None:
            alpha_mask = source_ds.GetRasterBand(alpha_band_index).ReadAsArray() > 0
            valid_mask = alpha_mask

        scaled_bands = []
        for band_index in display_band_indexes:
            raster_band = source_ds.GetRasterBand(band_index)
            band = raster_band.ReadAsArray().astype(np.float32)
            band_valid_mask = np.isfinite(band)

            nodata = raster_band.GetNoDataValue()
            if nodata is not None:
                band_valid_mask &= band != nodata

            mask_band = raster_band.GetMaskBand()
            if mask_band is not None:
                band_valid_mask &= mask_band.ReadAsArray() != 0

            if valid_mask is None:
                valid_mask = band_valid_mask
            else:
                valid_mask &= band_valid_mask

            valid = band[band_valid_mask]
            if valid.size == 0:
                scaled = np.zeros_like(band, dtype=np.uint8)
            else:
                p2 = np.percentile(valid, 2)
                p98 = np.percentile(valid, 98)
                if p98 > p2:
                    norm = (band - p2) / (p98 - p2)
                else:
                    norm = band - p2
                norm = np.clip(norm, 0, 1)
                scaled = (norm * 255).astype(np.uint8)
                scaled[~band_valid_mask] = 0
            scaled_bands.append(scaled)

        band_count = len(scaled_bands)

        if band_count == 1:
            scaled_bands = [scaled_bands[0], scaled_bands[0], scaled_bands[0]]
            band_count = 3

        include_alpha = valid_mask is not None and not np.all(valid_mask)
        output_band_count = 4 if include_alpha else band_count

        mem_drv = gdal.GetDriverByName('MEM')
        out_ds = mem_drv.Create(
            '',
            scaled_bands[0].shape[1],
            scaled_bands[0].shape[0],
            output_band_count,
            gdal.GDT_Byte
        )

        for idx in range(band_count):
            out_band = out_ds.GetRasterBand(idx + 1)
            out_band.WriteArray(scaled_bands[idx])
            out_band.SetColorInterpretation(
                [gdal.GCI_RedBand, gdal.GCI_GreenBand, gdal.GCI_BlueBand][idx]
            )

        if include_alpha:
            alpha_band = out_ds.GetRasterBand(4)
            alpha_band.WriteArray(np.where(valid_mask, 255, 0).astype(np.uint8))
            alpha_band.SetColorInterpretation(gdal.GCI_AlphaBand)

        png_path = '/vsimem/preview.png'
        gdal.Translate(png_path, out_ds, format='PNG')

        f = gdal.VSIFOpenL(png_path, 'rb')
        gdal.VSIFSeekL(f, 0, 2)
        size = gdal.VSIFTellL(f)
        gdal.VSIFSeekL(f, 0, 0)
        data = gdal.VSIFReadL(1, size, f)
        gdal.VSIFCloseL(f)
        gdal.Unlink(png_path)

        if source_ds is not ds:
            source_ds = None
        ds = None
        out_ds = None

        return {
            'base64': base64.b64encode(data).decode('utf-8'),
            'width': int(width),
            'height': int(height),
            'bands': int(bands)
        }
