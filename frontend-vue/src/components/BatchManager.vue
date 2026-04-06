<template>
  <div class="batch-manager" :class="{ 'is-touch': supportsTouch, 'is-phone': isPhoneViewport, 'is-tablet': isTabletViewport }">
    <header class="toolbar">
      <div class="toolbar-main">
        <div class="toolbar-title-row">
          <h2 class="toolbar-title">批量流程</h2>
          <span class="flow-status-badge" :class="`is-${workflowStatus.tone}`">
            {{ workflowStatus.label }}
          </span>
        </div>

        <div class="toolbar-meta-row">
          <div class="toolbar-meta-pill">
            <strong>{{ workflowSceneStats.selected }}</strong>
            <span>已选 / {{ workflowSceneStats.total }} 场景</span>
          </div>
          <div class="toolbar-meta-pill">
            <strong>{{ state.nodes.length }}</strong>
            <span>{{ state.edges.length }} 条连线</span>
          </div>
          <div class="toolbar-meta-pill">
            <strong>{{ state.queueStats.running }}</strong>
            <span>{{ state.queueStats.total }} 个任务</span>
          </div>
        </div>
      </div>

      <div class="toolbar-actions">
        <div class="toolbar-priority">
          <span class="toolbar-label">优先级</span>
          <div class="priority-group">
            <button
              v-for="item in priorityOptions"
              :key="item.value"
              type="button"
              class="priority-chip"
              :class="{ active: state.priority === item.value }"
              @click="setPriority(item.value)"
            >
              {{ item.label }}
            </button>
          </div>
        </div>

        <div class="toolbar-button-row">
          <button type="button" class="btn btn-ghost" @click="confirmResetCanvas" title="清空当前流程">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 .49-3.5" />
            </svg>
            重置
          </button>
          <button type="button" class="btn btn-primary" :disabled="state.submitting" @click="submitTask">
            <svg v-if="!state.submitting" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
            {{ state.submitting ? '提交中...' : '提交任务' }}
          </button>
        </div>
      </div>
    </header>

    <div class="main-area" :class="{ tablet: isTabletViewport }">
      <aside v-if="showPaletteRail" class="node-palette" :class="{ touch: supportsTouch, tablet: isTabletViewport }">
        <div class="palette-header">
          <div class="palette-title">流程构件</div>
          <button type="button" class="palette-fit-btn" @click="vfFitView()">查看全局</button>
        </div>

        <div class="palette-list">
          <div
            v-for="nt in nodeTypes"
            :key="nt.type"
            :class="['palette-item', `type-${nt.type}`]"
            :draggable="!supportsTouch"
            tabindex="0"
            @click="handlePaletteActivate(nt)"
            @keydown.enter.prevent="addNodeFromPalette(nt)"
            @keydown.space.prevent="addNodeFromPalette(nt)"
            @dragstart="onDragStart($event, nt)"
            @dragend="onDragEnd"
          >
            <span class="palette-icon" v-html="nt.iconSvg"></span>
            <div class="palette-copy">
              <div class="palette-name">{{ nt.label }}</div>
              <div class="palette-desc">{{ nt.desc }}</div>
            </div>
          </div>
        </div>
      </aside>

      <section class="canvas-stage">
        <div class="stage-header">
          <div class="stage-title">流程画布</div>
          <div class="stage-actions">
            <button type="button" class="stage-action" @click="vfFitView()">查看全局</button>
            <button v-if="showMobilePaletteDrawer" type="button" class="stage-action stage-action-primary" @click="togglePaletteDrawer">
              {{ state.paletteDrawerOpen ? '收起构件' : '流程构件' }}
            </button>
          </div>
        </div>

        <div
          ref="canvasWrapperRef"
          class="canvas-wrapper"
          :class="{ touch: supportsTouch }"
          @drop.prevent="onDrop"
          @dragover.prevent
        >
          <div class="canvas-status-strip">
            <span class="canvas-status-pill" :class="`is-${workflowStatus.tone}`">{{ workflowStatus.label }}</span>
            <span class="canvas-status-pill is-neutral">已选场景 {{ workflowSceneStats.selected }}</span>
            <span class="canvas-status-pill is-neutral">任务队列 {{ state.queueStats.total }}</span>
          </div>

          <VueFlow
            v-model:nodes="state.nodes"
            v-model:edges="state.edges"
            :node-types="customNodeTypes"
            :default-zoom="0.9"
            :min-zoom="0.3"
            :max-zoom="2"
            fit-view-on-init
            class="vue-flow-canvas"
            @node-click="onNodeClick"
            @pane-click="closeSidePanel"
            @connect="onConnect"
            @edges-change="onEdgesChange"
            @nodes-change="onNodesChange"
          >
            <Background pattern-color="#d6dde2" :gap="22" />
            <MiniMap
              v-if="!supportsTouch"
              :node-color="miniMapColor"
              :node-stroke-width="2"
              style="background:#f5f7f8;border-radius:14px"
            />
          </VueFlow>

          <div class="canvas-controls" :class="{ compact: supportsTouch }">
            <button type="button" class="ctrl-btn" title="放大" @click="vfZoomIn()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
                <line x1="11" y1="8" x2="11" y2="14" />
                <line x1="8" y1="11" x2="14" y2="11" />
              </svg>
            </button>
            <button type="button" class="ctrl-btn" title="缩小" @click="vfZoomOut()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
                <line x1="8" y1="11" x2="14" y2="11" />
              </svg>
            </button>
            <button type="button" class="ctrl-btn" title="适应画布" @click="vfFitView()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
              </svg>
            </button>
          </div>
        </div>
      </section>

      <aside class="right-panel">
        <transition name="slide-panel" mode="out-in">
          <section v-if="state.showSidePanel" key="side-panel" class="side-panel" :class="{ mobile: showMobilePaletteDrawer }">
            <div class="side-panel-header">
              <div class="side-panel-title">{{ sidePanelTitle }}</div>
              <button type="button" class="close-btn" @click="closeSidePanel">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div class="side-panel-body">
              <div v-if="panelSummary" class="panel-summary-card">
                <div class="panel-summary-top">
                  <div class="panel-summary-title">{{ panelSummary.title }}</div>
                  <span class="panel-summary-badge" :class="`is-${panelSummary.tone}`">
                    {{ panelSummary.badge }}
                  </span>
                </div>
                <div v-if="panelSummary.metrics.length" class="panel-summary-metrics">
                  <div v-for="item in panelSummary.metrics" :key="item.label" class="summary-metric-pill">
                    <strong>{{ item.value }}</strong>
                    <span>{{ item.label }}</span>
                  </div>
                </div>
              </div>

              <template v-if="state.selectedNode?.type === 'datadir'">
                <div class="form-group">
                  <label>数据根目录 <span class="required">*</span></label>
                  <div class="path-input-row">
                    <input
                      v-model="state.editingParams.root_dir"
                      readonly
                      class="form-input"
                      placeholder="选择包含多个场景子目录的根目录"
                    />
                    <button type="button" class="btn-pick" @click="pickPath('root_dir')">浏览</button>
                  </div>
                </div>

                <template v-if="panelScenes.length">
                  <div class="scene-stats">
                    <div class="scene-stat-card"><span>总场景</span><strong>{{ panelSceneStats.total }}</strong></div>
                    <div class="scene-stat-card"><span>已选</span><strong>{{ panelSceneStats.selected }}</strong></div>
                    <div class="scene-stat-card"><span>仅 L1</span><strong>{{ panelSceneStats.onlyL1 }}</strong></div>
                    <div class="scene-stat-card"><span>仅 L2</span><strong>{{ panelSceneStats.onlyL2 }}</strong></div>
                    <div class="scene-stat-card"><span>混合</span><strong>{{ panelSceneStats.mixed }}</strong></div>
                  </div>

                  <div class="scene-section">
                    <div class="scene-section-header">
                      <div class="section-title">场景列表</div>
                      <div class="scene-list-actions">
                        <button type="button" class="btn-link" @click="selectAllScenes">全选</button>
                        <button type="button" class="btn-link" @click="selectNoneScenes">清空</button>
                      </div>
                    </div>

                    <div class="scene-list">
                      <label
                        v-for="scene in panelScenes"
                        :key="scene.path"
                        class="scene-item"
                        :class="{
                          selected: isSceneSelected(scene, state.editingParams.selectedScenes),
                          mismatch: panelPreferredLevel && !sceneSupportsLevel(scene, panelPreferredLevel),
                        }"
                      >
                        <input
                          type="checkbox"
                          :value="getSceneSelectionKey(scene)"
                          v-model="state.editingParams.selectedScenes"
                        />
                        <div class="scene-item-copy">
                          <div class="scene-item-title-row">
                            <span class="scene-name">{{ scene.name }}</span>
                            <span class="scene-path" :title="scene.path">{{ shortPath(scene.path) }}</span>
                          </div>
                          <div class="scene-badge-row">
                            <span class="scene-badge" :class="`is-${getSceneAvailableTone(scene)}`">
                              {{ getSceneAvailableLabel(scene) }}
                            </span>
                            <span class="scene-badge" :class="scene.has_shp ? 'is-ok' : 'is-muted'">
                              {{ scene.has_shp ? '有 SHP' : '无 SHP' }}
                            </span>
                            <span class="scene-badge" :class="`is-${getSceneCurrentTone(scene, panelPreferredLevel)}`">
                              {{ getSceneCurrentLabel(scene, panelPreferredLevel) }}
                            </span>
                          </div>
                        </div>
                      </label>
                    </div>
                  </div>
                </template>

                <div v-else-if="state.editingParams.root_dir" class="inline-card">
                  保存后显示场景列表。
                </div>
              </template>

              <template v-else-if="state.selectedNode?.type === 'input' && !panelScenes.length">
                <div class="strategy-card">
                  <div class="strategy-header">
                    <div class="section-title">产品级别</div>
                    <span class="strategy-badge">{{ state.editingParams.product_level || 'L1' }}</span>
                  </div>
                  <div class="segmented-control">
                    <button
                      v-for="level in levelOptions"
                      :key="level"
                      type="button"
                      class="segment-btn"
                      :class="{ active: state.editingParams.product_level === level }"
                      @click="setEditingProductLevel(level)"
                    >
                      <strong>{{ level }}</strong>
                      <span>{{ level === 'L1' ? '预处理' : '直用' }}</span>
                    </button>
                  </div>
                </div>

                <div class="form-group">
                  <label>场景名称</label>
                  <input v-model="state.editingParams.scene_name" class="form-input" placeholder="如 LC08_L1TP_..." />
                </div>

                <div class="form-group">
                  <label>波段文件目录 <span class="required">*</span></label>
                  <div class="path-input-row">
                    <input
                      v-model="state.editingParams.band_dir"
                      readonly
                      class="form-input"
                      placeholder="选择或输入波段目录"
                    />
                    <button type="button" class="btn-pick" @click="pickPath('band_dir')">浏览</button>
                  </div>
                </div>

                <div class="form-group">
                  <label>MTL 元数据文件（可选）</label>
                  <div class="path-input-row">
                    <input v-model="state.editingParams.mtl_file" class="form-input" placeholder="如 *_MTL.txt" />
                    <button type="button" class="btn-pick" @click="pickPath('mtl_file')">浏览</button>
                  </div>
                </div>

                <div class="form-group">
                  <label>QA 波段文件（可选）</label>
                  <input v-model="state.editingParams.qa_band" class="form-input" placeholder="如 *_QA_PIXEL.TIF" />
                </div>

                <div class="form-group">
                  <label>QA_RADSAT 波段文件（可选）</label>
                  <input
                    v-model="state.editingParams.qa_radsat_band"
                    class="form-input"
                    placeholder="如 *_QA_RADSAT.TIF"
                  />
                </div>
              </template>

              <template v-else-if="state.selectedNode?.type === 'input' && panelScenes.length">
                <div class="strategy-card">
                  <div class="strategy-header">
                    <div class="strategy-title" :class="`is-${inputStrategy.tone}`">{{ inputStrategy.title }}</div>
                    <span class="strategy-badge">{{ panelPreferredLevel || '自动' }}</span>
                  </div>
                  <div class="segmented-control">
                    <button
                      v-for="level in levelOptions"
                      :key="level"
                      type="button"
                      class="segment-btn"
                      :class="{ active: state.editingParams.product_level === level }"
                      @click="setEditingProductLevel(level)"
                    >
                      <strong>{{ level }}</strong>
                      <span>{{ level === 'L1' ? '预处理' : '直用' }}</span>
                    </button>
                  </div>
                </div>

                <div class="scene-stats">
                  <div class="scene-stat-card"><span>总场景</span><strong>{{ panelSceneStats.total }}</strong></div>
                  <div class="scene-stat-card"><span>已选</span><strong>{{ panelSceneStats.selected }}</strong></div>
                  <div class="scene-stat-card"><span>仅 L1</span><strong>{{ panelSceneStats.onlyL1 }}</strong></div>
                  <div class="scene-stat-card"><span>仅 L2</span><strong>{{ panelSceneStats.onlyL2 }}</strong></div>
                  <div class="scene-stat-card"><span>混合</span><strong>{{ panelSceneStats.mixed }}</strong></div>
                </div>

                <div v-if="panelSceneStats.mismatch > 0" class="inline-card inline-card-warn">
                  当前有 {{ panelSceneStats.mismatch }} 个已选场景不包含 {{ panelPreferredLevel }} 产品。
                  场景不会被自动隐藏，但提交后这些任务可能失败。
                </div>

                <div class="scene-section">
                  <div class="scene-section-header">
                    <div class="section-title">场景列表</div>
                    <div class="scene-list-actions">
                      <button type="button" class="btn-link" @click="selectAllScenes">全选</button>
                      <button type="button" class="btn-link" @click="selectNoneScenes">清空</button>
                    </div>
                  </div>

                  <div class="scene-list">
                    <label
                      v-for="scene in panelScenes"
                      :key="scene.path"
                      class="scene-item"
                      :class="{
                        selected: isSceneSelected(scene, state.editingParams.selectedScenes),
                        mismatch: panelPreferredLevel && !sceneSupportsLevel(scene, panelPreferredLevel),
                      }"
                    >
                      <input
                        type="checkbox"
                        :value="getSceneSelectionKey(scene)"
                        v-model="state.editingParams.selectedScenes"
                      />
                      <div class="scene-item-copy">
                        <div class="scene-item-title-row">
                          <span class="scene-name">{{ scene.name }}</span>
                          <span class="scene-path" :title="scene.path">{{ shortPath(scene.path) }}</span>
                        </div>
                        <div class="scene-badge-row">
                          <span class="scene-badge" :class="`is-${getSceneAvailableTone(scene)}`">
                            {{ getSceneAvailableLabel(scene) }}
                          </span>
                          <span class="scene-badge" :class="scene.has_shp ? 'is-ok' : 'is-muted'">
                            {{ scene.has_shp ? '有 SHP' : '无 SHP' }}
                          </span>
                          <span class="scene-badge" :class="scene.mtl_file ? 'is-info' : 'is-muted'">
                            {{ scene.mtl_file ? 'MTL 已识别' : '无 MTL' }}
                          </span>
                          <span class="scene-badge" :class="`is-${getSceneCurrentTone(scene, panelPreferredLevel)}`">
                            {{ getSceneCurrentLabel(scene, panelPreferredLevel) }}
                          </span>
                        </div>
                      </div>
                    </label>
                  </div>
                </div>
              </template>

              <template v-else-if="state.selectedNode?.type === 'conditional'">
                <div class="inline-card">
                  检测 SHP 后决定是否进入裁剪分支。
                </div>
              </template>

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

                <div class="inline-card">
                  L2 输入自动跳过。
                </div>
              </template>

              <template v-else-if="state.selectedNode?.type === 'clip'">
                <div class="form-group">
                  <label>矢量文件路径（.shp）</label>
                  <div class="path-input-row">
                    <input
                      v-model="state.editingParams.clip_shapefile"
                      class="form-input"
                      placeholder="Shapefile 路径（可由 SHP 检测自动填充）"
                    />
                    <button type="button" class="btn-pick" @click="pickPath('clip_shapefile')">浏览</button>
                  </div>
                  <div class="clip-action-row">
                    <button
                      type="button"
                      class="btn-pick"
                      :disabled="state.clipPreviewLoading || !String(state.editingParams.clip_shapefile || '').trim()"
                      @click="loadClipVectorPreview(state.editingParams.clip_shapefile, { syncExtent: !String(state.editingParams.clip_extent || '').trim() })"
                    >
                      {{ state.clipPreviewLoading ? '预览中...' : '预览矢量' }}
                    </button>
                    <span class="form-hint">批处理页只保存本地路径，地图用于预览与 bbox 回写。</span>
                  </div>
                </div>

                <div class="form-group">
                  <label>共享 ROI 预览</label>
                  <AoiMapPicker
                    v-model="state.editingParams.clip_extent"
                    :bbox="state.clipPreviewBbox"
                    :geojson="state.clipPreviewGeoJson"
                    :coverage-geojson="state.clipCoverageGeoJson"
                    :status-text="clipPreviewStatusText"
                    label="当前 ROI"
                    :height="224"
                    @drawend="onClipDraw"
                    @clear="clearClipPreview"
                  />
                  <div class="clip-preview-meta">
                    <div class="clip-preview-pill">
                      <strong>来源</strong>
                      <span>{{ getClipSourceLabel(state.editingParams.clip_source || state.clipPreviewSource) }}</span>
                    </div>
                    <div class="clip-preview-pill">
                      <strong>要素</strong>
                      <span>{{ state.editingParams.clip_feature_count || state.clipPreviewFeatureCount || 0 }}</span>
                    </div>
                    <div class="clip-preview-pill">
                      <strong>确认</strong>
                      <span>{{ state.editingParams.clip_confirmed ? '已确认' : '未确认' }}</span>
                    </div>
                    <div class="clip-preview-pill">
                      <strong>越界校验</strong>
                      <span>{{ batchClipCoverageValidation.message || '待校验' }}</span>
                    </div>
                  </div>
                  <div v-if="state.clipPreviewError" class="form-hint form-hint-error">{{ state.clipPreviewError }}</div>
                </div>

                <div class="form-group">
                  <label>经纬度范围（共享 bbox）</label>
                  <input
                    v-model="state.editingParams.clip_extent"
                    class="form-input"
                    placeholder="minLon,minLat,maxLon,maxLat"
                    @change="syncClipPreviewFromExtent({ markManual: true })"
                  />
                  <div class="form-hint">例如：116.3,39.8,116.6,40.1。地图框选会自动回写；若保留上方 .shp 路径，提交时优先使用矢量。</div>
                </div>
              </template>

              <template v-else-if="state.selectedNode?.type === 'mosaic'">
                <div class="form-group">
                  <label>输出目录名</label>
                  <input v-model="state.editingParams.output_name" class="form-input" placeholder="如 mosaic_2024" />
                  <div class="form-hint">用于输出根目录下的镶嵌结果子目录，不影响单景中间目录名称。</div>
                </div>

                <div class="form-group">
                  <label class="checkbox-label">
                    <input type="checkbox" v-model="state.editingParams.keep_intermediate" />
                    保留每景中间产物
                  </label>
                  <div class="form-hint">关闭时会在聚合完成后自动清理 `_intermediate` 目录。</div>
                </div>

                <div class="form-group">
                  <label class="checkbox-label">
                    <input type="checkbox" v-model="state.editingParams.display_balance_enabled" />
                    启用显示匀色
                  </label>
                  <div class="form-hint">仅影响 true_color 等显示型合成，不改分析波段与指数输入。</div>
                </div>
              </template>

              <template v-else-if="state.selectedNode?.type === 'synthesis'">
                <div class="form-group">
                  <label>选择指数 / 合成色（可多选）</label>
                  <div class="composite-grid">
                    <div v-for="group in compositeGroups" :key="group.label" class="composite-group">
                      <div class="group-label">{{ group.label }}</div>
                      <label v-for="item in group.items" :key="item.value" class="checkbox-label">
                        <input type="checkbox" :value="item.value" v-model="state.editingParams.composites" />
                        {{ item.label }}
                      </label>
                    </div>
                  </div>
                </div>

                <div class="form-group">
                  <label>自定义指数（可选）</label>
                  <input
                    v-model="state.editingParams.custom_name"
                    class="form-input"
                    placeholder="指数名称，如 MyIndex"
                  />
                  <input
                    v-model="state.editingParams.custom_formula"
                    class="form-input"
                    placeholder="公式，如 (B5-B4)/(B5+B4)"
                    style="margin-top:8px"
                  />
                  <div class="form-hint">支持 B1-B11 以及 abs / sqrt / log / exp / clip。</div>
                </div>
              </template>

              <template v-else-if="state.selectedNode?.type === 'output'">
                <div class="form-group">
                  <label>输出根目录 <span class="required">*</span></label>
                  <div class="path-input-row">
                    <input
                      v-model="state.editingParams.output_dir"
                      readonly
                      class="form-input"
                      placeholder="选择输出目录"
                    />
                    <button type="button" class="btn-pick" @click="pickPath('output_dir')">浏览</button>
                  </div>
                </div>
              </template>

              <template v-else-if="state.selectedNode?.type === 'radiometric'">
                <div class="inline-card">
                  固定主链。L2 输入自动跳过。
                </div>
              </template>
            </div>

            <div v-if="showSidePanelFooter" class="side-panel-footer">
              <button type="button" class="btn btn-secondary" @click="closeSidePanel">取消</button>
              <button type="button" class="btn btn-primary" @click="saveNodeParams">保存</button>
            </div>
          </section>

          <section v-else key="queue-panel" class="queue-panel">
            <div class="queue-header">
              <div class="queue-title">任务队列</div>
              <button
                v-if="state.taskQueue.length > 0"
                type="button"
                class="btn-clear-queue"
                title="取消所有等待中的任务"
                @click="clearQueue"
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                  <path d="M10 11v6M14 11v6" />
                  <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                </svg>
                清空等待
              </button>
            </div>

            <div class="queue-summary-grid">
              <div v-for="item in queueSummaryCards" :key="item.label" class="queue-summary-card" :class="`is-${item.tone}`">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>

            <div v-if="state.taskQueue.length === 0" class="queue-empty">
              <strong>还没有批处理任务</strong>
              <span>提交后在这里查看进度。</span>
            </div>

            <div v-else class="queue-list">
              <div v-for="job in state.taskQueue" :key="job.job_id" class="queue-item" :data-status="job.status">
                <div class="queue-item-header">
                  <div class="queue-item-copy">
                    <span class="queue-scene" :title="job.scene_name">{{ job.scene_name || '未命名场景' }}</span>
                  </div>
                  <span class="status-badge" :class="job.status">{{ statusLabel[job.status] || job.status }}</span>
                </div>

                <div class="queue-item-meta">
                  <span class="queue-subline">优先级 {{ priorityLabel[job.priority] || job.priority }}</span>
                  <span class="progress-text">{{ job.progress }}%</span>
                </div>

                <div class="queue-progress-row">
                  <div class="queue-progress-bar">
                    <div class="queue-progress-fill" :class="job.status" :style="{ width: `${job.progress}%` }"></div>
                  </div>
                  <button
                    v-if="['queued', 'pending', 'paused'].includes(job.status)"
                    type="button"
                    class="btn-cancel"
                    @click="cancelJob(job.job_id)"
                  >
                    取消
                  </button>
                </div>
              </div>
            </div>
          </section>
        </transition>
      </aside>
    </div>

      <div v-if="showMobilePaletteDrawer" class="mobile-palette-drawer" :class="{ open: state.paletteDrawerOpen }">
      <button type="button" class="mobile-drawer-handle" @click="togglePaletteDrawer">
        <span>{{ state.paletteDrawerOpen ? '收起流程构件' : '流程构件' }}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
          <polyline :points="state.paletteDrawerOpen ? '18 15 12 9 6 15' : '6 9 12 15 18 9'" />
        </svg>
      </button>

        <div class="mobile-palette-content">
          <div class="mobile-palette-header">
            <div class="palette-title">流程构件</div>
            <button type="button" class="palette-fit-btn" @click="vfFitView()">查看全局</button>
          </div>

        <div class="mobile-palette-list">
          <button
            v-for="nt in nodeTypes"
            :key="nt.type"
            type="button"
            :class="['palette-item', 'mobile', `type-${nt.type}`]"
            @click="handlePaletteActivate(nt)"
          >
            <span class="palette-icon" v-html="nt.iconSvg"></span>
            <div class="palette-copy">
              <div class="palette-name">{{ nt.label }}</div>
              <div class="palette-desc">{{ nt.desc }}</div>
            </div>
          </button>
        </div>
      </div>
    </div>

    <div v-if="state.showPicker" class="picker-overlay" @click.self="state.showPicker = false">
      <div class="picker-dialog">
        <div class="picker-header">
          <span>{{ state.pickerTitle || '选择路径' }}</span>
          <button type="button" @click="state.showPicker = false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div class="picker-breadcrumb">
          <button
            v-for="(seg, i) in state.pickerBreadcrumb"
            :key="`${seg.path || 'root'}-${i}`"
            type="button"
            class="breadcrumb-btn"
            @click="navigatePicker(i)"
          >
            {{ seg.label }}
          </button>
        </div>

        <div class="picker-list">
          <div
            v-for="item in state.pickerItems"
            :key="item.path"
            class="picker-item dir"
            @click="onPickerItemClick(item)"
          >
            <span class="picker-item-icon">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
            </span>
            <span>{{ item.name }}</span>
          </div>
          <template v-if="state.pickerMode === 'file'">
            <div v-if="state.pickerFiles.length" class="picker-section-label">文件</div>
            <div
              v-for="file in state.pickerFiles"
              :key="file.path"
              :class="['picker-item', 'file', { selected: state.pickerSelectedPath === file.path }]"
              @click="selectPickerFile(file)"
            >
              <span class="picker-item-icon">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
              </span>
              <span>{{ file.name }}</span>
            </div>
          </template>
          <div
            v-if="state.pickerItems.length === 0 && (state.pickerMode !== 'file' || state.pickerFiles.length === 0)"
            class="picker-empty"
          >
            空目录
          </div>
        </div>

        <div class="picker-footer">
          <span class="picker-current">{{ pickerCurrentLabel }}</span>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="pickerConfirmDisabled"
            @click="confirmPick"
          >
            {{ pickerConfirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, markRaw, onMounted, onUnmounted, reactive, ref } from 'vue'
import { VueFlow, applyEdgeChanges, applyNodeChanges, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

import DataDirNode from './flow-nodes/DataDirNode.vue'
import InputNode from './flow-nodes/InputNode.vue'
import RadiometricNode from './flow-nodes/RadiometricNode.vue'
import AtmosphericNode from './flow-nodes/AtmosphericNode.vue'
import ClipNode from './flow-nodes/ClipNode.vue'
import MosaicNode from './flow-nodes/MosaicNode.vue'
import ConditionalNode from './flow-nodes/ConditionalNode.vue'
import SynthesisNode from './flow-nodes/SynthesisNode.vue'
import OutputNode from './flow-nodes/OutputNode.vue'
import AoiMapPicker from './AoiMapPicker.vue'
import { assessCoverage, buildBboxFeatureCollection, normalizeBbox } from '../utils/coverage'

const props = defineProps(['apiBase'])
const emit = defineEmits(['toast'])

const { zoomIn: vfZoomIn, zoomOut: vfZoomOut, fitView: vfFitView, screenToFlowCoordinate } = useVueFlow()
const canvasWrapperRef = ref(null)
const supportsTouch = ref(false)
const isPhoneViewport = ref(false)
const isTabletViewport = ref(false)
const showPaletteRail = computed(() => !isPhoneViewport.value || !supportsTouch.value)
const showMobilePaletteDrawer = computed(() => isPhoneViewport.value && supportsTouch.value)

const levelOptions = ['L1', 'L2']
const priorityOptions = [
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
]

const customNodeTypes = {
  datadir: markRaw(DataDirNode),
  input: markRaw(InputNode),
  radiometric: markRaw(RadiometricNode),
  atmospheric: markRaw(AtmosphericNode),
  clip: markRaw(ClipNode),
  mosaic: markRaw(MosaicNode),
  conditional: markRaw(ConditionalNode),
  synthesis: markRaw(SynthesisNode),
  output: markRaw(OutputNode),
}

const ICON_CLOUD = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10h-1.26A8 8 0 109 20h9a5 5 0 000-10z"/></svg>`
const ICON_CROP = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6.13 1L6 16a2 2 0 002 2h15"/><path d="M1 6.13L16 6a2 2 0 012 2v15"/></svg>`
const ICON_MOSAIC = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h7v7H3z"/><path d="M14 3h7v7h-7z"/><path d="M3 14h7v7H3z"/><path d="M14 14h7v7h-7z"/></svg>`
const ICON_LAYERS = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>`
const ICON_COND = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>`

const nodeTypes = [
  { type: 'atmospheric', iconSvg: ICON_CLOUD, label: '大气校正', desc: 'DOS / 6S 方法切换' },
  { type: 'conditional', iconSvg: ICON_COND, label: 'SHP 检测', desc: '按场景是否存在 SHP 分流' },
  { type: 'mosaic', iconSvg: ICON_MOSAIC, label: '影像镶嵌', desc: '多景同名波段拼接为单一结果' },
  { type: 'clip', iconSvg: ICON_CROP, label: '区域裁剪', desc: '支持 SHP 或经纬度范围' },
  { type: 'synthesis', iconSvg: ICON_LAYERS, label: '合成指数', desc: '多种组合与自定义公式' },
]

function createInitialNodes() {
  return [
    {
      id: 'datadir-1',
      type: 'datadir',
      position: { x: 40, y: 120 },
      data: { root_dir: '', scenes: [], selectedScenes: [] },
      deletable: false,
    },
    {
      id: 'input-1',
      type: 'input',
      position: { x: 280, y: 120 },
      data: {
        band_dir: '',
        scene_name: '',
        mtl_file: '',
        qa_band: '',
        qa_radsat_band: '',
        product_level: 'L1',
        scenes: [],
        selectedScenes: [],
      },
      deletable: false,
    },
    {
      id: 'radiometric-1',
      type: 'radiometric',
      position: { x: 510, y: 120 },
      data: {},
      deletable: false,
    },
    {
      id: 'output-1',
      type: 'output',
      position: { x: 750, y: 120 },
      data: { output_dir: '' },
      deletable: false,
    },
  ]
}

function createInitialEdges() {
  return [
    { id: 'e-dd-in', source: 'datadir-1', target: 'input-1', animated: false },
    { id: 'e-in-rad', source: 'input-1', target: 'radiometric-1', animated: false },
    { id: 'e-rad-out', source: 'radiometric-1', target: 'output-1', animated: false },
  ]
}

const state = reactive({
  nodes: createInitialNodes(),
  edges: createInitialEdges(),
  selectedNode: null,
  showSidePanel: false,
  editingParams: {},
  clipPreviewGeoJson: null,
  clipPreviewBbox: null,
  clipPreviewLabel: '',
  clipPreviewFeatureCount: 0,
  clipPreviewSource: '',
  clipPreviewLoading: false,
  clipPreviewError: '',
  clipCoverageGeoJson: null,
  clipCoverageBboxes: [],
  clipCoverageLoading: false,
  clipCoverageError: '',
  clipCoverageMode: '',
  priority: 'medium',
  submitting: false,
  taskQueue: [],
  queueStats: { total: 0, running: 0, queued: 0, completed: 0, failed: 0 },
  pollingTimer: null,
  showPicker: false,
  pickerField: '',
  pickerMode: 'directory',
  pickerTitle: '选择路径',
  pickerAllowedSuffixes: [],
  pickerCurrentPath: '',
  pickerBreadcrumb: [{ label: '根目录', path: '' }],
  pickerRoots: [],
  pickerItems: [],
  pickerFiles: [],
  pickerSelectedPath: '',
  pickerSelectedKind: '',
  paletteDrawerOpen: false,
})

const sidePanelTitle = computed(() => {
  const map = {
    datadir: '数据目录配置',
    input: '场景数据配置',
    radiometric: '辐射定标',
    atmospheric: '大气校正配置',
    conditional: 'SHP 检测',
    mosaic: '影像镶嵌配置',
    clip: '区域裁剪配置',
    synthesis: '合成指数配置',
    output: '输出配置',
  }
  return map[state.selectedNode?.type] || '节点配置'
})

const statusLabel = {
  queued: '排队中',
  pending: '等待',
  running: '运行中',
  success: '已完成',
  failed: '失败',
  cancelled: '已取消',
  paused: '已暂停',
}

const priorityLabel = { high: '高', medium: '中', low: '低' }

const PICKER_CONFIG = {
  root_dir: { mode: 'directory', title: '选择数据根目录', allowedSuffixes: [] },
  band_dir: { mode: 'directory', title: '选择波段目录', allowedSuffixes: [] },
  output_dir: { mode: 'directory', title: '选择输出目录', allowedSuffixes: [] },
  clip_shapefile: { mode: 'file', title: '选择矢量文件', allowedSuffixes: ['.shp', '.geojson', '.json'] },
  mtl_file: { mode: 'file', title: '选择 MTL 文件', allowedSuffixes: ['.txt', '.mtl'] },
}

const pickerConfirmLabel = computed(() => (state.pickerMode === 'file' ? '选择文件' : '选择此目录'))

const pickerConfirmDisabled = computed(() => {
  if (state.pickerMode === 'file') return !state.pickerSelectedPath
  return !state.pickerCurrentPath
})

const pickerCurrentLabel = computed(() => {
  if (state.pickerMode === 'file') return state.pickerSelectedPath || state.pickerCurrentPath || '未选择文件'
  return state.pickerCurrentPath || '未选择目录'
})

const compositeGroups = [
  {
    label: 'RGB 合成',
    items: [
      { value: 'true_color', label: '真彩色' },
      { value: 'false_color', label: '假彩色' },
      { value: 'agriculture', label: '农业' },
      { value: 'urban', label: '城市' },
      { value: 'natural_color', label: '自然彩色' },
      { value: 'swir', label: '短波红外' },
    ],
  },
  {
    label: '植被指数',
    items: [
      { value: 'ndvi', label: 'NDVI' },
      { value: 'evi', label: 'EVI' },
      { value: 'savi', label: 'SAVI' },
      { value: 'msavi', label: 'MSAVI' },
      { value: 'arvi', label: 'ARVI' },
      { value: 'rvi', label: 'RVI' },
    ],
  },
  {
    label: '水体指数',
    items: [
      { value: 'ndwi', label: 'NDWI' },
      { value: 'mndwi', label: 'MNDWI' },
      { value: 'awei', label: 'AWEI' },
      { value: 'wri', label: 'WRI' },
    ],
  },
  {
    label: '建筑/城市',
    items: [
      { value: 'ndbi', label: 'NDBI' },
      { value: 'ibi', label: 'IBI' },
      { value: 'ndbai', label: 'NDBaI' },
      { value: 'ui', label: 'UI' },
    ],
  },
  {
    label: '其他',
    items: [
      { value: 'nbr', label: 'NBR' },
      { value: 'bsi', label: 'BSI' },
      { value: 'ndsi', label: 'NDSI' },
    ],
  },
]

function normalizeProductLevel(level) {
  const normalized = String(level || '').trim().toUpperCase()
  return normalized === 'L1' || normalized === 'L2' ? normalized : ''
}

function shortPath(path, depth = 2) {
  if (!path) return ''
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean)
  if (parts.length <= depth) return path
  return `.../${parts.slice(-depth).join('/')}`
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
  return extent.map((value) => String(Number(value.toFixed(6)))).join(',')
}

function getClipSourceLabel(source) {
  if (source === 'filesystem') return '本地矢量'
  if (source === 'bbox') return '地图框选'
  if (source === 'manual') return '手填范围'
  return source || '未设置'
}

function resetClipPreview() {
  state.clipPreviewGeoJson = null
  state.clipPreviewBbox = null
  state.clipPreviewLabel = ''
  state.clipPreviewFeatureCount = 0
  state.clipPreviewSource = ''
  state.clipPreviewLoading = false
  state.clipPreviewError = ''
}

function resetClipCoverage() {
  state.clipCoverageGeoJson = null
  state.clipCoverageBboxes = []
  state.clipCoverageLoading = false
  state.clipCoverageError = ''
  state.clipCoverageMode = ''
}

function clearClipPreview({ preserveConfig = false } = {}) {
  resetClipPreview()
  if (preserveConfig || state.selectedNode?.type !== 'clip') return
  state.editingParams.clip_shapefile = ''
  state.editingParams.clip_extent = ''
  state.editingParams.clip_source = ''
  state.editingParams.clip_label = ''
  state.editingParams.clip_feature_count = 0
  state.editingParams.clip_confirmed = false
}

function applyClipPreview({
  bbox = null,
  geojson = null,
  label = '',
  featureCount = 0,
  source = '',
  confirmed = true,
  syncExtent = false,
  clearShapefile = false,
} = {}) {
  state.clipPreviewGeoJson = geojson || null
  state.clipPreviewBbox = Array.isArray(bbox) && bbox.length === 4 ? bbox.map((value) => Number(value)) : null
  state.clipPreviewLabel = label || ''
  state.clipPreviewFeatureCount = Number(featureCount || 0)
  state.clipPreviewSource = source || ''
  state.clipPreviewError = ''

  if (state.selectedNode?.type !== 'clip') return

  state.editingParams.clip_source = source || ''
  state.editingParams.clip_label = label || ''
  state.editingParams.clip_feature_count = Number(featureCount || 0)
  state.editingParams.clip_confirmed = confirmed

  if (syncExtent && state.clipPreviewBbox) {
    state.editingParams.clip_extent = formatExtentText(state.clipPreviewBbox)
  }
  if (clearShapefile) {
    state.editingParams.clip_shapefile = ''
  }
}

async function loadClipVectorPreview(path = '', options = {}) {
  const targetPath = (path || state.editingParams.clip_shapefile || '').trim()
  if (!targetPath) {
    state.clipPreviewError = '请先输入本地矢量路径'
    return false
  }

  state.clipPreviewLoading = true
  state.clipPreviewError = ''
  try {
    const body = new FormData()
    body.append('path', targetPath)
    const resp = await fetch(`${props.apiBase}/filesystem/vector_preview`, {
      method: 'POST',
      body,
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) {
      throw new Error(data.detail || '矢量预览失败')
    }

    applyClipPreview({
      bbox: data.bbox,
      geojson: data.geojson || null,
      label: data.label || targetPath.split(/[\\/]/).pop() || '矢量范围',
      featureCount: data.feature_count || 0,
      source: 'filesystem',
      confirmed: true,
      syncExtent: Boolean(options.syncExtent),
    })
    state.editingParams.clip_shapefile = targetPath
    return true
  } catch (error) {
    state.clipPreviewError = error.message
    if (!options.silent) {
      emit('toast', { type: 'error', message: `矢量预览失败：${error.message}` })
    }
    return false
  } finally {
    state.clipPreviewLoading = false
  }
}

function syncClipPreviewFromExtent({ markManual = false } = {}) {
  const bbox = parseExtentText(state.editingParams.clip_extent)
  if (!bbox) {
    if (!state.editingParams.clip_shapefile) resetClipPreview()
    return false
  }

  applyClipPreview({
    bbox,
    geojson: null,
    label: markManual ? '手填范围' : (state.editingParams.clip_label || '矩形范围'),
    featureCount: 1,
    source: markManual ? 'manual' : (state.editingParams.clip_source || 'bbox'),
    confirmed: true,
    syncExtent: false,
  })
  return true
}

function onClipDraw(bbox) {
  applyClipPreview({
    bbox,
    geojson: null,
    label: '矩形框选',
    featureCount: 1,
    source: 'bbox',
    confirmed: true,
    syncExtent: true,
    clearShapefile: true,
  })
}

async function restoreClipPreviewFromNode(nodeData = {}) {
  resetClipPreview()
  const clipPath = (nodeData.clip_shapefile || '').trim()
  if (clipPath) {
    await loadClipVectorPreview(clipPath, {
      silent: true,
      syncExtent: !String(nodeData.clip_extent || '').trim(),
    })
    return
  }

  const bbox = parseExtentText(nodeData.clip_extent)
  if (!bbox) return

  applyClipPreview({
    bbox,
    geojson: null,
    label: nodeData.clip_label || '矩形范围',
    featureCount: Number(nodeData.clip_feature_count || 1),
    source: nodeData.clip_source || 'bbox',
    confirmed: nodeData.clip_confirmed !== false,
    syncExtent: false,
  })
}

function getWorkflowSelectedScenes() {
  const selected = getSelectedSceneItems(workflowScenes.value, workflowSelectedScenes.value)
  if (selected.length) return selected

  const inputNode = workflowInputNode.value
  if (inputNode?.data?.band_dir && !(inputNode?.data?.scenes?.length ?? 0)) {
    return [{
      name: inputNode.data.scene_name || shortPath(inputNode.data.band_dir, 2),
      path: inputNode.data.band_dir,
      product_level: inputNode.data.product_level || 'L1',
      footprint_bbox: null,
    }]
  }
  return []
}

async function loadRasterFootprint(path, productLevel = '') {
  const body = new FormData()
  body.append('path', path)
  if (productLevel) body.append('product_level', productLevel)
  const resp = await fetch(`${props.apiBase}/filesystem/raster_footprint`, {
    method: 'POST',
    body,
  })
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    throw new Error(data.detail || '影像覆盖范围读取失败')
  }
  return data
}

async function restoreClipCoverage() {
  resetClipCoverage()
  const selectedScenes = getWorkflowSelectedScenes()
  if (!selectedScenes.length) return

  const sceneBoxes = selectedScenes
    .map((scene) => ({
      scene,
      bbox: normalizeBbox(scene.footprint_bbox),
    }))
    .filter((item) => item.bbox)

  if (sceneBoxes.length) {
    state.clipCoverageBboxes = sceneBoxes.map((item) => item.bbox)
    state.clipCoverageGeoJson = buildBboxFeatureCollection(
      sceneBoxes.map((item) => ({
        bbox: item.bbox,
        properties: { sceneName: item.scene.name },
      })),
    )
    state.clipCoverageMode = findNodeByType('mosaic') ? 'mosaic' : 'scene'
    if (sceneBoxes.length !== selectedScenes.length) {
      state.clipCoverageError = `有 ${selectedScenes.length - sceneBoxes.length} 个场景缺少覆盖范围，校验结果可能不完整`
    }
    return
  }

  const inputNode = workflowInputNode.value
  if (!inputNode?.data?.band_dir) {
    state.clipCoverageError = '当前输入节点未提供可用的影像覆盖范围'
    return
  }

  state.clipCoverageLoading = true
  try {
    const data = await loadRasterFootprint(inputNode.data.band_dir, inputNode.data.product_level || 'L1')
    const bbox = normalizeBbox(data.bbox)
    state.clipCoverageBboxes = bbox ? [bbox] : []
    state.clipCoverageGeoJson = data.geojson || (bbox ? buildBboxFeatureCollection([{ bbox }]) : null)
    state.clipCoverageMode = findNodeByType('mosaic') ? 'mosaic' : 'scene'
  } catch (error) {
    state.clipCoverageError = error.message
  } finally {
    state.clipCoverageLoading = false
  }
}

function getSceneSelectionKey(scene) {
  return scene?.id || scene?.path || scene?.name || ''
}

function sceneMatchesSelection(scene, selectedValues) {
  const selected = selectedValues instanceof Set ? selectedValues : new Set(selectedValues)
  return selected.has(getSceneSelectionKey(scene)) || selected.has(scene?.path) || selected.has(scene?.name)
}

function normalizeSceneSelections(selectedScenes, scenes = []) {
  const selected = new Set(Array.isArray(selectedScenes) ? selectedScenes : [])
  if (!selected.size || !scenes.length) return []

  const normalized = new Set()
  for (const scene of scenes) {
    const key = getSceneSelectionKey(scene)
    if (!key) continue
    if (sceneMatchesSelection(scene, selected)) normalized.add(key)
  }
  return Array.from(normalized)
}

function getAllSceneSelectionKeys(scenes = []) {
  return scenes.map((scene) => getSceneSelectionKey(scene)).filter(Boolean)
}

function syncSceneSelections(params, { defaultToAll = false } = {}) {
  const scenes = Array.isArray(params?.scenes) ? params.scenes : []
  if (!scenes.length) return

  if (Array.isArray(params.selectedScenes)) {
    const normalized = normalizeSceneSelections(params.selectedScenes, scenes)
    params.selectedScenes = normalized.length || params.selectedScenes.length === 0
      ? normalized
      : (defaultToAll ? getAllSceneSelectionKeys(scenes) : [])
    return
  }

  if (defaultToAll) {
    params.selectedScenes = getAllSceneSelectionKeys(scenes)
  }
}

function getSceneAvailableLevels(scene) {
  const base = Array.isArray(scene?.available_product_levels) && scene.available_product_levels.length
    ? scene.available_product_levels
    : [scene?.product_level]
  return [...new Set(base.map((item) => normalizeProductLevel(item)).filter(Boolean))]
}

function getSceneAvailableTone(scene) {
  const levels = getSceneAvailableLevels(scene)
  if (levels.length > 1) return 'mixed'
  if (levels[0] === 'L2') return 'l2'
  if (levels[0] === 'L1') return 'l1'
  return 'muted'
}

function getSceneAvailableLabel(scene) {
  const levels = getSceneAvailableLevels(scene)
  if (!levels.length) return '级别未知'
  if (levels.length > 1) return '可用 L1/L2'
  return `可用 ${levels[0]}`
}

function sceneSupportsLevel(scene, level) {
  const normalized = normalizeProductLevel(level)
  if (!normalized) return true
  const levels = getSceneAvailableLevels(scene)
  return !levels.length || levels.includes(normalized)
}

function getSceneCurrentLabel(scene, preferredLevel = '') {
  const normalized = normalizeProductLevel(preferredLevel)
  if (!normalized) {
    const levels = getSceneAvailableLevels(scene)
    if (levels.length > 1) return '待选择级别'
    return `自动 ${normalizeProductLevel(scene?.product_level) || levels[0] || 'L1'}`
  }
  return sceneSupportsLevel(scene, normalized) ? `处理 ${normalized}` : `不含 ${normalized}`
}

function getSceneCurrentTone(scene, preferredLevel = '') {
  const normalized = normalizeProductLevel(preferredLevel)
  if (!normalized) return 'neutral'
  return sceneSupportsLevel(scene, normalized) ? 'info' : 'warn'
}

function getSelectedSceneItems(scenes = [], selectedValues = []) {
  if (!Array.isArray(scenes) || !scenes.length) return []
  const selectedSet = new Set(normalizeSceneSelections(selectedValues, scenes))
  return scenes.filter((scene) => selectedSet.has(getSceneSelectionKey(scene)))
}

function buildSceneStats(scenes = [], selectedValues = [], preferredLevel = '') {
  const selectedScenes = getSelectedSceneItems(scenes, selectedValues)
  const stats = {
    total: scenes.length,
    selected: selectedScenes.length,
    onlyL1: 0,
    onlyL2: 0,
    mixed: 0,
    withShp: 0,
    withMtl: 0,
    mismatch: 0,
  }

  for (const scene of scenes) {
    const levels = getSceneAvailableLevels(scene)
    if (levels.length > 1) stats.mixed += 1
    else if (levels[0] === 'L2') stats.onlyL2 += 1
    else stats.onlyL1 += 1

    if (scene?.has_shp) stats.withShp += 1
    if (scene?.mtl_file) stats.withMtl += 1
  }

  if (preferredLevel) {
    stats.mismatch = selectedScenes.filter((scene) => !sceneSupportsLevel(scene, preferredLevel)).length
  }

  return stats
}

function inferUniformSceneLevel(scenes = []) {
  const stats = buildSceneStats(scenes, getAllSceneSelectionKeys(scenes))
  if (!stats.total) return ''
  if (stats.onlyL1 === stats.total) return 'L1'
  if (stats.onlyL2 === stats.total) return 'L2'
  return ''
}

function isSceneSelected(scene, selectedValues = []) {
  return sceneMatchesSelection(scene, new Set(normalizeSceneSelections(selectedValues, [scene]) || []))
    || sceneMatchesSelection(scene, new Set(Array.isArray(selectedValues) ? selectedValues : []))
}

function findNodeByType(type) {
  return state.nodes.find((node) => node.type === type) || null
}

function getDownstreamInputNode(sourceNodeId) {
  const edge = state.edges.find((item) => item.source === sourceNodeId)
  return edge ? state.nodes.find((node) => node.id === edge.target && node.type === 'input') || null : null
}

function getUpstreamDataDirNode(targetNodeId) {
  const edge = state.edges.find((item) => item.target === targetNodeId)
  return edge ? state.nodes.find((node) => node.id === edge.source && node.type === 'datadir') || null : null
}

function evaluateSavedClipCoverage(nodeData = {}) {
  const roi = normalizeBbox(parseExtentText(nodeData.clip_extent))
  const selectedScenes = getWorkflowSelectedScenes()
  const coverageBboxes = selectedScenes.map((scene) => normalizeBbox(scene.footprint_bbox)).filter(Boolean)
  if (!roi || !coverageBboxes.length) {
    return { status: 'unknown', invalid: false, message: '' }
  }

  if (findNodeByType('mosaic')) {
    const result = assessCoverage(roi, coverageBboxes)
    return {
      status: result.status,
      invalid: result.status === 'partial' || result.status === 'outside',
      message: result.status === 'inside'
        ? '共享 ROI 位于镶嵌覆盖范围内'
        : '共享 ROI 超出镶嵌覆盖范围',
    }
  }

  const invalidScenes = selectedScenes.filter((scene) => {
    const result = assessCoverage(roi, scene.footprint_bbox ? [scene.footprint_bbox] : [])
    return result.status === 'partial' || result.status === 'outside'
  })
  const unionCoverage = assessCoverage(roi, coverageBboxes)
  if (invalidScenes.length && unionCoverage.status === 'inside') {
    return {
      status: 'partial',
      invalid: true,
      message: '当前 ROI 需要多景联合覆盖；请先添加 mosaic 节点，再执行共享裁剪',
    }
  }
  return {
    status: invalidScenes.length ? 'partial' : 'inside',
    invalid: invalidScenes.length > 0,
    message: invalidScenes.length ? '共享 ROI 超出部分场景覆盖范围' : '共享 ROI 位于所有场景覆盖范围内',
  }
}

function isNodeConfigured(node) {
  const data = node?.data || {}
  switch (node?.type) {
    case 'datadir':
      return !!data.root_dir && (data.scenes?.length ?? 0) > 0
    case 'input':
      return (data.scenes?.length ?? 0) > 0 ? (data.selectedScenes?.length ?? 0) > 0 : !!data.band_dir
    case 'output':
      return !!data.output_dir
    case 'clip':
      return !!(data.clip_extent || data.clip_shapefile)
    case 'mosaic':
      return !!String(data.output_name || '').trim()
    case 'synthesis':
      return (data.composites?.length ?? 0) > 0 || !!data.custom_formula
    case 'atmospheric':
      return !!data.method
    case 'radiometric':
    case 'conditional':
      return true
    default:
      return true
  }
}

const workflowDataDirNode = computed(() => findNodeByType('datadir'))
const workflowInputNode = computed(() => findNodeByType('input'))
const workflowScenes = computed(() => {
  if (workflowInputNode.value?.data?.scenes?.length) return workflowInputNode.value.data.scenes
  if (workflowDataDirNode.value?.data?.scenes?.length) return workflowDataDirNode.value.data.scenes
  return []
})

const workflowSelectedScenes = computed(() => {
  if (workflowInputNode.value?.data?.scenes?.length) return workflowInputNode.value.data.selectedScenes || []
  if (workflowDataDirNode.value?.data?.scenes?.length) return workflowDataDirNode.value.data.selectedScenes || []
  return []
})

const workflowPreferredLevel = computed(() => normalizeProductLevel(workflowInputNode.value?.data?.product_level) || '')
const workflowSceneStats = computed(() => buildSceneStats(workflowScenes.value, workflowSelectedScenes.value, workflowPreferredLevel.value))
const workflowStatus = computed(() => {
  const outputNode = findNodeByType('output')
  const inputNode = workflowInputNode.value
  const dataDirNode = workflowDataDirNode.value
  const mosaicNode = findNodeByType('mosaic')
  const clipNode = findNodeByType('clip')
  const hasSingleInput = !!inputNode?.data?.band_dir && !(inputNode?.data?.scenes?.length ?? 0)
  const effectiveSceneCount = workflowSceneStats.value.selected || (hasSingleInput ? 1 : 0)

  if (state.submitting) {
    return {
      label: '提交中',
      tone: 'info',
      description: '正在将当前批处理流程提交到任务队列。',
    }
  }

  if (!outputNode?.data?.output_dir) {
    return {
      label: '待配置输出',
      tone: 'warn',
      description: '先为输出节点选择输出根目录，批处理结果会写入该位置。',
    }
  }

  if (!isFlowConnected()) {
    return {
      label: '流程未连通',
      tone: 'warn',
      description: '请保持从输入到输出的完整路径，避免任务提交后无效。',
    }
  }

  if ((dataDirNode?.data?.scenes?.length ?? 0) > 0 && workflowSceneStats.value.selected === 0) {
    return {
      label: '未选择场景',
      tone: 'warn',
      description: '当前已扫描到场景，但没有勾选任何待处理场景。',
    }
  }

  if (workflowSceneStats.value.mismatch > 0) {
    return {
      label: '级别需确认',
      tone: 'warn',
      description: `当前有 ${workflowSceneStats.value.mismatch} 个已选场景不包含 ${workflowPreferredLevel.value || '当前'} 产品，提交后可能失败。`,
    }
  }

  if (mosaicNode && effectiveSceneCount < 2) {
    return {
      label: '镶嵌场景不足',
      tone: 'warn',
      description: 'mosaic 节点至少需要 2 个已选场景，当前数量不足。',
    }
  }

  if (clipNode) {
    const clipCoverage = evaluateSavedClipCoverage(clipNode.data || {})
    if (clipCoverage.invalid) {
      return {
        label: 'ROI 越界',
        tone: 'warn',
        description: clipCoverage.message,
      }
    }
  }

  if ((dataDirNode?.data?.scenes?.length ?? 0) > 0 || hasSingleInput) {
    return {
      label: '可提交',
      tone: 'ok',
      description: mosaicNode
        ? `流程已就绪，预计提交 1 个镶嵌聚合任务（${effectiveSceneCount} 景）。`
        : `流程已就绪，预计提交 ${effectiveSceneCount} 个任务。`,
    }
  }

  return {
    label: '待扫描目录',
    tone: 'neutral',
    description: '先配置数据目录或单场景输入，系统会在这里汇总状态。',
  }
})

const panelScenes = computed(() => (Array.isArray(state.editingParams.scenes) ? state.editingParams.scenes : []))

const panelPreferredLevel = computed(() => {
  if (state.selectedNode?.type === 'input') {
    return normalizeProductLevel(state.editingParams.product_level || state.selectedNode?.data?.product_level) || 'L1'
  }

  if (state.selectedNode?.type === 'datadir') {
    const inputNode = getDownstreamInputNode(state.selectedNode.id)
    return normalizeProductLevel(inputNode?.data?.product_level) || inferUniformSceneLevel(panelScenes.value)
  }

  return normalizeProductLevel(state.editingParams.product_level) || ''
})

const panelSceneStats = computed(() => buildSceneStats(panelScenes.value, state.editingParams.selectedScenes, panelPreferredLevel.value))

const clipPreviewStatusText = computed(() => {
  if (state.clipCoverageLoading) return '正在加载影像覆盖范围...'
  if (state.clipCoverageError) return state.clipCoverageError
  if (state.clipPreviewLoading) return '正在读取本地矢量并生成预览...'
  if (batchClipCoverageValidation.value.status === 'inside') {
    return batchClipCoverageValidation.value.message
  }
  if (batchClipCoverageValidation.value.status === 'partial') {
    return batchClipCoverageValidation.value.message
  }
  if (batchClipCoverageValidation.value.status === 'outside') {
    return batchClipCoverageValidation.value.message
  }
  if (state.clipPreviewGeoJson) {
    return `${state.clipPreviewLabel || '矢量范围'}，${state.clipPreviewFeatureCount || 0} 个要素`
  }
  if (state.clipPreviewBbox) return '当前显示矩形范围，保存后会作为共享 ROI'
  return '可框选共享 ROI，或通过本地 .shp 路径请求预览'
})

const batchClipCoverageValidation = computed(() => {
  const roi = normalizeBbox(state.clipPreviewBbox || parseExtentText(state.editingParams.clip_extent))
  const coverageBboxes = state.clipCoverageBboxes.map((bbox) => normalizeBbox(bbox)).filter(Boolean)
  if (!roi || !coverageBboxes.length) {
    return {
      status: 'unknown',
      tone: 'neutral',
      message: state.clipCoverageError || '尚未加载影像覆盖范围或 ROI',
      invalid: false,
    }
  }

  const mosaicNode = findNodeByType('mosaic')
  if (mosaicNode) {
    const result = assessCoverage(roi, coverageBboxes)
    if (result.status === 'inside') {
      return { status: 'inside', tone: 'ok', message: `ROI 完全位于 ${coverageBboxes.length} 景镶嵌覆盖范围内`, invalid: false }
    }
    if (result.status === 'outside') {
      return { status: 'outside', tone: 'warn', message: 'ROI 完全不在选中场景的联合覆盖范围内', invalid: true }
    }
    return { status: 'partial', tone: 'warn', message: 'ROI 部分超出选中场景的联合覆盖范围', invalid: true }
  }

  const selectedScenes = getWorkflowSelectedScenes()
  const invalidScenes = selectedScenes
    .map((scene) => ({
      scene,
      coverage: assessCoverage(roi, scene.footprint_bbox ? [scene.footprint_bbox] : []),
    }))
    .filter((item) => item.coverage.status === 'partial' || item.coverage.status === 'outside')

  if (!invalidScenes.length) {
    return {
      status: 'inside',
      tone: 'ok',
      message: `ROI 完全位于全部 ${Math.max(selectedScenes.length, coverageBboxes.length)} 个已选场景覆盖范围内`,
      invalid: false,
    }
  }

  const unionCoverage = assessCoverage(roi, coverageBboxes)
  if (unionCoverage.status === 'inside') {
    return {
      status: 'partial',
      tone: 'warn',
      message: '当前 ROI 需要多景联合覆盖；请先添加 mosaic 节点，再执行共享裁剪',
      invalid: true,
    }
  }

  const allOutside = invalidScenes.every((item) => item.coverage.status === 'outside')
  return {
    status: allOutside ? 'outside' : 'partial',
    tone: 'warn',
    message: `${invalidScenes.length}/${selectedScenes.length} 个已选场景不能完整覆盖当前 ROI`,
    invalid: true,
  }
})

const inputStrategy = computed(() => {
  if (state.selectedNode?.type !== 'input') {
    return { title: '', copy: '', tone: 'neutral' }
  }

  if (!panelScenes.value.length) {
    return {
      title: '手动指定产品级别',
      copy: '单场景输入不会自动扫描 L1/L2 集合，请按波段目录的实际来源选择处理级别。',
      tone: 'neutral',
    }
  }

  const selectedScenes = getSelectedSceneItems(panelScenes.value, state.editingParams.selectedScenes)
  const selectedLevel = panelPreferredLevel.value
  const selectedStats = buildSceneStats(selectedScenes, getAllSceneSelectionKeys(selectedScenes), selectedLevel)

  if (selectedStats.total && selectedStats.onlyL1 === selectedStats.total) {
    return {
      title: '已自动识别为 L1 产品',
      copy: '当前选中的场景全部为 L1，可直接沿传统预处理链继续执行。',
      tone: 'ok',
    }
  }

  if (selectedStats.total && selectedStats.onlyL2 === selectedStats.total) {
    return {
      title: '已自动识别为 L2 产品',
      copy: '当前选中的场景全部为 L2，可直接使用地表反射率并跳过大气校正。',
      tone: 'ok',
    }
  }

  return {
    title: '检测到混合产品',
    copy: `当前批次同时包含 L1、L2 或混合场景，请明确本次处理级别。系统会保留所有场景，并显式标记不匹配项。`,
    tone: 'warn',
  }
})

const panelSummary = computed(() => {
  const node = state.selectedNode
  if (!node) return null

  const data = state.editingParams || {}
  const stats = panelSceneStats.value

  if (node.type === 'datadir') {
    const ready = !!data.root_dir && stats.total > 0
    return {
      label: '数据目录',
      title: ready ? '场景扫描已完成' : '等待场景扫描',
      badge: ready ? '已识别' : '待配置',
      tone: ready ? 'ok' : 'warn',
      copy: data.root_dir
        ? `当前目录 ${shortPath(data.root_dir, 3)} ${ready ? '已完成场景识别' : '尚未生成场景列表'}。`
        : '选择一个包含多个场景子目录的根目录，系统会自动扫描 SHP、MTL 与可用产品级别。',
      metrics: [
        { label: '总场景', value: stats.total },
        { label: '已选', value: stats.selected },
        { label: '混合', value: stats.mixed },
        { label: '含 SHP', value: stats.withShp },
      ],
      note: panelPreferredLevel.value
        ? `当前下游输入节点会优先按 ${panelPreferredLevel.value} 处理场景。`
        : '若目录中存在混合产品，建议在输入节点中明确选择本次处理级别。',
    }
  }

  if (node.type === 'input') {
    if (panelScenes.value.length) {
      const ready = stats.selected > 0
      return {
        label: '输入场景',
        title: ready ? '批处理场景已就绪' : '尚未勾选场景',
        badge: ready ? '待提交' : '待选择',
        tone: ready ? (stats.mismatch > 0 ? 'warn' : 'ok') : 'warn',
        copy: `${stats.selected} / ${stats.total} 个场景将按 ${panelPreferredLevel.value || '自动'} 进入后续流程。`,
        metrics: [
          { label: '仅 L1', value: stats.onlyL1 },
          { label: '仅 L2', value: stats.onlyL2 },
          { label: '混合', value: stats.mixed },
          { label: '不匹配', value: stats.mismatch },
        ],
        note: stats.mismatch > 0
          ? '不匹配场景仍会保留在列表中，以便你手动判断是否继续提交。'
          : '当前选择的处理级别与已选场景兼容，可直接提交批处理任务。',
      }
    }

    const ready = !!data.band_dir
    return {
      label: '单场景输入',
      title: ready ? '单场景输入已配置' : '等待波段目录',
      badge: ready ? '已配置' : '待配置',
      tone: ready ? 'ok' : 'warn',
      copy: ready
        ? `将按 ${normalizeProductLevel(data.product_level) || 'L1'} 处理 ${data.scene_name || shortPath(data.band_dir)}。`
        : '请指定单场景波段目录，并补充产品级别以确保预处理链正确。',
      metrics: [
        { label: '级别', value: normalizeProductLevel(data.product_level) || 'L1' },
        { label: 'MTL', value: data.mtl_file ? '有' : '无' },
        { label: 'QA', value: data.qa_band ? '有' : '无' },
        { label: 'RADSAT', value: data.qa_radsat_band ? '有' : '无' },
      ],
      note: '单场景模式不会自动推断目录中的 L1/L2 混合情况，建议按实际数据来源手动确认。',
    }
  }

  if (node.type === 'atmospheric') {
    return {
      label: '大气校正',
      title: '大气校正策略',
      badge: data.method || 'DOS',
      tone: 'info',
      copy: `当前方法为 ${data.method || 'DOS'}，${data.apply_cloud_mask ? '已启用' : '未启用'}云掩膜。`,
      metrics: [
        { label: '方法', value: data.method || 'DOS' },
        { label: '云掩膜', value: data.apply_cloud_mask ? '开启' : '关闭' },
      ],
      note: 'L2 输入时该节点会自动降级为仅应用 QA 掩膜。',
    }
  }

  if (node.type === 'mosaic') {
    const selectedSceneCount = workflowSceneStats.value.selected || (workflowInputNode.value?.data?.band_dir ? 1 : 0)
    const ready = !!String(data.output_name || '').trim()
    const enoughScenes = selectedSceneCount >= 2
    const displayBalanceEnabled = data.display_balance_enabled !== false
    return {
      label: '影像镶嵌',
      title: ready ? '聚合镶嵌任务已配置' : '等待镶嵌输出名',
      badge: ready ? `${selectedSceneCount} 景` : '待配置',
      tone: ready && enoughScenes ? 'ok' : 'warn',
      copy: ready
        ? `多景同名波段会先完成预处理，再统一镶嵌到 ${data.output_name || 'mosaic'} 目录。${displayBalanceEnabled ? '显示型合成会额外做匀色。' : '显示型合成保持原始镶嵌色调。'}`
        : '请指定镶嵌结果目录名，系统会将多景结果聚合为单个任务执行。',
      metrics: [
        { label: '输出名', value: data.output_name || 'mosaic' },
        { label: '中间产物', value: data.keep_intermediate ? '保留' : '清理' },
        { label: '显示匀色', value: displayBalanceEnabled ? '开启' : '关闭' },
        { label: '场景数', value: selectedSceneCount },
      ],
      note: enoughScenes
        ? '镶嵌后的共享结果会继续进入下游裁剪、合成或指数节点。'
        : 'mosaic 节点至少需要 2 个已选场景；单景或空批次会在提交时被拒绝。',
    }
  }

  if (node.type === 'clip') {
    const ready = !!(data.clip_shapefile || data.clip_extent)
    const sourceLabel = getClipSourceLabel(data.clip_source)
    const clipLabel = data.clip_label || (data.clip_shapefile ? shortPath(data.clip_shapefile, 3) : (data.clip_extent || ''))
    const coverage = evaluateSavedClipCoverage(data)
    return {
      label: '区域裁剪',
      title: ready ? (data.clip_confirmed ? '共享 ROI 已确认' : '裁剪条件已填写') : '等待裁剪条件',
      badge: ready ? (coverage.invalid ? '越界' : (data.clip_confirmed ? '已确认' : '待确认')) : '待配置',
      tone: ready ? (coverage.invalid ? 'warn' : (data.clip_confirmed ? 'ok' : 'warn')) : 'neutral',
      copy: data.clip_shapefile
        ? `矢量预览：${clipLabel}，提交时优先使用本地路径 ${shortPath(data.clip_shapefile, 3)}。`
        : (data.clip_extent || '可使用地图框选、手填 bbox 或本地 SHP 作为共享裁剪范围。'),
      metrics: [
        { label: '来源', value: sourceLabel },
        { label: '要素', value: data.clip_feature_count || (data.clip_extent ? 1 : 0) },
        { label: '矢量路径', value: data.clip_shapefile ? '已填' : '未填' },
      ],
      note: coverage.invalid
        ? coverage.message
        : (
          findNodeByType('mosaic')
            ? 'mosaic 下游只能使用一个共享 ROI；若切换为 bbox，建议直接在地图重新框选。'
            : '若接入 SHP 检测节点，系统可按场景自动切换到对应的矢量文件。'
        ),
    }
  }

  if (node.type === 'synthesis') {
    const compositeCount = (data.composites || []).length
    const ready = compositeCount > 0 || !!data.custom_formula
    return {
      label: '合成指数',
      title: ready ? '输出组合已选择' : '等待选择输出项',
      badge: ready ? `${compositeCount + (data.custom_formula ? 1 : 0)} 项` : '未配置',
      tone: ready ? 'ok' : 'neutral',
      copy: ready
        ? '系统将按所选组合与公式生成额外的合成图像和指数结果。'
        : '可同时选择预设组合与自定义公式，不会影响主处理链。',
      metrics: [
        { label: '预设', value: compositeCount },
        { label: '自定义', value: data.custom_formula ? '1' : '0' },
      ],
      note: '若不选择任何输出项，批处理仍会执行主链，只是不生成附加指数结果。',
    }
  }

  if (node.type === 'output') {
    const ready = !!data.output_dir
    const mosaicNode = findNodeByType('mosaic')
    return {
      label: '输出配置',
      title: ready ? '输出目录已配置' : '等待输出目录',
      badge: ready ? '已配置' : '待配置',
      tone: ready ? 'ok' : 'warn',
      copy: ready ? shortPath(data.output_dir, 3) : '请选择批处理结果的输出根目录。',
      metrics: [
        { label: '输出目录', value: ready ? '已选' : '未选' },
      ],
      note: mosaicNode
        ? '存在 mosaic 节点时，输出根目录下会生成单个镶嵌结果目录。'
        : '批量模式下每个场景会在输出根目录下自动创建同名子目录。',
    }
  }

  if (node.type === 'radiometric') {
    return {
      label: '辐射定标',
      title: '固定主链步骤',
      badge: '自动',
      tone: 'neutral',
      copy: '辐射定标会在 L1 输入时自动执行，用于完成 DN 到反射率的基础转换。',
      metrics: [
        { label: 'L1', value: '执行' },
        { label: 'L2', value: '跳过' },
      ],
      note: '该节点无需手动配置，只负责说明主链中的自动化行为。',
    }
  }

  if (node.type === 'conditional') {
    return {
      label: 'SHP 检测',
      title: '按场景路由裁剪',
      badge: '只读',
      tone: 'neutral',
      copy: '系统会根据场景目录内是否存在 SHP 自动决定是否进入裁剪分支。',
      metrics: [
        { label: '存在 SHP', value: '走“是”' },
        { label: '缺少 SHP', value: '走“否”' },
      ],
      note: '该节点用于描述流程逻辑，不需要额外输入参数。',
    }
  }

  return null
})

const showSidePanelFooter = computed(() => {
  return !!state.selectedNode && !['radiometric', 'conditional'].includes(state.selectedNode.type)
})

const queueSummaryCards = computed(() => [
  { label: '运行中', value: state.queueStats.running || 0, tone: 'running' },
  { label: '等待中', value: state.queueStats.queued || 0, tone: 'queued' },
  { label: '已完成', value: state.queueStats.completed || 0, tone: 'success' },
  { label: '失败', value: state.queueStats.failed || 0, tone: 'failed' },
])

function setPriority(priority) {
  state.priority = priority
}

function setEditingProductLevel(level) {
  state.editingParams.product_level = level
}

function selectAllScenes() {
  if (panelScenes.value.length) {
    state.editingParams.selectedScenes = getAllSceneSelectionKeys(panelScenes.value)
  }
}

function selectNoneScenes() {
  state.editingParams.selectedScenes = []
}

let dragNodeType = null
let nodeCounter = 100
const NODE_HALF_WIDTH = 85
const NODE_HALF_HEIGHT = 42

function updateInteractionMode() {
  if (typeof window === 'undefined') return
  const width = window.innerWidth
  const coarsePointer = window.matchMedia('(pointer: coarse)').matches || navigator.maxTouchPoints > 0
  supportsTouch.value = coarsePointer
  isPhoneViewport.value = width <= 767
  isTabletViewport.value = width > 767 && width <= 1180
  if (!showMobilePaletteDrawer.value) {
    state.paletteDrawerOpen = false
  }
}

function togglePaletteDrawer() {
  if (!showMobilePaletteDrawer.value) return
  state.paletteDrawerOpen = !state.paletteDrawerOpen
}

function getDefaultNodeData(type) {
  const defaults = {
    atmospheric: { method: 'DOS', apply_cloud_mask: false },
    conditional: {},
    clip: {
      clip_extent: '',
      clip_shapefile: '',
      clip_source: '',
      clip_label: '',
      clip_feature_count: 0,
      clip_confirmed: false,
    },
    mosaic: { output_name: 'mosaic', keep_intermediate: false, display_balance_enabled: true },
    synthesis: { composites: [], custom_formula: '', custom_name: '' },
  }
  return JSON.parse(JSON.stringify(defaults[type] || {}))
}

function resolveNodePosition(screenPoint, offsetIndex = 0) {
  const rect = canvasWrapperRef.value?.getBoundingClientRect()
  const fallbackPoint = rect
    ? {
        x: rect.left + rect.width * 0.55,
        y: rect.top + Math.max(120, rect.height * 0.42),
      }
    : { x: 320, y: 220 }

  const basePoint = screenPoint || fallbackPoint
  const flowPoint = screenToFlowCoordinate(basePoint)
  const spreadX = (offsetIndex % 3) * 28
  const spreadY = Math.floor(offsetIndex / 3) * 22

  return {
    x: Math.max(24, flowPoint.x - NODE_HALF_WIDTH + spreadX),
    y: Math.max(24, flowPoint.y - NODE_HALF_HEIGHT + spreadY),
  }
}

function createPaletteNode(nodeType, screenPoint = null) {
  const offsetIndex = state.nodes.filter((node) => node.deletable).length
  const id = `${nodeType}-${++nodeCounter}`
  state.nodes.push({
    id,
    type: nodeType,
    position: resolveNodePosition(screenPoint, offsetIndex),
    data: getDefaultNodeData(nodeType),
    deletable: true,
  })
}

function handlePaletteActivate(nt) {
  if (supportsTouch.value) {
    addNodeFromPalette(nt)
  }
}

function addNodeFromPalette(nt) {
  createPaletteNode(nt.type)
  state.paletteDrawerOpen = false
}

function onDragStart(event, nt) {
  if (supportsTouch.value) return
  dragNodeType = nt.type
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.dropEffect = 'move'
    event.dataTransfer.setData('application/vueflow', nt.type)
    event.dataTransfer.setData('text/plain', nt.type)
  }
}

