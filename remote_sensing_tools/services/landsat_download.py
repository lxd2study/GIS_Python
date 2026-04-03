"""Imagery scene search and download service with Landsat compatibility wrappers."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple
from urllib.parse import urlsplit

import httpx
import planetary_computer
import pystac_client
from fastapi.responses import StreamingResponse

from ..core.config import settings
from ..core.models import (
    ImageryDownloadTaskCreateRequest,
    ImagerySearchRequest,
    LandsatAuthRequest,
    LandsatProxyRequest,
)

logger = logging.getLogger(__name__)

DOWNLOAD_CHUNK_SIZE = 1024 * 1024
DOWNLOAD_MAX_ATTEMPTS = 4
DOWNLOAD_RETRY_DELAYS = (2, 5, 10)
DOWNLOAD_MAX_RETRIES = len(DOWNLOAD_RETRY_DELAYS)
RETRYABLE_DOWNLOAD_EXCEPTIONS = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.ConnectError,
    httpx.TimeoutException,
)


class DownloadTaskCancelled(Exception):
    """Raised when a download task is cancelled while downloading or waiting to retry."""


class LandsatDownloadService:
    """Encapsulates imagery search, auth and download task management."""

    EROS_LOGIN_URL = "https://ers.cr.usgs.gov/login"

    SENSOR_TITLES = {
        "landsat": "Landsat",
        "sentinel-2": "Sentinel-2",
    }

    PRODUCT_CONFIGS = {
        "landsat": {
            "title": "Landsat",
            "products": {
                "L2": {
                    "url": "https://planetarycomputer.microsoft.com/api/stac/v1",
                    "collection": "landsat-c2-l2",
                    "sign": True,
                    "title": "Collection 2 Level-2",
                    "description": "已完成大气校正与表面反射率处理，适合直接分析。",
                    "auth_required": False,
                    "platform_tokens": ("landsat-8",),
                },
                "L1": {
                    "url": "https://landsatlook.usgs.gov/stac-server",
                    "collection": "landsat-c2l1",
                    "sign": False,
                    "title": "Collection 2 Level-1",
                    "description": "原始级产品，适合保留完整原始数据链路。",
                    "auth_required": True,
                    "platform_tokens": ("landsat-8",),
                },
            },
        },
        "sentinel-2": {
            "title": "Sentinel-2",
            "products": {
                "L2A": {
                    "url": "https://planetarycomputer.microsoft.com/api/stac/v1",
                    "collection": "sentinel-2-l2a",
                    "sign": True,
                    "title": "Level-2A",
                    "description": "地表反射率产品，适合直接分析与波段下载。",
                    "auth_required": False,
                    "platform_tokens": ("sentinel-2a", "sentinel-2b", "sentinel-2c", "sentinel-2"),
                },
            },
        },
    }

    LANDSAT_ASSET_DISPLAY = {
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
        "qa_radsat": "QA_RADSAT - 饱和质量评估",
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
        "QA_RADSAT": "QA_RADSAT - 饱和质量评估",
        "MTL.txt": "MTL.txt - 元数据文件",
        "mtl.txt": "MTL.txt - 元数据文件",
    }

    SENTINEL_ASSET_DISPLAY = {
        "B01": "B01 - 气溶胶",
        "B02": "B02 - 蓝",
        "B03": "B03 - 绿",
        "B04": "B04 - 红",
        "B05": "B05 - 红边 1",
        "B06": "B06 - 红边 2",
        "B07": "B07 - 红边 3",
        "B08": "B08 - 近红外",
        "B8A": "B8A - 窄近红外",
        "B09": "B09 - 水汽",
        "B11": "B11 - SWIR1",
        "B12": "B12 - SWIR2",
        "AOT": "AOT - 气溶胶光学厚度",
        "WVP": "WVP - 水汽",
        "SCL": "SCL - 场景分类",
        "visual": "visual - 真彩色快速浏览",
    }

    SKIP_ASSETS = {
        "rendered_preview",
        "tilejson",
        "thumbnail",
        "overview",
        "mtl.json",
        "mtl.xml",
        "ang",
        "ANG.txt",
        "MTL.json",
        "granule-metadata",
        "product-metadata",
        "inspire-metadata",
        "metadata",
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
        proxy_url: Optional[str] = None,
        no_proxy: Optional[str] = None,
        max_concurrent_downloads: int = 3,
    ) -> None:
        self._default_download_dir = Path(download_dir or settings.LANDSAT_DOWNLOAD_DIR).resolve(strict=False)
        self.download_dir = self._default_download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.http_timeout = http_timeout or settings.HTTP_TIMEOUT
        self.download_timeout = max(self.http_timeout, 3600)
        self._lock = threading.Lock()
        self._initial_proxy_env = {
            key: os.environ.get(key)
            for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy")
        }

        self._eros_username = eros_username if eros_username is not None else settings.LANDSAT_EROS_USERNAME
        self._eros_password = eros_password if eros_password is not None else settings.LANDSAT_EROS_PASSWORD
        self._eros_cookies: Dict[str, str] = {}
        self._eros_cookie_expires = datetime.min.replace(tzinfo=timezone.utc)
        self._proxy_enabled = False
        self._proxy_url = ""
        self._no_proxy = ""
        self._set_proxy_state(
            enabled=bool(proxy_url if proxy_url is not None else settings.LANDSAT_PROXY_URL),
            proxy_url=proxy_url if proxy_url is not None else settings.LANDSAT_PROXY_URL,
            no_proxy=no_proxy if no_proxy is not None else settings.LANDSAT_NO_PROXY,
        )

        self._download_semaphore = asyncio.Semaphore(max_concurrent_downloads)
        self._tasks: Dict[str, Dict] = {}

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _local_today_folder() -> str:
        return datetime.now().astimezone().strftime("%Y-%m-%d")

    @classmethod
    def _is_usgs_url(cls, url: str) -> bool:
        return "landsatlook.usgs.gov" in url or "usgs-landsat" in url

    @staticmethod
    def _format_timestamp(timestamp: datetime) -> str:
        return timestamp.isoformat().replace("+00:00", "Z")

    def list_collections(self, sensor: Optional[str] = None) -> Dict:
        """Return frontend-facing imagery collection metadata."""
        normalized_sensor = None
        if sensor:
            normalized_sensor = str(sensor).strip().lower()
            if normalized_sensor not in self.PRODUCT_CONFIGS:
                raise ValueError(f"不支持的影像类型: {sensor}")

        collections = []
        sensors = []
        for sensor_key, sensor_info in self.PRODUCT_CONFIGS.items():
            if normalized_sensor and sensor_key != normalized_sensor:
                continue

            products = []
            for product_key, info in sensor_info["products"].items():
                entry = {
                    "sensor": sensor_key,
                    "sensor_title": sensor_info["title"],
                    "product": product_key,
                    "title": info["title"],
                    "description": info["description"],
                    "collection": info["collection"],
                    "stac_url": info["url"],
                    "auth_required": info["auth_required"],
                }
                collections.append(entry)
                products.append(dict(entry))

            sensors.append(
                {
                    "sensor": sensor_key,
                    "title": sensor_info["title"],
                    "products": products,
                }
            )

        return {
            "collections": collections,
            "sensors": sensors,
            "download_dir": str(self.download_dir),
        }

    def get_download_dir_status(self) -> Dict:
        with self._lock:
            current_dir = self.download_dir
            default_dir = self._default_download_dir
        return {
            "download_dir": str(current_dir),
            "default_download_dir": str(default_dir),
        }

    def get_default_download_dir(self) -> Path:
        with self._lock:
            return self._default_download_dir

    def configure_download_dir(self, download_dir: Optional[Path] = None) -> Dict:
        next_dir = Path(download_dir or self._default_download_dir).resolve(strict=False)
        next_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self.download_dir = next_dir
        return self.get_download_dir_status()

    @classmethod
    def _get_product_config(cls, *, sensor: str, product: str) -> Dict:
        sensor_key = cls._normalize_sensor(explicit_sensor=sensor)
        sensor_info = cls.PRODUCT_CONFIGS.get(sensor_key)
        if not sensor_info:
            raise ValueError(f"不支持的影像类型: {sensor}")

        requested_product = str(product or "").strip().upper()
        product_key = requested_product or cls._normalize_product(sensor=sensor_key, explicit_product=product)
        product_info = sensor_info["products"].get(product_key)
        if not product_info:
            raise ValueError(f"不支持的产品级别: {sensor_key}/{product}")

        return {
            "sensor": sensor_key,
            "sensor_title": sensor_info["title"],
            "product": product_key,
            **product_info,
        }

    @classmethod
    def _normalize_sensor(
        cls,
        *,
        explicit_sensor: Optional[str] = None,
        scene_id: str = "",
        filename: str = "",
        url: str = "",
        collection: str = "",
    ) -> str:
        candidates = []
        if explicit_sensor:
            candidates.append(explicit_sensor)
        candidates.extend([collection, scene_id, filename, url])

        for candidate in candidates:
            normalized = str(candidate or "").strip().lower()
            if not normalized:
                continue
            if "sentinel" in normalized or re.search(r"(^|[^a-z0-9])s2[a-c]?([^a-z0-9]|$)", normalized):
                return "sentinel-2"
            if "landsat" in normalized or re.search(
                r"(^|[^a-z0-9])(lc08|lc09|lo08|lo09|le07|lt05)([^a-z0-9]|$)",
                normalized,
            ):
                return "landsat"
        return "landsat"

    @classmethod
    def _normalize_product(
        cls,
        *,
        sensor: str = "",
        explicit_product: Optional[str] = None,
        explicit_level: Optional[str] = None,
        scene_id: str = "",
        filename: str = "",
        url: str = "",
        collection: str = "",
    ) -> str:
        sensor_key = cls._normalize_sensor(
            explicit_sensor=sensor,
            scene_id=scene_id,
            filename=filename,
            url=url,
            collection=collection,
        )
        candidates = []
        if explicit_product:
            candidates.append(explicit_product)
        if explicit_level:
            candidates.append(explicit_level)
        candidates.extend([collection, scene_id, filename, url])

        for candidate in candidates:
            normalized = str(candidate or "").upper()
            if not normalized:
                continue
            if sensor_key == "sentinel-2":
                if "L2A" in normalized or "SENTINEL-2-L2A" in normalized:
                    return "L2A"
                continue

            if "L2SP" in normalized or "_L2" in normalized or "LANDSAT-C2-L2" in normalized:
                return "L2"
            if any(token in normalized for token in ("L1TP", "L1GT", "L1GS", "_L1", "LANDSAT-C2L1")):
                return "L1"

        return "L2A" if sensor_key == "sentinel-2" else "L2"

    @classmethod
    def _safe_scene_id(cls, scene_id: str) -> str:
        safe_scene_id = re.sub(r'[\\/:*?"<>|]+', "_", (scene_id or "").strip())
        return safe_scene_id or "unknown_scene"

    @classmethod
    def _build_task_target_relative_dir(cls, task: Dict) -> Path:
        sensor = cls._normalize_sensor(
            explicit_sensor=task.get("sensor"),
            scene_id=task.get("scene_id", ""),
            filename=task.get("filename", ""),
            url=task.get("url", ""),
            collection=task.get("collection", ""),
        )
        product = cls._normalize_product(
            sensor=sensor,
            explicit_product=task.get("product"),
            explicit_level=task.get("level"),
            scene_id=task.get("scene_id", ""),
            filename=task.get("filename", ""),
            url=task.get("url", ""),
            collection=task.get("collection", ""),
        )
        date_folder = task.get("download_date") or cls._local_today_folder()
        scene_id = cls._safe_scene_id(task.get("scene_id") or "unknown_scene")
        return Path(date_folder) / sensor / product / scene_id

    @classmethod
    def _build_server_target_dir(cls, base_dir: Path, task: Dict) -> Path:
        return base_dir / cls._build_task_target_relative_dir(task)

    def get_auth_status(self) -> Dict:
        configured = bool(self._eros_username and self._eros_password)
        return {
            "configured": configured,
            "username": self._eros_username if configured else "",
        }

    def get_proxy_status(self) -> Dict:
        with self._lock:
            return {
                "enabled": self._proxy_enabled,
                "configured": self._proxy_enabled and bool(self._proxy_url),
                "proxy_url": self._proxy_url,
                "no_proxy": self._no_proxy,
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

    def configure_proxy(self, request: LandsatProxyRequest) -> Dict:
        proxy_url = request.proxy_url.strip()
        no_proxy = request.no_proxy.strip()
        if request.enabled:
            if not proxy_url:
                raise ValueError("启用代理时请填写代理地址")
            self._validate_proxy_url(proxy_url)

        self._set_proxy_state(
            enabled=request.enabled and bool(proxy_url),
            proxy_url=proxy_url,
            no_proxy=no_proxy,
        )
        return self.get_proxy_status()

    async def search(self, request: ImagerySearchRequest) -> Dict:
        self._apply_proxy_env()
        config = self._get_product_config(sensor=request.sensor, product=request.product)
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
            if not self._matches_platform(item, config):
                continue

            cloud_cover = self._item_cloud_cover(item)
            if cloud_cover is not None and request.max_cloud_cover < 100 and cloud_cover > request.max_cloud_cover:
                continue

            assets = self._parse_assets(item, config)
            if not assets:
                continue

            items.append(
                {
                    "id": item.id,
                    "sensor": config["sensor"],
                    "sensor_title": config["sensor_title"],
                    "product": config["product"],
                    "collection": config["collection"],
                    "title": config["title"],
                    "auth_required": config["auth_required"],
                    "datetime": item.datetime.isoformat() if item.datetime else None,
                    "cloud_cover": round(cloud_cover, 1) if cloud_cover is not None else None,
                    "bbox": item.bbox,
                    "thumbnail": self._pick_thumbnail(item),
                    "assets": assets,
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
        client, response = await self._execute_retryable_download(
            operation=lambda _attempt: self._open_download_stream(url),
            on_retry=self._sleep_before_retry,
        )

        safe_filename = filename.replace('"', "_") or "imagery_asset.bin"
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

    async def create_download_tasks(self, request: ImageryDownloadTaskCreateRequest) -> Dict:
        created_ids = []
        with self._lock:
            active_download_dir = self.download_dir
        for item in request.items:
            task_id = uuid.uuid4().hex[:10]
            sensor = self._normalize_sensor(
                explicit_sensor=item.sensor,
                scene_id=item.scene_id,
                filename=item.filename,
                url=item.url,
                collection=item.collection or "",
            )
            product = self._normalize_product(
                sensor=sensor,
                explicit_product=item.product,
                scene_id=item.scene_id,
                filename=item.filename,
                url=item.url,
                collection=item.collection or "",
            )
            config = self._get_product_config(sensor=sensor, product=product)
            task_record = {
                "id": task_id,
                "sensor": sensor,
                "product": product,
                "collection": item.collection or config["collection"],
                "auth_required": config["auth_required"] if item.auth_required is None else bool(item.auth_required),
                "scene_id": item.scene_id,
                "level": product if sensor == "landsat" else None,
                "band": item.band,
                "filename": item.filename,
                "url": item.url,
                "mode": request.mode,
                "status": "pending",
                "progress": 0,
                "size_total": 0,
                "size_downloaded": 0,
                "error": None,
                "last_error": None,
                "retry_count": 0,
                "max_retries": DOWNLOAD_MAX_RETRIES,
                "download_root": str(active_download_dir),
                "local_path": None,
                "download_date": self._local_today_folder(),
                "created_at": self._format_timestamp(self._utc_now()),
                "updated_at": self._format_timestamp(self._utc_now()),
            }
            task_record["target_dir"] = self._build_task_target_relative_dir(task_record).as_posix()
            with self._lock:
                self._tasks[task_id] = task_record

            created_ids.append(task_id)
            # 服务端模式立即交给后台协程，前端只负责轮询状态即可。
            if request.mode == "server":
                asyncio.create_task(self._download_in_background(task_id))

        return {"task_ids": created_ids, "count": len(created_ids)}

    def list_download_tasks(self, sensor: Optional[str] = None) -> Dict:
        with self._lock:
            tasks = [
                task.copy()
                for task in self._tasks.values()
                if not sensor or task.get("sensor") == self._normalize_sensor(explicit_sensor=sensor)
            ]
        tasks.sort(key=lambda item: item["created_at"], reverse=True)
        return {"tasks": tasks}

    def get_download_task(self, task_id: str, sensor: Optional[str] = None) -> Optional[Dict]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            if sensor and task.get("sensor") != self._normalize_sensor(explicit_sensor=sensor):
                return None
            return task.copy()

    def clear_completed_tasks(self, sensor: Optional[str] = None) -> Dict:
        terminal_states = {"completed", "failed", "cancelled"}
        deleted = 0
        sensor_key = self._normalize_sensor(explicit_sensor=sensor) if sensor else None
        with self._lock:
            task_ids = [
                task_id
                for task_id, task in self._tasks.items()
                if task["status"] in terminal_states and (not sensor_key or task.get("sensor") == sensor_key)
            ]
            for task_id in task_ids:
                deleted += 1
                self._tasks.pop(task_id, None)
        return {"deleted": deleted}

    def cancel_download_task(self, task_id: str, sensor: Optional[str] = None) -> Dict:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or (sensor and task.get("sensor") != self._normalize_sensor(explicit_sensor=sensor)):
                raise KeyError(task_id)

            if task["status"] in {"pending", "downloading", "retrying"}:
                task["status"] = "cancelled"
                task["updated_at"] = self._format_timestamp(self._utc_now())

        return {"ok": True, "task_id": task_id}

    async def build_task_file_response(self, task_id: str, sensor: Optional[str] = None) -> StreamingResponse:
        task = self.get_download_task(task_id, sensor=sensor)
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

            task_download_root = Path(task.get("download_root") or self.download_dir).resolve(strict=False)
            target_dir = self._build_server_target_dir(task_download_root, task)
            self._update_task(task_id, target_dir=self._build_task_target_relative_dir(task).as_posix())
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / task["filename"]

            async def perform_attempt(_attempt_index: int) -> None:
                current_task = self.get_download_task(task_id)
                if not current_task or current_task["status"] == "cancelled":
                    raise DownloadTaskCancelled()

                self._remove_partial_file(target_path)
                self._update_task(
                    task_id,
                    status="downloading",
                    progress=0,
                    size_total=0,
                    size_downloaded=0,
                    error=None,
                    last_error=None,
                    local_path=None,
                )

                client, response = await self._open_download_stream(task["url"])
                try:
                    total_size = int(response.headers.get("content-length", 0))
                    self._update_task(task_id, size_total=total_size, size_downloaded=0)

                    downloaded = 0
                    with open(target_path, "wb") as file_obj:
                        async for chunk in response.aiter_bytes(DOWNLOAD_CHUNK_SIZE):
                            if self._is_task_cancelled(task_id):
                                raise DownloadTaskCancelled()

                            file_obj.write(chunk)
                            downloaded += len(chunk)
                            progress = int(downloaded / total_size * 100) if total_size else 0
                            self._update_task(
                                task_id,
                                size_downloaded=downloaded,
                                progress=progress,
                            )
                finally:
                    await response.aclose()
                    await client.aclose()

                if self._is_task_cancelled(task_id):
                    raise DownloadTaskCancelled()

                final_size = target_path.stat().st_size if target_path.exists() else 0
                self._update_task(
                    task_id,
                    status="completed",
                    progress=100,
                    local_path=str(target_path),
                    size_total=total_size or final_size,
                    size_downloaded=final_size,
                    error=None,
                    last_error=None,
                )

            async def handle_retry(retry_count: int, delay_seconds: int, exc: Exception) -> bool:
                logger.warning(
                    "影像下载任务重试 %s [%s/%s]: retry=%s/%s delay=%ss error=%s",
                    task_id,
                    task.get("sensor"),
                    task.get("product"),
                    retry_count,
                    DOWNLOAD_MAX_RETRIES,
                    delay_seconds,
                    exc,
                )
                self._remove_partial_file(target_path)
                self._update_task(
                    task_id,
                    status="retrying",
                    progress=0,
                    size_total=0,
                    size_downloaded=0,
                    error=None,
                    last_error=str(exc),
                    retry_count=retry_count,
                    max_retries=DOWNLOAD_MAX_RETRIES,
                    local_path=None,
                )
                return await self._wait_for_retry(task_id, delay_seconds)

            try:
                await self._execute_retryable_download(
                    operation=perform_attempt,
                    on_retry=handle_retry,
                    is_cancelled=lambda: self._is_task_cancelled(task_id),
                )
            except DownloadTaskCancelled:
                self._remove_partial_file(target_path)
                if not self._is_task_cancelled(task_id):
                    self._update_task(task_id, status="cancelled")
                return
            except Exception as exc:
                logger.error(
                    "影像下载任务失败 %s [%s/%s]: %s",
                    task_id,
                    task.get("sensor"),
                    task.get("product"),
                    exc,
                    exc_info=True,
                )
                self._remove_partial_file(target_path)
                is_retryable = self._is_retryable_download_error(exc)
                self._update_task(
                    task_id,
                    status="failed",
                    progress=0,
                    size_total=0,
                    size_downloaded=0,
                    error=self._build_retry_exhausted_error() if is_retryable else str(exc),
                    last_error=str(exc),
                    local_path=None,
                )

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

    async def _open_download_stream(self, url: str) -> Tuple[httpx.AsyncClient, httpx.Response]:
        final_url, cookies = await self._resolve_download_url(url)
        client = httpx.AsyncClient(
            **self._build_httpx_client_kwargs(
                timeout=self.download_timeout,
                follow_redirects=True,
                cookies=cookies,
            )
        )

        try:
            response = await client.send(client.build_request("GET", final_url), stream=True)
            response.raise_for_status()
        except Exception:
            await client.aclose()
            raise

        return client, response

    async def _execute_retryable_download(
        self,
        *,
        operation: Callable[[int], Awaitable[Any]],
        on_retry: Callable[[int, int, Exception], Awaitable[bool]],
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Any:
        for attempt_index in range(DOWNLOAD_MAX_ATTEMPTS):
            if is_cancelled and is_cancelled():
                raise DownloadTaskCancelled()

            try:
                return await operation(attempt_index)
            except DownloadTaskCancelled:
                raise
            except Exception as exc:
                should_retry = (
                    self._is_retryable_download_error(exc)
                    and attempt_index < DOWNLOAD_MAX_ATTEMPTS - 1
                )
                if not should_retry:
                    raise

                retry_count = attempt_index + 1
                delay_seconds = DOWNLOAD_RETRY_DELAYS[attempt_index]
                continue_retry = await on_retry(retry_count, delay_seconds, exc)
                if not continue_retry:
                    raise DownloadTaskCancelled()

        raise RuntimeError("下载重试执行器未返回结果")

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
        async with httpx.AsyncClient(
            **self._build_httpx_client_kwargs(timeout=30, follow_redirects=True)
        ) as client:
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

    def _build_httpx_client_kwargs(
        self,
        *,
        timeout: int,
        follow_redirects: bool = False,
        cookies: Optional[Dict[str, str]] = None,
    ) -> Dict:
        with self._lock:
            proxy_enabled = self._proxy_enabled
            proxy_url = self._proxy_url

        kwargs: Dict[str, object] = {
            "timeout": httpx.Timeout(connect=30.0, read=float(timeout), write=30.0, pool=30.0),
            "follow_redirects": follow_redirects,
        }
        if cookies:
            kwargs["cookies"] = cookies
        if proxy_enabled and proxy_url:
            kwargs["proxy"] = proxy_url
            kwargs["trust_env"] = False
        return kwargs

    @staticmethod
    def _validate_proxy_url(proxy_url: str) -> None:
        parsed = urlsplit(proxy_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("代理地址格式错误，请使用 http://host:port 或 https://host:port")

    def _set_proxy_state(self, *, enabled: bool, proxy_url: str, no_proxy: str) -> None:
        with self._lock:
            self._proxy_enabled = enabled and bool(proxy_url)
            self._proxy_url = proxy_url if self._proxy_enabled else ""
            self._no_proxy = no_proxy if self._proxy_enabled else ""
        self._apply_proxy_env()

    def _apply_proxy_env(self) -> None:
        with self._lock:
            proxy_enabled = self._proxy_enabled
            proxy_url = self._proxy_url
            no_proxy = self._no_proxy

        proxy_keys = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
        no_proxy_keys = ("NO_PROXY", "no_proxy")

        if proxy_enabled and proxy_url:
            for key in proxy_keys:
                os.environ[key] = proxy_url
            if no_proxy:
                for key in no_proxy_keys:
                    os.environ[key] = no_proxy
            else:
                for key in no_proxy_keys:
                    os.environ.pop(key, None)
            return

        for key in proxy_keys + no_proxy_keys:
            original_value = self._initial_proxy_env.get(key)
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value

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

    @staticmethod
    def _is_retryable_download_error(exc: Exception) -> bool:
        return isinstance(exc, RETRYABLE_DOWNLOAD_EXCEPTIONS)

    @staticmethod
    def _build_retry_exhausted_error() -> str:
        return f"连接中断，已重试 {DOWNLOAD_MAX_RETRIES} 次仍失败"

    @staticmethod
    def _remove_partial_file(target_path: Optional[Path]) -> None:
        if target_path:
            target_path.unlink(missing_ok=True)

    def _is_task_cancelled(self, task_id: str) -> bool:
        current_task = self.get_download_task(task_id)
        return not current_task or current_task["status"] == "cancelled"

    async def _wait_for_retry(self, task_id: str, delay_seconds: int) -> bool:
        return await self._sleep_for_retry(delay_seconds, task_id=task_id)

    async def _sleep_before_retry(self, _retry_count: int, delay_seconds: int, exc: Exception) -> bool:
        logger.warning(
            "影像代理下载准备重试: delay=%ss error=%s",
            delay_seconds,
            exc,
        )
        return await self._sleep_for_retry(delay_seconds)

    async def _sleep_for_retry(self, delay_seconds: int, task_id: Optional[str] = None) -> bool:
        deadline = asyncio.get_running_loop().time() + delay_seconds
        while True:
            if task_id and self._is_task_cancelled(task_id):
                return False

            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return True
            await asyncio.sleep(min(0.25, remaining))

    @classmethod
    def _pick_thumbnail(cls, item) -> Optional[str]:
        for key in cls.THUMB_KEYS:
            if key in item.assets:
                return item.assets[key].href
        return None

    @classmethod
    def _matches_platform(cls, item, config: Dict) -> bool:
        platform_tokens = tuple(config.get("platform_tokens") or ())
        if not platform_tokens:
            return True

        platform_values = [
            str(item.properties.get("platform", "")),
            str(item.properties.get("constellation", "")),
            str(item.properties.get("mission", "")),
        ]
        normalized_text = " ".join(value.lower().replace("_", "-") for value in platform_values if value).strip()
        if not normalized_text:
            return True
        return any(token in normalized_text for token in platform_tokens)

    @staticmethod
    def _item_cloud_cover(item) -> Optional[float]:
        for key in ("eo:cloud_cover", "s2:cloud_cover", "s2:cloud_cover_percentage", "cloud_cover"):
            value = item.properties.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return None

    @classmethod
    def _asset_display_map(cls, sensor: str) -> Dict[str, str]:
        if sensor == "sentinel-2":
            return cls.SENTINEL_ASSET_DISPLAY
        return cls.LANDSAT_ASSET_DISPLAY

    @classmethod
    def _parse_assets(cls, item, config: Dict) -> Dict:
        assets = {}
        display_map = cls._asset_display_map(config.get("sensor", "landsat"))
        for key, asset in item.assets.items():
            if key in cls.SKIP_ASSETS:
                continue

            media_type = getattr(asset, "media_type", "") or ""
            href = getattr(asset, "href", "") or ""
            is_tiff_like = "tiff" in media_type.lower() or href.lower().endswith((".tif", ".tiff"))
            if not is_tiff_like and key not in display_map and key not in cls.EXTRA_ASSETS:
                continue

            assets[key] = {
                "href": href,
                "label": display_map.get(key, key),
                "signed": config["sign"],
            }
        return assets
