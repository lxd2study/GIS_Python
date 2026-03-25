"""Landsat scene search and download service."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

import httpx
import planetary_computer
import pystac_client
from fastapi.responses import StreamingResponse

from ..core.config import settings
from ..core.models import (
    LandsatAuthRequest,
    LandsatDownloadTaskCreateRequest,
    LandsatSearchRequest,
)

logger = logging.getLogger(__name__)

DOWNLOAD_CHUNK_SIZE = 1024 * 1024


class LandsatDownloadService:
    """Encapsulates Landsat search, auth and download task management."""

    EROS_LOGIN_URL = "https://ers.cr.usgs.gov/login"

    STAC_CONFIGS = {
        "L2": {
            "url": "https://planetarycomputer.microsoft.com/api/stac/v1",
            "collection": "landsat-c2-l2",
            "sign": True,
            "title": "Collection 2 Level-2",
            "description": "已完成大气校正与表面反射率处理，适合直接分析。",
            "auth_required": False,
        },
        "L1": {
            "url": "https://landsatlook.usgs.gov/stac-server",
            "collection": "landsat-c2l1",
            "sign": False,
            "title": "Collection 2 Level-1",
            "description": "原始级产品，适合保留完整原始数据链路。",
            "auth_required": True,
        },
    }

    BAND_DISPLAY = {
        "coastal": "B1 - 海岸/气溶胶",
        "blue": "B2 - 蓝",
        "green": "B3 - 绿",
        "red": "B4 - 红",
        "nir08": "B5 - 近红外",
        "swir16": "B6 - SWIR1",
        "swir22": "B7 - SWIR2",
        "lwir11": "B10 - 热红外 TIRS1",
        "lwir12": "B11 - 热红外 TIRS2",
        "qa_pixel": "QA_PIXEL - 质量评估",
        "B1": "B1 - 海岸/气溶胶",
        "B2": "B2 - 蓝",
        "B3": "B3 - 绿",
        "B4": "B4 - 红",
        "B5": "B5 - 近红外",
        "B6": "B6 - SWIR1",
        "B7": "B7 - SWIR2",
        "B8": "B8 - 全色",
        "B9": "B9 - 卷云",
        "B10": "B10 - 热红外 TIRS1",
        "B11": "B11 - 热红外 TIRS2",
        "QA_PIXEL": "QA_PIXEL - 质量评估",
        "MTL.txt": "MTL.txt - 元数据文件",
        "mtl.txt": "MTL.txt - 元数据文件",
    }

    SKIP_ASSETS = {
        "rendered_preview",
        "tilejson",
        "thumbnail",
        "overview",
        "mtl.json",
        "mtl.xml",
        "ang",
        "qa_radsat",
        "ANG.txt",
        "MTL.json",
    }
    EXTRA_ASSETS = {"MTL.txt", "mtl.txt"}
    THUMB_KEYS = ("rendered_preview", "thumbnail", "reduced_resolution_browse")

    def __init__(
        self,
        *,
        download_dir: Optional[Path] = None,
        http_timeout: Optional[int] = None,
        eros_username: Optional[str] = None,
        eros_password: Optional[str] = None,
        max_concurrent_downloads: int = 3,
    ) -> None:
        self.download_dir = Path(download_dir or settings.LANDSAT_DOWNLOAD_DIR)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.http_timeout = http_timeout or settings.HTTP_TIMEOUT
        self.download_timeout = max(self.http_timeout, 3600)

        self._eros_username = eros_username if eros_username is not None else settings.LANDSAT_EROS_USERNAME
        self._eros_password = eros_password if eros_password is not None else settings.LANDSAT_EROS_PASSWORD
        self._eros_cookies: Dict[str, str] = {}
        self._eros_cookie_expires = datetime.min.replace(tzinfo=timezone.utc)

        self._download_semaphore = asyncio.Semaphore(max_concurrent_downloads)
        self._tasks: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _is_usgs_url(cls, url: str) -> bool:
        return "landsatlook.usgs.gov" in url or "usgs-landsat" in url

    @staticmethod
    def _format_timestamp(timestamp: datetime) -> str:
        return timestamp.isoformat().replace("+00:00", "Z")

    def list_collections(self) -> Dict:
        """Return frontend-facing collection metadata."""
        collections = []
        for level, info in self.STAC_CONFIGS.items():
            collections.append(
                {
                    "level": level,
                    "title": info["title"],
                    "description": info["description"],
                    "collection": info["collection"],
                    "stac_url": info["url"],
                    "auth_required": info["auth_required"],
                }
            )

        return {
            "collections": collections,
            "download_dir": str(self.download_dir),
        }

    def get_auth_status(self) -> Dict:
        configured = bool(self._eros_username and self._eros_password)
        return {
            "configured": configured,
            "username": self._eros_username if configured else "",
        }

    async def configure_earthdata(self, request: LandsatAuthRequest) -> Dict:
        username = request.username.strip()
        password = request.password
        if not username or not password:
            raise ValueError("用户名和密码不能为空")

        if not await self._try_login(username, password):
            raise PermissionError("EROS 登录失败，请检查账号密码")

        self._eros_username = username
        self._eros_password = password
        return {"ok": True, "username": username}

    async def search(self, request: LandsatSearchRequest) -> Dict:
        level = request.level.upper()
        config = self.STAC_CONFIGS.get(level, self.STAC_CONFIGS["L2"])
        catalog_kwargs = {"modifier": planetary_computer.sign_inplace} if config["sign"] else {}
        catalog = pystac_client.Client.open(config["url"], **catalog_kwargs)
        raw_search = catalog.search(
            collections=[config["collection"]],
            bbox=request.bbox,
            datetime=f"{request.start_date}/{request.end_date}",
            max_items=request.limit * 5,
        )

        items = []
        for item in raw_search.items():
            platform = str(item.properties.get("platform", "")).lower().replace("_", "-")
            if "landsat-8" not in platform:
                continue

            cloud_cover = item.properties.get("eo:cloud_cover")
            if cloud_cover is not None and request.max_cloud_cover < 100 and cloud_cover > request.max_cloud_cover:
                continue

            items.append(
                {
                    "id": item.id,
                    "level": level,
                    "datetime": item.datetime.isoformat() if item.datetime else None,
                    "cloud_cover": round(cloud_cover, 1) if cloud_cover is not None else None,
                    "bbox": item.bbox,
                    "thumbnail": self._pick_thumbnail(item),
                    "assets": self._parse_assets(item, config),
                    "path": item.properties.get("landsat:wrs_path"),
                    "row": item.properties.get("landsat:wrs_row"),
                }
            )
            if len(items) >= request.limit:
                break

        return {"items": items, "count": len(items)}

    async def sign_url(self, url: str) -> Dict:
        if self._is_usgs_url(url):
            return {"signed_url": url}
        return {"signed_url": planetary_computer.sign(url)}

    async def create_proxy_download_response(self, url: str, filename: str) -> StreamingResponse:
        final_url, cookies = await self._resolve_download_url(url)
        client = httpx.AsyncClient(timeout=self.download_timeout, follow_redirects=True, cookies=cookies)

        try:
            response = await client.send(client.build_request("GET", final_url), stream=True)
            response.raise_for_status()
        except Exception:
            await client.aclose()
            raise

        safe_filename = filename.replace('"', "_") or "landsat_asset.bin"
        headers = {
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Content-Type": response.headers.get("content-type", "application/octet-stream"),
        }
        if "content-length" in response.headers:
            headers["Content-Length"] = response.headers["content-length"]

        async def stream_file():
            try:
                async for chunk in response.aiter_bytes(DOWNLOAD_CHUNK_SIZE):
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        return StreamingResponse(stream_file(), headers=headers)

    async def create_download_tasks(self, request: LandsatDownloadTaskCreateRequest) -> Dict:
        created_ids = []
        for item in request.items:
            task_id = uuid.uuid4().hex[:10]
            task_record = {
                "id": task_id,
                "scene_id": item.scene_id,
                "band": item.band,
                "filename": item.filename,
                "url": item.url,
                "mode": request.mode,
                "status": "pending",
                "progress": 0,
                "size_total": 0,
                "size_downloaded": 0,
                "error": None,
                "local_path": None,
                "created_at": self._format_timestamp(self._utc_now()),
                "updated_at": self._format_timestamp(self._utc_now()),
            }
            with self._lock:
                self._tasks[task_id] = task_record

            created_ids.append(task_id)
            # 服务端模式立即交给后台协程，前端只负责轮询状态即可。
            if request.mode == "server":
                asyncio.create_task(self._download_in_background(task_id))

        return {"task_ids": created_ids, "count": len(created_ids)}

    def list_download_tasks(self) -> Dict:
        with self._lock:
            tasks = [task.copy() for task in self._tasks.values()]
        tasks.sort(key=lambda item: item["created_at"], reverse=True)
        return {"tasks": tasks}

    def get_download_task(self, task_id: str) -> Optional[Dict]:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.copy() if task else None

    def clear_completed_tasks(self) -> Dict:
        terminal_states = {"completed", "failed", "cancelled"}
        deleted = 0
        with self._lock:
            task_ids = [task_id for task_id, task in self._tasks.items() if task["status"] in terminal_states]
            for task_id in task_ids:
                deleted += 1
                self._tasks.pop(task_id, None)
        return {"deleted": deleted}

    def cancel_download_task(self, task_id: str) -> Dict:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise KeyError(task_id)

            if task["status"] in {"pending", "downloading"}:
                task["status"] = "cancelled"
                task["updated_at"] = self._format_timestamp(self._utc_now())

        return {"ok": True, "task_id": task_id}

    async def build_task_file_response(self, task_id: str) -> StreamingResponse:
        task = self.get_download_task(task_id)
        if not task:
            raise KeyError(task_id)
        if task["status"] != "completed" or not task["local_path"]:
            raise ValueError("文件尚未准备好")

        file_path = Path(task["local_path"])
        if not file_path.exists():
            raise FileNotFoundError(str(file_path))

        media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        safe_filename = task["filename"].replace('"', "_")

        def iter_file():
            with open(file_path, "rb") as file_obj:
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

    async def _download_in_background(self, task_id: str) -> None:
        async with self._download_semaphore:
            task = self.get_download_task(task_id)
            if not task or task["status"] == "cancelled":
                return

            self._update_task(task_id, status="downloading", progress=0, error=None)
            target_path: Optional[Path] = None

            try:
                final_url, cookies = await self._resolve_download_url(task["url"])
                target_dir = self.download_dir / task["scene_id"]
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / task["filename"]

                async with httpx.AsyncClient(
                    timeout=self.download_timeout,
                    follow_redirects=True,
                    cookies=cookies,
                ) as client:
                    async with client.stream("GET", final_url) as response:
                        response.raise_for_status()
                        total_size = int(response.headers.get("content-length", 0))
                        self._update_task(task_id, size_total=total_size, size_downloaded=0)

                        downloaded = 0
                        with open(target_path, "wb") as file_obj:
                            async for chunk in response.aiter_bytes(DOWNLOAD_CHUNK_SIZE):
                                current_task = self.get_download_task(task_id)
                                if not current_task or current_task["status"] == "cancelled":
                                    break

                                file_obj.write(chunk)
                                downloaded += len(chunk)
                                progress = int(downloaded / total_size * 100) if total_size else 0
                                self._update_task(
                                    task_id,
                                    size_downloaded=downloaded,
                                    progress=progress,
                                )

                current_task = self.get_download_task(task_id)
                if not current_task or current_task["status"] == "cancelled":
                    if target_path:
                        target_path.unlink(missing_ok=True)
                    return

                final_size = target_path.stat().st_size if target_path and target_path.exists() else 0
                self._update_task(
                    task_id,
                    status="completed",
                    progress=100,
                    local_path=str(target_path) if target_path else None,
                    size_downloaded=final_size,
                )
            except Exception as exc:
                logger.error("Landsat 下载任务失败 %s: %s", task_id, exc, exc_info=True)
                if target_path:
                    target_path.unlink(missing_ok=True)
                self._update_task(task_id, status="failed", error=str(exc))

    def _update_task(self, task_id: str, **changes) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task.update(changes)
            task["updated_at"] = self._format_timestamp(self._utc_now())

    async def _resolve_download_url(self, url: str) -> Tuple[str, Dict[str, str]]:
        if self._is_usgs_url(url):
            return url, await self._get_usgs_cookies()
        return planetary_computer.sign(url), {}

    async def _get_usgs_cookies(self) -> Dict[str, str]:
        if not await self._ensure_eros_login():
            raise PermissionError("当前未配置可用的 EarthData / EROS 账号")
        return dict(self._eros_cookies)

    async def _ensure_eros_login(self) -> bool:
        now = self._utc_now()
        if self._eros_cookies and now < self._eros_cookie_expires:
            return True
        if not self._eros_username or not self._eros_password:
            return False
        return await self._try_login(self._eros_username, self._eros_password)

    async def _try_login(self, username: str, password: str) -> bool:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            login_page = await client.get(self.EROS_LOGIN_URL)
            csrf_token = self._extract_csrf_token(login_page.text)
            payload = {
                "username": username,
                "password": password,
                "csrf": csrf_token,
            }
            response = await client.post(self.EROS_LOGIN_URL, data=payload)
            if "login" in str(response.url) or response.status_code != 200:
                return False

            self._eros_cookies = dict(client.cookies)
            self._eros_cookie_expires = self._utc_now() + timedelta(hours=1)
            return True

    @staticmethod
    def _extract_csrf_token(html: str) -> str:
        patterns = (
            r'<input[^>]+name=["\']csrf["\'][^>]+value=["\']([^"\']+)["\']',
            r'<input[^>]+value=["\']([^"\']+)["\'][^>]+name=["\']csrf["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return ""

    @classmethod
    def _pick_thumbnail(cls, item) -> Optional[str]:
        for key in cls.THUMB_KEYS:
            if key in item.assets:
                return item.assets[key].href
        return None

    @classmethod
    def _parse_assets(cls, item, config: Dict) -> Dict:
        assets = {}
        for key, asset in item.assets.items():
            if key in cls.SKIP_ASSETS:
                continue

            media_type = getattr(asset, "media_type", "") or ""
            if "tiff" not in media_type.lower() and key not in cls.BAND_DISPLAY and key not in cls.EXTRA_ASSETS:
                continue

            assets[key] = {
                "href": asset.href,
                "label": cls.BAND_DISPLAY.get(key, key),
                "signed": config["sign"],
            }
        return assets
