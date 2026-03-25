<template>
  <div class="batch-manager">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <span class="toolbar-title">处理流程编辑器</span>
        <span class="toolbar-hint">将节点拖入画布，连线构建处理管线</span>
      </div>
      <div class="toolbar-right">
        <select v-model="state.priority" class="priority-select">
          <option value="high">高优先级</option>
          <option value="medium">中优先级</option>
          <option value="low">低优先级</option>
        </select>
        <div class="btn-divider"></div>
        <button class="btn btn-ghost" @click="confirmResetCanvas" title="清除画布">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
          </svg>
          重置画布
        </button>
        <button class="btn btn-primary" @click="submitTask" :disabled="state.submitting">
          <svg v-if="!state.submitting" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
          </svg>
          {{ state.submitting ? '提交中...' : '提交任务' }}
        </button>
      </div>
    </div>

    <div class="main-area">
      <!-- 左侧节点面板 -->
      <div class="node-palette">
        <div class="palette-title">可用节点</div>
        <div class="palette-hint">拖拽到画布</div>
        <div v-for="nt in nodeTypes" :key="nt.type" class="palette-item"
          draggable="true" @dragstart="onDragStart($event, nt)">
          <span class="palette-icon" v-html="nt.iconSvg"></span>
          <div>
            <div class="palette-name">{{ nt.label }}</div>
            <div class="palette-desc">{{ nt.desc }}</div>
          </div>
        </div>
      </div>

      <!-- 中间画布 -->
      <div class="canvas-wrapper" @drop="onDrop" @dragover.prevent>
        <VueFlow
          v-model:nodes="state.nodes"
          v-model:edges="state.edges"
          :node-types="customNodeTypes"
          :default-zoom="0.9"
          :min-zoom="0.3"
          :max-zoom="2"
          fit-view-on-init
          @node-click="onNodeClick"
          @pane-click="closeSidePanel"
          @connect="onConnect"
          @edges-change="onEdgesChange"
          @nodes-change="onNodesChange"
          class="vue-flow-canvas"
        >
          <Background pattern-color="#e5e7eb" :gap="20" />
          <MiniMap :node-color="miniMapColor" :node-stroke-width="2" style="background:#f9fafb" />
        </VueFlow>
        <!-- 自定义缩放控件 -->
        <div class="canvas-controls">
          <button class="ctrl-btn" @click="vfZoomIn()" title="放大">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              <line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>
            </svg>
          </button>
          <button class="ctrl-btn" @click="vfZoomOut()" title="缩小">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              <line x1="8" y1="11" x2="14" y2="11"/>
            </svg>
          </button>
          <button class="ctrl-btn" @click="vfFitView()" title="适应画布">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- 右侧面板 -->
      <div class="right-panel">
        <!-- 侧边配置面板（滑入覆盖队列） -->
        <transition name="slide-panel">
          <div v-if="state.showSidePanel" class="side-panel">
            <div class="side-panel-header">
              <span class="side-panel-title">{{ sidePanelTitle }}</span>
              <button class="close-btn" @click="closeSidePanel">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
            <div class="side-panel-body">

              <!-- DataDirNode 配置 -->
              <template v-if="state.selectedNode?.type === 'datadir'">
                <div class="form-group">
                  <label>数据根目录 <span class="required">*</span></label>
                  <div class="path-input-row">
                    <input v-model="state.editingParams.root_dir" placeholder="选择包含多个场景的根目录" class="form-input" readonly />
                    <button class="btn-pick" @click="pickPath('root_dir')">浏览</button>
                  </div>
                  <div class="form-hint">每个子文件夹将作为一个独立的遥感影像场景</div>
                </div>
                <!-- 场景列表 -->
                <div v-if="state.editingParams.scenes?.length" class="scene-list-panel">
                  <div class="scene-list-header">
                    <span>发现 {{ state.editingParams.scenes.length }} 个场景</span>
                    <div class="scene-list-actions">
                      <button class="btn-link" @click="selectAllScenes">全选</button>
                      <button class="btn-link" @click="selectNoneScenes">清空</button>
                    </div>
                  </div>
                  <div class="scene-list">
                    <label v-for="scene in state.editingParams.scenes" :key="scene.path" class="scene-item">
                      <input type="checkbox" :value="scene.name" v-model="state.editingParams.selectedScenes" />
                      <div class="scene-item-info">
                        <span class="scene-name">{{ scene.name }}</span>
                        <span class="shp-badge" :class="scene.has_shp ? 'has' : 'none'">
                          {{ scene.has_shp ? '有 SHP' : '无 SHP' }}
                        </span>
                      </div>
                    </label>
                  </div>
                </div>
                <div v-else-if="state.editingParams.root_dir" class="form-tip">
                  保存后将自动扫描该目录下的子文件夹
                </div>
              </template>

              <!-- InputNode 配置（单场景模式） -->
              <template v-else-if="state.selectedNode?.type === 'input' && !state.editingParams.scenes?.length">
                <div class="form-group">
                  <label>场景名称</label>
                  <input v-model="state.editingParams.scene_name" placeholder="如 LC08_L1TP_..." class="form-input" />
                </div>
                <div class="form-group">
                  <label>波段文件目录 <span class="required">*</span></label>
                  <div class="path-input-row">
                    <input v-model="state.editingParams.band_dir" placeholder="选择或输入目录路径" class="form-input" readonly />
                    <button class="btn-pick" @click="pickPath('band_dir')">浏览</button>
                  </div>
                </div>
                <div class="form-group">
                  <label>MTL 元数据文件（可选）</label>
                  <div class="path-input-row">
                    <input v-model="state.editingParams.mtl_file" placeholder="如 *_MTL.txt" class="form-input" />
                    <button class="btn-pick" @click="pickPath('mtl_file')">浏览</button>
                  </div>
                </div>
                <div class="form-group">
                  <label>QA 波段文件（可选）</label>
                  <input v-model="state.editingParams.qa_band" placeholder="如 *_QA_PIXEL.TIF" class="form-input" />
                </div>
              </template>

              <!-- InputNode 配置（批量场景模式） -->
              <template v-else-if="state.selectedNode?.type === 'input' && state.editingParams.scenes?.length">
                <div class="form-group">
                  <label>场景列表（来自数据目录）</label>
                  <div class="scene-list-header" style="margin-bottom:6px">
                    <span>共 {{ state.editingParams.scenes.length }} 个场景</span>
                    <div class="scene-list-actions">
                      <button class="btn-link" @click="selectAllScenes">全选</button>
                      <button class="btn-link" @click="selectNoneScenes">清空</button>
                    </div>
                  </div>
                  <div class="scene-list">
                    <label v-for="scene in state.editingParams.scenes" :key="scene.path" class="scene-item">
                      <input type="checkbox" :value="scene.name" v-model="state.editingParams.selectedScenes" />
                      <div class="scene-item-info">
                        <span class="scene-name">{{ scene.name }}</span>
                        <span class="shp-badge" :class="scene.has_shp ? 'has' : 'none'">
                          {{ scene.has_shp ? '有 SHP' : '无 SHP' }}
                        </span>
                      </div>
                    </label>
                  </div>
                </div>
              </template>

              <!-- ConditionalNode：只读说明 -->
              <template v-else-if="state.selectedNode?.type === 'conditional'">
                <div class="form-tip">
                  <strong>SHP 文件检测逻辑：</strong><br><br>
                  检测每个遥感影像目录下是否存在 <code>shp/</code> 文件夹，且该文件夹中包含 .shp 文件。<br><br>
                  · 若存在 → 连接 <strong>是</strong> 端口，自动使用该 SHP 进行裁剪<br>
                  · 若不存在 → 连接 <strong>否</strong> 端口，跳过裁剪步骤<br><br>
                  将 <strong>是</strong> 出口连接到 <em>区域裁剪</em> 节点，<strong>否</strong> 出口连接到下一步骤。
                </div>
              </template>

              <!-- AtmosphericNode 配置 -->
              <template v-else-if="state.selectedNode?.type === 'atmospheric'">
                <div class="form-group">
                  <label>大气校正方法</label>
                  <div class="radio-group">
                    <label class="radio-label">
                      <input type="radio" v-model="state.editingParams.method" value="DOS" />
                      DOS（暗目标法，推荐）
                    </label>
                    <label class="radio-label">
                      <input type="radio" v-model="state.editingParams.method" value="6S" />
                      6S（辐射传输，需 Py6S）
                    </label>
                  </div>
                </div>
                <div class="form-group">
                  <label class="checkbox-label">
                    <input type="checkbox" v-model="state.editingParams.apply_cloud_mask" />
                    启用云掩膜（需要 QA 波段）
                  </label>
                </div>
              </template>

              <!-- ClipNode 配置 -->
              <template v-else-if="state.selectedNode?.type === 'clip'">
                <div class="form-tip">选择矢量文件或手动输入经纬度范围（二选一）。若使用 SHP 检测节点，SHP 路径将自动填充。</div>
                <div class="form-group" style="margin-top:10px">
                  <label>矢量文件路径（.shp）</label>
                  <div class="path-input-row">
                    <input v-model="state.editingParams.clip_shapefile" placeholder="Shapefile 路径（SHP检测自动填充）" class="form-input" />
                    <button class="btn-pick" @click="pickPath('clip_shapefile')">浏览</button>
                  </div>
                </div>
                <div class="form-divider">— 或 —</div>
                <div class="form-group">
                  <label>经纬度范围</label>
                  <input v-model="state.editingParams.clip_extent" placeholder="minLon,minLat,maxLon,maxLat" class="form-input" />
                  <div class="form-hint">例如：116.3,39.8,116.6,40.1</div>
                </div>
              </template>

              <!-- SynthesisNode 配置 -->
              <template v-else-if="state.selectedNode?.type === 'synthesis'">
                <div class="form-group">
                  <label>选择指数/合成色（可多选）</label>
                  <div class="composite-grid">
                    <div v-for="group in compositeGroups" :key="group.label" class="composite-group">
                      <div class="group-label">{{ group.label }}</div>
                      <label v-for="c in group.items" :key="c.value" class="checkbox-label">
                        <input type="checkbox" :value="c.value" v-model="state.editingParams.composites" />
                        {{ c.label }}
                      </label>
                    </div>
                  </div>
                </div>
                <div class="form-group">
                  <label>自定义指数（可选）</label>
                  <input v-model="state.editingParams.custom_name" placeholder="指数名称，如 MyIndex" class="form-input" />
                  <input v-model="state.editingParams.custom_formula" placeholder="公式，如 (B5-B4)/(B5+B4)" class="form-input" style="margin-top:6px" />
                  <div class="form-hint">支持 B1-B11 及 abs/sqrt/log/exp/clip</div>
                </div>
              </template>

              <!-- OutputNode 配置 -->
              <template v-else-if="state.selectedNode?.type === 'output'">
                <div class="form-group">
                  <label>输出根目录 <span class="required">*</span></label>
                  <div class="path-input-row">
                    <input v-model="state.editingParams.output_dir" placeholder="选择输出目录" class="form-input" readonly />
                    <button class="btn-pick" @click="pickPath('output_dir')">浏览</button>
                  </div>
                  <div class="form-hint">批量模式下每个场景会在此目录下创建同名子目录</div>
                </div>
              </template>

              <!-- RadiometricNode：只读 -->
              <template v-else-if="state.selectedNode?.type === 'radiometric'">
                <div class="form-tip">
                  辐射定标为必需步骤，自动执行：<br><br>
                  1. DN → 辐亮度（L = ML×DN + AL）<br>
                  2. 辐亮度 → TOA 反射率<br><br>
                  无需手动配置。
                </div>
              </template>
            </div>
            <div class="side-panel-footer"
              v-if="!['radiometric','conditional'].includes(state.selectedNode?.type)">
              <button class="btn btn-primary" @click="saveNodeParams">保存</button>
              <button class="btn btn-secondary" @click="closeSidePanel">取消</button>
            </div>
          </div>
        </transition>

        <!-- 任务队列 -->
        <div class="queue-panel" :class="{ dimmed: state.showSidePanel }">
          <div class="queue-header">
            <span class="queue-title">任务队列</span>
            <div class="queue-stats">
              <span class="stat running">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                {{ state.queueStats.running }}
              </span>
              <span class="stat queued">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                {{ state.queueStats.queued }}
              </span>
              <span class="stat completed">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                {{ state.queueStats.completed }}
              </span>
              <span v-if="state.queueStats.failed > 0" class="stat failed">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                {{ state.queueStats.failed }}
              </span>
            </div>
            <button v-if="state.taskQueue.length > 0" class="btn-clear-queue" @click="clearQueue" title="取消所有等待中的任务">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/>
              </svg>
              清空
            </button>
          </div>
          <div v-if="state.taskQueue.length === 0" class="queue-empty">
            暂无任务<br><span>提交任务后显示</span>
          </div>
          <div v-else class="queue-list">
            <div v-for="job in state.taskQueue" :key="job.job_id" class="queue-item" :data-status="job.status">
              <div class="queue-item-header">
                <span class="queue-scene" :title="job.scene_name">{{ job.scene_name || '未命名' }}</span>
                <span class="status-badge" :class="job.status">{{ statusLabel[job.status] || job.status }}</span>
              </div>
              <div class="queue-progress-bar">
                <div class="queue-progress-fill" :style="{ width: job.progress + '%' }" :class="job.status"></div>
              </div>
              <div class="queue-item-footer">
                <span class="progress-text">{{ job.progress }}%</span>
                <span class="priority-text" :class="job.priority">{{ priorityLabel[job.priority] }}</span>
                <button v-if="['queued','pending','paused'].includes(job.status)"
                  class="btn-cancel" @click="cancelJob(job.job_id)">取消</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 路径选择器 -->
    <div v-if="state.showPicker" class="picker-overlay" @click.self="state.showPicker = false">
      <div class="picker-dialog">
        <div class="picker-header">
          <span>选择路径</span>
          <button @click="state.showPicker = false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="picker-breadcrumb">
          <button v-for="(seg, i) in state.pickerBreadcrumb" :key="i"
            @click="navigatePicker(i)" class="breadcrumb-btn">{{ seg }}</button>
        </div>
        <div class="picker-list">
          <div v-for="item in state.pickerItems" :key="item.path"
            class="picker-item dir" @click="onPickerItemClick(item)">
            <span class="picker-item-icon">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
            </span>
            <span>{{ item.name }}</span>
          </div>
          <div v-if="state.pickerItems.length === 0" class="picker-empty">空目录</div>
        </div>
        <div class="picker-footer">
          <span class="picker-current">{{ state.pickerCurrentPath }}</span>
          <button class="btn btn-primary" @click="confirmPick">选择此目录</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, computed, onMounted, onUnmounted, markRaw } from 'vue'
