# 遥感指数使用指南

本系统支持 **23种** 遥感指数和合成类型，涵盖农业、城市、水利、林业等多个应用领域。

---

## 📖 快速索引

| 类别 | 指数列表 | 数量 |
|------|---------|------|
| **RGB合成** | true_color, false_color, agriculture, urban, natural_color, swir | 6 |
| **植被指数** | ndvi, evi, savi, msavi, arvi, rvi | 6 |
| **水体指数** | ndwi, mndwi, awei, wri | 4 |
| **建筑指数** | ndbi, ibi, ndbai, ui | 4 |
| **其他指数** | nbr, bsi, ndsi | 3 |

---

## 🌱 植被指数 (Vegetation Indices)

### NDVI - 归一化植被指数
```
公式: (NIR - Red) / (NIR + Red)
值域: -1 到 1
用途: 最常用的植被指数，评估植被覆盖度和健康状况
阈值:
  < 0: 水体、云、雪
  0-0.2: 裸土、建筑
  0.2-0.4: 稀疏植被、草地
  0.4-0.6: 中等植被
  > 0.6: 茂密植被、森林
适用场景: 通用植被监测
```

### EVI - 增强型植被指数
```
公式: 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)
值域: -1 到 1
用途: 高生物量区域植被活力评估
优势: 在植被茂密区比NDVI更敏感，减少土壤和大气影响
适用场景: 森林、高覆盖度农田
```

### SAVI - 土壤调节植被指数
```
公式: ((NIR - Red) / (NIR + Red + L)) * (1 + L)
参数: L = 0.5 (土壤亮度校正因子)
值域: -1 到 1
用途: 减少土壤背景对植被指数的影响
适用场景: 植被稀疏的干旱/半干旱地区、农田早期生长阶段
推荐: 植被覆盖度 < 40% 时优于NDVI
```

### MSAVI - 修正土壤调节植被指数
```
公式: (2*NIR + 1 - sqrt((2*NIR + 1)^2 - 8*(NIR - Red))) / 2
值域: -1 到 1
用途: 自适应土壤调节，无需设定L参数
优势: 比SAVI更稳健，适应性更强
适用场景: 植被覆盖度变化大的区域
```

### ARVI - 抗大气植被指数
```
公式: (NIR - (2*Red - Blue)) / (NIR + (2*Red - Blue))
值域: -1 到 1
用途: 减少大气散射对植被指数的影响
适用场景: 大气条件差的区域（雾霾、气溶胶浓度高）
推荐: 6S大气校正失败时的备选方案
```

### RVI - 比值植被指数
```
公式: NIR / Red
值域: 0 到 +∞
用途: 简单快速的植被监测
特点: 计算简单但对土壤背景敏感
适用场景: 快速植被筛查、时序分析
```

---

## 💧 水体指数 (Water Indices)

### NDWI - 归一化水体指数
```
公式: (Green - NIR) / (Green + NIR)
值域: -1 到 1
用途: 基础水体识别和地表含水量评估
阈值: NDWI > 0 通常表示水体
适用场景: 通用水体提取
```

### MNDWI - 改进归一化水体指数
```
公式: (Green - SWIR1) / (Green + SWIR1)
值域: -1 到 1
用途: 城市区域水体提取
优势: 比NDWI更能抑制建筑物噪声
阈值: MNDWI > 0 表示水体
适用场景: 城市水体提取、混合像元处理
推荐: 优先使用MNDWI而非NDWI
```

### AWEI - 自动水体提取指数
```
公式:
  AWEI_nsh = 4*(Green - SWIR1) - (0.25*NIR + 2.75*SWIR2)
  AWEI_sh = Blue + 2.5*Green - 1.5*(NIR + SWIR1) - 0.25*SWIR2
用途: 自动化水体提取
特点: 支持有阴影(sh)/无阴影(nsh)两种模式
阈值: AWEI > 0 表示水体
适用场景: 复杂地形、有阴影的场景
```

### WRI - 水体比率指数
```
公式: (Green + Red) / (NIR + SWIR1)
值域: 0 到 +∞
用途: 水体识别，对浅水和浑浊水体效果好
阈值: WRI > 1 通常表示水体
适用场景: 浅水区、浑浊水体、湿地
```

---

## 🏙️ 建筑/城市指数 (Built-up Indices)

### NDBI - 归一化建筑指数
```
公式: (SWIR1 - NIR) / (SWIR1 + NIR)
值域: -1 到 1
用途: 基础建筑区和城市扩张识别
阈值: NDBI > 0 通常表示建筑区
适用场景: 通用城市提取
```

### IBI - 综合建筑指数
```
公式: (NDBI - (SAVI + MNDWI)/2) / (NDBI + (SAVI + MNDWI)/2)
值域: -1 到 1
用途: 精确的城市建筑区提取
优势: 综合NDBI、SAVI、MNDWI，比单一NDBI更准确
适用场景: 高精度城市边界提取、建筑密度分析
推荐: 优先使用IBI而非NDBI
```

