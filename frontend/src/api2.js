// 前端通过同源 /api 访问后端；开发时由 Vite proxy 转发到 127.0.0.1:8000
const BASE_URL = ''

const TIMEOUT = 90_000
let SESSION_ID = localStorage.getItem('zhiban-session-id')
if (!SESSION_ID) { SESSION_ID = 'web-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8); localStorage.setItem('zhiban-session-id', SESSION_ID) }

async function request(path, { method = 'POST', body } = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT)
  let res
  try {
    res = await fetch(BASE_URL + path, {
      method,
      headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal
    })
  } catch (err) {
    if (err.name === 'AbortError') throw new Error(`解析超时（> ${TIMEOUT / 1000}s），请稍后重试`)
    throw new Error(`连不上后端（${BASE_URL || '同源代理'}），请确认 C 的服务已启动`)
  } finally {
    clearTimeout(timer)
  }
  let payload = {}
  try { payload = await res.json() } catch { /* 非 JSON */ }
  if (!payload.success) {
    throw new Error(payload.error || `接口 ${path} 失败`)
  }
  return payload.data
}

export async function health() {
  try {
    const res = await fetch(BASE_URL + '/health')
    return await res.json()
  } catch {
    return { status: 'down' }
  }
}

export const analyzeNotification = (text) => request('/api/analyze', { body: { text } })
export const checkProfile = (payload) => request('/api/check', { body: payload })
export const prepareList = (payload) => request('/api/prepare-list', { body: payload })
export const savePrepareList = (payload) => request('/api/prepare-list/save', { body: payload })

export async function loadPrepareList(matterId) {
  const res = await fetch(`${BASE_URL}/api/prepare-list/${encodeURIComponent(matterId)}`, { headers: { 'X-Session-Id': SESSION_ID } })
  const payload = await res.json()
  if (!payload.success) throw new Error(payload.error || '加载准备清单失败')
  return payload.data
}

export async function analyzeImage(file) {
  const fd = new FormData(); fd.append('image', file)
  const ctrl = new AbortController(); const timer = setTimeout(() => ctrl.abort(), 90000)
  try {
    const res = await fetch(BASE_URL + '/api/analyze-image', { method: 'POST', body: fd, headers: { 'X-Session-Id': SESSION_ID }, signal: ctrl.signal })
    const payload = await res.json(); if (!payload.success) throw new Error(payload.error || '图片解析失败'); return payload.data
  } finally { clearTimeout(timer) }
}

export async function analyzePdf(file) {
  const fd = new FormData(); fd.append('file', file)
  const ctrl = new AbortController(); const timer = setTimeout(() => ctrl.abort(), 90000)
  try {
    const res = await fetch(BASE_URL + '/api/analyze-pdf', { method: 'POST', body: fd, headers: { 'X-Session-Id': SESSION_ID }, signal: ctrl.signal })
    const payload = await res.json(); if (!payload.success) throw new Error(payload.error || 'PDF 解析失败'); return payload.data
  } finally { clearTimeout(timer) }
}

export async function getEvidence(payload) {
  const res = await fetch(BASE_URL + '/api/evidence', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID }, body: JSON.stringify(payload) })
  return (await res.json()).data
}

export async function uploadFile(file) {
  const fd = new FormData(); fd.append('file', file)
  const res = await fetch(BASE_URL + '/api/files', { method: 'POST', body: fd, headers: { 'X-Session-Id': SESSION_ID } })
  const p = await res.json(); if (!p.success) throw new Error(p.error || '上传失败'); return p.data
}

export async function listFiles() {
  const res = await fetch(BASE_URL + '/api/files', { headers: { 'X-Session-Id': SESSION_ID } })
  const p = await res.json(); return p.data || []
}

export async function searchFiles(query) {
  const res = await fetch(BASE_URL + '/api/files/search', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID }, body: JSON.stringify({ query }) })
  return (await res.json()).data || []
}

export async function askQuestion(payload) {
  const res = await fetch(BASE_URL + '/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID }, body: JSON.stringify(payload) })
  const p = await res.json(); if (!p.success) throw new Error(p.error || '提问失败'); return p.data
}

export async function compareNotifications(payload) {
  const res = await fetch(BASE_URL + '/api/compare', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID }, body: JSON.stringify(payload) })
  const p = await res.json(); if (!p.success) throw new Error(p.error || '对比失败'); return p.data
}

export async function checkDate(payload) {
  const res = await fetch(BASE_URL + '/api/tools/check-date', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID }, body: JSON.stringify(payload) })
  const p = await res.json(); if (!p.success) throw new Error(p.error || '日期核对失败'); return p.data
}

export async function exportTasks() {
  const res = await fetch(BASE_URL + '/api/export', { headers: { 'X-Session-Id': SESSION_ID } })
  if (!res.ok) throw new Error('导出失败')
  const blob = await res.blob(); const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = 'tasks.csv'; a.click(); URL.revokeObjectURL(url)
}

export const apiBaseUrl = BASE_URL
