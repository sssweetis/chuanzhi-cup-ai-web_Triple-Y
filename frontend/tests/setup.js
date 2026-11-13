import { beforeEach, vi } from 'vitest'

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.useRealTimers()
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
})
