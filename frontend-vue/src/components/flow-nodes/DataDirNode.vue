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
      <div v-if="props.data.scenes?.length" class="scene-count">
        发现 {{ props.data.scenes.length }} 个场景
        <span class="sel-count">已选 {{ selectedCount }}</span>
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
function shortPath(p) {
  if (!p) return ''
  const parts = p.replace(/\\/g, '/').split('/')
  return parts.length <= 2 ? p : '.../' + parts.slice(-2).join('/')
}
</script>

<style scoped>
.flow-node {
  min-width: 170px; border-radius: 8px; border: 2px solid #a5b4fc;
  background: #eef2ff; cursor: pointer; font-family: inherit;
  transition: box-shadow 0.2s, border-color 0.2s;
}
.flow-node.selected { border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79,70,229,0.25); }
.flow-node.configured { border-color: #6366f1; }
.node-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px 6px; border-bottom: 1px solid #c7d2fe;
  background: #e0e7ff; border-radius: 6px 6px 0 0;
}
.node-icon { display: flex; align-items: center; color: #4338ca; }
.node-title { font-size: 13px; font-weight: 600; color: #4338ca; flex: 1; }
.node-status { display: flex; align-items: center; }
.node-status.ok { color: #16a34a; }
.node-status.warn { color: #d97706; }
.node-body { padding: 8px 10px; }
.node-path { font-size: 10px; color: #6b7280; word-break: break-all; margin-bottom: 4px; }
.node-hint { font-size: 11px; color: #9ca3af; font-style: italic; }
.scene-count { font-size: 11px; color: #4338ca; display: flex; align-items: center; gap: 6px; }
.sel-count { font-size: 10px; background: #6366f1; color: #fff; padding: 1px 6px; border-radius: 10px; }
</style>
