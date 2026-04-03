# 基于 Web 的 Landsat 8 遥感影像在线预处理系统

毕业设计项目 · v3.0.0 · 作者：李旭东

面向 Landsat 8 影像预处理的本地化 Web 平台，集成单景预处理、批量流程编排、多影像在线检索下载与结果预览。系统同时支持 `L1` 传统预处理链和 `L2` 地表反射率直用分析，影像下载模块当前支持 Landsat 与 Sentinel-2，前后端一体运行。

---

## 当前能力

| 模块 | 说明 |
|---|---|
| 单景预处理 | 上传波段、MTL、QA 文件后提交异步任务，支持结果预览与步骤进度追踪 |
| 产品级别 | 支持 `L1` 与 `L2` 输入；`L1` 走辐射定标 + 大气校正链，`L2` 自动跳过辐射/大气预处理，直接按官方缩放系数生成分析结果 |
| 质量掩膜 | 支持 `QA_PIXEL` 云/阴影/雪/卷云掩膜，支持 `QA_RADSAT` 饱和像元掩膜，并返回质量摘要与有效像元比例 |
| 大气校正 | DOS 简化模型；Py6S 精确 6S 辐射传输模型（依赖缺失或失败时自动回退） |
| 几何裁剪 | 基于范围框或 `.shp` 的栅格裁剪 |
| 波段合成 | 真彩色、假彩色、城市、农业、短波红外等预设；支持自定义指数公式 |
| 遥感指数 | NDVI、EVI、SAVI、MSAVI、ARVI、RVI、NDWI、MNDWI、AWEI、WRI、NDBI、IBI 等 |
| 批量处理 | Vue Flow 节点式流程编辑器，支持数据目录扫描、场景筛选、条件裁剪、合成指数和输出路径编排 |
| 影像下载检索 | STAC 检索 Landsat `L1/L2` 与 Sentinel-2 `L2A` 场景，支持 AOI 框选或矢量导入、资产勾选、浏览器下载与服务端下载队列，支持代理与下载目录配置 |

---

## 页面说明

| 页面 | 用途 |
|---|---|
| 主预处理页 | 面向单景文件上传，适合实验、调参和结果快速预览 |
| 批量处理页 | 面向目录级批处理，适合多景影像的流程化执行 |
| 影像下载页 | 面向在线检索与下载，当前支持 Landsat 与 Sentinel-2；预处理链路仍保持 Landsat 定位 |

---

## 技术栈

**后端**
- Python 3.10+，FastAPI + Uvicorn
- GDAL 3.6+（本地安装），NumPy，Py6S
- pystac-client + planetary-computer

**前端**
- Vue 3 + Vite
- OpenLayers 10
- Vue Flow

---

## 目录结构

```text
Remote_sensing_tools/
├── main.py
├── pyproject.toml
├── requirements.txt
├── remote_sensing_tools/
│   ├── api/                   # FastAPI 应用与路由
│   ├── core/                  # 配置、模型、处理器、常量
│   ├── operations/            # 辐射、大气、裁剪、合成算法
│   ├── services/              # 批处理、图执行器、下载、进度服务
│   └── utils/
├── frontend-vue/
│   ├── src/App.vue
│   └── src/components/
│       ├── BatchManager.vue
│       ├── LandsatDownload.vue
│       ├── IndicesInfo.vue
│       └── flow-nodes/
├── docs/
├── data/
├── output/
├── temp/
└── cache/
```

---

## 环境要求

- Python `>= 3.10`
- Node.js `>= 18`
- npm `>= 9`
- GDAL `>= 3.6`（本地安装，确保 `osgeo` 可用）
- 可选：Py6S 与 6S 可执行文件，用于更高精度的大气校正

建议使用 `venv` 或 `conda` 管理后端环境。

---

## 快速开始

### 1. 启动后端

```bash
# 安装后端依赖（requirements.txt 不包含 gdal）
python -m pip install -r requirements.txt

# 按需修改环境变量
copy .env.example .env

# 三种方式任选一种
python main.py
# 或
python -m remote_sensing_tools serve
# 或
rstool serve
```

默认监听地址为 [http://127.0.0.1:5001](http://127.0.0.1:5001)，接口文档位于 [http://127.0.0.1:5001/docs](http://127.0.0.1:5001/docs)。

### 2. 启动前端

```bash
cd frontend-vue
npm install
copy .env.example .env
npm run dev
```

默认访问地址为 [http://127.0.0.1:5173](http://127.0.0.1:5173)。

---

## 推荐使用流程

1. 在预处理页确认后端在线，设置输出目录。
2. 如果是本地单景数据，选择 `L1` 或 `L2` 产品级别后上传波段、MTL、`QA_PIXEL`、可选的 `QA_RADSAT`。
3. 如果是批量数据，进入批量处理页扫描数据目录，由节点自动传播场景和产品级别。
4. 如需在线取数，先在影像下载页完成 AOI 检索（矩形框选或矢量导入）与资产下载；Landsat L1 需配置 USGS 账号；如访问 STAC 或下载较慢，可配置 HTTP/HTTPS 代理或调整服务端下载目录。
5. 任务完成后在结果区查看产物路径、预览图和摘要信息。

服务端下载默认会按 `output/landsat_downloads/YYYY-MM-DD/sensor/product/场景ID/文件` 自动归档，便于按日期、传感器和产品级别整理。

---

## 环境变量

后端默认读取根目录 `.env`：

```env
HOST=127.0.0.1
PORT=5001
LOG_LEVEL=INFO
DATA_DIR=./data
OUTPUT_DIR=./output
TEMP_DIR=./temp
CACHE_DIR=./cache
MAX_WORKERS=4
GDAL_CACHEMAX=512
GDAL_NUM_THREADS=ALL_CPUS
LANDSAT_PROXY_URL=http://127.0.0.1:7890
LANDSAT_NO_PROXY=127.0.0.1,localhost
```

前端默认读取 `frontend-vue/.env`：

```env
VITE_API_BASE_URL=http://127.0.0.1:5001
```

---

## 文档

详见 [`docs/`](docs/) 目录：

- [批量处理快速开始](docs/batch_processing_quickstart.md)
- [批量处理指南](docs/batch_processing_guide.md)
- [遥感指数使用指南](docs/indices_usage_guide.md)
- [预处理科学分析](docs/PREPROCESSING_SCIENTIFIC_ANALYSIS.md)
- [项目目录结构](docs/project_structure.md)
