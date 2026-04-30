<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import XYZ from 'ol/source/XYZ'
import Draw, { createBox } from 'ol/interaction/Draw'
import GeoJSON from 'ol/format/GeoJSON'
import Feature from 'ol/Feature'
import { fromExtent as polygonFromExtent } from 'ol/geom/Polygon'
import { Fill, Stroke, Style } from 'ol/style'
import { fromLonLat, transformExtent } from 'ol/proj'

const DOWNLOAD_MAX_RETRIES = 3
const DOWNLOAD_RETRY_DELAYS = [2000, 5000, 10000]
const SERVER_ACTIVE_POLL_MS = 2000
const ACTIVE_DOWNLOAD_STATUSES = ['pending', 'downloading', 'retrying']
const TERMINAL_DOWNLOAD_STATUSES = ['completed', 'failed', 'cancelled']
const HISTORY_STATUS_FILTERS = [
  { value: 'all', label: '全部历史' },
  { value: 'failed', label: '仅失败' },
  { value: 'completed', label: '仅完成' },
  { value: 'cancelled', label: '仅取消' },
]
const RETRYABLE_DOWNLOAD_PATTERNS = [
  /peer closed connection/i,
  /incomplete message body/i,
  /failed to fetch/i,
  /load failed/i,
  /network/i,
  /connection/i,
  /socket/i,
  /body stream/i,
  /未发送回复/,
  /连接中断/,
  /服务器断线/,
]
const SENSOR_LABELS = {
  landsat: 'Landsat',
  'landsat-7': 'Landsat 7',
  'sentinel-2': 'Sentinel-2',
}
const PRODUCT_PRESETS = {
  landsat: {
    L1: {
      rgb: ['B4', 'B3', 'B2'],
      vegetation: ['B5', 'B4', 'B3'],
    },
    L2: {
      rgb: ['red', 'green', 'blue'],
      vegetation: ['nir08', 'red', 'green'],
    },
  },
  'landsat-7': {
    L1: {
      rgb: ['B3', 'B2', 'B1'],
      vegetation: ['B4', 'B3', 'B2'],
    },
    L2: {
      rgb: ['red', 'green', 'blue'],
      vegetation: ['nir08', 'red', 'green'],
    },
  },
  'sentinel-2': {
    L2A: {
      rgb: ['B04', 'B03', 'B02'],
      vegetation: ['B08', 'B04', 'B03'],
    },
  },
}

function createTaskPanelState() {
  return { keyword: '', historyStatus: 'all', historyOpen: false, expandedGroups: {} }
}

const props = defineProps({ apiBase: { type: String, required: true } })
const emit = defineEmits(['toast'])
const mapTarget = ref(null)
const aoiFileInput = ref(null)
const geoJsonFormat = new GeoJSON()

const state = reactive({
  collections: [],
  downloadRoot: '',
  defaultDownloadRoot: '',
  allowedDownloadRoots: [],
  authStatus: { configured: false, username: '' },
  proxyStatus: { enabled: false, configured: false, proxy_url: '', no_proxy: '' },
  sensor: 'landsat',
  product: 'L2',
  searchMode: 'spatial',
  sceneNameQuery: '',
  startDate: offsetDay(-90),
  endDate: offsetDay(0),
  maxCloudCover: 20,
  limit: 20,
  bbox: null,
  aoiLabel: '',
  aoiFeatureCount: 0,
  aoiSourceType: '',
  aoiParsing: false,
  searchLoading: false,
  searchResults: [],
  selectedScenes: {},
  hoveredSceneId: '',
  drawActive: false,
  downloadMode: 'server',
  modalOpen: false,
  modalScene: null,
  modalAssets: {},
  showAuthModal: false,
  showDownloadDirModal: false,
  showProxyModal: false,
  authForm: { username: '', password: '' },
  downloadDirSuffix: '',
  downloadDirNotice: '',
  authSaving: false,
  downloadDirSaving: false,
  proxyForm: { enabled: false, proxy_url: '', no_proxy: '' },
  proxySaving: false,
  serverTasks: [],
  serverSync: {
    polling: false,
    refreshing: false,
  },
  localTasks: {},
  localQueue: [],
  localBusy: false,
  taskPanels: {
    local: createTaskPanelState(),
    server: createTaskPanelState(),
  }
})

const aoiSource = new VectorSource()
const footprintSource = new VectorSource()
let map = null
let drawInteraction = null
let footprintLayer = null
let serverPollTimer = null
let serverPollInFlight = false
let serverTasksRequestPromise = null

