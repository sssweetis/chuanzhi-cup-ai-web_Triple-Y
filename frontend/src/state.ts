import type { AppError } from './errors.ts'
import type { ActiveTab, AnalysisResult, AnalysisStageKey, AppState, Profile, Task } from './types.ts'

export const STATE_STORAGE_KEY = 'zhiban-state-v2'

function loadInitial(): AppState {
  const base: AppState = {
    profile: { account: 'triple', password: '', nick: 'Triple', color: '#8b86e8', avatarUrl: '' },
    tasks: [
      { id: 1, title: '示例任务 1：提交申报书', date: '2026-11-15', done: false },
      { id: 2, title: '示例任务 2：缴纳评审费', date: '2026-11-20', done: false },
      { id: 3, title: '示例任务 3：参加现场答辩', date: '2026-12-05', done: false },
    ],
    analyzing: false,
    analyzeError: null,
    analyzeResult: null,
    resultFromImage: false,
    activeTab: 'doing',
    analysisStage: 'preparing',
    analysisSlow: false,
    analysisNotice: '',
    onUpdate: null,
  }
  try {
    const raw = localStorage.getItem(STATE_STORAGE_KEY)
    if (raw) {
      const saved = JSON.parse(raw) as {
        profile?: Profile
        tasks?: Task[]
        analyzeResult?: AnalysisResult
        activeTab?: ActiveTab
      }
      if (saved.profile) base.profile = { ...base.profile, ...saved.profile }
      if (Array.isArray(saved.tasks)) base.tasks = saved.tasks
      if (saved.analyzeResult) base.analyzeResult = saved.analyzeResult
      if (saved.activeTab) base.activeTab = saved.activeTab
    }
  } catch {
    // 损坏的数据不应阻止页面启动。
  }
  return base
}

export const state: AppState = loadInitial()

export interface SetStateOptions {
  notify?: boolean
}

export function setState(patch: Partial<AppState>, options: SetStateOptions = {}): void {
  const changedKeys = Object.keys(patch)
  Object.assign(state, patch)
  try {
    localStorage.setItem(
      STATE_STORAGE_KEY,
      JSON.stringify({
        profile: state.profile,
        tasks: state.tasks,
        analyzeResult: state.analyzeResult,
        activeTab: state.activeTab,
      }),
    )
  } catch {
    // localStorage 不可用时仍保留本次会话内状态。
  }
  if (options.notify === false) return
  state.onUpdate?.(changedKeys)
  window.dispatchEvent(new CustomEvent('zhiban:state-change', { detail: { keys: changedKeys } }))
}

export function setAnalysisStage(stage: AnalysisStageKey): void {
  setState({ analysisStage: stage }, { notify: false })
}

export function clearAnalysisError(): void {
  if (state.analyzeError) setState({ analyzeError: null, analysisNotice: '' }, { notify: false })
}

export function daysLeft(dateStr: string): number {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(dateStr || ''))
  if (!match) return Number.NaN
  const year = Number(match[1])
  const month = Number(match[2]) - 1
  const day = Number(match[3])
  const target = new Date(year, month, day)
  if (target.getFullYear() !== year || target.getMonth() !== month || target.getDate() !== day) return Number.NaN
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  target.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - today.getTime()) / 86400000)
}

export type { AppError }
