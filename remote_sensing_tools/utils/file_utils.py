"""
文件操作工具
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from ..utils.logger import logger


_BAND_RE = re.compile(r"(?:^|[_\-])B(1[0-1]|[1-9])(?:[_\-.]|$)", re.IGNORECASE)
_RASTER_SUFFIXES = {".tif", ".tiff", ".img"}


def _detect_band_name(filename: str) -> Optional[str]:
    """从文件名中解析 Landsat 波段名称 (B1-B11)。"""
    match = _BAND_RE.search(filename)
    if not match:
        return None
    return f"B{int(match.group(1))}"


def collect_band_paths(band_dir, on_duplicate: str = "warn") -> Dict[str, str]:
    """收集目录中的 Landsat 波段文件路径。

    Args:
        band_dir: 波段文件目录 (str 或 Path)。
        on_duplicate: 遇到重复波段时的行为:
            ``"raise"`` — 抛出 ValueError；
            ``"warn"``  — 记录警告并保留先匹配项 (默认)。

    Returns:
        ``{band_name: file_path}`` 映射，如 ``{'B1': '/path/to/B1.tif', ...}``。

    Raises:
        ValueError: 目录不存在、非目录、或未找到任何波段文件时。
    """
    band_dir = Path(band_dir)
    if not band_dir.exists():
        raise ValueError(f"波段目录不存在: {band_dir}")
    if not band_dir.is_dir():
        raise ValueError(f"不是目录: {band_dir}")

    band_paths: Dict[str, str] = {}
    for file_path in sorted(band_dir.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in _RASTER_SUFFIXES:
            continue

        band_name = _detect_band_name(file_path.name)
        if not band_name:
            continue

        if band_name in band_paths:
            if on_duplicate == "raise":
                raise ValueError(
                    f"波段重复: {band_name} ({band_paths[band_name]} 与 {file_path})"
                )
            logger.warning("发现重复波段文件，保留先匹配项: %s", band_name)
            continue

        band_paths[band_name] = str(file_path)

    if not band_paths:
        raise ValueError("未在目录中识别到 B1-B11 波段文件")

    return band_paths


def ensure_dir(path: Path) -> Path:
    """
    确保目录存在

    Args:
        path: 目录路径

    Returns:
        目录路径
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_remove(path: Path) -> bool:
    """
    安全删除文件或目录

    Args:
        path: 文件或目录路径

    Returns:
        是否成功删除
    """
    try:
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        logger.debug(f"删除: {path}")
        return True
    except Exception as e:
        logger.warning(f"删除失败: {path} - {str(e)}")
        return False


def get_file_size(path: Path) -> int:
    """
    获取文件大小（字节）

    Args:
        path: 文件路径

    Returns:
        文件大小
    """
    return path.stat().st_size if path.exists() else 0


def format_size(size_bytes: int) -> str:
    """
    格式化文件大小

    Args:
        size_bytes: 字节数

    Returns:
        格式化的大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def list_files(directory: Path, pattern: str = "*", recursive: bool = False) -> List[Path]:
    """
    列出目录中的文件

    Args:
        directory: 目录路径
        pattern: 文件模式
        recursive: 是否递归搜索

    Returns:
        文件路径列表
    """
    if recursive:
        return list(directory.rglob(pattern))
    else:
        return list(directory.glob(pattern))


def clean_temp_files(directory: Path, older_than_days: int = 7):
    """
    清理临时文件

    Args:
        directory: 目录路径
        older_than_days: 删除多少天前的文件
    """
    import time
    current_time = time.time()
    cutoff_time = current_time - (older_than_days * 86400)

    cleaned_count = 0
    cleaned_size = 0

    for file_path in directory.rglob("*"):
        if file_path.is_file():
            if file_path.stat().st_mtime < cutoff_time:
                size = get_file_size(file_path)
                if safe_remove(file_path):
                    cleaned_count += 1
                    cleaned_size += size

    if cleaned_count > 0:
        logger.info(f"清理了 {cleaned_count} 个临时文件，释放 {format_size(cleaned_size)}")