const selectedScenes = computed(() => state.searchResults.filter((scene) => state.selectedScenes[scene.id]))
const selectedSceneCount = computed(() => selectedScenes.value.length)
const localTaskList = computed(() => Object.values(state.localTasks).sort((a, b) => b.createdAt - a.createdAt))
const localActiveCount = computed(() => localTaskList.value.filter((task) => ACTIVE_DOWNLOAD_STATUSES.includes(task.status)).length)
const serverActiveCount = computed(() => state.serverTasks.filter((task) => ACTIVE_DOWNLOAD_STATUSES.includes(task.status)).length)
const selectedModalAssetCount = computed(() => Object.values(state.modalAssets).filter(Boolean).length)
const sensorOptions = computed(() => {
  const seen = new Set()
  return state.collections
    .filter((collection) => {
      if (seen.has(collection.sensor)) return false
      seen.add(collection.sensor)
      return true
    })
    .map((collection) => ({ sensor: collection.sensor, title: collection.sensor_title || SENSOR_LABELS[collection.sensor] || collection.sensor }))
})
const productOptions = computed(() => state.collections.filter((collection) => collection.sensor === state.sensor))
const activeCollection = computed(() => productOptions.value.find((collection) => collection.product === state.product) || null)
const localPanel = computed(() => buildTaskPanelData(localTaskList.value, state.taskPanels.local))
const serverPanel = computed(() => buildTaskPanelData(state.serverTasks, state.taskPanels.server))
const isSceneNameSearch = computed(() => state.searchMode === 'scene_name')
const searchResultsEmptyText = computed(() => isSceneNameSearch.value ? '还没有检索结果。先输入官方 scene ID / entity ID，再点击“开始检索”。' : '还没有检索结果。先画框或上传矢量选区，再点击“开始检索”。')
function offsetDay(days) { const d = new Date(); d.setDate(d.getDate() + days); return d.toISOString().slice(0, 10) }
function apiBase() { return (props.apiBase || '').trim().replace(/\/+$/, '') || 'http://127.0.0.1:5001' }
function toast(message, type = 'idle') { emit('toast', { message, type }) }
function statusLabel(status) { return { pending: '等待中', downloading: '下载中', retrying: '重试中', completed: '已完成', failed: '失败', cancelled: '已取消' }[status] || status }
function statusClass(status) { return `status-${status || 'pending'}` }
function sceneDate(value) { return value ? String(value).slice(0, 10) : '未知日期' }
function cloudText(value) { return value === null || value === undefined ? '--' : `${Number(value).toFixed(1)}%` }
function bboxText() { return state.bbox ? state.bbox.map((value) => Number(value).toFixed(4)).join(', ') : '尚未绘制' }
function aoiStatusText() { return state.aoiLabel ? `${state.aoiLabel}${state.aoiFeatureCount ? ` · ${state.aoiFeatureCount} 要素` : ''}` : '当前未导入矢量选区' }
function pathRow(scene) { return `P${String(scene?.path ?? '--').padStart(3, '0')} / R${String(scene?.row ?? '--').padStart(3, '0')}` }
function sizeText(done, total = 0) { const f = (v) => !v ? '0 B' : v >= 1073741824 ? `${(v / 1073741824).toFixed(1)} GB` : v >= 1048576 ? `${(v / 1048576).toFixed(1)} MB` : v >= 1024 ? `${(v / 1024).toFixed(0)} KB` : `${v} B`; return total > 0 ? `${f(done)} / ${f(total)}` : f(done) }
function taskHasKnownTotal(task) { return Number(task?.size_total || 0) > 0 }
function taskProgressLabel(task) {
  if (!task) return '--'
  if (task.status === 'completed') return '100%'
  if (taskHasKnownTotal(task)) return `${Math.max(0, Math.min(100, Number(task.progress || 0)))}%`
  if (ACTIVE_DOWNLOAD_STATUSES.includes(task.status) && Number(task?.size_downloaded || 0) > 0) return '大小未知'
  return '0%'
}
function isIndeterminateProgress(task) {
  return ACTIVE_DOWNLOAD_STATUSES.includes(task?.status) && !taskHasKnownTotal(task) && Number(task?.size_downloaded || 0) > 0
}
function sensorLabel(sensor) {
  const matched = state.collections.find((collection) => collection.sensor === sensor)
  return matched?.sensor_title || SENSOR_LABELS[sensor] || sensor || '--'
}
function taskSensor(task) { return task?.sensor || 'landsat' }
function taskProduct(task) { return task?.product || task?.level || '--' }
function productBadgeClass(product) { return `level-${String(product || 'default').toLowerCase().replace(/[^a-z0-9]+/g, '') || 'default'}` }
function hasPathRow(scene) { return scene?.path !== null && scene?.path !== undefined && scene?.row !== null && scene?.row !== undefined }
function sceneMetaLine(scene) { return [sceneDate(scene?.datetime), sensorLabel(scene?.sensor)].filter(Boolean).join(' · ') }
function sceneDetailLine(scene) { return hasPathRow(scene) ? `${pathRow(scene)} · ${scene.collection}` : (scene.collection || '未提供 collection') }
function sceneThumbFallback(scene) { return scene?.sensor === 'sentinel-2' ? 'S2' : scene?.sensor === 'landsat-7' ? 'L7' : 'L8' }
function taskSummaryLine(task) { return `${sensorLabel(taskSensor(task))} / ${taskProduct(task)} / ${task.scene_id || '--'}` }
function taskTargetDir(task) {
  if (task?.target_dir) return task.target_dir
  const sceneId = task?.scene_id || 'unknown_scene'
  return [task?.download_date || '--', taskSensor(task), taskProduct(task), sceneId].join('/')
}
function sortedAssets(assets) { return Object.entries(assets || {}).sort((a, b) => a[0].localeCompare(b[0], 'en')) }
function filenameFrom(url, sceneId, band) { const name = (url || '').split('?')[0].split('/').pop(); return name || `${sceneId}_${band}.tif` }
function errorText(detail) { if (typeof detail === 'string') return detail; if (Array.isArray(detail)) return detail.map((item) => item.msg || JSON.stringify(item)).join(' | '); if (detail && typeof detail === 'object') return detail.msg || JSON.stringify(detail); return '请求失败' }
function normalizeErrorMessage(error) { return error?.message || String(error || '下载失败') }
function buildRetryFailureMessage() { return `连接中断，已重试 ${DOWNLOAD_MAX_RETRIES} 次仍失败` }
function retryText(task) { const retryCount = Number(task?.retry_count || 0); const maxRetries = Number(task?.max_retries ?? DOWNLOAD_MAX_RETRIES); if (!retryCount && task?.status !== 'retrying') return ''; return task?.status === 'retrying' ? `重试中 ${retryCount}/${maxRetries}` : `已重试 ${retryCount}/${maxRetries}` }
function detailErrorText(task) { if (!task?.last_error) return ''; return task.last_error === task.error ? '' : `详情：${task.last_error}` }
function sleep(ms) { return new Promise((resolve) => window.setTimeout(resolve, ms)) }
function createAbortError() { const error = new Error('The operation was aborted.'); error.name = 'AbortError'; return error }
function isAbortError(error) { return error?.name === 'AbortError' }
function isRetryableDownloadError(error) { if (!error || isAbortError(error)) return false; if (error instanceof TypeError) return true; const message = normalizeErrorMessage(error); return RETRYABLE_DOWNLOAD_PATTERNS.some((pattern) => pattern.test(message)) }
function resetLocalTaskProgress(task) { task.progress = 0; task.size_total = 0; task.size_downloaded = 0 }
function normalizeTaskKeyword(value) { return String(value || '').trim().toLowerCase() }
function normalizeHistoryStatus(value) {
  return HISTORY_STATUS_FILTERS.some((option) => option.value === value) ? value : 'all'
}
function taskMatchesKeyword(task, keyword) {
  if (!keyword) return true
  return [task.scene_id, task.filename, task.band, task.product, task.sensor].some((value) => normalizeTaskKeyword(value).includes(keyword))
}
function normalizePath(value) {
  return String(value || '').trim().replace(/[\\/]+/g, '/').replace(/\/+$/, '')
}
function normalizePathForCompare(value) {
  return normalizePath(value).toLowerCase()
}
function sanitizeDownloadDirSuffix(value) {
  return String(value || '').trim().replace(/^[\\/]+/, '').split(/[\\/]+/).filter(Boolean).join('/')
}
function joinDownloadDir(prefix, suffix) {
  const base = String(prefix || '').trim().replace(/[\\/]+$/, '')
  const cleanSuffix = sanitizeDownloadDirSuffix(suffix)
  if (!base) return cleanSuffix
  if (!cleanSuffix) return base
  const separator = base.includes('\\') ? '\\' : '/'
  return `${base}${separator}${cleanSuffix.split('/').join(separator)}`
}
function extractDownloadDirSuffix(currentDir, prefix) {
  const base = String(prefix || '').trim()
  const current = String(currentDir || '').trim()
  if (!base) return { suffix: '', notice: '' }
  const basePath = normalizePath(base)
  const currentPath = normalizePath(current || base)
  const baseKey = normalizePathForCompare(base)
  const currentKey = normalizePathForCompare(current || base)
  if (!currentKey || currentKey === baseKey) return { suffix: '', notice: '' }
  if (currentKey.startsWith(`${baseKey}/`)) {
    const suffix = currentPath.slice(basePath.length + 1)
    const separator = base.includes('\\') ? '\\' : '/'
    return { suffix: suffix.split('/').filter(Boolean).join(separator), notice: '' }
  }
  return { suffix: '', notice: '当前目录不在预设目录下，保存后会自动迁回固定目录体系。' }
}
function buildTaskPanelData(tasks, panelState) {
  const keyword = normalizeTaskKeyword(panelState.keyword)
  const historyStatus = normalizeHistoryStatus(panelState.historyStatus)
  const activeTasks = tasks.filter((task) => ACTIVE_DOWNLOAD_STATUSES.includes(task.status) && taskMatchesKeyword(task, keyword))
  const historyTasks = tasks.filter((task) => TERMINAL_DOWNLOAD_STATUSES.includes(task.status) && taskMatchesKeyword(task, keyword) && (historyStatus === 'all' || task.status === historyStatus))
  const activeGroups = buildSceneTaskGroups(activeTasks)
  const historyGroups = buildSceneTaskGroups(historyTasks)
  return {
    activeGroups,
    historyGroups,
    activeTaskCount: activeTasks.length,
    historyTaskCount: historyTasks.length,
    activeGroupCount: activeGroups.length,
    historyGroupCount: historyGroups.length,
  }
}
function buildSceneTaskGroups(tasks) {
  const groups = []
  const byScene = new Map()
  tasks.forEach((task) => {
    const sceneId = task.scene_id || '--'
    let group = byScene.get(sceneId)
    if (!group) {
      group = { sceneId, tasks: [], variants: [], variantLookup: {}, fileCount: 0, activeCount: 0, failedCount: 0 }
      byScene.set(sceneId, group)
      groups.push(group)
    }
    group.tasks.push(task)
    group.fileCount += 1
    const sensor = taskSensor(task)
    const product = taskProduct(task)
    const variantKey = `${sensor}:${product}`
    if (!group.variantLookup[variantKey]) {
      group.variantLookup[variantKey] = true
      group.variants.push({ sensor, product })
    }
    if (ACTIVE_DOWNLOAD_STATUSES.includes(task.status)) group.activeCount += 1
    if (task.status === 'failed') group.failedCount += 1
  })
  return groups.map((group) => ({
    sceneId: group.sceneId,
    tasks: group.tasks,
    variants: group.variants.sort((a, b) => `${a.sensor}:${a.product}`.localeCompare(`${b.sensor}:${b.product}`, 'en')),
    fileCount: group.fileCount,
    activeCount: group.activeCount,
    failedCount: group.failedCount,
  }))
}
function panelGroupKey(kind, sceneId) { return `${kind}:${sceneId}` }
function isGroupExpanded(panelKey, kind, sceneId) {
  const value = state.taskPanels[panelKey].expandedGroups[panelGroupKey(kind, sceneId)]
  return value === undefined ? kind === 'active' : value
}
function toggleGroup(panelKey, kind, sceneId) {
  const key = panelGroupKey(kind, sceneId)
  state.taskPanels[panelKey].expandedGroups[key] = !isGroupExpanded(panelKey, kind, sceneId)
}
function toggleHistory(panelKey) { state.taskPanels[panelKey].historyOpen = !state.taskPanels[panelKey].historyOpen }
function activeEmptyText(panelKey) { return normalizeTaskKeyword(state.taskPanels[panelKey].keyword) ? '没有匹配的进行中任务。' : '暂无进行中任务。' }
function historyEmptyText(panelKey) {
  const panelState = state.taskPanels[panelKey]
  return normalizeTaskKeyword(panelState.keyword) || normalizeHistoryStatus(panelState.historyStatus) !== 'all' ? '没有匹配的历史任务。' : '暂无历史任务。'
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(errorText(data.detail || data.message || `HTTP ${response.status}`))
  return data
}

function resetSearchState() {
  state.searchResults = []
  state.selectedScenes = {}
  state.hoveredSceneId = ''
  closeAssetModal()
  renderFootprints()
}

function syncCollectionSelection() {
  if (!state.collections.length) return
  const availableProducts = state.collections.filter((collection) => collection.sensor === state.sensor)
  if (!availableProducts.length) {
    state.sensor = state.collections[0].sensor
    state.product = state.collections[0].product
    return
  }
  if (!availableProducts.some((collection) => collection.product === state.product)) {
    state.product = availableProducts[0].product
  }
}

watch(() => state.hoveredSceneId, () => footprintLayer && footprintLayer.changed())
watch(() => state.selectedScenes, () => footprintLayer && footprintLayer.changed(), { deep: true })
watch(
  () => state.serverTasks.map((task) => `${task.id}:${task.status}`).join('|'),
  () => {
    updateFailedServerRetryBar()
  },
)

watch(() => props.apiBase, async () => {
  stopServerPoll()
  await Promise.all([loadCollections(true), loadAuthStatus(true), loadProxyStatus(true), loadServerTasks(true)])
})
watch(() => state.sensor, (next, prev) => {
  syncCollectionSelection()
  if (prev !== undefined && next !== prev) resetSearchState()
})
watch(() => state.product, (next, prev) => {
  if (prev !== undefined && next !== prev) resetSearchState()
})
watch(() => state.searchMode, async (next, prev) => {
  if (prev !== undefined && next !== prev) {
    resetSearchState()
    if (next !== 'scene_name') {
      await nextTick()
      map && map.updateSize()
    }
  }
})

function initMap() {
  footprintLayer = new VectorLayer({
    source: footprintSource,
    style: (feature) => new Style({
      stroke: new Stroke({ color: state.hoveredSceneId === feature.get('sceneId') || state.selectedScenes[feature.get('sceneId')] ? '#0f7c66' : '#9ac6ba', width: state.hoveredSceneId === feature.get('sceneId') || state.selectedScenes[feature.get('sceneId')] ? 2.4 : 1.4 }),
      fill: new Fill({ color: state.hoveredSceneId === feature.get('sceneId') || state.selectedScenes[feature.get('sceneId')] ? 'rgba(15,124,102,0.18)' : 'rgba(154,198,186,0.1)' })
    })
  })
  map = new Map({
    target: mapTarget.value,
    layers: [
      new TileLayer({ source: new XYZ({ url: 'https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}.png', maxZoom: 19, attributions: 'Tiles © Esri — Source: Esri, USGS, NOAA' }) }),
      footprintLayer,
      new VectorLayer({ source: aoiSource, style: new Style({ stroke: new Stroke({ color: '#0f7c66', width: 2 }), fill: new Fill({ color: 'rgba(15,124,102,0.12)' }) }) })
    ],
    view: new View({ center: fromLonLat([105, 35]), zoom: 4 })
  })
}

