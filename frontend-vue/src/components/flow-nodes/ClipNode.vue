<template>
  <div class="flow-node clip-node" :class="{ configured: isConfigured, selected: props.selected }">
    <Handle type="target" :position="Position.Left" id="in" />
    <div class="node-header">
      <span class="node-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M6.13 1L6 16a2 2 0 002 2h15"/>
          <path d="M1 6.13L16 6a2 2 0 012 2v15"/>
        </svg>
      </span>
      <span class="node-title">区域裁剪</span>
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
      <div v-if="props.data.clip_shapefile" class="node-info">矢量：{{ shortPath(props.data.clip_shapefile) }}</div>
      <div v-else-if="props.data.clip_extent" class="node-info">范围：{{ props.data.clip_extent }}</div>
      <div v-else class="node-hint">点击配置裁剪范围</div>
    </div>
    <Handle type="source" :position="Position.Right" id="out" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
const props = defineProps(['id', 'data', 'selected'])
const isConfigured = computed(() => !!(props.data.clip_extent || props.data.clip_shapefile))
function shortPath(p) {
  if (!p) return ''
  const parts = p.replace(/\\/g, '/').split('/')
  return parts.length <= 2 ? p : '.../' + parts.slice(-2).join('/')
}
</script>

<style scoped>
.flow-node {
  min-width: 150px; border-radius: 8px; border: 2px solid #fed7aa;
  background: #fff7ed; cursor: pointer; transition: box-shadow 0.2s, border-color 0.2s;
}
.flow-node.selected { border-color: #ea580c; box-shadow: 0 0 0 3px rgba(234,88,12,0.25); }
.flow-node.configured { border-color: #f97316; }
.node-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px 6px; border-bottom: 1px solid #fed7aa;
  background: #ffedd5; border-radius: 6px 6px 0 0;
}
.node-icon { display: flex; align-items: center; color: #9a3412; }
.node-title { font-size: 13px; font-weight: 600; color: #9a3412; flex: 1; }
.node-status { display: flex; align-items: center; }
.node-status.ok { color: #16a34a; }
.node-status.warn { color: #d97706; }
.node-body { padding: 8px 10px; }
.node-info { font-size: 11px; color: #c2410c; word-break: break-all; }
.node-hint { font-size: 11px; color: #9ca3af; font-style: italic; }
</style>
