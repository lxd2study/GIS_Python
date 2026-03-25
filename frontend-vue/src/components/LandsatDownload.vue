<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import XYZ from 'ol/source/XYZ'
import Draw, { createBox } from 'ol/interaction/Draw'
import Feature from 'ol/Feature'
import Polygon, { fromExtent as polygonFromExtent } from 'ol/geom/Polygon'
import { Fill, Stroke, Style } from 'ol/style'
import { fromLonLat, transformExtent } from 'ol/proj'

const props = defineProps({ apiBase: { type: String, required: true } })
const emit = defineEmits(['toast'])
const mapTarget = ref(null)

const state = reactive({
  collections: [],
  downloadRoot: '',
  authStatus: { configured: false, username: '' },
  level: 'L2',
  startDate: offsetDay(-90),
  endDate: offsetDay(0),
  maxCloudCover: 20,
  limit: 20,
  bbox: null,
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
  authForm: { username: '', password: '' },
  authSaving: false,
  serverTasks: [],
  localTasks: {},
  localQueue: [],
  localBusy: false
})

const aoiSource = new VectorSource()
const footprintSource = new VectorSource()
let map = null
let drawInteraction = null
let footprintLayer = null
let serverPollTimer = null

const selectedScenes = computed(() => state.searchResults.filter((scene) => state.selectedScenes[scene.id]))
const selectedSceneCount = computed(() => selectedScenes.value.length)
const localTaskList = computed(() => Object.values(state.localTasks).sort((a, b) => b.createdAt - a.createdAt))
const localActiveCount = computed(() => localTaskList.value.filter((task) => ['pending', 'downloading'].includes(task.status)).length)
const serverActiveCount = computed(() => state.serverTasks.filter((task) => ['pending', 'downloading'].includes(task.status)).length)
const selectedModalAssetCount = computed(() => Object.values(state.modalAssets).filter(Boolean).length)

function offsetDay(days) { const d = new Date(); d.setDate(d.getDate() + days); return d.toISOString().slice(0, 10) }
function apiBase() { return (props.apiBase || '').trim().replace(/\/+$/, '') || 'http://127.0.0.1:5001' }
function toast(message, type = 'idle') { emit('toast', { message, type }) }
function statusLabel(status) { return { pending: '等待中', downloading: '下载中', completed: '已完成', failed: '失败', cancelled: '已取消' }[status] || status }
function statusClass(status) { return `status-${status || 'pending'}` }
function sceneDate(value) { return value ? String(value).slice(0, 10) : '未知日期' }
function cloudText(value) { return value === null || value === undefined ? '--' : `${Number(value).toFixed(1)}%` }
function bboxText() { return state.bbox ? state.bbox.map((value) => Number(value).toFixed(4)).join(', ') : '尚未绘制' }
function pathRow(scene) { return `P${String(scene?.path ?? '--').padStart(3, '0')} / R${String(scene?.row ?? '--').padStart(3, '0')}` }
function sizeText(done, total = 0) { const f = (v) => !v ? '0 B' : v >= 1073741824 ? `${(v / 1073741824).toFixed(1)} GB` : v >= 1048576 ? `${(v / 1048576).toFixed(1)} MB` : v >= 1024 ? `${(v / 1024).toFixed(0)} KB` : `${v} B`; return total > 0 ? `${f(done)} / ${f(total)}` : f(done) }
function sortedAssets(assets) { return Object.entries(assets || {}).sort((a, b) => a[0].localeCompare(b[0], 'en')) }
function filenameFrom(url, sceneId, band) { const name = (url || '').split('?')[0].split('/').pop(); return name || `${sceneId}_${band}.tif` }
function errorText(detail) { if (typeof detail === 'string') return detail; if (Array.isArray(detail)) return detail.map((item) => item.msg || JSON.stringify(item)).join(' | '); if (detail && typeof detail === 'object') return detail.msg || JSON.stringify(detail); return '请求失败' }

async function request(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(errorText(data.detail || data.message || `HTTP ${response.status}`))
  return data
}

