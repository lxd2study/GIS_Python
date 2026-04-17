"""批量任务管理器"""

import logging
import shutil
import queue
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from osgeo import gdal

from ..core.config import settings
from ..core.constants import COMPOSITE_MAP
from ..core.models import (
    BatchJob,
    BatchJobConfig,
    BatchStatusResponse,
    JobKind,
    TaskPriority,
    TaskStatus,
    ProcessingResult,
    SceneInputConfig,
)
from ..core.processor import Landsat8Processor
from ..operations import clip_raster, mosaic_rasters
from ..services.task_results import write_task_manifest
from ..utils.file_utils import collect_band_paths, detect_product_level_from_path, find_scene_support_files
from ..utils.path_policy import PathAccessController

logger = logging.getLogger(__name__)

DISPLAY_COMPOSITE_TYPES = (
    "true_color",
    "false_color",
    "natural_color",
    "agriculture",
    "urban",
    "swir",
)
DISPLAY_COMPOSITE_TYPE_SET = set(DISPLAY_COMPOSITE_TYPES)
DISPLAY_BALANCE_PERCENTILES = np.asarray([1, 5, 25, 50, 75, 95, 99], dtype=np.float32)
DISPLAY_BALANCE_SAMPLE_TARGET = 200_000
DISPLAY_BALANCE_CLIP_RANGE = (np.float32(-0.2), np.float32(1.6))


