<template>
  <div class="flow-node mosaic-node" :class="{ configured: isConfigured, selected: props.selected }">
    <Handle type="target" :position="Position.Left" id="in" />
    <div class="node-header">
      <span class="node-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 3h7v7H3z"/>
          <path d="M14 3h7v7h-7z"/>
          <path d="M3 14h7v7H3z"/>
          <path d="M14 14h7v7h-7z"/>
        </svg>
      </span>
      <span class="node-title">影像镶嵌</span>
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
      <div class="node-info">输出：{{ props.data.output_name || 'mosaic' }}</div>
      <div class="node-tag">{{ props.data.keep_intermediate ? '保留中间产物' : '自动清理中间产物' }}</div>
      <div class="node-tag secondary">{{ props.data.display_balance_enabled !== false ? '显示匀色开启' : '显示匀色关闭' }}</div>
    </div>
    <Handle type="source" :position="Position.Right" id="out" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps(['id', 'data', 'selected'])
const isConfigured = computed(() => !!String(props.data.output_name || '').trim())
</script>

<style scoped>
.flow-node {
  --node-accent: #546f8d;
  --node-accent-soft: #edf2f8;
  --node-accent-text: #425a74;
  min-width: 182px;
  border-radius: 14px;
  border: 1px solid #d8e0dd;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(23, 32, 29, 0.05);
  cursor: pointer;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}
.flow-node.selected {
  border-color: rgba(84, 111, 141, 0.32);
  box-shadow: 0 0 0 2px rgba(84, 111, 141, 0.1);
}
.flow-node.configured {
  border-color: rgba(84, 111, 141, 0.22);
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
  color: #5d6d67;
  line-height: 1.45;
  word-break: break-all;
}
.node-tag {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid #d9e2ee;
  background: #f1f5fb;
  color: #4d617a;
  font-size: 10px;
  font-weight: 700;
}
.node-tag.secondary {
  border-color: #d8e3dc;
  background: #f6faf7;
  color: #4d6b5e;
}
</style>
