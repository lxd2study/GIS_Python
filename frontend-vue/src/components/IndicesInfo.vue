<script setup>
import { ref, computed } from 'vue'

const activeCategory = ref('all')
const searchQuery = ref('')

const categories = [
  { id: 'all', name: '全部', icon: 'chart' },
  { id: 'rgb', name: 'RGB合成', icon: 'palette' },
  { id: 'vegetation', name: '植被指数', icon: 'leaf' },
  { id: 'water', name: '水体指数', icon: 'drop' },
  { id: 'urban', name: '建筑指数', icon: 'city' },
  { id: 'other', name: '其他指数', icon: 'flask' }
]

const indices = [
  // RGB合成
  {
    category: 'rgb',
    type: 'true_color',
    name: '真彩色 (RGB)',
    formula: 'R: Band4 (Red), G: Band3 (Green), B: Band2 (Blue)',
    range: '0-65535',
    usage: '自然色彩还原，直观展示地表真实色彩',
    threshold: '',
    bands: 'B2, B3, B4'
  },
  {
    category: 'rgb',
    type: 'false_color',
    name: '假彩色 (CIR)',
    formula: 'R: Band5 (NIR), G: Band4 (Red), B: Band3 (Green)',
    range: '0-65535',
    usage: '植被显示为红色，突出植被健康状况',
    threshold: '',
    bands: 'B3, B4, B5'
  },
  {
    category: 'rgb',
    type: 'agriculture',
    name: '农业监测',
    formula: 'R: Band6 (SWIR1), G: Band5 (NIR), B: Band2 (Blue)',
    range: '0-65535',
    usage: '农作物分析，强调植被与土壤差异',
    threshold: '',
    bands: 'B2, B5, B6'
  },
  {
    category: 'rgb',
    type: 'urban',
    name: '城市研究',
    formula: 'R: Band7 (SWIR2), G: Band6 (SWIR1), B: Band4 (Red)',
    range: '0-65535',
    usage: '城市区域分析，建筑物显示为青色/紫色',
    threshold: '',
    bands: 'B4, B6, B7'
  },
  {
    category: 'rgb',
    type: 'natural_color',
    name: '自然彩色',
    formula: 'R: Band4 (Red), G: Band3 (Green), B: Band2 (Blue) + 大气校正',
    range: '0-65535',
    usage: '类似真彩色，经过大气校正后的色彩',
    threshold: '',
    bands: 'B2, B3, B4'
  },
  {
    category: 'rgb',
    type: 'swir',
    name: '短波红外',
    formula: 'R: Band7 (SWIR2), G: Band5 (NIR), B: Band3 (Green)',
    range: '0-65535',
    usage: '水体和植被对比，适合地质勘探',
    threshold: '',
    bands: 'B3, B5, B7'
  },
  // 植被指数
  {
    category: 'vegetation',
    type: 'ndvi',
    name: 'NDVI - 归一化植被指数',
    formula: '(NIR - Red) / (NIR + Red)',
    range: '-1 到 1',
    usage: '最常用的植被指数，评估植被覆盖度和健康状况',
    threshold: '< 0: 水体/云; 0-0.2: 裸土; 0.2-0.4: 稀疏植被; 0.4-0.6: 中等植被; > 0.6: 茂密植被',
    bands: 'B4 (Red), B5 (NIR)'
  },
  {
    category: 'vegetation',
    type: 'evi',
    name: 'EVI - 增强型植被指数',
    formula: '2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)',
    range: '-1 到 1',
    usage: '高生物量区域植被活力评估，减少土壤和大气影响',
    threshold: '适用于植被茂密区域（森林、高覆盖度农田）',
    bands: 'B2 (Blue), B4 (Red), B5 (NIR)'
  },
  {
    category: 'vegetation',
    type: 'savi',
    name: 'SAVI - 土壤调节植被指数',
    formula: '((NIR - Red) / (NIR + Red + 0.5)) * 1.5',
    range: '-1 到 1',
    usage: '减少土壤背景影响，适合植被稀疏区域',
    threshold: '植被覆盖度 < 40% 时优于NDVI',
    bands: 'B4 (Red), B5 (NIR)'
  },
  {
    category: 'vegetation',
    type: 'msavi',
    name: 'MSAVI - 修正土壤调节植被指数',
    formula: '(2*NIR + 1 - sqrt((2*NIR + 1)² - 8*(NIR - Red))) / 2',
    range: '-1 到 1',
    usage: '自适应土壤调节，无需设定参数',
    threshold: '适用于植被覆盖度变化大的区域',
    bands: 'B4 (Red), B5 (NIR)'
  },
  {
    category: 'vegetation',
    type: 'arvi',
    name: 'ARVI - 抗大气植被指数',
    formula: '(NIR - (2*Red - Blue)) / (NIR + (2*Red - Blue))',
    range: '-1 到 1',
    usage: '减少大气散射影响，适合有雾霾的环境',
    threshold: '大气条件差时优于NDVI',
    bands: 'B2 (Blue), B4 (Red), B5 (NIR)'
  },
  {
    category: 'vegetation',
    type: 'rvi',
    name: 'RVI - 比值植被指数',
    formula: 'NIR / Red',
    range: '0 到 +∞',
    usage: '简单快速的植被监测',
    threshold: 'RVI > 1 通常表示植被',
    bands: 'B4 (Red), B5 (NIR)'
  },
  // 水体指数
  {
    category: 'water',
    type: 'ndwi',
    name: 'NDWI - 归一化水体指数',
    formula: '(Green - NIR) / (Green + NIR)',
    range: '-1 到 1',
    usage: '基础水体识别和地表含水量评估',
    threshold: 'NDWI > 0 通常表示水体',
    bands: 'B3 (Green), B5 (NIR)'
  },
  {
    category: 'water',
    type: 'mndwi',
    name: 'MNDWI - 改进归一化水体指数',
    formula: '(Green - SWIR1) / (Green + SWIR1)',
    range: '-1 到 1',
    usage: '城市区域水体提取，比NDWI更能抑制建筑物噪声',
    threshold: 'MNDWI > 0 表示水体（推荐优先使用）',
    bands: 'B3 (Green), B6 (SWIR1)'
  },
  {
    category: 'water',
    type: 'awei',
    name: 'AWEI - 自动水体提取指数',
    formula: '4*(Green - SWIR1) - (0.25*NIR + 2.75*SWIR2)',
    range: '连续值',
    usage: '自动化水体提取，适合复杂地形',
    threshold: 'AWEI > 0 表示水体（支持有/无阴影模式）',
    bands: 'B3 (Green), B5 (NIR), B6 (SWIR1), B7 (SWIR2)'
  },
  {
    category: 'water',
    type: 'wri',
    name: 'WRI - 水体比率指数',
    formula: '(Green + Red) / (NIR + SWIR1)',
    range: '0 到 +∞',
    usage: '浅水和浑浊水体识别',
    threshold: 'WRI > 1 通常表示水体',
    bands: 'B3 (Green), B4 (Red), B5 (NIR), B6 (SWIR1)'
  },
  // 建筑指数
  {
    category: 'urban',
    type: 'ndbi',
    name: 'NDBI - 归一化建筑指数',
    formula: '(SWIR1 - NIR) / (SWIR1 + NIR)',
    range: '-1 到 1',
    usage: '基础建筑区和城市扩张识别',
    threshold: 'NDBI > 0 通常表示建筑区',
    bands: 'B5 (NIR), B6 (SWIR1)'
  },
  {
    category: 'urban',
    type: 'ibi',
    name: 'IBI - 综合建筑指数',
    formula: '(NDBI - (SAVI + MNDWI)/2) / (NDBI + (SAVI + MNDWI)/2)',
    range: '-1 到 1',
    usage: '精确的城市建筑区提取，综合多个指数',
    threshold: 'IBI > 0 表示建筑区（推荐优先使用）',
    bands: 'B3, B4, B5, B6 (综合计算)'
  },
  {
    category: 'urban',
    type: 'ndbai',
    name: 'NDBaI - 归一化裸地与建筑指数',
    formula: '(SWIR1 - TIR) / (SWIR1 + TIR)',
    range: '-1 到 1',
    usage: '裸地和建筑区识别（需要热红外波段）',
    threshold: 'NDBaI > 0 表示裸地/建筑',
    bands: 'B6 (SWIR1), B10/B11 (TIR)'
  },
  {
    category: 'urban',
    type: 'ui',
    name: 'UI - 城市指数',
    formula: '(SWIR2 - NIR) / (SWIR2 + NIR)',
    range: '-1 到 1',
    usage: '简单高效的城市区域识别',
    threshold: 'UI > 0 通常表示城市区域',
    bands: 'B5 (NIR), B7 (SWIR2)'
  },
  // 其他指数
  {
    category: 'other',
    type: 'nbr',
    name: 'NBR - 归一化燃烧指数',
    formula: '(NIR - SWIR2) / (NIR + SWIR2)',
    range: '-1 到 1',
    usage: '火灾监测、燃烧程度评估',
    threshold: 'dNBR = NBR前 - NBR后: < -0.1: 植被恢复; 0.1-0.27: 低烧; 0.44-0.66: 中高烧; > 0.66: 高烧',
    bands: 'B5 (NIR), B7 (SWIR2)'
  },
  {
    category: 'other',
    type: 'bsi',
    name: 'BSI - 裸土指数',
    formula: '((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))',
    range: '-1 到 1',
    usage: '裸土识别、土壤侵蚀监测',
    threshold: 'BSI > 0 通常表示裸土',
    bands: 'B2 (Blue), B4 (Red), B5 (NIR), B6 (SWIR1)'
  },
  {
    category: 'other',
    type: 'ndsi',
    name: 'NDSI - 归一化积雪指数',
    formula: '(Green - SWIR1) / (Green + SWIR1)',
    range: '-1 到 1',
    usage: '雪盖监测、冰川变化分析',
    threshold: 'NDSI > 0.4 通常表示积雪',
    bands: 'B3 (Green), B6 (SWIR1)'
  }
]

