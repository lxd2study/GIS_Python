# 批量自动化处理系统使用指南

## 功能概述

批量自动化处理系统支持同时处理多个Landsat影像场景，提供任务队列管理、优先级控制、失败自动重试等企业级功能。

### 核心特性

- ✅ **优先级队列**: 支持高/中/低三级任务优先级
- ✅ **并行处理**: 多线程并发处理（默认2个工作线程）
- ✅ **预设流程**: 4种专业处理流程模板（标准/农业/城市/水体）
- ✅ **失败重试**: 自动重试机制（可配置重试次数）
- ✅ **任务控制**: 支持任务暂停/恢复/取消
- ✅ **进度监控**: 实时查询批次和任务进度
- ✅ **状态管理**: 7种任务状态精细化管理

---

## API端点

### 1. 查看处理模板

**GET** `/batch/templates`

返回所有可用的预设处理流程模板。

**响应示例**:
```json
{
  "templates": [
    {
      "template": "standard",
      "name": "标准预处理",
      "description": "辐射定标 + 大气校正 + 云掩膜 + 裁剪，适用于一般遥感分析",
      "composites": ["true_color", "false_color", "natural_color"],
      "atm_correction": "DOS",
      "cloud_mask": true
    },
    {
      "template": "agriculture",
      "name": "农业监测",
      "description": "标准预处理 + 植被指数计算，适用于农作物监测、长势评估",
      "composites": ["false_color", "agriculture", "ndvi", "evi"],
      "atm_correction": "6S",
      "cloud_mask": true
    }
  ]
}
```

---

### 2. 提交批量任务

**POST** `/batch/submit`

提交一批处理任务到队列。

**请求体**:
```json
{
  "batch_name": "2020年夏季农业监测",
  "priority": "high",
  "auto_retry": true,
  "max_retries": 3,
  "jobs": [
    {
      "scene_name": "LC08_123032_20200601",
      "band_dir": "/path/to/scene1",
      "output_dir": "/path/to/output/scene1",
      "mtl_file": "/path/to/scene1/MTL.txt",
      "qa_band": "/path/to/scene1/BQA.TIF",
      "template": "agriculture",
      "atm_correction_method": "6S",
      "apply_cloud_mask": true,
      "create_composites": ["ndvi", "evi", "false_color"]
    },
    {
      "scene_name": "LC08_123032_20200701",
      "band_dir": "/path/to/scene2",
      "output_dir": "/path/to/output/scene2",
      "template": "agriculture"
    }
  ]
}
```

**参数说明**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `batch_name` | string | ✅ | 批次名称 |
| `priority` | string | ❌ | 优先级: `high`/`medium`/`low` (默认 `medium`) |
| `auto_retry` | boolean | ❌ | 失败时是否自动重试 (默认 `true`) |
| `max_retries` | integer | ❌ | 最大重试次数 (默认 `3`) |
| `jobs` | array | ✅ | 任务配置列表 |

**任务配置字段**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `scene_name` | string | ✅ | 场景名称（用于标识） |
| `band_dir` | string | ✅ | 波段文件目录 |
| `output_dir` | string | ✅ | 输出目录 |
| `mtl_file` | string | ❌ | MTL元数据文件路径 |
| `qa_band` | string | ❌ | QA波段路径 |
| `template` | string | ❌ | 处理模板: `standard`/`agriculture`/`urban`/`water`/`custom` |
| `atm_correction_method` | string | ❌ | 大气校正方法: `DOS`/`6S` |
| `apply_cloud_mask` | boolean | ❌ | 是否应用云掩膜 |
| `create_composites` | array | ❌ | 合成类型列表 |
| `clip_extent` | array | ❌ | 裁剪范围 `[xmin, ymin, xmax, ymax]` |
| `clip_shapefile` | string | ❌ | 裁剪矢量文件 |
| `custom_index_formula` | string | ❌ | 自定义指数公式 |
| `custom_index_name` | string | ❌ | 自定义指数名称 |

