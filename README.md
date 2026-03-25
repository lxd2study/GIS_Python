# 基于 Web 的 Landsat 8 遥感影像在线预处理系统

毕业设计项目 · v3.0.0 · 作者：李旭东

面向 Landsat 8 影像的全流程 Web 预处理平台，支持辐射定标、大气校正、几何裁剪、波段合成、遥感指数计算与场景下载，前后端一体，本地单机运行。

---

## 功能

| 模块 | 说明 |
|---|---|
| 辐射定标 | DN → 辐射亮度 → 表观反射率 → 亮度温度（B10/B11）|
| 大气校正 | DOS 简化模型；Py6S 精确 6S 辐射传输模型（自动降级）|
| 几何裁剪 | 基于 GeoJSON/shp AOI 的栅格裁剪（GDAL /vsimem/）|
| 波段合成 | 真彩色、假彩色、植被增强等预设；自定义波段公式（AST 安全解析）|
| 遥感指数 | NDVI / EVI / NDWI / NDBI / BSI / SAVI / MNDWI 等；支持用户扩展|
| 批量处理 | Vue Flow 可视化节点流程编辑器，后台异步队列执行|
| Landsat 下载 | STAC 检索（L1/L2）、AOI 框选、资产选择、浏览器/服务端双模式下载|

---

## 技术栈

**后端**
- Python 3.10+，FastAPI + Uvicorn
- GDAL 3.6+，NumPy，Py6S
- pystac-client + planetary-computer（STAC 检索与签名）

**前端**
- Vue 3 + Vite，`<script setup>` SFC
- OpenLayers 10（地图与 AOI 绘制）
- Vue Flow（批处理流程节点画布）

---

## 目录结构

```
Remote_sensing_tools/
├── main.py                    # 启动入口
├── pyproject.toml
├── requirements.txt
├── remote_sensing_tools/      # Python 后端包
│   ├── api/                   # FastAPI 路由
│   ├── core/                  # Processor、模型、常量、配置
│   ├── operations/            # 辐射/大气/几何/合成算法
│   ├── services/              # 批处理、进度、下载、模板
│   └── utils/
├── frontend-vue/              # Vue 3 前端
│   └── src/
│       ├── App.vue
│       └── components/
│           ├── BatchManager.vue
│           ├── LandsatDownload.vue
│           ├── IndicesInfo.vue
│           └── flow-nodes/
├── docs/                      # 技术与使用文档
├── data/                      # 原始影像（本地，gitignore）
└── output/                    # 输出产品（本地，gitignore）
```

---

## 环境要求

- Python ≥ 3.10，建议使用虚拟环境（venv / conda）
- GDAL 3.6+（需系统级安装或 conda 环境）
- Node.js ≥ 18，npm ≥ 9
- （可选）Py6S 及 6S 二进制，用于精确大气校正

---

## 启动

### 后端

```bash
# 安装依赖
pip install -r requirements.txt

# 复制并按需修改环境变量
copy .env.example .env   # Windows
# cp .env.example .env   # Linux / macOS

# 启动服务（默认 http://127.0.0.1:5001）
python main.py
```

### 前端

```bash
cd frontend-vue
npm install

# 复制环境变量（如需修改后端地址）
copy .env.example .env

npm run dev
# 浏览器打开 http://127.0.0.1:5173
```

---

## 文档

详见 [`docs/`](docs/) 目录：

- [批量处理指南](docs/batch_processing_guide.md)
- [遥感指数使用指南](docs/indices_usage_guide.md)
- [预处理科学分析](docs/PREPROCESSING_SCIENTIFIC_ANALYSIS.md)
- [项目目录结构](docs/project_structure.md)