class BatchJobManager:
    """批量任务管理器 - 支持优先级队列、暂停/恢复、失败重试"""

    def __init__(self, max_workers: int = 2):
        """初始化批量任务管理器

        Args:
            max_workers: 最大并行工作线程数
        """
        self.max_workers = max_workers
        self.batches: Dict[str, Dict] = {}  # batch_id -> batch_info
        self.jobs: Dict[str, BatchJob] = {}  # job_id -> BatchJob
        self.job_queues: Dict[str, queue.PriorityQueue] = {
            TaskPriority.HIGH: queue.PriorityQueue(),
            TaskPriority.MEDIUM: queue.PriorityQueue(),
            TaskPriority.LOW: queue.PriorityQueue(),
        }

        self.lock = threading.Lock()
        self.workers: List[threading.Thread] = []
        self.shutdown_flag = threading.Event()
        self.paused_jobs: Dict[str, BatchJob] = {}  # 暂停的任务
        self.path_access = PathAccessController(settings.allowed_path_roots)

        # 启动工作线程
        self._start_workers()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _enqueue_job(self, job: BatchJob) -> None:
        priority_value = self._get_priority_value(job.priority)
        self.job_queues[job.priority].put((priority_value, job.job_id))

    def _mark_job_running(self, job: BatchJob) -> None:
        now = self._utc_now()
        job.status = TaskStatus.RUNNING
        job.started_at = now
        job.updated_at = now

    def _mark_job_success(self, job: BatchJob, result: Dict) -> None:
        now = self._utc_now()
        job.status = TaskStatus.SUCCESS
        job.progress = 100
        job.error = None
        job.result = ProcessingResult(**result)
        job.completed_at = now
        job.updated_at = now

    @staticmethod
    def _count_jobs_by_status(jobs: List[BatchJob], statuses) -> int:
        if not isinstance(statuses, (list, tuple, set)):
            statuses = {statuses}
        return sum(1 for job in jobs if job.status in statuses)

    def _start_workers(self):
        """启动工作线程池"""
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
            worker.start()
            self.workers.append(worker)

    def _worker_loop(self, worker_id: int):
        """工作线程主循环"""
        logger.info("Worker %d started", worker_id)

        while not self.shutdown_flag.is_set():
            job = self._get_next_job()
            if job is None:
                self.shutdown_flag.wait(1)
                continue

            try:
                self._execute_job(job, worker_id)
            except Exception as e:
                logger.error("Worker %d job %s error: %s", worker_id, job.job_id, e)
                self._handle_job_failure(job, str(e))

    def _get_next_job(self) -> Optional[BatchJob]:
        """从优先级队列中获取下一个任务"""
        # 按优先级顺序尝试获取任务
        for priority in [TaskPriority.HIGH, TaskPriority.MEDIUM, TaskPriority.LOW]:
            try:
                _, job_id = self.job_queues[priority].get_nowait()
                with self.lock:
                    job = self.jobs.get(job_id)
                    if job and job.status == TaskStatus.QUEUED:
                        return job
            except queue.Empty:
                continue
        return None

    def _execute_job(self, job: BatchJob, worker_id: int):
        """执行单个任务"""
        logger.info("Worker %d executing job %s", worker_id, job.job_id)

        with self.lock:
            self._mark_job_running(job)

        try:
            def progress_callback(progress_info: Dict):
                with self.lock:
                    if 'progress' in progress_info:
                        job.progress = progress_info['progress']
                    job.updated_at = self._utc_now()

            if job.config.job_kind == JobKind.MOSAIC:
                result = self._execute_mosaic_job(job.config, progress_callback)
            else:
                result = self._execute_scene_job(job.config, progress_callback)

            if result.get("status") != "success":
                error_message = result.get("error") or "批处理预处理返回失败状态"
                raise RuntimeError(error_message)

            with self.lock:
                self._mark_job_success(job, result)

            try:
                self._write_job_manifest(job, result)
            except Exception as exc:
                logger.warning("写入批量任务结果清单失败，不影响任务成功状态: %s", exc, exc_info=True)
            logger.info("Job %s completed successfully", job.job_id)

        except Exception as e:
            logger.error("Job %s failed: %s", job.job_id, e)
            self._handle_job_failure(job, str(e))

    @staticmethod
    def _resolve_support_file(
        configured_path: Optional[str],
        detected_path: Optional[str],
        product_level: str,
        scene_name: str,
    ) -> Optional[str]:
        if not configured_path:
            return detected_path

        detected_level = detect_product_level_from_path(Path(configured_path))
        if (
            product_level
            and detected_level
            and detected_level != product_level
            and detected_path
        ):
            logger.info(
                "场景 %s 检测到辅助文件产品级别不匹配，已切换为自动发现的 %s 文件: %s",
                scene_name,
                product_level,
                detected_path,
            )
            return detected_path

        return configured_path

    def _resolve_scene_inputs(self, config: BatchJobConfig) -> Tuple[Dict[str, str], Optional[str], Optional[str], Optional[str]]:
        band_paths = collect_band_paths(
            config.band_dir,
            product_level=config.product_level,
        )
        band_paths = {
            band_name: str(
                self.path_access.require_file(
                    band_path,
                    access_label="读取波段文件",
                )
            )
            for band_name, band_path in band_paths.items()
        }

        scene_support_files = find_scene_support_files(
            config.band_dir,
            product_level=config.product_level,
        )
        scene_support_files = {
            "mtl_file": self.path_access.optional_file(
                scene_support_files.get("mtl_file"),
                access_label="读取自动发现的 MTL 文件",
            ),
            "qa_band": self.path_access.optional_file(
                scene_support_files.get("qa_band"),
                access_label="读取自动发现的 QA 文件",
            ),
            "qa_radsat_band": self.path_access.optional_file(
                scene_support_files.get("qa_radsat_band"),
                access_label="读取自动发现的 QA_RADSAT 文件",
            ),
        }

        mtl_file = self._resolve_support_file(
            config.mtl_file,
            scene_support_files.get("mtl_file"),
            config.product_level,
            config.scene_name,
        )
        qa_band = self._resolve_support_file(
            config.qa_band,
            scene_support_files.get("qa_band"),
            config.product_level,
            config.scene_name,
        )
        qa_radsat_band = self._resolve_support_file(
            config.qa_radsat_band,
            scene_support_files.get("qa_radsat_band"),
            config.product_level,
            config.scene_name,
        )
        return band_paths, mtl_file, qa_band, qa_radsat_band

    def _execute_scene_job(
        self,
        config: BatchJobConfig,
        progress_callback: Optional[Callable[[Dict], None]] = None,
    ) -> Dict:
        band_paths, mtl_file, qa_band, qa_radsat_band = self._resolve_scene_inputs(config)
        processor = Landsat8Processor()
        return processor.one_click_preprocess(
            band_paths=band_paths,
            output_dir=config.output_dir,
            mtl_path=mtl_file,
            clip_extent=config.clip_extent,
            clip_shapefile=config.clip_shapefile,
            create_composites=config.create_composites,
            apply_cloud_mask=config.apply_cloud_mask,
            qa_band_path=qa_band,
            qa_radsat_band_path=qa_radsat_band,
            atm_correction_method=config.atm_correction_method,
            product_level=config.product_level,
            custom_index_formula=config.custom_index_formula,
            custom_index_name=config.custom_index_name,
            progress_callback=progress_callback,
        )

    def _update_mosaic_progress(
        self,
        progress_callback: Optional[Callable[[Dict], None]],
        progress: int,
        detail: str,
    ) -> None:
        if progress_callback is None:
            return
        progress_callback({"progress": progress, "detail": detail})

    def _scene_input_to_job_config(
        self,
        scene_input: SceneInputConfig,
        output_dir: str,
        template,
        atm_correction_method: str,
        apply_cloud_mask: bool,
    ) -> BatchJobConfig:
        return BatchJobConfig(
            scene_name=scene_input.scene_name,
            band_dir=scene_input.band_dir,
            output_dir=output_dir,
            mtl_file=scene_input.mtl_file,
            qa_band=scene_input.qa_band,
            qa_radsat_band=scene_input.qa_radsat_band,
            product_level=scene_input.product_level,
            template=template,
            atm_correction_method=atm_correction_method,
            apply_cloud_mask=apply_cloud_mask,
            clip_extent=None,
            clip_shapefile=None,
            create_composites=[],
            custom_index_formula=None,
            custom_index_name=None,
            display_balance_enabled=False,
        )

    @staticmethod
    def _filter_display_composites(create_composites: Optional[List[str]]) -> List[str]:
        return [item for item in (create_composites or []) if item in DISPLAY_COMPOSITE_TYPE_SET]

    @staticmethod
    def _collect_display_band_names(display_composites: List[str]) -> List[str]:
        ordered: List[str] = []
        seen = set()
        for composite_type in display_composites:
            for band_name in COMPOSITE_MAP.get(composite_type, []):
                if band_name in seen:
                    continue
                seen.add(band_name)
                ordered.append(band_name)
        return ordered

    @staticmethod
    def _read_processed_band_array(band_path: str) -> np.ndarray:
        dataset = gdal.Open(band_path)
        if dataset is None:
            raise RuntimeError(f"无法打开匀色输入波段: {band_path}")

        band = dataset.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        band_array = band.ReadAsArray().astype(np.float32)
        mask = band.GetMaskBand().ReadAsArray()
        dataset = None

        if mask is not None:
            band_array = np.where(mask == 0, np.nan, band_array)
        if nodata is not None:
            band_array = np.where(band_array == nodata, np.nan, band_array)
        return band_array

    @staticmethod
    def _sample_valid_values(array: np.ndarray, sample_target: int = DISPLAY_BALANCE_SAMPLE_TARGET) -> np.ndarray:
        if array.size == 0:
            return np.asarray([], dtype=np.float32)

        step = max(int(np.sqrt(array.size / max(sample_target, 1))), 1)
        sampled = array[::step, ::step]
        valid = sampled[np.isfinite(sampled)]
        if valid.size == 0 and step > 1:
            valid = array[np.isfinite(array)]
        return valid.astype(np.float32, copy=False)

    def _compute_band_quantiles(self, band_path: str) -> Optional[np.ndarray]:
        band_array = self._read_processed_band_array(band_path)
        valid = self._sample_valid_values(band_array)
        if valid.size == 0:
            return None
        return np.percentile(valid, DISPLAY_BALANCE_PERCENTILES).astype(np.float32)

    def _build_display_balance_stats(
        self,
        scene_inputs: List[SceneInputConfig],
        scene_results: List[Dict],
        display_band_names: List[str],
    ) -> List[Dict]:
        stats: List[Dict] = []
        for scene_input, scene_result in zip(scene_inputs, scene_results):
            processed_bands = scene_result.get("processed_bands") or {}
            band_stats: Dict[str, Dict[str, object]] = {}
            scene_medians: List[float] = []
            for band_name in display_band_names:
                band_path = processed_bands.get(band_name)
                if not band_path:
                    continue
                quantiles = self._compute_band_quantiles(band_path)
                if quantiles is None:
                    continue
                band_stats[band_name] = {
                    "path": band_path,
                    "quantiles": quantiles,
                }
                scene_medians.append(float(quantiles[3]))
            brightness = float(np.mean(scene_medians)) if scene_medians else None
            stats.append({
                "scene_name": scene_input.scene_name,
                "band_stats": band_stats,
                "brightness": brightness,
            })
        return stats

    @staticmethod
    def _select_reference_scene(scene_stats: List[Dict], display_band_names: List[str]) -> Optional[Dict]:
        full_candidates = [
            (index, item)
            for index, item in enumerate(scene_stats)
            if item.get("brightness") is not None
            and all(band_name in (item.get("band_stats") or {}) for band_name in display_band_names)
        ]
        candidates = full_candidates or [
            (index, item)
            for index, item in enumerate(scene_stats)
            if item.get("brightness") is not None
        ]
        if not candidates:
            return None

        brightness_values = [item["brightness"] for _, item in candidates]
        target_brightness = float(np.median(brightness_values))
        reference_index, reference_item = min(
            candidates,
            key=lambda pair: (abs(pair[1]["brightness"] - target_brightness), pair[0]),
        )
        return {
            "index": reference_index,
            "scene_name": reference_item["scene_name"],
            "band_stats": reference_item["band_stats"],
            "brightness": reference_item["brightness"],
        }

    @staticmethod
    def _prepare_interp_knots(source_quantiles: np.ndarray, target_quantiles: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        source = np.asarray(source_quantiles, dtype=np.float32)
        target = np.asarray(target_quantiles, dtype=np.float32)
        if source.shape != target.shape:
            raise RuntimeError("匀色分位点数量不一致")

        unique_source, unique_indices = np.unique(source, return_index=True)
        unique_target = target[unique_indices]
        return unique_source.astype(np.float32), unique_target.astype(np.float32)

    def _write_display_balanced_band(
        self,
        source_path: str,
        output_path: str,
        source_quantiles: np.ndarray,
        target_quantiles: np.ndarray,
    ) -> str:
        source_knots, target_knots = self._prepare_interp_knots(source_quantiles, target_quantiles)
        band_array = self._read_processed_band_array(source_path)
        valid_mask = np.isfinite(band_array)

        balanced = np.array(band_array, dtype=np.float32, copy=True)
        if np.any(valid_mask):
            if source_knots.size <= 1:
                balanced[valid_mask] = target_knots[0]
            else:
                balanced[valid_mask] = np.interp(
                    balanced[valid_mask],
                    source_knots,
                    target_knots,
                ).astype(np.float32)
            balanced_valid = np.clip(
                balanced[valid_mask],
                DISPLAY_BALANCE_CLIP_RANGE[0],
                DISPLAY_BALANCE_CLIP_RANGE[1],
            )
            balanced[valid_mask] = balanced_valid.astype(np.float32, copy=False)
        balanced[~valid_mask] = np.nan

        Landsat8Processor._write_processed_band(output_path, source_path, balanced)
        return output_path

    def _build_display_balance_overrides(
        self,
        config: BatchJobConfig,
        scene_results: List[Dict],
        output_root: Path,
        processed_bands: Dict[str, str],
        progress_callback: Optional[Callable[[Dict], None]] = None,
    ) -> Tuple[Dict[str, Dict[str, str]], bool, str]:
        display_composites = self._filter_display_composites(config.create_composites)
        if not display_composites or not config.display_balance_enabled:
            return {}, False, ""

        display_band_names = self._collect_display_band_names(display_composites)
        if not display_band_names:
            return {}, False, ""

        self._update_mosaic_progress(progress_callback, 80, "正在分析显示匀色参考景")
        scene_stats = self._build_display_balance_stats(config.scene_inputs, scene_results, display_band_names)
        reference_scene = self._select_reference_scene(scene_stats, display_band_names)
        if reference_scene is None:
            logger.warning("显示匀色已跳过：无法为镶嵌结果选择参考景")
            return {}, False, ""

        display_root = output_root / "_display_balance"
        display_root.mkdir(parents=True, exist_ok=True)
        balanced_scene_band_paths: Dict[str, List[str]] = defaultdict(list)

        for scene_stat in scene_stats:
            scene_band_stats = scene_stat.get("band_stats") or {}
            scene_output_dir = display_root / scene_stat["scene_name"]
            scene_output_dir.mkdir(parents=True, exist_ok=True)
            for band_name in display_band_names:
                band_info = scene_band_stats.get(band_name)
                source_path = band_info.get("path") if band_info else None
                if not source_path:
                    continue

                reference_band_info = (reference_scene.get("band_stats") or {}).get(band_name)
                if not reference_band_info or scene_stat["scene_name"] == reference_scene["scene_name"]:
                    balanced_scene_band_paths[band_name].append(source_path)
                    continue

                balanced_path = scene_output_dir / f"{band_name}_balanced_processed.tif"
                self._write_display_balanced_band(
                    source_path,
                    str(balanced_path),
                    band_info["quantiles"],
                    reference_band_info["quantiles"],
                )
                balanced_scene_band_paths[band_name].append(str(balanced_path))

        self._update_mosaic_progress(progress_callback, 84, "正在生成匀色后的显示波段镶嵌")
        balanced_mosaics: Dict[str, str] = {}
        for band_name in display_band_names:
            input_paths = balanced_scene_band_paths.get(band_name) or []
            if not input_paths:
                continue

            mosaic_path = display_root / f"{band_name}_display_processed.tif"
            mosaic_rasters(input_paths, str(mosaic_path), reference_path=input_paths[0])

            final_path = mosaic_path
            if config.clip_extent or config.clip_shapefile:
                clipped_path = display_root / f"{band_name}_display_clipped.tif"
                clip_raster(
                    str(mosaic_path),
                    str(clipped_path),
                    extent=config.clip_extent,
                    shapefile=config.clip_shapefile,
                )
                final_path = clipped_path
                if not config.keep_intermediate:
                    mosaic_path.unlink(missing_ok=True)

            balanced_mosaics[band_name] = str(final_path)

        if not balanced_mosaics:
            return {}, False, reference_scene["scene_name"]

        composite_overrides = {
            composite_type: {**processed_bands, **balanced_mosaics}
            for composite_type in display_composites
        }
        return composite_overrides, True, reference_scene["scene_name"]

    def _execute_mosaic_job(
        self,
        config: BatchJobConfig,
        progress_callback: Optional[Callable[[Dict], None]] = None,
    ) -> Dict:
        if not config.scene_inputs:
            raise RuntimeError("镶嵌任务缺少输入场景")

        output_root = Path(config.output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        intermediate_root = output_root / "_intermediate"
        intermediate_root.mkdir(parents=True, exist_ok=True)

        processor = Landsat8Processor()
        scene_results: List[Dict] = []
        total_scenes = len(config.scene_inputs)
        self._update_mosaic_progress(progress_callback, 5, "开始执行镶嵌任务")

        for index, scene_input in enumerate(config.scene_inputs, start=1):
            scene_output_dir = intermediate_root / scene_input.scene_name
            scene_output_dir.mkdir(parents=True, exist_ok=True)
            self._update_mosaic_progress(
                progress_callback,
                10 + int(35 * (index - 1) / max(total_scenes, 1)),
                f"预处理场景 {scene_input.scene_name} ({index}/{total_scenes})",
            )
            scene_config = self._scene_input_to_job_config(
                scene_input,
                str(scene_output_dir),
                config.template,
                config.atm_correction_method,
                config.apply_cloud_mask,
            )
            scene_result = self._execute_scene_job(scene_config)
            if scene_result.get("status") != "success":
                error_message = scene_result.get("error") or f"场景 {scene_input.scene_name} 预处理失败"
                raise RuntimeError(error_message)
            scene_results.append(scene_result)

        skipped_bands = sorted({
            band_name
            for result in scene_results
            for band_name in (result.get("skipped_bands") or [])
        })

        grouped_band_paths: Dict[str, List[str]] = defaultdict(list)
        for result in scene_results:
            for band_name, band_path in (result.get("processed_bands") or {}).items():
                grouped_band_paths[band_name].append(band_path)
        if not grouped_band_paths:
            raise RuntimeError("镶嵌任务未产生可用波段")

        processed_bands: Dict[str, str] = {}
        band_names = sorted(grouped_band_paths)
        total_bands = len(band_names)
        self._update_mosaic_progress(progress_callback, 48, "开始执行同名波段镶嵌")

        for index, band_name in enumerate(band_names, start=1):
            input_paths = grouped_band_paths[band_name]
            mosaic_path = output_root / f"{band_name}_processed.tif"
            mosaic_rasters(input_paths, str(mosaic_path), reference_path=input_paths[0])

            final_path = mosaic_path
            if config.clip_extent or config.clip_shapefile:
                clipped_path = output_root / f"{band_name}_clipped.tif"
                clip_raster(
                    str(mosaic_path),
                    str(clipped_path),
                    extent=config.clip_extent,
                    shapefile=config.clip_shapefile,
                )
                final_path = clipped_path
                if not config.keep_intermediate:
                    mosaic_path.unlink(missing_ok=True)

            processed_bands[band_name] = str(final_path)
            self._update_mosaic_progress(
                progress_callback,
                50 + int(25 * index / max(total_bands, 1)),
                f"已完成波段 {band_name} 镶嵌 ({index}/{total_bands})",
            )

        composites: Dict[str, str] = {}
        composite_band_overrides: Dict[str, Dict[str, str]] = {}
        display_balance_applied = False
        display_balance_reference_scene = ""
        if config.create_composites or (config.custom_index_formula and config.custom_index_formula.strip()):
            composite_band_overrides, display_balance_applied, display_balance_reference_scene = self._build_display_balance_overrides(
                config,
                scene_results,
                output_root,
                processed_bands,
                progress_callback,
            )
            self._update_mosaic_progress(progress_callback, 85, "开始生成镶嵌结果的合成与指数")
            composites = processor._create_requested_composites(
                processed_bands,
                str(output_root),
                config.create_composites,
                config.custom_index_formula,
                config.custom_index_name,
                composite_band_overrides=composite_band_overrides,
            )

        if not config.keep_intermediate:
            shutil.rmtree(intermediate_root, ignore_errors=True)
            shutil.rmtree(output_root / "_display_balance", ignore_errors=True)

        return {
            "status": "success",
            "processed_bands": processed_bands,
            "composites": composites,
            "cloud_mask": None,
            "metadata": {
                "job_kind": JobKind.MOSAIC.value,
                "scene_count": total_scenes,
                "display_balance_enabled": bool(config.display_balance_enabled),
                "display_balance_applied": bool(display_balance_applied),
                "display_balance_reference_scene": display_balance_reference_scene or "",
            },
            "summary": {
                "scene_count": total_scenes,
                "band_count": total_bands,
            },
            "atm_correction_method": config.atm_correction_method,
            "skipped_bands": skipped_bands,
            "product_level": config.product_level,
            "processing_mode": "mosaic",
        }

    def _handle_job_failure(self, job: BatchJob, error: str):
        """处理任务失败"""
        with self.lock:
            job.error = error
            job.retry_count += 1

            # 判断是否需要重试
            if job.retry_count <= job.max_retries:
                logger.info("Job %s retry %d/%d", job.job_id, job.retry_count, job.max_retries)
                job.status = TaskStatus.QUEUED
                job.updated_at = self._utc_now()
                self._enqueue_job(job)
            else:
                logger.error("Job %s failed after %d retries", job.job_id, job.retry_count)
                job.status = TaskStatus.FAILED
                job.completed_at = self._utc_now()
                job.updated_at = job.completed_at

    def _get_priority_value(self, priority: TaskPriority) -> int:
        """获取优先级数值（用于排序）"""
        priority_map = {
            TaskPriority.HIGH: 0,
            TaskPriority.MEDIUM: 1,
            TaskPriority.LOW: 2,
        }
        return priority_map.get(priority, 1)

    def submit_batch(
        self,
        batch_name: str,
        jobs_config: List[BatchJobConfig],
        priority: TaskPriority = TaskPriority.MEDIUM,
        max_retries: int = 3,
    ) -> str:
        """提交批量任务

        Args:
            batch_name: 批次名称
            jobs_config: 任务配置列表
            priority: 任务优先级
            max_retries: 最大重试次数

        Returns:
            batch_id: 批次ID
        """
        batch_id = str(uuid.uuid4())
        created_at = self._utc_now()
        validated_configs = [self.path_access.validate_batch_job_config(config) for config in jobs_config]

        job_list = []
        for config in validated_configs:
            job_id = str(uuid.uuid4())
            job = BatchJob(
                job_id=job_id,
                batch_id=batch_id,
                config=config,
                status=TaskStatus.QUEUED,
                priority=priority,
                max_retries=max_retries,
                created_at=created_at,
                updated_at=created_at,
            )
            job_list.append(job)

            with self.lock:
                self.jobs[job_id] = job

            self._enqueue_job(job)

        # 保存批次信息
        with self.lock:
            self.batches[batch_id] = {
                "batch_id": batch_id,
                "batch_name": batch_name,
                "job_ids": [job.job_id for job in job_list],
                "created_at": created_at,
            }

        logger.info("Submitted batch %s with %d jobs", batch_id, len(job_list))
        return batch_id

    def get_batch_status(self, batch_id: str) -> Optional[BatchStatusResponse]:
        """获取批次状态"""
        with self.lock:
            batch_info = self.batches.get(batch_id)
            if not batch_info:
                return None

            job_ids = batch_info["job_ids"]
            jobs = [self.jobs[jid] for jid in job_ids if jid in self.jobs]

            if not jobs:
                return None

            total_jobs = len(jobs)
            completed_jobs = self._count_jobs_by_status(jobs, TaskStatus.SUCCESS)
            failed_jobs = self._count_jobs_by_status(jobs, TaskStatus.FAILED)
            running_jobs = self._count_jobs_by_status(jobs, TaskStatus.RUNNING)
            pending_jobs = self._count_jobs_by_status(jobs, {TaskStatus.PENDING, TaskStatus.QUEUED})
            overall_progress = sum(j.progress for j in jobs) // total_jobs if total_jobs > 0 else 0

            return BatchStatusResponse(
                batch_id=batch_id,
                batch_name=batch_info["batch_name"],
                total_jobs=total_jobs,
                completed_jobs=completed_jobs,
                failed_jobs=failed_jobs,
                running_jobs=running_jobs,
                pending_jobs=pending_jobs,
                overall_progress=overall_progress,
                jobs=jobs,
            )

    def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        """获取任务状态"""
        with self.lock:
            return self.jobs.get(job_id)

    def list_jobs(self, status: Optional[TaskStatus] = None) -> List[BatchJob]:
        """列出所有任务。"""
        with self.lock:
            jobs = list(self.jobs.values())
        if status is None:
            return jobs
        expected = getattr(status, "value", status)
        return [job for job in jobs if getattr(job.status, "value", job.status) == expected]

    def get_batch_name(self, batch_id: str) -> str:
        """根据批次 ID 获取批次名称。"""
        with self.lock:
            batch_info = self.batches.get(batch_id) or {}
        return str(batch_info.get("batch_name") or "")

    def _write_job_manifest(self, job: BatchJob, result: Dict) -> None:
        """将成功任务的结果摘要写入输出目录。"""
        batch_name = self.get_batch_name(job.batch_id)
        task_type = "mosaic" if job.config.job_kind == JobKind.MOSAIC else "batch"
        if task_type == "mosaic":
            title = f"镶嵌任务 · {job.config.scene_name}" if job.config.scene_name else "镶嵌任务"
        else:
            title = job.config.scene_name or batch_name or Path(job.config.output_dir).name
            if batch_name and job.config.scene_name and batch_name != job.config.scene_name:
                title = f"{batch_name} / {job.config.scene_name}"

        write_task_manifest(
            task_type=task_type,
            title=title,
            output_dir=job.config.output_dir,
            result=result,
            job_id=job.job_id,
            batch_id=job.batch_id,
            created_at=job.created_at,
            completed_at=job.completed_at or job.updated_at,
            summary=result.get("summary") or {},
        )

    def pause_job(self, job_id: str) -> bool:
        """暂停任务（仅对排队中的任务有效）"""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return False

            if job.status in [TaskStatus.PENDING, TaskStatus.QUEUED]:
                job.status = TaskStatus.PAUSED
                job.updated_at = self._utc_now()
                self.paused_jobs[job_id] = job
                logger.info("Job %s paused", job_id)
                return True

            return False

    def resume_job(self, job_id: str) -> bool:
        """恢复任务"""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job.status != TaskStatus.PAUSED:
                return False

            job.status = TaskStatus.QUEUED
            job.updated_at = self._utc_now()
            self.paused_jobs.pop(job_id, None)
            self._enqueue_job(job)

            logger.info("Job %s resumed", job_id)
            return True

    def cancel_job(self, job_id: str) -> bool:
        """取消任务"""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return False

            if job.status in [TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.PAUSED]:
                job.status = TaskStatus.CANCELLED
                job.completed_at = self._utc_now()
                job.updated_at = job.completed_at
                self.paused_jobs.pop(job_id, None)
                logger.info("Job %s cancelled", job_id)
                return True

            # 运行中的任务无法取消（需要增强实现）
            return False

    def list_batches(self) -> List[Dict]:
        """列出所有批次"""
        with self.lock:
            return [
                {
                    "batch_id": bid,
                    "batch_name": info["batch_name"],
                    "job_count": len(info["job_ids"]),
                    "created_at": info["created_at"],
                }
                for bid, info in self.batches.items()
            ]

    def shutdown(self):
        """关闭批量任务管理器"""
        logger.info("Shutting down...")
        self.shutdown_flag.set()
        for worker in self.workers:
            worker.join(timeout=5)
        logger.info("Shutdown complete")