function onDragEnd() {
  dragNodeType = null
}

function onDrop(event) {
  const droppedType = dragNodeType || event.dataTransfer?.getData('application/vueflow') || event.dataTransfer?.getData('text/plain')
  if (!droppedType) return
  createPaletteNode(droppedType, { x: event.clientX, y: event.clientY })
  dragNodeType = null
}

async function onNodeClick({ node }) {
  state.selectedNode = node
  state.editingParams = JSON.parse(JSON.stringify(node.data))
  state.paletteDrawerOpen = false
  state.showSidePanel = true

  if (node.type === 'datadir') {
    syncSceneSelections(state.editingParams, { defaultToAll: true })
  }

  if (node.type === 'input') {
    const dataDirNode = getUpstreamDataDirNode(node.id)
    if (dataDirNode?.data.scenes?.length) {
      state.editingParams.scenes = dataDirNode.data.scenes
      if (Array.isArray(node.data.selectedScenes)) {
        state.editingParams.selectedScenes = normalizeSceneSelections(node.data.selectedScenes, dataDirNode.data.scenes)
      } else {
        state.editingParams.selectedScenes = Array.isArray(dataDirNode.data.selectedScenes)
          ? normalizeSceneSelections(dataDirNode.data.selectedScenes, dataDirNode.data.scenes)
          : getAllSceneSelectionKeys(dataDirNode.data.scenes)
      }

      if (
        !state.editingParams.selectedScenes.length
        && !Array.isArray(node.data.selectedScenes)
        && !Array.isArray(dataDirNode.data.selectedScenes)
      ) {
        state.editingParams.selectedScenes = getAllSceneSelectionKeys(dataDirNode.data.scenes)
      }
    }

    syncSceneSelections(state.editingParams, { defaultToAll: true })
  }

  if (node.type === 'mosaic') {
    state.editingParams.display_balance_enabled = state.editingParams.display_balance_enabled !== false
  }

  if (node.type === 'clip') {
    await restoreClipPreviewFromNode(state.editingParams)
    await restoreClipCoverage()
  } else {
    resetClipPreview()
    resetClipCoverage()
  }
}

