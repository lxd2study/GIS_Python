"""File handling helpers."""

import logging
import os
import shutil
import tempfile
import threading
from typing import Dict, List, Optional

from ..core.constants import COMPOSITE_MAP

logger = logging.getLogger(__name__)
UPLOAD_CHUNK_SIZE = 1024 * 1024


class FileManager:
    """File manager for temporary data and parameter parsing."""

    def __init__(self):
        self.temp_dirs: Dict[str, str] = {}
        self.lock = threading.Lock()

    def create_temp_dir(self, prefix: str = "landsat8_") -> str:
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        with self.lock:
            self.temp_dirs[temp_dir] = temp_dir
        return temp_dir

    def cleanup_temp_dir(self, temp_dir: str) -> None:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as exc:
                logger.warning("清理临时目录失败: %s", exc)

        with self.lock:
            self.temp_dirs.pop(temp_dir, None)

    @staticmethod
    def _copy_file_stream(file_obj, target_path: str) -> None:
        """按块复制文件流，避免一次性把大文件读入内存。"""
        try:
            file_obj.seek(0)
        except Exception:
            pass

        with open(target_path, "wb") as output_file:
            while True:
                chunk = file_obj.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                output_file.write(chunk)

    def save_shapefiles(self, shape_files, temp_shape_dir: str) -> Optional[str]:
        """Save uploaded shapefile family and return .shp path."""
        shapefile_path = None
        allowed_ext = {".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx"}

        for shape_file in shape_files:
            filename = shape_file.filename
            file_extension = os.path.splitext(filename)[-1].lower()

            if file_extension not in allowed_ext:
                logger.warning("不支持的矢量文件类型: %s，文件名: %s", file_extension, filename)
                continue

            temp_shape_path = os.path.join(temp_shape_dir, filename)
            # Shapefile 依赖同名配套文件，这里保留用户上传的原始文件名。
            self._copy_file_stream(shape_file.file, temp_shape_path)

            if file_extension == ".shp":
                shapefile_path = temp_shape_path

        return shapefile_path

    def parse_extent(self, extent_str: Optional[str]) -> Optional[List[float]]:
        """Parse xmin,ymin,xmax,ymax text to float list."""
        if not extent_str:
            return None

        try:
            extent_list = [float(item.strip()) for item in extent_str.split(",")]
        except Exception as exc:
            raise ValueError(f"裁剪范围格式错误: {exc}") from exc

        if len(extent_list) != 4:
            raise ValueError("裁剪范围必须包含4个值: xmin,ymin,xmax,ymax")

        return extent_list

    def parse_composites(self, composite_str: Optional[str]) -> Optional[List[str]]:
        """Parse composite string and validate against supported keys."""
        if not composite_str:
            return None

        composite_list = [item.strip() for item in composite_str.split(",") if item.strip()]
        if not composite_list:
            return None

        valid_composites = set(COMPOSITE_MAP.keys())
        invalid_items = [item for item in composite_list if item not in valid_composites]
        if invalid_items:
            valid_text = ", ".join(sorted(valid_composites))
            invalid_text = ", ".join(invalid_items)
            raise ValueError(f"不支持的合成类型: {invalid_text}。有效类型: {valid_text}")

        return composite_list
