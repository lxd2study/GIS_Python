<template>
  <div class="flow-node conditional-node" :class="{ selected: props.selected }">
    <Handle type="target" :position="Position.Left" id="in" />
    <div class="node-header">
      <span class="node-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><path d="M5.64 5.64l2.12 2.12M16.24 16.24l2.12 2.12M5.64 18.36l2.12-2.12M16.24 7.76l2.12-2.12"/>
        </svg>
      </span>
      <span class="node-title">SHP 检测</span>
    </div>
    <div class="node-body">
      <div class="node-desc">检测遥感影像目录下是否存在 <code>shp/</code> 文件夹及 .shp 文件</div>
      <div class="branch-labels">
        <span class="label-yes">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          是 → 裁剪
        </span>
        <span class="label-no">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          否 → 跳过
        </span>
      </div>
    </div>
    <!-- 两个出口 handle：是（上）否（下） -->
    <Handle type="source" :position="Position.Right" id="yes" :style="{ top: '32%' }" />
    <Handle type="source" :position="Position.Right" id="no"  :style="{ top: '68%' }" />
  </div>
</template>

<script setup>
import { Handle, Position } from '@vue-flow/core'
const props = defineProps(['id', 'data', 'selected'])
</script>

<style scoped>
.flow-node {
  --node-accent: #7c7462;
  --node-accent-soft: #f2eee7;
  --node-accent-text: #655f52;
  min-width: 186px;
  border-radius: 14px;
  border: 1px solid #d8e0dd;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(23, 32, 29, 0.05);
  cursor: pointer;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}
.flow-node.selected {
  border-color: rgba(124, 116, 98, 0.32);
  box-shadow: 0 0 0 2px rgba(124, 116, 98, 0.1);
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
}
.node-body {
  padding: 10px 11px 11px;
}
.node-desc {
  font-size: 10.5px;
  color: #5d6d67;
  line-height: 1.45;
  margin-bottom: 8px;
}
.node-desc code {
  background: #eef2f1;
  padding: 0 4px;
  border-radius: 4px;
  font-size: 10px;
}
.branch-labels {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.label-yes,
.label-no {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: fit-content;
  min-height: 20px;
  padding: 0 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
}
.label-yes {
  color: #1b7a57;
  background: #e5f4ed;
  border: 1px solid #d3eadf;
}
.label-no {
  color: #b64537;
  background: #f8e5e1;
  border: 1px solid #edd3cd;
}
</style>
