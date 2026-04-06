<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import AoiMapPicker from './components/AoiMapPicker.vue'
import { assessCoverage } from './utils/coverage'

const BatchManager = defineAsyncComponent(() => import('./components/BatchManager.vue'))
const IndicesInfo = defineAsyncComponent(() => import('./components/IndicesInfo.vue'))
const LandsatDownload = defineAsyncComponent(() => import('./components/LandsatDownload.vue'))

const ENV_API = (import.meta.env.VITE_API_BASE_URL || '').trim()
const HISTORY_KEY = 'rst_output_history'
const API_KEY = 'rst_vue_api_base'
const OUTPUT_MODE_KEY = 'rst_output_mode'
const OUTPUT_BASE_KEY = 'rst_output_base'
const OUTPUT_MANUAL_KEY = 'rst_output_manual'
const TOAST_DURATION = {
  idle: 2200,
  ok: 2600,
  warn: 3600,
  error: 5200
}

const CORE_BANDS = ['B2', 'B3', 'B4', 'B5']
const ALL_BANDS = Array.from({ length: 11 }, (_, i) => `B${i + 1}`)

const fallbackComposites = [
  // RGB合成 (6种)
  { type: 'true_color', name: '真彩色 (RGB)' },
  { type: 'false_color', name: '假彩色 (CIR)' },
  { type: 'agriculture', name: '农业监测' },
  { type: 'urban', name: '城市研究' },
  { type: 'natural_color', name: '自然彩色' },
  { type: 'swir', name: '短波红外' },
  // 植被指数 (6种)
  { type: 'ndvi', name: 'NDVI - 归一化植被指数' },
  { type: 'evi', name: 'EVI - 增强型植被指数' },
  { type: 'savi', name: 'SAVI - 土壤调节植被指数' },
  { type: 'msavi', name: 'MSAVI - 修正土壤调节植被指数' },
  { type: 'arvi', name: 'ARVI - 抗大气植被指数' },
  { type: 'rvi', name: 'RVI - 比值植被指数' },
  // 水体指数 (4种)
  { type: 'ndwi', name: 'NDWI - 归一化水体指数' },
  { type: 'mndwi', name: 'MNDWI - 改进归一化水体指数' },
  { type: 'awei', name: 'AWEI - 自动水体提取指数' },
  { type: 'wri', name: 'WRI - 水体比率指数' },
  // 建筑/城市指数 (4种)
  { type: 'ndbi', name: 'NDBI - 归一化建筑指数' },
  { type: 'ibi', name: 'IBI - 综合建筑指数' },
  { type: 'ndbai', name: 'NDBaI - 归一化裸地与建筑指数' },
  { type: 'ui', name: 'UI - 城市指数' },
  // 其他指数 (3种)
  { type: 'nbr', name: 'NBR - 归一化燃烧指数' },
  { type: 'bsi', name: 'BSI - 裸土指数' },
  { type: 'ndsi', name: 'NDSI - 归一化积雪指数' }
]

function loadHistory() {
  try {
    const value = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
    return Array.isArray(value) ? value.filter((item) => typeof item === 'string') : []
  } catch {
    return []
  }
}

const state = reactive({
  apiBase: localStorage.getItem(API_KEY) || ENV_API || 'http://127.0.0.1:5001',
  currentTab: 'single',
  health: null,
  composites: [],
  bands: [],
  mtlFile: null,
  qaFile: null,
  qaRadsatFile: null,
  shapeFiles: [],
  productLevel: 'L1',
  clipExtent: '',
  clipGeoJson: null,
  clipBbox: null,
  clipAoiLabel: '',
  clipAoiFeatureCount: 0,
  clipAoiSourceType: '',
  clipAoiParsing: false,
  sceneCoverageGeoJson: null,
  sceneCoverageBbox: null,
  sceneCoverageLabel: '',
  sceneCoverageLoading: false,
  sceneCoverageError: '',
  selectedComposites: ['true_color', 'ndvi'],
  customFormula: '',
  customName: '',
  applyCloudMask: false,
  atmMethod: 'DOS',
  outputMode: localStorage.getItem(OUTPUT_MODE_KEY) || 'auto',
  outputBaseDir: localStorage.getItem(OUTPUT_BASE_KEY) || 'E:\\毕业设计\\Remote_sensing_tools\\output',
  outputSceneName: '',
  outputDirManual: localStorage.getItem(OUTPUT_MANUAL_KEY) || '',
  outputHistory: loadHistory(),
  outputBookmarks: JSON.parse(localStorage.getItem('rst_output_bookmarks') || '[]'),
  showHistoryDropdown: false,
  showAdvancedOptions: false,
  showBandDetails: false,
  pathPickerOpen: false,
  pathPickerLoading: false,
  pathPickerError: '',
  pathPickerCurrent: '',
  pathPickerParent: '',
  pathPickerDirectories: [],
  pathPickerTarget: 'manual',
  pathPickerBreadcrumbs: [],
  submitting: false,
  loadingMeta: false,
  toast: '',
  toastType: 'idle',
  jobId: '',
  manualJobId: '',
  progress: null,
  polling: true,
  previewPath: '',
  previewSize: 768,
  previewImage: '',
  previewMeta: null
})

let timer = null
const clipFileInput = ref(null)
let singleCoverageRequestId = 0

function normalizedApiBase() {
  const value = state.apiBase.trim().replace(/\/+$/, '')
  return value || 'http://127.0.0.1:5001'
}

function detectBandName(filename) {
  const match = filename.toUpperCase().match(/(?:^|[_-])B(1[0-1]|[1-9])(?:[_\-.]|$)/)
  return match ? `B${Number(match[1])}` : null
}