function onConnect(params) {
  const id = `e-${params.source}-${params.sourceHandle || 'out'}-${params.target}-${params.targetHandle || 'in'}`
  if (!state.edges.find((edge) => edge.id === id)) {
    state.edges.push({ ...params, id })
  }
}

function onEdgesChange(changes) {
  state.edges = applyEdgeChanges(changes, state.edges)
}

function onNodesChange(changes) {
  state.nodes = applyNodeChanges(changes, state.nodes)
}

function closeSidePanel() {
  state.showSidePanel = false
  state.selectedNode = null
  state.editingParams = {}
  resetClipPreview()
  resetClipCoverage()
}

async function saveNodeParams() {
  if (!state.selectedNode) return
  const node = state.nodes.find((item) => item.id === state.selectedNode.id)
  if (!node) return

  syncSceneSelections(state.editingParams)

  if (node.type === 'clip') {
    state.editingParams.clip_shapefile = String(state.editingParams.clip_shapefile || '').trim()
    state.editingParams.clip_extent = String(state.editingParams.clip_extent || '').trim()

    if (!state.editingParams.clip_shapefile && !parseExtentText(state.editingParams.clip_extent)) {
      state.editingParams.clip_source = ''
      state.editingParams.clip_label = ''
      state.editingParams.clip_feature_count = 0
      state.editingParams.clip_confirmed = false
    } else if (!state.editingParams.clip_shapefile && parseExtentText(state.editingParams.clip_extent)) {
      state.editingParams.clip_source = state.editingParams.clip_source || 'bbox'
      state.editingParams.clip_label = state.editingParams.clip_label || '矩形范围'
      state.editingParams.clip_feature_count = Number(state.editingParams.clip_feature_count || 1)
      state.editingParams.clip_confirmed = state.editingParams.clip_confirmed !== false
    } else if (state.editingParams.clip_shapefile) {
      state.editingParams.clip_source = state.editingParams.clip_source || 'filesystem'
      state.editingParams.clip_label = state.editingParams.clip_label || shortPath(state.editingParams.clip_shapefile, 3)
      state.editingParams.clip_confirmed = state.editingParams.clip_confirmed !== false
    }
  }

  if (node.type === 'mosaic') {
    state.editingParams.output_name = String(state.editingParams.output_name || '').trim() || 'mosaic'
    state.editingParams.keep_intermediate = Boolean(state.editingParams.keep_intermediate)
    state.editingParams.display_balance_enabled = state.editingParams.display_balance_enabled !== false
  }

  Object.assign(node.data, state.editingParams)

  if (node.type === 'datadir' && node.data.root_dir) {
    await scanAndPropagateScenes(node.id)
  }

  if (node.type === 'input') {
    const dataDirNode = getUpstreamDataDirNode(node.id)
    if (dataDirNode) {
      dataDirNode.data.selectedScenes = [...(node.data.selectedScenes || [])]
    }
  }

  closeSidePanel()
}

