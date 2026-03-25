"""大气校正操作模块 - 重构版本

提供两种大气校正方法：
1. 6S (Second Simulation of Satellite Signal in the Solar Spectrum) - 基于物理的辐射传输模型
2. DOS (Dark Object Subtraction) - 基于经验的暗目标扣除法
"""

import numpy as np
from osgeo import gdal
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
import logging


logger = logging.getLogger(__name__)


# ============================================================================
# Py6S 库导入 (可选依赖)
# ============================================================================

try:
    from Py6S import (
        SixS, Wavelength, AtmosProfile, AeroProfile,
        Geometry, GroundReflectance
    )
    PY6S_AVAILABLE = True
except ImportError as e:
    PY6S_AVAILABLE = False
    # 创建占位符类型以避免类型注解错误
    SixS = type(None)
    Wavelength = type(None)
    AtmosProfile = type(None)
    AeroProfile = type(None)
    Geometry = type(None)
    GroundReflectance = type(None)
    logger.warning("Py6S库导入失败，6S大气校正功能将不可用: %s", e)
    logger.warning("可使用 conda install -c conda-forge py6s 安装")
except Exception as e:
    PY6S_AVAILABLE = False
    # 创建占位符类型以避免类型注解错误
    SixS = type(None)
    Wavelength = type(None)
    AtmosProfile = type(None)
    AeroProfile = type(None)
    Geometry = type(None)
    GroundReflectance = type(None)
    logger.warning("Py6S库加载异常，6S功能将不可用: %s", e)


# ============================================================================
# 数据类定义
# ============================================================================

@dataclass
class SixSCoefficients:
    """6S大气校正系数"""
    xa: float  # 透过率项 (斜率)
    xb: float  # 大气贡献 (截距)
    xc: Optional[float] = None  # 耦合项 (可选)
    method: str = "calculated"  # 获取方法: "direct" 或 "calculated"

    def apply_correction(self, toa_reflectance: np.ndarray) -> np.ndarray:
        """
        应用大气校正到TOA反射率

        Args:
            toa_reflectance: 大气顶层反射率数组

        Returns:
            地表反射率数组
        """
        if self.xc is not None:
            # 三系数模型（非线性）
            denom = self.xa + self.xc * toa_reflectance
            denom = np.where(np.abs(denom) < 1e-10, 1e-10, denom)
            surface_reflectance = (toa_reflectance - self.xb) / denom
        else:
            # 二系数线性模型
            xa = self.xa if abs(self.xa) > 1e-10 else 1e-10
            surface_reflectance = (toa_reflectance - self.xb) / xa

        # 限制到物理有效范围 [0, 1]
        return np.clip(surface_reflectance, 0, 1)


@dataclass
class SixSConfig:
    """6S模型配置参数"""
    # 必需参数（无默认值，必须放在前面）
    sun_zenith: float           # 太阳天顶角（度）
    sun_azimuth: float          # 太阳方位角（度）
    wavelength_center: float    # 波段中心波长（μm）
    wavelength_fwhm: float      # 波段半宽度（μm）

    # 可选几何参数
    view_zenith: float = 0.0    # 观测天顶角（度），默认星下点
    view_azimuth: float = 0.0   # 观测方位角（度）

    # 可选大气参数
    atmospheric_profile: int = 2            # 大气模型：1-6
    aerosol_profile: int = 1                # 气溶胶模型：0-6
    visibility: Optional[float] = 40.0      # 能见度（km）
    aot550: Optional[float] = None          # 550nm气溶胶光学厚度

    # 可选地表参数
    altitude: float = 0.0                   # 目标高度（km）

    # 可选时间参数
    date: Optional[str] = None              # 观测日期 YYYY-MM-DD

    def get_wavelength_range(self) -> Tuple[float, float]:
        """计算波段范围（6S需要min-max格式）"""
        wl_min = self.wavelength_center - self.wavelength_fwhm / 2.0
        wl_max = self.wavelength_center + self.wavelength_fwhm / 2.0

        # 确保在6S支持范围内 (0.2 - 4.0 μm)
        wl_min = max(0.2, wl_min)
        wl_max = min(4.0, wl_max)

        return wl_min, wl_max


# ============================================================================
# 6S 大气校正核心类
# ============================================================================

