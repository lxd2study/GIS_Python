"""Unified task result catalog and download helpers."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

from fastapi.responses import StreamingResponse

from ..core.config import settings
from ..core.constants import COMPOSITE_MAP
from ..core.models import ProcessingResult, ResultArtifactItem, ResultTaskItem
from ..utils.path_policy import PathAccessController

if TYPE_CHECKING:
    from .batch_manager import BatchJobManager
    from .progress import ProgressManager


MANIFEST_FILENAME = "task_manifest.json"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
PREVIEWABLE_SUFFIXES = {".tif", ".tiff", ".img", ".png"}
METADATA_SUFFIXES = {".json", ".txt", ".md", ".csv"}
COMPOSITE_NAMES = set(COMPOSITE_MAP) | {"custom_index"}
SKIP_HISTORY_DIRS = {"landsat_downloads"}
ARTIFACT_CATEGORY_ORDER = {
    "processed": 0,
    "composite": 1,
    "mask": 2,
    "metadata": 3,
    "extra": 4,
}
PROCESSED_PATTERN = re.compile(r"^B\d{1,2}(?:_display)?_(?:processed|clipped)$", re.IGNORECASE)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp_or_zero(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _normalize_output_dir(raw_path: str) -> str:
    return str(Path(raw_path).resolve(strict=False))


def _result_to_dict(result: Optional[Any]) -> Dict[str, Any]:
    if result is None:
        return {}
    if isinstance(result, ProcessingResult):
        return result.model_dump()
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, dict):
        return dict(result)
    return {}


def _category_from_path(file_path: Path) -> str:
    if file_path.name == MANIFEST_FILENAME:
        return "metadata"

    stem = file_path.stem
    if stem.lower() == "cloud_mask":
        return "mask"
    if PROCESSED_PATTERN.match(stem):
        return "processed"
    if stem in COMPOSITE_NAMES:
        return "composite"
    if file_path.suffix.lower() in METADATA_SUFFIXES:
        return "metadata"
    return "extra"


def _artifact_sort_key(item: ResultArtifactItem) -> tuple[int, str, str]:
    return (
        ARTIFACT_CATEGORY_ORDER.get(item.category, 99),
        item.label.lower(),
        item.filename.lower(),
    )


def _sorted_artifacts(items: Iterable[ResultArtifactItem]) -> List[ResultArtifactItem]:
    return sorted(items, key=_artifact_sort_key)


def _same_parent(candidate: Path, target_dir: Path) -> bool:
    return os.path.normcase(str(candidate.resolve(strict=False).parent)) == os.path.normcase(str(target_dir.resolve(strict=False)))


def _make_artifact_item(
    file_path: Path,
    *,
    category: Optional[str] = None,
    key: Optional[str] = None,
    label: Optional[str] = None,
    allow_missing: bool = False,
) -> Optional[ResultArtifactItem]:
    resolved = file_path.resolve(strict=False)
    if not allow_missing and (not resolved.exists() or not resolved.is_file()):
        return None

    item_category = category or _category_from_path(resolved)
    size_bytes = resolved.stat().st_size if resolved.exists() and resolved.is_file() else 0
    return ResultArtifactItem(
        key=key or resolved.name,
        label=label or resolved.stem,
        category=item_category,
        path=str(resolved),
        filename=resolved.name,
        size_bytes=size_bytes,
        previewable=resolved.suffix.lower() in PREVIEWABLE_SUFFIXES,
    )


def build_result_artifacts(
    result: Optional[Any],
    output_dir: str,
    *,
    include_manifest: bool = False,
) -> List[ResultArtifactItem]:
    result_dict = _result_to_dict(result)
    output_path = Path(output_dir).resolve(strict=False)
    seen = set()
    artifacts: List[ResultArtifactItem] = []

    def add_result_artifact(path_value: Optional[str], *, category: str, label: str) -> None:
        if not path_value:
            return
        artifact_path = Path(path_value).resolve(strict=False)
        normalized = os.path.normcase(str(artifact_path))
        if normalized in seen:
            return
        item = _make_artifact_item(
            artifact_path,
            category=category,
            key=artifact_path.name,
            label=label,
        )
        if not item:
            return
        seen.add(normalized)
        artifacts.append(item)

    for label, path_value in (result_dict.get("processed_bands") or {}).items():
        add_result_artifact(path_value, category="processed", label=str(label))

    for label, path_value in (result_dict.get("composites") or {}).items():
        add_result_artifact(path_value, category="composite", label=str(label))

    add_result_artifact(result_dict.get("cloud_mask"), category="mask", label="cloud_mask")

    if include_manifest:
        manifest_path = output_path / MANIFEST_FILENAME
        normalized = os.path.normcase(str(manifest_path.resolve(strict=False)))
        if normalized not in seen:
            item = _make_artifact_item(
                manifest_path,
                category="metadata",
                key=MANIFEST_FILENAME,
                label=MANIFEST_FILENAME,
            )
            if item:
                seen.add(normalized)
                artifacts.append(item)

    return _sorted_artifacts(artifacts)


def _build_manifest_payload(
    *,
    task_type: str,
    title: str,
    output_dir: str,
    artifacts: List[ResultArtifactItem],
    job_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    created_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "task_type": task_type,
        "job_id": job_id,
        "batch_id": batch_id,
        "title": title,
        "output_dir": _normalize_output_dir(output_dir),
        "created_at": created_at,
        "completed_at": completed_at,
        "summary": dict(summary or {}),
        "artifacts": [item.model_dump() for item in _sorted_artifacts(artifacts)],
    }


def write_task_manifest(
    *,
    task_type: str,
    title: str,
    output_dir: str,
    result: Optional[Any],
    job_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    created_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    summary: Optional[Dict[str, Any]] = None,
) -> Path:
    output_path = Path(output_dir).resolve(strict=False)
    output_path.mkdir(parents=True, exist_ok=True)

    manifest_path = output_path / MANIFEST_FILENAME
    artifacts = build_result_artifacts(result, str(output_path), include_manifest=False)

    payload = _build_manifest_payload(
        task_type=task_type,
        title=title,
        output_dir=str(output_path),
        artifacts=artifacts,
        job_id=job_id,
        batch_id=batch_id,
        created_at=created_at,
        completed_at=completed_at or _utc_now_iso(),
        summary=summary,
    )
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest_item = _make_artifact_item(
        manifest_path,
        category="metadata",
        key=MANIFEST_FILENAME,
        label=MANIFEST_FILENAME,
    )
    if manifest_item:
        payload["artifacts"] = [
            item.model_dump()
            for item in _sorted_artifacts([*artifacts, manifest_item])
        ]
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return manifest_path


class TaskResultService:
    """Aggregate completed task results across current and historical sources."""

    def __init__(
        self,
        *,
        progress_manager: "ProgressManager",
        batch_manager: "BatchJobManager",
        path_access: Optional[PathAccessController] = None,
        output_root: Optional[Path] = None,
        temp_root: Optional[Path] = None,
    ) -> None:
        self.progress_manager = progress_manager
        self.batch_manager = batch_manager
        self.path_access = path_access or PathAccessController(settings.allowed_path_roots)
        self.output_root = Path(output_root or settings.OUTPUT_DIR).resolve(strict=False)
        self.temp_root = Path(temp_root or settings.TEMP_DIR).resolve(strict=False)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def list_result_tasks(self) -> List[ResultTaskItem]:
        merged: Dict[str, ResultTaskItem] = {}

        for item in [*self._collect_current_tasks(), *self._scan_history_tasks()]:
            if item.artifact_count <= 0:
                continue
            key = os.path.normcase(_normalize_output_dir(item.output_dir))
            existing = merged.get(key)
            if existing is None or self._should_replace(existing, item):
                merged[key] = item

        return sorted(merged.values(), key=self._task_sort_key, reverse=True)

    def get_task_by_output_dir(self, output_dir: str) -> Optional[ResultTaskItem]:
        normalized = os.path.normcase(_normalize_output_dir(output_dir))
        for item in self.list_result_tasks():
            if os.path.normcase(_normalize_output_dir(item.output_dir)) == normalized:
                return item
        return None

    def build_file_response(self, file_path: str) -> StreamingResponse:
        resolved = self.path_access.require_file(file_path, access_label="下载结果文件")
        media_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        safe_filename = resolved.name.replace('"', "_")

        def iter_file():
            with open(resolved, "rb") as file_obj:
                while True:
                    chunk = file_obj.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk

        return StreamingResponse(
            iter_file(),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
        )

    def build_archive_response(self, output_dir: str) -> StreamingResponse:
        target_dir = self.path_access.require_directory(output_dir, access_label="读取结果目录")
        task = self.get_task_by_output_dir(str(target_dir))
        if not task:
            raise ValueError("结果目录暂无可下载产物")

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".zip",
            prefix="rst-results-",
            dir=self.temp_root,
        )
        temp_path = Path(temp_file.name)
        temp_file.close()

        try:
            added_names = set()
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for artifact in task.artifacts:
                    artifact_path = self.path_access.require_file(artifact.path, access_label="读取结果压缩文件")
                    if not _same_parent(artifact_path, target_dir):
                        continue
                    archive.write(artifact_path, arcname=artifact_path.name)
                    added_names.add(artifact_path.name)

                if MANIFEST_FILENAME not in added_names:
                    payload = _build_manifest_payload(
                        task_type=task.task_type,
                        title=task.title,
                        output_dir=task.output_dir,
                        artifacts=task.artifacts,
                        job_id=task.job_id,
                        batch_id=task.batch_id,
                        created_at=task.created_at,
                        completed_at=task.completed_at,
                        summary=task.summary,
                    )
                    archive.writestr(
                        MANIFEST_FILENAME,
                        json.dumps(payload, ensure_ascii=False, indent=2),
                    )
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        safe_dir_name = re.sub(r"[^\w.-]+", "_", target_dir.name or "result").strip("_") or "result"
        archive_name = f"{safe_dir_name}.zip"

        def iter_archive():
            try:
                with open(temp_path, "rb") as file_obj:
                    while True:
                        chunk = file_obj.read(DOWNLOAD_CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk
            finally:
                temp_path.unlink(missing_ok=True)

        return StreamingResponse(
            iter_archive(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{archive_name}"'},
        )

    def _should_replace(self, existing: ResultTaskItem, candidate: ResultTaskItem) -> bool:
        return self._task_priority(candidate) > self._task_priority(existing)

    def _task_priority(self, item: ResultTaskItem) -> tuple[int, float, float]:
        return (
            1 if item.source == "current" else 0,
            _timestamp_or_zero(item.completed_at),
            _timestamp_or_zero(item.created_at),
        )

    def _task_sort_key(self, item: ResultTaskItem) -> tuple[float, float, str]:
        completed = _timestamp_or_zero(item.completed_at)
        created = _timestamp_or_zero(item.created_at)
        return (completed or created, created, item.title.lower())

    def _collect_current_tasks(self) -> List[ResultTaskItem]:
        items = []
        items.extend(self._collect_single_tasks())
        items.extend(self._collect_batch_tasks())
        return items

    def _collect_single_tasks(self) -> List[ResultTaskItem]:
        tasks: List[ResultTaskItem] = []
        for record in self.progress_manager.list_progress_records(status="success"):
            result_dict = _result_to_dict(record.result)
            summary = dict(result_dict.get("summary") or {})
            output_dir = _normalize_output_dir(summary.get("output_directory") or "")
            if not output_dir:
                continue
            if not self.path_access.is_allowed(output_dir):
                continue

            artifacts = build_result_artifacts(result_dict, output_dir, include_manifest=True)
            summary.setdefault("output_directory", output_dir)
            title = (
                str((result_dict.get("metadata") or {}).get("scene_id") or "").strip()
                or Path(output_dir).name
            )
            tasks.append(
                ResultTaskItem(
                    id=f"single:{record.job_id}",
                    source="current",
                    task_type="single",
                    title=title,
                    job_id=record.job_id,
                    batch_id=None,
                    status=record.status,
                    output_dir=output_dir,
                    created_at=record.created_at,
                    completed_at=record.updated_at,
                    summary=summary,
                    artifact_count=len(artifacts),
                    artifacts=artifacts,
                )
            )
        return tasks

    def _collect_batch_tasks(self) -> List[ResultTaskItem]:
        tasks: List[ResultTaskItem] = []
        for job in self.batch_manager.list_jobs(status="success"):
            output_dir = _normalize_output_dir(job.config.output_dir)
            if not self.path_access.is_allowed(output_dir):
                continue

            result_dict = _result_to_dict(job.result)
            summary = dict(result_dict.get("summary") or {})
            artifacts = build_result_artifacts(result_dict, output_dir, include_manifest=True)
            batch_name = self.batch_manager.get_batch_name(job.batch_id)
            task_type = "mosaic" if getattr(job.config.job_kind, "value", job.config.job_kind) == "mosaic" else "batch"
            if task_type == "mosaic":
                title = f"镶嵌任务 · {job.config.scene_name}" if job.config.scene_name else "镶嵌任务"
            else:
                title = job.config.scene_name or batch_name or Path(output_dir).name
                if batch_name and job.config.scene_name and batch_name != job.config.scene_name:
                    title = f"{batch_name} / {job.config.scene_name}"
            summary.setdefault("output_directory", output_dir)

            tasks.append(
                ResultTaskItem(
                    id=f"batch:{job.job_id}",
                    source="current",
                    task_type=task_type,
                    title=title,
                    job_id=job.job_id,
                    batch_id=job.batch_id,
                    status=str(getattr(job.status, "value", job.status)),
                    output_dir=output_dir,
                    created_at=job.created_at,
                    completed_at=job.completed_at or job.updated_at,
                    summary=summary,
                    artifact_count=len(artifacts),
                    artifacts=artifacts,
                )
            )
        return tasks

    def _scan_history_tasks(self) -> List[ResultTaskItem]:
        if not self.output_root.exists() or not self.output_root.is_dir():
            return []

        tasks: List[ResultTaskItem] = []
        for child in self.output_root.iterdir():
            if not child.is_dir():
                continue
            if child.name.startswith("_") or child.name in SKIP_HISTORY_DIRS:
                continue
            if not self.path_access.is_allowed(child):
                continue

            manifest_path = child / MANIFEST_FILENAME
            task = self._task_from_manifest(manifest_path) if manifest_path.exists() else self._task_from_directory(child)
            if task:
                tasks.append(task)
        return tasks

    def _task_from_manifest(self, manifest_path: Path) -> Optional[ResultTaskItem]:
        output_dir = manifest_path.parent.resolve(strict=False)
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return self._task_from_directory(output_dir)

        artifacts = self._artifacts_from_manifest_payload(payload.get("artifacts"), output_dir)
        if not artifacts:
            artifacts = self._scan_directory_artifacts(output_dir)
        elif not any(item.filename == MANIFEST_FILENAME for item in artifacts):
            manifest_item = _make_artifact_item(
                manifest_path,
                category="metadata",
                key=MANIFEST_FILENAME,
                label=MANIFEST_FILENAME,
            )
            if manifest_item:
                artifacts = _sorted_artifacts([*artifacts, manifest_item])

        normalized_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        normalized_summary.setdefault("output_directory", str(output_dir))
        completed_at = payload.get("completed_at") or self._path_mtime_iso(manifest_path)
        created_at = payload.get("created_at") or completed_at
        task_type = str(payload.get("task_type") or self._infer_history_task_type(output_dir))
        title = str(payload.get("title") or output_dir.name)

        return ResultTaskItem(
            id=f"history:{output_dir.name}",
            source="history",
            task_type=task_type,
            title=title,
            job_id=payload.get("job_id"),
            batch_id=payload.get("batch_id"),
            status="success",
            output_dir=str(output_dir),
            created_at=created_at,
            completed_at=completed_at,
            summary=normalized_summary,
            artifact_count=len(artifacts),
            artifacts=artifacts,
        )

    def _task_from_directory(self, output_dir: Path) -> Optional[ResultTaskItem]:
        artifacts = self._scan_directory_artifacts(output_dir)
        if not artifacts:
            return None

        completed_at = self._path_mtime_iso(output_dir)
        task_type = self._infer_history_task_type(output_dir)
        title = output_dir.name

        return ResultTaskItem(
            id=f"history:{output_dir.name}",
            source="history",
            task_type=task_type,
            title=title,
            job_id=None,
            batch_id=None,
            status="success",
            output_dir=str(output_dir.resolve(strict=False)),
            created_at=completed_at,
            completed_at=completed_at,
            summary={"output_directory": str(output_dir.resolve(strict=False))},
            artifact_count=len(artifacts),
            artifacts=artifacts,
        )

    def _artifacts_from_manifest_payload(self, raw_artifacts: Any, output_dir: Path) -> List[ResultArtifactItem]:
        if not isinstance(raw_artifacts, list):
            return []

        items: List[ResultArtifactItem] = []
        seen = set()
        for entry in raw_artifacts:
            if not isinstance(entry, dict):
                continue
            raw_path = str(entry.get("path") or "").strip()
            if not raw_path:
                continue
            path = Path(raw_path)
            if not path.is_absolute():
                path = output_dir / path
            path = path.resolve(strict=False)
            if not _same_parent(path, output_dir):
                continue
            normalized = os.path.normcase(str(path))
            if normalized in seen or not path.exists() or not path.is_file():
                continue

            item = _make_artifact_item(
                path,
                category=str(entry.get("category") or _category_from_path(path)),
                key=str(entry.get("key") or path.name),
                label=str(entry.get("label") or path.stem),
            )
            if not item:
                continue
            seen.add(normalized)
            items.append(item)
        return _sorted_artifacts(items)

    def _scan_directory_artifacts(self, output_dir: Path) -> List[ResultArtifactItem]:
        items: List[ResultArtifactItem] = []
        for child in output_dir.iterdir():
            if not child.is_file():
                continue
            item = _make_artifact_item(
                child,
                category=_category_from_path(child),
                key=child.name,
                label=child.name if child.name == MANIFEST_FILENAME else child.stem,
            )
            if item:
                items.append(item)
        return _sorted_artifacts(items)

    def _infer_history_task_type(self, output_dir: Path) -> str:
        if output_dir.name.lower() == "mosaic":
            return "mosaic"
        return "single"

    @staticmethod
    def _path_mtime_iso(path: Path) -> str:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
