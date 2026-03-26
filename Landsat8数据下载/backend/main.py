import re
import asyncio
import uuid
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

import httpx
import pystac_client
import planetary_computer
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── 应用 ──────────────────────────────────────────────────────
app = FastAPI(title="Landsat 8 数据下载器")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── 配置常量 ──────────────────────────────────────────────────
DOWNLOAD_DIR = Path("downloads")
EROS_LOGIN_URL = "https://ers.cr.usgs.gov/login"
STAC_CONFIGS = {
    "L2": {"url": "https://planetarycomputer.microsoft.com/api/stac/v1",  "collection": "landsat-c2-l2", "sign": True},
    "L1": {"url": "https://landsatlook.usgs.gov/stac-server",             "collection": "landsat-c2l1",  "sign": False},
}
BAND_DISPLAY = {
    "coastal": "B1 - 海岸/气溶胶 (0.43–0.45 μm)", "blue":  "B2 - 蓝 (0.45–0.51 μm)",
    "green":   "B3 - 绿 (0.53–0.59 μm)",          "red":   "B4 - 红 (0.64–0.67 μm)",
    "nir08":   "B5 - 近红外 NIR (0.85–0.88 μm)",   "swir16":"B6 - SWIR1 (1.57–1.65 μm)",
    "swir22":  "B7 - SWIR2 (2.11–2.29 μm)",        "lwir11":"B10 - 热红外 TIRS1 (10.6–11.2 μm)",
    "lwir12":  "B11 - 热红外 TIRS2 (11.5–12.5 μm)","qa_pixel":"QA_PIXEL - 质量评估",
    "B1":"B1 - 海岸/气溶胶 (0.43–0.45 μm)", "B2":"B2 - 蓝 (0.45–0.51 μm)",
    "B3":"B3 - 绿 (0.53–0.59 μm)",          "B4":"B4 - 红 (0.64–0.67 μm)",
    "B5":"B5 - 近红外 NIR (0.85–0.88 μm)",  "B6":"B6 - SWIR1 (1.57–1.65 μm)",
    "B7":"B7 - SWIR2 (2.11–2.29 μm)",       "B8":"B8 - 全色 PAN (0.50–0.68 μm)",
    "B9":"B9 - 卷云 (1.36–1.38 μm)",        "B10":"B10 - 热红外 TIRS1 (10.6–11.2 μm)",
    "B11":"B11 - 热红外 TIRS2 (11.5–12.5 μm)", "QA_PIXEL":"QA_PIXEL - 质量评估",
    "MTL.txt":"MTL.txt - 元数据文件", "mtl.txt":"MTL.txt - 元数据文件",
}
SKIP_ASSETS  = {"rendered_preview","tilejson","thumbnail","overview","mtl.json","mtl.xml","ang","qa_radsat","ANG.txt","MTL.json"}
EXTRA_ASSETS = {"MTL.txt", "mtl.txt"}
THUMB_KEYS   = ["rendered_preview", "thumbnail", "reduced_resolution_browse"]

# ── 运行时状态 ────────────────────────────────────────────────
_eros_creds: dict         = {"username": os.getenv("EROS_USERNAME",""), "password": os.getenv("EROS_PASSWORD","")}
_eros_cookies: dict       = {}
_eros_cookie_expires: datetime = datetime.min
_dl_sem = asyncio.Semaphore(3)
tasks: dict[str, dict]    = {}


# ══════════════════════════════════════════════════════════════
#  EROS 认证
# ══════════════════════════════════════════════════════════════

def is_usgs_url(url: str) -> bool:
    return "landsatlook.usgs.gov" in url or "usgs-landsat" in url

async def ensure_eros_login() -> bool:
    """用 EROS cookie 登录，缓存约 1 小时。"""
    global _eros_cookies, _eros_cookie_expires
    u, p = _eros_creds["username"], _eros_creds["password"]
    if not u or not p:
        return False
    if _eros_cookies and datetime.utcnow() < _eros_cookie_expires:
        return True

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        r1   = await c.get(EROS_LOGIN_URL)
        m    = re.search(r'<input[^>]+name=["\']csrf["\'][^>]+value=["\']([^"\']+)["\']', r1.text) or \
               re.search(r'<input[^>]+value=["\']([^"\']+)["\'][^>]+name=["\']csrf["\']', r1.text)
        csrf = m.group(1) if m else ""
        r2   = await c.post(EROS_LOGIN_URL, data={"username": u, "password": p, "csrf": csrf})
        if "login" not in str(r2.url) and r2.status_code == 200:
            _eros_cookies = dict(c.cookies)
            _eros_cookie_expires = datetime.utcnow() + timedelta(hours=1)
            return True
    return False

