"""Batch processing route registration."""

from __future__ import annotations

import logging
from typing import Dict

from fastapi import FastAPI, HTTPException

from ..core.models import BatchSubmitRequest, GraphSubmitRequest, TaskQueueItem
from ..services.batch_manager import BatchJobManager
from ..services.graph_executor import GraphExecutor
from ..services.templates import ProcessingTemplates
from ..utils.path_policy import PathAccessError

logger = logging.getLogger(__name__)


def _raise_path_access_http_error(exc: PathAccessError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


def register_batch_routes(app: FastAPI, batch_manager: BatchJobManager) -> None:
    """Register batch routes without changing their public paths."""

    @app.get("/batch/templates")
    def list_processing_templates() -> Dict:
        return {"templates": ProcessingTemplates.list_templates()}

    @app.post("/batch/submit_graph")
    def submit_graph_jobs(request: GraphSubmitRequest) -> Dict:
        try:
            executor = GraphExecutor()
            nodes = [n.model_dump() for n in request.nodes]
            edges = [e.model_dump() for e in request.edges]
            configs, errors = executor.build_job_configs(nodes, edges)

            if errors:
                raise HTTPException(status_code=400, detail="; ".join(errors))
            if not configs:
                raise HTTPException(status_code=400, detail="未生成任何任务配置，请检查画布")

            processed_configs = [ProcessingTemplates.apply_template(c) for c in configs]
            batch_id = batch_manager.submit_batch(
                batch_name=request.batch_name,
                jobs_config=processed_configs,
                priority=request.priority,
                max_retries=request.max_retries if request.auto_retry else 0,
            )
            return {
                "batch_id": batch_id,
                "batch_name": request.batch_name,
                "total_jobs": len(configs),
                "status": "submitted",
                "message": f"成功提交 {len(configs)} 个任务到批量处理队列",
            }
        except HTTPException:
            raise
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)
        except Exception as exc:
            logger.error("图任务提交失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"图任务提交失败: {exc}")

    @app.post("/batch/submit")
    def submit_batch_jobs(request: BatchSubmitRequest) -> Dict:
        try:
            processed_configs = [
                ProcessingTemplates.apply_template(job_config)
                for job_config in request.jobs
            ]
            batch_id = batch_manager.submit_batch(
                batch_name=request.batch_name,
                jobs_config=processed_configs,
                priority=request.priority,
                max_retries=request.max_retries if request.auto_retry else 0,
            )

            return {
                "batch_id": batch_id,
                "batch_name": request.batch_name,
                "total_jobs": len(request.jobs),
                "status": "submitted",
                "message": f"成功提交 {len(request.jobs)} 个任务到批量处理队列",
            }
        except PathAccessError as exc:
            _raise_path_access_http_error(exc)
        except Exception as exc:
            logger.error("批量任务提交失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"批量任务提交失败: {exc}")

    @app.get("/batch/list")
    def list_batches() -> Dict:
        batches = batch_manager.list_batches()
        return {"batches": batches, "total": len(batches)}

    @app.get("/batch/{batch_id}/status")
    def get_batch_status(batch_id: str) -> Dict:
        status = batch_manager.get_batch_status(batch_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"批次不存在: {batch_id}")
        return status.model_dump()

    @app.get("/batch/job/{job_id}/status")
    def get_job_status(job_id: str) -> Dict:
        job = batch_manager.get_job_status(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"任务不存在: {job_id}")
        return job.model_dump()

    @app.post("/batch/job/{job_id}/pause")
    def pause_job(job_id: str) -> Dict:
        success = batch_manager.pause_job(job_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="无法暂停任务（任务可能不存在或已在运行中）",
            )
        return {"job_id": job_id, "status": "paused", "message": "任务已暂停"}

    @app.post("/batch/job/{job_id}/resume")
    def resume_job(job_id: str) -> Dict:
        success = batch_manager.resume_job(job_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="无法恢复任务（任务可能不存在或未暂停）",
            )
        return {"job_id": job_id, "status": "resumed", "message": "任务已恢复"}

    @app.post("/batch/job/{job_id}/cancel")
    def cancel_job(job_id: str) -> Dict:
        success = batch_manager.cancel_job(job_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="无法取消任务（任务可能不存在或已在运行中）",
            )
        return {"job_id": job_id, "status": "cancelled", "message": "任务已取消"}

    @app.get("/tasks/queue")
    def get_tasks_queue() -> Dict:
        jobs = []
        with batch_manager.lock:
            all_jobs = list(batch_manager.jobs.values())
        for job in all_jobs:
            jobs.append(TaskQueueItem(
                job_id=job.job_id,
                batch_id=job.batch_id,
                scene_name=job.config.scene_name,
                status=job.status,
                progress=job.progress,
                priority=job.priority,
                created_at=job.created_at,
                started_at=job.started_at,
            ).model_dump())
        jobs.sort(key=lambda j: j["created_at"], reverse=True)
        running = sum(1 for j in jobs if j["status"] == "running")
        queued = sum(1 for j in jobs if j["status"] in ("queued", "pending"))
        completed = sum(1 for j in jobs if j["status"] == "success")
        failed = sum(1 for j in jobs if j["status"] == "failed")
        return {
            "jobs": jobs,
            "total": len(jobs),
            "running": running,
            "queued": queued,
            "completed": completed,
            "failed": failed,
        }
