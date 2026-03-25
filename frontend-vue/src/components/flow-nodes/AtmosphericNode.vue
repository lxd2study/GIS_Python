<template>
  <div class="flow-node atm-node" :class="{ selected: props.selected }">
    <Handle type="target" :position="Position.Left" id="in" />
    <div class="node-header">
      <span class="node-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 10h-1.26A8 8 0 109 20h9a5 5 0 000-10z"/>
        </svg>
      </span>
      <span class="node-title">大气校正</span>
      <span class="method-badge">{{ props.data.method || 'DOS' }}</span>
    </div>
    <div class="node-body">
      <div class="node-info">方法：{{ props.data.method || 'DOS' }}</div>
      <div class="node-info cloud-mask" v-if="props.data.apply_cloud_mask">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0">
          <path d="M18 10h-1.26A8 8 0 109 20h9a5 5 0 000-10z"/>
        </svg>
        启用云掩膜
      </div>
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
  min-width: 150px; border-radius: 8px; border: 2px solid #6ee7b7;
  background: #ecfdf5; cursor: pointer; transition: box-shadow 0.2s, border-color 0.2s;
}
.flow-node.selected { border-color: #059669; box-shadow: 0 0 0 3px rgba(5,150,105,0.25); }
.node-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px 6px; border-bottom: 1px solid #a7f3d0;
  background: #d1fae5; border-radius: 6px 6px 0 0;
}
.node-icon { display: flex; align-items: center; color: #065f46; }
.node-title { font-size: 13px; font-weight: 600; color: #065f46; flex: 1; }
.method-badge { font-size: 10px; font-weight: 700; background: #059669; color: #fff; padding: 1px 6px; border-radius: 4px; }
.node-body { padding: 8px 10px; }
.node-info { font-size: 11px; color: #047857; margin-bottom: 2px; }
.cloud-mask { display: flex; align-items: center; gap: 4px; }
</style>