watch(() => state.hoveredSceneId, () => footprintLayer && footprintLayer.changed())
watch(() => state.selectedScenes, () => footprintLayer && footprintLayer.changed(), { deep: true })
watch(() => props.apiBase, async () => { await Promise.all([loadCollections(true), loadAuthStatus(true), loadServerTasks(true)]) })

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
// 用 OpenLayers 的 box geometryFunction 生成矩形 AOI，直接得到后端需要的 bbox。
function drawBox() { if (!map) return; removeDraw(); drawInteraction = new Draw({ source: aoiSource, type: 'Circle', geometryFunction: createBox() }); drawInteraction.on('drawstart', () => aoiSource.clear()); drawInteraction.on('drawend', (event) => { state.bbox = transformExtent(event.feature.getGeometry().getExtent(), 'EPSG:3857', 'EPSG:4326').map((value) => Number(value.toFixed(4))); removeDraw(); toast('检索范围已更新', 'ok') }); map.addInteraction(drawInteraction); state.drawActive = true }
function clearBox() { aoiSource.clear(); state.bbox = null; removeDraw() }
function locateScene(scene) { if (!map || !scene?.bbox) return; map.getView().fit(transformExtent(scene.bbox, 'EPSG:4326', 'EPSG:3857'), { padding: [48, 48, 48, 48], duration: 250, maxZoom: 10 }) }
function renderFootprints() { footprintSource.clear(); state.searchResults.forEach((scene) => { if (!scene.bbox || scene.bbox.length !== 4) return; const feature = new Feature(polygonFromExtent(transformExtent(scene.bbox, 'EPSG:4326', 'EPSG:3857'))); feature.set('sceneId', scene.id); footprintSource.addFeature(feature) }); footprintLayer && footprintLayer.changed() }

async function loadCollections(silent = false) { try { const data = await request('/landsat/collections'); state.collections = data.collections || []; state.downloadRoot = data.download_dir || '' } catch (error) { if (!silent) toast(`加载配置失败：${error.message}`, 'error') } }
async function loadAuthStatus(silent = false) { try { state.authStatus = await request('/landsat/auth/status') } catch (error) { if (!silent) toast(`读取账号状态失败：${error.message}`, 'error') } }
async function loadServerTasks(silent = false) { try { const data = await request('/landsat/download_tasks'); state.serverTasks = (data.tasks || []).sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))); if (state.serverTasks.some((task) => ['pending', 'downloading'].includes(task.status))) startServerPoll(); else stopServerPoll() } catch (error) { if (!silent) toast(`读取服务端任务失败：${error.message}`, 'error') } }
function startServerPoll() { if (serverPollTimer !== null) return; serverPollTimer = window.setInterval(() => loadServerTasks(true), 2000) }
function stopServerPoll() { if (serverPollTimer !== null) { window.clearInterval(serverPollTimer); serverPollTimer = null } }

