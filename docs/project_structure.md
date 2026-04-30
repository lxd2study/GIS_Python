# 项目结构说明

本文档说明当前源码交付边界和主要目录职责。根目录中的本地数据、缓存、输出结果、论文草稿和学校规范材料不属于源码交付内容。

## 顶层目录

```text
Remote_sensing_tools/
├── main.py                         # 兼容启动入口，默认启动 API 服务
├── pyproject.toml                   # Python 包元数据与命令入口
├── requirements.txt                 # 后端运行依赖，不包含本地 GDAL 安装包
├── README.md                        # 项目总说明与启动步骤
├── TODO.md                          # 当前交付前待办
├── remote_sensing_tools/            # 后端源码
├── frontend-vue/                    # Vue 3 前端源码
├── docs/                            # 使用文档与项目说明
├── tools/                           # 文档转换等辅助工具
├── data/                            # 本地输入数据，忽略提交
├── output/                          # 处理结果与下载结果，忽略提交
├── cache/                           # 本地缓存，忽略提交
└── temp/                            # 临时文件，忽略提交
```

## 后端源码

```text
remote_sensing_tools/
├── api/
│   ├── app.py                       # FastAPI 应用创建与中间件配置
│   └── routes.py                    # 预处理、下载、预览、文件系统等接口
├── core/
│   ├── config.py                    # 环境变量与运行配置
│   ├── constants.py                 # 波段、合成类型等常量
│   ├── models.py                    # Pydantic 请求与响应模型
│   └── processor.py                 # Landsat 与 Sentinel-2 处理器
├── operations/
│   ├── atmospheric.py               # 大气校正
│   ├── geometric.py                 # 裁剪与几何处理
│   ├── radiometric.py               # 辐射定标与反射率换算
│   ├── raster_analysis.py           # 栅格二值化与面积统计
│   └── synthesis.py                 # 波段合成、指数计算、APGI
├── services/
│   ├── batch_manager.py             # 批量任务队列
│   ├── file_manager.py              # 文件与参数解析
│   ├── graph_executor.py            # Vue Flow 节点流程执行
│   ├── landsat_download.py          # Landsat/Sentinel-2 STAC 检索与下载
│   ├── progress.py                  # 异步任务进度
│   ├── task_results.py              # 结果资产清单
│   └── templates.py                 # 批处理模板
└── utils/
    ├── file_utils.py                # 场景识别、波段收集、辅助文件查找
    ├── logger.py                    # 日志辅助
    └── path_policy.py               # 文件访问范围控制
```

## 前端源码

```text
frontend-vue/
├── package.json                     # 前端依赖与脚本
├── vite.config.js                   # Vite 配置
├── public/                          # 静态资源
└── src/
    ├── App.vue                      # 主应用与页面切换
    ├── style.css                    # 全局样式
    ├── components/
    │   ├── BatchManager.vue         # 批量流程编排
    │   ├── LandsatDownload.vue      # 影像检索下载
    │   ├── IndicesInfo.vue          # 指数说明
    │   ├── TaskAssetCenter.vue      # 结果资产中心
    │   └── flow-nodes/              # 批处理节点组件
    └── utils/
        └── coverage.js              # AOI 覆盖率计算
```

## 文档目录

```text
docs/
├── README.md                        # 文档导航
├── batch_processing_quickstart.md   # 批量处理快速入门
├── batch_processing_guide.md        # 批量处理完整指南
├── indices_usage_guide.md           # 遥感指数使用指南
└── project_structure.md             # 当前项目结构说明
```

本地可能还存在以下目录，但默认不提交：

- `docs/archive/`: 历史开发记录。
- `docs/thesis-prep/`: 论文草稿、截图、参考文献核验材料。
- `docs/standard/`: 学校模板或写作规范文件。

## 运行边界

- 后端默认读取根目录 `.env`，示例见 `.env.example`。
- 前端默认读取 `frontend-vue/.env`，示例见 `frontend-vue/.env.example`。
- `data/`、`output/`、`cache/`、`temp/` 和 `frontend-vue/dist/` 是运行产物或本地数据目录，打包源码时应排除。
- 根目录的本地 GDAL wheel 只用于 Windows 环境手动安装，不作为项目依赖文件提交。
