# 批量自动化处理系统 - 快速开始指南

## 🚀 5分钟快速上手

### 步骤1: 安装依赖

```bash
# 激活conda环境
conda activate Landsat8

# 安装缺少的依赖
pip install fastapi uvicorn

# （可选）安装6S大气校正库
conda install -c conda-forge py6s
```

### 步骤2: 启动API服务

```bash
cd E:\毕业设计\Remote_sensing_tools
python main.py
```

看到以下输出说明启动成功：
```
INFO:     Started server process [xxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:5001
```

### 步骤3: 访问API文档

在浏览器打开: http://127.0.0.1:5001/docs

你会看到Swagger UI界面，包含所有API端点。

### 步骤4: 测试批量处理功能

#### 方法1: 使用Swagger UI（推荐）

1. 找到 `GET /batch/templates`
2. 点击 "Try it out"
3. 点击 "Execute"
4. 查看返回的处理模板列表

#### 方法2: 使用测试脚本

```bash
# 需要先准备测试数据，修改脚本中的路径
python tools/test_batch_processing.py
```

#### 方法3: 使用curl命令

```bash
# 查看处理模板
curl http://127.0.0.1:5001/batch/templates

# 查看所有批次
curl http://127.0.0.1:5001/batch/list
```

---

## 📝 简单示例

### Python代码示例

```python
import requests

# 1. 查看可用模板
response = requests.get("http://127.0.0.1:5001/batch/templates")
templates = response.json()
print(f"可用模板: {len(templates['templates'])} 个")

# 2. 提交批量任务
batch_request = {
    "batch_name": "测试批次",
    "priority": "high",
    "jobs": [
        {
            "scene_name": "场景1",
            "band_dir": "E:/data/scene1",
            "output_dir": "E:/output/scene1",
            "template": "agriculture"
        },
        {
            "scene_name": "场景2",
            "band_dir": "E:/data/scene2",
            "output_dir": "E:/output/scene2",
            "template": "urban"
        }
    ]
}

response = requests.post("http://127.0.0.1:5001/batch/submit", json=batch_request)
result = response.json()
batch_id = result["batch_id"]
print(f"批次ID: {batch_id}")

# 3. 查询批次状态
response = requests.get(f"http://127.0.0.1:5001/batch/{batch_id}/status")
status = response.json()
print(f"进度: {status['overall_progress']}%")
print(f"完成: {status['completed_jobs']}/{status['total_jobs']}")
```

---

## 🎯 下一步

- 阅读完整文档: [批量处理使用指南](batch_processing_guide.md)
- 查看测试报告: [测试报告](batch_processing_test_report.md)
- 准备演示数据: 2-3个Landsat场景
- 录制演示视频: 展示批量处理功能

---

## ❓ 常见问题

### Q: 启动时报 "ModuleNotFoundError: No module named 'fastapi'"？
A: 运行 `pip install fastapi uvicorn` 安装依赖

### Q: 6S大气校正不可用？
A: 这是正常的，系统会自动回退到DOS方法。如需6S，运行 `conda install -c conda-forge py6s`

### Q: 批量任务都失败了？
A: 检查任务配置中的路径是否存在，特别是 `band_dir` 目录

---

**版本**: 3.0.0
**更新**: 2026-03-06
