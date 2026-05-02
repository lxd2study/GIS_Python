export const CORE_BANDS = ['B2', 'B3', 'B4', 'B5']
export const SENTINEL_CORE_BANDS = ['B01', 'B04', 'B08', 'B12']
export const ALL_BANDS = Array.from({ length: 11 }, (_, i) => `B${i + 1}`)
export const SENTINEL_ALL_BANDS = ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B09', 'B11', 'B12']

export const fallbackComposites = [
  { type: 'true_color', name: '真彩色 (RGB)' },
  { type: 'false_color', name: '假彩色 (CIR)' },
  { type: 'agriculture', name: '农业监测' },
  { type: 'urban', name: '城市研究' },
  { type: 'natural_color', name: '自然彩色' },
  { type: 'swir', name: '短波红外' },
  { type: 'ndvi', name: 'NDVI - 归一化植被指数' },
  { type: 'evi', name: 'EVI - 增强型植被指数' },
  { type: 'savi', name: 'SAVI - 土壤调节植被指数' },
  { type: 'msavi', name: 'MSAVI - 修正土壤调节植被指数' },
  { type: 'arvi', name: 'ARVI - 抗大气植被指数' },
  { type: 'rvi', name: 'RVI - 比值植被指数' },
  { type: 'ndwi', name: 'NDWI - 归一化水体指数' },
  { type: 'mndwi', name: 'MNDWI - 改进归一化水体指数' },
  { type: 'awei', name: 'AWEI - 自动水体提取指数' },
  { type: 'wri', name: 'WRI - 水体比率指数' },
  { type: 'ndbi', name: 'NDBI - 归一化建筑指数' },
  { type: 'ibi', name: 'IBI - 综合建筑指数' },
  { type: 'ndbai', name: 'NDBaI - 归一化裸地与建筑指数' },
  { type: 'ui', name: 'UI - 城市指数' },
  { type: 'apgi', name: 'APGI - 大棚指数' },
  { type: 'nbr', name: 'NBR - 归一化燃烧指数' },
  { type: 'bsi', name: 'BSI - 裸土指数' },
  { type: 'ndsi', name: 'NDSI - 归一化积雪指数' },
]

export const SENTINEL_COMPOSITE_ORDER = [
  'apgi',
  'true_color',
  'false_color',
  'agriculture',
  'urban',
  'natural_color',
  'swir',
  'ndvi',
  'evi',
  'ndwi',
  'mndwi',
  'ndbi',
]
