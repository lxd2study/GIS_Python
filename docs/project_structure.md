# Remote Sensing Tools - 项目结构

## 项目概述
遥感影像预处理工具集,支持Landsat系列卫星数据的辐射定标、大气校正、几何校正等操作。

## 目录结构

```
Remote_sensing_tools/
├── remote_sensing_tools/      # 主要代码目录
│   ├── api/                   # FastAPI Web服务
│   │   ├── app.py            # 应用入口
│   │   └── routes.py         # API路由定义
│   ├── core/                  # 核心模块
│   │   ├── config.py         # 配置管理
│   │   ├── constants.py      # 常量定义
│   │   ├── models.py         # 数据模型
│   │   └── processor.py      # 核心处理器
│   ├── operations/            # 影像处理操作
│   │   ├── atmospheric.py    # 大气校正
│   │   ├── geometric.py      # 几何校正
│   │   ├── radiometric.py    # 辐射定标
│   │   └── synthesis.py      # 影像合成
│   ├── services/              # 业务服务
│   │   ├── batch_manager.py  # 批处理管理
│   │   ├── file_manager.py   # 文件管理
│   │   ├── landsat_catalog.py # Landsat目录服务
│   │   ├── progress.py       # 进度跟踪
│   │   └── templates.py      # 模板管理
│   ├── utils/                 # 工具函数
│   │   ├── file_utils.py     # 文件工具
│   │   └── logger.py         # 日志工具
│   ├── cli.py                 # 命令行接口
│   ├── __init__.py
│   └── __main__.py           # 模块入口
├── tests/                     # 测试目录
│   ├── unit/                  # 单元测试
│   │   ├── test_atmospheric.py
│   │   ├── test_batch_manager.py
│   │   ├── test_landsat_catalog.py
│   │   └── test_radiometric.py
│   └── integration/           # 集成测试
│       ├── test_batch_processing.py
│       └── test_preprocessing_pipeline.py
├── tools/                     # 辅助工具
│   ├── md_to_docx.py         # Markdown转Word
│   └── pdf_to_png.py         # PDF转PNG
├── frontend-vue/              # Vue前端项目
├── docs/                      # 文档目录
│   ├── batch_processing_*.md # 批量处理文档
│   ├── indices_*.md          # 遥感指数文档
│   ├── PREPROCESSING_SCIENTIFIC_ANALYSIS.md
│   ├── proposal/             # 开题报告
│   ├── archive/              # 开发文档归档
│   └── README.md             # 文档目录说明
├── data/                      # 数据目录(gitignore)
├── output/                    # 输出目录(gitignore)
├── 参考文献/                  # 参考文献
├── main.py                    # 快速启动脚本
├── conftest.py               # pytest配置
├── pytest.ini                # pytest设置
├── run_tests.py              # 测试运行脚本
├── requirements.txt          # 项目依赖
├── requirements-test.txt     # 测试依赖
├── pyproject.toml            # 项目配置
├── .env.example              # 环境变量示例
├── .gitignore                # Git忽略规则
├── README.md                 # 项目说明
└── TODO.md                   # 待办事项

```

## 主要模块说明

### 1. API模块 (remote_sensing_tools/api/)
- 提供RESTful API接口
- 支持影像上传、处理、下载
- 基于FastAPI框架

### 2. 核心模块 (remote_sensing_tools/core/)
- **processor.py**: 影像处理核心逻辑
- **models.py**: Pydantic数据模型
- **config.py**: 配置管理(环境变量、设置)
- **constants.py**: 常量定义(波段信息、参数等)

### 3. 操作模块 (remote_sensing_tools/operations/)
- **radiometric.py**: DN值转辐射亮度、反射率、亮温
- **atmospheric.py**: 6S大气校正
- **geometric.py**: 几何校正、重投影
- **synthesis.py**: 多波段合成、指数计算

### 4. 服务模块 (remote_sensing_tools/services/)
- **batch_manager.py**: 批量处理任务管理
- **landsat_catalog.py**: Landsat元数据解析
- **file_manager.py**: 文件操作封装
- **progress.py**: 进度条和状态跟踪

### 5. 工具模块 (remote_sensing_tools/utils/)
- **file_utils.py**: 文件路径、格式处理
- **logger.py**: 日志配置

## 运行方式

### 启动API服务
```bash
python main.py
# 或
python -m remote_sensing_tools serve
```

### 命令行使用
```bash
python -m remote_sensing_tools --help
```

### 运行测试
```bash
python run_tests.py
# 或
pytest
```

## 依赖说明

### 核心依赖
- **GDAL**: 栅格数据处理
- **NumPy**: 数值计算
- **FastAPI**: Web框架
- **Py6S**: 大气校正
- **Pydantic**: 数据验证

### 可选依赖
- **python-docx**: Markdown转Word工具
- **PyMuPDF**: PDF转PNG工具

## 配置文件

### .env
环境变量配置文件(不提交到Git):
- 数据路径
- API密钥
- 日志级别等

### pyproject.toml
项目元数据和构建配置

### pytest.ini
测试框架配置

## 开发规范

1. 代码风格遵循PEP 8
2. 使用类型注解
3. 编写单元测试
4. 更新文档和注释
5. 提交前运行测试

## 最近更新 (2026-03-14)

- 删除了.deps vendored依赖(58MB),改用标准库
- 删除了重复的测试文件(test_radiometric_simple.py, test_radiometric_v2.py)
- 整理了项目结构,删除缓存和临时文件(约65MB)
- 更新了.gitignore,添加IDE配置忽略
- 移动测试文件到正确位置(tools/test_batch_processing.py → tests/integration/)
- 更新tools中的文件,移除对.deps的依赖
- 整理docs目录,将开发文档归档到archive/
- 创建PROJECT_STRUCTURE.md和docs/README.md文档
