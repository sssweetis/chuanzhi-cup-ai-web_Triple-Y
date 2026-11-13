import { AppError, type AppErrorCode } from './errors.ts'
import type { ApiEnvelope, ApiErrorPayload, AnalysisResult } from './types.ts'

const BASE_URL = ''
export const REQUEST_WARNING_MS = 90_000

let SESSION_ID = localStorage.getItem('zhiban-session-id')
if (!SESSION_ID) {
  SESSION_ID = `web-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  localStorage.setItem('zhiban-session-id', SESSION_ID)
}

export interface RequestOptions {
  signal?: AbortSignal
  onTimeoutWarning?: () => void
  timeoutWarningMs?: number
}

function payloadCode(status: number, payload: ApiErrorPayload): AppErrorCode {
  const detail = payload.error
  const detailCode = detail && typeof detail === 'object' ? detail.code || '' : ''
  const detailMessage = detail && typeof detail === 'object' ? detail.message || '' : detail || ''
  const value = `${payload.error_code || ''} ${detailCode} ${detailMessage}`.toLowerCase()
  if (status === 429 || /rate.?limit|too many requests|请求过多/.test(value)) return 'rate_limited'
  if (status === 413 || /too large|payload too large|文件过大|超过.*大小/.test(value)) return 'file_too_large'
  if (status === 415 || /unsupported media|unsupported file|不支持.*格式/.test(value)) return 'unsupported_media'
  if (status === 401 || /unauthorized|api.?key|invalid token|llm.*401/.test(value)) return 'auth'
  if (/scanned|扫描版|扫描 pdf|no extractable text|未提取到文字/.test(value)) return 'scanned_pdf'
  if (/ocr|vision unavailable|图片识别|截图识别/.test(value)) return 'ocr_unavailable'
  if (/schema|validation|missing required|格式异常/.test(value)) return 'invalid_response'
  if (/empty result|no tasks|未找到.*任务|没有.*任务/.test(value)) return 'empty_result'
  if (/timeout|timed out|超时/.test(value)) return 'timeout'
  return status >= 500 ? 'server_error' : 'network'
}

function responseError(status: number, payload: ApiErrorPayload, path: string, cause?: unknown): AppError {
  return new AppError({
    code: payloadCode(status, payload),
    status,
    requestId: payload.request_id,
    cause: cause || { path, status, error: payload.error, errorCode: payload.error_code },
  })
}

function transportError(error: unknown): AppError {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return new AppError({ code: 'cancelled', cause: error })
  }
  if (error instanceof Error && /abort/i.test(error.name)) {
    return new AppError({ code: 'cancelled', cause: error })
  }
  const offline = typeof navigator !== 'undefined' && navigator.onLine === false
  return new AppError({ code: offline ? 'offline' : 'network', cause: error })
}

async function fetchWithWarning(url: string, init: RequestInit, options: RequestOptions): Promise<Response> {
  const controller = new AbortController()
  const forwardAbort = () => controller.abort(options.signal?.reason)
  if (options.signal?.aborted) forwardAbort()
  else options.signal?.addEventListener('abort', forwardAbort, { once: true })
  const warningTimer = options.onTimeoutWarning
    ? window.setTimeout(options.onTimeoutWarning, options.timeoutWarningMs || REQUEST_WARNING_MS)
    : 0
  try {
    return await fetch(url, { ...init, signal: controller.signal })
  } catch (error) {
    throw transportError(error)
  } finally {
    clearTimeout(warningTimer)
    options.signal?.removeEventListener('abort', forwardAbort)
  }
}

async function readEnvelope<T>(response: Response, path: string): Promise<T> {
  let payload: ApiEnvelope<T> = { success: false }
  try {
    payload = (await response.json()) as ApiEnvelope<T>
  } catch (error) {
    throw new AppError({ code: 'invalid_response', status: response.status, cause: { path, error } })
  }
  if (!response.ok || !payload.success) {
    throw responseError(response.status, payload, path, payload)
  }
  return payload.data as T
}

async function requestJson<T>(path: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
  const response = await fetchWithWarning(
    BASE_URL + path,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID },
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    options,
  )
  return readEnvelope<T>(response, path)
}

async function requestForm<T>(path: string, field: string, file: File, options: RequestOptions = {}): Promise<T> {
  const form = new FormData()
  form.append(field, file)
  const response = await fetchWithWarning(
    BASE_URL + path,
    {
      method: 'POST',
      body: form,
      headers: { 'X-Session-Id': SESSION_ID },
    },
    options,
  )
  return readEnvelope<T>(response, path)
}

export async function health(): Promise<{ status: string }> {
  try {
    const response = await fetch(`${BASE_URL}/health`)
    return await response.json()
  } catch {
    return { status: 'down' }
  }
}

export function analyzeNotification(text: string, options?: RequestOptions): Promise<AnalysisResult> {
  return requestJson('/api/analyze', { text }, options)
}

export function checkProfile<T = unknown>(payload: unknown, options?: RequestOptions): Promise<T> {
  return requestJson('/api/check', payload, options)
}

export function prepareList<T = { todo_list?: AnalysisResult['todo_list'] }>(
  payload: unknown,
  options?: RequestOptions,
): Promise<T> {
  return requestJson('/api/prepare-list', payload, options)
}

export function savePrepareList<T = unknown>(payload: unknown, options?: RequestOptions): Promise<T> {
  return requestJson('/api/prepare-list/save', payload, options)
}

export async function loadPrepareList<T = unknown>(matterId: string): Promise<T> {
  const path = `/api/prepare-list/${encodeURIComponent(matterId)}`
  try {
    const response = await fetch(BASE_URL + path, { headers: { 'X-Session-Id': SESSION_ID } })
    return await readEnvelope<T>(response, path)
  } catch (error) {
    throw error instanceof AppError ? error : transportError(error)
  }
}

export function analyzeImage(file: File, options?: RequestOptions): Promise<AnalysisResult> {
  return requestForm('/api/analyze-image', 'image', file, options)
}

export function analyzePdf(file: File, options?: RequestOptions): Promise<AnalysisResult> {
  return requestForm('/api/analyze-pdf', 'file', file, options)
}

export async function getEvidence<T = { found?: boolean; quote?: string; is_suggestion?: boolean }>(
  payload: unknown,
): Promise<T> {
  return requestJson('/api/evidence', payload)
}

export function uploadFile<T = unknown>(file: File): Promise<T> {
  return requestForm('/api/files', 'file', file)
}

export async function listFiles<T = unknown[]>(): Promise<T[]> {
  const path = '/api/files'
  try {
    const response = await fetch(BASE_URL + path, { headers: { 'X-Session-Id': SESSION_ID } })
    const payload = (await response.json()) as ApiEnvelope<T[]>
    if (!response.ok || !payload.success) throw responseError(response.status, payload, path)
    return payload.data || []
  } catch (error) {
    throw error instanceof AppError ? error : transportError(error)
  }
}

export function searchFiles<T = unknown[]>(query: string): Promise<T[]> {
  return requestJson('/api/files/search', { query })
}

export function askQuestion<
  T = {
    answer?: string
    found_evidence?: boolean
    evidence_chunks?: unknown[]
    sources?: unknown[]
  },
>(payload: unknown): Promise<T> {
  return requestJson('/api/ask', payload)
}

export function compareNotifications<
  T = {
    diff?: unknown
    left?: { matter?: AnalysisResult }
    right?: { matter?: AnalysisResult }
  },
>(payload: unknown): Promise<T> {
  return requestJson('/api/compare', payload)
}

export function checkDate<
  T = {
    message?: string
    suggestion?: string
    recommended_date?: string
  },
>(payload: unknown, options?: RequestOptions): Promise<T> {
  return requestJson('/api/tools/check-date', payload, options)
}

export async function exportTasks(): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/export`, { headers: { 'X-Session-Id': SESSION_ID } })
  if (!response.ok) throw new AppError({ code: 'server_error', status: response.status })
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'tasks.csv'
  anchor.click()
  URL.revokeObjectURL(url)
}

export const apiBaseUrl = BASE_URL