function removeDraw() { if (map && drawInteraction) map.removeInteraction(drawInteraction); drawInteraction = null; state.drawActive = false }
function fitAoiSource() {
  if (!map || aoiSource.isEmpty()) return
  map.getView().fit(aoiSource.getExtent(), { padding: [48, 48, 48, 48], duration: 250, maxZoom: 11 })
}
function applyAoiGeoJson(geojson, bbox, options = {}) {
  aoiSource.clear()
  const features = geoJsonFormat.readFeatures(geojson, { dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857' })
  if (features.length) aoiSource.addFeatures(features)
  state.bbox = Array.isArray(bbox) && bbox.length === 4 ? bbox.map((value) => Number(value)) : null
  state.aoiLabel = options.label || ''
  state.aoiFeatureCount = Number(options.featureCount || features.length || 0)
  state.aoiSourceType = options.sourceType || ''
  removeDraw()
  fitAoiSource()
}
// 用 OpenLayers 的 box geometryFunction 生成矩形 AOI，直接得到后端需要的 bbox。
function drawBox() { if (!map) return; removeDraw(); drawInteraction = new Draw({ source: aoiSource, type: 'Circle', geometryFunction: createBox() }); drawInteraction.on('drawstart', () => aoiSource.clear()); drawInteraction.on('drawend', (event) => { state.bbox = transformExtent(event.feature.getGeometry().getExtent(), 'EPSG:3857', 'EPSG:4326').map((value) => Number(value.toFixed(4))); state.aoiLabel = '矩形框选'; state.aoiFeatureCount = 1; state.aoiSourceType = 'bbox'; removeDraw(); toast('检索范围已更新', 'ok') }); map.addInteraction(drawInteraction); state.drawActive = true }
function clearBox() { aoiSource.clear(); state.bbox = null; state.aoiLabel = ''; state.aoiFeatureCount = 0; state.aoiSourceType = ''; removeDraw(); if (aoiFileInput.value) aoiFileInput.value.value = '' }
function locateScene(scene) { if (!map || !scene?.bbox) return; map.getView().fit(transformExtent(scene.bbox, 'EPSG:4326', 'EPSG:3857'), { padding: [48, 48, 48, 48], duration: 250, maxZoom: 10 }) }
function renderFootprints() { footprintSource.clear(); state.searchResults.forEach((scene) => { if (!scene.bbox || scene.bbox.length !== 4) return; const feature = new Feature(polygonFromExtent(transformExtent(scene.bbox, 'EPSG:4326', 'EPSG:3857'))); feature.set('sceneId', scene.id); footprintSource.addFeature(feature) }); footprintLayer && footprintLayer.changed() }
function triggerAoiUpload() { aoiFileInput.value?.click() }
async function handleAoiUpload(event) {
  const files = Array.from(event?.target?.files || [])
  if (!files.length) return

  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  state.aoiParsing = true
  try {
    const data = await request('/imagery/aoi/parse', { method: 'POST', body: formData })
    applyAoiGeoJson(data.geojson, data.bbox, { label: data.label, featureCount: data.feature_count, sourceType: data.source_type })
    toast(`已加载选区：${data.label || 'AOI'}，共 ${data.feature_count || 0} 个要素`, 'ok')
  } catch (error) {
    toast(`解析矢量选区失败：${error.message}`, 'error')
  } finally {
    state.aoiParsing = false
    if (event?.target) event.target.value = ''
  }
}

async function loadCollections(silent = false) {
  try {
    const data = await request('/imagery/collections')
    state.collections = data.collections || []
    state.downloadRoot = data.download_dir || ''
    state.defaultDownloadRoot = data.default_download_dir || data.download_dir || ''
    state.allowedDownloadRoots = data.allowed_download_roots || []
    syncCollectionSelection()
  } catch (error) {
    if (!silent) toast(`加载配置失败：${error.message}`, 'error')
  }
}
async function loadAuthStatus(silent = false) { try { state.authStatus = await request('/imagery/auth/status') } catch (error) { if (!silent) toast(`读取账号状态失败：${error.message}`, 'error') } }
async function loadProxyStatus(silent = false) { try { state.proxyStatus = await request('/imagery/proxy/status') } catch (error) { if (!silent) toast(`读取代理配置失败：${error.message}`, 'error') } }
function hasActiveServerTasks(tasks = state.serverTasks) {
  return tasks.some((task) => ACTIVE_DOWNLOAD_STATUSES.includes(task.status))
}
function scheduleServerPoll(delay = SERVER_ACTIVE_POLL_MS) {
  if (!state.serverSync.polling) return
  if (serverPollTimer !== null) window.clearTimeout(serverPollTimer)
  serverPollTimer = window.setTimeout(() => { void pollServerTasks() }, delay)
}
function stopServerPoll() {
  state.serverSync.polling = false
  if (serverPollTimer !== null) {
    window.clearTimeout(serverPollTimer)
    serverPollTimer = null
  }
}
function syncServerPollingState() {
  if (!hasActiveServerTasks()) {
    stopServerPoll()
    return
  }
  state.serverSync.polling = true
  scheduleServerPoll()
}
async function loadServerTasks(silent = false) {
  if (serverTasksRequestPromise) return serverTasksRequestPromise
  serverTasksRequestPromise = (async () => {
    state.serverSync.refreshing = true
    try {
      const data = await request('/imagery/download_tasks')
      state.serverTasks = (data.tasks || []).sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
    } catch (error) {
      if (!silent) toast(`读取服务端任务失败：${normalizeErrorMessage(error)}`, 'error')
    } finally {
      state.serverSync.refreshing = false
      syncServerPollingState()
      serverTasksRequestPromise = null
    }
  })()
  return serverTasksRequestPromise
}
async function pollServerTasks() {
  if (serverPollInFlight) return
  serverPollInFlight = true
  try {
    await loadServerTasks(true)
  } finally {
    serverPollInFlight = false
  }
}
function handleVisibilityChange() {
  if (document.visibilityState === 'visible' && !state.serverSync.refreshing) void loadServerTasks(true)
}

async function searchScenes() {
  if (state.searchMode === 'scene_name') {
    if (!state.sceneNameQuery.trim()) return toast('请先填写官方 scene ID / entity ID', 'warn')
  } else {
    if (!state.bbox) return toast('请先绘制矩形或上传 GeoJSON / Shapefile 选区', 'warn')
    if (!state.startDate || !state.endDate) return toast('请填写完整日期范围', 'warn')
    if (state.startDate > state.endDate) return toast('开始日期不能晚于结束日期', 'warn')
  }
  state.searchLoading = true
  try {
    const payload = {
      sensor: state.sensor,
      product: state.product,
      search_mode: state.searchMode,
      scene_name_query: state.searchMode === 'scene_name' ? state.sceneNameQuery.trim() : '',
      bbox: state.searchMode === 'scene_name' ? null : state.bbox,
      start_date: state.searchMode === 'scene_name' ? null : state.startDate,
      end_date: state.searchMode === 'scene_name' ? null : state.endDate,
      max_cloud_cover: Number(state.maxCloudCover),
      limit: Number(state.limit),
    }
    const data = await request('/imagery/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    state.searchResults = data.items || []
    state.selectedScenes = {}
    state.hoveredSceneId = ''
    renderFootprints()
    toast(`找到 ${data.count || 0} 景数据`, 'ok')
  } catch (error) { toast(`检索失败：${error.message}`, 'error') } finally { state.searchLoading = false }
}

function setScene(sceneId, checked) { state.selectedScenes[sceneId] = checked }
function toggleAll(checked) { const next = {}; state.searchResults.forEach((scene) => { next[scene.id] = checked }); state.selectedScenes = next }
function openAssetModal(scene) { const next = {}; Object.keys(scene.assets || {}).forEach((key) => { next[key] = true }); state.modalScene = scene; state.modalAssets = next; state.modalOpen = true }
function closeAssetModal() { state.modalOpen = false; state.modalScene = null; state.modalAssets = {} }
function choosePreset(preset) { const scene = state.modalScene; if (!scene) return; const keep = preset === 'all' ? null : new Set(PRODUCT_PRESETS[scene.sensor]?.[scene.product]?.[preset] || []); Object.keys(scene.assets || {}).forEach((key) => { state.modalAssets[key] = keep ? keep.has(key) : true }) }
function buildItems(scene, assetKeys = null) { const assets = scene.assets || {}; return (assetKeys || Object.keys(assets)).filter((key) => assets[key]).map((key) => ({ sensor: scene.sensor, product: scene.product, collection: scene.collection, auth_required: scene.auth_required, scene_id: scene.id, band: key, filename: filenameFrom(assets[key].href, scene.id, key), url: assets[key].href })) }
async function confirmAssetDownload() { if (!state.modalScene) return; const assetKeys = Object.entries(state.modalAssets).filter(([, checked]) => checked).map(([key]) => key); if (!assetKeys.length) return toast('请至少选择一个资产', 'warn'); const items = buildItems(state.modalScene, assetKeys); closeAssetModal(); await enqueue(items) }
async function downloadScene(scene) { await enqueue(buildItems(scene)) }
async function downloadSelected() { if (!selectedScenes.value.length) return toast('请先勾选至少一景', 'warn'); await enqueue(selectedScenes.value.flatMap((scene) => buildItems(scene))) }

async function enqueue(items) {
  if (!items.length) return toast('没有可加入的下载项', 'warn')
  if (state.downloadMode === 'server') {
    try { const data = await request('/imagery/download', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items, mode: 'server' }) }); toast(`已创建 ${data.count || items.length} 个服务端任务`, 'ok'); await loadServerTasks(true) } catch (error) { toast(`创建服务端任务失败：${error.message}`, 'error') }
    return
  }
  items.forEach((item) => { const id = `${Date.now()}_${Math.random().toString(16).slice(2, 8)}`; state.localTasks[id] = { ...item, id, status: 'pending', progress: 0, size_total: 0, size_downloaded: 0, error: '', last_error: '', retry_count: 0, max_retries: DOWNLOAD_MAX_RETRIES, createdAt: Date.now(), controller: null }; state.localQueue.push(id) })
  toast(`已加入 ${items.length} 个浏览器下载任务`, 'ok')
  processLocalQueue()
}

