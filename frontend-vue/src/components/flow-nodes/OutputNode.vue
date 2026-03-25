<template>
  <div class="flow-node output-node" :class="{ configured: isConfigured, selected: props.selected }">
    <div class="node-header">
      <span class="node-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
          <polyline points="17 21 17 13 7 13 7 21"/>
          <polyline points="7 3 7 8 15 8"/>
        </svg>
      </span>
      <span class="node-title">输出配置</span>
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
      <div v-if="props.data.output_dir" class="node-path" :title="props.data.output_dir">{{ shortPath(props.data.output_dir) }}</div>
      <div v-else class="node-hint">点击配置输出目录</div>
    </div>
    <Handle type="target" :position="Position.Left" id="in" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
const props = defineProps(['id', 'data', 'selected'])
const isConfigured = computed(() => !!props.data.output_dir)
function shortPath(p) {
  if (!p) return ''
  const parts = p.replace(/\\/g, '/').split('/')
  return parts.length <= 2 ? p : '.../' + parts.slice(-2).join('/')
}
</script>

<style scoped>
.flow-node {
  min-width: 170px; border-radius: 8px; border: 2px solid #99f6e4;
  background: #f0fdfa; cursor: pointer; font-family: inherit;
  transition: box-shadow 0.2s, border-color 0.2s;
}
.flow-node.selected { border-color: #0d9488; box-shadow: 0 0 0 3px rgba(13,148,136,0.25); }
.flow-node.configured { border-color: #14b8a6; }
.node-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px 6px; border-bottom: 1px solid #ccfbf1;
  background: #ccfbf1; border-radius: 6px 6px 0 0;
}
.node-icon { display: flex; align-items: center; color: #0f766e; }
.node-title { font-size: 13px; font-weight: 600; color: #0f766e; flex: 1; }
.node-status { display: flex; align-items: center; }
.node-status.ok { color: #16a34a; }
.node-status.warn { color: #d97706; }
.node-body { padding: 8px 10px; }
.node-path { font-size: 10px; color: #6b7280; word-break: break-all; }
.node-hint { font-size: 11px; color: #9ca3af; font-style: italic; }
</style>