class SixSAtmosphericCorrector:
    """6S大气校正处理器"""

    # 大气模型名称映射
    ATMOS_NAMES = {
        1: "Tropical(热带)",
        2: "Midlatitude Summer(中纬度夏季)",
        3: "Midlatitude Winter(中纬度冬季)",
        4: "Subarctic Summer(亚北极夏季)",
        5: "Subarctic Winter(亚北极冬季)",
        6: "US Standard(美国标准大气)"
    }

    # 气溶胶模型名称映射
    AERO_NAMES = {
        0: "No Aerosols(无气溶胶)",
        1: "Continental(大陆型)",
        2: "Maritime(海洋型)",
        3: "Urban(城市型)",
        4: "Desert(沙漠型)",
        5: "Biomass Burning(生物质燃烧)",
        6: "Stratospheric(平流层)"
    }

    def __init__(self, config: SixSConfig, verbose: bool = True):
        """
        初始化6S校正器

        Args:
            config: 6S配置参数
            verbose: 是否输出详细日志
        """
        if not PY6S_AVAILABLE:
            raise ImportError(
                "Py6S库未安装，无法使用6S大气校正。\n"
                "安装方法: conda install -c conda-forge py6s"
            )

        self.config = config
        self.verbose = verbose
        self._sixs_model = None
        self._coefficients = None

    def _setup_sixs_model(self) -> SixS:
        """配置6S模型"""
        s = SixS()

        # 1. 几何配置
        s.geometry = Geometry.User()
        s.geometry.solar_z = self.config.sun_zenith
        s.geometry.solar_a = self.config.sun_azimuth
        s.geometry.view_z = self.config.view_zenith
        s.geometry.view_a = self.config.view_azimuth

        # 2. 日期配置（可选）
        if self.config.date:
            try:
                year, month, day = map(int, self.config.date.split('-'))
                s.geometry.month = month
                s.geometry.day = day
            except ValueError:
                if self.verbose:
                    logger.warning("日期格式错误: %s, 已忽略", self.config.date)

        # 3. 大气模型
        atmos_map = {
            1: AtmosProfile.Tropical,
            2: AtmosProfile.MidlatitudeSummer,
            3: AtmosProfile.MidlatitudeWinter,
            4: AtmosProfile.SubarcticSummer,
            5: AtmosProfile.SubarcticWinter,
            6: AtmosProfile.USStandard1962
        }
        atmos_type = atmos_map.get(self.config.atmospheric_profile, AtmosProfile.MidlatitudeSummer)
        s.atmos_profile = AtmosProfile.PredefinedType(atmos_type)

        # 4. 气溶胶模型
        aero_map = {
            0: AeroProfile.NoAerosols,
            1: AeroProfile.Continental,
            2: AeroProfile.Maritime,
            3: AeroProfile.Urban,
            4: AeroProfile.Desert,
            5: AeroProfile.BiomassBurning,
            6: AeroProfile.Stratospheric
        }
        aero_type = aero_map.get(self.config.aerosol_profile, AeroProfile.Continental)
        s.aero_profile = AeroProfile.PredefinedType(aero_type)

        # 5. 能见度或AOT
        if self.config.aot550 is not None:
            s.aot550 = self.config.aot550
        elif self.config.visibility is not None:
            s.visibility = self.config.visibility
        else:
            s.visibility = 40.0  # 默认清洁大气

        # 6. 高度
        s.altitudes.set_target_custom_altitude(self.config.altitude)
        s.altitudes.set_sensor_satellite_level()

        # 7. 波段
        wl_min, wl_max = self.config.get_wavelength_range()
        s.wavelength = Wavelength(wl_min, wl_max)

        # 8. 地表反射率（用于系数计算）
        # 设置为0.5的朗伯体，用于反算大气校正系数
        s.ground_reflectance = GroundReflectance.HomogeneousLambertian(0.5)

        return s

    def _log_config(self):
        """输出配置信息"""
        if not self.verbose:
            return

        wl_min, wl_max = self.config.get_wavelength_range()

        logger.info("6S模型配置:")
        logger.info("  几何参数:")
        logger.info("    - 太阳天顶角: %.2f°", self.config.sun_zenith)
        logger.info("    - 太阳方位角: %.2f°", self.config.sun_azimuth)
        logger.info("    - 观测天顶角: %.2f°", self.config.view_zenith)
        logger.info("  波段参数:")
        logger.info("    - 中心波长: %.3f μm", self.config.wavelength_center)
        logger.info("    - 半宽度: %.3f μm", self.config.wavelength_fwhm)
        logger.info("    - 范围: %.3f - %.3f μm", wl_min, wl_max)
        logger.info("  大气参数:")
        logger.info("    - 大气模型: %s", self.ATMOS_NAMES.get(self.config.atmospheric_profile, '未知'))
        logger.info("    - 气溶胶: %s", self.AERO_NAMES.get(self.config.aerosol_profile, '未知'))

        if self.config.aot550 is not None:
            logger.info("    - AOT550: %s", self.config.aot550)
        elif self.config.visibility is not None:
            logger.info("    - 能见度: %s km", self.config.visibility)

    def _extract_coefficients(self, sixs_model: SixS) -> SixSCoefficients:
        """
        从6S输出提取大气校正系数

        策略:
        1. 尝试直接访问 coef_xa/coef_xb (某些Py6S版本提供)
        2. 如果失败，从基础输出参数计算

        Args:
            sixs_model: 已运行的6S模型实例

        Returns:
            大气校正系数对象
        """
        # 方法1: 直接访问系数（首选）
        try:
            xa = sixs_model.outputs.coef_xa
            xb = sixs_model.outputs.coef_xb
            xc = None
            try:
                xc = sixs_model.outputs.coef_xc
            except AttributeError:
                pass

            if self.verbose:
                logger.info("系数获取: 直接访问")

            return SixSCoefficients(xa=xa, xb=xb, xc=xc, method="direct")

        except Exception:
            pass

        # 方法2: 从基础输出计算（回退方案）
        try:
            # xb = 大气本征反射率（大气散射贡献）
            xb = sixs_model.outputs.atmospheric_intrinsic_reflectance

            # 表观反射率（6S模拟的卫星观测值）
            rho_apparent = sixs_model.outputs.apparent_reflectance

            # 已知地表反射率（我们设置的0.5）
            rho_surface_known = 0.5

            # 反算xa: ρ_apparent = xa * ρ_surface + xb
            xa = (rho_apparent - xb) / rho_surface_known

            if self.verbose:
                logger.info("系数获取: 计算方法")
                logger.debug("  - 表观反射率: %.6f", rho_apparent)
                logger.debug("  - 大气本征反射率: %.6f", xb)
                logger.debug("  - 计算得xa: %.6f", xa)

            return SixSCoefficients(xa=xa, xb=xb, xc=None, method="calculated")

        except Exception as e:
            raise RuntimeError(
                f"无法从6S输出提取大气校正系数。\n"
                f"错误: {str(e)}\n"
                f"请检查Py6S版本和安装。"
            )

    def compute_coefficients(self) -> SixSCoefficients:
        """
        运行6S模型并计算大气校正系数

        Returns:
            大气校正系数
        """
        if self._coefficients is not None:
            return self._coefficients

        if self.verbose:
            logger.info("初始化6S模型...")
            self._log_config()

        # 配置6S
        self._sixs_model = self._setup_sixs_model()

        # 运行6S
        if self.verbose:
            logger.info("运行6S辐射传输模拟...")

        try:
            self._sixs_model.run()
            if self.verbose:
                logger.info("6S模型运行成功")
        except Exception as e:
            raise RuntimeError(
                f"6S模型运行失败: {str(e)}\n"
                f"请确保6S可执行文件已正确安装。\n"
                f"参考: https://py6s.readthedocs.io/en/latest/installation.html"
            )

        # 提取系数
        self._coefficients = self._extract_coefficients(self._sixs_model)

        if self.verbose:
            logger.info("大气校正系数:")
            logger.debug("  - xa (透过率): %.6f", self._coefficients.xa)
            logger.debug("  - xb (大气贡献): %.6f", self._coefficients.xb)
            if self._coefficients.xc is not None:
                logger.debug("  - xc (耦合项): %.6f", self._coefficients.xc)

        return self._coefficients

    def correct(self, toa_reflectance: np.ndarray) -> np.ndarray:
        """
        对TOA反射率进行大气校正

        Args:
            toa_reflectance: 大气顶层反射率数组

        Returns:
            地表反射率数组
        """
        # 确保已计算系数
        if self._coefficients is None:
            self.compute_coefficients()

        # 应用校正
        surface_reflectance = self._coefficients.apply_correction(toa_reflectance)

        if self.verbose:
            valid_pixels = np.sum(~np.isnan(surface_reflectance))
            mean_toa = np.nanmean(toa_reflectance)
            mean_surface = np.nanmean(surface_reflectance)
            logger.info("大气校正完成:")
            logger.debug("  - 有效像元: %s", f"{valid_pixels:,}")
            logger.debug("  - TOA反射率均值: %.4f", mean_toa)
            logger.debug("  - 地表反射率均值: %.4f", mean_surface)

        return surface_reflectance


