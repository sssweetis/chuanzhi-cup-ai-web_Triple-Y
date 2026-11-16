import { describe, expect, it, vi } from 'vitest'
import {
  AppError,
  ERROR_SCENARIOS,
  assertAnalysisResult,
  normalizeError,
  renderErrorState,
  userErrorMessage,
} from '../src/errors.ts'

describe('error scenarios', () => {
  it('exposes exactly 12 user-facing scenarios', () => {
    expect(Object.keys(ERROR_SCENARIOS)).toHaveLength(12)
  })

  it.each([
    ['429 rate limit', 'rate_limited'],
    ['413 payload too large', 'file_too_large'],
    ['415 unsupported media', 'unsupported_media'],
    ['scanned pdf with no extractable text', 'scanned_pdf'],
    ['llm api key unauthorized', 'auth'],
    ['ocr unavailable', 'ocr_unavailable'],
    ['schema validation missing required', 'invalid_response'],
    ['timeout after 90 seconds', 'timeout'],
    ['empty result no tasks', 'empty_result'],
  ])('maps %s to %s', (message, code) => {
    expect(normalizeError(new Error(message)).code).toBe(code)
  })

  it('maps offline devices to the offline scenario', () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    expect(normalizeError(new Error('Failed to fetch')).code).toBe('offline')
  })

  it('does not expose backend implementation details', () => {
    const message = userErrorMessage(new Error('服务内部异常：C的服务未启动 at 127.0.0.1'))
    expect(message).not.toMatch(/127\.0\.0\.1|C 的服务|服务内部异常|API Key/i)
  })

  it('uses a safe backend message as fallback copy', () => {
    const message = userErrorMessage(
      new AppError({ code: 'server_error', backendMessage: '当前暂时无法解析，请稍后重试' }),
    )
    expect(message).toBe('当前暂时无法解析，请稍后重试')
  })

  it('rejects an empty analysis result', () => {
    expect(() => assertAnalysisResult(null)).toThrow(AppError)
    expect(() => assertAnalysisResult({ title: '任务' })).not.toThrow()
  })

  it('renders an aria-live error card with actions and reference number', () => {
    const container = document.createElement('div')
    renderErrorState(container, new AppError({ code: 'network', requestId: 'TY-TEST-001' }), {
      onRetry: vi.fn(),
    })
    expect(container.querySelector('[role="alert"]')).not.toBeNull()
    expect(container.querySelector('[aria-live="assertive"]')).not.toBeNull()
    expect(container.textContent).toContain('TY-TEST-001')
    expect(container.querySelector('[data-error-action="retry"]')).not.toBeNull()
  })

  it('shows a safe backend error message but hides technical details', () => {
    const safe = document.createElement('div')
    renderErrorState(safe, new AppError({ code: 'server_error', backendMessage: '材料解析暂时不可用，请稍后重试' }))
    expect(safe.textContent).toContain('服务说明')
    expect(safe.textContent).toContain('材料解析暂时不可用')

    const unsafe = document.createElement('div')
    renderErrorState(unsafe, new AppError({ code: 'server_error', backendMessage: 'Traceback at 127.0.0.1' }))
    expect(unsafe.textContent).not.toContain('127.0.0.1')
  })
})
