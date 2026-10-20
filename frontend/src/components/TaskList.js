import { state, setState, daysLeft } from '../state.js'

// 展开态存在模块变量里（不持久化也行，刷新收起即可）
const expanded = new Set()

export function renderTaskList(mount) {
  mount.innerHTML = `
    <div class="card">
      <div class="list-head">
        <div class="list-title">任务清单</div>
        <div class="tabs">
          <button data-tab="doing" class="${state.activeTab === 'doing' ? 'on' : ''}">进行中 (${state.tasks.filter(t => !t.done).length})</button>
          <button data-tab="done" class="${state.activeTab === 'done' ? 'on' : ''}">已完成 (${state.tasks.filter(t => t.done).length})</button>
        </div>
      </div>
      <div id="taskListBody"></div>
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
    .sort((a, b) => state.activeTab === 'doing' ? (a.date < b.date ? -1 : 1) : ((b.doneAt || '') < (a.doneAt || '') ? 1 : -1))

  const body = mount.querySelector('#taskListBody')
  mount.querySelector('#emptyTip').style.display = list.length ? 'none' : 'block'

  body.innerHTML = list.map(t => {
    const open = expanded.has(t.id)
    const steps = Array.isArray(t.steps) ? t.steps : []
    const doneSteps = steps.filter(s => s.done).length
    return `
    <div class="task-row ${t.done ? 'done-row' : ''}">
      <div class="task-main">
        <span class="task-arrow ${open ? 'open' : ''}">▸</span>
        <span class="task-title" data-expand="${t.id}">${t.title}</span>
        <span class="task-date">${t.date}</span>
        <span class="task-left">${t.done ? `<span class="done-at">完成于 ${t.doneAt || ''}</span>` : leftTag(t)}</span>
        ${t.done ? '' : `<button class="btn btn-ghost btn-sm" data-done="${t.id}">完成</button>`}
      </div>
      ${open ? `
      <div class="task-detail">
        ${t.desc ? `<div class="detail-line"><b>要求：</b>${t.desc}</div>` : ''}
        <div class="detail-line"><b>截止：</b>${t.date}</div>
        <div class="detail-line detail-sub">子任务（${doneSteps}/${steps.length}）</div>
        <ul class="step-chk">
          ${steps.map(s => `<li><label><input type="checkbox" data-step="${t.id}" data-sid="${s.id}" ${s.done ? 'checked' : ''}> ${s.title}</label></li>`).join('')}
          ${steps.length === 0 ? '<li class="detail-empty">还没有子任务，在下面加一条</li>' : ''}
        </ul>
        <div class="add-step-row">
          <input type="text" placeholder="加一条子任务/备注，回车确认" data-addstep="${t.id}" class="add-step-input">
        </div>
        ${t.note ? `<div class="detail-line"><b>备注：</b>${t.note}</div>` : ''}
      </div>` : ''}
    </div>`
  }).join('')

  // 展开/收起
  body.querySelectorAll('[data-expand]').forEach(el => el.onclick = () => {
    const id = Number(el.dataset.expand)
    expanded.has(id) ? expanded.delete(id) : expanded.add(id)
    renderTaskList(mount)
  })

  // 完成按钮
  body.querySelectorAll('[data-done]').forEach(b => b.onclick = () => {
    const t = state.tasks.find(x => x.id === Number(b.dataset.done))
    t.done = true; t.doneAt = new Date().toISOString().slice(0, 10)
    setState({})
  })

  // 子任务勾选
  body.querySelectorAll('[data-step]').forEach(cb => cb.onchange = () => {
    const t = state.tasks.find(x => x.id === Number(cb.dataset.step))
    const s = t.steps.find(x => x.id === Number(cb.dataset.sid))
    if (s) s.done = cb.checked
    setState({})
  })

  // 加子任务
  body.querySelectorAll('[data-addstep]').forEach(inp => {
    inp.onkeydown = (e) => {
      if (e.key === 'Enter' && inp.value.trim()) {
        const t = state.tasks.find(x => x.id === Number(inp.dataset.addstep))
        if (!Array.isArray(t.steps)) t.steps = []
        t.steps.push({ id: Date.now(), title: inp.value.trim(), done: false })
        setState({})
      }
    }
  })

  mount.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {
    setState({ activeTab: b.dataset.tab })
  })
}
