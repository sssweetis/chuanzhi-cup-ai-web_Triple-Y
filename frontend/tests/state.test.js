import { describe, expect, it, vi } from 'vitest'

describe('state persistence and dates', () => {
  it('restores tasks and profile from the existing localStorage key', async () => {
    localStorage.setItem(
      'zhiban-state-v2',
      JSON.stringify({
        profile: { nick: '测试用户', password: 'legacy-password' },
        tasks: [{ id: 9, title: '恢复任务', date: '2026-11-20', done: false }],
        activeTab: 'doing',
      }),
    )
    vi.resetModules()
    const { state } = await import('../src/state.ts')
    expect(state.profile.nick).toBe('测试用户')
    expect('password' in state.profile).toBe(false)
    expect(JSON.parse(localStorage.getItem('zhiban-state-v2')).profile.password).toBeUndefined()
    expect(state.tasks[0].title).toBe('恢复任务')
  })

  it('persists setState without changing the localStorage key', async () => {
    vi.resetModules()
    const { setState, state } = await import('../src/state.ts')
    setState({ activeTab: 'history', resultIsDemo: true })
    expect(JSON.parse(localStorage.getItem('zhiban-state-v2')).activeTab).toBe('history')
    expect(JSON.parse(localStorage.getItem('zhiban-state-v2')).resultIsDemo).toBe(true)
    expect(state.activeTab).toBe('history')
  })

  it('handles today, tomorrow and invalid dates correctly', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-12T09:00:00+08:00'))
    const { daysLeft, toDateKey } = await import('../src/state.ts')
    expect(daysLeft('2026-11-12')).toBe(0)
    expect(daysLeft('2026-11-13')).toBe(1)
    expect(daysLeft('2026-11-15T18:00:00+08:00')).toBe(3)
    expect(daysLeft('2026-02-31')).toBeNull()
    expect(daysLeft('bad-date')).toBeNull()
    expect(daysLeft(null)).toBeNull()
    expect(toDateKey('2026-11-15T18:00:00+08:00')).toBe('2026-11-15')
    expect(toDateKey('')).toBe('')
  })
})
