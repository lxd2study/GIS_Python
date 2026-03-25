"""进度管理服务"""

import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Union

from ..core.constants import PROGRESS_STEPS
from ..core.models import ProcessingResult, ProgressRecord, ProgressStep


class ProgressManager:
    """进度管理器（轮询模式）"""

    def __init__(self):
        self.progress_tasks: Dict[str, ProgressRecord] = {}
        self.lock = threading.Lock()

    def _build_step_state(self) -> list:
        """构建步骤状态列表"""
        return [ProgressStep(**step) for step in PROGRESS_STEPS]

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def init_progress(self, job_id: str) -> ProgressRecord:
        """初始化进度记录"""
        now = self._utc_now()
        record = ProgressRecord(
            job_id=job_id,
            status="pending",
            progress=0,
            current_step=None,
            detail="等待开始",
            steps=self._build_step_state(),
            created_at=now,
            updated_at=now,
        )
        with self.lock:
            self.progress_tasks[job_id] = record
        return record

    def update_progress(
        self,
        job_id: str,
        step_id: str = None,
        step_status: str = None,
        progress: int = None,
        detail: str = None,
        status: str = None,
        result: Union[dict, ProcessingResult] = None,
        error: str = None,
    ):
        """更新进度"""
        with self.lock:
            task = self.progress_tasks.get(job_id)
            if not task:
                return

            if step_id:
                if step_status == "active":
                    for step in task.steps:
                        if step.status == "active" and step.id != step_id:
                            step.status = "completed"

                for step in task.steps:
                    if step.id == step_id:
                        if step_status:
                            step.status = step_status
                        if detail:
                            step.detail = detail
                        step.time = datetime.now().strftime("%H:%M:%S")
                task.current_step = step_id

            if progress is not None:
                task.progress = progress

            if detail:
                task.detail = detail

            if result is not None:
                if isinstance(result, dict):
                    task.result = ProcessingResult(**result)
                else:
                    task.result = result

            if error:
                task.error = error

            if status:
                task.status = status
                if status == "success":
                    for step in task.steps:
                        if step.status not in ["completed", "exception"]:
                            step.status = "completed"
                    task.progress = 100
                if status == "error":
                    for step in task.steps:
                        if step.status == "active":
                            step.status = "exception"
                    task.progress = max(task.progress, 100)

            task.updated_at = self._utc_now()

    def _task_to_dict(self, job_id: str) -> dict:
        """将任务转为可序列化的字典"""
        with self.lock:
            task = self.progress_tasks.get(job_id)
            if not task:
                return {}
            return {
                "job_id": task.job_id,
                "status": task.status,
                "progress": task.progress,
                "current_step": task.current_step,
                "detail": task.detail,
                "steps": [
                    {
                        "id": step.id,
                        "title": step.title,
                        "status": step.status,
                        "detail": step.detail,
                        "time": step.time,
                    }
                    for step in task.steps
                ],
                "error": task.error,
                "updated_at": task.updated_at,
            }

    def get_progress(self, job_id: str) -> Optional[ProgressRecord]:
        """获取进度记录"""
        with self.lock:
            return self.progress_tasks.get(job_id)

    def remove_progress(self, job_id: str):
        """移除进度记录"""
        with self.lock:
            self.progress_tasks.pop(job_id, None)