async function searchScenes() {
  if (!state.bbox) return toast('请先在地图上绘制矩形范围', 'warn')
  if (!state.startDate || !state.endDate) return toast('请填写完整日期范围', 'warn')
  if (state.startDate > state.endDate) return toast('开始日期不能晚于结束日期', 'warn')
  state.searchLoading = true
  try {
    const data = await request('/landsat/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bbox: state.bbox, start_date: state.startDate, end_date: state.endDate, max_cloud_cover: Number(state.maxCloudCover), level: state.level, limit: Number(state.limit) }) })
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
function choosePreset(preset) { const scene = state.modalScene; if (!scene) return; const isL1 = scene.level === 'L1'; const keep = preset === 'all' ? null : new Set({ rgb: isL1 ? ['B4', 'B3', 'B2'] : ['red', 'green', 'blue'], vegetation: isL1 ? ['B5', 'B4', 'B3'] : ['nir08', 'red', 'green'] }[preset] || []); Object.keys(scene.assets || {}).forEach((key) => { state.modalAssets[key] = keep ? keep.has(key) : true }) }
function buildItems(scene, assetKeys = null) { const assets = scene.assets || {}; return (assetKeys || Object.keys(assets)).filter((key) => assets[key]).map((key) => ({ scene_id: scene.id, band: key, filename: filenameFrom(assets[key].href, scene.id, key), url: assets[key].href })) }
async function confirmAssetDownload() { if (!state.modalScene) return; const assetKeys = Object.entries(state.modalAssets).filter(([, checked]) => checked).map(([key]) => key); if (!assetKeys.length) return toast('请至少选择一个资产', 'warn'); const items = buildItems(state.modalScene, assetKeys); closeAssetModal(); await enqueue(items) }
async function downloadScene(scene) { await enqueue(buildItems(scene)) }
async function downloadSelected() { if (!selectedScenes.value.length) return toast('请先勾选至少一景', 'warn'); await enqueue(selectedScenes.value.flatMap((scene) => buildItems(scene))) }

async function enqueue(items) {
  if (!items.length) return toast('没有可加入的下载项', 'warn')
  if (state.downloadMode === 'server') {
    try { const data = await request('/landsat/download', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items, mode: 'server' }) }); toast(`已创建 ${data.count || items.length} 个服务端任务`, 'ok'); await loadServerTasks(true) } catch (error) { toast(`创建服务端任务失败：${error.message}`, 'error') }
    return
  }
  items.forEach((item) => { const id = `${Date.now()}_${Math.random().toString(16).slice(2, 8)}`; state.localTasks[id] = { ...item, id, status: 'pending', progress: 0, size_total: 0, size_downloaded: 0, error: '', createdAt: Date.now(), controller: null }; state.localQueue.push(id) })
  toast(`已加入 ${items.length} 个浏览器下载任务`, 'ok')
  processLocalQueue()
}