async function scanAndPropagateScenes(dataDirNodeId) {
  const dataDirNode = state.nodes.find((node) => node.id === dataDirNodeId)
  if (!dataDirNode?.data.root_dir) return

  try {
    const previousDataDirSelections = Array.isArray(dataDirNode.data.selectedScenes)
      ? [...dataDirNode.data.selectedScenes]
      : null

    const resp = await fetch(`${props.apiBase}/filesystem/scan_scenes?path=${encodeURIComponent(dataDirNode.data.root_dir)}`)
    if (!resp.ok) return
    const data = await resp.json()

    dataDirNode.data.scenes = data.scenes
    dataDirNode.data.selectedScenes = Array.isArray(previousDataDirSelections)
      ? (() => {
          const normalized = normalizeSceneSelections(previousDataDirSelections, data.scenes)
          return normalized.length || previousDataDirSelections.length === 0
            ? normalized
            : getAllSceneSelectionKeys(data.scenes)
        })()
      : getAllSceneSelectionKeys(data.scenes)

    const inputNode = getDownstreamInputNode(dataDirNodeId)
    if (inputNode) {
      const previousInputSelections = Array.isArray(inputNode.data.selectedScenes)
        ? [...inputNode.data.selectedScenes]
        : null

      inputNode.data.scenes = data.scenes
      inputNode.data.selectedScenes = Array.isArray(previousInputSelections)
        ? (() => {
            const normalized = normalizeSceneSelections(previousInputSelections, data.scenes)
            return normalized.length || previousInputSelections.length === 0
              ? normalized
              : [...dataDirNode.data.selectedScenes]
          })()
        : [...dataDirNode.data.selectedScenes]

      const levels = [...new Set(data.scenes.map((scene) => normalizeProductLevel(scene.product_level)).filter(Boolean))]
      if (levels.length === 1) inputNode.data.product_level = levels[0]
    }
  } catch (_) {}
}

