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
  --node-accent: #8b6951;
  --node-accent-soft: #f5efe9;
  --node-accent-text: #735744;
  min-width: 178px;
  border-radius: 14px;
  border: 1px solid #d8e0dd;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(23, 32, 29, 0.05);
  cursor: pointer;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}
.flow-node.selected {
  border-color: rgba(139, 105, 81, 0.32);
  box-shadow: 0 0 0 2px rgba(139, 105, 81, 0.1);
}
.flow-node.configured { border-color: rgba(139, 105, 81, 0.22); }
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
}
.node-info {
  font-size: 11px;
  color: #5d6d67;
  line-height: 1.45;
  word-break: break-all;
}
.node-hint {
  font-size: 11px;
  color: #889691;
  font-style: italic;
}
</style>
