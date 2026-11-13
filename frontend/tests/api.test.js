// @ts-nocheck -- fetch mocks intentionally implement only the Response fields used by the API layer.
import { beforeEach, describe, expect, it, vi } from 'vitest'

async function loadApi() {
  vi.resetModules()
  return import('../src/api2.ts')
}

describe('api cancellation and response mapping', () => {
  beforeEach(() => {
    localStorage.setItem('zhiban-session-id', 'test-session')
  })

  it('cancels an in-flight analysis request', async () => {
    const { analyzeNotification } = await loadApi()
    globalThis.fetch = vi.fn(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
        }),
    )
    const controller = new AbortController()
    const request = analyzeNotification('通知', { signal: controller.signal })
    controller.abort()
    await expect(request).rejects.toMatchObject({ code: 'cancelled' })
  })

  it('emits the 90 second warning without aborting the request', async () => {
    vi.useFakeTimers()
    const { analyzeNotification } = await loadApi()
    globalThis.fetch = vi.fn(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
        }),
    )
    const onTimeoutWarning = vi.fn()
    const controller = new AbortController()
    const request = analyzeNotification('通知', { signal: controller.signal, onTimeoutWarning })
    await vi.advanceTimersByTimeAsync(90_000)
    expect(onTimeoutWarning).toHaveBeenCalledTimes(1)
    expect(controller.signal.aborted).toBe(false)
    controller.abort()
    await expect(request).rejects.toMatchObject({ code: 'cancelled' })
  })

  it('maps a 429 envelope to a friendly rate-limit error', async () => {
    const { analyzeNotification } = await loadApi()
    globalThis.fetch = vi.fn(async () => ({
      ok: false,
      status: 429,
      json: async () => ({ success: false, error: 'Too many requests' }),
    }))
    await expect(analyzeNotification('通知')).rejects.toMatchObject({ code: 'rate_limited', status: 429 })
  })

  it('maps a structured error object without exposing its message', async () => {
    const { analyzeNotification } = await loadApi()
    globalThis.fetch = vi.fn(async () => ({
      ok: false,
      status: 401,
      json: async () => ({
        success: false,
        error: { code: 'llm_unauthorized', message: 'internal api key invalid at 127.0.0.1' },
        request_id: 'req-structured-401',
      }),
    }))
    await expect(analyzeNotification('通知')).rejects.toMatchObject({
      code: 'auth',
      status: 401,
      requestId: 'req-structured-401',
    })
  })

  it('keeps the existing X-Session-Id header', async () => {
    const { analyzeNotification } = await loadApi()
    globalThis.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: { title: '任务' } }),
    }))
    await analyzeNotification('通知')
    expect(globalThis.fetch.mock.calls[0][1].headers['X-Session-Id']).toBe('test-session')
  })
})
