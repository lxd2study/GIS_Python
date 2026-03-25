"""数据模型和类型定义"""

from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field


class CompositeType(str, Enum):
    """合成影像类型"""
    # RGB合成
    TRUE_COLOR = "true_color"
    FALSE_COLOR = "false_color"
    AGRICULTURE = "agriculture"
    URBAN = "urban"
    NATURAL_COLOR = "natural_color"
    SWIR = "swir"

    # 植被指数
    NDVI = "ndvi"
    EVI = "evi"
    SAVI = "savi"
    MSAVI = "msavi"
    ARVI = "arvi"
    RVI = "rvi"

    # 水体指数
    NDWI = "ndwi"
    MNDWI = "mndwi"
    AWEI = "awei"
    WRI = "wri"

    # 建筑/城市指数
    NDBI = "ndbi"
    IBI = "ibi"
    NDBAI = "ndbai"
    UI = "ui"

    # 其他指数
    NBR = "nbr"
    BSI = "bsi"
    NDSI = "ndsi"


class BandPaths(BaseModel):
    """波段路径模型"""
    bands: Dict[str, str]


class ProcessingResult(BaseModel):
    """处理结果模型"""
    status: str = "success"
    processed_bands: Dict[str, str] = Field(default_factory=dict)
    composites: Dict[str, str] = Field(default_factory=dict)
    cloud_mask: Optional[str] = None
    metadata: Dict[str, Union[str, float]] = Field(default_factory=dict)
    summary: Optional[Dict] = None
    error: Optional[str] = None
    atm_correction_method: Optional[str] = None  # 实际使用的大气校正方法


class ProgressStep(BaseModel):
    """进度步骤模型"""
    id: str
    title: str
    detail: str
    status: str = "pending"
    time: str = ""


class ProgressRecord(BaseModel):
    """进度记录模型"""
    job_id: str
    status: str
    progress: int
    current_step: Optional[str]
    detail: str
    steps: List[ProgressStep]
    result: Optional[ProcessingResult] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class Metadata(BaseModel):
    """元数据模型"""
    scene_id: str = ""
    date_acquired: str = ""
    sun_elevation: float = 45.0
    sun_azimuth: float = 135.0
    cloud_cover: float = 0.0


class TaskPriority(str, Enum):
    """任务优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingTemplate(str, Enum):
    """预设处理流程模板"""
    STANDARD = "standard"  # 标准预处理
    AGRICULTURE = "agriculture"  # 农业监测
    URBAN = "urban"  # 城市分析
    WATER = "water"  # 水体提取
    CUSTOM = "custom"  # 自定义


class BatchJobConfig(BaseModel):
    """批量任务配置"""
    scene_name: str = Field(..., description="场景名称")
    band_dir: str = Field(..., description="波段文件目录")
    output_dir: str = Field(..., description="输出目录")
    mtl_file: Optional[str] = Field(None, description="MTL元数据文件路径")
    qa_band: Optional[str] = Field(None, description="QA波段路径")

    # 处理选项
    template: ProcessingTemplate = Field(ProcessingTemplate.STANDARD, description="处理流程模板")
    atm_correction_method: str = Field("DOS", description="大气校正方法")
    apply_cloud_mask: bool = Field(False, description="是否应用云掩膜")

    # 裁剪选项
    clip_extent: Optional[List[float]] = Field(None, description="裁剪范围 [xmin, ymin, xmax, ymax]")
    clip_shapefile: Optional[str] = Field(None, description="裁剪矢量文件")

    # 合成和指数
    create_composites: List[str] = Field(default_factory=list, description="合成类型列表")
    custom_index_formula: Optional[str] = Field(None, description="自定义指数公式")
    custom_index_name: Optional[str] = Field(None, description="自定义指数名称")


class BatchJob(BaseModel):
    """批量任务模型"""
    job_id: str = Field(..., description="任务ID")
    batch_id: str = Field(..., description="批次ID")
    config: BatchJobConfig = Field(..., description="任务配置")

    # 状态管理
    status: TaskStatus = Field(TaskStatus.PENDING, description="任务状态")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="任务优先级")
    progress: int = Field(0, description="进度百分比")

    # 结果
    result: Optional[ProcessingResult] = Field(None, description="处理结果")
    error: Optional[str] = Field(None, description="错误信息")

    # 重试配置
    retry_count: int = Field(0, description="已重试次数")
    max_retries: int = Field(3, description="最大重试次数")

    # 时间戳
    created_at: str = Field(..., description="创建时间")
    started_at: Optional[str] = Field(None, description="开始时间")
    completed_at: Optional[str] = Field(None, description="完成时间")
    updated_at: str = Field(..., description="更新时间")


class BatchSubmitRequest(BaseModel):
    """批量提交请求"""
    batch_name: str = Field(..., description="批次名称")
    jobs: List[BatchJobConfig] = Field(..., description="任务列表")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="批次优先级")
    auto_retry: bool = Field(True, description="失败时是否自动重试")
    max_retries: int = Field(3, description="最大重试次数")


class TaskQueueItem(BaseModel):
    """任务队列条目（/tasks/queue 响应用）"""
    job_id: str
    batch_id: str
    scene_name: str
    status: TaskStatus
    progress: int
    priority: TaskPriority
    created_at: str
    started_at: Optional[str] = None


class FlowNode(BaseModel):
    """Vue Flow 节点（前端图提交用）"""
    id: str
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)


class FlowEdge(BaseModel):
    """Vue Flow 边（前端图提交用）"""
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None


class GraphSubmitRequest(BaseModel):
    """基于节点图的批量提交请求"""
    batch_name: str
    nodes: List[FlowNode]
    edges: List[FlowEdge]
    priority: TaskPriority = Field(TaskPriority.MEDIUM)
    auto_retry: bool = True
    max_retries: int = 3


class BatchStatusResponse(BaseModel):
    """批量状态响应"""
    batch_id: str
    batch_name: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    running_jobs: int
    pending_jobs: int
    overall_progress: int
    jobs: List[BatchJob]


class LandsatSearchRequest(BaseModel):
    """Landsat 场景检索请求。"""
    bbox: List[float] = Field(..., min_length=4, max_length=4, description="[west, south, east, north]")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    max_cloud_cover: int = Field(100, ge=0, le=100, description="最大云量百分比")
    level: str = Field("L2", pattern="^(L1|L2)$", description="数据级别")
    limit: int = Field(20, ge=1, le=100, description="最大返回景数")


class LandsatDownloadItem(BaseModel):
    """单个 Landsat 资产下载项。"""
    scene_id: str = Field(..., description="场景 ID")
    band: str = Field(..., description="资产键")
    filename: str = Field(..., description="建议保存文件名")
    url: str = Field(..., description="资产 URL")


class LandsatDownloadTaskCreateRequest(BaseModel):
    """批量创建下载任务请求。"""
    items: List[LandsatDownloadItem] = Field(..., description="待下载资产列表")
    mode: str = Field("server", pattern="^(local|server)$", description="下载模式")


class LandsatAuthRequest(BaseModel):
    """USGS 凭据配置请求。"""
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")
