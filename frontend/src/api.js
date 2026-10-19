// 后端联调：http://127.0.0.1:8000，CORS 已开，无需代理
// 响应信封统一为 HTTP 200 + { success, data, error }，这里拆开返回 data / 抛 error
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')
const TIMEOUT = 90_000

async function request(path, { method = 'POST', body } = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT)
  let res
  try {
    res = await fetch(BASE_URL + path, {
      method,
      headers: { 'Content-Type': 'application/json' },
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
// body: { notification_id, profile:{team_size,has_doc,has_video,has_teacher_confirm}, checked_material_ids:string[] }
export const checkProfile = (payload) =>
  request('/api/check', { body: payload })

export const apiBaseUrl = BASE_URL