function saveBlob(blob, filename) { const href = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = href; link.download = filename; document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(href), 5000) }
async function waitForLocalRetry(task, delayMs) { const deadline = Date.now() + delayMs; while (Date.now() < deadline) { if (!task || task.status === 'cancelled') return false; await sleep(Math.min(250, deadline - Date.now())) } return task.status !== 'cancelled' }
async function fetchLocalTaskBlob(task, signal) { const response = await fetch(`${apiBase()}/imagery/proxy_download?url=${encodeURIComponent(task.url)}&filename=${encodeURIComponent(task.filename)}`, { signal }); if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(errorText(data.detail || `HTTP ${response.status}`)) } const total = Number(response.headers.get('content-length') || 0); task.size_total = total; if (response.body && response.body.getReader) { const reader = response.body.getReader(); const chunks = []; let downloaded = 0; try { while (true) { const { done, value } = await reader.read(); if (done) break; if (task.status === 'cancelled') { await reader.cancel().catch(() => {}); throw createAbortError() } chunks.push(value); downloaded += value.byteLength || value.length || 0; task.size_downloaded = downloaded; task.progress = total ? Math.round(downloaded / total * 100) : 0 } } catch (error) { await reader.cancel().catch(() => {}); throw error } const blob = new Blob(chunks); task.size_downloaded = blob.size; task.size_total = total || blob.size; return blob } const blob = await response.blob(); task.size_downloaded = blob.size; task.size_total = total || blob.size; return blob }
async function downloadLocalTask(task) { if (!task || task.status === 'cancelled') return; for (let attemptIndex = 0; attemptIndex <= DOWNLOAD_MAX_RETRIES; attemptIndex += 1) { if (!task || task.status === 'cancelled') { task.status = 'cancelled'; return } resetLocalTaskProgress(task); task.status = 'downloading'; task.error = ''; task.last_error = ''; const controller = new AbortController(); task.controller = controller; try { const blob = await fetchLocalTaskBlob(task, controller.signal); if (task.status === 'cancelled') return; task.progress = 100; task.status = 'completed'; task.error = ''; task.last_error = ''; saveBlob(blob, task.filename); return } catch (error) { if (task.status === 'cancelled' || isAbortError(error)) { task.status = 'cancelled'; return } const rawError = normalizeErrorMessage(error); const retryable = isRetryableDownloadError(error); task.last_error = rawError; if (!retryable || attemptIndex >= DOWNLOAD_MAX_RETRIES) { task.status = 'failed'; if (retryable) resetLocalTaskProgress(task); task.error = retryable ? buildRetryFailureMessage() : rawError; return } task.retry_count = attemptIndex + 1; task.status = 'retrying'; task.error = ''; resetLocalTaskProgress(task); const shouldContinue = await waitForLocalRetry(task, DOWNLOAD_RETRY_DELAYS[attemptIndex]); if (!shouldContinue) { task.status = 'cancelled'; return } } finally { task.controller = null } } }
// 浏览器模式顺序下载，避免多景并发时把内存和网络同时拉满。
async function processLocalQueue() { if (state.localBusy || !state.localQueue.length) return; state.localBusy = true; try { while (state.localQueue.length) { const taskId = state.localQueue.shift(); const task = state.localTasks[taskId]; if (!task || task.status === 'cancelled') continue; await downloadLocalTask(task) } } finally { state.localBusy = false; if (state.localQueue.length) window.setTimeout(() => processLocalQueue(), 0) } }
function cancelLocal(taskId) { const task = state.localTasks[taskId]; if (!task) return; task.status = 'cancelled'; task.controller?.abort(); state.localQueue = state.localQueue.filter((item) => item !== taskId) }
let failedServerRetryBar = null

function removeFailedServerRetryBar() {
  if (!failedServerRetryBar) return
  failedServerRetryBar.remove()
  failedServerRetryBar = null
}

function updateFailedServerRetryBar() {
  if (typeof document === 'undefined') return
  const failedCount = state.serverTasks.filter((task) => task.status === 'failed').length
  if (!failedCount) {
    removeFailedServerRetryBar()
    return
  }

  if (!failedServerRetryBar) {
    const container = document.createElement('div')
    container.style.position = 'fixed'
    container.style.right = '20px'
    container.style.bottom = '20px'
    container.style.zIndex = '50'
    container.style.display = 'flex'
    container.style.alignItems = 'center'
    container.style.gap = '12px'
    container.style.padding = '12px 14px'
    container.style.borderRadius = '12px'
    container.style.background = 'rgba(16, 24, 40, 0.94)'
    container.style.color = '#f8fafc'
    container.style.boxShadow = '0 18px 40px rgba(15, 23, 42, 0.28)'

    const label = document.createElement('span')
    label.dataset.role = 'label'
    label.style.fontSize = '13px'
    label.style.fontWeight = '600'
    container.appendChild(label)

    const button = document.createElement('button')
    button.type = 'button'
    button.textContent = '重新下载'
    button.style.border = '0'
    button.style.borderRadius = '10px'
    button.style.padding = '8px 12px'
    button.style.cursor = 'pointer'
    button.style.background = '#f97316'
    button.style.color = '#fff7ed'
    button.style.fontSize = '12px'
    button.style.fontWeight = '700'
    button.addEventListener('click', () => {
      void retryFailedServerTasks()
    })
    container.appendChild(button)

    document.body.appendChild(container)
    failedServerRetryBar = container
  }

  const label = failedServerRetryBar.querySelector('[data-role="label"]')
  if (label) {
    label.textContent = `${failedCount} 个服务端失败任务`
  }
}

async function retryFailedServerTasks() {
  const failedTasks = state.serverTasks.filter((task) => task.status === 'failed')
  if (!failedTasks.length) return

  const button = failedServerRetryBar?.querySelector('button')
  if (button) button.disabled = true

  try {
    for (const task of failedTasks) {
      await request(`/imagery/download_tasks/${encodeURIComponent(task.id)}/retry`, {
        method: 'POST',
      })
    }
    await loadServerTasks(true)
    scheduleServerPoll()
  } finally {
    if (button) button.disabled = false
    updateFailedServerRetryBar()
  }
}

