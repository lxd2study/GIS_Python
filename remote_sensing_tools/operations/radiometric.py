"""辐射定标操作模块"""

import logging
import numpy as np
import math
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def calculate_earth_sun_distance(date_str: Optional[str] = None,
                                  doy: Optional[int] = None) -> float:
    """
    计算日地距离校正因子

    根据观测日期或儒略日计算地球-太阳距离的平方（AU²）
    用于TOA反射率计算中的太阳辐照度校正

    Args:
        date_str: 观测日期 (YYYY-MM-DD 格式), 可选
        doy: 一年中的第几天 (1-366), 可选

    Returns:
        日地距离平方 (天文单位的平方)

    Notes:
        - 如果两个参数都提供，优先使用doy
        - 如果都不提供，返回1.0（一年平均值）
        - 公式基于天文年历简化模型
    """
    # 如果都没提供，返回默认值
    if doy is None and date_str is None:
        return 1.0

    # 计算儒略日
    if doy is None:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            doy = date.timetuple().tm_yday
        except (ValueError, AttributeError):
            return 1.0

    # 使用天文年历公式计算日地距离
    # d = 1 - 0.01672 * cos(0.9856 * (DOY - 4))
    # 其中 0.01672 是地球轨道离心率
    # 0.9856 = 360/365.25 (度/天)
    # 4 是近日点偏移量

    theta = 0.9856 * (doy - 4) * math.pi / 180.0
    d = 1.0 - 0.01672 * math.cos(theta)

    # 返回距离的平方（用于反射率计算）
    return d * d


def dn_to_radiance(dn_array: np.ndarray, band_name: str,
                   radiance_mult: Dict, radiance_add: Dict) -> np.ndarray:
    """
    DN值转辐射亮度

    公式: L = ML * DN + AL
    其中: L-辐射亮度, ML-增益, AL-偏移, DN-像元值

    Args:
        dn_array: DN值数组
        band_name: 波段名称 (如 'B1', 'B2')
        radiance_mult: 辐射增益参数字典
        radiance_add: 辐射偏移参数字典

    Returns:
        辐射亮度数组
    """
    ml = radiance_mult.get(band_name, 0.00001)
    al = radiance_add.get(band_name, 0.1)

    radiance = ml * dn_array.astype(np.float32) + al

    # 确保辐射亮度为正值
    radiance = np.maximum(radiance, 0.0)

    return radiance


def radiance_to_reflectance(radiance: np.ndarray, band_name: str,
                           esun: Dict, sun_elevation: float = 45.0,
                           earth_sun_distance: float = None,
                           date_acquired: str = None) -> np.ndarray:
    """
    辐射亮度转地表反射率 (TOA反射率)

    公式: ρ = (π * L * d²) / (ESUN * sin(θ))
    其中: ρ-反射率, L-辐射亮度, d-日地距离, ESUN-太阳辐照度, θ-太阳高度角

    Args:
        radiance: 辐射亮度数组
        band_name: 波段名称
        esun: 太阳辐照度参数字典
        sun_elevation: 太阳高度角(度)
        earth_sun_distance: 日地距离平方（优先使用此参数，可从MTL的EARTH_SUN_DISTANCE读取）
        date_acquired: 观测日期 (YYYY-MM-DD格式), 用于计算日地距离

    Returns:
        反射率数组 (0-1范围)
    """
    # 日地距离校正因子
    # 优先级: 1) 直接提供的距离平方 2) 根据日期计算 3) 使用默认值1.0
    if earth_sun_distance is None:
        if date_acquired is not None:
            d_squared = calculate_earth_sun_distance(date_str=date_acquired)
            logger.info("根据观测日期 %s 计算日地距离平方: %.6f", date_acquired, d_squared)
        else:
            d_squared = 1.0
            logger.warning("未提供日期信息，使用默认日地距离平方: %s", d_squared)
    else:
        # 如果提供的是距离而不是距离平方，需要平方
        # MTL中的EARTH_SUN_DISTANCE已经是距离值
        d_squared = earth_sun_distance * earth_sun_distance
        logger.debug("使用MTL提供的日地距离，距离平方: %.6f", d_squared)

    # 太阳辐照度
    esun_value = esun.get(band_name, 1500.0)

    # 太阳高度角转弧度
    sun_elevation_rad = np.deg2rad(sun_elevation)

    # 计算反射率
    reflectance = (np.pi * radiance * d_squared) / (esun_value * np.sin(sun_elevation_rad))

    # 限制在合理范围，但允许小的负值用于后续处理
    reflectance = np.clip(reflectance, -0.1, 2.0)

    return reflectance


def radiance_to_brightness_temperature(radiance: np.ndarray,
                                       band_name: str,
                                       thermal_constants: Dict = None) -> np.ndarray:
    """
    热红外波段：辐射亮度转亮温 (Brightness Temperature)

    适用于 Landsat 8 TIRS 热红外波段 (B10, B11)

    公式: BT = K2 / ln(K1/L + 1) - 273.15
    其中: BT-亮温(°C), L-辐射亮度, K1/K2-定标常数

    Args:
        radiance: 辐射亮度数组 (W/(m²·sr·μm))
        band_name: 波段名称 ('B10' 或 'B11')
        thermal_constants: 热红外定标常数字典，如果为None则使用默认值

    Returns:
        亮温数组（摄氏度）

    Raises:
        ValueError: 如果波段不是热红外波段

    References:
        Landsat 8 Data Users Handbook
        https://www.usgs.gov/landsat-missions/landsat-8-data-users-handbook
    """
    # 默认的 Landsat 8 TIRS 热红外定标常数
    if thermal_constants is None:
        thermal_constants = {
            'B10': {
                'K1': 774.8853,   # W/(m²·sr·μm)
                'K2': 1321.0789   # K (开尔文)
            },
            'B11': {
                'K1': 480.8883,   # W/(m²·sr·μm)
                'K2': 1201.1442   # K (开尔文)
            }
        }

    if band_name not in thermal_constants:
        raise ValueError(
            f"{band_name} 不是有效的热红外波段。"
            f"仅支持: {', '.join(thermal_constants.keys())}"
        )

    K1 = thermal_constants[band_name]['K1']
    K2 = thermal_constants[band_name]['K2']

    # 避免除零错误和对数运算错误
    # 将极小的辐射亮度值限制到一个最小值
    radiance = np.maximum(radiance, 0.01)

    # 计算亮温（开尔文）
    # BT(K) = K2 / ln(K1/L + 1)
    bt_kelvin = K2 / np.log((K1 / radiance) + 1.0)

    # 转为摄氏度
    bt_celsius = bt_kelvin - 273.15

    # 合理性检查：地表温度通常在 -100°C 到 +100°C 之间
    # 如果超出这个范围，可能是数据问题
    if np.nanmin(bt_celsius) < -100 or np.nanmax(bt_celsius) > 100:
        logger.warning("%s 亮温超出常见范围 [-100°C, 100°C]", band_name)
        logger.warning("  实际范围: [%.2f°C, %.2f°C]", np.nanmin(bt_celsius), np.nanmax(bt_celsius))
        logger.warning("  请检查输入数据的有效性")

    return bt_celsius