import { VueFlow, applyEdgeChanges, applyNodeChanges, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

import DataDirNode    from './flow-nodes/DataDirNode.vue'
import InputNode      from './flow-nodes/InputNode.vue'
import RadiometricNode from './flow-nodes/RadiometricNode.vue'
import AtmosphericNode from './flow-nodes/AtmosphericNode.vue'
import ClipNode       from './flow-nodes/ClipNode.vue'
import ConditionalNode from './flow-nodes/ConditionalNode.vue'
import SynthesisNode  from './flow-nodes/SynthesisNode.vue'
import OutputNode     from './flow-nodes/OutputNode.vue'

const props = defineProps(['apiBase'])
const emit = defineEmits(['toast'])

const { zoomIn: vfZoomIn, zoomOut: vfZoomOut, fitView: vfFitView } = useVueFlow()

const customNodeTypes = {
  datadir:      markRaw(DataDirNode),
  input:        markRaw(InputNode),
  radiometric:  markRaw(RadiometricNode),
  atmospheric:  markRaw(AtmosphericNode),
  clip:         markRaw(ClipNode),
  conditional:  markRaw(ConditionalNode),
  synthesis:    markRaw(SynthesisNode),
  output:       markRaw(OutputNode),
}

const ICON_CLOUD  = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10h-1.26A8 8 0 109 20h9a5 5 0 000-10z"/></svg>`
const ICON_CROP   = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6.13 1L6 16a2 2 0 002 2h15"/><path d="M1 6.13L16 6a2 2 0 012 2v15"/></svg>`
const ICON_LAYERS = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>`
const ICON_COND   = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>`

const nodeTypes = [
  { type: 'atmospheric', iconSvg: ICON_CLOUD,  label: '大气校正',  desc: 'DOS / 6S' },
  { type: 'conditional', iconSvg: ICON_COND,   label: 'SHP 检测',  desc: '条件判断裁剪' },
  { type: 'clip',        iconSvg: ICON_CROP,   label: '区域裁剪',  desc: '矢量/范围裁剪' },
  { type: 'synthesis',   iconSvg: ICON_LAYERS, label: '合成指数',  desc: '23种指数/合成' },
]

function createInitialNodes() {
  return [
    { id: 'datadir-1',     type: 'datadir',     position: { x: 40,  y: 120 }, data: { root_dir: '', scenes: [], selectedScenes: [] }, deletable: false },
    { id: 'input-1',       type: 'input',       position: { x: 280, y: 120 }, data: { band_dir: '', scene_name: '', mtl_file: '', qa_band: '', scenes: [], selectedScenes: [] }, deletable: false },
    { id: 'radiometric-1', type: 'radiometric',  position: { x: 510, y: 120 }, data: {}, deletable: false },
    { id: 'output-1',      type: 'output',       position: { x: 750, y: 120 }, data: { output_dir: '' }, deletable: false },
  ]
}
function createInitialEdges() {
  return [
    { id: 'e-dd-in',   source: 'datadir-1',    target: 'input-1',       animated: false },
    { id: 'e-in-rad',  source: 'input-1',      target: 'radiometric-1', animated: false },
    { id: 'e-rad-out', source: 'radiometric-1', target: 'output-1',     animated: false },
  ]
}

const state = reactive({
  nodes: createInitialNodes(),
  edges: createInitialEdges(),
  selectedNode: null,
  showSidePanel: false,
  editingParams: {},
  priority: 'medium',
  submitting: false,
  taskQueue: [],
  queueStats: { total: 0, running: 0, queued: 0, completed: 0, failed: 0 },
  pollingTimer: null,
  showPicker: false,
  pickerField: '',
  pickerCurrentPath: '',
  pickerBreadcrumb: ['根目录'],
  pickerItems: [],
})

const sidePanelTitle = computed(() => {
  const map = {
    datadir:     '数据目录配置',
    input:       '场景数据配置',
    radiometric: '辐射定标（只读）',
    atmospheric: '大气校正配置',
    conditional: 'SHP 检测（只读）',
    clip:        '区域裁剪配置',
    synthesis:   '合成指数配置',
    output:      '输出配置',
  }
  return map[state.selectedNode?.type] || '节点配置'
})

const statusLabel = {
  queued: '排队中', pending: '等待', running: '运行中',
  success: '已完成', failed: '失败', cancelled: '已取消', paused: '已暂停',
}
const priorityLabel = { high: '高', medium: '中', low: '低' }

const compositeGroups = [
  { label: 'RGB 合成', items: [
    { value: 'true_color', label: '真彩色' }, { value: 'false_color', label: '假彩色' },
    { value: 'agriculture', label: '农业' }, { value: 'urban', label: '城市' },
    { value: 'natural_color', label: '自然彩色' }, { value: 'swir', label: '短波红外' },
  ]},
  { label: '植被指数', items: [
    { value: 'ndvi', label: 'NDVI' }, { value: 'evi', label: 'EVI' },
    { value: 'savi', label: 'SAVI' }, { value: 'msavi', label: 'MSAVI' },
    { value: 'arvi', label: 'ARVI' }, { value: 'rvi', label: 'RVI' },
  ]},
  { label: '水体指数', items: [
    { value: 'ndwi', label: 'NDWI' }, { value: 'mndwi', label: 'MNDWI' },
    { value: 'awei', label: 'AWEI' }, { value: 'wri', label: 'WRI' },
  ]},
  { label: '建筑/城市', items: [
    { value: 'ndbi', label: 'NDBI' }, { value: 'ibi', label: 'IBI' },
    { value: 'ndbai', label: 'NDBaI' }, { value: 'ui', label: 'UI' },
  ]},
  { label: '其他', items: [
    { value: 'nbr', label: 'NBR' }, { value: 'bsi', label: 'BSI' }, { value: 'ndsi', label: 'NDSI' },
  ]},
]

// ─── 场景列表操作 ─────────────────────────────────────────
function selectAllScenes() {
  if (state.editingParams.scenes) {
    state.editingParams.selectedScenes = state.editingParams.scenes.map(s => s.name)
  }
}
function selectNoneScenes() {
  state.editingParams.selectedScenes = []
}

// ─── 画布交互 ─────────────────────────────────────────────
let dragNodeType = null
let nodeCounter = 100

function onDragStart(event, nt) {
  dragNodeType = nt.type
  event.dataTransfer.effectAllowed = 'move'
}

function onDrop(event) {
  if (!dragNodeType) return
  const rect = event.currentTarget.getBoundingClientRect()
  const id = `${dragNodeType}-${++nodeCounter}`
  const defaults = {
    atmospheric: { method: 'DOS', apply_cloud_mask: false },
    conditional: {},
    clip:        { clip_extent: '', clip_shapefile: '' },
    synthesis:   { composites: [], custom_formula: '', custom_name: '' },
  }
  state.nodes.push({
    id, type: dragNodeType,
    position: { x: event.clientX - rect.left - 75, y: event.clientY - rect.top - 40 },
    data: defaults[dragNodeType] || {},
    deletable: true,
  })
  dragNodeType = null
}

function onNodeClick({ node }) {
  state.selectedNode = node
  state.editingParams = JSON.parse(JSON.stringify(node.data))

  // InputNode：若上游连接了 DataDirNode，直接注入其场景列表
  if (node.type === 'input') {
    const upstreamEdge = state.edges.find(e => e.target === node.id)
    const dataDirNode = upstreamEdge
      ? state.nodes.find(n => n.id === upstreamEdge.source && n.type === 'datadir')
      : null
    if (dataDirNode?.data.scenes?.length) {
      state.editingParams.scenes = dataDirNode.data.scenes
      state.editingParams.selectedScenes =
        node.data.selectedScenes?.length
          ? node.data.selectedScenes
          : dataDirNode.data.scenes.map(s => s.name)
    }
  }

  state.showSidePanel = true
}

function onConnect(params) {
  const id = `e-${params.source}-${params.sourceHandle || 'out'}-${params.target}-${params.targetHandle || 'in'}`
  if (!state.edges.find(e => e.id === id)) {
    state.edges.push({ ...params, id })
  }
}

function onEdgesChange(changes) {
  state.edges = applyEdgeChanges(changes, state.edges)
}

function onNodesChange(changes) {
  // 仅允许移动和选中变更；deletable:false 的节点由 Vue Flow 内部过滤
  state.nodes = applyNodeChanges(changes, state.nodes)
}

function closeSidePanel() {
  state.showSidePanel = false
  state.selectedNode = null
  state.editingParams = {}
}

async function saveNodeParams() {
  if (!state.selectedNode) return
  const node = state.nodes.find(n => n.id === state.selectedNode.id)
  if (node) {
    Object.assign(node.data, state.editingParams)
    // DataDirNode 保存后自动扫描并传递到 InputNode
    if (node.type === 'datadir' && node.data.root_dir) {
      await scanAndPropagateScenes(node.id)
    }
    // InputNode 保存时把 selectedScenes 同步回上游 DataDirNode
    if (node.type === 'input') {
      const upstreamEdge = state.edges.find(e => e.target === node.id)
      const dataDirNode = upstreamEdge
        ? state.nodes.find(n => n.id === upstreamEdge.source && n.type === 'datadir')
        : null
      if (dataDirNode) {
        dataDirNode.data.selectedScenes = state.editingParams.selectedScenes || []
      }
    }
  }
  closeSidePanel()
}

async function scanAndPropagateScenes(dataDirNodeId) {
  const dataDirNode = state.nodes.find(n => n.id === dataDirNodeId)
  if (!dataDirNode?.data.root_dir) return
  try {
    const resp = await fetch(`${props.apiBase}/filesystem/scan_scenes?path=${encodeURIComponent(dataDirNode.data.root_dir)}`)
    if (!resp.ok) return
    const data = await resp.json()
    dataDirNode.data.scenes = data.scenes
    dataDirNode.data.selectedScenes = data.scenes.map(s => s.name) // 默认全选
    // 找到 DataDirNode 的直接下游 InputNode
    const edge = state.edges.find(e => e.source === dataDirNodeId)
    if (edge) {
      const inputNode = state.nodes.find(n => n.id === edge.target && n.type === 'input')
      if (inputNode) {
        inputNode.data.scenes = data.scenes
        inputNode.data.selectedScenes = data.scenes.map(s => s.name)
      }
    }
  } catch (_) {}
}

function confirmResetCanvas() {
  if (state.nodes.some(n => n.data && Object.values(n.data).some(v => v && v !== '' && !Array.isArray(v)))) {
    if (!confirm('确认重置画布？所有节点配置将被清空。')) return
  }
  resetCanvas()
}

function resetCanvas() {
  state.nodes = createInitialNodes()
  state.edges = createInitialEdges()
  closeSidePanel()
  nodeCounter = 100
}

function miniMapColor(node) {
  const map = {
    datadir:     '#a5b4fc',
    input:       '#93c5fd',
    radiometric: '#9ca3af',
    atmospheric: '#6ee7b7',
    conditional: '#fcd34d',
    clip:        '#fed7aa',
    synthesis:   '#d8b4fe',
    output:      '#99f6e4',
  }
  return map[node.type] || '#ccc'
}

// ─── 提交任务 ─────────────────────────────────────────────
function isFlowConnected() {
  const startNode = state.nodes.find(n => n.type === 'datadir') || state.nodes.find(n => n.type === 'input')
  const outputNode = state.nodes.find(n => n.type === 'output')
  if (!startNode || !outputNode) return false
  const visited = new Set()
  const queue = [startNode.id]
  while (queue.length) {
    const cur = queue.shift()
    if (cur === outputNode.id) return true
    if (visited.has(cur)) continue
    visited.add(cur)
    state.edges.filter(e => e.source === cur).forEach(e => queue.push(e.target))
  }
  return false
}

async function submitTask() {
  const outputNode = state.nodes.find(n => n.type === 'output')
  if (!outputNode?.data.output_dir) {
    emit('toast', { type: 'error', message: '请配置输出节点的输出目录' })
    return
  }
  if (!isFlowConnected()) {
    emit('toast', { type: 'error', message: '流程未完整连接，请确保有完整路径到输出节点' })
    return
  }

  // 序列化图结构发送给后端，由后端拓扑排序后决定执行步骤
  const batchName = `graph_batch_${Date.now()}`
  const payload = {
    batch_name: batchName,
    nodes: state.nodes.map(n => ({ id: n.id, type: n.type, data: n.data })),
    edges: state.edges.map(e => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle ?? null,
      targetHandle: e.targetHandle ?? null,
    })),
    priority: state.priority,
    auto_retry: true,
    max_retries: 3,
  }

  state.submitting = true
  try {
    const resp = await fetch(`${props.apiBase}/batch/submit_graph`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || '提交失败')
    }
    const result = await resp.json()
    emit('toast', { type: 'ok', message: `已提交 ${result.total_jobs} 个任务到队列` })
    await fetchQueue()
  } catch (e) {
    emit('toast', { type: 'error', message: e.message })
  } finally {
    state.submitting = false
  }
}

