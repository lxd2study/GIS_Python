<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import AoiMapPicker from './components/AoiMapPicker.vue'
import {
  ALL_BANDS,
  CORE_BANDS,
  SENTINEL_ALL_BANDS,
  SENTINEL_COMPOSITE_ORDER,
  SENTINEL_CORE_BANDS,
  fallbackComposites,
} from './config/processingOptions'
import { apiRequest, normalizeApiBase } from './utils/apiClient'
import { assessCoverage } from './utils/coverage'

const BatchManager = defineAsyncComponent(() => import('./components/BatchManager.vue'))
const IndicesInfo = defineAsyncComponent(() => import('./components/IndicesInfo.vue'))
const LandsatDownload = defineAsyncComponent(() => import('./components/LandsatDownload.vue'))
const TaskAssetCenter = defineAsyncComponent(() => import('./components/TaskAssetCenter.vue'))

const ENV_API = (import.meta.env.VITE_API_BASE_URL || '').trim()
const HISTORY_KEY = 'rst_output_history'
const API_KEY = 'rst_vue_api_base'
const OUTPUT_MODE_KEY = 'rst_output_mode'
const OUTPUT_BASE_KEY = 'rst_output_base'
const OUTPUT_MANUAL_KEY = 'rst_output_manual'
const CURRENT_TAB_KEY = 'rst_current_tab'
const ADVANCED_OPEN_KEY = 'rst_single_advanced_open'
const PREVIEW_SIZE_KEY = 'rst_preview_size'
const VALID_TABS = ['single', 'batch', 'download', 'results', 'indices']
const RESULT_GROUP_LABELS = {
  processed: '处理波段',
  composite: '合成与指数',
  mask: '质量掩膜',
  binary: '二值化结果',
  derived: '派生产物',
}
const TOAST_DURATION = {
  idle: 2200,
  ok: 2600,
  warn: 3600,
  error: 5200
}

function loadHistory() {
  try {
    const value = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
    return Array.isArray(value) ? value.filter((item) => typeof item === 'string') : []
  } catch {
    return []
  }
}

function loadSavedTab() {
  const saved = localStorage.getItem(CURRENT_TAB_KEY)
  return VALID_TABS.includes(saved) ? saved : 'single'
}

function loadPreviewSize() {
  const value = Number(localStorage.getItem(PREVIEW_SIZE_KEY))
  return Number.isFinite(value) ? Math.max(128, Math.min(2048, value)) : 768
}

const state = reactive({
  apiBase: localStorage.getItem(API_KEY) || ENV_API || 'http://127.0.0.1:5001',
  currentTab: loadSavedTab(),
  health: null,
  sensor: 'landsat',
  inputSource: 'upload',
  composites: [],
  serverResourceRoot: '',
  serverRootLoading: false,
  serverScenes: [],
  serverScenesLoading: false,
  serverSceneError: '',
  selectedServerScenePath: '',
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
  showAdvancedOptions: localStorage.getItem(ADVANCED_OPEN_KEY) === '1',
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
  derivedResults: [],
  previewPath: '',
  previewSize: loadPreviewSize(),
  previewImage: '',
  previewMeta: null,
  binaryThreshold: '0',
  binaryUpperThreshold: '',
  binaryComparison: 'gte',
  binaryOutputPath: '',
  binaryRunning: false,
  binaryResult: null
})

let timer = null
const clipFileInput = ref(null)
let singleCoverageRequestId = 0

function normalizedApiBase() {
  return normalizeApiBase(state.apiBase)
}

function bandSortValue(band) {
  if (band === 'B8A') return 8.5
  return Number(String(band || '').replace(/^B0?/, '')) || 999
}

function detectBandName(filename, sensor = state.sensor) {
  const upper = filename.toUpperCase()
  if (sensor === 'sentinel-2') {
    const match = upper.match(/(?:^|[_-])B(0[1-9]|1[0-2]|8A)(?:[_\-.]|$)/)
    if (!match) return null
    return match[1] === '8A' ? 'B8A' : `B${match[1]}`
  }
  const match = upper.match(/(?:^|[_-])B(1[0-1]|[1-9])(?:[_\-.]|$)/)
  return match ? `B${Number(match[1])}` : null
}

