"""FastAPI应用配置"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import settings
from ..services.progress import ProgressManager
from ..services.file_manager import FileManager
from ..services.batch_manager import BatchJobManager
from ..services.landsat_download import LandsatDownloadService
from .routes import setup_routes


def create_app() -> FastAPI:
    """创建并配置FastAPI应用"""

    # 配置日志
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )

    # 创建应用
    app = FastAPI(
        title="Remote Sensing Tools API",
        description="Landsat 8 影像预处理服务，包含辐射定标、大气校正、云掩膜、裁剪、合成与指数计算。支持批量自动化处理。",
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 初始化服务
    progress_manager = ProgressManager()
    file_manager = FileManager()
    batch_manager = BatchJobManager(max_workers=settings.MAX_WORKERS)  # 批量任务管理器
    landsat_download_service = LandsatDownloadService()
    # 设置路由
    setup_routes(
        app,
        progress_manager,
        file_manager,
        batch_manager,
        landsat_download_service,
    )

    return app