function confirmResetCanvas() {
  if (state.nodes.some((node) => node.data && Object.values(node.data).some((value) => value && value !== '' && !Array.isArray(value)))) {
    if (!confirm('确认重置画布？所有节点配置将被清空。')) return
  }
  resetCanvas()
}

function resetCanvas() {
  state.nodes = createInitialNodes()
  state.edges = createInitialEdges()
  closeSidePanel()
  nodeCounter = 100
  state.paletteDrawerOpen = false
}

function miniMapColor(node) {
  const map = {
    datadir: '#6f848d',
    input: '#3b7080',
    radiometric: '#78848b',
    atmospheric: '#628273',
    conditional: '#9a855b',
    mosaic: '#546f8d',
    clip: '#9f8266',
    synthesis: '#80789a',
    output: '#4f7d83',
  }
  return map[node.type] || '#98a5ab'
}

function isFlowConnected() {
  const startNode = findNodeByType('datadir') || findNodeByType('input')
  const outputNode = findNodeByType('output')
  if (!startNode || !outputNode) return false

  const visited = new Set()
  const queue = [startNode.id]

  while (queue.length) {
    const current = queue.shift()
    if (current === outputNode.id) return true
    if (visited.has(current)) continue
    visited.add(current)
    state.edges.filter((edge) => edge.source === current).forEach((edge) => queue.push(edge.target))
  }

  return false
}

