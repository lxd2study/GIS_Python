"""Root, health and metadata route registration."""

from __future__ import annotations

from typing import Dict

from fastapi import FastAPI

from ..core.constants import BAND_INFO, COMPOSITE_MAP
from .route_helpers import get_composite_description


def register_metadata_routes(app: FastAPI) -> None:
    """Register API metadata routes without changing their public paths."""

    @app.get("/")
    def root_info() -> Dict:
        return {
            "service": "Remote Sensing Tools API",
            "version": "3.0.0",
            "docs": "/docs",
            "health": "/health",
            "frontend_project": "frontend-vue (Vue3 + Vite)",
            "usage": "可通过 frontend-vue 前端项目调用 API，或通过 /docs 调用 API",
            "core_endpoints": [
                "/preprocess_landsat8_async",
                "/preprocess_sentinel2_async",
                "/preprocess_landsat8_status/{job_id}",
                "/composite_types",
                "/band_info",
                "/preview_raster",
                "/raster/binarize",
                "/filesystem/list_dirs",
            ],
            "batch_endpoints": [
                "/batch/templates",
                "/batch/submit",
                "/batch/list",
                "/batch/{batch_id}/status",
                "/batch/job/{job_id}/status",
                "/batch/job/{job_id}/pause",
                "/batch/job/{job_id}/resume",
                "/batch/job/{job_id}/cancel",
            ],
            "imagery_download_endpoints": [
                "/imagery/collections",
                "/imagery/search",
                "/imagery/aoi/parse",
                "/imagery/auth/status",
                "/imagery/auth/earthdata",
                "/imagery/proxy/status",
                "/imagery/proxy",
                "/imagery/download_dir",
                "/imagery/proxy_download",
                "/imagery/download",
                "/imagery/download_tasks",
            ],
            "landsat_download_compat_endpoints": [
                "/landsat/collections",
                "/landsat/search",
                "/landsat/auth/status",
                "/landsat/auth/earthdata",
                "/landsat/proxy/status",
                "/landsat/proxy",
                "/landsat/download_dir",
                "/landsat/proxy_download",
                "/landsat/download",
                "/landsat/download_tasks",
            ],
            "result_endpoints": [
                "/results/tasks",
                "/results/download/file",
                "/results/download/archive",
            ],
        }

    @app.get("/health")
    def health_check() -> Dict:
        return {
            "status": "healthy",
            "service": "remote-sensing-tools",
            "version": "3.0.0",
        }

    @app.get("/composite_types")
    def get_composite_types() -> Dict:
        return {
            "composite_types": [
                {
                    "type": comp_type,
                    "name": info[0],
                    "bands": bands,
                    "description": info[1],
                    "use_case": info[2],
                }
                for comp_type, bands in COMPOSITE_MAP.items()
                for info in [get_composite_description(comp_type)]
            ]
        }

    @app.get("/band_info")
    def get_band_info() -> Dict:
        return BAND_INFO