# ============================================================================
# 便捷函数（保持API兼容性）
# ============================================================================

def sixs_atmospheric_correction(
    reflectance: np.ndarray,
    band_name: str,
    sun_zenith: float,
    sun_azimuth: float,
    view_zenith: float = 0.0,
    view_azimuth: float = 0.0,
    date: Optional[str] = None,
    wavelengths: Optional[Dict] = None,
    atmospheric_profile: int = 2,
    aerosol_profile: int = 1,
    visibility: Optional[float] = None,
    aot550: Optional[float] = None,
    altitude: float = 0.0
) -> np.ndarray:
    """
    使用6S模型进行大气校正（便捷函数）

    这是一个兼容旧API的包装函数，内部使用重构后的SixSAtmosphericCorrector。

    Args:
        reflectance: TOA反射率数组
        band_name: 波段名称 (如 'B1', 'B2', ...)
        sun_zenith: 太阳天顶角 (度)
        sun_azimuth: 太阳方位角 (度)
        view_zenith: 观测天顶角 (度), 默认0(星下点)
        view_azimuth: 观测方位角 (度), 默认0
        date: 观测日期 (YYYY-MM-DD格式), 可选
        wavelengths: 波段波长字典,包含center和fwhm
        atmospheric_profile: 大气模型 (1-6)
        aerosol_profile: 气溶胶模型 (0-6)
        visibility: 能见度(km), 如果为None则使用AOT
        aot550: 550nm气溶胶光学厚度
        altitude: 目标高度(km)

    Returns:
        大气校正后的地表反射率数组
    """
    # 检查波段波长信息
    if wavelengths is None or band_name not in wavelengths:
        raise ValueError(f"未提供波段 {band_name} 的波长信息")

    wl_info = wavelengths[band_name]

    # 创建配置
    config = SixSConfig(
        sun_zenith=sun_zenith,
        sun_azimuth=sun_azimuth,
        view_zenith=view_zenith,
        view_azimuth=view_azimuth,
        wavelength_center=wl_info['center'],
        wavelength_fwhm=wl_info['fwhm'],
        atmospheric_profile=atmospheric_profile,
        aerosol_profile=aerosol_profile,
        visibility=visibility,
        aot550=aot550,
        altitude=altitude,
        date=date
    )

    # 创建校正器并执行
    logger.info("波段 %s: 6S大气校正", band_name)
    corrector = SixSAtmosphericCorrector(config, verbose=True)
    return corrector.correct(reflectance)