**响应示例**:
```json
{
  "batch_id": "e4a2c8f0-1234-5678-abcd-ef1234567890",
  "batch_name": "2020年夏季农业监测",
  "total_jobs": 2,
  "status": "submitted",
  "message": "成功提交 2 个任务到批量处理队列"
}
```

---

### 3. 查询批次状态

**GET** `/batch/{batch_id}/status`

获取批次的整体状态和所有任务详情。

**响应示例**:
```json
{
  "batch_id": "e4a2c8f0-1234-5678-abcd-ef1234567890",
  "batch_name": "2020年夏季农业监测",
  "total_jobs": 2,
  "completed_jobs": 1,
  "failed_jobs": 0,
  "running_jobs": 1,
  "pending_jobs": 0,
  "overall_progress": 75,
  "jobs": [
    {
      "job_id": "job-001",
      "status": "success",
      "progress": 100,
      "config": { "scene_name": "LC08_123032_20200601", ... },
      "result": { "status": "success", "processed_bands": {...}, ... },
      "created_at": "2026-03-06T10:00:00Z",
      "completed_at": "2026-03-06T10:15:30Z"
    },
    {
      "job_id": "job-002",
      "status": "running",
      "progress": 50,
      "config": { "scene_name": "LC08_123032_20200701", ... },
      "created_at": "2026-03-06T10:00:00Z",
      "started_at": "2026-03-06T10:15:35Z"
    }
  ]
}
```

---

### 4. 查询单个任务状态

**GET** `/batch/job/{job_id}/status`

获取单个任务的详细状态。

**响应示例**:
```json
{
  "job_id": "job-001",
  "batch_id": "e4a2c8f0-1234-5678-abcd-ef1234567890",
  "status": "running",
  "priority": "high",
  "progress": 65,
  "config": {
    "scene_name": "LC08_123032_20200601",
    "template": "agriculture",
    ...
  },
  "result": null,
  "error": null,
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "2026-03-06T10:00:00Z",
  "started_at": "2026-03-06T10:00:05Z",
  "updated_at": "2026-03-06T10:08:30Z"
}
```

**任务状态说明**:

| 状态 | 说明 |
|------|------|
| `pending` | 待处理（刚创建） |
| `queued` | 已加入队列 |
| `running` | 运行中 |
| `paused` | 已暂停 |
| `success` | 成功完成 |
| `failed` | 失败（超过重试次数） |
| `cancelled` | 已取消 |

---

### 5. 暂停任务

**POST** `/batch/job/{job_id}/pause`

暂停一个待处理或排队中的任务（运行中的任务无法暂停）。

**响应示例**:
```json
{
  "job_id": "job-002",
  "status": "paused",
  "message": "任务已暂停"
}
```

---

### 6. 恢复任务

**POST** `/batch/job/{job_id}/resume`

恢复一个已暂停的任务。

**响应示例**:
```json
{
  "job_id": "job-002",
  "status": "resumed",
  "message": "任务已恢复"
}
```

---

### 7. 取消任务

**POST** `/batch/job/{job_id}/cancel`

取消一个待处理或排队中的任务。

**响应示例**:
```json
{
  "job_id": "job-002",
  "status": "cancelled",
  "message": "任务已取消"
}
```

---

### 8. 列出所有批次

**GET** `/batch/list`

获取所有批次的概览信息。

**响应示例**:
```json
{
  "batches": [
    {
      "batch_id": "e4a2c8f0-1234-5678-abcd-ef1234567890",
      "batch_name": "2020年夏季农业监测",
      "job_count": 5,
      "created_at": "2026-03-06T10:00:00Z"
    }
  ],
  "total": 1
}
```

---

## Python使用示例

### 示例1: 提交农业监测批量任务

