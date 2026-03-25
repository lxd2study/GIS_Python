<template>
  <div class="flow-node synthesis-node" :class="{ configured: isConfigured, selected: props.selected }">
    <Handle type="target" :position="Position.Left" id="in" />
    <div class="node-header">
      <span class="node-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="12 2 2 7 12 12 22 7 12 2"/>
          <polyline points="2 17 12 22 22 17"/>
          <polyline points="2 12 12 17 22 12"/>
        </svg>
      </span>
      <span class="node-title">合成指数</span>
      <span v-if="isConfigured" class="count-badge">{{ totalCount }}</span>
    </div>
    <div class="node-body">
      <div v-if="isConfigured" class="node-info">
        已选 {{ totalCount }} 项
        <span v-if="props.data.custom_name" class="custom-badge">+自定义</span>
      </div>
      <div v-else class="node-hint">点击选择指数/合成色</div>
    </div>
    <Handle type="source" :position="Position.Right" id="out" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
const props = defineProps(['id', 'data', 'selected'])
const isConfigured = computed(() => (props.data.composites || []).length > 0 || props.data.custom_name)
const totalCount = computed(() => {
  const base = (props.data.composites || []).length
  return props.data.custom_name ? base + 1 : base
})
</script>

<style scoped>
.flow-node {
  min-width: 150px; border-radius: 8px; border: 2px solid #d8b4fe;
  background: #faf5ff; cursor: pointer; transition: box-shadow 0.2s, border-color 0.2s;
}
.flow-node.selected { border-color: #7c3aed; box-shadow: 0 0 0 3px rgba(124,58,237,0.25); }
.flow-node.configured { border-color: #9333ea; }
.node-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px 6px; border-bottom: 1px solid #e9d5ff;
  background: #ede9fe; border-radius: 6px 6px 0 0;
}
.node-icon { display: flex; align-items: center; color: #7c3aed; }
.node-title { font-size: 13px; font-weight: 600; color: #6b21a8; flex: 1; }
.count-badge { font-size: 11px; font-weight: 700; background: #9333ea; color: #fff; padding: 1px 6px; border-radius: 10px; }
.node-body { padding: 8px 10px; }
.node-info { font-size: 11px; color: #7e22ce; }
.custom-badge { font-size: 10px; background: #7c3aed; color: #fff; padding: 1px 5px; border-radius: 3px; margin-left: 4px; }
.node-hint { font-size: 11px; color: #9ca3af; font-style: italic; }
</style>