async function submitTask() {
  const outputNode = findNodeByType('output')
  if (!outputNode?.data.output_dir) {
    emit('toast', { type: 'error', message: '请先配置输出节点的输出目录' })
    return
  }

  if (!isFlowConnected()) {
    emit('toast', { type: 'error', message: '流程未完整连接，请确保存在通往输出节点的完整路径' })
    return
  }

  const clipNode = findNodeByType('clip')
  if (clipNode) {
    const clipCoverage = evaluateSavedClipCoverage(clipNode.data || {})
    if (clipCoverage.invalid) {
      emit('toast', { type: 'error', message: clipCoverage.message })
      return
    }
  }

  const batchName = `graph_batch_${Date.now()}`
  const payload = {
    batch_name: batchName,
    nodes: state.nodes.map((node) => ({ id: node.id, type: node.type, data: node.data })),
    edges: state.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle ?? null,
      targetHandle: edge.targetHandle ?? null,
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
  } catch (error) {
    emit('toast', { type: 'error', message: error.message })
  } finally {
    state.submitting = false
  }
}

async function fetchQueue() {
  try {
    const resp = await fetch(`${props.apiBase}/tasks/queue`)
    if (!resp.ok) return
    const data = await resp.json()
    state.taskQueue = data.jobs || []
    state.queueStats = {
      total: data.total || 0,
      running: data.running || 0,
      queued: data.queued || 0,
      completed: data.completed || 0,
      failed: data.failed || 0,
    }
  } catch (_) {}
}

async function cancelJob(jobId) {
  try {
    await fetch(`${props.apiBase}/batch/job/${jobId}/cancel`, { method: 'POST' })
    await fetchQueue()
  } catch (_) {}
}

async function clearQueue() {
  const cancellable = state.taskQueue.filter((job) => ['queued', 'pending', 'paused'].includes(job.status))
  if (!cancellable.length) return
  if (!confirm(`确认取消 ${cancellable.length} 个等待中的任务？`)) return
  await Promise.all(cancellable.map((job) => cancelJob(job.job_id)))
}

async function pickPath(field) {
  const config = PICKER_CONFIG[field] || { mode: 'directory', title: '选择路径', allowedSuffixes: [] }
  const initialValue = String(state.editingParams[field] || '').trim()
  state.pickerField = field
  state.pickerMode = config.mode
  state.pickerTitle = config.title
  state.pickerAllowedSuffixes = Array.isArray(config.allowedSuffixes) ? [...config.allowedSuffixes] : []
  state.pickerCurrentPath = ''
  state.pickerBreadcrumb = [{ label: '根目录', path: '' }]
  state.pickerRoots = []
  state.pickerItems = []
  state.pickerFiles = []
  state.pickerSelectedPath = ''
  state.pickerSelectedKind = ''
  state.showPicker = true

  let initialDir = ''
  let preselectPath = ''
  if (initialValue) {
    if (config.mode === 'file') {
      const { directory } = splitParentPath(initialValue)
      initialDir = directory
      preselectPath = initialValue
    } else {
      initialDir = initialValue
    }
  }

  await loadPickerDir('')
  if (initialDir) {
    const loaded = await loadPickerDir(initialDir, { preselectPath })
    if (!loaded) {
      await loadPickerDir('')
    }
  }
  state.showPicker = true
}

function splitParentPath(path) {
  const raw = String(path || '').trim()
  if (!raw) return { directory: '', basename: '' }
  const slashIndex = Math.max(raw.lastIndexOf('/'), raw.lastIndexOf('\\'))
  if (slashIndex < 0) return { directory: '', basename: raw }
  let directory = raw.slice(0, slashIndex)
  if (/^[A-Za-z]:$/.test(directory)) {
    directory = `${directory}\\`
  }
  return {
    directory,
    basename: raw.slice(slashIndex + 1),
  }
}