```python
import requests

batch_request = {
    "batch_name": "6-8月农作物监测",
    "priority": "high",
    "jobs": [
        {
            "scene_name": "2020年6月",
            "band_dir": "/data/landsat/202006",
            "output_dir": "/output/202006",
            "mtl_file": "/data/landsat/202006/MTL.txt",
            "template": "agriculture"
        },
        {
            "scene_name": "2020年7月",
            "band_dir": "/data/landsat/202007",
            "output_dir": "/output/202007",
            "mtl_file": "/data/landsat/202007/MTL.txt",
            "template": "agriculture"
        },
        {
            "scene_name": "2020年8月",
            "band_dir": "/data/landsat/202008",
            "output_dir": "/output/202008",
            "mtl_file": "/data/landsat/202008/MTL.txt",
            "template": "agriculture"
        }
    ]
}

response = requests.post("http://127.0.0.1:5001/batch/submit", json=batch_request)
batch_id = response.json()["batch_id"]
print(f"批次ID: {batch_id}")
```

### 示例2: 监控批次进度

```python
import requests
import time

def monitor_batch(batch_id):
    while True:
        response = requests.get(f"http://127.0.0.1:5001/batch/{batch_id}/status")
        status = response.json()

        total = status['total_jobs']
        completed = status['completed_jobs']
        progress = status['overall_progress']

        print(f"进度: {progress}% ({completed}/{total})")

        if completed == total:
            print("全部完成！")
            break

        time.sleep(5)  # 每5秒查询一次

monitor_batch("your-batch-id")
```

---

## 预设处理流程说明

### 1. 标准预处理 (standard)
- **用途**: 通用遥感影像预处理
- **流程**: DN → 辐射亮度 → 反射率 → DOS大气校正 → 云掩膜 → 裁剪
- **输出**: 真彩色、假彩色、自然彩色合成
- **适用**: 基础数据准备、多用途分析

### 2. 农业监测 (agriculture)
- **用途**: 农作物监测、长势评估、产量预测
- **流程**: 标准预处理 + 6S大气校正 + 植被指数
- **输出**: NDVI、EVI、假彩色、农业合成
- **适用**: 农业遥感、精准农业

### 3. 城市分析 (urban)
- **用途**: 城市扩张监测、建筑物识别
- **流程**: 标准预处理 + 建筑/城市指数
- **输出**: NDBI、真彩色、城市合成
- **适用**: 城市规划、土地利用分析

### 4. 水体提取 (water)
- **用途**: 水体识别、湿度分析、水资源调查
- **流程**: 标准预处理 + 水体指数
- **输出**: NDWI、短波红外合成
- **适用**: 水资源管理、湿地监测

---

## 最佳实践

### 1. 合理设置优先级
- **高优先级**: 紧急任务、小数据量任务
- **中优先级**: 常规任务（默认）
- **低优先级**: 后台批量任务、大数据量任务

### 2. 选择合适的模板
- 如果不确定使用哪个模板，选择 `standard`
- 针对特定应用场景，选择专业模板可获得最佳结果
- 高级用户可选择 `custom` 并手动指定所有参数

### 3. 配置自动重试
- 对于网络不稳定或系统资源紧张的环境，建议启用 `auto_retry`
- 重试次数建议设置为 2-3 次

### 4. 监控批次进度
- 使用轮询方式定期查询批次状态（建议间隔3-5秒）
- 对于长时间运行的批次，可增加轮询间隔以减少服务器压力

---

## 常见问题

### Q1: 批量任务的最大并发数是多少？
A: 默认为2个工作线程，可在 `BatchJobManager` 初始化时通过 `max_workers` 参数调整。

### Q2: 如何知道哪些任务失败了？
A: 查询批次状态时，检查 `failed_jobs` 计数和每个任务的 `status` 字段。失败任务的 `error` 字段会包含错误信息。

### Q3: 可以修改正在运行的任务吗？
A: 不可以。但可以取消待处理的任务，修改配置后重新提交。

### Q4: 批次数据会持久化吗？
A: 当前版本在内存中管理（服务重启后丢失）。后续版本将支持数据库持久化。

---

## 下一步

- 查看 [API文档](http://127.0.0.1:5001/docs) 了解完整接口
- 运行测试脚本 `tools/test_batch_processing.py` 体验功能
- 集成到前端界面，提供可视化批量任务管理

---

**版本**: 3.0.0
**更新日期**: 2026-03-06
