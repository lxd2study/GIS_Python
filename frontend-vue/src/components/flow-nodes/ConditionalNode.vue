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
  min-width: 175px; border-radius: 8px; border: 2px solid #fcd34d;
  background: #fffbeb; cursor: pointer; transition: box-shadow 0.2s, border-color 0.2s;
}
.flow-node.selected { border-color: #d97706; box-shadow: 0 0 0 3px rgba(217,119,6,0.25); }
.node-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px 6px; border-bottom: 1px solid #fde68a;
  background: #fef3c7; border-radius: 6px 6px 0 0;
}
.node-icon { display: flex; align-items: center; color: #92400e; }
.node-title { font-size: 13px; font-weight: 600; color: #92400e; }
.node-body { padding: 8px 10px; }
.node-desc { font-size: 10px; color: #6b7280; line-height: 1.5; margin-bottom: 6px; }
.node-desc code { background: #f3f4f6; padding: 0 3px; border-radius: 2px; font-size: 10px; }
.branch-labels { display: flex; flex-direction: column; gap: 3px; }
.label-yes, .label-no {
  display: flex; align-items: center; gap: 4px;
  font-size: 11px; font-weight: 600; padding: 2px 0;
}
.label-yes { color: #16a34a; }
.label-no { color: #dc2626; }
</style>
