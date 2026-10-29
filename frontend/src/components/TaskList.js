import { state, setState, daysLeft } from '../state.js'

// 展开态存在模块变量里（不持久化也行，刷新收起即可）
const expanded = new Set()
let searchTerm = ''

export function renderTaskList(mount) {
  mount.innerHTML = `
    <div class="card">
      <div class="list-head">
        <div class="list-title">任务清单</div>
        <div class="tabs">
          <button data-tab="doing" class="${state.activeTab === 'doing' ? 'on' : ''}">进行中 (${state.tasks.filter(t => !t.done).length})</button>
          <button data-tab="done" class="${state.activeTab === 'done' ? 'on' : ''}">最近完成 (${state.tasks.filter(t => t.done && daysOld(t.doneAt) <= 3).length})</button>
          <button data-tab="history" class="${state.activeTab === 'history' ? 'on' : ''}">历史清单 (${state.tasks.filter(t => t.done && daysOld(t.doneAt) > 3).length})</button>
        </div>
      </div>
      <div class="search-row">
        <input type="text" id="taskSearch" placeholder="搜索任务…" value="${searchTerm}">
        <button class="btn btn-ghost btn-sm" id="downloadList">⬇ 下载清单</button>
        ${state.activeTab === 'history' ? '<button class="btn btn-ghost btn-sm" id="clearHistory">清空全部历史</button>' : ''}
      </div>
      <div id="taskListBody"></div>
      <div class="empty" id="emptyTip" style="display:none">没有匹配的任务</div>
    </div>`

  function leftTag(t) {
    const n = daysLeft(t.date)
    if (n < 0) return `<span class="left-tag over">已逾期 ${-n} 天</span>`
    if (n === 0) return `<span class="left-tag over">紧急 · 今天截止</span>`
    if (n <= 2) return `<span class="left-tag over">紧急 · 还剩 ${n} 天</span>`
    if (n <= 7) return `<span class="left-tag mid">还剩 ${n} 天</span>`
    return `<span class="left-tag ok">还剩 ${n} 天</span>`
  }
  function daysOld(dateStr) {
    if (!dateStr) return 0
    return Math.round((Date.now() - new Date(dateStr + 'T00:00:00').getTime()) / 86400000)
  }

  const list = state.tasks.filter(t => {
    if (state.activeTab === 'doing') return !t.done
    if (state.activeTab === 'history') return t.done && daysOld(t.doneAt) > 3
    return t.done && daysOld(t.doneAt) <= 3
  }).filter(t => !searchTerm || t.title.toLowerCase().includes(searchTerm.toLowerCase()))
  .sort((a, b) => state.activeTab === 'doing' ? (a.date < b.date ? -1 : 1) : ((b.doneAt || '') < (a.doneAt || '') ? 1 : -1))

  const body = mount.querySelector('#taskListBody')
  mount.querySelector('#emptyTip').style.display = list.length ? 'none' : 'block'
  const emptyMsgs = {
    doing: '🎉 暂无进行中的任务，把上面的通知粘进来试试',
    done: '最近 3 天完成的任务会显示在这里',
    history: '完成超过 3 天的任务会自动归入历史清单'
  }
  mount.querySelector('#emptyTip').textContent = emptyMsgs[state.activeTab] || '暂无任务'

  body.innerHTML = list.map(t => {
    const open = expanded.has(t.id)
    const steps = Array.isArray(t.steps) ? t.steps : []
    const doneSteps = steps.filter(s => s.done).length
    return `
    <div class="task-row ${t.done ? 'done-row' : ''} ${state.focusDate === t.date ? 'focus-row' : ''}">
      <div class="task-main">
        <span class="task-arrow ${open ? 'open' : ''}">▸</span>
        <span class="task-title" data-expand="${t.id}" title="点击展开">${t.title}</span>
        <button class="task-edit" data-edit="${t.id}" title="改名">✏️</button>
        <span class="task-date">${t.done ? '' : t.date}</span>
        <span class="task-left">${t.done ? `<span class="done-at">完成于 ${t.doneAt || ''}</span>` : leftTag(t)}</span>
        ${t.done
          ? `<button class="btn btn-ghost btn-sm" data-undo="${t.id}" title="误触了？点这里恢复">撤销完成</button>`
          : `<button class="btn btn-ghost btn-sm" data-done="${t.id}">完成</button>`}
        ${state.activeTab === 'history' ? `<button class="btn btn-ghost btn-sm" data-del="${t.id}" title="删除">🗑</button>` : ''}
      </div>
      ${open ? `
      <div class="task-detail">
        ${t.desc ? `<div class="detail-line"><b>要求：</b>${t.desc}</div>` : ''}
        <div class="detail-line"><b>截止：</b>${t.date}</div>
        <div class="detail-line detail-sub">子任务（${doneSteps}/${steps.length}）</div>
        <ul class="step-chk">
          ${steps.map((s, i) => `<li><label><input type="checkbox" data-step="${t.id}" data-sid="${s.id}" ${s.done ? 'checked' : ''}> ${s.title}</label>
            <button class="step-mv" data-up="${t.id}" data-sid="${s.id}" ${i === 0 ? 'disabled' : ''} title="上移">↑</button>
            <button class="step-mv" data-down="${t.id}" data-sid="${s.id}" ${i === steps.length - 1 ? 'disabled' : ''} title="下移">↓</button>
            <button class="step-del" data-delsep="${t.id}" data-sid="${s.id}" title="删除">×</button></li>`).join('')}
          ${steps.length === 0 ? '<li class="detail-empty">还没有子任务，在下面加一条</li>' : ''}
        </ul>
        <div class="add-step-row">
          <input type="text" placeholder="加一条子任务/备注，回车确认" data-addstep="${t.id}" class="add-step-input">
        </div>
        ${t.note ? `<div class="detail-line"><b>备注：</b>${t.note}</div>` : ''}
        ${t.sourceText ? `<div class="detail-line"><button class="btn btn-ghost btn-sm" data-src="${t.id}">📄 查看原文通知</button></div>` : ''}
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

  // 撤销完成（误触恢复）
  body.querySelectorAll('[data-undo]').forEach(b => b.onclick = () => {
    const t = state.tasks.find(x => x.id === Number(b.dataset.undo))
    t.done = false; t.doneAt = ''
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

  // 删除子任务
  body.querySelectorAll('[data-delsep]').forEach(b => b.onclick = () => {
    const t = state.tasks.find(x => x.id === Number(b.dataset.delsep))
    t.steps = t.steps.filter(s => s.id !== Number(b.dataset.sid))
    setState({})
  })

  // 子任务上下移动
  function moveStep(taskId, sid, dir) {
    const t = state.tasks.find(x => x.id === taskId)
    const i = t.steps.findIndex(s => s.id === sid)
    const j = i + dir
    if (i < 0 || j < 0 || j >= t.steps.length) return
    const [x] = t.steps.splice(i, 1)
    t.steps.splice(j, 0, x)
    setState({})
  }
  body.querySelectorAll('[data-up]').forEach(b => b.onclick = () => moveStep(Number(b.dataset.up), Number(b.dataset.sid), -1))
  body.querySelectorAll('[data-down]').forEach(b => b.onclick = () => moveStep(Number(b.dataset.down), Number(b.dataset.sid), 1))

  // 点击改名按钮
  body.querySelectorAll('[data-edit]').forEach(el => el.onclick = (e) => {
    e.stopPropagation()
    const id = Number(el.dataset.edit)
    const titleEl = el.parentElement.querySelector('.task-title')
    const old = titleEl.textContent
    const input = document.createElement('input')
    input.value = old
    input.style.cssText = 'font:inherit;flex:1;border:1px solid #8b86e8;border-radius:4px;padding:2px 6px;'
    titleEl.replaceWith(input)
    el.style.display = 'none'
    input.focus(); input.select()
    const save = () => {
      const v = input.value.trim()
      if (v) {
        const t = state.tasks.find(x => x.id === id)
        if (t) t.title = v
      }
      setState({})
    }
    input.onblur = save
    input.onkeydown = (e) => { if (e.key === 'Enter') input.blur(); if (e.key === 'Escape') { input.value = old; input.blur() } }
  })

  mount.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {
    setState({ activeTab: b.dataset.tab })
  })

  // 搜索
  mount.querySelector('#taskSearch').oninput = (e) => {
    searchTerm = e.target.value
    renderTaskList(mount)
    mount.querySelector('#taskSearch').focus()
    mount.querySelector('#taskSearch').setSelectionRange(searchTerm.length, searchTerm.length)
  }

  // 删除单条
  body.querySelectorAll('[data-del]').forEach(b => b.onclick = () => {
    state.tasks = state.tasks.filter(x => x.id !== Number(b.dataset.del))
    setState({})
  })

  // 查看原文通知
  body.querySelectorAll('[data-src]').forEach(b => b.onclick = () => {
    const t = state.tasks.find(x => x.id === Number(b.dataset.src))
    if (!t || !t.sourceText) return
    let mask = document.getElementById('srcMask')
    if (!mask) {
      mask = document.createElement('div')
      mask.id = 'srcMask'
      mask.className = 'mask'
      mask.innerHTML = `<div class="modal">
        <h3>📄 原文通知</h3>
        <div class="src-quote-modal" id="srcQuote" style="max-height:50vh;overflow:auto;white-space:pre-wrap"></div>
        <div class="modal-foot"><button class="btn btn-primary" id="srcClose">关闭</button></div>
      </div>`
      document.body.appendChild(mask)
      mask.onclick = (e) => { if (e.target === mask) mask.classList.remove('show') }
      mask.querySelector('#srcClose').onclick = () => mask.classList.remove('show')
    }
    mask.querySelector('#srcQuote').textContent = t.sourceText
    mask.classList.add('show')
  })

  // 清空全部历史
  const clr = mount.querySelector('#clearHistory')
  if (clr) clr.onclick = () => {
    if (!confirm('确定清空全部历史清单？此操作不可恢复。')) return
    state.tasks = state.tasks.filter(t => !(t.done && daysOld(t.doneAt) > 3))
    setState({})
  }

  // 下载清单 CSV
  mount.querySelector('#downloadList').onclick = () => {
    const rows = [['任务', '截止日期', '状态', '备注']]
    state.tasks.forEach(t => {
      rows.push([t.title, t.date, t.done ? '已完成' : '进行中', t.note || ''])
    })
    const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `任务清单_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }
}
