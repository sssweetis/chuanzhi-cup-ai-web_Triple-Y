import type { AnalysisResult } from './types.ts'
import { copyText, escapeHtml, showToast } from './util.ts'

export type ErrorActionKey = 'continue' | 'retry' | 'edit' | 'reupload' | 'help'

export type AppErrorCode =
  | 'offline'
  | 'network'
  | 'timeout'
  | 'rate_limited'
  | 'file_too_large'
  | 'unsupported_media'
  | 'scanned_pdf'
  | 'empty_result'
  | 'auth'
  | 'ocr_unavailable'
  | 'server_error'
  | 'invalid_response'

export type InternalErrorCode = AppErrorCode | 'cancelled'

export interface ErrorScenario {
  code: AppErrorCode
  title: string
  message: string
  next: string
  actions: ErrorActionKey[]
}

export interface AppErrorInit {
  code: InternalErrorCode
  status?: number
  requestId?: string
  retryable?: boolean
  cause?: unknown
}

export interface ErrorStateHandlers {
  onContinue?: () => void
  onRetry?: () => void
  onEdit?: () => void
  onReupload?: () => void
  onHelp?: () => void
}

const ACTION_LABELS: Record<ErrorActionKey, string> = {
  continue: '继续等待',
  retry: '重试',
  edit: '换文字',
  reupload: '重新上传',
  help: '查看帮助',
}

export const ERROR_SCENARIOS: Record<AppErrorCode, ErrorScenario> = {
  offline: {
    code: 'offline',
    title: '当前没有网络',
    message: '通知还在这里，只是现在暂时连不上解析服务。',
    next: '连接网络后再试一次，输入内容不会丢失。',
    actions: ['retry', 'edit'],
  },
  network: {
    code: 'network',
    title: '连接服务失败',
    message: '这次请求没有送达，已经替你保留输入内容。',
    next: '稍后重试；如果一直失败，可以先换成文字通知。',
    actions: ['retry', 'edit'],
  },
  timeout: {
    code: 'timeout',
    title: '这次处理得有点久',
    message: '已经等待 90 秒，任务可能还在处理中。',
    next: '可以继续等待，也可以重新发起或换一段文字。',
    actions: ['continue', 'retry', 'edit'],
  },
  rate_limited: {
    code: 'rate_limited',
    title: '提交得有点频繁',
    message: '短时间内的请求比较多，暂时需要缓一缓。',
    next: '等待几十秒后再试，已经填写的内容会保留。',
    actions: ['retry', 'edit'],
  },
  file_too_large: {
    code: 'file_too_large',
    title: '这个文件太大了',
    message: '文件超过了当前可处理的大小。',
    next: '压缩图片或换一个更小的文件后重新上传。',
    actions: ['reupload', 'edit', 'help'],
  },
  unsupported_media: {
    code: 'unsupported_media',
    title: '暂时读不了这种格式',
    message: '这个文件格式不在当前支持范围内。',
    next: '请改用 JPG、PNG、文字型 PDF，或直接粘贴通知文字。',
    actions: ['reupload', 'edit', 'help'],
  },
  scanned_pdf: {
    code: 'scanned_pdf',
    title: '这份 PDF 可能是扫描版',
    message: '没有从文件中提取到可识别的文字。',
    next: '把相关页面截图后上传，或直接粘贴通知原文。',
    actions: ['reupload', 'edit', 'help'],
  },
  empty_result: {
    code: 'empty_result',
    title: '没有找到明确任务',
    message: '通知里可能缺少截止时间、步骤或材料信息。',
    next: '补充上下文或换一段更完整的通知再试。',
    actions: ['edit', 'retry', 'help'],
  },
  auth: {
    code: 'auth',
    title: '解析服务需要维护',
    message: '后台的解析凭证暂时不可用，这不是你的操作问题。',
    next: '请联系维护人员；演示时可以先打开离线示例。',
    actions: ['help', 'edit'],
  },
  ocr_unavailable: {
    code: 'ocr_unavailable',
    title: '截图文字识别暂不可用',
    message: '当前无法读取图片里的文字。',
    next: '可以直接粘贴文字，或稍后更换一张更清晰的截图。',
    actions: ['reupload', 'edit', 'retry'],
  },
  server_error: {
    code: 'server_error',
    title: '这次没有处理完成',
    message: '服务遇到了临时问题，输入内容已经保留。',
    next: '稍后重试；如果反复出现，可以复制错误编号反馈。',
    actions: ['retry', 'edit', 'help'],
  },
  invalid_response: {
    code: 'invalid_response',
    title: '结果没有整理完整',
    message: '服务返回了结果，但内容缺少必要字段。',
    next: '重试一次，或者换一段更完整的通知。',
    actions: ['retry', 'edit', 'help'],
  },
}

function referenceNumber(): string {
  return `TY-${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).slice(2, 5).toUpperCase()}`
}