const filteredIndices = computed(() => {
  let filtered = indices

  // Filter by category
  if (activeCategory.value !== 'all') {
    filtered = filtered.filter(idx => idx.category === activeCategory.value)
  }

  // Filter by search query
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(idx =>
      idx.name.toLowerCase().includes(query) ||
      idx.type.toLowerCase().includes(query) ||
      idx.usage.toLowerCase().includes(query)
    )
  }

  return filtered
})

const stats = computed(() => {
  return {
    total: indices.length,
    rgb: indices.filter(i => i.category === 'rgb').length,
    vegetation: indices.filter(i => i.category === 'vegetation').length,
    water: indices.filter(i => i.category === 'water').length,
    urban: indices.filter(i => i.category === 'urban').length,
    other: indices.filter(i => i.category === 'other').length
  }
})

function iconPaths(icon) {
  switch (icon) {
    case 'chart':
      return [
        'M4 19V10',
        'M10 19V5',
        'M16 19v-7',
        'M22 19V3'
      ]
    case 'palette':
      return [
        'M12 3a9 9 0 0 0 0 18h1.2a2.8 2.8 0 0 0 0-5.6H12a1.6 1.6 0 0 1 0-3.2h1.6A4.4 4.4 0 0 0 18 7.8 4.8 4.8 0 0 0 12 3Z',
        'M7.5 10.5h.01',
        'M9.5 7.5h.01',
        'M14.5 7.5h.01',
        'M16.5 10.5h.01'
      ]
    case 'leaf':
      return [
        'M6 20C15 20 19 14 19 6c-8 0-13 4-13 14Z',
        'M8.5 15.5c2.5-2.6 5.6-4.7 9.5-6.5'
      ]
    case 'drop':
      return [
        'M12 3C9.5 7.2 6 10.6 6 14a6 6 0 0 0 12 0c0-3.4-3.5-6.8-6-11Z'
      ]
    case 'city':
      return [
        'M3 21V9l6-4v16',
        'M9 21V3l6 3v15',
        'M15 21v-8l6-3v11',
        'M6 12h.01',
        'M6 16h.01',
        'M12 10h.01',
        'M12 14h.01',
        'M18 15h.01',
        'M18 18h.01'
      ]
    case 'flask':
      return [
        'M10 3v5l-5.5 9.2A2 2 0 0 0 6.2 20h11.6a2 2 0 0 0 1.7-2.8L14 8V3',
        'M9 12h6',
        'M8 16h8'
      ]
    default:
      return []
  }
}
</script>