// ─── 队列轮询 ─────────────────────────────────────────────
async function fetchQueue() {
  try {
    const resp = await fetch(`${props.apiBase}/tasks/queue`)
    if (!resp.ok) return
    const data = await resp.json()
    state.taskQueue = data.jobs || []
    state.queueStats = { total: data.total||0, running: data.running||0, queued: data.queued||0, completed: data.completed||0, failed: data.failed||0 }
  } catch (_) {}
}

async function cancelJob(jobId) {
  try {
    await fetch(`${props.apiBase}/batch/job/${jobId}/cancel`, { method: 'POST' })
    await fetchQueue()
  } catch (_) {}
}

async function clearQueue() {
  const cancellable = state.taskQueue.filter(j => ['queued', 'pending', 'paused'].includes(j.status))
  if (cancellable.length === 0) return
  if (!confirm(`确认取消 ${cancellable.length} 个等待中的任务？`)) return
  await Promise.all(cancellable.map(j => cancelJob(j.job_id)))
}

onMounted(() => { fetchQueue(); state.pollingTimer = setInterval(fetchQueue, 3000) })
onUnmounted(() => clearInterval(state.pollingTimer))

// ─── 路径选择器 ───────────────────────────────────────────
async function pickPath(field) {
  state.pickerField = field
  state.pickerCurrentPath = ''
  state.pickerBreadcrumb = ['根目录']
  await loadPickerDir('')
  state.showPicker = true
}

