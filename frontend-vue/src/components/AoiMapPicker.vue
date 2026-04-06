<template>
  <div class="aoi-picker" :class="{ disabled: props.disabled }">
    <div ref="mapTarget" class="aoi-map" :style="{ height: `${props.height}px` }"></div>
    <div class="aoi-toolbar">
      <div class="aoi-summary">
        <span>{{ props.label }}</span>
        <strong>{{ bboxText }}</strong>
        <p>{{ summaryText }}</p>
      </div>
      <div class="aoi-actions">
        <button class="btn" type="button" :disabled="props.disabled" @click="drawBox">
          {{ drawActive ? '重新框选中...' : '绘制矩形' }}
        </button>
        <button class="btn sub" type="button" :disabled="props.disabled" @click="clearSelection">清空</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import XYZ from 'ol/source/XYZ'
import Draw, { createBox } from 'ol/interaction/Draw'
import GeoJSON from 'ol/format/GeoJSON'
import Feature from 'ol/Feature'
import { fromExtent as polygonFromExtent } from 'ol/geom/Polygon'
import { Fill, Stroke, Style } from 'ol/style'
import { fromLonLat, transformExtent } from 'ol/proj'
import { createEmpty, extend as extendExtent } from 'ol/extent'

const props = defineProps({
  modelValue: { type: String, default: '' },
  bbox: { type: Array, default: null },
  geojson: { type: Object, default: null },
  coverageBbox: { type: Array, default: null },
  coverageGeojson: { type: Object, default: null },
  statusText: { type: String, default: '' },
  label: { type: String, default: '当前范围' },
  height: { type: Number, default: 240 },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'drawend', 'clear'])

const mapTarget = ref(null)
const drawActive = ref(false)
const coverageSource = new VectorSource()
const selectionSource = new VectorSource()
const geoJsonFormat = new GeoJSON()

let map = null
let drawInteraction = null

function parseExtentText(text) {
  if (!text || !String(text).trim()) return null
  const values = String(text)
    .split(',')
    .map((item) => Number(item.trim()))
  if (values.length !== 4 || values.some((value) => Number.isNaN(value))) return null
  return values
}

const resolvedBbox = computed(() => {
  if (Array.isArray(props.bbox) && props.bbox.length === 4) {
    return props.bbox.map((value) => Number(value))
  }
  return parseExtentText(props.modelValue)
})

const bboxText = computed(() => {
  return resolvedBbox.value
    ? resolvedBbox.value.map((value) => Number(value).toFixed(4)).join(', ')
    : '尚未设置'
})

const summaryText = computed(() => {
  if (props.statusText) return props.statusText
  if (props.geojson) return '当前显示矢量选区'
  if (resolvedBbox.value) return '当前显示矩形范围'
  return '点击绘制矩形，或在上层载入矢量选区'
})

function removeDraw() {
  if (map && drawInteraction) {
    map.removeInteraction(drawInteraction)
  }
  drawInteraction = null
  drawActive.value = false
}

function fitSources() {
  if (!map) return

  const extent = createEmpty()
  let hasExtent = false
  if (!coverageSource.isEmpty()) {
    extendExtent(extent, coverageSource.getExtent())
    hasExtent = true
  }
  if (!selectionSource.isEmpty()) {
    extendExtent(extent, selectionSource.getExtent())
    hasExtent = true
  }
  if (!hasExtent) return

  map.getView().fit(extent, {
    padding: [40, 40, 40, 40],
    duration: 240,
    maxZoom: 12,
  })
}

