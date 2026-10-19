// 极简全局状态：任务列表、用户、加载/错误态，变化后触发重渲染
export const state = {
  profile: { account: 'triple', password: '', nick: 'Triple', color: '#8b86e8', avatarUrl: '' },
  tasks: [
    { id: 1, title: '整理比赛测试通知（3 套）', date: '2026-10-20', done: false },
    { id: 2, title: '提交比赛报名表 + 成绩单', date: '2026-10-25', done: false },
    { id: 3, title: '缴纳报名费 100 元', date: '2026-10-30', done: false },
    { id: 4, title: '打印准考证', date: '2026-11-01', done: false },
    { id: 5, title: '现场答辩彩排', date: '2026-11-05', done: false },
    { id: 6, title: '画出三个页面草图', date: '2026-10-15', done: true, doneAt: '2026-10-15' }
  ],
  analyzing: false,     // AI 解析 loading
  analyzeError: '',     // 解析错误文案（带重试）
  analyzeResult: null,  // 最近一次解析结果 { mode, title, deadline, ... }
  activeTab: 'doing',
  onUpdate: null
}

export function setState(patch) {
  Object.assign(state, patch)
  state.onUpdate && state.onUpdate()
}

export function daysLeft(dateStr) {
  const today = new Date(); today.setHours(0, 0, 0, 0)
  return Math.round((new Date(dateStr + 'T00:00:00') - today) / 86400000)
}
