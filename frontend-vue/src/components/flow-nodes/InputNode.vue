<template>
  <div class="flow-node input-node" :class="{ configured: isConfigured, selected: props.selected }">
    <div class="node-header">
      <span class="node-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
        </svg>
      </span>
      <span class="node-title">{{ isBatchMode ? '场景选择' : '输入数据' }}</span>
      <span v-if="isConfigured" class="node-status ok">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      </span>
      <span v-else class="node-status warn">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
      </span>
    </div>
    <div class="node-body">
      <!-- 批量场景模式 -->
      <template v-if="isBatchMode">
        <div class="node-summary">
          <div class="summary-pill">
            <strong>{{ selectedCount }}</strong>
            <span>已选场景</span>
          </div>
          <div class="summary-pill">
            <strong>{{ props.data.scenes.length }}</strong>
            <span>总场景</span>
          </div>
        </div>
        <div class="node-meta">
          <span class="node-badge accent">{{ productLevelLabel }}</span>
          <span class="node-badge" :class="hasMixedProducts ? 'warn' : 'ok'">
            {{ hasMixedProducts ? '混合产品' : '级别统一' }}
          </span>
        </div>
        <div class="node-meta">
          <span class="node-badge">{{ shpCount }} SHP</span>
          <span class="node-badge">{{ mtlCount }} MTL</span>
        </div>
      </template>
      <!-- 单场景模式 -->
      <template v-else>
        <div v-if="props.data.scene_name" class="node-info">{{ props.data.scene_name }}</div>
        <div class="node-meta">
          <span class="node-badge accent">{{ productLevelLabel }}</span>
          <span class="node-badge" :class="props.data.mtl_file ? 'ok' : 'muted'">
            {{ props.data.mtl_file ? 'MTL 已配' : '无 MTL' }}
          </span>
        </div>
        <div v-if="props.data.band_dir" class="node-path" :title="props.data.band_dir">{{ shortPath(props.data.band_dir) }}</div>
        <div v-else class="node-hint">点击配置波段目录</div>
      </template>
    </div>
    <Handle type="target" :position="Position.Left" id="in" />
    <Handle type="source" :position="Position.Right" id="out" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
const props = defineProps(['id', 'data', 'selected'])
const isBatchMode = computed(() => (props.data.scenes?.length ?? 0) > 0)
const selectedCount = computed(() => (props.data.selectedScenes || []).length)
const shpCount = computed(() => (props.data.scenes || []).filter(s => s.has_shp).length)
const mtlCount = computed(() => (props.data.scenes || []).filter(s => s.mtl_file).length)
const sceneLevelStats = computed(() => {
  const stats = { onlyL1: 0, onlyL2: 0, mixed: 0 }
  for (const scene of props.data.scenes || []) {
    const levels = Array.isArray(scene?.available_product_levels) && scene.available_product_levels.length
      ? scene.available_product_levels
      : [scene?.product_level]
    const normalized = [...new Set(levels.map((item) => String(item || '').trim().toUpperCase()).filter(Boolean))]
    if (normalized.length > 1) stats.mixed += 1
    else if (normalized[0] === 'L2') stats.onlyL2 += 1
    else stats.onlyL1 += 1
  }
  return stats
})
const hasMixedProducts = computed(() => {
  return sceneLevelStats.value.mixed > 0 || (sceneLevelStats.value.onlyL1 > 0 && sceneLevelStats.value.onlyL2 > 0)
})
const effectiveProductLevel = computed(() => {
  if (isBatchMode.value) {
    const sceneLevels = new Set((props.data.scenes || []).map((scene) => scene.product_level).filter(Boolean))
    if (sceneLevels.size === 1) return [...sceneLevels][0]
  }
  return props.data.product_level || 'L1'
})
const productLevelLabel = computed(() => effectiveProductLevel.value === 'L2' ? '当前 L2 路径' : '当前 L1 路径')
const isConfigured = computed(() => {
  if (isBatchMode.value) return selectedCount.value > 0
  return !!props.data.band_dir
})
function shortPath(p) {
  if (!p) return ''
  const parts = p.replace(/\\/g, '/').split('/')
  return parts.length <= 2 ? p : '.../' + parts.slice(-2).join('/')
}
</script>

<style scoped>
.flow-node {
  --node-accent: #3f6c83;
  --node-accent-soft: #ebf2f6;
  --node-accent-text: #36586b;
  position: relative;
  overflow: visible;
  min-width: 196px;
  border-radius: 14px;
  border: 1px solid #d8e0dd;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(23, 32, 29, 0.05);
  cursor: pointer;
  font-family: inherit;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}
.flow-node.selected {
  border-color: rgba(63, 108, 131, 0.34);
  box-shadow: 0 0 0 2px rgba(63, 108, 131, 0.1);
}
.flow-node.configured { border-color: rgba(63, 108, 131, 0.22); }
.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 11px 7px;
  border-bottom: 1px solid #e7edeb;
  background: #f8faf9;
}
.node-icon {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--node-accent-soft);
  color: var(--node-accent-text);
  flex-shrink: 0;
}
.node-title {
  font-size: 12px;
  font-weight: 700;
  color: #22312d;
  flex: 1;
}
.node-status {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
}
.node-status.ok {
  color: #1b7a57;
  background: #e5f4ed;
}
.node-status.warn {
  color: #9d6b16;
  background: #f8eed8;
}
.node-body {
  padding: 10px 11px 11px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.node-info {
  font-size: 11px;
  color: #33433e;
  font-weight: 600;
  line-height: 1.5;
  word-break: break-all;
}
.node-path {
  font-size: 10.5px;
  color: #62716c;
  line-height: 1.45;
  word-break: break-all;
}
.node-hint {
  font-size: 11px;
  color: #889691;
  font-style: italic;
}
.node-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}
.summary-pill {
  padding: 7px 8px;
  border: 1px solid #e6ece9;
  border-radius: 10px;
  background: #f7f9f8;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.summary-pill strong {
  font-size: 13px;
  line-height: 1;
  color: #22312d;
}
.summary-pill span {
  font-size: 10px;
  color: #80908a;
}
.node-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.node-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid #e1e8e5;
  background: #f3f6f5;
  color: #5f6d68;
  font-size: 10px;
  font-weight: 700;
}
.node-badge.accent {
  background: var(--node-accent-soft);
  border-color: #dce6eb;
  color: var(--node-accent-text);
}
.node-badge.ok {
  background: #e5f4ed;
  border-color: #d3eadf;
  color: #1b7a57;
}
.node-badge.warn {
  background: #f8eed8;
  border-color: #ecdcc0;
  color: #9d6b16;
}
.node-badge.muted {
  color: #7d8c87;
}

.input-node :deep(.vue-flow__handle-left[data-handleid="in"]) {
  left: 0;
  transform: translate(-50%, -50%);
}

.input-node :deep(.vue-flow__handle-right[data-handleid="out"]) {
  top: 40px;
  right: 0;
  transform: translate(50%, -50%);
}
</style>