async function loadPickerDir(path) {
  try {
    const resp = await fetch(`${props.apiBase}/filesystem/list_dirs?path=${encodeURIComponent(path)}`)
    if (!resp.ok) return
    const data = await resp.json()
    state.pickerCurrentPath = data.current || path
    state.pickerItems = (data.directories || [])
    if (state.pickerCurrentPath) {
      const segs = state.pickerCurrentPath.replace(/\\/g, '/').split('/').filter(Boolean)
      state.pickerBreadcrumb = ['根目录', ...segs]
    } else {
      state.pickerBreadcrumb = ['根目录']
    }
  } catch (_) {}
}

async function onPickerItemClick(item) {
  await loadPickerDir(item.path)
}

async function navigatePicker(index) {
  if (index === 0) {
    await loadPickerDir('')
  } else {
    const segs = state.pickerBreadcrumb.slice(1, index + 1)
    await loadPickerDir(segs.join('/'))
  }
}

function confirmPick() {
  if (state.selectedNode) state.editingParams[state.pickerField] = state.pickerCurrentPath
  state.showPicker = false
}
</script>

<style scoped>
.batch-manager {
  display: flex; flex-direction: column;
  height: 100%; min-height: 0; font-family: inherit; overflow: hidden;
}

/* ── 工具栏 ── */
.toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px; background: #fff; border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0; gap: 12px;
}
.toolbar-left { display: flex; align-items: baseline; gap: 12px; }
.toolbar-title { font-size: 14px; font-weight: 700; color: #111827; }
.toolbar-hint { font-size: 12px; color: #9ca3af; }
.toolbar-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.priority-select { padding: 5px 8px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; background: #fff; cursor: pointer; }
.btn-divider { width: 1px; height: 20px; background: #e5e7eb; margin: 0 2px; }
.btn-ghost {
  display: flex; align-items: center; gap: 5px; white-space: nowrap;
  padding: 6px 11px; border-radius: 6px; font-size: 13px; cursor: pointer;
  border: 1px solid #d1d5db; background: #fff; color: #374151; font-weight: 500;
  transition: background 0.15s, border-color 0.15s;
}
.btn-ghost:hover { background: #f9fafb; border-color: #9ca3af; }
.btn { display: flex; align-items: center; gap: 5px; white-space: nowrap; padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; border: none; font-weight: 500; transition: background 0.15s; }
.btn-primary { background: #2563eb; color: #fff; }
.btn-primary:hover { background: #1d4ed8; }
.btn-primary:disabled { background: #93c5fd; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
.btn-secondary:hover { background: #e5e7eb; }

/* ── 主体 ── */
.main-area { display: flex; flex: 1; min-height: 0; overflow: hidden; }

/* ── 左侧节点面板 ── */
.node-palette {
  width: 145px; flex-shrink: 0; background: #f9fafb;
  border-right: 1px solid #e5e7eb; padding: 10px 8px; overflow-y: auto;
}
.palette-title { font-size: 10px; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 2px; }
.palette-hint { font-size: 10px; color: #9ca3af; margin-bottom: 8px; }
.palette-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 8px;
  border-radius: 8px; margin-bottom: 5px; background: #fff;
  border: 1px solid #e5e7eb; cursor: grab; user-select: none;
  transition: box-shadow 0.15s, border-color 0.15s;
}
.palette-item:hover { border-color: #93c5fd; box-shadow: 0 2px 6px rgba(0,0,0,.08); }
.palette-item:active { cursor: grabbing; }
.palette-icon { display: flex; align-items: center; color: #374151; flex-shrink: 0; }
.palette-name { font-size: 12px; font-weight: 600; color: #111827; }
.palette-desc { font-size: 10px; color: #6b7280; }

/* ── 画布 ── */
.canvas-wrapper { flex: 1; min-width: 0; background: #f3f4f6; position: relative; overflow: hidden; }
.vue-flow-canvas { width: 100%; height: 100%; }

/* 自定义缩放控件 */
.canvas-controls {
  position: absolute; left: 12px; bottom: 12px; z-index: 5;
  display: flex; flex-direction: column; gap: 2px;
  background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
  padding: 4px; box-shadow: 0 2px 8px rgba(0,0,0,.08);
}
.ctrl-btn {
  width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
  border: none; background: none; cursor: pointer; border-radius: 5px; color: #374151;
  transition: background 0.15s;
}
.ctrl-btn:hover { background: #f3f4f6; }

/* 消除 Vue Flow 节点 wrapper 自带的边框/背景，避免双层框 */
:deep(.vue-flow__node) {
  background: transparent;
  border: none;
  padding: 0;
  box-shadow: none;
  border-radius: 0;
}

/* ── 右侧面板容器 ── */
.right-panel {
  width: 270px; flex-shrink: 0; position: relative;
  border-left: 1px solid #e5e7eb; display: flex; flex-direction: column;
}

/* ── 侧边配置面板 ── */
.side-panel {
  position: absolute; inset: 0; z-index: 10; background: #fff;
  display: flex; flex-direction: column;
  box-shadow: -4px 0 16px rgba(0,0,0,.1);
}
.slide-panel-enter-active, .slide-panel-leave-active { transition: transform 0.22s ease, opacity 0.22s ease; }
.slide-panel-enter-from, .slide-panel-leave-to { transform: translateX(100%); opacity: 0; }
.side-panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; background: #f9fafb; border-bottom: 1px solid #e5e7eb; flex-shrink: 0;
}
.side-panel-title { font-size: 13px; font-weight: 600; color: #111827; }
.close-btn { background: none; border: none; cursor: pointer; display: flex; align-items: center; color: #6b7280; padding: 4px; border-radius: 4px; }
.close-btn:hover { background: #f3f4f6; color: #374151; }
.side-panel-body { flex: 1; overflow-y: auto; padding: 12px; }
.side-panel-footer { padding: 8px 12px; border-top: 1px solid #e5e7eb; display: flex; gap: 8px; flex-shrink: 0; }

/* 表单 */
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 4px; }
.required { color: #dc2626; }
.form-input {
  width: 100%; padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px;
  font-size: 12px; background: #fff; box-sizing: border-box; transition: border-color 0.15s;
}
.form-input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,.15); }
.path-input-row { display: flex; gap: 6px; }
.path-input-row .form-input { flex: 1; }
.btn-pick { padding: 5px 9px; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; font-size: 12px; cursor: pointer; white-space: nowrap; flex-shrink: 0; }
.btn-pick:hover { background: #e5e7eb; }
.form-hint { font-size: 10px; color: #9ca3af; margin-top: 3px; }
.form-tip { font-size: 12px; color: #6b7280; line-height: 1.8; background: #f9fafb; padding: 10px; border-radius: 6px; border: 1px solid #e5e7eb; }
.form-tip code { background: #e5e7eb; padding: 1px 4px; border-radius: 3px; font-size: 11px; }
.form-tip strong { color: #374151; }
.form-tip em { color: #3b82f6; font-style: normal; }
.form-divider { text-align: center; font-size: 11px; color: #9ca3af; margin: 8px 0; }
.radio-group { display: flex; flex-direction: column; gap: 6px; }
.radio-label, .checkbox-label { display: flex; align-items: center; gap: 7px; font-size: 12px; color: #374151; cursor: pointer; }
.composite-grid { display: flex; flex-direction: column; gap: 8px; }
.group-label { font-size: 10px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 3px; }
.composite-group .checkbox-label { margin-bottom: 2px; }

/* 场景列表 */
.scene-list-panel { border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; }
.scene-list-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 10px; background: #f9fafb; border-bottom: 1px solid #e5e7eb;
  font-size: 12px; color: #6b7280;
}
.scene-list-actions { display: flex; gap: 8px; }
.btn-link { background: none; border: none; font-size: 11px; color: #3b82f6; cursor: pointer; padding: 0; }
.btn-link:hover { text-decoration: underline; }
.scene-list { max-height: 220px; overflow-y: auto; }
.scene-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 10px;
  border-bottom: 1px solid #f3f4f6; cursor: pointer;
}
.scene-item:last-child { border-bottom: none; }
.scene-item:hover { background: #f9fafb; }
.scene-item input { cursor: pointer; flex-shrink: 0; }
.scene-item-info { display: flex; align-items: center; gap: 6px; min-width: 0; }
.scene-name { font-size: 11px; color: #374151; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.shp-badge { font-size: 10px; padding: 1px 5px; border-radius: 3px; white-space: nowrap; flex-shrink: 0; }
.shp-badge.has { background: #dcfce7; color: #16a34a; }
.shp-badge.none { background: #f3f4f6; color: #9ca3af; }

/* ── 任务队列 ── */
.queue-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; transition: opacity 0.2s; }
.queue-panel.dimmed { opacity: 0.25; pointer-events: none; }
.queue-header { padding: 8px 12px; border-bottom: 1px solid #e5e7eb; flex-shrink: 0; display: flex; align-items: center; gap: 6px; }
.queue-title { font-size: 13px; font-weight: 700; color: #111827; flex: 1; }
.btn-clear-queue {
  display: flex; align-items: center; gap: 4px;
  padding: 3px 8px; background: none; border: 1px solid #e5e7eb;
  border-radius: 4px; font-size: 11px; color: #9ca3af; cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.btn-clear-queue:hover { background: #fee2e2; border-color: #fca5a5; color: #dc2626; }
.queue-stats { display: flex; gap: 8px; }
.stat { font-size: 11px; font-weight: 600; display: flex; align-items: center; gap: 3px; }
.stat.running { color: #3b82f6; }
.stat.queued { color: #f59e0b; }
.stat.completed { color: #10b981; }
.stat.failed { color: #ef4444; }
.queue-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #9ca3af; font-size: 13px; text-align: center; line-height: 2.2; }
.queue-empty span { font-size: 11px; }
.queue-list { flex: 1; overflow-y: auto; padding: 6px; display: flex; flex-direction: column; gap: 5px; }
.queue-item { background: #fff; border-radius: 8px; padding: 8px 10px; border: 1px solid #e5e7eb; border-left: 3px solid #9ca3af; }
.queue-item[data-status="running"] { border-left-color: #3b82f6; }
.queue-item[data-status="success"] { border-left-color: #10b981; }
.queue-item[data-status="failed"]  { border-left-color: #ef4444; }
.queue-item[data-status="queued"],
.queue-item[data-status="pending"] { border-left-color: #f59e0b; }
.queue-item-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; }
.queue-scene { font-size: 11px; font-weight: 600; color: #111827; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 140px; }
.status-badge { font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; white-space: nowrap; }
.status-badge.running  { background: #dbeafe; color: #1d4ed8; }
.status-badge.queued, .status-badge.pending { background: #fef3c7; color: #92400e; }
.status-badge.success  { background: #d1fae5; color: #065f46; }
.status-badge.failed   { background: #fee2e2; color: #991b1b; }
.status-badge.paused   { background: #f3f4f6; color: #374151; }
.status-badge.cancelled{ background: #f3f4f6; color: #9ca3af; }
.queue-progress-bar { height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin-bottom: 4px; }
.queue-progress-fill { height: 100%; border-radius: 2px; transition: width 0.3s ease; background: #9ca3af; }
.queue-progress-fill.running { background: #3b82f6; }
.queue-progress-fill.success { background: #10b981; }
.queue-progress-fill.failed  { background: #ef4444; }
.queue-progress-fill.queued, .queue-progress-fill.pending { background: #f59e0b; }
.queue-item-footer { display: flex; align-items: center; gap: 6px; }
.progress-text { font-size: 10px; color: #6b7280; }
.priority-text { font-size: 10px; padding: 1px 5px; border-radius: 3px; }
.priority-text.high   { background: #fee2e2; color: #dc2626; }
.priority-text.medium { background: #fef3c7; color: #d97706; }
.priority-text.low    { background: #f0fdf4; color: #16a34a; }
.btn-cancel { margin-left: auto; padding: 2px 7px; background: #fee2e2; border: none; border-radius: 4px; color: #dc2626; font-size: 10px; cursor: pointer; }
.btn-cancel:hover { background: #fecaca; }
@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 1s linear infinite; }

/* ── 路径选择器 ── */
.picker-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.picker-dialog { background: #fff; border-radius: 10px; width: 500px; max-height: 70vh; display: flex; flex-direction: column; box-shadow: 0 20px 60px rgba(0,0,0,.2); }
.picker-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid #e5e7eb; font-size: 14px; font-weight: 600; color: #111827; }
.picker-header button { background: none; border: none; cursor: pointer; display: flex; align-items: center; color: #6b7280; padding: 4px; border-radius: 4px; }
.picker-header button:hover { background: #f3f4f6; }
.picker-breadcrumb { display: flex; gap: 4px; padding: 6px 16px; background: #f9fafb; border-bottom: 1px solid #e5e7eb; flex-wrap: wrap; }
.breadcrumb-btn { background: none; border: none; padding: 2px 6px; border-radius: 4px; font-size: 12px; color: #3b82f6; cursor: pointer; }
.breadcrumb-btn:hover { background: #dbeafe; }
.picker-list { flex: 1; overflow-y: auto; padding: 8px; }
.picker-item { display: flex; align-items: center; gap: 8px; padding: 7px 10px; border-radius: 6px; cursor: pointer; font-size: 13px; color: #374151; }
.picker-item:hover { background: #f3f4f6; }
.picker-item.dir { font-weight: 500; }
.picker-item-icon { display: flex; align-items: center; color: #6b7280; flex-shrink: 0; }
.picker-empty { padding: 20px; text-align: center; color: #9ca3af; font-size: 13px; }
.picker-footer { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; border-top: 1px solid #e5e7eb; }
.picker-current { font-size: 11px; color: #6b7280; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