function inferSceneName(files) {
  const counts = new Map()
  for (const file of files) {
    const name = file.name.replace(/\.[^.]+$/, '')
    const match = name.match(/(.+?)_B(?:0[1-9]|1[0-2]|8A|1[0-1]|[1-9])(?:_|$)/i)
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

function normalizeProductLevel(value, fallback = 'L1') {
  const normalized = String(value || '').trim().toUpperCase()
  if (normalized === 'L1' || normalized === 'L2' || normalized === 'L2A') return normalized
  return fallback
}

function normalizeBbox(value) {
  if (!Array.isArray(value) || value.length !== 4) return null
  const numbers = value.map((item) => Number(item))
  return numbers.every((item) => Number.isFinite(item)) ? numbers : null
}

function shortPath(path, keepSegments = 2) {
  if (!path) return ''
  const parts = String(path).replace(/\\/g, '/').split('/').filter(Boolean)
  return parts.length <= keepSegments ? String(path) : `.../${parts.slice(-keepSegments).join('/')}`
}

function getSceneAvailableLevels(scene) {
  const base = Array.isArray(scene?.available_product_levels) && scene.available_product_levels.length
    ? scene.available_product_levels
    : [scene?.product_level]
  return [...new Set(base.map((item) => normalizeProductLevel(item, '')).filter(Boolean))]
}

function sceneSupportsProductLevel(scene, level) {
  const normalized = normalizeProductLevel(level)
  const levels = getSceneAvailableLevels(scene)
  return !levels.length || levels.includes(normalized)
}

function saveOutputPrefs() {
  localStorage.setItem(OUTPUT_MODE_KEY, state.outputMode)
  localStorage.setItem(OUTPUT_BASE_KEY, state.outputBaseDir.trim())
  localStorage.setItem(OUTPUT_MANUAL_KEY, state.outputDirManual.trim())
}

function setProcessingSensor(sensor) {
  if (!['landsat', 'sentinel-2'].includes(sensor) || state.sensor === sensor) return
  state.sensor = sensor
  state.productLevel = sensor === 'sentinel-2' ? 'L2A' : 'L1'
  state.selectedComposites = sensor === 'sentinel-2' ? ['apgi'] : ['true_color', 'ndvi']
  state.mtlFile = null
  state.qaFile = null
  state.qaRadsatFile = null
  state.applyCloudMask = false
  state.atmMethod = sensor === 'sentinel-2' ? 'NONE' : 'DOS'
  resetSingleSceneCoverage()
  if (state.bands.length) void loadSingleSceneCoverage(state.bands)
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

async function request(path, options = {}) {
  return apiRequest(normalizedApiBase(), path, options)
}

const bandAnalysis = computed(() => {
  const map = new Map()
  const unknown = []
  state.bands.forEach((file) => {
    const band = detectBandName(file.name, state.sensor)
    if (!band) {
      unknown.push(file.name)
      return
    }
    if (!map.has(band)) map.set(band, [])
    map.get(band).push(file.name)
  })

  const recognized = [...map.entries()]
    .map(([band, files]) => ({ band, files }))
    .sort((a, b) => bandSortValue(a.band) - bandSortValue(b.band))

  const duplicates = recognized.filter((item) => item.files.length > 1)
  const recognizedBands = new Set(recognized.map((item) => item.band))
  const requiredCore = state.sensor === 'sentinel-2' ? SENTINEL_CORE_BANDS : CORE_BANDS
  const allBands = state.sensor === 'sentinel-2' ? SENTINEL_ALL_BANDS : ALL_BANDS
  const missingCore = requiredCore.filter((band) => !recognizedBands.has(band))
  const missingAll = allBands.filter((band) => !recognizedBands.has(band))
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

const selectedServerScene = computed(() => {
  return state.serverScenes.find((scene) => scene.path === state.selectedServerScenePath) || null
})

const serverSceneAvailableLevels = computed(() => getSceneAvailableLevels(selectedServerScene.value))

const activeProductLevel = computed(() => normalizeProductLevel(state.productLevel))
const isSentinel2Mode = computed(() => state.sensor === 'sentinel-2')
const compositeOptions = computed(() => {
  const options = state.composites.length ? state.composites : fallbackComposites
  if (!isSentinel2Mode.value) return options.filter((item) => item.type !== 'apgi')

  const order = new Map(SENTINEL_COMPOSITE_ORDER.map((type, index) => [type, index]))
  return [...options].sort((a, b) => {
    const aOrder = order.has(a.type) ? order.get(a.type) : 100
    const bOrder = order.has(b.type) ? order.get(b.type) : 100
    if (aOrder !== bOrder) return aOrder - bOrder
    return a.name.localeCompare(b.name, 'zh-CN')
  })
})

const outputSceneResolved = computed(() => {
  const fallbackSceneName = state.inputSource === 'server'
    ? selectedServerScene.value?.name
    : bandAnalysis.value.sceneHint
  return sanitizeSceneName(state.outputSceneName || fallbackSceneName || 'scene')
})

const outputDirResolved = computed(() => {
  if (state.outputMode === 'manual') return state.outputDirManual.trim()
  return joinPath(state.outputBaseDir, outputSceneResolved.value)
})

const selectedBandCount = computed(() => state.bands.length)
const serviceOk = computed(() => state.health?.status === 'healthy')
const statusLabel = computed(() => state.progress?.status || 'pending')
const progressValue = computed(() => Number(state.progress?.progress || 0))
const singleInputSummaryText = computed(() => {
  if (state.inputSource === 'server') {
    if (selectedServerScene.value) return '已选 1 景'
    return `${state.serverScenes.length} 景可选`
  }
  return `${selectedBandCount.value} 文件`
})
const suggestedOutputSceneName = computed(() => {
  if (state.inputSource === 'server') {
    return sanitizeSceneName(selectedServerScene.value?.name || '')
  }
  return bandAnalysis.value.sceneHint
})

const pathPickerTitle = computed(() => {
  if (state.pathPickerTarget === 'base') return '选择输出基路径'
  if (state.pathPickerTarget === 'manual') return '选择输出目录'
  if (state.pathPickerTarget === 'serverRoot') return '选择资源根目录'
  return '选择目录'
})

const singleReadinessItems = computed(() => {
  const items = []
  const outputDir = outputDirResolved.value.trim()
  const hasOutput = outputDir.length > 0

  if (state.inputSource === 'server') {
    const hasRoot = normalizePath(state.serverResourceRoot).length > 0
    items.push({
      key: 'input',
      label: '输入数据',
      status: selectedServerScene.value ? 'ok' : 'blocked',
      text: selectedServerScene.value
        ? `已选择 ${selectedServerScene.value.name || shortPath(selectedServerScene.value.path, 2)}`
        : (hasRoot ? '已设置根目录，请扫描并选择场景' : '请先选择资源根目录并扫描场景'),
    })
  } else {
    const bandStatus = selectedBandCount.value > 0
      ? (bandAnalysis.value.duplicates.length ? 'blocked' : (bandAnalysis.value.missingCore.length ? 'warn' : 'ok'))
      : 'blocked'
    items.push({
      key: 'input',
      label: '输入数据',
      status: bandStatus,
      text: selectedBandCount.value > 0
        ? `${selectedBandCount.value} 个文件，识别 ${bandAnalysis.value.recognized.length} 个波段`
        : '请上传 GeoTIFF/IMG 波段文件',
    })
  }

  items.push({
    key: 'output',
    label: '输出目录',
    status: hasOutput ? 'ok' : 'blocked',
    text: hasOutput ? shortPath(outputDir, 3) : '请设置输出目录',
  })

  if (state.inputSource === 'upload' && bandAnalysis.value.duplicates.length) {
    items.push({
      key: 'duplicates',
      label: '波段冲突',
      status: 'blocked',
      text: `重复波段：${bandAnalysis.value.duplicates.map((item) => item.band).join(', ')}`,
    })
  } else if (state.inputSource === 'upload' && bandAnalysis.value.missingCore.length) {
    items.push({
      key: 'missingCore',
      label: '核心波段',
      status: 'warn',
      text: `缺少核心波段：${bandAnalysis.value.missingCore.join(', ')}`,
    })
  } else {
    items.push({
      key: 'bands',
      label: '波段识别',
      status: state.inputSource === 'server' || selectedBandCount.value > 0 ? 'ok' : 'blocked',
      text: state.inputSource === 'server' ? '使用在线场景元数据' : '未发现阻塞项',
    })
  }

  const coverageStatus = singleCoverageValidation.value.status
  if (state.sceneCoverageLoading && singleClipRoiBbox.value) {
    items.push({ key: 'roi', label: 'ROI 覆盖', status: 'blocked', text: '正在读取覆盖范围，请稍候' })
  } else if (['partial', 'outside'].includes(coverageStatus)) {
    items.push({
      key: 'roi',
      label: 'ROI 覆盖',
      status: 'blocked',
      text: coverageStatus === 'partial' ? 'ROI 部分超出影像覆盖范围' : 'ROI 完全不在影像覆盖范围内',
    })
  } else if (singleClipRoiBbox.value) {
    items.push({
      key: 'roi',
      label: 'ROI 覆盖',
      status: state.sceneCoverageBbox ? 'ok' : 'warn',
      text: state.sceneCoverageBbox ? 'ROI 可用于裁剪' : '未加载影像覆盖范围，提交时仍会按 ROI 裁剪',
    })
  } else {
    items.push({ key: 'roi', label: 'ROI 覆盖', status: 'ok', text: '未设置裁剪 ROI，将处理完整影像' })
  }

  items.push({
    key: 'composites',
    label: '合成项',
    status: state.selectedComposites.length ? 'ok' : 'warn',
    text: state.selectedComposites.length ? `已选 ${state.selectedComposites.length} 项` : '未选择合成项，仅输出基础处理结果',
  })

  const hasFormula = state.customFormula.trim().length > 0
  items.push({
    key: 'formula',
    label: '自定义公式',
    status: hasFormula && !state.customName.trim() ? 'warn' : 'ok',
    text: hasFormula
      ? (state.customName.trim() ? `输出名 ${state.customName.trim()}` : '未填写名称，将使用后端默认命名')
      : '未启用',
  })

  return items
})

const singleSubmitBlockReason = computed(() => {
  if (state.submitting) return '任务正在提交'
  const blocked = singleReadinessItems.value.find((item) => item.status === 'blocked')
  return blocked ? `${blocked.label}：${blocked.text}` : ''
})

const canSubmit = computed(() => {
  return !singleSubmitBlockReason.value
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
  state.derivedResults.forEach((item) => {
    list.push({ label: item.label, path: item.path, group: item.group || 'derived' })
  })
  return list
})

const groupedResultItems = computed(() => {
  const groups = []
  resultItems.value.forEach((item) => {
    const key = item.group || 'derived'
    let group = groups.find((entry) => entry.key === key)
    if (!group) {
      group = {
        key,
        label: RESULT_GROUP_LABELS[key] || RESULT_GROUP_LABELS.derived,
        items: [],
      }
      groups.push(group)
    }
    group.items.push(item)
  })
  return groups
})

const currentJobId = computed(() => (state.manualJobId || state.jobId || '').trim())
const hasTerminalProgress = computed(() => ['success', 'error', 'partial'].includes(state.progress?.status))
const previewDisplayName = computed(() => {
  if (!state.previewPath) return '等待预览'
  return fileStem(state.previewPath)
})
const binaryDisabledReason = computed(() => {
  if (state.binaryRunning) return '二值化处理中'
  if (!state.previewPath) return '请先加载一个栅格结果'
  return ''
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
  void loadServerDownloadRoot({ force: true, silent: true })
}

async function loadServerDownloadRoot({ force = false, silent = false } = {}) {
  if (state.serverRootLoading) return

  state.serverRootLoading = true
  try {
    const data = await request('/imagery/download_dir')
    const nextRoot = normalizePath(data.download_dir || data.default_download_dir || '')
    const currentRoot = normalizePath(state.serverResourceRoot)
    if (nextRoot && (force || !normalizePath(state.serverResourceRoot))) {
      state.serverResourceRoot = nextRoot
      if (nextRoot !== currentRoot) {
        state.serverScenes = []
        state.selectedServerScenePath = ''
        state.serverSceneError = ''
        if (state.inputSource === 'server') resetSingleSceneCoverage()
      }
    }
  } catch (error) {
    if (!silent) setToast(`读取在线资源根目录失败：${error.message}`, 'error')
  } finally {
    state.serverRootLoading = false
  }
}

function handleServerRootEdited() {
  state.serverResourceRoot = normalizePath(state.serverResourceRoot)
  state.serverScenes = []
  state.selectedServerScenePath = ''
  state.serverSceneError = ''
  resetSingleSceneCoverage()
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
  } else if (target === 'serverRoot') {
    start = normalizePath(state.serverResourceRoot)
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

async function selectCurrentPath() {
  const selected = normalizePath(state.pathPickerCurrent)
  if (!selected) return
  const target = state.pathPickerTarget
  let message = ''

  if (target === 'base') {
    state.outputBaseDir = selected
    state.outputMode = 'auto'
    message = `已选择输出基路径：${selected}`
  } else if (target === 'serverRoot') {
    state.serverResourceRoot = selected
  } else {
    state.outputDirManual = selected
    state.outputMode = 'manual'
    message = `已选择输出路径：${selected}`
  }

  if (target === 'base' || target === 'manual') {
    saveOutputPrefs()
  }
  closePathPicker()
  if (target === 'serverRoot') {
    await scanServerScenes()
    return
  }
  setToast(message, 'ok')
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
  singleCoverageRequestId += 1
  state.sceneCoverageGeoJson = null
  state.sceneCoverageBbox = null
  state.sceneCoverageLabel = ''
  state.sceneCoverageLoading = false
  state.sceneCoverageError = ''
}

function applySingleSceneCoveragePayload(payload, fallbackLabel = '') {
  state.sceneCoverageGeoJson = payload?.geojson || null
  state.sceneCoverageBbox = normalizeBbox(payload?.bbox)
  state.sceneCoverageLabel = payload?.label || fallbackLabel
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

async function loadServerSceneCoverage(scene = selectedServerScene.value, { silent = false } = {}) {
  const currentRequestId = ++singleCoverageRequestId
  if (!scene?.path) {
    resetSingleSceneCoverage()
    return
  }

  const availableLevels = getSceneAvailableLevels(scene)
  const preferredLevel = normalizeProductLevel(scene?.product_level, availableLevels[0] || activeProductLevel.value)
  const targetLevel = sceneSupportsProductLevel(scene, activeProductLevel.value) ? activeProductLevel.value : preferredLevel
  if (state.productLevel !== targetLevel) state.productLevel = targetLevel

  state.sceneCoverageLoading = true
  state.sceneCoverageError = ''
  try {
    const defaultFootprint = normalizeBbox(scene?.footprint_bbox)
    const defaultLevel = normalizeProductLevel(scene?.product_level, targetLevel)
    const sceneLabel = scene?.name || shortPath(scene?.path, 2)

    if (defaultFootprint && defaultLevel === targetLevel) {
      if (currentRequestId !== singleCoverageRequestId) return
      applySingleSceneCoveragePayload({ bbox: defaultFootprint, label: sceneLabel }, sceneLabel)
      return
    }

    const body = new FormData()
    body.append('path', scene.path)
    body.append('product_level', targetLevel)
    const data = await request('/filesystem/raster_footprint', { method: 'POST', body })
    if (currentRequestId !== singleCoverageRequestId) return
    applySingleSceneCoveragePayload(data, sceneLabel)
  } catch (error) {
    if (currentRequestId !== singleCoverageRequestId) return
    state.sceneCoverageGeoJson = null
    state.sceneCoverageBbox = null
    state.sceneCoverageLabel = ''
    state.sceneCoverageError = error.message
    if (!silent) setToast(`读取在线资源覆盖范围失败：${error.message}`, 'warn')
  } finally {
    if (currentRequestId === singleCoverageRequestId) {
      state.sceneCoverageLoading = false
    }
  }
}

async function scanServerScenes(silent = false) {
  const root = normalizePath(state.serverResourceRoot)
  if (!root) {
    if (!silent) setToast('请先选择资源根目录', 'warn')
    return
  }

  state.serverScenesLoading = true
  state.serverSceneError = ''
  const previousSelection = state.selectedServerScenePath
  try {
    const data = await request(`/filesystem/scan_scenes?path=${encodeURIComponent(root)}`)
    state.serverScenes = Array.isArray(data.scenes) ? data.scenes : []

    const matchedScene = previousSelection
      ? state.serverScenes.find((scene) => scene.path === previousSelection) || null
      : null
    if (matchedScene) {
      await loadServerSceneCoverage(matchedScene, { silent: true })
    } else {
      state.selectedServerScenePath = ''
      resetSingleSceneCoverage()
    }

    if (!silent) setToast(`在线资源扫描完成：${state.serverScenes.length} 景`, 'ok')
  } catch (error) {
    state.serverScenes = []
    state.selectedServerScenePath = ''
    resetSingleSceneCoverage()
    state.serverSceneError = error.message
    if (!silent) setToast(`扫描在线资源失败：${error.message}`, 'error')
  } finally {
    state.serverScenesLoading = false
  }
}

function selectServerScene(scene) {
  if (!scene?.path) return

  state.selectedServerScenePath = scene.path
  if (scene.sensor === 'sentinel-2') {
    state.sensor = 'sentinel-2'
    state.productLevel = 'L2A'
    if (!state.selectedComposites.includes('apgi')) state.selectedComposites = ['apgi']
  } else if (scene.sensor && scene.sensor !== state.sensor) {
    state.sensor = 'landsat'
    if (state.productLevel === 'L2A') state.productLevel = 'L1'
    state.selectedComposites = state.selectedComposites.filter((type) => type !== 'apgi')
    if (!state.selectedComposites.length) {
      state.selectedComposites = ['true_color', 'ndvi']
    }
  }
  const availableLevels = getSceneAvailableLevels(scene)
  const preferredLevel = normalizeProductLevel(scene?.product_level, availableLevels[0] || activeProductLevel.value)
  if (!sceneSupportsProductLevel(scene, activeProductLevel.value)) {
    state.productLevel = preferredLevel
  }
  void loadServerSceneCoverage(scene)
}

async function switchInputSource(source) {
  if (!['upload', 'server'].includes(source) || state.inputSource === source) return

  state.inputSource = source
  if (source === 'server') {
    await loadServerDownloadRoot({ silent: true })
    if (!state.serverScenes.length && normalizePath(state.serverResourceRoot)) {
      await scanServerScenes(true)
    } else if (selectedServerScene.value) {
      await loadServerSceneCoverage(selectedServerScene.value, { silent: true })
    } else {
      resetSingleSceneCoverage()
    }
    return
  }

  if (state.bands.length) {
    await loadSingleSceneCoverage(state.bands)
  } else {
    resetSingleSceneCoverage()
  }
}

function toggleComposite(type) {
  if (!isSentinel2Mode.value && type === 'apgi') return
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
  if (suggestedOutputSceneName.value) {
    state.outputSceneName = suggestedOutputSceneName.value
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
  if (!canSubmit.value) {
    setToast(singleSubmitBlockReason.value || '请先完成必填配置', 'warn')
    return
  }
  state.submitting = true
  setToast('提交任务中...', 'idle')
  state.previewImage = ''
  state.previewMeta = null

  try {
    const targetProductLevel = activeProductLevel.value
    const sentinelMode = isSentinel2Mode.value
    state.derivedResults = []
    state.binaryResult = null
    if (state.sceneCoverageLoading && singleClipRoiBbox.value) {
      setToast('正在读取影像覆盖范围，请稍候再提交', 'warn')
      return
    }
    if (['partial', 'outside'].includes(singleCoverageValidation.value.status)) {
      setToast('当前 ROI 超出影像覆盖范围，请先调整裁剪区域', 'error')
      return
    }

    const body = new FormData()
    if (state.inputSource === 'server') {
      if (!selectedServerScene.value?.path) {
        setToast('请先选择在线资源场景', 'warn')
        return
      }
      body.append('scene_path', selectedServerScene.value.path)
    } else {
      state.bands.forEach((file) => body.append('bands', file))
      if (!sentinelMode && state.mtlFile) body.append('mtl_file', state.mtlFile)
      if (!sentinelMode && state.qaFile) body.append('qa_band', state.qaFile)
      if (!sentinelMode && state.qaRadsatFile) body.append('qa_radsat_band', state.qaRadsatFile)
    }
    state.shapeFiles.forEach((file) => body.append('clip_shapefile', file))

    body.append('output_dir', outputDirResolved.value)
    body.append('apply_cloud_mask', String(!sentinelMode && state.applyCloudMask))
    body.append('atm_correction_method', sentinelMode ? 'NONE' : state.atmMethod)
    body.append('product_level', targetProductLevel)

    if (state.clipExtent.trim()) body.append('clip_extent', state.clipExtent.trim())
    if (state.selectedComposites.length) body.append('create_composites', state.selectedComposites.join(','))
    if (state.customFormula.trim()) {
      body.append('custom_formula', state.customFormula.trim())
      if (state.customName.trim()) body.append('custom_name', state.customName.trim())
    }

    const endpoint = state.inputSource === 'server'
      ? (sentinelMode ? '/filesystem/preprocess_sentinel2_async' : '/filesystem/preprocess_landsat8_async')
      : (sentinelMode ? '/preprocess_sentinel2_async' : '/preprocess_landsat8_async')
    const data = await request(endpoint, { method: 'POST', body })
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
    if (['success', 'error', 'partial'].includes(task.status)) {
      stopPolling()
      if (task.status === 'success' || task.status === 'partial') {
        await loadFirstPreviewResult()
      }
    }
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
  state.selectedServerScenePath = ''
  state.shapeFiles = []
  state.productLevel = isSentinel2Mode.value ? 'L2A' : 'L1'
  state.clipExtent = ''
  resetSingleClipPreview()
  resetSingleSceneCoverage()
  if (clipFileInput.value) clipFileInput.value.value = ''
  state.selectedComposites = isSentinel2Mode.value ? ['apgi'] : ['true_color', 'ndvi']
  state.customFormula = ''
  state.customName = ''
  state.applyCloudMask = false
  state.atmMethod = isSentinel2Mode.value ? 'NONE' : 'DOS'
  state.derivedResults = []
  state.binaryResult = null
  state.binaryOutputPath = ''
  setToast('表单已重置', 'idle')
}

async function loadFirstPreviewResult() {
  const first = resultItems.value[0]
  if (!first?.path || (state.previewImage && state.previewPath === first.path)) return
  await loadPreview(first.path)
}

const singleClipRoiBbox = computed(() => {
  return state.clipBbox || parseExtentText(state.clipExtent)
})

const singleCoverageValidation = computed(() => {
  return assessCoverage(singleClipRoiBbox.value, state.sceneCoverageBbox ? [state.sceneCoverageBbox] : [])
})

const singleClipStatusText = computed(() => {
  if (state.inputSource === 'server' && !selectedServerScene.value) return '请先扫描并选择一个在线场景，再进行 ROI 校验'
  if (state.inputSource === 'upload' && !state.bands.length && !state.sceneCoverageBbox) return '请先上传波段文件，再进行 ROI 校验'
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
  if (state.inputSource === 'server' && !selectedServerScene.value) return '未选景'
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

function fileStem(path) {
  const filename = String(path || '').split(/[\\/]/).pop() || ''
  return filename.replace(/\.[^.]+$/, '') || 'binary'
}

function binaryNeedsUpperThreshold() {
  return ['between', 'outside'].includes(state.binaryComparison)
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '--'
  return Number(value).toLocaleString('zh-CN', {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  })
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '--'
  return `${(Number(value) * 100).toFixed(2)}%`
}

async function loadPreview(path = '', options = {}) {
  const targetPath = (path || state.previewPath).trim()
  if (!targetPath) {
    setToast('请输入预览文件路径', 'warn')
    return
  }

  try {
    const body = new FormData()
    body.append('file_path', targetPath)
    const previewSize = Math.max(128, Math.min(2048, Number(state.previewSize) || 768))
    state.previewSize = previewSize
    localStorage.setItem(PREVIEW_SIZE_KEY, String(previewSize))
    body.append('max_size', String(previewSize))
    const data = await request('/preview_raster', { method: 'POST', body })
    if (!options.preserveBinaryResult && targetPath !== state.previewPath) {
      state.binaryResult = null
      state.binaryOutputPath = ''
    }
    state.previewPath = targetPath
    state.previewMeta = data.preview
    state.previewImage = `data:image/png;base64,${data.preview.base64}`
    setToast('预览加载完成', 'ok')
  } catch (error) {
    setToast(`预览失败：${error.message}`, 'error')
  }
}

async function runBinarization() {
  const targetPath = state.previewPath.trim()
  if (!targetPath) {
    setToast('请先选择或加载一个栅格结果', 'warn')
    return
  }

  const threshold = Number(state.binaryThreshold)
  if (!Number.isFinite(threshold)) {
    setToast('请输入有效阈值', 'warn')
    return
  }

  const upperText = String(state.binaryUpperThreshold).trim()
  const upperThreshold = Number(upperText)
  if (binaryNeedsUpperThreshold() && (!upperText || !Number.isFinite(upperThreshold))) {
    setToast('请输入有效上限阈值', 'warn')
    return
  }

  state.binaryRunning = true
  try {
    const body = new FormData()
    body.append('file_path', targetPath)
    body.append('threshold', String(threshold))
    body.append('comparison', state.binaryComparison)
    if (binaryNeedsUpperThreshold()) body.append('upper_threshold', String(upperThreshold))
    if (state.binaryOutputPath.trim()) body.append('output_path', state.binaryOutputPath.trim())

    const result = await request('/raster/binarize', { method: 'POST', body })
    state.binaryResult = result
    state.binaryOutputPath = ''
    state.derivedResults = [
      { label: `${fileStem(result.output_path)}`, path: result.output_path, group: 'binary' },
      ...state.derivedResults.filter((item) => item.path !== result.output_path),
    ].slice(0, 8)
    await loadPreview(result.output_path, { preserveBinaryResult: true })
    setToast('二值化与面积统计完成', 'ok')
  } catch (error) {
    setToast(`二值化失败：${error.message}`, 'error')
  } finally {
    state.binaryRunning = false
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
  if (!VALID_TABS.includes(tab)) return
  state.currentTab = tab
  localStorage.setItem(CURRENT_TAB_KEY, tab)
}

function toggleAdvancedOptions() {
  state.showAdvancedOptions = !state.showAdvancedOptions
  localStorage.setItem(ADVANCED_OPEN_KEY, state.showAdvancedOptions ? '1' : '0')
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
  if (!text) {
    setToast('没有可复制的内容', 'warn')
    return
  }
  if (!navigator.clipboard?.writeText) {
    setToast('复制失败，请手动复制', 'warn')
    return
  }
  navigator.clipboard.writeText(text).then(() => {
    setToast('已复制到剪贴板', 'ok')
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
  void loadServerDownloadRoot({ silent: true })

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
  <main class="page" :class="state.currentTab === 'indices' || state.currentTab === 'download' || state.currentTab === 'results' ? 'scrollable' : 'no-scroll'">
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
    <section class="tabs-bar" role="tablist" aria-label="主功能导航">
      <button
        class="tab-btn"
        :class="{ active: state.currentTab === 'single' }"
        type="button"
        role="tab"
        :aria-selected="state.currentTab === 'single'"
        @click="switchTab('single')"
      >
        单任务处理
      </button>
      <button
        class="tab-btn"
        :class="{ active: state.currentTab === 'batch' }"
        type="button"
        role="tab"
        :aria-selected="state.currentTab === 'batch'"
        @click="switchTab('batch')"
      >
        批量处理
      </button>
      <button
        class="tab-btn"
        :class="{ active: state.currentTab === 'download' }"
        type="button"
        role="tab"
        :aria-selected="state.currentTab === 'download'"
        @click="switchTab('download')"
      >
        影像下载
      </button>
      <button
        class="tab-btn"
        :class="{ active: state.currentTab === 'results' }"
        type="button"
        role="tab"
        :aria-selected="state.currentTab === 'results'"
        @click="switchTab('results')"
      >
        结果下载
      </button>
      <button
        class="tab-btn"
        :class="{ active: state.currentTab === 'indices' }"
        type="button"
        role="tab"
        :aria-selected="state.currentTab === 'indices'"
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
            <small>{{ singleInputSummaryText }}</small>
          </div>

          <div class="readiness-panel" :class="{ blocked: !!singleSubmitBlockReason }">
            <div class="readiness-head">
              <strong>{{ singleSubmitBlockReason ? '任务未就绪' : '任务已就绪' }}</strong>
              <span>{{ singleSubmitBlockReason || '可以提交单景预处理任务' }}</span>
            </div>
            <div class="readiness-grid">
              <div
                v-for="item in singleReadinessItems"
                :key="item.key"
                class="readiness-item"
                :data-status="item.status"
              >
                <strong>{{ item.label }}</strong>
                <span>{{ item.text }}</span>
              </div>
            </div>
          </div>

        <div class="form-grid-compact">
          <div class="field-compact full">
            <span>数据来源</span>
              <div class="mode-row-compact">
              <button class="btn-tiny" :class="{ active: state.inputSource === 'upload' }" type="button" @click="switchInputSource('upload')">
                本地上传
              </button>
              <button class="btn-tiny" :class="{ active: state.inputSource === 'server' }" type="button" @click="switchInputSource('server')">
                在线资源
              </button>
            </div>
          </div>

          <div class="field-compact full">
            <span>处理类型</span>
            <div class="mode-row-compact">
              <button class="btn-tiny" :class="{ active: state.sensor === 'landsat' }" type="button" @click="setProcessingSensor('landsat')">
                Landsat
              </button>
              <button class="btn-tiny" :class="{ active: state.sensor === 'sentinel-2' }" type="button" @click="setProcessingSensor('sentinel-2')">
                Sentinel-2 L2A
              </button>
            </div>
          </div>

          <template v-if="state.inputSource === 'upload'">
            <label class="field-compact full">
              <span>波段文件（必选）</span>
              <input type="file" multiple accept=".tif,.tiff,.img" @change="(e) => onPickFile(e, 'bands')" />
            </label>

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
              <select v-model="state.productLevel" :disabled="isSentinel2Mode">
                <option v-if="isSentinel2Mode" value="L2A">L2A: Sentinel-2 地表反射率</option>
                <option value="L1">L1: DN/辐射定标链</option>
                <option value="L2">L2: 地表反射率直用</option>
              </select>
            </label>

            <label v-if="!isSentinel2Mode" class="field-compact">
              <span>MTL 文件</span>
              <input type="file" accept=".txt,.mtl" @change="(e) => onPickFile(e, 'mtl')" />
            </label>

            <label v-if="!isSentinel2Mode" class="field-compact">
              <span>QA 文件</span>
              <input type="file" accept=".tif,.tiff,.img" @change="(e) => onPickFile(e, 'qa')" />
            </label>

            <label v-if="!isSentinel2Mode" class="field-compact">
              <span>QA_RADSAT</span>
              <input type="file" accept=".tif,.tiff,.img" @change="(e) => onPickFile(e, 'qa_radsat')" />
            </label>
          </template>

          <template v-else>
            <label class="field-compact full">
              <span>资源根目录</span>
              <div class="input-row">
                <input
                  v-model="state.serverResourceRoot"
                  type="text"
                  placeholder="服务端白名单目录"
                  @change="handleServerRootEdited"
                />
                <button class="btn-mini" type="button" aria-label="选择资源根目录" @click="openPathPicker('serverRoot')">...</button>
                <button
                  class="btn-mini pri"
                  type="button"
                  :disabled="state.serverScenesLoading || state.serverRootLoading"
                  @click="scanServerScenes()"
                >
                  {{ state.serverScenesLoading ? '扫描中...' : '扫描' }}
                </button>
              </div>
            </label>

            <div class="field-compact full">
              <span>在线场景（单选）</span>
              <p class="meta-compact server-root-meta" :class="{ placeholder: !state.serverResourceRoot }">
                {{ state.serverRootLoading ? '正在读取下载目录...' : (state.serverResourceRoot || '未选择资源根目录') }}
              </p>
              <p v-if="state.serverSceneError" class="err-line">{{ state.serverSceneError }}</p>
              <p v-else-if="state.serverScenesLoading" class="meta-line">扫描场景中...</p>
              <div v-else-if="state.serverScenes.length" class="server-scene-list">
                <button
                  v-for="scene in state.serverScenes"
                  :key="scene.path"
                  class="server-scene-card"
                  :class="{ active: state.selectedServerScenePath === scene.path }"
                  type="button"
                  @click="selectServerScene(scene)"
                >
                  <div class="server-scene-head">
                    <strong>{{ scene.name }}</strong>
                    <span class="server-scene-status">{{ state.selectedServerScenePath === scene.path ? '已选' : '选择' }}</span>
                  </div>
                  <p class="server-scene-path" :title="scene.path">{{ scene.path }}</p>
                  <div class="server-scene-meta">
                    <span class="scene-pill level">{{ scene.sensor === 'sentinel-2' ? 'Sentinel-2' : 'Landsat' }}</span>
                    <span class="scene-pill level">{{ getSceneAvailableLevels(scene).join('/') || normalizeProductLevel(scene.product_level) }}</span>
                    <span class="scene-pill" :class="scene.mtl_file ? 'ok' : 'muted'">{{ scene.mtl_file ? 'MTL' : '无 MTL' }}</span>
                    <span class="scene-pill" :class="scene.qa_band ? 'ok' : 'muted'">{{ scene.qa_band ? 'QA' : '无 QA' }}</span>
                    <span v-if="scene.sensor === 'sentinel-2'" class="scene-pill" :class="scene.scl_file ? 'ok' : 'muted'">{{ scene.scl_file ? 'SCL' : '无 SCL' }}</span>
                    <span class="scene-pill" :class="scene.footprint_bbox ? 'ok' : 'muted'">{{ scene.footprint_bbox ? 'Footprint' : '无范围' }}</span>
                  </div>
                </button>
              </div>
              <p v-else class="meta-line">当前目录未识别到可处理场景</p>
            </div>

            <label v-if="selectedServerScene" class="field-compact">
              <span>处理级别</span>
              <select
                v-model="state.productLevel"
                :disabled="serverSceneAvailableLevels.length <= 1"
                @change="loadServerSceneCoverage(selectedServerScene)"
              >
                <option
                  v-for="level in (serverSceneAvailableLevels.length ? serverSceneAvailableLevels : [activeProductLevel])"
                  :key="level"
                  :value="level"
                >
                  {{ level }}: {{ level === 'L2A' ? 'Sentinel-2 地表反射率' : (level === 'L2' ? '地表反射率直用' : 'DN/辐射定标链') }}
                </option>
              </select>
            </label>

            <label v-if="selectedServerScene" class="field-compact">
              <span>当前场景</span>
              <input :value="selectedServerScene.name || shortPath(selectedServerScene.path, 2)" type="text" readonly />
            </label>
          </template>

          <!-- 输出路径 -->
          <div class="field-compact full">
            <span>输出模式</span>
            <div class="mode-row-compact">
              <button class="btn-tiny" :class="{ active: state.outputMode === 'auto' }" type="button" @click="switchOutputMode('auto')">
                自动组合
              </button>
              <button class="btn-tiny" :class="{ active: state.outputMode === 'manual' }" type="button" @click="switchOutputMode('manual')">
                手动输入
              </button>
            </div>
          </div>

          <template v-if="state.outputMode === 'auto'">
            <label class="field-compact full">
              <span>基路径</span>
              <div class="input-row">
                <input v-model="state.outputBaseDir" type="text" @change="saveOutputPrefs" placeholder="E:\..." />
                <button class="btn-mini" type="button" aria-label="选择输出基路径" @click="openPathPicker('base')">...</button>
              </div>
            </label>
            <label class="field-compact full">
              <span>场景名</span>
              <div class="input-row">
                <input v-model="state.outputSceneName" type="text" @change="saveOutputPrefs" placeholder="LC08_..." />
                <button class="btn-mini" type="button" @click="useSceneHint" :disabled="!suggestedOutputSceneName">识别</button>
              </div>
            </label>
          </template>

          <label v-else class="field-compact full">
            <span>输出目录</span>
            <div class="input-row">
              <input v-model="state.outputDirManual" type="text" @change="saveOutputPrefs" placeholder="完整路径" />
              <button class="btn-mini" type="button" aria-label="选择输出目录" @click="openPathPicker('manual')">...</button>
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
            <button class="btn-mini" type="button" aria-label="添加输出路径书签" @click="addBookmark">+</button>
          </div>

          <!-- 高级选项（可折叠） -->
          <div class="field-compact full">
            <button class="toggle-section" type="button" :aria-expanded="state.showAdvancedOptions" @click="toggleAdvancedOptions">
              <span>高级选项：ROI、校正与掩膜</span>
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

            <label v-if="!isSentinel2Mode" class="field-compact">
              <span>大气校正</span>
              <select v-model="state.atmMethod" :disabled="activeProductLevel === 'L2'">
                <option value="DOS">DOS</option>
                <option value="6S">6S</option>
              </select>
            </label>

            <label v-if="!isSentinel2Mode" class="field-compact checkfield">
              <input v-model="state.applyCloudMask" type="checkbox" />
              <span>云掩膜</span>
            </label>
          </template>

          <!-- 合成类型 -->
          <div class="field-compact full">
            <span>合成类型（{{ state.selectedComposites.length }} 个）</span>
            <div class="chips-compact">
              <button
                v-for="item in compositeOptions.slice(0, 12)"
                :key="item.type"
                class="chip-compact"
                :class="{ active: state.selectedComposites.includes(item.type) }"
                type="button"
                @click="toggleComposite(item.type)"
              >
                {{ item.name }}
              </button>
              <button v-if="compositeOptions.length > 12" class="chip-compact more" type="button" @click="switchTab('indices')">
                +{{ compositeOptions.length - 12 }} 更多...
              </button>
            </div>
          </div>

          <!-- 自定义公式 -->
          <div class="field-compact full optional-section-label">
            <span>可选分析项</span>
          </div>

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
          <button class="btn pri" type="button" :disabled="!canSubmit" :title="singleSubmitBlockReason || '提交任务'" @click="submitTask">
            {{ state.submitting ? '提交中...' : '提交任务' }}
          </button>
          <button class="btn sub" type="button" @click="resetForm">重置</button>
        </div>
      </article>

      <article class="card monitor-card-compact">
        <div class="title-row-compact">
          <h2>任务监控</h2>
          <small>{{ statusLabel }}</small>
        </div>

        <div class="job-card-compact" :class="{ done: hasTerminalProgress }">
          <span>当前 Job ID</span>
          <strong>{{ currentJobId || '尚未创建' }}</strong>
          <button class="btn-mini" type="button" :disabled="!currentJobId" @click="copyToClipboard(currentJobId)">
            复制
          </button>
        </div>

        <div class="query-row-compact">
          <input v-model="state.manualJobId" type="text" placeholder="job_id" />
          <button class="btn-mini pri" type="button" @click="queryStatus()">查询</button>
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
          <div v-if="groupedResultItems.length" class="result-list-compact">
            <section v-for="group in groupedResultItems" :key="group.key" class="result-group">
              <h3>{{ group.label }}</h3>
              <div class="result-group-list">
                <article v-for="item in group.items" :key="`${item.group}-${item.label}-${item.path}`" class="result-item-compact">
                  <button class="result-main-action" type="button" @click="loadPreview(item.path)">
                    <strong>{{ item.label }}</strong>
                    <span>{{ shortPath(item.path, 3) }}</span>
                  </button>
                  <button class="result-copy-action" type="button" @click="copyToClipboard(item.path)">
                    复制
                  </button>
                </article>
              </div>
            </section>
          </div>
          <p v-else class="empty-compact">暂无产物</p>
        </div>
      </article>

      <article class="card preview-card-compact">
        <div class="title-row-compact">
          <h2>影像预览</h2>
          <small>{{ previewDisplayName }}</small>
        </div>

        <div class="preview-query-compact">
          <input v-model="state.previewPath" type="text" placeholder="路径" />
          <input v-model="state.previewSize" class="preview-size-input" type="number" min="128" max="2048" aria-label="预览尺寸" />
          <button class="btn-mini pri" type="button" @click="loadPreview()">加载</button>
        </div>

        <div class="binary-panel-compact">
          <div class="binary-head-compact">
            <strong>二值化与面积统计</strong>
            <button class="btn-mini pri" type="button" :disabled="!!binaryDisabledReason" :title="binaryDisabledReason || '生成二值化结果'" @click="runBinarization">
              {{ state.binaryRunning ? '处理中...' : '生成' }}
            </button>
          </div>
          <p v-if="binaryDisabledReason" class="binary-hint-compact">{{ binaryDisabledReason }}</p>
          <div class="binary-controls-compact" :class="{ range: binaryNeedsUpperThreshold() }">
            <select v-model="state.binaryComparison">
              <option value="gte">≥ 阈值</option>
              <option value="gt">&gt; 阈值</option>
              <option value="lte">≤ 阈值</option>
              <option value="lt">&lt; 阈值</option>
              <option value="between">区间内</option>
              <option value="outside">区间外</option>
            </select>
            <input v-model="state.binaryThreshold" type="number" step="0.0001" placeholder="阈值" />
            <input
              v-if="binaryNeedsUpperThreshold()"
              v-model="state.binaryUpperThreshold"
              type="number"
              step="0.0001"
              placeholder="上限"
            />
            <input v-model="state.binaryOutputPath" type="text" placeholder="输出路径（可选）" />
          </div>
          <div v-if="state.binaryResult" class="binary-stats-compact">
            <span><strong>目标像元</strong>{{ formatNumber(state.binaryResult.stats.target_pixels, 0) }}</span>
            <span><strong>占比</strong>{{ formatPercent(state.binaryResult.stats.target_ratio) }}</span>
            <span><strong>面积</strong>{{ formatNumber(state.binaryResult.stats.target_area_ha) }} ha</span>
            <span><strong>折合</strong>{{ formatNumber(state.binaryResult.stats.target_area_mu) }} 亩</span>
          </div>
        </div>

        <div class="preview-frame-compact">
          <img v-if="state.previewImage" :src="state.previewImage" :alt="`${previewDisplayName} 预览图`" />
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

    <section v-if="state.currentTab === 'results'" class="results-view">
      <TaskAssetCenter :api-base="normalizedApiBase()" @toast="handleBatchToast" />
    </section>

    <!-- Indices Encyclopedia View -->
    <section v-if="state.currentTab === 'indices'" class="indices-view">
      <IndicesInfo />
    </section>

    <p v-if="state.toast" :class="toastClass()" role="status" aria-live="polite">{{ state.toast }}</p>

    <div v-if="state.pathPickerOpen" class="picker-mask" @click.self="closePathPicker">
      <div class="picker-dialog card">
        <div class="picker-head">
          <h3>{{ pathPickerTitle }}</h3>
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

.binary-panel-compact {
  display: grid;
  gap: 10px;
  padding: 10px;
  border: 1px solid #d8e3df;
  border-radius: 8px;
  background: #f8fbfa;
}

.binary-head-compact {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.binary-head-compact strong {
  font-size: 13px;
  color: #1f312c;
}

.binary-controls-compact {
  display: grid;
  grid-template-columns: minmax(92px, 0.7fr) minmax(86px, 0.7fr) minmax(0, 1.6fr);
  gap: 8px;
}

.binary-controls-compact.range {
  grid-template-columns: minmax(92px, 0.7fr) minmax(86px, 0.6fr) minmax(86px, 0.6fr) minmax(0, 1.5fr);
}

.binary-controls-compact select,
.binary-controls-compact input {
  min-width: 0;
  height: 34px;
  border: 1px solid #d2dfdb;
  border-radius: 8px;
  padding: 0 9px;
  background: #fff;
  color: #20352f;
}

.binary-stats-compact {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.binary-stats-compact span {
  min-width: 0;
  padding: 8px 9px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e1e9e6;
  color: #243932;
  font-size: 12px;
  word-break: break-word;
}

.binary-stats-compact strong {
  display: block;
  margin-bottom: 3px;
  font-size: 10px;
  color: #657871;
}

.server-root-meta {
  margin: 0;
}

.server-root-meta.placeholder {
  color: var(--muted);
}

.server-scene-list {
  display: grid;
  gap: 8px;
  max-height: 220px;
  overflow-y: auto;
}

.server-scene-card {
  width: 100%;
  border: 1px solid #d5dfdc;
  border-radius: 10px;
  background: #fff;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
  display: grid;
  gap: 6px;
  transition: border-color 0.18s ease, background 0.18s ease;
}

.server-scene-card:hover {
  border-color: #9ac6ba;
  background: #f8fbfa;
}

.server-scene-card.active {
  border-color: var(--pri);
  background: #eef8f5;
}

.server-scene-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.server-scene-head strong {
  font-size: 12px;
  color: #1f312c;
}

.server-scene-status {
  font-size: 11px;
  color: var(--pri);
  font-weight: 700;
  white-space: nowrap;
}

.server-scene-path {
  margin: 0;
  font-size: 11px;
  color: #5d716a;
  font-family: var(--mono);
  word-break: break-all;
}

.server-scene-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.scene-pill {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid #d9e3e0;
  background: #f5f9f7;
  color: #5a6d67;
  font-size: 11px;
  font-weight: 600;
}

.scene-pill.level {
  background: #edf4f9;
  border-color: #d9e5ef;
  color: #395a70;
}

.scene-pill.ok {
  background: #e7f4f1;
  border-color: #cce4dc;
  color: #1d745b;
}

.scene-pill.muted {
  background: #f7faf9;
  border-color: #dde7e4;
  color: #7d8c87;
}

@media (max-width: 900px) {
  .clip-meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
