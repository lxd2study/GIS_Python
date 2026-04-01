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
  --node-accent: #4d7b67;
  --node-accent-soft: #edf4f0;
  --node-accent-text: #426755;
  min-width: 178px;
  border-radius: 14px;
  border: 1px solid #d8e0dd;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(23, 32, 29, 0.05);
  cursor: pointer;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}
.flow-node.selected {
  border-color: rgba(77, 123, 103, 0.32);
  box-shadow: 0 0 0 2px rgba(77, 123, 103, 0.1);
}
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
.method-badge {
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid #d5e5dd;
  background: var(--node-accent-soft);
  color: var(--node-accent-text);
  font-size: 10px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
}
.node-body {
  padding: 10px 11px 11px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.node-info {
  font-size: 11px;
  color: #5d6d67;
  line-height: 1.45;
}
.cloud-mask {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  align-self: flex-start;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid #d5e5dd;
  background: #edf5f1;
  color: #496858;
}
</style>