### NDBaI - 归一化裸地与建筑指数
```
公式: (SWIR1 - TIR) / (SWIR1 + TIR)
值域: -1 到 1
用途: 裸地和建筑区识别
注意: 需要热红外波段，如无则使用SWIR2代替
适用场景: 裸地监测、建设用地识别
```

### UI - 城市指数
```
公式: (SWIR2 - NIR) / (SWIR2 + NIR)
值域: -1 到 1
用途: 简单高效的城市区域识别
特点: 计算简单，适合快速制图
适用场景: 快速城市扩张监测
```

### BSI - 裸土指数
```
公式: ((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))
值域: -1 到 1
用途: 裸土识别、土壤侵蚀监测
阈值: BSI > 0 通常表示裸土
适用场景: 土壤侵蚀监测、建设用地前期识别
```

---

## 🔥 其他专题指数

### NBR - 归一化燃烧指数
```
公式: (NIR - SWIR2) / (NIR + SWIR2)
值域: -1 到 1
用途: 火灾监测、燃烧程度评估
应用: 计算dNBR = NBR(火前) - NBR(火后)
dNBR阈值:
  < -0.1: 高植被恢复
  -0.1-0.1: 未燃烧
  0.1-0.27: 低燃烧程度
  0.27-0.44: 中低燃烧程度
  0.44-0.66: 中高燃烧程度
  > 0.66: 高燃烧程度
适用场景: 森林火灾监测、灾后评估
```

### NDSI - 归一化积雪指数
```
公式: (Green - SWIR1) / (Green + SWIR1)
值域: -1 到 1
用途: 雪盖监测、冰川变化分析
阈值: NDSI > 0.4 通常表示积雪
适用场景: 雪线监测、冰川消融分析、冬季积雪分布
```

---

## 🎯 应用场景推荐

### 场景1: 农作物长势监测
**推荐指数**: NDVI, EVI, SAVI
- **NDVI**: 整体覆盖度评估
- **EVI**: 高覆盖度区域细节
- **SAVI**: 苗期/裸露土壤区

**使用模板**: `agriculture`

### 场景2: 城市扩张监测
**推荐指数**: IBI, NDBI, UI
- **IBI**: 精确建筑区边界
- **NDBI**: 快速识别建筑
- **UI**: 时序分析城市扩张

**使用模板**: `urban`

### 场景3: 水资源调查
**推荐指数**: MNDWI, AWEI, NDWI
- **MNDWI**: 城市水体提取
- **AWEI**: 复杂地形水体
- **NDWI**: 开阔水面

**使用模板**: `water`

### 场景4: 森林火灾评估
**推荐指数**: NBR
- 火前火后影像计算dNBR
- 评估燃烧程度
- 绘制灾害等级图

### 场景5: 土地利用分类
**推荐指数**: NDVI, MNDWI, NDBI, BSI
- **NDVI**: 植被类
- **MNDWI**: 水体类
- **NDBI**: 建筑类
- **BSI**: 裸地类

---

## 🔧 使用方法

### 方法1: API调用
```python
import requests

# 提交任务
response = requests.post("http://127.0.0.1:5001/preprocess_landsat8_async", data={
    "create_composites": "ndvi,evi,savi,mndwi,ibi",
    # ... 其他参数
})

job_id = response.json()["job_id"]

# 查询结果
response = requests.get(f"http://127.0.0.1:5001/preprocess_landsat8_status/{job_id}")
```

### 方法2: 命令行
```bash
python -m remote_sensing_tools preprocess \
  --band-dir /path/to/bands \
  --output-dir /path/to/output \
  --create-composites ndvi,evi,savi,mndwi,ibi
```

### 方法3: 批量处理模板
```python
# 使用农业监测模板（自动包含 ndvi, evi, savi, msavi）
batch_request = {
    "template": "agriculture",
    # ...
}
```

---

## 💡 最佳实践

### 1. 指数选择建议
- 优先使用改进版指数（MNDWI > NDWI, IBI > NDBI）
- 根据植被覆盖度选择合适的植被指数
- 城市区域水体提取必用MNDWI

### 2. 阈值设定
- 不同地区阈值不同，建议根据实际情况调整
- 可通过直方图分析确定最佳阈值
- 时序分析时使用相对变化而非绝对阈值

### 3. 组合使用
- 土地利用分类：NDVI + MNDWI + NDBI + BSI
- 农业精准监测：NDVI + EVI + SAVI
- 城市精细提取：IBI + UI + BSI

### 4. 质量控制
- 确保大气校正质量（影响所有指数）
- 云掩膜处理必不可少
- 注意数据饱和（高反射率区域）

---

## 📚 参考资源

- [完整API文档](http://127.0.0.1:5001/docs)
- [批量处理指南](batch_processing_guide.md)
- [指数扩展报告](indices_extension_report.md)

---

**版本**: 3.0.0
**更新**: 2026-03-06
**支持指数**: 23种