def dark_object_subtraction(
    reflectance: np.ndarray,
    percentile: float = 1.0
) -> np.ndarray:
    """
    暗目标法大气校正 (DOS)

    基于假设：最暗的像元应该接近零反射率，任何非零值都是大气散射造成的。

    Args:
        reflectance: 反射率数组
        percentile: 用于确定暗目标的百分位数 (0-100)

    Returns:
        大气校正后的反射率
    """
    # 获取大于0的反射率值
    positive_reflectance = reflectance[reflectance > 0]

    # 检查是否有有效值
    if len(positive_reflectance) == 0:
        return np.clip(reflectance, 0, 1)

    # 计算暗目标值（第percentile百分位）
    dark_value = np.percentile(positive_reflectance, percentile)

    # 减去暗目标值
    corrected = reflectance - dark_value

    # 限制到物理有效范围 [0, 1] - 保持这个限制，因为反射率应该在0-1之间
    # 注意：这个限制不会影响NDVI计算，因为NDVI会在自己的函数中处理
    corrected = np.clip(corrected, 0, 1)

    return corrected


def cloud_mask_from_qa(
    qa_band_path: str,
    confidence_threshold: str = 'medium'
) -> np.ndarray:
    """
    从Landsat 8 QA波段提取云掩膜

    Args:
        qa_band_path: QA波段文件路径
        confidence_threshold: 云置信度阈值
            - 'low': 低置信度及以上
            - 'medium': 中等置信度及以上（默认）
            - 'high': 仅高置信度

    Returns:
        云掩膜数组 (0=无云, 1=有云)
    """
    dataset = gdal.Open(qa_band_path)
    if dataset is None:
        raise FileNotFoundError(f"无法打开QA波段: {qa_band_path}")

    qa = dataset.ReadAsArray()
    dataset = None

    if qa.size == 0:
        raise ValueError(f"QA波段文件为空: {qa_band_path}")

    # Landsat 8 QA位定义
    # Bit 4: Cloud (1=Yes, 0=No)
    # Bits 5-6: Cloud Confidence (00=Not Determined, 01=Low, 10=Medium, 11=High)

    cloud_bit = 4
    cloud_confidence_bits = [5, 6]

    # 提取云标记
    cloud = np.bitwise_and(qa, 1 << cloud_bit) > 0

    # 提取云置信度
    conf_value = (
        (np.bitwise_and(qa, 1 << cloud_confidence_bits[0]) > 0).astype(int) +
        (np.bitwise_and(qa, 1 << cloud_confidence_bits[1]) > 0).astype(int) * 2
    )

    # 根据置信度阈值创建掩膜
    threshold_map = {'low': 1, 'medium': 2, 'high': 3}
    threshold = threshold_map.get(confidence_threshold, 2)

    cloud_mask = np.logical_or(cloud, conf_value >= threshold).astype(np.uint8)

    return cloud_mask