function inferSceneName(files) {
  const counts = new Map()
  for (const file of files) {
    const name = file.name.replace(/\.[^.]+$/, '')
    const match = name.match(/(.+?)_B(?:1[0-1]|[1-9])(?:_|$)/i)
    const scene = sanitizeSceneName(match ? match[1] : name.split('_')[0])
    if (!scene) continue
    counts.set(scene, (counts.get(scene) || 0) + 1)
  }
  let best = ''
  let max = 0
  for (const [name, count] of counts.entries()) {
    if (count > max) {
      best = name
      max = count
    }
  }
  return best
}

function sanitizeSceneName(name) {
  return (name || '')
    .trim()
    .replace(/[\\/:*?"<>|]+/g, '_')
    .replace(/\s+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function joinPath(base, child) {
  const b = base.trim().replace(/[\\/]+$/, '')
  const c = child.trim().replace(/^[\\/]+/, '')
  if (!b) return c
  if (!c) return b
  const separator = b.includes('\\') || /^[A-Za-z]:/.test(b) ? '\\' : '/'
  return `${b}${separator}${c}`
}

function saveOutputPrefs() {
  localStorage.setItem(OUTPUT_MODE_KEY, state.outputMode)
  localStorage.setItem(OUTPUT_BASE_KEY, state.outputBaseDir.trim())
  localStorage.setItem(OUTPUT_MANUAL_KEY, state.outputDirManual.trim())
}

function normalizePath(path) {
  return (path || '').trim().replace(/[\\/]+$/, '')
}

let toastTimer = null

function setToast(text, type = 'idle') {
  if (toastTimer) {
    window.clearTimeout(toastTimer)
    toastTimer = null
  }

  state.toast = text
  state.toastType = type

  if (!text) return

  const duration = TOAST_DURATION[type] ?? TOAST_DURATION.idle
  toastTimer = window.setTimeout(() => {
    state.toast = ''
    state.toastType = 'idle'
    toastTimer = null
  }, duration)
}

function parseDetail(detail) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => (typeof item === 'object' ? item.msg || JSON.stringify(item) : String(item))).join(' | ')
  }
  if (detail && typeof detail === 'object') return detail.msg || JSON.stringify(detail)
  return '请求失败'
}

async function request(path, options = {}) {
  const resp = await fetch(`${normalizedApiBase()}${path}`, options)
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new Error(parseDetail(data.detail || data.message || `HTTP ${resp.status}`))
  return data
}

const bandAnalysis = computed(() => {
  const map = new Map()
  const unknown = []
  state.bands.forEach((file) => {
    const band = detectBandName(file.name)
    if (!band) {
      unknown.push(file.name)
      return
    }
    if (!map.has(band)) map.set(band, [])
    map.get(band).push(file.name)
  })

  const recognized = [...map.entries()]
    .map(([band, files]) => ({ band, files }))
    .sort((a, b) => Number(a.band.slice(1)) - Number(b.band.slice(1)))

  const duplicates = recognized.filter((item) => item.files.length > 1)
  const recognizedBands = new Set(recognized.map((item) => item.band))
  const missingCore = CORE_BANDS.filter((band) => !recognizedBands.has(band))
  const missingAll = ALL_BANDS.filter((band) => !recognizedBands.has(band))
  const sceneHint = inferSceneName(state.bands)

  return {
    recognized,
    duplicates,
    unknown,
    missingCore,
    missingAll,
    sceneHint
  }
})

const outputSceneResolved = computed(() => {
  return sanitizeSceneName(state.outputSceneName || bandAnalysis.value.sceneHint || 'scene')
})

const outputDirResolved = computed(() => {
  if (state.outputMode === 'manual') return state.outputDirManual.trim()
  return joinPath(state.outputBaseDir, outputSceneResolved.value)
})

const selectedBandCount = computed(() => state.bands.length)
const serviceOk = computed(() => state.health?.status === 'healthy')
const statusLabel = computed(() => state.progress?.status || 'pending')
const progressValue = computed(() => Number(state.progress?.progress || 0))

const canSubmit = computed(() => {
  return (
    selectedBandCount.value > 0 &&
    outputDirResolved.value.length > 0 &&
    bandAnalysis.value.duplicates.length === 0 &&
    !state.submitting
  )
})

const resultItems = computed(() => {
  const result = state.progress?.result
  if (!result) return []
  const list = []
  Object.entries(result.processed_bands || {}).forEach(([name, path]) => {
    list.push({ label: name, path, group: 'processed' })
  })
  Object.entries(result.composites || {}).forEach(([name, path]) => {
    list.push({ label: name, path, group: 'composite' })
  })
  if (result.cloud_mask) {
    list.push({ label: 'cloud_mask', path: result.cloud_mask, group: 'mask' })
  }
  return list
})

async function checkHealth() {
  try {
    state.health = await request('/health')
  } catch (error) {
    state.health = { status: 'offline', detail: error.message }
  }
}

async function loadMeta() {
  state.loadingMeta = true
  try {
    await checkHealth()
    const data = await request('/composite_types')
    state.composites = data.composite_types || []
  } catch (error) {
    state.composites = [...fallbackComposites]
    setToast(`加载元数据失败：${error.message}`, 'error')
  } finally {
    state.loadingMeta = false
  }
}

function saveApiBase() {
  state.apiBase = normalizedApiBase()
  localStorage.setItem(API_KEY, state.apiBase)
  setToast(`API 地址已保存：${state.apiBase}`, 'ok')
  loadMeta()
}

async function loadPathPicker(path = '') {
  state.pathPickerLoading = true
  state.pathPickerError = ''
  try {
    const query = path ? `?path=${encodeURIComponent(path)}` : ''
    const data = await request(`/filesystem/list_dirs${query}`)
    state.pathPickerCurrent = data.current || ''
    state.pathPickerParent = data.parent || ''
    state.pathPickerDirectories = data.directories || []
    state.pathPickerBreadcrumbs = buildBreadcrumbs(data.current || '')
    return true
  } catch (error) {
    state.pathPickerError = error.message
    state.pathPickerCurrent = ''
    state.pathPickerParent = ''
    state.pathPickerDirectories = []
    state.pathPickerBreadcrumbs = []
    return false
  } finally {
    state.pathPickerLoading = false
  }
}

async function openPathPicker(target = 'manual') {
  state.pathPickerTarget = target
  state.pathPickerOpen = true

  let start = ''
  if (target === 'base') {
    start = normalizePath(state.outputBaseDir)
  } else if (target === 'manual') {
    start = normalizePath(state.outputDirManual || outputDirResolved.value)
  }

  const ok = await loadPathPicker(start)
  if (!ok && start) {
    await loadPathPicker('')
  }
}

function closePathPicker() {
  state.pathPickerOpen = false
  state.pathPickerError = ''
}

async function enterPath(path) {
  await loadPathPicker(path)
}

function selectCurrentPath() {
  const selected = normalizePath(state.pathPickerCurrent)
  if (!selected) return

  if (state.pathPickerTarget === 'base') {
    state.outputBaseDir = selected
    state.outputMode = 'auto'
  } else {
    state.outputDirManual = selected
    state.outputMode = 'manual'
  }
  saveOutputPrefs()
  closePathPicker()
  setToast(`已选择输出路径：${selected}`, 'ok')
}

function onPickFile(event, type) {
  const files = Array.from(event.target.files || [])
  if (type === 'bands') {
    state.bands = files
    if (!state.outputSceneName.trim()) {
      const hint = inferSceneName(files)
      if (hint) state.outputSceneName = hint
    }
    void loadSingleSceneCoverage(files)
  }
  if (type === 'mtl') state.mtlFile = files[0] || null
  if (type === 'qa') state.qaFile = files[0] || null
  if (type === 'qa_radsat') state.qaRadsatFile = files[0] || null
  if (type === 'shape') state.shapeFiles = files
}

function parseExtentText(text) {
  if (!text || !String(text).trim()) return null
  const values = String(text)
    .split(',')
    .map((item) => Number(item.trim()))
  if (values.length !== 4 || values.some((value) => Number.isNaN(value))) return null
  return values
}

function formatExtentText(extent) {
  return extent
    .map((value) => {
      const rounded = Number(value.toFixed(6))
      return Number.isInteger(rounded) ? String(rounded) : String(rounded)
    })
    .join(',')
}

function resetSingleClipPreview() {
  state.clipGeoJson = null
  state.clipBbox = null
  state.clipAoiLabel = ''
  state.clipAoiFeatureCount = 0
  state.clipAoiSourceType = ''
}

function resetSingleSceneCoverage() {
  state.sceneCoverageGeoJson = null
  state.sceneCoverageBbox = null
  state.sceneCoverageLabel = ''
  state.sceneCoverageLoading = false
  state.sceneCoverageError = ''
}

function clearSingleClipSelection() {
  state.clipExtent = ''
  state.shapeFiles = []
  resetSingleClipPreview()
  if (clipFileInput.value) clipFileInput.value.value = ''
}

function syncSingleClipExtentPreview() {
  const bbox = parseExtentText(state.clipExtent)
  if (!bbox) {
    if (!state.shapeFiles.length) resetSingleClipPreview()
    return
  }

  if (!state.shapeFiles.length || !state.clipGeoJson) {
    state.clipBbox = bbox
    state.clipGeoJson = null
    state.clipAoiLabel = state.clipAoiLabel || '矩形范围'
    state.clipAoiFeatureCount = 1
    state.clipAoiSourceType = 'bbox'
  }
}

function onSingleClipDraw(bbox) {
  state.clipExtent = formatExtentText(bbox)
  state.shapeFiles = []
  state.clipGeoJson = null
  state.clipBbox = bbox
  state.clipAoiLabel = '矩形框选'
  state.clipAoiFeatureCount = 1
  state.clipAoiSourceType = 'bbox'
  if (clipFileInput.value) clipFileInput.value.value = ''
}

function triggerSingleClipUpload() {
  clipFileInput.value?.click()
}

async function handleSingleClipUpload(event) {
  const files = Array.from(event?.target?.files || [])
  if (!files.length) return

  const body = new FormData()
  files.forEach((file) => body.append('files', file))

  state.clipAoiParsing = true
  try {
    const data = await request('/imagery/aoi/parse', { method: 'POST', body })
    state.shapeFiles = files
    state.clipGeoJson = data.geojson || null
    state.clipBbox = Array.isArray(data.bbox) && data.bbox.length === 4 ? data.bbox.map((value) => Number(value)) : null
    state.clipAoiLabel = data.label || 'AOI'
    state.clipAoiFeatureCount = Number(data.feature_count || 0)
    state.clipAoiSourceType = data.source_type || 'vector'
    if (state.clipBbox) state.clipExtent = formatExtentText(state.clipBbox)
    setToast(`已加载裁剪范围：${state.clipAoiLabel}`, 'ok')
  } catch (error) {
    state.shapeFiles = []
    resetSingleClipPreview()
    setToast(`解析矢量选区失败：${error.message}`, 'error')
  } finally {
    state.clipAoiParsing = false
    if (event?.target) event.target.value = ''
  }
}

async function loadSingleSceneCoverage(files = state.bands) {
  const currentRequestId = ++singleCoverageRequestId
  const targetFile = files.find((file) => detectBandName(file.name)) || files[0]
  if (!targetFile) {
    resetSingleSceneCoverage()
    return
  }

  state.sceneCoverageLoading = true
  state.sceneCoverageError = ''
  try {
    const body = new FormData()
    body.append('raster', targetFile)
    const data = await request('/imagery/raster_footprint', { method: 'POST', body })
    if (currentRequestId !== singleCoverageRequestId) return
    state.sceneCoverageGeoJson = data.geojson || null
    state.sceneCoverageBbox = Array.isArray(data.bbox) && data.bbox.length === 4 ? data.bbox.map((value) => Number(value)) : null
    state.sceneCoverageLabel = data.label || targetFile.name
  } catch (error) {
    if (currentRequestId !== singleCoverageRequestId) return
    state.sceneCoverageGeoJson = null
    state.sceneCoverageBbox = null
    state.sceneCoverageLabel = ''
    state.sceneCoverageError = error.message
    setToast(`读取影像覆盖范围失败：${error.message}`, 'warn')
  } finally {
    if (currentRequestId === singleCoverageRequestId) {
      state.sceneCoverageLoading = false
    }
  }
}

function toggleComposite(type) {
  if (state.selectedComposites.includes(type)) {
    state.selectedComposites = state.selectedComposites.filter((item) => item !== type)
  } else {
    state.selectedComposites = [...state.selectedComposites, type]
  }
}

function switchOutputMode(mode) {
  state.outputMode = mode
  saveOutputPrefs()
}

function useSceneHint() {
  if (bandAnalysis.value.sceneHint) {
    state.outputSceneName = bandAnalysis.value.sceneHint
    saveOutputPrefs()
  }
}

function addOutputHistory(path) {
  const normalized = path.trim()
  if (!normalized) return
  const latest = [normalized, ...state.outputHistory.filter((item) => item !== normalized)].slice(0, 8)
  state.outputHistory = latest
  localStorage.setItem(HISTORY_KEY, JSON.stringify(latest))
}

function pickHistory(path) {
  state.outputMode = 'manual'
  state.outputDirManual = path
  saveOutputPrefs()
}

async function submitTask() {
  if (!canSubmit.value) return
  state.submitting = true
  setToast('提交任务中...', 'idle')
  state.previewImage = ''
  state.previewMeta = null

  try {
    if (state.sceneCoverageLoading && singleClipRoiBbox.value) {
      setToast('正在读取影像覆盖范围，请稍候再提交', 'warn')
      return
    }
    if (['partial', 'outside'].includes(singleCoverageValidation.value.status)) {
      setToast('当前 ROI 超出影像覆盖范围，请先调整裁剪区域', 'error')
      return
    }

    const body = new FormData()
    state.bands.forEach((file) => body.append('bands', file))
    if (state.mtlFile) body.append('mtl_file', state.mtlFile)
    if (state.qaFile) body.append('qa_band', state.qaFile)
    if (state.qaRadsatFile) body.append('qa_radsat_band', state.qaRadsatFile)
    state.shapeFiles.forEach((file) => body.append('clip_shapefile', file))

    body.append('output_dir', outputDirResolved.value)
    body.append('apply_cloud_mask', String(state.applyCloudMask))
    body.append('atm_correction_method', state.atmMethod)
    body.append('product_level', state.productLevel)

    if (state.clipExtent.trim()) body.append('clip_extent', state.clipExtent.trim())
    if (state.selectedComposites.length) body.append('create_composites', state.selectedComposites.join(','))
    if (state.customFormula.trim()) {
      body.append('custom_formula', state.customFormula.trim())
      if (state.customName.trim()) body.append('custom_name', state.customName.trim())
    }

    const data = await request('/preprocess_landsat8_async', { method: 'POST', body })
    state.jobId = data.job_id
    state.manualJobId = data.job_id
    state.progress = { status: 'processing', progress: 0, detail: '任务已创建', steps: [] }
    addOutputHistory(outputDirResolved.value)
    saveOutputPrefs()
    setToast(`任务创建成功，job_id: ${data.job_id}`, 'ok')
    await queryStatus()
    restartPolling()
  } catch (error) {
    setToast(`提交失败：${error.message}`, 'error')
  } finally {
    state.submitting = false
  }
}

function stopPolling() {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

function restartPolling() {
  stopPolling()
  if (!state.polling) return
  timer = window.setInterval(() => queryStatus(true), 2500)
}

async function queryStatus(silent = false) {
  const targetId = (state.manualJobId || state.jobId).trim()
  if (!targetId) {
    if (!silent) setToast('请先输入或创建 job_id', 'warn')
    return
  }

  try {
    const task = await request(`/preprocess_landsat8_status/${encodeURIComponent(targetId)}`)
    state.jobId = targetId
    state.progress = task
    if (['success', 'error', 'partial'].includes(task.status)) stopPolling()
  } catch (error) {
    if (!silent) setToast(`查询失败：${error.message}`, 'error')
    stopPolling()
  }
}

function resetForm() {
  state.bands = []
  state.mtlFile = null
  state.qaFile = null
  state.qaRadsatFile = null
  state.shapeFiles = []
  state.productLevel = 'L1'
  state.clipExtent = ''
  resetSingleClipPreview()
  resetSingleSceneCoverage()
  if (clipFileInput.value) clipFileInput.value.value = ''
  state.selectedComposites = ['true_color', 'ndvi']
  state.customFormula = ''
  state.customName = ''
  state.applyCloudMask = false
  state.atmMethod = 'DOS'
  setToast('表单已重置', 'idle')
}

const singleClipRoiBbox = computed(() => {
  return state.clipBbox || parseExtentText(state.clipExtent)
})

const singleCoverageValidation = computed(() => {
  return assessCoverage(singleClipRoiBbox.value, state.sceneCoverageBbox ? [state.sceneCoverageBbox] : [])
})

const singleClipStatusText = computed(() => {
  if (state.sceneCoverageLoading) return '正在加载影像覆盖范围...'
  if (state.sceneCoverageError) return `影像覆盖范围读取失败：${state.sceneCoverageError}`
  if (state.sceneCoverageBbox && singleClipRoiBbox.value) {
    if (singleCoverageValidation.value.status === 'inside') return 'ROI 完全位于当前影像覆盖范围内'
    if (singleCoverageValidation.value.status === 'partial') return 'ROI 部分超出当前影像覆盖范围，请调整'
    if (singleCoverageValidation.value.status === 'outside') return 'ROI 完全不在当前影像覆盖范围内'
  }
  if (state.clipAoiParsing) return '正在解析矢量范围...'
  if (state.clipGeoJson) {
    const label = state.clipAoiLabel || '矢量范围'
    const count = state.clipAoiFeatureCount || 0
    return `${label}，${count} 个要素，提交时优先使用上传矢量`
  }
  if (state.sceneCoverageBbox) return `已叠加影像覆盖范围：${state.sceneCoverageLabel || '当前场景'}`
  if (state.clipBbox) return '当前显示矩形范围，提交时按 bbox 裁剪'
  return '可在地图框选矩形，或上传 GeoJSON / Shapefile 预览 ROI'
})

const singleCoverageStateLabel = computed(() => {
  if (state.sceneCoverageLoading) return '加载中'
  if (state.sceneCoverageError) return '读取失败'
  if (!state.sceneCoverageBbox) return '未加载'
  if (!singleClipRoiBbox.value) return '已加载'
  if (singleCoverageValidation.value.status === 'inside') return '完全覆盖'
  if (singleCoverageValidation.value.status === 'partial') return '部分越界'
  if (singleCoverageValidation.value.status === 'outside') return '完全越界'
  return '待校验'
})

const singleClipFileSummary = computed(() => {
  if (!state.shapeFiles.length) return '未上传矢量文件'
  if (state.shapeFiles.length === 1) return state.shapeFiles[0].name
  return `${state.shapeFiles[0].name} 等 ${state.shapeFiles.length} 个文件`
})

async function loadPreview(path = '') {
  const targetPath = (path || state.previewPath).trim()
  if (!targetPath) {
    setToast('请输入预览文件路径', 'warn')
    return
  }

  try {
    const body = new FormData()
    body.append('file_path', targetPath)
    body.append('max_size', String(Math.max(128, Math.min(2048, Number(state.previewSize) || 768))))
    const data = await request('/preview_raster', { method: 'POST', body })
    state.previewPath = targetPath
    state.previewMeta = data.preview
    state.previewImage = `data:image/png;base64,${data.preview.base64}`
    setToast('预览加载完成', 'ok')
  } catch (error) {
    setToast(`预览失败：${error.message}`, 'error')
  }
}

function toastClass() {
  if (state.toastType === 'ok') return 'toast ok'
  if (state.toastType === 'warn') return 'toast warn'
  if (state.toastType === 'error') return 'toast err'
  return 'toast idle'
}

function handleBatchToast({ type = 'idle', message } = {}) {
  setToast(message, type)
}

function switchTab(tab) {
  state.currentTab = tab
}

function toggleHistoryDropdown() {
  state.showHistoryDropdown = !state.showHistoryDropdown
}

function addBookmark() {
  const path = state.outputMode === 'auto' ? state.outputBaseDir : state.outputDirManual
  const normalized = normalizePath(path)
  if (!normalized) {
    setToast('请先设置路径', 'warn')
    return
  }

  if (state.outputBookmarks.includes(normalized)) {
    setToast('书签已存在', 'warn')
    return
  }

  state.outputBookmarks = [normalized, ...state.outputBookmarks].slice(0, 5)
  localStorage.setItem('rst_output_bookmarks', JSON.stringify(state.outputBookmarks))
  setToast('已添加到书签', 'ok')
}

function removeBookmark(path) {
  state.outputBookmarks = state.outputBookmarks.filter(p => p !== path)
  localStorage.setItem('rst_output_bookmarks', JSON.stringify(state.outputBookmarks))
}

function useBookmark(path) {
  state.outputMode = 'manual'
  state.outputDirManual = path
  saveOutputPrefs()
  setToast('已应用书签路径', 'ok')
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    setToast('路径已复制到剪贴板', 'ok')
  }).catch(() => {
    setToast('复制失败，请手动复制', 'warn')
  })
}

