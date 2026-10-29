// 后端联调：http://127.0.0.1:8000，CORS 已开，无需代理
// 响应信封统一为 HTTP 200 + { success, data, error }，这里拆开返回 data / 抛 error
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')
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
    throw new Error(`连不上后端（${BASE_URL}），请确认 C 的服务已启动`)
  } finally {
    clearTimeout(timer)
  }
  // 后端永远 200 + { success, data, error }
  let payload = {}
  try { payload = await res.json() } catch { /* 非 JSON */ }
  if (!payload.success) {
    throw new Error(payload.error || `接口 ${path} 失败`)
  }
  return payload.data
}

// 健康检查：{ status:'ok', mode:'mock'|'real' }
export async function health() {
  try {
    const res = await fetch(BASE_URL + '/health')
    return await res.json()
  } catch {
    return { status: 'down' }
  }
}

// POST /api/analyze  body: { text: '通知原文' } → Matter 对象
export const analyzeNotification = (text) =>
  request('/api/analyze', { body: { text } })

// POST /api/check
// body: { matter?: Matter对象, profile:{people_count,has_doc,has_video,has_teacher_confirm}, checked_material_ids:string[] }
// 返回 checked / missing_required / missing_optional / need_confirm / profile_issues / summary
export const checkProfile = (payload) =>
  request('/api/check', { body: payload })

// POST /api/prepare-list
// body: { matter, checked_material_ids } 或 { text }
// 返回 { matter_id, title, todo_list[], missing_items[], ready_items[], summary }
export const prepareList = (payload) =>
  request('/api/prepare-list', { body: payload })

// POST /api/prepare-list/save
// body: { matter_id, todo_list, checked_material_ids? } → { matter_id, todo_list, saved_at }
export const savePrepareList = (payload) =>
  request('/api/prepare-list/save', { body: payload })

// GET /api/prepare-list/{matter_id} → 之前保存的记录
export async function loadPrepareList(matterId) {
  const res = await fetch(`${BASE_URL}/api/prepare-list/${encodeURIComponent(matterId)}`, { headers: { 'X-Session-Id': SESSION_ID } })
  const payload = await res.json()
  if (!payload.success) throw new Error(payload.error || '加载准备清单失败')
  return payload.data
}

// POST /api/analyze-image  multipart/form-data 字段名 image → Matter
export async function analyzeImage(file) {
  const fd = new FormData()
  fd.append('image', file)
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 90000)
  try {
    const res = await fetch(BASE_URL + '/api/analyze-image', { method: 'POST', body: fd, headers: { 'X-Session-Id': SESSION_ID }, signal: ctrl.signal })
    const payload = await res.json()
    if (!payload.success) throw new Error(payload.error || '图片解析失败')
    return payload.data
  } finally { clearTimeout(timer) }
}

// POST /api/analyze-pdf  FormData 字段 file → Matter
export async function analyzePdf(file) {
  const fd = new FormData()
  fd.append('file', file)
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 90000)
  try {
    const res = await fetch(BASE_URL + '/api/analyze-pdf', { method: 'POST', body: fd, headers: { 'X-Session-Id': SESSION_ID }, signal: ctrl.signal })
    const payload = await res.json()
    if (!payload.success) throw new Error(payload.error || 'PDF 解析失败')
    return payload.data
  } finally { clearTimeout(timer) }
}

// POST /api/evidence  {matter, target_type, target_id} → {found, title, quote, is_suggestion, note}
export async function getEvidence(payload) {
  const res = await fetch(BASE_URL + '/api/evidence', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID },
    body: JSON.stringify(payload)
  })
  return (await res.json()).data
}

// POST /api/files  FormData 字段 file → {file_id, filename}
export async function uploadFile(file) {
  const fd = new FormData(); fd.append('file', file)
  const res = await fetch(BASE_URL + '/api/files', { method: 'POST', body: fd, headers: { 'X-Session-Id': SESSION_ID } })
  const p = await res.json()
  if (!p.success) throw new Error(p.error || '上传失败')
  return p.data
}

// GET /api/files → 已上传文件列表
export async function listFiles() {
  const res = await fetch(BASE_URL + '/api/files', { headers: { 'X-Session-Id': SESSION_ID } })
  const p = await res.json()
  return p.data || []
}

// POST /api/files/search  {query} → [{file_id, filename, chunk_id, text, score}]
export async function searchFiles(query) {
  const res = await fetch(BASE_URL + '/api/files/search', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID },
    body: JSON.stringify({ query })
  })
  return (await res.json()).data || []
}

// POST /api/ask  {question, file_ids?} → {answer, sources}
export async function askQuestion(payload) {
  const res = await fetch(BASE_URL + '/api/ask', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID },
    body: JSON.stringify(payload)
  })
  const p = await res.json()
  if (!p.success) throw new Error(p.error || '提问失败')
  return p.data
}

// POST /api/compare  {old_notification, new_notification} → diff/affected_todos
export async function compareNotifications(payload) {
  const res = await fetch(BASE_URL + '/api/compare', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID },
    body: JSON.stringify(payload)
  })
  const p = await res.json()
  if (!p.success) throw new Error(p.error || '对比失败')
  return p.data
}

// POST /api/tools/check-date  {deadline} → 剩余天数/节假日/建议
export async function checkDate(payload) {
  const res = await fetch(BASE_URL + '/api/tools/check-date', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID },
    body: JSON.stringify(payload)
  })
  const p = await res.json()
  if (!p.success) throw new Error(p.error || '日期核对失败')
  return p.data
}

export const apiBaseUrl = BASE_URL