function retryLocal(taskId) {
  const task = state.localTasks[taskId]
  if (!task || task.status !== 'failed') return
  task.status = 'pending'
  task.error = ''
  task.last_error = ''
  task.retry_count = 0
  task.createdAt = Date.now()
  resetLocalTaskProgress(task)
  if (!state.localQueue.includes(taskId)) state.localQueue.push(taskId)
  toast(`已重新加入浏览器下载：${task.filename}`, 'ok')
  processLocalQueue()
}
async function cancelServer(taskId) { try { await request(`/imagery/download_tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' }); await loadServerTasks(true) } catch (error) { toast(`取消失败：${error.message}`, 'error') } }
async function retryServer(taskId) { try { await request(`/imagery/download_tasks/${encodeURIComponent(taskId)}/retry`, { method: 'POST' }); await loadServerTasks(true); toast('服务端失败任务已重新加入下载', 'ok') } catch (error) { toast(`重新下载失败：${error.message}`, 'error') } }
function saveServer(task) { const link = document.createElement('a'); link.href = `${apiBase()}/imagery/download_tasks/${encodeURIComponent(task.id)}/file`; link.target = '_blank'; link.rel = 'noopener'; document.body.appendChild(link); link.click(); link.remove() }
async function clearServer() { try { await request('/imagery/download_tasks/completed', { method: 'DELETE' }); await loadServerTasks(true) } catch (error) { toast(`清理失败：${error.message}`, 'error') } }
function clearLocal() { Object.entries(state.localTasks).forEach(([id, task]) => { if (['completed', 'failed', 'cancelled'].includes(task.status)) delete state.localTasks[id] }) }

function openAuth() { state.authForm.username = state.authStatus.username || ''; state.authForm.password = ''; state.showAuthModal = true }
function closeAuth() { state.showAuthModal = false; state.authForm.password = '' }
async function saveAuth() { const username = state.authForm.username.trim(); const password = state.authForm.password; if (!username || !password) return toast('请填写完整账号和密码', 'warn'); state.authSaving = true; try { await request('/imagery/auth/earthdata', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) }); await loadAuthStatus(true); closeAuth(); toast('EarthData / EROS 账号已更新', 'ok') } catch (error) { toast(`账号验证失败：${error.message}`, 'error') } finally { state.authSaving = false } }
function openDownloadDir() {
  const fixedPrefix = String(state.defaultDownloadRoot || state.downloadRoot || '').trim()
  const { suffix, notice } = extractDownloadDirSuffix(state.downloadRoot || fixedPrefix, fixedPrefix)
  state.downloadDirSuffix = suffix
  state.downloadDirNotice = notice
  state.showDownloadDirModal = true
}
function closeDownloadDir() { state.showDownloadDirModal = false; state.downloadDirNotice = '' }
async function saveDownloadDir(useDefault = false) {
  const fixedPrefix = String(state.defaultDownloadRoot || '').trim()
  const cleanSuffix = sanitizeDownloadDirSuffix(state.downloadDirSuffix)
  if (!useDefault && cleanSuffix && !fixedPrefix) return toast('默认下载目录未加载，无法保存子目录', 'warn')
  const payload = { download_dir: useDefault || !cleanSuffix ? '' : joinDownloadDir(fixedPrefix, cleanSuffix) }
  if (!useDefault) state.downloadDirSuffix = cleanSuffix
  state.downloadDirSaving = true
  try {
    const data = await request('/imagery/download_dir', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    state.downloadRoot = data.download_dir || ''
    state.defaultDownloadRoot = data.default_download_dir || state.defaultDownloadRoot
    state.allowedDownloadRoots = data.allowed_download_roots || state.allowedDownloadRoots
    closeDownloadDir()
    toast(useDefault ? '服务端下载目录已恢复默认' : '服务端下载目录已更新', 'ok')
  } catch (error) {
    toast(`保存下载目录失败：${error.message}`, 'error')
  } finally {
    state.downloadDirSaving = false
  }
}
function openProxy() { state.proxyForm = { enabled: !!state.proxyStatus.enabled, proxy_url: state.proxyStatus.proxy_url || '', no_proxy: state.proxyStatus.no_proxy || '' }; state.showProxyModal = true }
function closeProxy() { state.showProxyModal = false }
async function saveProxy() { const payload = { enabled: !!state.proxyForm.enabled, proxy_url: state.proxyForm.proxy_url.trim(), no_proxy: state.proxyForm.no_proxy.trim() }; if (payload.enabled && !payload.proxy_url) return toast('启用代理时请填写代理地址', 'warn'); state.proxySaving = true; try { await request('/imagery/proxy', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); await loadProxyStatus(true); closeProxy(); toast(payload.enabled ? '下载代理已更新' : '下载代理已关闭', 'ok') } catch (error) { toast(`保存代理失败：${error.message}`, 'error') } finally { state.proxySaving = false } }
async function disableProxy() { state.proxyForm.enabled = false; state.proxyForm.proxy_url = ''; state.proxyForm.no_proxy = ''; await saveProxy() }

onMounted(async () => {
  updateFailedServerRetryBar()
  await nextTick()
  initMap()
  document.addEventListener('visibilitychange', handleVisibilityChange)
  window.setTimeout(() => map && map.updateSize(), 320)
  await Promise.all([loadCollections(true), loadAuthStatus(true), loadProxyStatus(true), loadServerTasks(true)])
})
onBeforeUnmount(() => {
  removeFailedServerRetryBar()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  stopServerPoll()
  removeDraw()
  Object.values(state.localTasks).forEach((task) => { task.status = 'cancelled'; task.controller?.abort() })
  if (map) map.setTarget(null)
})
</script>

<template>
  <div class="landsat-download">
    <section class="grid">
      <article class="card">
        <div class="head"><div><h3>检索条件</h3></div><div class="row"><button class="btn sub" type="button" @click="openDownloadDir">下载目录</button><button class="btn sub" type="button" @click="openProxy">{{ state.proxyStatus.enabled ? '代理已启用' : '配置代理' }}</button><button class="btn sub" type="button" @click="openAuth">{{ state.authStatus.configured ? `账号：${state.authStatus.username}` : '配置 EarthData' }}</button></div></div>
        <div class="sensor-switch"><button v-for="sensor in sensorOptions" :key="sensor.sensor" class="pill sensor-pill" :class="{ active: state.sensor === sensor.sensor }" type="button" @click="state.sensor = sensor.sensor">{{ sensor.title }}</button></div>
        <div class="collections"><button v-for="collection in productOptions" :key="`${collection.sensor}:${collection.product}`" class="collection-chip" :class="{ active: state.product === collection.product }" type="button" @click="state.product = collection.product"><strong>{{ collection.product }}</strong><span>{{ collection.title }}</span></button></div>
        <div class="fields">
          <div class="full"><span>检索模式</span><div class="mode-switch"><button class="pill" :class="{ active: state.searchMode === 'spatial' }" type="button" @click="state.searchMode = 'spatial'">按范围</button><button class="pill" :class="{ active: state.searchMode === 'scene_name' }" type="button" @click="state.searchMode = 'scene_name'">按影像名</button></div></div>
          <template v-if="state.searchMode === 'scene_name'">
            <label class="full"><span>影像名 / Scene ID</span><input v-model.trim="state.sceneNameQuery" type="text" placeholder="例如 LE07_L2SP_123032_20200415_20200509_02_T1 或 LE71230322020106EDC00" /></label>
            <label><span>返回上限</span><input v-model.number="state.limit" type="number" min="1" max="100" /></label>
            <div><span>下载模式</span><div class="mode-switch"><button class="pill" :class="{ active: state.downloadMode === 'server' }" type="button" @click="state.downloadMode = 'server'">服务端</button><button class="pill" :class="{ active: state.downloadMode === 'local' }" type="button" @click="state.downloadMode = 'local'">浏览器</button></div></div>
          </template>
          <template v-else>
            <label><span>开始日期</span><input v-model="state.startDate" type="date" /></label>
            <label><span>结束日期</span><input v-model="state.endDate" type="date" /></label>
            <label class="full"><span>最大云量 {{ state.maxCloudCover }}%</span><input v-model.number="state.maxCloudCover" type="range" min="0" max="100" step="1" /></label>
            <label><span>返回上限</span><input v-model.number="state.limit" type="number" min="1" max="100" /></label>
            <div><span>下载模式</span><div class="mode-switch"><button class="pill" :class="{ active: state.downloadMode === 'server' }" type="button" @click="state.downloadMode = 'server'">服务端</button><button class="pill" :class="{ active: state.downloadMode === 'local' }" type="button" @click="state.downloadMode = 'local'">浏览器</button></div></div>
          </template>
        </div>
        <p v-if="activeCollection" class="root-hint">当前产品：{{ sensorLabel(state.sensor) }} / {{ state.product }}</p>
        <p v-if="activeCollection?.auth_required" class="root-hint">需要 EarthData / EROS 认证</p>
        <p v-if="state.searchMode === 'scene_name'" class="root-hint">影像名模式支持官方 scene ID / entity ID 的精确匹配和前缀匹配，不再要求 AOI、日期和云量条件。</p>
        <template v-else>
          <div class="bbox-box"><div><span>当前范围</span><strong>{{ bboxText() }}</strong><p class="aoi-hint">{{ aoiStatusText() }}</p></div><div class="row"><button class="btn" type="button" @click="drawBox">{{ state.drawActive ? '重新框选中...' : '绘制矩形' }}</button><button class="btn sub" type="button" :disabled="state.aoiParsing" @click="triggerAoiUpload">{{ state.aoiParsing ? '解析中...' : '上传矢量' }}</button><button class="btn sub" type="button" @click="clearBox">清空</button></div></div>
          <input ref="aoiFileInput" class="hidden-file-input" type="file" multiple accept=".geojson,.json,.shp,.dbf,.shx,.prj,.cpg,.sbn,.sbx" @change="handleAoiUpload" />
          <p class="root-hint">支持 GeoJSON / Shapefile，Shapefile 建议同时选择 `.dbf`、`.shx`、`.prj`。</p>
        </template>
        <button class="btn main" type="button" :disabled="state.searchLoading" @click="searchScenes">{{ state.searchLoading ? '检索中...' : '开始检索' }}</button>
      </article>
      <article v-show="state.searchMode !== 'scene_name'" class="card"><div class="head"><div><h3>地图范围</h3><p>{{ state.searchResults.length }} 景，{{ selectedSceneCount }} 已选</p></div></div><div ref="mapTarget" class="map"></div></article>
      <article class="card span-all">
        <div class="head"><div><h3>检索结果</h3></div><div class="row"><button class="btn sub" type="button" @click="toggleAll(true)">全选</button><button class="btn sub" type="button" @click="toggleAll(false)">清空</button><button class="btn" type="button" @click="downloadSelected">下载所选景全部资产</button></div></div>
        <div v-if="!state.searchResults.length" class="empty">{{ searchResultsEmptyText }}</div>
        <div v-else class="scene-grid">
          <article v-for="scene in state.searchResults" :key="`${scene.sensor}:${scene.id}`" class="scene-card" :class="{ selected: state.selectedScenes[scene.id] }" @mouseenter="state.hoveredSceneId = scene.id" @mouseleave="state.hoveredSceneId = ''">
            <div class="scene-top"><div class="thumb"><img v-if="scene.thumbnail" :src="scene.thumbnail" :alt="scene.id" loading="lazy" /><span v-else>{{ sceneThumbFallback(scene) }}</span></div><div class="scene-text"><div class="between"><h4>{{ scene.id }}</h4><span class="badge" :class="productBadgeClass(scene.product)">{{ scene.product }}</span></div><p>{{ sceneMetaLine(scene) }}</p><p>{{ sceneDetailLine(scene) }}</p><p>云量 {{ cloudText(scene.cloud_cover) }} · {{ Object.keys(scene.assets || {}).length }} 个资产</p></div><label class="checker"><input :checked="!!state.selectedScenes[scene.id]" type="checkbox" @change="setScene(scene.id, $event.target.checked)" /><span>{{ state.selectedScenes[scene.id] ? '已选' : '选择' }}</span></label></div>
            <div class="row"><button class="btn sub" type="button" @click="locateScene(scene)">定位</button><button class="btn sub" type="button" @click="openAssetModal(scene)">选资产</button><button class="btn" type="button" @click="downloadScene(scene)">全部资产</button></div>
          </article>
        </div>
      </article>
      <article class="card span-all">
        <div class="task-columns">
          <section class="task-column">
            <div class="task-column-top">
              <div class="head task-head">
                <div class="task-head-copy">
                  <h3>浏览器下载</h3>
                  <p>{{ localActiveCount }} 个应用内传输中 · {{ localTaskList.length }} 个总任务</p>
                </div>
                <button class="btn sub" type="button" @click="clearLocal">清理终态任务</button>
              </div>
              <p class="task-column-hint">交给浏览器保存后，任务会记为已完成；浏览器自己的保存进度无法继续读取。</p>
            </div>
            <div class="task-toolbar">
              <input v-model.trim="state.taskPanels.local.keyword" type="text" placeholder="筛选 scene / 文件 / band" />
              <select v-model="state.taskPanels.local.historyStatus">
                <option v-for="option in HISTORY_STATUS_FILTERS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
            <article class="task-section">
              <div class="task-section-head">
                <div>
                  <h4>进行中</h4>
                  <p>{{ localPanel.activeGroupCount }} 景，{{ localPanel.activeTaskCount }} 个任务</p>
                </div>
              </div>
              <div v-if="!localPanel.activeGroups.length" class="empty small">{{ activeEmptyText('local') }}</div>
              <div v-else class="task-groups">
                <article v-for="group in localPanel.activeGroups" :key="`local-active-${group.sceneId}`" class="task-group">
                  <button class="task-group-toggle" type="button" @click="toggleGroup('local', 'active', group.sceneId)">
                    <div class="task-group-main">
                      <div class="task-group-title">
                        <strong>{{ group.sceneId }}</strong>
                        <div class="task-group-levels">
                          <span v-for="variant in group.variants" :key="`${variant.sensor}:${variant.product}`" class="badge" :class="productBadgeClass(variant.product)">{{ sensorLabel(variant.sensor) }} / {{ variant.product }}</span>
                        </div>
                      </div>
                      <div class="task-group-stats">
                        <span>{{ group.fileCount }} 文件</span>
                        <span>{{ group.activeCount }} 进行中</span>
                        <span v-if="group.failedCount">{{ group.failedCount }} 失败</span>
                      </div>
                    </div>
                    <span class="task-toggle-label">{{ isGroupExpanded('local', 'active', group.sceneId) ? '收起' : '展开' }}</span>
                  </button>
                  <div v-if="isGroupExpanded('local', 'active', group.sceneId)" class="task-group-body">
                    <article v-for="task in group.tasks" :key="task.id" class="task-card compact">
                      <div class="between">
                        <div>
                          <strong>{{ task.filename }}</strong>
                          <p>{{ taskSummaryLine(task) }}</p>
                          <p>资产：{{ task.band }}</p>
                          <p v-if="retryText(task)">{{ retryText(task) }}</p>
                        </div>
                        <span class="status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
                      </div>
                      <div class="progress" :class="{ indeterminate: isIndeterminateProgress(task) }"><div class="fill" :style="{ width: `${isIndeterminateProgress(task) ? 36 : task.progress}%` }"></div></div>
                      <div class="between">
                        <span>{{ sizeText(task.size_downloaded, task.size_total) }}</span>
                        <span class="progress-text">{{ taskProgressLabel(task) }}</span>
                        <button v-if="ACTIVE_DOWNLOAD_STATUSES.includes(task.status)" class="btn sub tiny" type="button" @click="cancelLocal(task.id)">取消</button>
                      </div>
                      <p v-if="task.error" class="error">{{ task.error }}</p>
                      <p v-if="detailErrorText(task)" class="error error-detail">{{ detailErrorText(task) }}</p>
                    </article>
                  </div>
                </article>
              </div>
            </article>
            <article class="task-section history-section">
              <div class="task-section-head">
                <div>
                  <h4>历史</h4>
                  <p>{{ localPanel.historyGroupCount }} 景，{{ localPanel.historyTaskCount }} 个任务</p>
                </div>
                <button class="btn sub tiny" type="button" @click="toggleHistory('local')">{{ state.taskPanels.local.historyOpen ? '收起历史' : '展开历史' }}</button>
              </div>
              <div v-if="!localPanel.historyGroups.length" class="empty small">{{ historyEmptyText('local') }}</div>
              <div v-else-if="!state.taskPanels.local.historyOpen" class="task-collapsed-hint">历史区已折叠，当前共 {{ localPanel.historyGroupCount }} 景 / {{ localPanel.historyTaskCount }} 个任务。</div>
              <div v-else class="task-history-scroll">
                <div class="task-groups">
                  <article v-for="group in localPanel.historyGroups" :key="`local-history-${group.sceneId}`" class="task-group">
                    <button class="task-group-toggle" type="button" @click="toggleGroup('local', 'history', group.sceneId)">
                      <div class="task-group-main">
                        <div class="task-group-title">
                          <strong>{{ group.sceneId }}</strong>
                          <div class="task-group-levels">
                            <span v-for="variant in group.variants" :key="`${variant.sensor}:${variant.product}`" class="badge" :class="productBadgeClass(variant.product)">{{ sensorLabel(variant.sensor) }} / {{ variant.product }}</span>
                          </div>
                        </div>
                        <div class="task-group-stats">
                          <span>{{ group.fileCount }} 文件</span>
                          <span v-if="group.failedCount">{{ group.failedCount }} 失败</span>
                        </div>
                      </div>
                      <span class="task-toggle-label">{{ isGroupExpanded('local', 'history', group.sceneId) ? '收起' : '展开' }}</span>
                    </button>
                    <div v-if="isGroupExpanded('local', 'history', group.sceneId)" class="task-group-body">
                      <article v-for="task in group.tasks" :key="task.id" class="task-card compact">
                        <div class="between">
                          <div>
                            <strong>{{ task.filename }}</strong>
                            <p>{{ taskSummaryLine(task) }}</p>
                            <p>资产：{{ task.band }}</p>
                            <p v-if="retryText(task)">{{ retryText(task) }}</p>
                          </div>
                          <span class="status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
                        </div>
                        <div class="progress" :class="{ indeterminate: isIndeterminateProgress(task) }"><div class="fill" :style="{ width: `${isIndeterminateProgress(task) ? 36 : task.progress}%` }"></div></div>
                        <div class="between"><span>{{ sizeText(task.size_downloaded, task.size_total) }}</span><span class="progress-text">{{ taskProgressLabel(task) }}</span></div>
                        <p v-if="task.error" class="error">{{ task.error }}</p>
                        <p v-if="detailErrorText(task)" class="error error-detail">{{ detailErrorText(task) }}</p>
                      </article>
                    </div>
                  </article>
                </div>
              </div>
            </article>
          </section>
          <section class="task-column">
            <div class="task-column-top">
              <div class="head task-head">
                <div class="task-head-copy">
                  <h3>服务端下载</h3>
                  <p>{{ serverActiveCount }} 个进行中 · {{ state.serverTasks.length }} 个总任务</p>
                </div>
                <button class="btn sub" type="button" @click="clearServer">清理终态任务</button>
              </div>
              <p class="task-column-hint" :class="{ placeholder: !state.downloadRoot }" :title="state.downloadRoot || ''">{{ state.downloadRoot || '下载根目录未设置' }}</p>
            </div>
            <div class="task-toolbar">
              <input v-model.trim="state.taskPanels.server.keyword" type="text" placeholder="筛选 scene / 文件 / band" />
              <select v-model="state.taskPanels.server.historyStatus">
                <option v-for="option in HISTORY_STATUS_FILTERS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
            <article class="task-section">
              <div class="task-section-head">
                <div>
                  <h4>进行中</h4>
                  <p>{{ serverPanel.activeGroupCount }} 景，{{ serverPanel.activeTaskCount }} 个任务</p>
                </div>
              </div>
              <div v-if="!serverPanel.activeGroups.length" class="empty small">{{ activeEmptyText('server') }}</div>
              <div v-else class="task-groups">
                <article v-for="group in serverPanel.activeGroups" :key="`server-active-${group.sceneId}`" class="task-group">
                  <button class="task-group-toggle" type="button" @click="toggleGroup('server', 'active', group.sceneId)">
                    <div class="task-group-main">
                      <div class="task-group-title">
                        <strong>{{ group.sceneId }}</strong>
                        <div class="task-group-levels">
                          <span v-for="variant in group.variants" :key="`${variant.sensor}:${variant.product}`" class="badge" :class="productBadgeClass(variant.product)">{{ sensorLabel(variant.sensor) }} / {{ variant.product }}</span>
                        </div>
                      </div>
                      <div class="task-group-stats">
                        <span>{{ group.fileCount }} 文件</span>
                        <span>{{ group.activeCount }} 进行中</span>
                        <span v-if="group.failedCount">{{ group.failedCount }} 失败</span>
                      </div>
                    </div>
                    <span class="task-toggle-label">{{ isGroupExpanded('server', 'active', group.sceneId) ? '收起' : '展开' }}</span>
                  </button>
                  <div v-if="isGroupExpanded('server', 'active', group.sceneId)" class="task-group-body">
                    <article v-for="task in group.tasks" :key="task.id" class="task-card compact">
                      <div class="between">
                        <div>
                          <strong>{{ task.filename }}</strong>
                          <p>{{ taskSummaryLine(task) }}</p>
                          <p>资产：{{ task.band }}</p>
                          <p v-if="task.download_date">目录：{{ taskTargetDir(task) }}</p>
                          <p v-if="retryText(task)">{{ retryText(task) }}</p>
                        </div>
                        <span class="status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
                      </div>
                      <div class="progress" :class="{ indeterminate: isIndeterminateProgress(task) }"><div class="fill" :style="{ width: `${isIndeterminateProgress(task) ? 36 : (task.progress || 0)}%` }"></div></div>
                      <div class="between">
                        <span>{{ sizeText(task.size_downloaded || 0, task.size_total || 0) }}</span>
                        <span class="progress-text">{{ taskProgressLabel(task) }}</span>
                        <div class="row">
                          <button v-if="task.status === 'completed'" class="btn sub tiny" type="button" @click="saveServer(task)">保存到本地</button>
                          <button v-if="ACTIVE_DOWNLOAD_STATUSES.includes(task.status)" class="btn sub tiny" type="button" @click="cancelServer(task.id)">取消</button>
                        </div>
                      </div>
                      <p v-if="task.error" class="error">{{ task.error }}</p>
                      <p v-if="detailErrorText(task)" class="error error-detail">{{ detailErrorText(task) }}</p>
                    </article>
                  </div>
                </article>
              </div>
            </article>
            <article class="task-section history-section">
              <div class="task-section-head">
                <div>
                  <h4>历史</h4>
                  <p>{{ serverPanel.historyGroupCount }} 景，{{ serverPanel.historyTaskCount }} 个任务</p>
                </div>
                <button class="btn sub tiny" type="button" @click="toggleHistory('server')">{{ state.taskPanels.server.historyOpen ? '收起历史' : '展开历史' }}</button>
              </div>
              <div v-if="!serverPanel.historyGroups.length" class="empty small">{{ historyEmptyText('server') }}</div>
              <div v-else-if="!state.taskPanels.server.historyOpen" class="task-collapsed-hint">历史区已折叠，当前共 {{ serverPanel.historyGroupCount }} 景 / {{ serverPanel.historyTaskCount }} 个任务。</div>
              <div v-else class="task-history-scroll">
                <div class="task-groups">
                  <article v-for="group in serverPanel.historyGroups" :key="`server-history-${group.sceneId}`" class="task-group">
                    <button class="task-group-toggle" type="button" @click="toggleGroup('server', 'history', group.sceneId)">
                      <div class="task-group-main">
                        <div class="task-group-title">
                          <strong>{{ group.sceneId }}</strong>
                          <div class="task-group-levels">
                            <span v-for="variant in group.variants" :key="`${variant.sensor}:${variant.product}`" class="badge" :class="productBadgeClass(variant.product)">{{ sensorLabel(variant.sensor) }} / {{ variant.product }}</span>
                          </div>
                        </div>
                        <div class="task-group-stats">
                          <span>{{ group.fileCount }} 文件</span>
                          <span v-if="group.failedCount">{{ group.failedCount }} 失败</span>
                        </div>
                      </div>
                      <span class="task-toggle-label">{{ isGroupExpanded('server', 'history', group.sceneId) ? '收起' : '展开' }}</span>
                    </button>
                    <div v-if="isGroupExpanded('server', 'history', group.sceneId)" class="task-group-body">
                      <article v-for="task in group.tasks" :key="task.id" class="task-card compact">
                        <div class="between">
                          <div>
                            <strong>{{ task.filename }}</strong>
                            <p>{{ taskSummaryLine(task) }}</p>
                            <p>资产：{{ task.band }}</p>
                            <p v-if="task.download_date">目录：{{ taskTargetDir(task) }}</p>
                            <p v-if="retryText(task)">{{ retryText(task) }}</p>
                          </div>
                          <span class="status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
                        </div>
                        <div class="progress" :class="{ indeterminate: isIndeterminateProgress(task) }"><div class="fill" :style="{ width: `${isIndeterminateProgress(task) ? 36 : (task.progress || 0)}%` }"></div></div>
                        <div class="between">
                          <span>{{ sizeText(task.size_downloaded || 0, task.size_total || 0) }}</span>
                          <span class="progress-text">{{ taskProgressLabel(task) }}</span>
                          <button v-if="task.status === 'completed'" class="btn sub tiny" type="button" @click="saveServer(task)">保存到本地</button>
                        </div>
                        <p v-if="task.error" class="error">{{ task.error }}</p>
                        <p v-if="detailErrorText(task)" class="error error-detail">{{ detailErrorText(task) }}</p>
                      </article>
                    </div>
                  </article>
                </div>
              </div>
            </article>
          </section>
        </div>
      </article>
    </section>
    <div v-if="state.modalOpen" class="mask" @click.self="closeAssetModal"><div class="modal"><div class="head"><div><h3>选择资产</h3><p>{{ state.modalScene?.id }} · {{ sensorLabel(state.modalScene?.sensor) }} / {{ state.modalScene?.product }}</p></div><button class="btn sub" type="button" @click="closeAssetModal">关闭</button></div><div class="row"><button class="btn sub" type="button" @click="choosePreset('rgb')">RGB</button><button class="btn sub" type="button" @click="choosePreset('vegetation')">植被组合</button><button class="btn sub" type="button" @click="choosePreset('all')">全选</button><span class="count">已选 {{ selectedModalAssetCount }} 项</span></div><div class="asset-grid"><label v-for="[key, asset] in sortedAssets(state.modalScene?.assets)" :key="key" class="asset-item"><input v-model="state.modalAssets[key]" type="checkbox" /><div><strong>{{ key }}</strong><p>{{ asset.label }}</p></div></label></div><div class="row end"><button class="btn" type="button" @click="confirmAssetDownload">加入下载</button></div></div></div>
    <div v-if="state.showAuthModal" class="mask" @click.self="closeAuth"><div class="modal auth-modal"><div class="head"><div><h3>EarthData / EROS</h3><p>当前主要用于 Landsat L1 / USGS 资产下载。</p></div><button class="btn sub" type="button" @click="closeAuth">关闭</button></div><div class="fields"><label class="full"><span>用户名</span><input v-model="state.authForm.username" type="text" placeholder="EarthData 用户名" /></label><label class="full"><span>密码</span><input v-model="state.authForm.password" type="password" placeholder="密码" /></label></div><div class="row end"><button class="btn" type="button" :disabled="state.authSaving" @click="saveAuth">{{ state.authSaving ? '验证中...' : '保存并验证' }}</button></div></div></div>
    <div v-if="state.showDownloadDirModal" class="mask" @click.self="closeDownloadDir">
      <div class="modal auth-modal">
        <div class="head">
          <div>
            <h3>服务端下载目录</h3>
            <p>服务端任务会保存到该目录下的 YYYY-MM-DD/sensor/product/场景ID。</p>
          </div>
          <button class="btn sub" type="button" @click="closeDownloadDir">关闭</button>
        </div>
        <div class="fields">
          <label class="full">
            <span>子目录</span>
            <input v-model.trim="state.downloadDirSuffix" type="text" placeholder="只填写后半段，例如 project-a/2026-04；留空则使用默认目录" />
          </label>
          <p class="root-hint full">这里只需要填写后半段目录，系统会自动保存到固定目录下。</p>
          <p v-if="state.downloadDirNotice" class="root-hint full">{{ state.downloadDirNotice }}</p>
        </div>
        <div class="row between">
          <button class="btn sub" type="button" :disabled="state.downloadDirSaving" @click="saveDownloadDir(true)">恢复默认</button>
          <button class="btn" type="button" :disabled="state.downloadDirSaving" @click="saveDownloadDir(false)">{{ state.downloadDirSaving ? '保存中...' : '保存目录' }}</button>
        </div>
      </div>
    </div>
    <div v-if="state.showProxyModal" class="mask" @click.self="closeProxy"><div class="modal auth-modal"><div class="head"><div><h3>下载代理</h3><p>用于 STAC 检索、EarthData 登录和影像下载请求。</p></div><button class="btn sub" type="button" @click="closeProxy">关闭</button></div><div class="fields"><label class="full proxy-toggle"><span>启用代理</span><input v-model="state.proxyForm.enabled" type="checkbox" /></label><label class="full"><span>代理地址</span><input v-model="state.proxyForm.proxy_url" type="text" placeholder="http://127.0.0.1:7890" :disabled="!state.proxyForm.enabled" /></label><label class="full"><span>直连列表（可选）</span><input v-model="state.proxyForm.no_proxy" type="text" placeholder="127.0.0.1,localhost,.microsoft.com" :disabled="!state.proxyForm.enabled" /></label></div><div class="row between"><button class="btn sub" type="button" :disabled="state.proxySaving || !state.proxyStatus.enabled" @click="disableProxy">关闭代理</button><button class="btn" type="button" :disabled="state.proxySaving" @click="saveProxy">{{ state.proxySaving ? '保存中...' : '保存配置' }}</button></div></div></div>
  </div>
</template>

<style scoped>
.landsat-download { display: flex; flex-direction: column; gap: 0.75rem; }

/* ── Grid layout ──────────────────────────────────────────── */
.grid { display: grid; grid-template-columns: minmax(300px, 380px) minmax(380px, 1fr); gap: 0.75rem; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 0.65rem 0.75rem; }
.span-all { grid-column: 1 / -1; }

/* ── Common layout helpers ────────────────────────────────── */
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.6rem; }
.head h3 { margin: 0; font-family: 'Teko', sans-serif; font-size: 0.95rem; letter-spacing: 0.05em; text-transform: uppercase; color: var(--text); }
.head p, .scene-text p, .task-card p, .asset-item p { color: var(--muted); font-size: 0.72rem; margin: 2px 0 0; }
.root-hint { color: var(--muted); font-size: 0.65rem; font-family: var(--mono); word-break: break-all; margin: 1px 0 0; }
.row { display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }
.between { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.4rem; }
.end { justify-content: flex-end; }

/* ── Collection chips ─────────────────────────────────────── */
.sensor-switch { display: flex; gap: 0.35rem; flex-wrap: wrap; margin-bottom: 0.5rem; }
.sensor-pill { display: inline-flex; align-items: center; justify-content: center; min-width: 120px; }
.collections { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.4rem; margin-bottom: 0.6rem; }
.collection-chip { display: flex; flex-direction: column; gap: 2px; padding: 0.45rem 0.55rem; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); color: var(--text); text-align: left; cursor: pointer; transition: all 0.15s; }
.collection-chip strong { font-size: 0.82rem; font-weight: 700; font-family: var(--mono); }
.collection-chip span { color: var(--muted); font-size: 0.68rem; }
.collection-chip.active { border-color: var(--pri); background: #e7f4f1; color: var(--pri-dark); }
.collection-chip:hover:not(.active) { border-color: #9ac6ba; }

/* ── Form fields ──────────────────────────────────────────── */
.fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.4rem; margin-bottom: 0.6rem; }
.fields label, .fields > div { display: flex; flex-direction: column; gap: 0.22rem; }
.fields span { font-size: 0.7rem; color: var(--muted); font-weight: 500; }
.fields input { padding: 0.32rem 0.4rem; border: 1px solid #cdd8d4; border-radius: 6px; background: #fff; color: var(--text); font-size: 0.78rem; font-family: inherit; width: 100%; }
.fields input[type='range'] { padding: 0; accent-color: var(--pri); }
.full { grid-column: 1 / -1; }
.download-root-list { display: flex; gap: 0.35rem; flex-wrap: wrap; margin-top: 0.1rem; }
.root-note { padding: 0.45rem 0.55rem; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); }
.root-note strong { color: var(--text); font-family: var(--mono); font-size: 0.72rem; word-break: break-all; }
.mode-switch { display: inline-flex; gap: 0.3rem; margin-top: 2px; }
.pill { padding: 0.26rem 0.55rem; border: 1px solid var(--line); border-radius: 999px; background: var(--card); color: var(--muted); font-size: 0.7rem; cursor: pointer; transition: all 0.15s; }
.pill.active { border-color: var(--pri); background: #e7f4f1; color: var(--pri-dark); font-weight: 600; }
.proxy-toggle { flex-direction: row !important; justify-content: space-between; align-items: center; padding: 0.45rem 0.55rem; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); }
.proxy-toggle input { width: auto !important; padding: 0; border: 0; background: transparent; accent-color: var(--pri); }

/* ── BBox display ─────────────────────────────────────────── */
.bbox-box { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; padding: 0.45rem 0.55rem; border-radius: 6px; background: var(--bg); border: 1px solid var(--line); margin-bottom: 0.6rem; }
.bbox-box span { font-size: 0.7rem; color: var(--muted); }
.bbox-box strong { display: block; margin-top: 2px; color: var(--text); font-family: var(--mono); font-size: 0.68rem; word-break: break-word; }
.aoi-hint { margin: 0.22rem 0 0; color: #4e6f67; font-size: 0.67rem; line-height: 1.45; word-break: break-word; }
.hidden-file-input { display: none; }

/* ── Buttons ──────────────────────────────────────────────── */
.btn { border: 1px solid transparent; border-radius: 6px; cursor: pointer; padding: 0.32rem 0.6rem; font-size: 0.76rem; font-weight: 600; font-family: inherit; transition: all 0.15s; white-space: nowrap; }
.btn.main { width: 100%; background: var(--pri); color: #fff; border-color: var(--pri); padding: 0.42rem 0.6rem; }
.btn.main:hover:not(:disabled) { background: var(--pri-dark); }
.btn.sub { background: #f7faf9; border-color: #c8d7d2; color: #355049; }
.btn.sub:hover:not(:disabled) { background: #e8f5f1; border-color: var(--pri); }
.btn.tiny { padding: 0.2rem 0.42rem; font-size: 0.68rem; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }

/* ── Map ──────────────────────────────────────────────────── */
.map { height: 500px; border-radius: 6px; overflow: hidden; border: 1px solid var(--line); }

/* ── Empty state ──────────────────────────────────────────── */
.empty { margin-top: 0.5rem; padding: 1.5rem 1rem; border: 1px dashed var(--line); border-radius: 6px; color: var(--muted); text-align: center; font-size: 0.78rem; }
.empty.small { padding: 0.65rem 0.5rem; font-size: 0.72rem; }

/* ── Scene grid / cards ───────────────────────────────────── */
.scene-grid { margin-top: 0.5rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 0.5rem; }
.scene-card { padding: 0.6rem; border: 1px solid var(--line); border-radius: 8px; background: var(--card); transition: border-color 0.15s; }
.scene-card.selected { border-color: var(--pri); background: #f4faf8; }
.scene-card:hover { border-color: #9ac6ba; }
.scene-top { display: grid; grid-template-columns: 76px 1fr auto; gap: 0.55rem; align-items: start; margin-bottom: 0.5rem; }
.thumb { width: 76px; height: 76px; border-radius: 6px; overflow: hidden; background: var(--bg); display: flex; align-items: center; justify-content: center; color: var(--muted); font-weight: 700; font-size: 0.78rem; border: 1px solid var(--line); }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.scene-text h4 { margin: 0 0 2px; font-size: 0.7rem; color: var(--text); font-family: var(--mono); word-break: break-all; }
.checker { display: flex; flex-direction: column; gap: 4px; align-items: center; font-size: 0.65rem; color: var(--muted); }
.badge, .status { display: inline-flex; align-items: center; justify-content: center; padding: 2px 8px; border-radius: 999px; font-size: 0.62rem; font-weight: 700; border: 1px solid; }
.level-l1 { background: #fffbf0; color: var(--warn); border-color: #f5e6c3; }
.level-l2 { background: #e7f4f1; color: var(--ok); border-color: #b9d9d0; }
.level-l2a { background: #eef3ff; color: #355cb3; border-color: #c7d5f8; }
.level-default { background: var(--bg); color: var(--muted); border-color: var(--line); }
.between small { font-size: 0.65rem; color: var(--muted); }

/* ── Task panel ───────────────────────────────────────────── */
.task-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; align-items: start; }
.task-column { display: flex; flex-direction: column; gap: 0.75rem; min-width: 0; }
.task-column-top { display: flex; flex-direction: column; gap: 0.3rem; min-width: 0; }
.task-head { margin-bottom: 0; }
.task-head-copy { min-width: 0; }
.task-column-hint { margin: 0; min-height: 1rem; color: var(--muted); font-size: 0.65rem; font-family: var(--mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.task-column-hint.placeholder { visibility: hidden; }
.task-toolbar { display: flex; gap: 0.45rem; flex-wrap: wrap; }
.task-toolbar input, .task-toolbar select { flex: 1 1 180px; min-width: 0; padding: 0.32rem 0.4rem; border: 1px solid #cdd8d4; border-radius: 6px; background: #fff; color: var(--text); font-size: 0.76rem; font-family: inherit; }
.task-section { border: 1px solid var(--line); border-radius: 8px; background: #fbfcfb; padding: 0.55rem 0.6rem; }
.history-section { background: #f6faf8; }
.task-section-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.45rem; flex-wrap: wrap; margin-bottom: 0.45rem; }
.task-section-head h4 { margin: 0; font-size: 0.78rem; font-family: var(--mono); color: var(--text); }
.task-section-head p { margin: 2px 0 0; color: var(--muted); font-size: 0.68rem; }
.task-collapsed-hint { padding: 0.55rem 0.6rem; border: 1px dashed var(--line); border-radius: 6px; background: rgba(255, 255, 255, 0.65); color: var(--muted); font-size: 0.72rem; }
.task-history-scroll { max-height: 420px; overflow: auto; padding-right: 0.15rem; }
.task-groups { display: flex; flex-direction: column; gap: 0.45rem; }
.task-group { border: 1px solid var(--line); border-radius: 8px; background: var(--card); overflow: hidden; }
.task-group-toggle { width: 100%; display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; padding: 0.52rem 0.6rem; border: 0; background: transparent; cursor: pointer; text-align: left; }
.task-group-main { display: flex; flex: 1; justify-content: space-between; align-items: flex-start; gap: 0.75rem; flex-wrap: wrap; min-width: 0; }
.task-group-title { display: flex; flex-direction: column; gap: 0.3rem; min-width: 0; }
.task-group-title strong { font-size: 0.73rem; color: var(--text); display: block; font-family: var(--mono); word-break: break-all; }
.task-group-levels { display: flex; gap: 0.25rem; flex-wrap: wrap; }
.task-group-stats { display: flex; gap: 0.35rem; flex-wrap: wrap; justify-content: flex-end; }
.task-group-stats span { padding: 2px 8px; border-radius: 999px; border: 1px solid var(--line); background: var(--bg); color: var(--muted); font-size: 0.64rem; white-space: nowrap; }
.task-toggle-label { padding-top: 2px; color: #355049; font-size: 0.64rem; font-weight: 600; white-space: nowrap; }
.task-group-body { display: flex; flex-direction: column; gap: 0.35rem; padding: 0 0.55rem 0.55rem 0.9rem; }
.task-card { padding: 0.5rem 0.6rem; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); }
.task-card.compact { background: #fff; }
.task-card strong { font-size: 0.73rem; color: var(--text); display: block; }
.task-card p { color: var(--muted); font-size: 0.65rem; margin: 1px 0; }
.progress { height: 6px; margin: 0.35rem 0 0.28rem; border-radius: 999px; background: var(--line); overflow: hidden; }
.fill { height: 100%; background: linear-gradient(90deg, var(--pri), #6fae7f); border-radius: inherit; transition: width 0.25s ease; }
.progress.indeterminate .fill { width: 36%; animation: progress-slide 1.15s ease-in-out infinite; }
.progress-text { margin-left: auto; color: #355049; font-size: 0.65rem; font-weight: 700; white-space: nowrap; }
.status-pending { background: var(--bg); color: var(--muted); border-color: var(--line); }
.status-downloading { background: #e7f4f1; color: var(--ok); border-color: #b9d9d0; }
.status-retrying { background: #fffbf0; color: var(--warn); border-color: #f5e6c3; }
.status-completed { background: #e7f4f1; color: var(--ok); border-color: #b9d9d0; }
.status-failed { background: #fee2e2; color: var(--err); border-color: #e2c4c2; }
.status-cancelled { background: var(--bg); color: var(--muted); border-color: var(--line); }
.error { margin: 0.28rem 0 0; color: var(--err); font-size: 0.65rem; line-height: 1.4; }
.error-detail { color: var(--muted); }
@keyframes progress-slide {
  0% { transform: translateX(-120%); }
  100% { transform: translateX(320%); }
}

/* ── Modals ───────────────────────────────────────────────── */
.mask { position: fixed; inset: 0; z-index: 30; display: flex; align-items: center; justify-content: center; padding: 1rem; background: rgba(20, 30, 27, 0.42); }
.modal { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 1rem; width: min(720px, 100%); max-height: 88vh; overflow: auto; }
.auth-modal { width: min(480px, 100%); }
.asset-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(196px, 1fr)); gap: 0.4rem; margin-top: 0.6rem; }
.asset-item { display: flex; gap: 0.4rem; align-items: flex-start; padding: 0.4rem 0.5rem; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); cursor: pointer; }
.asset-item strong { display: block; font-size: 0.72rem; color: var(--text); font-family: var(--mono); }
.count { margin-left: auto; color: var(--pri); font-weight: 700; font-size: 0.72rem; }

/* ── Responsive ───────────────────────────────────────────── */
@media (max-width: 1100px) { .grid { grid-template-columns: 1fr; } .map { height: 400px; } .task-columns { grid-template-columns: 1fr; } }
@media (max-width: 720px) { .bbox-box { flex-direction: column; } .fields, .collections, .asset-grid, .scene-grid { grid-template-columns: 1fr; } .scene-top { grid-template-columns: 70px 1fr auto; } }
</style>
