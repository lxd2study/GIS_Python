<template>
  <div class="flow-node datadir-node" :class="{ configured: isConfigured, selected: props.selected }">
    <div class="node-header">
      <span class="node-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
          <polyline points="9 22 9 12 15 12 15 22"/>
        </svg>
      </span>
      <span class="node-title">数据目录</span>
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
      <div v-if="props.data.root_dir" class="node-path" :title="props.data.root_dir">{{ shortPath(props.data.root_dir) }}</div>
      <div v-else class="node-hint">点击选择数据根目录</div>
      <div v-if="props.data.scenes?.length" class="node-summary">
        <div class="summary-pill">
          <strong>{{ props.data.scenes.length }}</strong>
          <span>总场景</span>
        </div>
        <div class="summary-pill">
          <strong>{{ selectedCount }}</strong>
          <span>已选</span>
        </div>
      </div>
      <div v-if="props.data.scenes?.length" class="node-meta">
        <span class="node-badge accent">{{ productMixLabel }}</span>
        <span class="node-badge" :class="sceneStats.shp > 0 ? 'ok' : 'muted'">{{ shpSummary }}</span>
      </div>
    </div>
    <Handle type="source" :position="Position.Right" id="out" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
const props = defineProps(['id', 'data', 'selected'])
const isConfigured = computed(() => !!props.data.root_dir && (props.data.scenes?.length ?? 0) > 0)
const selectedCount = computed(() => (props.data.selectedScenes || []).length)
const sceneStats = computed(() => {
  const scenes = props.data.scenes || []
  let onlyL1 = 0
  let onlyL2 = 0
  let mixed = 0
  let shp = 0

  for (const scene of scenes) {
    const levels = Array.isArray(scene?.available_product_levels) && scene.available_product_levels.length
      ? scene.available_product_levels
      : [scene?.product_level]
    const normalized = [...new Set(levels.map((item) => String(item || '').trim().toUpperCase()).filter(Boolean))]
    if (scene?.has_shp) shp += 1
    if (normalized.length > 1) mixed += 1
    else if (normalized[0] === 'L2') onlyL2 += 1
    else onlyL1 += 1
  }

  return { onlyL1, onlyL2, mixed, shp }
})
const productMixLabel = computed(() => {
  if (!(props.data.scenes?.length ?? 0)) return '级别待识别'
  if (sceneStats.value.mixed > 0) return `L1/L2 混合 ${sceneStats.value.mixed}`
  if (sceneStats.value.onlyL2 > 0 && sceneStats.value.onlyL1 === 0) return '已识别为 L2'
  return '已识别为 L1'
})
const shpSummary = computed(() => {
  const total = props.data.scenes?.length ?? 0
  if (!total) return 'SHP 待识别'
  return `SHP ${sceneStats.value.shp}/${total}`
})
function shortPath(p) {
  if (!p) return ''
  const parts = p.replace(/\\/g, '/').split('/')
  return parts.length <= 2 ? p : '.../' + parts.slice(-2).join('/')
}
</script>

<style scoped>
.flow-node {
  --node-accent: #4f677e;
  --node-accent-soft: #edf2f6;
  --node-accent-text: #3f566b;
  min-width: 192px;
  border-radius: 14px;
  border: 1px solid #d8e0dd;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(23, 32, 29, 0.05);
  cursor: pointer;
  font-family: inherit;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}
.flow-node.selected {
  border-color: rgba(79, 103, 126, 0.34);
  box-shadow: 0 0 0 2px rgba(79, 103, 126, 0.1);
}
.flow-node.configured { border-color: rgba(79, 103, 126, 0.22); }
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
  border-color: #dfe7ed;
  color: var(--node-accent-text);
}
.node-badge.ok {
  background: #e5f4ed;
  border-color: #d3eadf;
  color: #1b7a57;
}
.node-badge.muted {
  color: #7d8c87;
}
</style>
