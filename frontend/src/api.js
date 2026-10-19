// 统一的接口封装：BASE_URL 走 .env，超时 60s（真实解析 10~30s，不能更短）
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const TIMEOUT = 60_000

async function request(path, { method = 'POST', body } = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT)
  try {
    const res = await fetch(BASE_URL + path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`接口 ${path} 返回 ${res.status}：${text || '请稍后重试'}`)
    }
    return await res.json()
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('请求超时（60s），解析时间过长，请重试')
    throw err
  } finally {
    clearTimeout(timer)
  }
}

// 提交一段通知原文，AI 解析成任务卡片
// 返回结构（A 对齐）：{ mode: 'simple'|'standard'|'complex', title, deadline,
//                     materials[], location, notes[], steps[], assignee, warnings[] }
export const analyzeNotification = (text) =>
  request('/api/analyze', { body: { text } })

// 用户填写团队情况 + 勾选已备材料，后端据此算出"已准备/缺少/需要确认"
// payload: { notification_id, profile: { team_size, has_doc, has_video, has_teacher_confirm },
//            checked_material_ids: string[] }
export const checkProfile = (payload) =>
  request('/api/check', { body: payload })

export const apiBaseUrl = BASE_URL
