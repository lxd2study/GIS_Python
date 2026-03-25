<template>
  <div class="flow-node input-node" :class="{ configured: isConfigured, selected: props.selected }">
    <div class="node-header">
      <span class="node-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
        </svg>
      </span>
      <span class="node-title">{{ isBatchMode ? '场景选择' : '输入数据' }}</span>
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
      <!-- 批量场景模式 -->
      <template v-if="isBatchMode">
        <div class="scene-summary">
          已选 <strong>{{ selectedCount }}</strong> / {{ props.data.scenes.length }} 个场景
        </div>
        <div class="scene-shp">
          <span class="shp-has">{{ shpCount }} 个含 SHP</span>
          <span v-if="noShpCount" class="shp-none">{{ noShpCount }} 个无 SHP</span>
        </div>
        <div class="scene-mtl">
          <span class="mtl-has">{{ mtlCount }} 个含 MTL</span>
          <span v-if="noMtlCount" class="mtl-none">{{ noMtlCount }} 个无 MTL</span>
        </div>
      </template>
      <!-- 单场景模式 -->
      <template v-else>
        <div v-if="props.data.scene_name" class="node-info">{{ props.data.scene_name }}</div>
        <div v-if="props.data.band_dir" class="node-path" :title="props.data.band_dir">{{ shortPath(props.data.band_dir) }}</div>
        <div v-else class="node-hint">点击配置波段目录</div>
      </template>
    </div>
    <Handle type="target" :position="Position.Left" id="in" />
    <Handle type="source" :position="Position.Right" id="out" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
const props = defineProps(['id', 'data', 'selected'])
const isBatchMode = computed(() => (props.data.scenes?.length ?? 0) > 0)
const selectedCount = computed(() => (props.data.selectedScenes || []).length)
const shpCount = computed(() => (props.data.scenes || []).filter(s => s.has_shp).length)
const noShpCount = computed(() => (props.data.scenes || []).filter(s => !s.has_shp).length)
const mtlCount = computed(() => (props.data.scenes || []).filter(s => s.mtl_file).length)
const noMtlCount = computed(() => (props.data.scenes || []).filter(s => !s.mtl_file).length)
const isConfigured = computed(() => {
  if (isBatchMode.value) return selectedCount.value > 0
  return !!props.data.band_dir
})
function shortPath(p) {
  if (!p) return ''
  const parts = p.replace(/\\/g, '/').split('/')
  return parts.length <= 2 ? p : '.../' + parts.slice(-2).join('/')
}
</script>

<style scoped>
.flow-node {
  min-width: 170px; border-radius: 8px; border: 2px solid #93c5fd;
  background: #eff6ff; cursor: pointer; font-family: inherit;
  transition: box-shadow 0.2s, border-color 0.2s;
}
.flow-node.selected { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.25); }
.flow-node.configured { border-color: #3b82f6; }
.node-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px 6px; border-bottom: 1px solid #bfdbfe;
  background: #dbeafe; border-radius: 6px 6px 0 0;
}
.node-icon { display: flex; align-items: center; color: #1d4ed8; }
.node-title { font-size: 13px; font-weight: 600; color: #1d4ed8; flex: 1; }
.node-status { display: flex; align-items: center; }
.node-status.ok { color: #16a34a; }
.node-status.warn { color: #d97706; }
.node-body { padding: 8px 10px; }
.node-info { font-size: 11px; color: #1e40af; font-weight: 500; margin-bottom: 2px; word-break: break-all; }
.node-path { font-size: 10px; color: #6b7280; word-break: break-all; }
.node-hint { font-size: 11px; color: #9ca3af; font-style: italic; }
.scene-summary { font-size: 12px; color: #1e40af; font-weight: 600; margin-bottom: 3px; }
.scene-shp { display: flex; gap: 6px; }
.scene-mtl { display: flex; gap: 6px; margin-top: 3px; }
.mtl-has { font-size: 10px; color: #2563eb; background: #dbeafe; padding: 1px 5px; border-radius: 3px; }
.mtl-none { font-size: 10px; color: #9ca3af; background: #f3f4f6; padding: 1px 5px; border-radius: 3px; }
</style>