function samePickerPath(left, right) {
  return String(left || '').replace(/\\/g, '/').toLowerCase() === String(right || '').replace(/\\/g, '/').toLowerCase()
}

function pathWithinPickerRoot(candidate, rootPath) {
  const left = String(candidate || '').replace(/\\/g, '/').toLowerCase()
  const right = String(rootPath || '').replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
  return left === right || left.startsWith(`${right}/`)
}

function buildPickerBreadcrumb(currentPath) {
  if (!currentPath) return [{ label: '根目录', path: '' }]

  const matchedRoot = state.pickerRoots
    .filter((item) => item?.path && pathWithinPickerRoot(currentPath, item.path))
    .sort((left, right) => String(right.path || '').length - String(left.path || '').length)[0]

  if (!matchedRoot?.path) {
    return [
      { label: '根目录', path: '' },
      { label: currentPath, path: currentPath },
    ]
  }

  const breadcrumbs = [
    { label: '根目录', path: '' },
    { label: matchedRoot.name || matchedRoot.path, path: matchedRoot.path },
  ]

  const normalizedCurrent = String(currentPath).replace(/\\/g, '/')
  const normalizedRoot = String(matchedRoot.path).replace(/\\/g, '/').replace(/\/+$/, '')
  const relativePath = normalizedCurrent === normalizedRoot
    ? ''
    : normalizedCurrent.slice(normalizedRoot.length).replace(/^\/+/, '')

  if (!relativePath) return breadcrumbs

  const separator = String(matchedRoot.path).includes('\\') ? '\\' : '/'
  let accPath = String(matchedRoot.path).replace(/[\\/]+$/, '')
  for (const segment of relativePath.split('/').filter(Boolean)) {
    accPath = `${accPath}${separator}${segment}`
    breadcrumbs.push({ label: segment, path: accPath })
  }
  return breadcrumbs
}

async function loadPickerDir(path, { preselectPath = '' } = {}) {
  try {
    const params = new URLSearchParams()
    if (path) params.set('path', path)
    if (state.pickerMode === 'file') {
      params.set('include_files', 'true')
      if (state.pickerAllowedSuffixes.length) {
        params.set('allowed_suffixes', state.pickerAllowedSuffixes.join(','))
      }
    }

    const query = params.toString()
    const resp = await fetch(`${props.apiBase}/filesystem/list_dirs${query ? `?${query}` : ''}`)
    if (!resp.ok) return false
    const data = await resp.json()
    state.pickerCurrentPath = data.current || path
    state.pickerItems = data.directories || []
    state.pickerFiles = data.files || []
    if (!state.pickerCurrentPath) {
      state.pickerRoots = state.pickerItems.map((item) => ({ name: item.name, path: item.path }))
    }

    if (state.pickerMode === 'file') {
      const matched = state.pickerFiles.find((item) => samePickerPath(item.path, preselectPath))
      state.pickerSelectedPath = matched?.path || ''
      state.pickerSelectedKind = matched ? 'file' : ''
    } else {
      state.pickerSelectedPath = state.pickerCurrentPath
      state.pickerSelectedKind = state.pickerCurrentPath ? 'directory' : ''
    }

    state.pickerBreadcrumb = buildPickerBreadcrumb(state.pickerCurrentPath)
    return true
  } catch (_) {
    return false
  }
}

async function onPickerItemClick(item) {
  await loadPickerDir(item.path)
}

function selectPickerFile(file) {
  state.pickerSelectedPath = file.path
  state.pickerSelectedKind = 'file'
}

async function navigatePicker(index) {
  const target = state.pickerBreadcrumb[index]
  await loadPickerDir(target?.path || '')
}

async function confirmPick() {
  const selectedPath = state.pickerMode === 'file' ? state.pickerSelectedPath : state.pickerCurrentPath
  if (!selectedPath) return
  if (state.selectedNode) {
    state.editingParams[state.pickerField] = selectedPath
    if (state.pickerField === 'clip_shapefile') {
      await loadClipVectorPreview(selectedPath, {
        syncExtent: !String(state.editingParams.clip_extent || '').trim(),
        silent: true,
      })
    }
  }
  state.showPicker = false
}

onMounted(() => {
  updateInteractionMode()
  window.addEventListener('resize', updateInteractionMode)
  fetchQueue()
  state.pollingTimer = setInterval(fetchQueue, 3000)
})

onUnmounted(() => {
  clearInterval(state.pollingTimer)
  window.removeEventListener('resize', updateInteractionMode)
})
</script>

<style scoped>
.batch-manager {
  --page-bg: #eef3f2;
  --surface: #ffffff;
  --surface-soft: #f8faf9;
  --surface-muted: #f2f5f4;
  --border: #d8e0dd;
  --border-strong: #c1ccc8;
  --text: #17201d;
  --text-soft: #5c6b66;
  --text-faint: #83928d;
  --accent: #1f7280;
  --accent-soft: #e6f0f2;
  --ok: #1b7a57;
  --ok-soft: #def3e9;
  --warn: #9d6b16;
  --warn-soft: #f9edd1;
  --danger: #b64537;
  --danger-soft: #f9e1dc;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background:
    radial-gradient(circle at top right, rgba(31, 114, 128, 0.08), transparent 24%),
    linear-gradient(180deg, #f4f7f6 0%, var(--page-bg) 100%);
  color: var(--text);
  overflow: hidden;
}

.toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px 14px;
  align-items: start;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid rgba(199, 210, 206, 0.8);
  backdrop-filter: blur(12px);
}

.toolbar-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.palette-title,
.group-label,
.section-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-faint);
}

.toolbar-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar-title {
  margin: 0;
  font-size: 18px;
  line-height: 1;
  letter-spacing: 0.02em;
}

.flow-status-badge,
.scene-badge,
.canvas-status-pill,
.panel-summary-badge,
.strategy-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid transparent;
  padding: 4px 9px;
  font-size: 10.5px;
  font-weight: 700;
  white-space: nowrap;
}

.flow-status-badge.is-ok,
.panel-summary-badge.is-ok,
.canvas-status-pill.is-ok,
.scene-badge.is-ok {
  background: var(--ok-soft);
  border-color: rgba(27, 122, 87, 0.18);
  color: var(--ok);
}

.flow-status-badge.is-warn,
.panel-summary-badge.is-warn,
.canvas-status-pill.is-warn,
.scene-badge.is-warn {
  background: var(--warn-soft);
  border-color: rgba(157, 107, 22, 0.18);
  color: var(--warn);
}

.flow-status-badge.is-info,
.panel-summary-badge.is-info,
.canvas-status-pill.is-info,
.scene-badge.is-info {
  background: var(--accent-soft);
  border-color: rgba(31, 114, 128, 0.18);
  color: var(--accent);
}

.flow-status-badge.is-neutral,
.panel-summary-badge.is-neutral,
.canvas-status-pill.is-neutral,
.scene-badge.is-neutral,
.scene-badge.is-muted {
  background: var(--surface-muted);
  border-color: rgba(130, 146, 141, 0.14);
  color: var(--text-soft);
}

.scene-badge.is-l1 {
  background: #e7eef9;
  border-color: rgba(60, 96, 142, 0.16);
  color: #3d5f8a;
}

.scene-badge.is-l2 {
  background: #e3f3ec;
  border-color: rgba(43, 110, 86, 0.16);
  color: #2d6c56;
}

.scene-badge.is-mixed {
  background: #ebe8fb;
  border-color: rgba(112, 92, 170, 0.16);
  color: #6656a8;
}

.toolbar-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.toolbar-meta-pill {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(247, 249, 248, 0.96);
}

.toolbar-meta-pill strong {
  font-size: 13px;
  line-height: 1;
  color: var(--text);
}

.toolbar-meta-pill span {
  min-width: 0;
  font-size: 11px;
  color: var(--text-soft);
  white-space: nowrap;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.toolbar-priority {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-label {
  font-size: 11px;
  color: var(--text-faint);
  font-weight: 700;
  letter-spacing: 0.02em;
}

.priority-group,
.segmented-control {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border-radius: 999px;
  background: var(--surface-muted);
  border: 1px solid var(--border);
}

.priority-chip,
.segment-btn {
  border: none;
  background: transparent;
  color: var(--text-soft);
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.priority-chip {
  padding: 5px 9px;
  font-size: 11px;
  font-weight: 700;
}

.priority-chip.active,
.segment-btn.active {
  background: var(--surface);
  color: var(--accent);
  box-shadow: 0 2px 8px rgba(23, 32, 29, 0.07);
}

.segment-btn {
  min-width: 94px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.segment-btn strong {
  font-size: 13px;
}

.segment-btn span {
  font-size: 10px;
  color: inherit;
  opacity: 0.8;
}

.toolbar-button-row {
  display: flex;
  gap: 7px;
  align-items: center;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 11px;
  border: 1px solid transparent;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.btn-primary {
  background: var(--accent);
  color: #fff;
  box-shadow: 0 6px 16px rgba(31, 114, 128, 0.16);
}

.btn-secondary,
.btn-ghost {
  background: rgba(255, 255, 255, 0.88);
  color: var(--text);
  border-color: var(--border);
}

.main-area {
  display: grid;
  grid-template-columns: 192px minmax(0, 1fr) 340px;
  gap: 12px;
  padding: 12px;
  min-height: 0;
  flex: 1;
}

.main-area.tablet {
  grid-template-columns: 176px minmax(0, 1fr);
  grid-template-rows: minmax(460px, 62vh) minmax(276px, 34vh);
  grid-template-areas:
    "palette canvas"
    "panel panel";
  align-content: stretch;
  align-items: stretch;
  height: 100%;
}

.node-palette,
.canvas-stage,
.right-panel {
  min-height: 0;
  border: 1px solid rgba(199, 210, 206, 0.82);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 8px 24px rgba(23, 32, 29, 0.05);
  backdrop-filter: blur(10px);
}

.node-palette {
  padding: 11px 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-area.tablet .node-palette {
  grid-area: palette;
  padding: 10px 9px;
}

.node-palette.touch .palette-item {
  cursor: pointer;
}

.palette-header,
.mobile-palette-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.inline-card,
.form-hint {
  color: var(--text-soft);
  font-size: 12px;
  line-height: 1.6;
}

.form-hint-error {
  color: var(--danger);
}

.palette-fit-btn,
.stage-action {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--accent);
  border-radius: 12px;
  padding: 7px 11px;
  font-size: 11.5px;
  font-weight: 700;
  cursor: pointer;
}

.palette-fit-btn {
  padding: 6px 9px;
  font-size: 11px;
}

.stage-action-primary {
  background: var(--accent-soft);
}

.palette-list,
.mobile-palette-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  min-height: 0;
}

.palette-item {
  --palette-accent: #1f7280;
  --palette-soft: rgba(31, 114, 128, 0.12);
  --palette-border: rgba(31, 114, 128, 0.2);
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 14px;
  background:
    radial-gradient(circle at top right, var(--palette-soft) 0%, transparent 52%),
    linear-gradient(180deg, #ffffff 0%, #f8fbfa 100%);
  padding: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  text-align: left;
  cursor: grab;
  position: relative;
  overflow: hidden;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.palette-item.mobile {
  cursor: pointer;
}

.palette-item:hover {
  transform: translateY(-1px);
  border-color: var(--palette-border);
  box-shadow: 0 7px 16px rgba(23, 32, 29, 0.06);
}

.palette-item:focus-visible {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(31, 114, 128, 0.12);
}

.palette-icon {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.92) 0%, var(--palette-soft) 100%);
  color: var(--palette-accent);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
  flex-shrink: 0;
}

.palette-copy {
  min-width: 0;
}

.palette-name {
  font-size: 12px;
  font-weight: 700;
  line-height: 1.3;
}

.palette-desc {
  margin-top: 3px;
  font-size: 10.5px;
  color: var(--text-soft);
  line-height: 1.45;
}

.palette-item.type-atmospheric {
  --palette-accent: #4d7b67;
  --palette-soft: rgba(77, 123, 103, 0.14);
  --palette-border: rgba(77, 123, 103, 0.26);
}

.palette-item.type-conditional {
  --palette-accent: #7c7462;
  --palette-soft: rgba(124, 116, 98, 0.14);
  --palette-border: rgba(124, 116, 98, 0.24);
}

.palette-item.type-mosaic {
  --palette-accent: #546f8d;
  --palette-soft: rgba(84, 111, 141, 0.14);
  --palette-border: rgba(84, 111, 141, 0.24);
}

.palette-item.type-clip {
  --palette-accent: #8b6951;
  --palette-soft: rgba(139, 105, 81, 0.14);
  --palette-border: rgba(139, 105, 81, 0.26);
}

.palette-item.type-synthesis {
  --palette-accent: #6f6582;
  --palette-soft: rgba(111, 101, 130, 0.14);
  --palette-border: rgba(111, 101, 130, 0.24);
}

.canvas-stage {
  display: flex;
  flex-direction: column;
  padding: 12px;
  min-height: 0;
}

.main-area.tablet .canvas-stage {
  grid-area: canvas;
  padding: 10px;
  height: 100%;
}

.main-area.tablet .canvas-wrapper {
  flex: 1 1 auto;
  min-height: 420px;
  height: 100%;
}

.main-area.tablet .canvas-wrapper.touch {
  min-height: 420px;
  height: 100%;
}

.main-area.tablet .vue-flow-canvas {
  min-height: 420px;
}

.stage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.stage-title {
  font-size: 14px;
  font-weight: 700;
}

.stage-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.canvas-wrapper {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(246, 249, 248, 0.94)),
    radial-gradient(circle at top left, rgba(31, 114, 128, 0.06), transparent 28%);
}

.canvas-wrapper.touch {
  min-height: 360px;
}

.vue-flow-canvas {
  width: 100%;
  height: 100%;
}

.canvas-status-strip {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 5;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.canvas-controls {
  position: absolute;
  left: 14px;
  bottom: 14px;
  z-index: 5;
  display: flex;
  gap: 4px;
  padding: 5px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 8px 18px rgba(23, 32, 29, 0.09);
}

.canvas-controls.compact {
  left: 14px;
  bottom: 14px;
}

.ctrl-btn {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
}

.ctrl-btn:hover {
  background: var(--surface-muted);
}

:deep(.vue-flow__node) {
  background: transparent;
  border: none;
  padding: 0;
  box-shadow: none;
  border-radius: 0;
}

:deep(.flow-node) {
  background-clip: padding-box;
  isolation: isolate;
}

:deep(.flow-node .node-header) {
  border-top-left-radius: 13px;
  border-top-right-radius: 13px;
  background-clip: padding-box;
}

.right-panel {
  min-height: 0;
  overflow: hidden;
}

.main-area.tablet .right-panel {
  grid-area: panel;
  overflow: hidden;
  height: 100%;
}

.queue-panel,
.side-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.queue-header,
.side-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 12px 9px;
  border-bottom: 1px solid var(--border);
  background: rgba(247, 249, 248, 0.92);
}

.queue-title,
.side-panel-title {
  font-size: 14px;
  font-weight: 700;
  margin-top: 0;
}

.btn-clear-queue,
.close-btn {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-soft);
  border-radius: 10px;
  padding: 6px 9px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
}

.btn-clear-queue:hover,
.close-btn:hover {
  border-color: rgba(182, 69, 55, 0.24);
  color: var(--danger);
  background: var(--danger-soft);
}

.queue-summary-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 12px 6px;
}

.queue-summary-card {
  min-width: 0;
  flex: 1 1 calc(50% - 3px);
  padding: 6px 9px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(249, 251, 250, 0.96);
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.queue-summary-card span {
  font-size: 10.5px;
  color: var(--text-soft);
}

.queue-summary-card strong {
  font-size: 13px;
  line-height: 1;
}

.queue-summary-card.is-running strong { color: var(--accent); }
.queue-summary-card.is-queued strong { color: var(--warn); }
.queue-summary-card.is-success strong { color: var(--ok); }
.queue-summary-card.is-failed strong { color: var(--danger); }

.queue-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-align: center;
  padding: 18px;
  color: var(--text-soft);
}

.queue-empty strong {
  font-size: 14px;
  color: var(--text);
}

.queue-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.queue-item {
  border-radius: 12px;
  border: 1px solid var(--border);
  background: linear-gradient(180deg, #ffffff 0%, #f8faf9 100%);
  padding: 9px 10px 8px;
  box-shadow: 0 4px 10px rgba(23, 32, 29, 0.035);
}

.queue-item[data-status="running"] { border-left: 3px solid var(--accent); }
.queue-item[data-status="queued"],
.queue-item[data-status="pending"] { border-left: 3px solid var(--warn); }
.queue-item[data-status="success"] { border-left: 3px solid var(--ok); }
.queue-item[data-status="failed"] { border-left: 3px solid var(--danger); }

.queue-item-header,
.queue-item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.queue-item-copy {
  min-width: 0;
}

.queue-scene {
  display: block;
  font-size: 12.5px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.queue-subline,
.progress-text {
  font-size: 10px;
  color: var(--text-soft);
}

.queue-item-meta {
  margin-top: 3px;
}

.queue-progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 7px;
}

.queue-progress-bar {
  flex: 1;
  min-width: 0;
  height: 5px;
  border-radius: 999px;
  background: var(--surface-muted);
  overflow: hidden;
}

.queue-progress-fill {
  height: 100%;
  border-radius: inherit;
  transition: width 0.28s ease;
  background: var(--border-strong);
}

.queue-progress-fill.running { background: var(--accent); }
.queue-progress-fill.queued,
.queue-progress-fill.pending { background: var(--warn); }
.queue-progress-fill.success { background: var(--ok); }
.queue-progress-fill.failed { background: var(--danger); }

.status-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 3px 7px;
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}

.status-badge.running {
  background: var(--accent-soft);
  color: var(--accent);
}

.status-badge.queued,
.status-badge.pending {
  background: var(--warn-soft);
  color: var(--warn);
}

.status-badge.success {
  background: var(--ok-soft);
  color: var(--ok);
}

.status-badge.failed {
  background: var(--danger-soft);
  color: var(--danger);
}

.status-badge.paused,
.status-badge.cancelled {
  background: var(--surface-muted);
  color: var(--text-soft);
}

.btn-cancel {
  border: none;
  border-radius: 999px;
  padding: 4px 8px;
  background: var(--danger-soft);
  color: var(--danger);
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
  flex-shrink: 0;
}

.side-panel-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.side-panel-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 12px 12px;
  border-top: 1px solid var(--border);
  background: rgba(247, 249, 248, 0.92);
}

