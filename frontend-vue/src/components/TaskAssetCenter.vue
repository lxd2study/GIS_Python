<script setup>
import { computed, onMounted, reactive, watch } from 'vue'

const props = defineProps({
  apiBase: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['toast'])

const CATEGORY_LABELS = {
  processed: '处理波段',
  composite: '合成与指数',
  mask: '掩膜结果',
  metadata: '摘要与清单',
  extra: '其他文件'
}

const SUMMARY_LABELS = {
  total_bands_processed: '处理波段',
  composites_created: '合成数量',
  cloud_mask_applied: '云掩膜',
  clipped: '裁剪',
  product_level: '产品级别',
  processing_mode: '处理模式',
  scene_count: '场景数',
  band_count: '波段数',
  output_directory: '输出目录'
}

const state = reactive({
  loading: false,
  tasks: [],
  search: '',
  sourceFilter: 'all',
  typeFilter: 'all',
  selectedTaskId: '',
  previewPath: '',
  previewImage: '',
  previewMeta: null,
  previewLoading: false
})

function apiBase() {
  const value = String(props.apiBase || '').trim().replace(/\/+$/, '')
  return value || 'http://127.0.0.1:5001'
}

function parseDetail(detail) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => (typeof item === 'object' ? item.msg || JSON.stringify(item) : String(item))).join(' | ')
  if (detail && typeof detail === 'object') return detail.msg || JSON.stringify(detail)
  return '请求失败'
}

async function request(path, options = {}) {
  const resp = await fetch(`${apiBase()}${path}`, options)
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new Error(parseDetail(data.detail || data.message || `HTTP ${resp.status}`))
  return data
}

const taskStats = computed(() => ({
  total: state.tasks.length,
  current: state.tasks.filter((item) => item.source === 'current').length,
  history: state.tasks.filter((item) => item.source === 'history').length
}))