function buildBreadcrumbs(path) {
  if (!path) return []
  const parts = path.split(/[\\/]/).filter(Boolean)
  const crumbs = []
  let current = ''

  parts.forEach((part, index) => {
    if (index === 0 && /^[A-Za-z]:$/.test(part)) {
      current = part + '\\'
      crumbs.push({ name: part, path: current })
    } else {
      current = current ? `${current}\\${part}` : part
      crumbs.push({ name: part, path: current })
    }
  })

  return crumbs
}

async function navigateToBreadcrumb(path) {
  await loadPathPicker(path)
}

function getQuickPaths() {
  const projectRoot = 'E:\\毕业设计\\Remote_sensing_tools'
  return [
    { name: '项目根目录', path: projectRoot },
    { name: '项目输出', path: `${projectRoot}\\output` },
    { name: 'C盘根目录', path: 'C:\\' },
    { name: 'D盘根目录', path: 'D:\\' },
    { name: 'E盘根目录', path: 'E:\\' }
  ]
}

async function useQuickPath(path) {
  await loadPathPicker(path)
}

onMounted(() => {
  state.apiBase = normalizedApiBase()
  loadMeta()

  // Close history dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.history-dropdown-container')) {
      state.showHistoryDropdown = false
    }
  })
})

onBeforeUnmount(() => {
  stopPolling()
  if (toastTimer) {
    window.clearTimeout(toastTimer)
    toastTimer = null
  }
})
</script>

