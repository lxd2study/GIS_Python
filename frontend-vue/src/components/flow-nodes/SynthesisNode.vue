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
  --node-accent: #6f6582;
  --node-accent-soft: #efedf4;
  --node-accent-text: #5d556d;
  min-width: 180px;
  border-radius: 14px;
  border: 1px solid #d8e0dd;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(23, 32, 29, 0.05);
  cursor: pointer;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}
.flow-node.selected {
  border-color: rgba(111, 101, 130, 0.32);
  box-shadow: 0 0 0 2px rgba(111, 101, 130, 0.1);
}
.flow-node.configured { border-color: rgba(111, 101, 130, 0.22); }
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
.count-badge {
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid #ddd8e8;
  background: var(--node-accent-soft);
  color: var(--node-accent-text);
  font-size: 10px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
}
.node-body {
  padding: 10px 11px 11px;
}
.node-info {
  font-size: 11px;
  color: #5d6d67;
  line-height: 1.5;
}
.custom-badge {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  padding: 0 7px;
  border-radius: 999px;
  border: 1px solid #ddd8e8;
  background: #f2f0f7;
  color: #5d556d;
  font-size: 10px;
  font-weight: 700;
  margin-left: 6px;
}
.node-hint {
  font-size: 11px;
  color: #889691;
  font-style: italic;
}
</style>