function renderLayers() {
  coverageSource.clear()
  selectionSource.clear()

  if (props.coverageGeojson) {
    const features = geoJsonFormat.readFeatures(props.coverageGeojson, {
      dataProjection: 'EPSG:4326',
      featureProjection: 'EPSG:3857',
    })
    if (features.length) {
      coverageSource.addFeatures(features)
    }
  } else if (Array.isArray(props.coverageBbox) && props.coverageBbox.length === 4) {
    coverageSource.addFeature(
      new Feature(
        polygonFromExtent(transformExtent(props.coverageBbox.map((value) => Number(value)), 'EPSG:4326', 'EPSG:3857')),
      ),
    )
  }

  if (props.geojson) {
    const features = geoJsonFormat.readFeatures(props.geojson, {
      dataProjection: 'EPSG:4326',
      featureProjection: 'EPSG:3857',
    })
    if (features.length) {
      selectionSource.addFeatures(features)
    }
  }

  if (resolvedBbox.value) {
    selectionSource.addFeature(
      new Feature(polygonFromExtent(transformExtent(resolvedBbox.value, 'EPSG:4326', 'EPSG:3857'))),
    )
  }

  fitSources()
}

function drawBox() {
  if (!map || props.disabled) return
  removeDraw()
  drawInteraction = new Draw({
    source: selectionSource,
    type: 'Circle',
    geometryFunction: createBox(),
  })
  drawInteraction.on('drawstart', () => selectionSource.clear())
  drawInteraction.on('drawend', (event) => {
    const bbox = transformExtent(
      event.feature.getGeometry().getExtent(),
      'EPSG:3857',
      'EPSG:4326',
    ).map((value) => Number(value.toFixed(6)))
    emit('update:modelValue', bbox.join(','))
    emit('drawend', bbox)
    removeDraw()
  })
  map.addInteraction(drawInteraction)
  drawActive.value = true
}

function clearSelection() {
  selectionSource.clear()
  emit('update:modelValue', '')
  emit('clear')
  removeDraw()
}

onMounted(() => {
  map = new Map({
    target: mapTarget.value,
    layers: [
      new TileLayer({
        source: new XYZ({
          url: 'https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}.png',
          maxZoom: 19,
          attributions: 'Tiles © Esri — Source: Esri, USGS, NOAA',
        }),
      }),
      new VectorLayer({
        source: coverageSource,
        style: new Style({
          stroke: new Stroke({ color: '#56708f', width: 2, lineDash: [8, 5] }),
          fill: new Fill({ color: 'rgba(86,112,143,0.08)' }),
        }),
      }),
      new VectorLayer({
        source: selectionSource,
        style: new Style({
          stroke: new Stroke({ color: '#0f7c66', width: 2 }),
          fill: new Fill({ color: 'rgba(15,124,102,0.12)' }),
        }),
      }),
    ],
    view: new View({
      center: fromLonLat([105, 35]),
      zoom: 4,
    }),
  })
  renderLayers()
})

watch(
  () => [props.geojson, props.modelValue, props.bbox, props.coverageGeojson, props.coverageBbox],
  () => renderLayers(),
  { deep: true },
)

onBeforeUnmount(() => {
  removeDraw()
  if (map) {
    map.setTarget(undefined)
    map = null
  }
})
</script>

<style scoped>
.aoi-picker {
  border: 1px solid #d8e0dd;
  border-radius: 14px;
  overflow: hidden;
  background: #fbfdfc;
}

.aoi-picker.disabled {
  opacity: 0.72;
}

.aoi-map {
  width: 100%;
  background: #eef3f1;
}

.aoi-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-top: 1px solid #e4ebe8;
  background: linear-gradient(180deg, rgba(248, 251, 250, 0.96) 0%, rgba(242, 247, 245, 0.96) 100%);
}

.aoi-summary {
  min-width: 0;
}

.aoi-summary span {
  display: block;
  font-size: 11px;
  color: #5f726b;
}

.aoi-summary strong {
  display: block;
  margin-top: 3px;
  color: #22312d;
  font-size: 12px;
  font-family: 'Consolas', 'SFMono-Regular', monospace;
  word-break: break-all;
}

.aoi-summary p {
  margin: 6px 0 0;
  color: #60726a;
  font-size: 11px;
  line-height: 1.5;
}

.aoi-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.btn {
  min-height: 32px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid #cfe0d9;
  background: #0f7c66;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.btn.sub {
  background: #ffffff;
  color: #305448;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

@media (max-width: 720px) {
  .aoi-toolbar {
    flex-direction: column;
  }

  .aoi-actions {
    width: 100%;
  }

  .btn {
    flex: 1;
  }
}
</style>