<template>
  <main class="page" :class="state.currentTab === 'indices' || state.currentTab === 'download' ? 'scrollable' : 'no-scroll'">
    <header class="top">
      <div>
        <h1>遥感预处理控制台</h1>
        <p class="desc">简洁版 Vue3 操作页：任务配置、进度查询、结果预览。</p>
      </div>
      <div class="status" :class="{ on: serviceOk }">
        <span class="dot"></span>
        <span>{{ serviceOk ? 'API 在线' : 'API 离线' }}</span>
      </div>
    </header>

    <section class="card api-card">
      <label class="field-grow">
        <span>API Base URL</span>
        <input v-model="state.apiBase" type="text" placeholder="http://127.0.0.1:5001" />
      </label>
      <button class="btn sub" type="button" @click="saveApiBase">保存地址</button>
      <button class="btn pri" type="button" @click="loadMeta">刷新元数据</button>
    </section>

    <!-- Tab Navigation -->
    <section class="tabs-bar">
      <button
        class="tab-btn"
        :class="{ active: state.currentTab === 'single' }"
        @click="switchTab('single')"
      >
        单任务处理
      </button>
      <button
        class="tab-btn"
        :class="{ active: state.currentTab === 'batch' }"
        @click="switchTab('batch')"
      >
        批量处理
      </button>
      <button
        class="tab-btn"
        :class="{ active: state.currentTab === 'download' }"
        @click="switchTab('download')"
      >
        影像下载
      </button>
      <button
        class="tab-btn"
        :class="{ active: state.currentTab === 'indices' }"
        @click="switchTab('indices')"
      >
        遥感指数百科
      </button>
    </section>

    <!-- Single Task View -->
    <section v-if="state.currentTab === 'single'" class="layout-compact">
      <article class="card form-card-compact">
        <div class="title-row-compact">
          <h2>任务配置</h2>
          <small>{{ selectedBandCount }} 文件</small>
        </div>

        <div class="form-grid-compact">
          <!-- 波段文件 -->
          <label class="field-compact full">
            <span>波段文件（必选）</span>
            <input type="file" multiple accept=".tif,.tiff,.img" @change="(e) => onPickFile(e, 'bands')" />
          </label>

          <!-- 波段识别信息（可折叠） -->
          <div class="band-info-compact full">
            <div class="info-summary" @click="state.showBandDetails = !state.showBandDetails">
              <strong>识别波段：</strong>{{ bandAnalysis.recognized.map((item) => item.band).join(', ') || '无' }}
              <span class="toggle-icon" :class="{ open: state.showBandDetails }" aria-hidden="true">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 3.5 10 8l-5 4.5" />
                </svg>
              </span>
            </div>
            <div v-if="state.showBandDetails" class="info-details">
              <p v-if="bandAnalysis.missingCore.length" class="warn-line">
                缺少核心波段：{{ bandAnalysis.missingCore.join(', ') }}
              </p>
              <p v-if="bandAnalysis.duplicates.length" class="err-line">
                重复波段：{{ bandAnalysis.duplicates.map((item) => `${item.band}(${item.files.length})`).join(', ') }}
              </p>
            </div>
          </div>

          <label class="field-compact">
            <span>产品级别</span>
            <select v-model="state.productLevel">
              <option value="L1">L1: DN/辐射定标链</option>
              <option value="L2">L2: 地表反射率直用</option>
            </select>
          </label>

          <!-- 可选文件 -->
          <label class="field-compact">
            <span>MTL 文件</span>
            <input type="file" accept=".txt,.mtl" @change="(e) => onPickFile(e, 'mtl')" />
          </label>

          <label class="field-compact">
            <span>QA 文件</span>
            <input type="file" accept=".tif,.tiff,.img" @change="(e) => onPickFile(e, 'qa')" />
          </label>

          <label class="field-compact">
            <span>QA_RADSAT</span>
            <input type="file" accept=".tif,.tiff,.img" @change="(e) => onPickFile(e, 'qa_radsat')" />
          </label>

          <!-- 输出路径 -->
          <div class="field-compact full">
            <span>输出模式</span>
            <div class="mode-row-compact">
              <button class="btn-tiny" :class="{ active: state.outputMode === 'auto' }" @click="switchOutputMode('auto')">
                自动组合
              </button>
              <button class="btn-tiny" :class="{ active: state.outputMode === 'manual' }" @click="switchOutputMode('manual')">
                手动输入
              </button>
            </div>
          </div>

          <template v-if="state.outputMode === 'auto'">
            <label class="field-compact full">
              <span>基路径</span>
              <div class="input-row">
                <input v-model="state.outputBaseDir" type="text" @change="saveOutputPrefs" placeholder="E:\..." />
                <button class="btn-mini" @click="openPathPicker('base')">...</button>
              </div>
            </label>
            <label class="field-compact full">
              <span>场景名</span>
              <div class="input-row">
                <input v-model="state.outputSceneName" type="text" @change="saveOutputPrefs" placeholder="LC08_..." />
                <button class="btn-mini" @click="useSceneHint" :disabled="!bandAnalysis.sceneHint">识别</button>
              </div>
            </label>
          </template>

          <label v-else class="field-compact full">
            <span>输出目录</span>
            <div class="input-row">
              <input v-model="state.outputDirManual" type="text" @change="saveOutputPrefs" placeholder="完整路径" />
              <button class="btn-mini" @click="openPathPicker('manual')">...</button>
            </div>
          </label>

          <!-- 书签和历史（紧凑版） -->
          <div class="quick-access full" v-if="state.outputBookmarks.length || state.outputHistory.length">
            <select v-model="state.outputDirManual" @change="state.outputMode = 'manual'; saveOutputPrefs()" class="path-select">
              <option value="">-- 快捷路径 --</option>
              <optgroup label="书签" v-if="state.outputBookmarks.length">
                <option v-for="path in state.outputBookmarks" :key="'b-'+path" :value="path">{{ path }}</option>
              </optgroup>
              <optgroup label="历史" v-if="state.outputHistory.length">
                <option v-for="path in state.outputHistory" :key="'h-'+path" :value="path">{{ path }}</option>
              </optgroup>
            </select>
            <button class="btn-mini" @click="addBookmark">+</button>
          </div>

          <!-- 高级选项（可折叠） -->
          <div class="field-compact full">
            <button class="toggle-section" @click="state.showAdvancedOptions = !state.showAdvancedOptions">
              <span>高级选项</span>
              <span class="toggle-section-icon" :class="{ open: state.showAdvancedOptions }" aria-hidden="true">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 3.5 10 8l-5 4.5" />
                </svg>
              </span>
            </button>
          </div>

          <template v-if="state.showAdvancedOptions">
            <div class="field-compact full clip-visual-field">
              <div class="clip-visual-head">
                <span>可视化裁剪 ROI</span>
                <div class="clip-visual-actions">
                  <button class="btn-mini" type="button" :disabled="state.clipAoiParsing" @click="triggerSingleClipUpload">
                    {{ state.clipAoiParsing ? '解析中...' : '上传矢量' }}
                  </button>
                  <button class="btn-mini ghost" type="button" @click="clearSingleClipSelection">清空 ROI</button>
                </div>
              </div>
              <input
                ref="clipFileInput"
                type="file"
                multiple
                accept=".shp,.shx,.dbf,.prj,.geojson,.json"
                class="sr-only"
                @change="handleSingleClipUpload"
              />
              <AoiMapPicker
                v-model="state.clipExtent"
                :bbox="state.clipBbox"
                :geojson="state.clipGeoJson"
                :coverage-geojson="state.sceneCoverageGeoJson"
                :coverage-bbox="state.sceneCoverageBbox"
                :status-text="singleClipStatusText"
                label="当前 ROI"
                :height="250"
                @drawend="onSingleClipDraw"
                @clear="clearSingleClipSelection"
              />
              <div class="clip-meta-grid">
                <div class="clip-meta-pill">
                  <strong>来源</strong>
                  <span>{{ state.clipAoiSourceType || '未设置' }}</span>
                </div>
                <div class="clip-meta-pill">
                  <strong>要素</strong>
                  <span>{{ state.clipAoiFeatureCount || 0 }}</span>
                </div>
                <div class="clip-meta-pill">
                  <strong>覆盖校验</strong>
                  <span>{{ singleCoverageStateLabel }}</span>
                </div>
                <div class="clip-meta-pill clip-meta-pill-wide">
                  <strong>矢量文件</strong>
                  <span>{{ singleClipFileSummary }}</span>
                </div>
              </div>
            </div>

            <label class="field-compact full">
              <span>裁剪范围（xmin,ymin,xmax,ymax）</span>
              <input
                v-model="state.clipExtent"
                type="text"
                placeholder="xmin,ymin,xmax,ymax"
                @change="syncSingleClipExtentPreview"
              />
            </label>

            <label class="field-compact">
              <span>大气校正</span>
              <select v-model="state.atmMethod" :disabled="state.productLevel === 'L2'">
                <option value="DOS">DOS</option>
                <option value="6S">6S</option>
              </select>
            </label>

            <label class="field-compact checkfield">
              <input v-model="state.applyCloudMask" type="checkbox" />
              <span>云掩膜</span>
            </label>
          </template>

          <!-- 合成类型 -->
          <div class="field-compact full">
            <span>合成类型（{{ state.selectedComposites.length }} 个）</span>
            <div class="chips-compact">
              <button
                v-for="item in state.composites.slice(0, 12)"
                :key="item.type"
                class="chip-compact"
                :class="{ active: state.selectedComposites.includes(item.type) }"
                @click="toggleComposite(item.type)"
              >
                {{ item.name }}
              </button>
              <button v-if="state.composites.length > 12" class="chip-compact more" @click="switchTab('indices')">
                +{{ state.composites.length - 12 }} 更多...
              </button>
            </div>
          </div>

          <!-- 自定义公式 -->
          <label class="field-compact">
            <span>自定义公式</span>
            <input v-model="state.customFormula" type="text" placeholder="(B5-B4)/(B5+B4)" />
          </label>

          <label class="field-compact">
            <span>公式名称</span>
            <input v-model="state.customName" type="text" placeholder="my_ndvi" />
          </label>
        </div>

        <div class="actions-compact">
          <button class="btn pri" :disabled="!canSubmit" @click="submitTask">
            {{ state.submitting ? '提交中...' : '提交任务' }}
          </button>
          <button class="btn sub" @click="resetForm">重置</button>
        </div>
      </article>

      <article class="card monitor-card-compact">
        <div class="title-row-compact">
          <h2>任务监控</h2>
          <small>{{ statusLabel }}</small>
        </div>

        <div class="query-row-compact">
          <input v-model="state.manualJobId" type="text" placeholder="job_id" />
          <button class="btn-mini pri" @click="queryStatus()">查询</button>
          <label class="poll-compact">
            <input v-model="state.polling" type="checkbox" @change="restartPolling" />
            <span>轮询</span>
          </label>
        </div>

        <div class="progress-track-compact">
          <div class="progress-fill" :style="{ width: `${progressValue}%` }"></div>
        </div>
        <p class="meta-compact">{{ state.progress?.detail || '等待任务' }} {{ progressValue }}%</p>

        <div class="result-box-compact">
          <strong>产物列表</strong>
          <div v-if="resultItems.length" class="result-list-compact">
            <button v-for="item in resultItems" :key="`${item.group}-${item.label}`" class="result-item-compact" @click="loadPreview(item.path)">
              {{ item.label }}
            </button>
          </div>
          <p v-else class="empty-compact">暂无产物</p>
        </div>
      </article>

      <article class="card preview-card-compact">
        <div class="title-row-compact">
          <h2>影像预览</h2>
        </div>

        <div class="preview-query-compact">
          <input v-model="state.previewPath" type="text" placeholder="路径" />
          <input v-model="state.previewSize" type="number" min="128" max="1024" style="width: 70px;" />
          <button class="btn-mini pri" @click="loadPreview()">加载</button>
        </div>

        <div class="preview-frame-compact">
          <img v-if="state.previewImage" :src="state.previewImage" alt="preview" />
          <p v-else class="empty-compact">等待预览</p>
        </div>
      </article>
    </section>

    <!-- Batch Processing View -->
    <section v-if="state.currentTab === 'batch'" class="batch-view">
      <BatchManager :api-base="normalizedApiBase()" @toast="handleBatchToast" />
    </section>

    <section v-if="state.currentTab === 'download'" class="download-view">
      <LandsatDownload :api-base="normalizedApiBase()" @toast="handleBatchToast" />
    </section>

    <!-- Indices Encyclopedia View -->
    <section v-if="state.currentTab === 'indices'" class="indices-view">
      <IndicesInfo />
    </section>

    <p v-if="state.toast" :class="toastClass()">{{ state.toast }}</p>

    <div v-if="state.pathPickerOpen" class="picker-mask" @click.self="closePathPicker">
      <div class="picker-dialog card">
        <div class="picker-head">
          <h3>选择输出路径</h3>
          <button class="btn sub" type="button" @click="closePathPicker">关闭</button>
        </div>

        <!-- 面包屑导航 -->
        <div v-if="state.pathPickerBreadcrumbs.length" class="breadcrumbs">
          <button
            v-for="(crumb, index) in state.pathPickerBreadcrumbs"
            :key="crumb.path"
            class="breadcrumb-item"
            type="button"
            @click="navigateToBreadcrumb(crumb.path)"
          >
            {{ crumb.name }}
            <span v-if="index < state.pathPickerBreadcrumbs.length - 1" class="separator">\</span>
          </button>
        </div>

        <p class="picker-current">
          当前目录：<code>{{ state.pathPickerCurrent || '根目录' }}</code>
        </p>

        <!-- 快捷路径 -->
        <div class="quick-paths">
          <span class="quick-label">快捷访问：</span>
          <button
            v-for="quick in getQuickPaths()"
            :key="quick.path"
            class="quick-btn"
            type="button"
            @click="useQuickPath(quick.path)"
          >
            {{ quick.name }}
          </button>
        </div>

        <div class="picker-actions">
          <button class="btn sub" type="button" :disabled="!state.pathPickerParent || state.pathPickerLoading" @click="enterPath(state.pathPickerParent)">
            返回上级
          </button>
          <button class="btn sub" type="button" :disabled="state.pathPickerLoading" @click="loadPathPicker(state.pathPickerCurrent)">
            刷新目录
          </button>
          <button class="btn pri" type="button" :disabled="!state.pathPickerCurrent || state.pathPickerLoading" @click="selectCurrentPath">
            选择当前目录
          </button>
        </div>

        <p v-if="state.pathPickerError" class="err-line">{{ state.pathPickerError }}</p>
        <p v-if="state.pathPickerLoading" class="meta-line">读取目录中...</p>
        <p v-else-if="!state.pathPickerDirectories.length" class="meta-line">当前目录没有子目录</p>

        <ul v-else class="picker-list">
          <li v-for="item in state.pathPickerDirectories" :key="item.path">
            <button class="picker-item" type="button" @click="enterPath(item.path)">
              <div class="picker-item-content">
                <strong>{{ item.name }}</strong>
                <small>{{ item.path }}</small>
              </div>
            </button>
          </li>
        </ul>
      </div>
    </div>
  </main>
</template>

<style scoped>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.clip-visual-field {
  gap: 10px;
}

.clip-visual-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.clip-visual-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.clip-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.clip-meta-pill {
  min-width: 0;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(206, 217, 212, 0.9);
  background: rgba(248, 251, 250, 0.94);
}

.clip-meta-pill strong {
  display: block;
  font-size: 11px;
  color: #4a5d56;
}

.clip-meta-pill span {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #1f312c;
  word-break: break-all;
}

.clip-meta-pill-wide {
  grid-column: span 1;
}

.btn-mini.ghost {
  background: #fff;
  color: #33564b;
}

@media (max-width: 900px) {
  .clip-meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
