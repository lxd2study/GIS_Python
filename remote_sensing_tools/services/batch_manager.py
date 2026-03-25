"""批量任务管理器"""

import logging
import queue
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..core.models import (
    BatchJob,
    BatchJobConfig,
    BatchStatusResponse,
    TaskPriority,
    TaskStatus,
    ProcessingResult,
)
from ..core.processor import Landsat8Processor
from ..utils.file_utils import collect_band_paths

logger = logging.getLogger(__name__)


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
            band_paths = collect_band_paths(job.config.band_dir)
            processor = Landsat8Processor()

            def progress_callback(progress_info: Dict):
                with self.lock:
                    if 'progress' in progress_info:
                        job.progress = progress_info['progress']
                    job.updated_at = self._utc_now()

            result = processor.one_click_preprocess(
                band_paths=band_paths,
                output_dir=job.config.output_dir,
                mtl_path=job.config.mtl_file,
                clip_extent=job.config.clip_extent,
                clip_shapefile=job.config.clip_shapefile,
                create_composites=job.config.create_composites,
                apply_cloud_mask=job.config.apply_cloud_mask,
                qa_band_path=job.config.qa_band,
                atm_correction_method=job.config.atm_correction_method,
                custom_index_formula=job.config.custom_index_formula,
                custom_index_name=job.config.custom_index_name,
                progress_callback=progress_callback,
            )

            if result.get("status") != "success":
                error_message = result.get("error") or "批处理预处理返回失败状态"
                raise RuntimeError(error_message)

            with self.lock:
                self._mark_job_success(job, result)

            logger.info("Job %s completed successfully", job.job_id)

        except Exception as e:
            logger.error("Job %s failed: %s", job.job_id, e)
            self._handle_job_failure(job, str(e))

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

        job_list = []
        for config in jobs_config:
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
