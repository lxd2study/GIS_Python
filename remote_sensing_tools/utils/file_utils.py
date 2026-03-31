"""
文件操作工具
"""

import fnmatch
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from ..utils.logger import logger


_BAND_RE = re.compile(r"(?:^|[_\-])B(1[0-1]|[1-9])(?:[_\-.]|$)", re.IGNORECASE)
_RASTER_SUFFIXES = {".tif", ".tiff", ".img"}
_L2_FILE_HINTS = ("_SR_B", "_ST_B", "_L2", "L2SP", "SURFACE_REFLECTANCE")
_L1_FILE_HINTS = ("_L1", "L1TP", "L1GT", "L1GS", "BQA")


def _detect_band_name(filename: str) -> Optional[str]:
    """从文件名中解析 Landsat 波段名称 (B1-B11)。"""
    match = _BAND_RE.search(filename)
    if not match:
        return None
    return f"B{int(match.group(1))}"


def _normalize_product_level(product_level: Optional[str]) -> Optional[str]:
    if not product_level:
        return None
    normalized = str(product_level).upper()
    return normalized if normalized in {"L1", "L2"} else None


def detect_product_level_from_path(path: Path) -> Optional[str]:
    """根据文件路径推断产品级别。"""
    upper_path = str(path).upper()
    if any(token in upper_path for token in _L2_FILE_HINTS):
        return "L2"

    if any(token in upper_path for token in _L1_FILE_HINTS):
        return "L1"

    if _detect_band_name(path.name):
        return "L1"

    return None


def _iter_files(root: Path, recursive: bool = True):
    iterator = root.rglob("*") if recursive else root.iterdir()
    for path in iterator:
        if path.is_file():
            yield path


def _relative_sort_key(root: Path, file_path: Path):
    relative = file_path.relative_to(root)
    return (len(relative.parts), str(relative).upper())


def _preferred_candidates(candidates: List[Path], root: Path, product_level: Optional[str]) -> List[Path]:
    ordered = sorted(candidates, key=lambda item: _relative_sort_key(root, item))
    normalized_level = _normalize_product_level(product_level)
    if not normalized_level:
        return ordered

    matched = [path for path in ordered if detect_product_level_from_path(path) == normalized_level]
    if matched:
        return matched

    unknown = [path for path in ordered if detect_product_level_from_path(path) is None]
    if unknown:
        return unknown

    return []


def _find_matching_files(root: Path, patterns: List[str], recursive: bool = True) -> List[Path]:
    normalized_patterns = [pattern.upper() for pattern in patterns]
    matches: List[Path] = []
    for file_path in _iter_files(root, recursive=recursive):
        upper_name = file_path.name.upper()
        if any(fnmatch.fnmatch(upper_name, pattern) for pattern in normalized_patterns):
            matches.append(file_path)
    return sorted(matches, key=lambda item: _relative_sort_key(root, item))


def _choose_scene_file(
    root: Path,
    patterns: List[str],
    product_level: Optional[str] = None,
    recursive: bool = True,
    fallback_to_any: bool = True,
) -> Optional[str]:
    candidates = _find_matching_files(root, patterns, recursive=recursive)
    if not candidates:
        return None

    preferred = _preferred_candidates(candidates, root, product_level)
    if preferred:
        return str(preferred[0])

    return str(candidates[0]) if fallback_to_any else None


def infer_available_product_levels(scene_dir) -> List[str]:
    """扫描场景目录中可用的产品级别。"""
    scene_dir = Path(scene_dir)
    if not scene_dir.exists() or not scene_dir.is_dir():
        return []

    levels = set()
    for file_path in _iter_files(scene_dir, recursive=True):
        level = detect_product_level_from_path(file_path)
        if level:
            levels.add(level)

    return [level for level in ("L1", "L2") if level in levels]


def find_scene_support_files(scene_dir, product_level: Optional[str] = None) -> Dict[str, Optional[str]]:
    """按产品级别查找 MTL / QA 等辅助文件。"""
    scene_dir = Path(scene_dir)
    if not scene_dir.exists() or not scene_dir.is_dir():
        raise ValueError(f"场景目录不存在或不是目录: {scene_dir}")

    normalized_level = _normalize_product_level(product_level)
    qa_patterns = ["*QA_PIXEL*.tif", "*QA_PIXEL*.TIF", "*BQA*.tif", "*BQA*.TIF"]
    if normalized_level == "L1":
        qa_patterns = ["*BQA*.tif", "*BQA*.TIF", "*QA_PIXEL*.tif", "*QA_PIXEL*.TIF"]

    return {
        "mtl_file": _choose_scene_file(
            scene_dir,
            ["*MTL*.txt", "*MTL*.TXT"],
            product_level=normalized_level,
            recursive=True,
            fallback_to_any=True,
        ),
        "qa_band": _choose_scene_file(
            scene_dir,
            qa_patterns,
            product_level=normalized_level,
            recursive=True,
            fallback_to_any=True,
        ),
        "qa_radsat_band": _choose_scene_file(
            scene_dir,
            ["*QA_RADSAT*.tif", "*QA_RADSAT*.TIF"],
            product_level=normalized_level,
            recursive=True,
            fallback_to_any=True,
        ),
    }


def collect_band_paths(
    band_dir,
    on_duplicate: str = "warn",
    product_level: Optional[str] = None,
    recursive: bool = True,
) -> Dict[str, str]:
    """收集目录中的 Landsat 波段文件路径。

    Args:
        band_dir: 波段文件目录 (str 或 Path)。
        on_duplicate: 遇到重复波段时的行为:
            ``"raise"`` — 抛出 ValueError；
            ``"warn"``  — 记录警告并保留先匹配项 (默认)。
        product_level: 期望的产品级别，L1/L2。若指定，将优先筛选匹配级别的波段文件。
        recursive: 是否递归扫描子目录，默认启用以兼容场景目录下同时存在 L1/L2 子目录的情况。

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

    band_candidates: Dict[str, List[Path]] = {}
    for file_path in _iter_files(band_dir, recursive=recursive):
        if file_path.suffix.lower() not in _RASTER_SUFFIXES:
            continue

        band_name = _detect_band_name(file_path.name)
        if not band_name:
            continue

        band_candidates.setdefault(band_name, []).append(file_path)

    band_paths: Dict[str, str] = {}
    normalized_level = _normalize_product_level(product_level)
    for band_name, candidates in sorted(band_candidates.items()):
        if len(candidates) > 1 and on_duplicate == "raise":
            raise ValueError(
                f"波段重复: {band_name} ({'；'.join(str(path) for path in candidates)})"
            )

        preferred = _preferred_candidates(candidates, band_dir, normalized_level)
        if not preferred:
            logger.warning(
                "波段 %s 未找到匹配 %s 的候选文件，已跳过该波段",
                band_name,
                normalized_level,
            )
            continue

        selected = preferred[0]
        if len(candidates) > 1:
            logger.warning(
                "发现重复波段文件，已选择更匹配的候选: %s -> %s",
                band_name,
                selected,
            )

        band_paths[band_name] = str(selected)

    if not band_paths:
        if normalized_level:
            raise ValueError(f"未在目录中识别到 {normalized_level} 产品的 B1-B11 波段文件")
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
