<template>
  <div class="flow-node radiometric-node" :class="{ selected: props.selected }">
    <Handle type="target" :position="Position.Left" id="in" />
    <div class="node-header">
      <span class="node-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
      </span>
      <span class="node-title">辐射定标</span>
      <span class="node-lock">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
          <path d="M7 11V7a5 5 0 0110 0v4"/>
        </svg>
      </span>
    </div>
    <div class="node-body">
      <div class="node-steps">
        <span class="step">DN</span>
        <svg class="arrow" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        <span class="step">辐亮度</span>
        <svg class="arrow" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        <span class="step">反射率</span>
      </div>
      <div class="node-hint">必需步骤，自动执行</div>
    </div>
    <Handle type="source" :position="Position.Right" id="out" />
  </div>
</template>

<script setup>
import { Handle, Position } from '@vue-flow/core'
const props = defineProps(['id', 'data', 'selected'])
</script>

<style scoped>
.flow-node {
  min-width: 160px; border-radius: 8px; border: 2px solid #9ca3af;
  background: #f9fafb; cursor: default; transition: box-shadow 0.2s;
}
.flow-node.selected { border-color: #6b7280; box-shadow: 0 0 0 3px rgba(107,114,128,0.2); }
.node-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px 6px; border-bottom: 1px solid #e5e7eb;
  background: #e5e7eb; border-radius: 6px 6px 0 0;
}
.node-icon { display: flex; align-items: center; color: #374151; }
.node-title { font-size: 13px; font-weight: 600; color: #374151; flex: 1; }
.node-lock { display: flex; align-items: center; color: #9ca3af; }
.node-body { padding: 8px 10px; }
.node-steps { display: flex; align-items: center; gap: 4px; margin-bottom: 4px; }
.step { font-size: 10px; background: #d1d5db; padding: 1px 5px; border-radius: 3px; color: #374151; font-weight: 500; }
.arrow { color: #9ca3af; flex-shrink: 0; }
.node-hint { font-size: 10px; color: #9ca3af; font-style: italic; }
</style>
