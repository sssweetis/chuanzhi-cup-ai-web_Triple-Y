// 极简全局状态：任务列表、用户、加载/错误态，变化后触发重渲染
// 10/20：tasks / profile / 最近结果 持久化到 localStorage，刷新不丢
const LS_KEY = 'zhiban-state-v2'

function loadInitial() {
  const base = {
    profile: { account: 'triple', password: '', nick: 'Triple', color: '#8b86e8', avatarUrl: '' },
    tasks: [
      { id: 1, title: '示例任务 1：提交申报书', date: '2026-11-15', done: false },
      { id: 2, title: '示例任务 2：缴纳评审费', date: '2026-11-20', done: false },
      { id: 3, title: '示例任务 3：参加现场答辩', date: '2026-12-05', done: false }
    ],
    analyzing: false,
    analyzeError: '',
    analyzeResult: null,
    activeTab: 'doing',
    onUpdate: null
  }
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (raw) {
      const saved = JSON.parse(raw)
      if (saved.profile) base.profile = { ...base.profile, ...saved.profile }
      if (Array.isArray(saved.tasks)) base.tasks = saved.tasks
      if (saved.analyzeResult) base.analyzeResult = saved.analyzeResult
      if (saved.activeTab) base.activeTab = saved.activeTab
    }
  } catch { /* 损坏就用默认 */ }
  return base
}

export const state = loadInitial()

export function setState(patch) {
  Object.assign(state, patch)
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({
      profile: state.profile,
      tasks: state.tasks,
      analyzeResult: state.analyzeResult,
      activeTab: state.activeTab
    }))
  } catch {}
  state.onUpdate && state.onUpdate()
}

export function daysLeft(dateStr) {
  const today = new Date(); today.setHours(0, 0, 0, 0)
  return Math.round((new Date(dateStr + 'T00:00:00') - today) / 86400000)
}