<template>
  <div class="indices-info">
    <div class="header-section">
      <div>
        <h2>遥感指数百科</h2>
        <p class="desc">共计 {{ stats.total }} 种合成类型和遥感指数，涵盖多个应用领域</p>
      </div>
      <div class="search-box">
        <input v-model="searchQuery" type="text" placeholder="搜索指数..." />
      </div>
    </div>

    <div class="category-tabs">
      <button
        v-for="cat in categories"
        :key="cat.id"
        class="category-btn"
        :class="{ active: activeCategory === cat.id }"
        @click="activeCategory = cat.id"
      >
        <span class="icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <path v-for="path in iconPaths(cat.icon)" :key="path" :d="path" />
          </svg>
        </span>
        <span class="label">{{ cat.name }}</span>
        <span v-if="cat.id !== 'all'" class="count">({{ stats[cat.id] }})</span>
      </button>
    </div>

    <div class="indices-grid">
      <div v-for="index in filteredIndices" :key="index.type" class="index-card">
        <div class="index-header">
          <h3>{{ index.name }}</h3>
          <span class="type-badge">{{ index.type }}</span>
        </div>

        <div class="index-body">
          <div class="info-row">
            <span class="label">公式：</span>
            <code class="formula">{{ index.formula }}</code>
          </div>

          <div class="info-row" v-if="index.range">
            <span class="label">值域：</span>
            <span class="value">{{ index.range }}</span>
          </div>

          <div class="info-row" v-if="index.bands">
            <span class="label">波段：</span>
            <span class="bands">{{ index.bands }}</span>
          </div>

          <div class="info-row usage">
            <span class="label">用途：</span>
            <p class="value">{{ index.usage }}</p>
          </div>

          <div v-if="index.threshold" class="threshold-box">
            <span class="label">阈值：</span>
            <p class="value">{{ index.threshold }}</p>
          </div>
        </div>
      </div>
    </div>

    <div v-if="filteredIndices.length === 0" class="empty-state">
      <p>没有找到匹配的遥感指数</p>
    </div>
  </div>