const filteredTasks = computed(() => {
  const search = state.search.trim().toLowerCase()
  return state.tasks.filter((task) => {
    if (state.sourceFilter !== 'all' && task.source !== state.sourceFilter) return false
    if (state.typeFilter !== 'all' && task.task_type !== state.typeFilter) return false
    if (!search) return true
    const haystack = [
      task.title,
      task.job_id,
      task.batch_id,
      task.output_dir
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return haystack.includes(search)
  })
})

const selectedTask = computed(() => {
  return filteredTasks.value.find((item) => item.id === state.selectedTaskId) || null
})

const artifactGroups = computed(() => {
  const task = selectedTask.value
  if (!task) return []

  return ['processed', 'composite', 'mask', 'metadata', 'extra']
    .map((category) => ({
      category,
      label: CATEGORY_LABELS[category] || category,
      items: (task.artifacts || []).filter((item) => item.category === category)
    }))
    .filter((group) => group.items.length)
})

const summaryEntries = computed(() => {
  const task = selectedTask.value
  if (!task?.summary) return []

  return Object.entries(task.summary)
    .filter(([key, value]) => key !== 'output_directory' && value !== null && value !== undefined && value !== '')
    .map(([key, value]) => ({
      key,
      label: SUMMARY_LABELS[key] || key,
      value: formatSummaryValue(value)
    }))
})

function syncSelection() {
  if (!filteredTasks.value.length) {
    state.selectedTaskId = ''
    resetPreview()
    return
  }
  const exists = filteredTasks.value.some((item) => item.id === state.selectedTaskId)
  if (!exists) {
    state.selectedTaskId = filteredTasks.value[0].id
  }
}

function resetPreview() {
  state.previewPath = ''
  state.previewImage = ''
  state.previewMeta = null
  state.previewLoading = false
}

async function loadTasks(silent = false) {
  state.loading = true
  try {
    const data = await request('/results/tasks')
    state.tasks = Array.isArray(data.tasks) ? data.tasks : []
    syncSelection()
    if (!silent) emit('toast', { type: 'ok', message: `已加载 ${state.tasks.length} 个结果任务` })
  } catch (error) {
    if (!silent) emit('toast', { type: 'error', message: `读取结果任务失败：${error.message}` })
  } finally {
    state.loading = false
  }
}

function selectTask(task) {
  state.selectedTaskId = task.id
  if (!task || !(task.artifacts || []).some((item) => item.path === state.previewPath)) {
    resetPreview()
  }
}

async function previewArtifact(item) {
  if (!item?.previewable) return
  state.previewLoading = true
  try {
    const body = new FormData()
    body.append('file_path', item.path)
    body.append('max_size', '768')
    const data = await request('/preview_raster', { method: 'POST', body })
    state.previewPath = item.path
    state.previewMeta = data.preview || null
    state.previewImage = data.preview?.base64 ? `data:image/png;base64,${data.preview.base64}` : ''
  } catch (error) {
    emit('toast', { type: 'error', message: `预览失败：${error.message}` })
  } finally {
    state.previewLoading = false
  }
}

function triggerDownload(url) {
  const link = document.createElement('a')
  link.href = url
  link.target = '_blank'
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

function downloadFile(item) {
  if (!item?.path) return
  triggerDownload(`${apiBase()}/results/download/file?file_path=${encodeURIComponent(item.path)}`)
}

function downloadArchive(task = selectedTask.value) {
  if (!task?.output_dir) return
  triggerDownload(`${apiBase()}/results/download/archive?output_dir=${encodeURIComponent(task.output_dir)}`)
}

function formatTime(value) {
  if (!value) return '未知时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatSize(value) {
  const size = Number(value || 0)
  if (!Number.isFinite(size) || size <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let next = size
  let unitIndex = 0
  while (next >= 1024 && unitIndex < units.length - 1) {
    next /= 1024
    unitIndex += 1
  }
  const precision = next >= 10 || unitIndex === 0 ? 0 : 1
  return `${next.toFixed(precision)} ${units[unitIndex]}`
}

function formatSummaryValue(value) {
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return value.join(', ')
  if (value && typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function sourceLabel(source) {
  return source === 'current' ? '当前' : '历史'
}

function taskTypeLabel(taskType) {
  if (taskType === 'mosaic') return '镶嵌'
  if (taskType === 'batch') return '批量'
  return '单任务'
}

function shortId(value) {
  const text = String(value || '')
  if (text.length <= 12) return text
  return `${text.slice(0, 6)}...${text.slice(-4)}`
}

watch(filteredTasks, () => {
  syncSelection()
})

watch(() => props.apiBase, () => {
  void loadTasks(true)
})

onMounted(() => {
  void loadTasks(true)
})
</script>

<template>
  <section class="results-shell">
    <article class="card results-sidebar">
      <div class="results-section-head">
        <div>
          <h2>结果下载</h2>
          <p>统一查看当前成功任务与历史输出目录中的可下载产物。</p>
        </div>
        <button class="btn sub tiny" type="button" :disabled="state.loading" @click="loadTasks()">
          {{ state.loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <div class="results-filters">
        <label class="results-field full">
          <span>搜索任务</span>
          <input v-model="state.search" type="text" placeholder="标题 / job_id / batch_id / 输出目录" />
        </label>
        <label class="results-field">
          <span>结果来源</span>
          <select v-model="state.sourceFilter">
            <option value="all">全部</option>
            <option value="current">当前任务</option>
            <option value="history">历史目录</option>
          </select>
        </label>
        <label class="results-field">
          <span>任务类型</span>
          <select v-model="state.typeFilter">
            <option value="all">全部</option>
            <option value="single">单任务</option>
            <option value="batch">批量</option>
            <option value="mosaic">镶嵌</option>
          </select>
        </label>
      </div>

      <div class="results-stats">
        <div class="stat-pill">
          <strong>{{ taskStats.total }}</strong>
          <span>全部结果</span>
        </div>
        <div class="stat-pill">
          <strong>{{ taskStats.current }}</strong>
          <span>当前</span>
        </div>
        <div class="stat-pill">
          <strong>{{ taskStats.history }}</strong>
          <span>历史</span>
        </div>
      </div>

      <div v-if="state.loading" class="results-empty">
        正在读取可下载任务...
      </div>
      <div v-else-if="!state.tasks.length" class="results-empty">
        还没有可下载的处理结果。
      </div>
      <div v-else-if="!filteredTasks.length" class="results-empty">
        当前筛选条件下没有匹配任务。
      </div>
      <div v-else class="task-card-list">
        <button
          v-for="task in filteredTasks"
          :key="task.id"
          class="task-card"
          :class="{ active: task.id === state.selectedTaskId }"
          type="button"
          @click="selectTask(task)"
        >
          <div class="task-card-head">
            <strong>{{ task.title }}</strong>
            <span class="source-badge" :class="`is-${task.source}`">{{ sourceLabel(task.source) }}</span>
          </div>
          <div class="task-chip-row">
            <span class="task-chip">{{ taskTypeLabel(task.task_type) }}</span>
            <span v-if="task.job_id" class="task-chip mono">job {{ shortId(task.job_id) }}</span>
            <span v-if="task.batch_id" class="task-chip mono">batch {{ shortId(task.batch_id) }}</span>
          </div>
          <p class="task-meta">{{ formatTime(task.completed_at || task.created_at) }}</p>
          <p class="task-meta">{{ task.artifact_count }} 个产物</p>
          <p class="task-path" :title="task.output_dir">{{ task.output_dir }}</p>
        </button>
      </div>
    </article>

    <article class="card results-detail">
      <template v-if="selectedTask">
        <div class="results-section-head detail-head">
          <div>
            <h2>{{ selectedTask.title }}</h2>
            <p>{{ selectedTask.output_dir }}</p>
          </div>
          <div class="detail-actions">
            <button class="btn pri tiny" type="button" @click="downloadArchive(selectedTask)">整包 ZIP</button>
          </div>
        </div>

        <div class="detail-summary-grid">
          <div class="summary-card">
            <span>来源</span>
            <strong>{{ sourceLabel(selectedTask.source) }}</strong>
          </div>
          <div class="summary-card">
            <span>类型</span>
            <strong>{{ taskTypeLabel(selectedTask.task_type) }}</strong>
          </div>
          <div class="summary-card">
            <span>完成时间</span>
            <strong>{{ formatTime(selectedTask.completed_at || selectedTask.created_at) }}</strong>
          </div>
          <div class="summary-card">
            <span>产物数量</span>
            <strong>{{ selectedTask.artifact_count }}</strong>
          </div>
        </div>

        <div v-if="summaryEntries.length" class="summary-list">
          <div v-for="item in summaryEntries" :key="item.key" class="summary-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>

        <div class="artifact-groups">
          <section v-for="group in artifactGroups" :key="group.category" class="artifact-group">
            <div class="artifact-group-head">
              <h3>{{ group.label }}</h3>
              <span>{{ group.items.length }} 项</span>
            </div>
            <div class="artifact-list">
              <article v-for="item in group.items" :key="item.key" class="artifact-item">
                <div class="artifact-main">
                  <strong>{{ item.label }}</strong>
                  <p>{{ item.filename }}</p>
                </div>
                <div class="artifact-side">
                  <span>{{ formatSize(item.size_bytes) }}</span>
                  <div class="artifact-actions">
                    <button class="btn sub tiny" type="button" @click="downloadFile(item)">下载</button>
                    <button
                      v-if="item.previewable"
                      class="btn tiny"
                      type="button"
                      :disabled="state.previewLoading && state.previewPath === item.path"
                      @click="previewArtifact(item)"
                    >
                      {{ state.previewLoading && state.previewPath === item.path ? '预览中...' : '预览' }}
                    </button>
                  </div>
                </div>
              </article>
            </div>
          </section>
        </div>

        <section class="preview-panel">
          <div class="artifact-group-head">
            <h3>预览面板</h3>
            <span v-if="state.previewMeta">{{ state.previewMeta.width }}×{{ state.previewMeta.height }} · {{ state.previewMeta.bands }} 波段</span>
          </div>
          <div class="preview-frame">
            <img v-if="state.previewImage" :src="state.previewImage" alt="preview" />
            <p v-else class="results-empty compact">点击某个支持预览的栅格产物后，在这里查看缩略图。</p>
          </div>
        </section>
      </template>

      <div v-else class="results-empty">
        选择左侧任务后查看产物详情。
      </div>
    </article>
  </section>
</template>

<style scoped>
.results-shell {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 0.5rem;
  min-height: 0;
}

.results-sidebar,
.results-detail {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.results-section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
}

.results-section-head h2 {
  margin: 0;
  font-family: 'Teko', sans-serif;
  font-size: 1.1rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.results-section-head p {
  margin: 0.2rem 0 0;
  color: var(--muted);
  font-size: 0.74rem;
  line-height: 1.5;
}

.results-filters {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.45rem;
}

.results-field {
  display: grid;
  gap: 0.2rem;
}

.results-field.full {
  grid-column: 1 / -1;
}

.results-field span {
  color: var(--muted);
  font-size: 0.7rem;
}

.results-field input,
.results-field select {
  padding: 0.38rem 0.45rem;
  font-size: 0.75rem;
  border: 1px solid #cdd8d4;
  border-radius: 6px;
  background: #fff;
}

.results-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.4rem;
}

.stat-pill,
.summary-card {
  border: 1px solid #dbe4e1;
  border-radius: 10px;
  background: linear-gradient(180deg, #ffffff 0%, #f7fbf9 100%);
  padding: 0.55rem 0.65rem;
}

.stat-pill strong,
.summary-card strong {
  display: block;
  font-size: 0.95rem;
  color: var(--pri-dark);
}

.stat-pill span,
.summary-card span {
  display: block;
  margin-top: 0.15rem;
  color: var(--muted);
  font-size: 0.68rem;
}

.task-card-list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  min-height: 0;
  overflow-y: auto;
  padding-right: 0.1rem;
}

.task-card {
  border: 1px solid #d6dfdc;
  border-radius: 12px;
  padding: 0.7rem;
  background: #fff;
  text-align: left;
  cursor: pointer;
  display: grid;
  gap: 0.35rem;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.task-card:hover {
  border-color: #9bc4b9;
  box-shadow: 0 8px 18px rgba(15, 124, 102, 0.07);
}

.task-card.active {
  border-color: var(--pri);
  background: #f3fbf8;
  transform: translateY(-1px);
}

.task-card-head,
.artifact-group-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}

.task-card-head strong {
  font-size: 0.83rem;
  line-height: 1.45;
  color: var(--text);
}

.source-badge,
.task-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.15rem 0.45rem;
  font-size: 0.65rem;
  border: 1px solid #d7e2de;
  color: var(--muted);
  background: #f7fbf9;
  white-space: nowrap;
}

.source-badge.is-current {
  border-color: #cce3db;
  color: #0f7c66;
  background: #eaf7f2;
}

.source-badge.is-history {
  border-color: #dde3ef;
  color: #46637d;
  background: #eef4fb;
}

.task-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.task-chip.mono {
  font-family: var(--mono);
}

.task-meta {
  margin: 0;
  color: var(--muted);
  font-size: 0.7rem;
}

.task-path {
  margin: 0;
  color: #30423d;
  font-size: 0.68rem;
  line-height: 1.5;
  word-break: break-all;
}

.detail-head {
  padding-bottom: 0.15rem;
  border-bottom: 1px solid #e4ece9;
}

.detail-actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.detail-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.45rem;
}

.summary-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.4rem;
}

.summary-row {
  border: 1px solid #e2e8e6;
  border-radius: 10px;
  background: #fbfcfc;
  padding: 0.55rem 0.65rem;
}

.summary-row span {
  display: block;
  color: var(--muted);
  font-size: 0.68rem;
}

.summary-row strong {
  display: block;
  margin-top: 0.18rem;
  font-size: 0.78rem;
  line-height: 1.45;
  word-break: break-word;
}

.artifact-groups {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  min-height: 0;
}

.artifact-group {
  border: 1px solid #e2e9e6;
  border-radius: 12px;
  background: #fbfcfc;
  padding: 0.65rem;
}

.artifact-group h3 {
  margin: 0;
  font-size: 0.86rem;
}

.artifact-group-head span {
  color: var(--muted);
  font-size: 0.68rem;
}

.artifact-list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  margin-top: 0.55rem;
}

.artifact-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.65rem;
  align-items: center;
  border: 1px solid #e5ece9;
  border-radius: 10px;
  background: #fff;
  padding: 0.55rem 0.65rem;
}

.artifact-main {
  min-width: 0;
}

.artifact-main strong {
  display: block;
  font-size: 0.8rem;
}

.artifact-main p {
  margin: 0.18rem 0 0;
  color: var(--muted);
  font-size: 0.68rem;
  line-height: 1.4;
  word-break: break-all;
}

.artifact-side {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.artifact-side span {
  color: var(--muted);
  font-size: 0.68rem;
  font-family: var(--mono);
}

.artifact-actions {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.preview-panel {
  border: 1px solid #dfe7e4;
  border-radius: 12px;
  background: linear-gradient(180deg, #fbfdfc 0%, #f6faf8 100%);
  padding: 0.7rem;
}

.preview-frame {
  margin-top: 0.55rem;
  min-height: 260px;
  border: 1px dashed #ced9d4;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.8);
}

.preview-frame img {
  display: block;
  width: 100%;
  height: auto;
  object-fit: contain;
}

.results-empty {
  min-height: 120px;
  border: 1px dashed #d7dfdc;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--muted);
  background: #fbfcfc;
  padding: 1rem;
}

.results-empty.compact {
  min-height: 200px;
}

@media (max-width: 1100px) {
  .results-shell {
    grid-template-columns: 320px minmax(0, 1fr);
  }

  .detail-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .summary-list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .results-shell {
    grid-template-columns: 1fr;
  }

  .results-sidebar,
  .results-detail {
    overflow: visible;
  }

  .results-stats,
  .detail-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .results-filters,
  .results-stats,
  .detail-summary-grid {
    grid-template-columns: 1fr;
  }

  .artifact-item {
    grid-template-columns: 1fr;
  }

  .artifact-side {
    justify-content: flex-start;
  }
}
</style>
