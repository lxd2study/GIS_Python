"""Filesystem whitelist enforcement helpers."""

import os
from pathlib import Path
from typing import Dict, Optional, Sequence

from ..core.config import settings
from ..core.models import BatchJobConfig


class PathAccessError(ValueError):
    """Raised when a filesystem path violates the access policy."""

    def __init__(self, message: str, *, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


def _normalized_case(path: Path) -> str:
    return os.path.normcase(str(path))


class PathAccessController:
    """Restrict filesystem access to configured root directories."""

    def __init__(self, allowed_roots: Sequence[Path], base_path: Optional[Path] = None):
        self.base_path = (base_path or settings.PROJECT_ROOT).resolve(strict=False)

        normalized_roots = []
        seen = set()
        for root in allowed_roots:
            resolved = self._resolve_path(root)
            key = _normalized_case(resolved)
            if key in seen:
                continue
            seen.add(key)
            normalized_roots.append(resolved)

        if not normalized_roots:
            raise ValueError("至少需要配置一个允许访问的根目录")

        self.allowed_roots = tuple(normalized_roots)

    def _resolve_path(self, raw_path) -> Path:
        path = raw_path if isinstance(raw_path, Path) else Path(str(raw_path).strip()).expanduser()
        if not path.is_absolute():
            path = self.base_path / path
        return path.resolve(strict=False)

    @staticmethod
    def _is_relative_to(candidate: Path, root: Path) -> bool:
        candidate_text = _normalized_case(candidate)
        root_text = _normalized_case(root)
        return candidate_text == root_text or candidate_text.startswith(root_text + os.sep)

    def is_allowed(self, raw_path) -> bool:
        candidate = self._resolve_path(raw_path)
        return any(self._is_relative_to(candidate, root) for root in self.allowed_roots)

    def _check_allowed(self, candidate: Path, raw_path: str, access_label: str) -> None:
        if self.is_allowed(candidate):
            return

        roots_text = "；".join(str(root) for root in self.allowed_roots)
        raise PathAccessError(
            f"禁止{access_label}白名单目录之外的路径: {raw_path}。允许的根目录: {roots_text}",
            status_code=403,
        )

    def require_directory(
        self,
        raw_path,
        *,
        access_label: str = "访问目录",
        must_exist: bool = True,
        allow_create: bool = False,
    ) -> Path:
        path_text = str(raw_path).strip() if raw_path is not None else ""
        if not path_text:
            raise PathAccessError("路径不能为空", status_code=400)

        candidate = self._resolve_path(path_text)
        self._check_allowed(candidate, path_text, access_label)

        if candidate.exists():
            if not candidate.is_dir():
                raise PathAccessError(f"不是目录: {path_text}", status_code=400)
        elif must_exist and not allow_create:
            raise PathAccessError(f"路径不存在: {path_text}", status_code=404)

        return candidate

    def require_file(
        self,
        raw_path,
        *,
        access_label: str = "访问文件",
        allowed_suffixes: Optional[Sequence[str]] = None,
    ) -> Path:
        path_text = str(raw_path).strip() if raw_path is not None else ""
        if not path_text:
            raise PathAccessError("路径不能为空", status_code=400)

        candidate = self._resolve_path(path_text)
        self._check_allowed(candidate, path_text, access_label)

        if not candidate.exists():
            raise PathAccessError(f"文件不存在: {path_text}", status_code=404)
        if not candidate.is_file():
            raise PathAccessError(f"不是文件: {path_text}", status_code=400)

        if allowed_suffixes:
            normalized_suffixes = {suffix.lower() for suffix in allowed_suffixes}
            if candidate.suffix.lower() not in normalized_suffixes:
                suffix_text = ", ".join(sorted(normalized_suffixes))
                raise PathAccessError(
                    f"不支持的文件类型: {candidate.suffix or '(无扩展名)'}。允许的扩展名: {suffix_text}",
                    status_code=400,
                )

        return candidate

    def optional_file(self, raw_path, *, access_label: str = "访问文件") -> Optional[str]:
        if raw_path is None or not str(raw_path).strip():
            return None
        return str(self.require_file(raw_path, access_label=access_label))

    def allowed_roots_payload(self):
        return [
            {
                "name": root.name or str(root),
                "path": str(root),
            }
            for root in self.allowed_roots
        ]

    def validate_batch_job_config(self, config: BatchJobConfig) -> BatchJobConfig:
        updates: Dict[str, Optional[str]] = {
            "band_dir": str(self.require_directory(config.band_dir, access_label="读取波段目录")),
            "output_dir": str(
                self.require_directory(
                    config.output_dir,
                    access_label="写入输出目录",
                    must_exist=False,
                    allow_create=True,
                )
            ),
        }

        if config.mtl_file:
            updates["mtl_file"] = str(self.require_file(config.mtl_file, access_label="读取 MTL 文件"))
        if config.qa_band:
            updates["qa_band"] = str(self.require_file(config.qa_band, access_label="读取 QA 文件"))
        if config.qa_radsat_band:
            updates["qa_radsat_band"] = str(
                self.require_file(config.qa_radsat_band, access_label="读取 QA_RADSAT 文件")
            )
        if config.clip_shapefile:
            updates["clip_shapefile"] = str(
                self.require_file(config.clip_shapefile, access_label="读取裁剪矢量文件")
            )

        return config.model_copy(update=updates)
