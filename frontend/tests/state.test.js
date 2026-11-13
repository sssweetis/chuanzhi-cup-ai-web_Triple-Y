import { describe, expect, it, vi } from 'vitest'

describe('state persistence and dates', () => {
  it('restores tasks and profile from the existing localStorage key', async () => {
    localStorage.setItem('zhiban-state-v2', JSON.stringify({
      profile: { nick: '测试用户' },
      tasks: [{ id: 9, title: '恢复任务', date: '2026-11-20', done: false }],
      activeTab: 'doing',
    }))
    vi.resetModules()
    const { state } = await import('../src/state.ts')
    expect(state.profile.nick).toBe('测试用户')
    expect(state.tasks[0].title).toBe('恢复任务')
  })

  it('persists setState without changing the localStorage key', async () => {
    vi.resetModules()
    const { setState, state } = await import('../src/state.ts')
    setState({ activeTab: 'history' })
    expect(JSON.parse(localStorage.getItem('zhiban-state-v2')).activeTab).toBe('history')
    expect(state.activeTab).toBe('history')
  })

  it('handles today, tomorrow and invalid dates correctly', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-12T09:00:00+08:00'))
    const { daysLeft } = await import('../src/state.ts')
    expect(daysLeft('2026-11-12')).toBe(0)
    expect(daysLeft('2026-11-13')).toBe(1)
    expect(Number.isNaN(daysLeft('2026-02-31'))).toBe(true)
    expect(Number.isNaN(daysLeft('bad-date'))).toBe(true)
  })
})
