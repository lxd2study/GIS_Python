export const DEFAULT_API_BASE = 'http://127.0.0.1:5001'

export function normalizeApiBase(value) {
  const normalized = String(value || '').trim().replace(/\/+$/, '')
  return normalized || DEFAULT_API_BASE
}

export function buildApiUrl(apiBase, path) {
  const normalizedPath = String(path || '')
  return `${normalizeApiBase(apiBase)}${normalizedPath.startsWith('/') ? normalizedPath : `/${normalizedPath}`}`
}

export function parseApiErrorDetail(detail) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === 'object' ? item.msg || JSON.stringify(item) : String(item)))
      .join(' | ')
  }
  if (detail && typeof detail === 'object') return detail.msg || JSON.stringify(detail)
  return '请求失败'
}

export async function apiRequest(apiBase, path, options = {}) {
  const response = await fetch(buildApiUrl(apiBase, path), options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(parseApiErrorDetail(data.detail || data.message || `HTTP ${response.status}`))
  }
  return data
}