.panel-summary-card,
.strategy-card,
.inline-card,
.scene-section {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(249, 251, 250, 0.96);
  padding: 10px 12px;
}

.panel-summary-top,
.strategy-header,
.scene-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.panel-summary-title,
.strategy-title {
  margin-top: 0;
  font-size: 13px;
  font-weight: 700;
}

.strategy-title.is-ok { color: var(--ok); }
.strategy-title.is-warn { color: var(--warn); }

.panel-summary-metrics,
.scene-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.summary-metric-pill,
.scene-stat-card {
  border-radius: 999px;
  padding: 6px 9px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.summary-metric-pill strong,
.scene-stat-card strong {
  font-size: 13px;
  line-height: 1;
}

.summary-metric-pill span,
.scene-stat-card span {
  font-size: 10.5px;
  color: var(--text-soft);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-group label {
  font-size: 12px;
  font-weight: 700;
}

.required {
  color: var(--danger);
}

.form-input {
  width: 100%;
  min-height: 38px;
  border-radius: 10px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  padding: 9px 11px;
  font-size: 12.5px;
  color: var(--text);
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.form-input:focus {
  outline: none;
  border-color: rgba(31, 114, 128, 0.42);
  box-shadow: 0 0 0 4px rgba(31, 114, 128, 0.08);
}

.path-input-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

.clip-action-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.clip-preview-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.clip-preview-pill {
  min-width: 0;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
}

.clip-preview-pill strong {
  display: block;
  font-size: 11px;
  color: var(--text-soft);
}

.clip-preview-pill span {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text);
  word-break: break-all;
}

.btn-pick {
  min-height: 38px;
  padding: 0 11px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-soft);
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.radio-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.radio-label,
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--text);
}

.radio-label input,
.checkbox-label input,
.scene-item input {
  width: 16px;
  height: 16px;
}

.or-divider {
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-faint);
}

.inline-card {
  padding: 9px 10px;
  border-radius: 10px;
  background: var(--surface-soft);
  line-height: 1.6;
}

.inline-card code {
  display: inline-flex;
  align-items: center;
  padding: 1px 5px;
  border-radius: 8px;
  background: var(--surface-muted);
  font-size: 12px;
}

.inline-card-warn {
  background: var(--warn-soft);
  border-color: rgba(157, 107, 22, 0.18);
  color: #6e4d12;
}

.scene-list-actions {
  display: flex;
  gap: 8px;
}

.btn-link {
  border: none;
  background: none;
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
}

.scene-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 292px;
  overflow-y: auto;
}

.scene-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: flex-start;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface-soft);
  cursor: pointer;
  transition: border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
}

.scene-item:hover {
  border-color: rgba(31, 114, 128, 0.2);
  box-shadow: 0 6px 16px rgba(23, 32, 29, 0.05);
}

.scene-item.selected {
  border-color: rgba(31, 114, 128, 0.32);
  background: #fbfdfd;
}

.scene-item.mismatch {
  border-color: rgba(182, 69, 55, 0.24);
}

.scene-item-copy {
  min-width: 0;
}

.scene-item-title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.scene-name {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
}

.scene-path {
  font-size: 10.5px;
  color: var(--text-faint);
}

.scene-badge-row {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  margin-top: 6px;
}

.composite-grid {
  display: grid;
  gap: 12px;
}

.composite-group {
  padding: 12px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
}

.group-label {
  margin-bottom: 8px;
}

.mobile-palette-drawer {
  display: none;
}

.picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: rgba(9, 15, 17, 0.48);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
}

.picker-dialog {
  width: min(620px, 100%);
  max-height: min(76vh, 760px);
  display: flex;
  flex-direction: column;
  border-radius: 22px;
  overflow: hidden;
  background: var(--surface);
  border: 1px solid rgba(199, 210, 206, 0.9);
  box-shadow: 0 18px 48px rgba(9, 15, 17, 0.18);
}

.picker-header,
.picker-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

.picker-header {
  font-size: 15px;
  font-weight: 700;
}

.picker-header button {
  border: 1px solid var(--border);
  background: var(--surface-soft);
  color: var(--text-soft);
  border-radius: 999px;
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.picker-breadcrumb {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px 16px;
  background: var(--surface-soft);
  border-bottom: 1px solid var(--border);
}

.breadcrumb-btn {
  border: none;
  background: var(--surface);
  color: var(--accent);
  border-radius: 999px;
  padding: 5px 9px;
  font-size: 11.5px;
  font-weight: 700;
  cursor: pointer;
}

.picker-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 10px;
}

.picker-section-label {
  padding: 10px 12px 6px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-faint);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.picker-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  cursor: pointer;
  font-size: 12.5px;
}

.picker-item:hover {
  background: var(--surface-soft);
}

.picker-item.selected {
  background: rgba(30, 122, 94, 0.1);
  border: 1px solid rgba(30, 122, 94, 0.28);
}

.picker-item.file {
  margin-top: 4px;
}

.picker-item-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text-soft);
}

.picker-empty {
  padding: 28px 16px;
  text-align: center;
  color: var(--text-faint);
}

.picker-footer {
  border-top: 1px solid var(--border);
  border-bottom: none;
}

.picker-current {
  font-size: 10.5px;
  color: var(--text-faint);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.spin {
  animation: spin 1s linear infinite;
}

.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.slide-panel-enter-from,
.slide-panel-leave-to {
  opacity: 0;
  transform: translateX(18px);
}

@media (max-width: 1240px) {
  .toolbar {
    grid-template-columns: minmax(0, 1fr);
  }

  .toolbar-actions,
  .toolbar-priority {
    justify-content: flex-start;
  }

  .toolbar-meta-row,
  .toolbar-actions {
    width: 100%;
  }

  .main-area {
    grid-template-columns: 184px minmax(0, 1fr) 320px;
  }
}

@media (max-width: 900px) {
  .batch-manager.is-phone {
    overflow: visible;
    height: auto;
  }

  .toolbar {
    padding: 10px 12px;
  }

  .toolbar-meta-row {
    width: 100%;
    overflow-x: auto;
    padding-bottom: 2px;
  }

  .toolbar-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .toolbar-priority {
    width: 100%;
    flex-wrap: wrap;
  }

  .toolbar-button-row {
    width: auto;
    flex-wrap: wrap;
  }

  .toolbar-button-row .btn {
    flex: 0 0 auto;
  }

  .batch-manager.is-phone .main-area {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 10px;
    overflow: visible;
  }

  .batch-manager.is-phone .canvas-stage,
  .batch-manager.is-phone .right-panel {
    width: 100%;
  }

  .batch-manager.is-phone .canvas-stage {
    padding: 10px;
  }

  .batch-manager.is-phone .canvas-wrapper {
    min-height: 54vh;
  }

  .canvas-status-strip {
    right: 12px;
  }

  .batch-manager.is-phone .right-panel {
    overflow: visible;
  }

  .batch-manager.is-phone .side-panel.mobile {
    position: fixed;
    inset: 0;
    z-index: 40;
    border-radius: 0;
    background: var(--surface);
  }

  .batch-manager.is-phone .side-panel.mobile .side-panel-header {
    padding-top: 14px;
  }

  .batch-manager.is-phone .side-panel.mobile .side-panel-footer {
    position: sticky;
    bottom: 0;
    padding-bottom: calc(16px + env(safe-area-inset-bottom));
    background: rgba(247, 249, 248, 0.98);
  }

  .side-panel-footer {
    justify-content: stretch;
  }

  .side-panel-footer .btn {
    flex: 1;
  }

  .queue-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .scene-section-header,
  .strategy-header,
  .queue-header,
  .picker-footer {
    flex-wrap: wrap;
  }

  .clip-preview-meta {
    grid-template-columns: 1fr;
  }

  .batch-manager.is-phone .mobile-palette-drawer {
    position: fixed;
    left: 10px;
    right: 10px;
    bottom: 10px;
    z-index: 35;
    display: block;
    pointer-events: none;
  }

  .batch-manager.is-phone .mobile-drawer-handle,
  .batch-manager.is-phone .mobile-palette-content {
    pointer-events: auto;
  }

  .batch-manager.is-phone .mobile-drawer-handle {
    width: 100%;
    border: 1px solid rgba(199, 210, 206, 0.88);
    background: rgba(255, 255, 255, 0.95);
    color: var(--text);
    border-radius: 999px;
    min-height: 40px;
    padding: 0 12px;
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    font-weight: 700;
    box-shadow: 0 10px 24px rgba(9, 15, 17, 0.15);
    backdrop-filter: blur(12px);
    cursor: pointer;
  }

  .batch-manager.is-phone .mobile-palette-content {
    margin-top: 8px;
    border-radius: 20px;
    border: 1px solid rgba(199, 210, 206, 0.92);
    background: rgba(255, 255, 255, 0.98);
    box-shadow: 0 18px 36px rgba(9, 15, 17, 0.16);
    padding: 10px;
    max-height: 0;
    opacity: 0;
    overflow: hidden;
    transform: translateY(12px);
    transition: max-height 0.24s ease, opacity 0.24s ease, transform 0.24s ease;
  }

  .batch-manager.is-phone .mobile-palette-drawer.open .mobile-palette-content {
    max-height: 296px;
    opacity: 1;
    transform: translateY(0);
  }

  .batch-manager.is-phone .mobile-palette-list {
    max-height: 214px;
  }

  .batch-manager.is-phone .picker-overlay {
    padding: 0;
  }

  .batch-manager.is-phone .picker-dialog {
    width: 100%;
    max-height: 100%;
    height: 100%;
    border-radius: 0;
  }
}

@media (max-width: 640px) {
  .toolbar {
    gap: 12px;
  }

  .toolbar-title {
    font-size: 18px;
  }

  .toolbar-actions,
  .path-input-row {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-button-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }

  .path-input-row {
    display: flex;
  }

  .priority-group,
  .segmented-control {
    width: 100%;
  }

  .priority-chip,
  .segment-btn {
    flex: 1;
    justify-content: center;
    align-items: center;
  }

  .scene-item-title-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .canvas-status-strip {
    left: 10px;
    right: 10px;
  }

  .canvas-controls {
    left: 10px;
    bottom: 72px;
  }

  .picker-current {
    white-space: normal;
    word-break: break-all;
  }
}
</style>
