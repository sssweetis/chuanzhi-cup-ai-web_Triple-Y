import { state, setState, daysLeft } from '../state.js'

export function renderTaskList(mount) {
  mount.innerHTML = `
    <div class="card">
      <div class="list-head">
        <div class="list-title">任务清单</div>
        <div class="tabs">
          <button data-tab="doing" class="${state.activeTab === 'doing' ? 'on' : ''}">进行中 (${state.tasks.filter(t => !t.done).length})</button>
          <button data-tab="done" class="${state.activeTab === 'done' ? 'on' : ''}">历史清单 (${state.tasks.filter(t => t.done).length})</button>
        </div>
      </div>
      <table class="tasks">
        <thead><tr><th>截止日期</th><th>任务</th><th>剩余时间</th><th style="text-align:right">操作</th></tr></thead>
        <tbody id="taskBody"></tbody>
      </table>
      <div class="empty" id="emptyTip" style="display:none">这里还没有内容</div>
    </div>`

  function leftTag(t) {
    const n = daysLeft(t.date)
    if (n < 0) return `<span class="left-tag over">已逾期 ${-n} 天</span>`
    if (n === 0) return `<span class="left-tag over">紧急 · 今天截止</span>`
    if (n <= 2) return `<span class="left-tag over">紧急 · 还剩 ${n} 天</span>`
    if (n <= 7) return `<span class="left-tag mid">还剩 ${n} 天</span>`
    return `<span class="left-tag ok">还剩 ${n} 天</span>`
  }

  const list = state.tasks
    .filter(t => state.activeTab === 'doing' ? !t.done : t.done)
    .sort((a, b) => state.activeTab === 'doing' ? a.date < b.date ? -1 : 1 : (b.doneAt || '') < (a.doneAt || '') ? 1 : -1)

  const body = mount.querySelector('#taskBody')
  mount.querySelector('#emptyTip').style.display = list.length ? 'none' : 'block'
  body.innerHTML = list.map(t => `
    <tr class="${t.done ? 'done-row' : ''}">
      <td class="c-date">${t.date}</td>
      <td class="c-task">${t.title}</td>
      <td class="c-left">${t.done ? `<span class="done-at">完成于 ${t.doneAt || ''}</span>` : leftTag(t)}</td>
      <td class="c-act">${t.done ? '' : `<button class="btn btn-ghost btn-sm" data-done="${t.id}">已完成</button>`}</td>
    </tr>`).join('')

  body.querySelectorAll('[data-done]').forEach(b => b.onclick = () => {
    const t = state.tasks.find(x => x.id === Number(b.dataset.done))
    t.done = true; t.doneAt = new Date().toISOString().slice(0, 10)
    setState({})
  })
  mount.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {
    setState({ activeTab: b.dataset.tab })
  })
}
