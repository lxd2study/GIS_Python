"""
配置管理模块
集中管理所有配置项
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 5001
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # 项目路径
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    OUTPUT_DIR: Path = PROJECT_ROOT / "output"
    TEMP_DIR: Path = PROJECT_ROOT / "temp"
    CACHE_DIR: Path = PROJECT_ROOT / "cache"
    LANDSAT_DOWNLOAD_DIR: Path = OUTPUT_DIR / "landsat_downloads"

    # 6S配置
    SIXS_EXECUTABLE_PATH: Optional[str] = None
    DEFAULT_ATMOSPHERIC_PROFILE: int = 2
    DEFAULT_AEROSOL_PROFILE: int = 1
    DEFAULT_VISIBILITY: float = 40.0

    # 性能配置
    MAX_WORKERS: int = 4
    CHUNK_SIZE: int = 1024
    ENABLE_CACHE: bool = True

    # GDAL配置
    GDAL_CACHEMAX: int = 512
    GDAL_NUM_THREADS: str = "ALL_CPUS"

    HTTP_TIMEOUT: int = 60

    # Landsat 下载配置
    LANDSAT_EROS_USERNAME: str = ""
    LANDSAT_EROS_PASSWORD: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保目录存在
        self._ensure_directories()
        # 设置GDAL环境变量
        self._setup_gdal_env()

    def _ensure_directories(self):
        """确保必要的目录存在"""
        for dir_path in [
            self.DATA_DIR,
            self.OUTPUT_DIR,
            self.TEMP_DIR,
            self.CACHE_DIR,
            self.LANDSAT_DOWNLOAD_DIR,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _setup_gdal_env(self):
        """设置GDAL环境变量"""
        os.environ['GDAL_CACHEMAX'] = str(self.GDAL_CACHEMAX)
        os.environ['GDAL_NUM_THREADS'] = self.GDAL_NUM_THREADS


# 全局配置实例
settings = Settings()