function saveBlob(blob, filename) { const href = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = href; link.download = filename; document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(href), 5000) }
// 浏览器模式顺序下载，避免多景并发时把内存和网络同时拉满。
async function processLocalQueue() { if (state.localBusy || !state.localQueue.length) return; state.localBusy = true; while (state.localQueue.length) { const taskId = state.localQueue.shift(); const task = state.localTasks[taskId]; if (!task || task.status === 'cancelled') continue; task.status = 'downloading'; const controller = new AbortController(); task.controller = controller; try { const response = await fetch(`${apiBase()}/landsat/proxy_download?url=${encodeURIComponent(task.url)}&filename=${encodeURIComponent(task.filename)}`, { signal: controller.signal }); if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(errorText(data.detail || `HTTP ${response.status}`)) } const total = Number(response.headers.get('content-length') || 0); task.size_total = total; if (response.body && response.body.getReader) { const reader = response.body.getReader(); const chunks = []; let downloaded = 0; while (true) { const { done, value } = await reader.read(); if (done) break; if (task.status === 'cancelled') { await reader.cancel().catch(() => {}); break } chunks.push(value); downloaded += value.length; task.size_downloaded = downloaded; task.progress = total ? Math.round(downloaded / total * 100) : 0 } if (task.status !== 'cancelled') { const blob = new Blob(chunks); task.size_downloaded = blob.size; task.size_total = total || blob.size; task.progress = 100; task.status = 'completed'; saveBlob(blob, task.filename) } } else { const blob = await response.blob(); if (task.status !== 'cancelled') { task.size_downloaded = blob.size; task.size_total = blob.size; task.progress = 100; task.status = 'completed'; saveBlob(blob, task.filename) } } } catch (error) { if (task.status === 'cancelled' || error.name === 'AbortError') task.status = 'cancelled'; else { task.status = 'failed'; task.error = error.message || '下载失败' } } finally { task.controller = null } } state.localBusy = false }
function cancelLocal(taskId) { const task = state.localTasks[taskId]; if (!task) return; task.status = 'cancelled'; task.controller?.abort(); state.localQueue = state.localQueue.filter((item) => item !== taskId) }
async function cancelServer(taskId) { try { await request(`/landsat/download_tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' }); await loadServerTasks(true) } catch (error) { toast(`取消失败：${error.message}`, 'error') } }
function saveServer(task) { const link = document.createElement('a'); link.href = `${apiBase()}/landsat/download_tasks/${encodeURIComponent(task.id)}/file`; link.target = '_blank'; link.rel = 'noopener'; document.body.appendChild(link); link.click(); link.remove() }
async function clearServer() { try { await request('/landsat/download_tasks/completed', { method: 'DELETE' }); await loadServerTasks(true) } catch (error) { toast(`清理失败：${error.message}`, 'error') } }
function clearLocal() { Object.entries(state.localTasks).forEach(([id, task]) => { if (['completed', 'failed', 'cancelled'].includes(task.status)) delete state.localTasks[id] }) }

function openAuth() { state.authForm.username = state.authStatus.username || ''; state.authForm.password = ''; state.showAuthModal = true }
function closeAuth() { state.showAuthModal = false; state.authForm.password = '' }
async function saveAuth() { const username = state.authForm.username.trim(); const password = state.authForm.password; if (!username || !password) return toast('请填写完整账号和密码', 'warn'); state.authSaving = true; try { await request('/landsat/auth/earthdata', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) }); await loadAuthStatus(true); closeAuth(); toast('EarthData / EROS 账号已更新', 'ok') } catch (error) { toast(`账号验证失败：${error.message}`, 'error') } finally { state.authSaving = false } }

onMounted(async () => { await nextTick(); initMap(); window.setTimeout(() => map && map.updateSize(), 320); await Promise.all([loadCollections(true), loadAuthStatus(true), loadServerTasks(true)]) })
onBeforeUnmount(() => { stopServerPoll(); removeDraw(); if (map) map.setTarget(null) })
</script>

<template>
  <div class="landsat-download">
    <section class="grid">
      <article class="card">
        <div class="head"><div><h3>检索条件</h3></div><button class="btn sub" type="button" @click="openAuth">{{ state.authStatus.configured ? `账号：${state.authStatus.username}` : '配置 EarthData' }}</button></div>
        <div class="collections"><button v-for="collection in state.collections" :key="collection.level" class="collection-chip" :class="{ active: state.level === collection.level }" type="button" @click="state.level = collection.level"><strong>{{ collection.level }}</strong><span>{{ collection.title }}</span></button></div>
        <div class="fields">
          <label><span>开始日期</span><input v-model="state.startDate" type="date" /></label>
          <label><span>结束日期</span><input v-model="state.endDate" type="date" /></label>
          <label class="full"><span>最大云量 {{ state.maxCloudCover }}%</span><input v-model.number="state.maxCloudCover" type="range" min="0" max="100" step="1" /></label>
          <label><span>返回上限</span><input v-model.number="state.limit" type="number" min="1" max="100" /></label>
          <div><span>下载模式</span><div class="mode-switch"><button class="pill" :class="{ active: state.downloadMode === 'server' }" type="button" @click="state.downloadMode = 'server'">服务端</button><button class="pill" :class="{ active: state.downloadMode === 'local' }" type="button" @click="state.downloadMode = 'local'">浏览器</button></div></div>
        </div>
        <div class="bbox-box"><div><span>当前范围</span><strong>{{ bboxText() }}</strong></div><div class="row"><button class="btn" type="button" @click="drawBox">{{ state.drawActive ? '重新框选中...' : '绘制矩形' }}</button><button class="btn sub" type="button" @click="clearBox">清空</button></div></div>
        <button class="btn main" type="button" :disabled="state.searchLoading" @click="searchScenes">{{ state.searchLoading ? '检索中...' : '开始检索' }}</button>
      </article>
      <article class="card"><div class="head"><div><h3>地图范围</h3><p>{{ state.searchResults.length }} 景，{{ selectedSceneCount }} 已选</p></div></div><div ref="mapTarget" class="map"></div></article>
      <article class="card span-all">
        <div class="head"><div><h3>检索结果</h3></div><div class="row"><button class="btn sub" type="button" @click="toggleAll(true)">全选</button><button class="btn sub" type="button" @click="toggleAll(false)">清空</button><button class="btn" type="button" @click="downloadSelected">下载所选景全部资产</button></div></div>
        <div v-if="!state.searchResults.length" class="empty">还没有检索结果。先画框，再点击“开始检索”。</div>
        <div v-else class="scene-grid">
          <article v-for="scene in state.searchResults" :key="scene.id" class="scene-card" :class="{ selected: state.selectedScenes[scene.id] }" @mouseenter="state.hoveredSceneId = scene.id" @mouseleave="state.hoveredSceneId = ''">
            <div class="scene-top"><div class="thumb"><img v-if="scene.thumbnail" :src="scene.thumbnail" :alt="scene.id" loading="lazy" /><span v-else>L8</span></div><div class="scene-text"><div class="between"><h4>{{ scene.id }}</h4><span class="badge" :class="`level-${scene.level?.toLowerCase()}`">{{ scene.level }}</span></div><p>{{ sceneDate(scene.datetime) }} · {{ pathRow(scene) }}</p><p>云量 {{ cloudText(scene.cloud_cover) }} · {{ Object.keys(scene.assets || {}).length }} 个资产</p></div><label class="checker"><input :checked="!!state.selectedScenes[scene.id]" type="checkbox" @change="setScene(scene.id, $event.target.checked)" /><span>{{ state.selectedScenes[scene.id] ? '已选' : '选择' }}</span></label></div>
            <div class="row"><button class="btn sub" type="button" @click="locateScene(scene)">定位</button><button class="btn sub" type="button" @click="openAssetModal(scene)">选资产</button><button class="btn" type="button" @click="downloadScene(scene)">全部资产</button></div>
          </article>
        </div>
      </article>
      <article class="card span-all">
        <div class="task-columns">
          <section><div class="head"><div><h3>浏览器下载</h3><p>{{ localActiveCount }} 个进行中</p></div><button class="btn sub" type="button" @click="clearLocal">清理已完成</button></div><div v-if="!localTaskList.length" class="empty small">暂无浏览器下载任务。</div><div v-else class="task-list"><article v-for="task in localTaskList" :key="task.id" class="task-card"><div class="between"><div><strong>{{ task.filename }}</strong><p>{{ task.scene_id }} / {{ task.band }}</p></div><span class="status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span></div><div class="progress"><div class="fill" :style="{ width: `${task.progress}%` }"></div></div><div class="between"><span>{{ sizeText(task.size_downloaded, task.size_total) }}</span><button v-if="['pending', 'downloading'].includes(task.status)" class="btn sub tiny" type="button" @click="cancelLocal(task.id)">取消</button></div><p v-if="task.error" class="error">{{ task.error }}</p></article></div></section>
          <section><div class="head"><div><h3>服务端下载</h3><p>{{ serverActiveCount }} 个进行中</p><p v-if="state.downloadRoot" class="root-hint">{{ state.downloadRoot }}</p></div><button class="btn sub" type="button" @click="clearServer">清理终态任务</button></div><div v-if="!state.serverTasks.length" class="empty small">暂无服务端下载任务。</div><div v-else class="task-list"><article v-for="task in state.serverTasks" :key="task.id" class="task-card"><div class="between"><div><strong>{{ task.filename }}</strong><p>{{ task.scene_id }} / {{ task.band }}</p></div><span class="status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span></div><div class="progress"><div class="fill" :style="{ width: `${task.progress || 0}%` }"></div></div><div class="between"><span>{{ sizeText(task.size_downloaded || 0, task.size_total || 0) }}</span><div class="row"><button v-if="task.status === 'completed'" class="btn sub tiny" type="button" @click="saveServer(task)">保存到本地</button><button v-if="['pending', 'downloading'].includes(task.status)" class="btn sub tiny" type="button" @click="cancelServer(task.id)">取消</button></div></div><p v-if="task.error" class="error">{{ task.error }}</p></article></div></section>
        </div>
      </article>
    </section>
    <div v-if="state.modalOpen" class="mask" @click.self="closeAssetModal"><div class="modal"><div class="head"><div><h3>选择资产</h3><p>{{ state.modalScene?.id }}</p></div><button class="btn sub" type="button" @click="closeAssetModal">关闭</button></div><div class="row"><button class="btn sub" type="button" @click="choosePreset('rgb')">RGB</button><button class="btn sub" type="button" @click="choosePreset('vegetation')">植被组合</button><button class="btn sub" type="button" @click="choosePreset('all')">全选</button><span class="count">已选 {{ selectedModalAssetCount }} 项</span></div><div class="asset-grid"><label v-for="[key, asset] in sortedAssets(state.modalScene?.assets)" :key="key" class="asset-item"><input v-model="state.modalAssets[key]" type="checkbox" /><div><strong>{{ key }}</strong><p>{{ asset.label }}</p></div></label></div><div class="row end"><button class="btn" type="button" @click="confirmAssetDownload">加入下载</button></div></div></div>
    <div v-if="state.showAuthModal" class="mask" @click.self="closeAuth"><div class="modal auth-modal"><div class="head"><div><h3>EarthData / EROS</h3><p>仅在下载部分 USGS 资产时需要。</p></div><button class="btn sub" type="button" @click="closeAuth">关闭</button></div><div class="fields"><label class="full"><span>用户名</span><input v-model="state.authForm.username" type="text" placeholder="EarthData 用户名" /></label><label class="full"><span>密码</span><input v-model="state.authForm.password" type="password" placeholder="密码" /></label></div><div class="row end"><button class="btn" type="button" :disabled="state.authSaving" @click="saveAuth">{{ state.authSaving ? '验证中...' : '保存并验证' }}</button></div></div></div>
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
.mode-switch { display: inline-flex; gap: 0.3rem; margin-top: 2px; }
.pill { padding: 0.26rem 0.55rem; border: 1px solid var(--line); border-radius: 999px; background: var(--card); color: var(--muted); font-size: 0.7rem; cursor: pointer; transition: all 0.15s; }
.pill.active { border-color: var(--pri); background: #e7f4f1; color: var(--pri-dark); font-weight: 600; }

/* ── BBox display ─────────────────────────────────────────── */
.bbox-box { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; padding: 0.45rem 0.55rem; border-radius: 6px; background: var(--bg); border: 1px solid var(--line); margin-bottom: 0.6rem; }
.bbox-box span { font-size: 0.7rem; color: var(--muted); }
.bbox-box strong { display: block; margin-top: 2px; color: var(--text); font-family: var(--mono); font-size: 0.68rem; word-break: break-word; }

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
.between small { font-size: 0.65rem; color: var(--muted); }

/* ── Task panel ───────────────────────────────────────────── */
.task-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; }
.task-list { display: flex; flex-direction: column; gap: 0.4rem; margin-top: 0.5rem; }
.task-card { padding: 0.5rem 0.6rem; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); }
.task-card strong { font-size: 0.73rem; color: var(--text); display: block; }
.task-card p { color: var(--muted); font-size: 0.65rem; margin: 1px 0; }
.progress { height: 6px; margin: 0.35rem 0 0.28rem; border-radius: 999px; background: var(--line); overflow: hidden; }
.fill { height: 100%; background: linear-gradient(90deg, var(--pri), #6fae7f); border-radius: inherit; transition: width 0.25s ease; }
.status-pending { background: var(--bg); color: var(--muted); border-color: var(--line); }
.status-downloading { background: #e7f4f1; color: var(--ok); border-color: #b9d9d0; }
.status-completed { background: #e7f4f1; color: var(--ok); border-color: #b9d9d0; }
.status-failed { background: #fee2e2; color: var(--err); border-color: #e2c4c2; }
.status-cancelled { background: var(--bg); color: var(--muted); border-color: var(--line); }
.error { margin: 0.28rem 0 0; color: var(--err); font-size: 0.65rem; line-height: 1.4; }

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