async def usgs_cookies() -> dict:
    await ensure_eros_login()
    return _eros_cookies

async def resolve_url(url: str) -> tuple[str, dict]:
    """返回 (最终URL, cookies)；PC URL 自动签名，USGS URL 注入 EROS cookies。"""
    if is_usgs_url(url):
        return url, await usgs_cookies()
    return planetary_computer.sign(url), {}


# ══════════════════════════════════════════════════════════════
#  启动
# ══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    DOWNLOAD_DIR.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════
#  搜索
# ══════════════════════════════════════════════════════════════

class SearchRequest(BaseModel):
    bbox: List[float]
    start_date: str
    end_date: str
    max_cloud_cover: int
    level: str = "L2"
    limit: Optional[int] = 20

def _parse_assets(item, cfg) -> dict:
    assets = {}
    for key, asset in item.assets.items():
        if key in SKIP_ASSETS:
            continue
        mt = getattr(asset, "media_type", "") or ""
        if "tiff" in mt.lower() or key in BAND_DISPLAY or key in EXTRA_ASSETS:
            assets[key] = {"href": asset.href, "label": BAND_DISPLAY.get(key, key), "signed": cfg["sign"]}
    return assets

@app.post("/api/search")
async def search(req: SearchRequest):
    try:
        level = req.level.upper()
        cfg   = STAC_CONFIGS.get(level, STAC_CONFIGS["L2"])
        kwargs = {"modifier": planetary_computer.sign_inplace} if cfg["sign"] else {}
        catalog = pystac_client.Client.open(cfg["url"], **kwargs)
        raw     = catalog.search(collections=[cfg["collection"]], bbox=req.bbox,
                                 datetime=f"{req.start_date}/{req.end_date}", max_items=req.limit * 5)
        items = []
        for item in raw.items():
            platform = item.properties.get("platform", "").lower().replace("_", "-")
            if "landsat-8" not in platform:
                continue
            cloud = item.properties.get("eo:cloud_cover")
            if cloud is not None and req.max_cloud_cover < 100 and cloud > req.max_cloud_cover:
                continue
            thumb = next((item.assets[k].href for k in THUMB_KEYS if k in item.assets), None)
            items.append({
                "id":          item.id,
                "level":       level,
                "datetime":    item.datetime.isoformat() if item.datetime else None,
                "cloud_cover": round(cloud, 1) if cloud is not None else None,
                "bbox":        item.bbox,
                "thumbnail":   thumb,
                "assets":      _parse_assets(item, cfg),
                "path":        item.properties.get("landsat:wrs_path"),
                "row":         item.properties.get("landsat:wrs_row"),
            })
            if len(items) >= req.limit:
                break
        return {"items": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ══════════════════════════════════════════════════════════════
#  认证 API
# ══════════════════════════════════════════════════════════════

class ErosCreds(BaseModel):
    username: str
    password: str

@app.get("/api/auth/status")
async def auth_status():
    has = bool(_eros_creds["username"] and _eros_creds["password"])
    return {"configured": has, "username": _eros_creds["username"] if has else ""}

@app.post("/api/auth/earthdata")
async def set_eros(creds: ErosCreds):
    if not creds.username or not creds.password:
        raise HTTPException(400, "用户名和密码不能为空")
    _eros_creds["username"] = creds.username
    _eros_creds["password"] = creds.password
    _eros_cookies.clear()
    if not await ensure_eros_login():
        raise HTTPException(401, "EROS 登录失败，请检查账号密码")
    return {"ok": True, "username": creds.username}

@app.get("/api/sign")
async def sign_url(url: str = Query(...)):
    if is_usgs_url(url):
        return {"signed_url": url}
    try:
        return {"signed_url": planetary_computer.sign(url)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ══════════════════════════════════════════════════════════════
#  下载任务管理
# ══════════════════════════════════════════════════════════════

class TaskItem(BaseModel):
    scene_id: str
    band:     str
    filename: str
    url:      str

class TaskCreateRequest(BaseModel):
    items: List[TaskItem]
    mode:  str = "server"

@app.post("/api/tasks")
async def create_tasks(req: TaskCreateRequest):
    created = []
    for item in req.items:
        tid  = uuid.uuid4().hex[:10]
        task = {
            "id": tid, "scene_id": item.scene_id, "band": item.band,
            "filename": item.filename, "url": item.url, "mode": req.mode,
            "status": "pending", "progress": 0,
            "size_total": 0, "size_downloaded": 0,
            "error": None, "local_path": None,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        tasks[tid] = task
        created.append(tid)
        if req.mode == "server":
            asyncio.create_task(_download_server(tid))
    return {"task_ids": created, "count": len(created)}

@app.get("/api/tasks")
async def list_tasks():
    return {"tasks": list(tasks.values())}

@app.delete("/api/tasks/completed")
async def clear_completed():
    ids = [k for k, v in tasks.items() if v["status"] in ("completed","failed","cancelled")]
    for k in ids:
        del tasks[k]
    return {"deleted": len(ids)}

@app.delete("/api/tasks/{task_id}")
async def cancel_task(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] in ("pending","downloading"):
        task["status"] = "cancelled"
    return {"ok": True}

@app.get("/api/tasks/{task_id}/file")
async def serve_task_file(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] != "completed" or not task["local_path"]:
        raise HTTPException(400, "File not ready")
    fp = Path(task["local_path"])
    if not fp.exists():
        raise HTTPException(404, "File missing on disk")
    mt = "text/plain" if task["filename"].lower().endswith(".txt") else "image/tiff"
    def _iter():
        with open(fp, "rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk
    return StreamingResponse(_iter(), media_type=mt,
                             headers={"Content-Disposition": f'attachment; filename="{task["filename"]}"'})


# ══════════════════════════════════════════════════════════════
#  下载代理（本地模式 & 服务端后台）
# ══════════════════════════════════════════════════════════════

@app.get("/api/download")
async def proxy_download(url: str = Query(...), filename: str = Query("landsat.tif")):
    try:
        final_url, cookies = await resolve_url(url)
        client = httpx.AsyncClient(timeout=3600, follow_redirects=True, cookies=cookies)
        try:
            resp = await client.send(client.build_request("GET", final_url), stream=True)
            resp.raise_for_status()
        except Exception as e:
            await client.aclose()
            raise HTTPException(500, str(e))

        out_headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": resp.headers.get("content-type", "application/octet-stream"),
        }
        if "content-length" in resp.headers:
            out_headers["Content-Length"] = resp.headers["content-length"]

        async def _stream():
            try:
                async for chunk in resp.aiter_bytes(1024 * 1024):
                    yield chunk
            finally:
                await resp.aclose()
                await client.aclose()

        return StreamingResponse(_stream(), headers=out_headers)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

async def _download_server(tid: str):
    async with _dl_sem:
        task = tasks.get(tid)
        if not task or task["status"] == "cancelled":
            return
        task["status"] = "downloading"
        try:
            final_url, cookies = await resolve_url(task["url"])
            dest = DOWNLOAD_DIR / task["scene_id"]
            dest.mkdir(parents=True, exist_ok=True)
            fp = dest / task["filename"]

            async with httpx.AsyncClient(timeout=3600, follow_redirects=True, cookies=cookies) as c:
                async with c.stream("GET", final_url) as resp:
                    resp.raise_for_status()
                    total = int(resp.headers.get("content-length", 0))
                    task["size_total"] = total
                    done = 0
                    with open(fp, "wb") as f:
                        async for chunk in resp.aiter_bytes(1024 * 1024):
                            if tasks.get(tid, {}).get("status") == "cancelled":
                                break
                            f.write(chunk)
                            done += len(chunk)
                            task["size_downloaded"] = done
                            task["progress"] = int(done / total * 100) if total else 0

            if task["status"] == "cancelled":
                fp.unlink(missing_ok=True)
            else:
                task.update(status="completed", progress=100, local_path=str(fp))
        except Exception as e:
            task.update(status="failed", error=str(e))