</template>

<style scoped>
.indices-info {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.header-section h2 {
  margin: 0;
  font-size: 1.8rem;
  font-weight: 700;
  color: #1f2b27;
}

.header-section .desc {
  margin: 0.5rem 0 0;
  color: #5f726b;
  font-size: 0.95rem;
}

.search-box input {
  width: 280px;
  padding: 0.6rem 1rem;
  border: 1px solid #d9e1de;
  border-radius: 8px;
  font-size: 0.9rem;
}

.category-tabs {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.category-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem 1rem;
  border: 1px solid #d9e1de;
  border-radius: 8px;
  background: white;
  color: #5f726b;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.category-btn:hover {
  border-color: #0f7c66;
  color: #0f7c66;
}

.category-btn.active {
  background: #e7f4f1;
  border-color: #0f7c66;
  color: #0a6352;
  font-weight: 600;
}

.category-btn .icon {
  width: 1.1rem;
  height: 1.1rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.category-btn .icon svg {
  width: 100%;
  height: 100%;
}

.category-btn .count {
  font-size: 0.8rem;
  color: #5f726b;
}

.indices-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 1rem;
}

.index-card {
  background: white;
  border: 1px solid #d9e1de;
  border-radius: 12px;
  padding: 1.2rem;
  transition: all 0.2s;
}

.index-card:hover {
  border-color: #0f7c66;
  box-shadow: 0 4px 12px rgba(15, 124, 102, 0.1);
}

.index-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  gap: 0.5rem;
}

.index-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: #1f2b27;
  line-height: 1.3;
}

.type-badge {
  padding: 0.25rem 0.6rem;
  background: #f3f5f4;
  color: #5f726b;
  font-size: 0.75rem;
  font-family: 'Cascadia Mono', 'Consolas', monospace;
  border-radius: 4px;
  white-space: nowrap;
}

.index-body {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.info-row {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.5rem;
  align-items: start;
}

.info-row.usage {
  grid-template-columns: auto 1fr;
}

.info-row .label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #5f726b;
  white-space: nowrap;
}

.info-row .value {
  margin: 0;
  font-size: 0.85rem;
  color: #1f2b27;
  line-height: 1.5;
}

.info-row .formula {
  font-family: 'Cascadia Mono', 'Consolas', monospace;
  font-size: 0.8rem;
  color: #0f7c66;
  background: #f7faf9;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  word-break: break-word;
}

.info-row .bands {
  font-size: 0.82rem;
  color: #39534b;
  font-weight: 500;
}

.threshold-box {
  padding: 0.7rem;
  background: #eff6ff;
  border-left: 3px solid #3b82f6;
  border-radius: 4px;
  margin-top: 0.3rem;
}

.threshold-box .label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  color: #1e40af;
  margin-bottom: 0.3rem;
}

.threshold-box .value {
  margin: 0;
  font-size: 0.8rem;
  color: #1e3a8a;
  line-height: 1.6;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #5f726b;
}

.empty-state p {
  margin: 0;
  font-size: 1rem;
}

@media (max-width: 1040px) {
  .indices-grid {
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  }
}

@media (max-width: 720px) {
  .header-section {
    flex-direction: column;
  }

  .search-box input {
    width: 100%;
  }

  .indices-grid {
    grid-template-columns: 1fr;
  }
}
</style>