function codeFromMessage(message: string, status?: number): InternalErrorCode {
  const text = message.toLowerCase()
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return 'offline'
  if (status === 429 || /rate.?limit|too many requests|请求过多/.test(text)) return 'rate_limited'
  if (status === 413 || /too large|payload too large|文件过大|超过.*大小/.test(text)) return 'file_too_large'
  if (status === 415 || /unsupported media|unsupported file|不支持.*格式/.test(text)) return 'unsupported_media'
  if (status === 401 || /unauthorized|api.?key|llm.*401|invalid token/.test(text)) return 'auth'
  if (/scanned|扫描版|扫描 pdf|no extractable text|未提取到文字/.test(text)) return 'scanned_pdf'
  if (/ocr|vision unavailable|图片识别|截图识别/.test(text)) return 'ocr_unavailable'
  if (/schema|validation|missing required|格式异常/.test(text)) return 'invalid_response'
  if (/empty result|no tasks|未找到.*任务|没有.*任务/.test(text)) return 'empty_result'
  if (/timeout|timed out|超时/.test(text)) return 'timeout'
  if (/failed to fetch|networkerror|network request failed|offline/.test(text)) return 'network'
  return status && status >= 500 ? 'server_error' : 'server_error'
}

export class AppError extends Error {
  code: InternalErrorCode
  status?: number
  requestId: string
  retryable: boolean

  constructor({ code, status, requestId, retryable, cause }: AppErrorInit) {
    super(code)
    this.name = 'AppError'
    this.code = code
    this.status = status
    this.requestId = requestId || referenceNumber()
    this.retryable = retryable ?? !['auth', 'cancelled'].includes(code)
    this.cause = cause
  }
}

export type ApiError = AppError

export function normalizeError(error: unknown, fallbackCode: InternalErrorCode = 'server_error'): AppError {
  if (error instanceof AppError) return error
  if (error instanceof DOMException && error.name === 'AbortError') {
    return new AppError({ code: 'cancelled', cause: error })
  }
  if (error instanceof Error && /abort/i.test(error.name)) {
    return new AppError({ code: 'cancelled', cause: error })
  }
  const message = error instanceof Error ? error.message : String(error || '')
  return new AppError({
    code: codeFromMessage(message, undefined) || fallbackCode,
    cause: error,
  })
}

export function isCancelled(error: unknown): boolean {
  return normalizeError(error).code === 'cancelled'
}

export function getErrorScenario(error: AppError | null | undefined): ErrorScenario {
  if (!error || error.code === 'cancelled') return ERROR_SCENARIOS.server_error
  return ERROR_SCENARIOS[error.code]
}

export function userErrorMessage(error: unknown, fallback = '操作没有完成，请稍后再试。'): string {
  const normalized = normalizeError(error)
  if (normalized.code === 'cancelled') return '操作已取消。'
  const scenario = getErrorScenario(normalized)
  return scenario ? `${scenario.title}。${scenario.next}` : fallback
}

export function assertAnalysisResult(data: AnalysisResult | null | undefined): AnalysisResult {
  if (!data || (!data.title && !Array.isArray(data.enabled_sections))) {
    throw new AppError({ code: 'empty_result' })
  }
  return data
}

export function renderErrorState(container: HTMLElement, error: AppError, handlers: ErrorStateHandlers = {}): void {
  const scenario = getErrorScenario(error)
  container.innerHTML = `
    <div class="error-state" role="alert" aria-live="assertive">
      <div class="error-state-head">
        <span class="error-state-mark" aria-hidden="true">!</span>
        <div>
          <h3>${escapeHtml(scenario.title)}</h3>
          <p>${escapeHtml(scenario.message)}</p>
        </div>
      </div>
      <div class="error-next"><b>下一步</b><span>${escapeHtml(scenario.next)}</span></div>
      <div class="error-actions">
        ${scenario.actions
          .map(
            (action, index) => `
          <button class="btn ${index === 0 ? 'btn-primary' : 'btn-ghost'} btn-sm" type="button" data-error-action="${action}">
            ${escapeHtml(ACTION_LABELS[action])}
          </button>
        `,
          )
          .join('')}
        <button class="btn btn-ghost btn-sm error-copy" type="button" data-error-action="copy">复制错误编号</button>
      </div>
      <div class="error-reference">错误编号：${escapeHtml(error.requestId)}</div>
    </div>`
  container.querySelectorAll<HTMLElement>('[data-error-action]').forEach((button) => {
    button.onclick = async () => {
      const action = button.dataset.errorAction
      if (action === 'copy') {
        const copied = await copyText(error.requestId)
        showToast(copied ? '错误编号已复制' : `错误编号：${error.requestId}`, copied ? 'success' : 'info')
        return
      }
      if (action === 'continue') handlers.onContinue?.()
      if (action === 'retry') handlers.onRetry?.()
      if (action === 'edit') handlers.onEdit?.()
      if (action === 'reupload') handlers.onReupload?.()
      if (action === 'help') handlers.onHelp?.()
    }
  })
}
