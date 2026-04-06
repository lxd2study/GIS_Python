export function normalizeBbox(bbox) {
  if (!Array.isArray(bbox) || bbox.length !== 4) return null
  const values = bbox.map((value) => Number(value))
  if (values.some((value) => Number.isNaN(value) || !Number.isFinite(value))) return null
  const [x1, y1, x2, y2] = values
  const minX = Math.min(x1, x2)
  const minY = Math.min(y1, y2)
  const maxX = Math.max(x1, x2)
  const maxY = Math.max(y1, y2)
  if (!(maxX > minX) || !(maxY > minY)) return null
  return [minX, minY, maxX, maxY]
}

export function buildBboxFeatureCollection(items = []) {
  const features = items
    .map((item) => {
      const bbox = normalizeBbox(Array.isArray(item) ? item : item?.bbox)
      if (!bbox) return null
      const properties = Array.isArray(item) ? {} : (item?.properties || {})
      const [minX, minY, maxX, maxY] = bbox
      return {
        type: 'Feature',
        properties,
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [minX, minY],
            [maxX, minY],
            [maxX, maxY],
            [minX, maxY],
            [minX, minY],
          ]],
        },
      }
    })
    .filter(Boolean)

  return {
    type: 'FeatureCollection',
    features,
  }
}

function intersectBbox(a, b) {
  const boxA = normalizeBbox(a)
  const boxB = normalizeBbox(b)
  if (!boxA || !boxB) return null
  const minX = Math.max(boxA[0], boxB[0])
  const minY = Math.max(boxA[1], boxB[1])
  const maxX = Math.min(boxA[2], boxB[2])
  const maxY = Math.min(boxA[3], boxB[3])
  if (!(maxX > minX) || !(maxY > minY)) return null
  return [minX, minY, maxX, maxY]
}

function bboxArea(bbox) {
  const normalized = normalizeBbox(bbox)
  if (!normalized) return 0
  return (normalized[2] - normalized[0]) * (normalized[3] - normalized[1])
}

function unionArea(rectangles = []) {
  const rects = rectangles.map(normalizeBbox).filter(Boolean)
  if (!rects.length) return 0

  const xs = [...new Set(rects.flatMap((rect) => [rect[0], rect[2]]))].sort((a, b) => a - b)
  let area = 0

  for (let index = 0; index < xs.length - 1; index += 1) {
    const x1 = xs[index]
    const x2 = xs[index + 1]
    if (!(x2 > x1)) continue

    const midX = (x1 + x2) / 2
    const intervals = rects
      .filter((rect) => rect[0] < midX && rect[2] > midX)
      .map((rect) => [rect[1], rect[3]])
      .sort((left, right) => left[0] - right[0])

    if (!intervals.length) continue

    let coveredY = 0
    let [currentStart, currentEnd] = intervals[0]
    for (let intervalIndex = 1; intervalIndex < intervals.length; intervalIndex += 1) {
      const [start, end] = intervals[intervalIndex]
      if (start <= currentEnd) {
        currentEnd = Math.max(currentEnd, end)
      } else {
        coveredY += currentEnd - currentStart
        currentStart = start
        currentEnd = end
      }
    }
    coveredY += currentEnd - currentStart
    area += (x2 - x1) * coveredY
  }

  return area
}

export function assessCoverage(roiBbox, coverageBboxes = [], tolerance = 1e-6) {
  const roi = normalizeBbox(roiBbox)
  const coverages = coverageBboxes.map(normalizeBbox).filter(Boolean)
  if (!roi || !coverages.length) {
    return {
      status: 'unknown',
      roiBbox: roi,
      coverageCount: coverages.length,
      coveredAreaRatio: null,
      coveredArea: 0,
      roiArea: bboxArea(roi),
    }
  }

  const roiArea = bboxArea(roi)
  if (!(roiArea > 0)) {
    return {
      status: 'unknown',
      roiBbox: roi,
      coverageCount: coverages.length,
      coveredAreaRatio: null,
      coveredArea: 0,
      roiArea,
    }
  }

  const intersections = coverages.map((coverage) => intersectBbox(roi, coverage)).filter(Boolean)
  const coveredArea = unionArea(intersections)
  const coveredAreaRatio = coveredArea / roiArea

  let status = 'partial'
  if (coveredAreaRatio >= 1 - tolerance) status = 'inside'
  else if (coveredAreaRatio <= tolerance) status = 'outside'

  return {
    status,
    roiBbox: roi,
    coverageCount: coverages.length,
    coveredAreaRatio,
    coveredArea,
    roiArea,
  }
}
