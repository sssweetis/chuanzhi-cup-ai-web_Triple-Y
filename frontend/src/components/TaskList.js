// @ts-nocheck -- 渐进迁移：任务 UI 尚在使用 JS 模板渲染。
import { state, setState, daysLeft } from '../state.js'
import { closeModal, escapeHtml, openModal, showToast } from '../util.js'
import { userErrorMessage } from '../errors.js'

// 展开态存在模块变量里（不持久化也行，刷新收起即可）
const expanded = new Set()
let searchTerm = ''

export function renderTaskList(mount) {
  mount.innerHTML = `
    <div class="card task-card">
      <div class="list-head">
        <div>
          <div class="list-title">任务清单</div>
          <div class="list-subtitle">按截止时间自动排序</div>
        </div>
        <div class="tabs" role="tablist" aria-label="任务状态">
          <button type="button" role="tab" data-tab="doing" aria-selected="${state.activeTab === 'doing'}" class="${state.activeTab === 'doing' ? 'on' : ''}">进行中 (${state.tasks.filter((t) => !t.done).length})</button>
          <button type="button" role="tab" data-tab="done" aria-selected="${state.activeTab === 'done'}" class="${state.activeTab === 'done' ? 'on' : ''}">最近完成 (${state.tasks.filter((t) => t.done && daysOld(t.doneAt) <= 3).length})</button>
          <button type="button" role="tab" data-tab="history" aria-selected="${state.activeTab === 'history'}" class="${state.activeTab === 'history' ? 'on' : ''}">历史清单 (${state.tasks.filter((t) => t.done && daysOld(t.doneAt) > 3).length})</button>
        </div>
      </div>
      <div class="search-row">
        <label class="search-field">
          <span class="search-icon" aria-hidden="true">⌕</span>
          <input type="search" id="taskSearch" placeholder="搜索任务…" value="${escapeHtml(searchTerm)}" aria-label="搜索任务">
        </label>
        <button class="btn btn-ghost btn-sm" id="downloadList" type="button">⬇ 下载清单</button>
        ${state.activeTab === 'history' ? '<button class="btn btn-ghost btn-sm btn-danger-ghost" id="clearHistory" type="button">清空全部历史</button>' : ''}
      </div>
      <div id="taskListBody" class="task-list-body"></div>
      <div class="empty" id="emptyTip" hidden></div>
    </div>`

  function leftTag(t) {
    const n = daysLeft(t.date)
    if (n < 0) return `<span class="left-tag over">已逾期 ${-n} 天</span>`
    if (n === 0) return `<span class="left-tag urgent">紧急 · 今天截止</span>`
    if (n <= 2) return `<span class="left-tag urgent">紧急 · 还剩 ${n} 天</span>`
    if (n <= 7) return `<span class="left-tag mid">还剩 ${n} 天</span>`
    return `<span class="left-tag ok">还剩 ${n} 天</span>`
  }
  function daysOld(dateStr) {
    if (!dateStr) return 0
    return Math.round((Date.now() - new Date(dateStr + 'T00:00:00').getTime()) / 86400000)
  }

  const list = state.tasks
    .filter((t) => {
      if (state.activeTab === 'doing') return !t.done
      if (state.activeTab === 'history') return t.done && daysOld(t.doneAt) > 3
      return t.done && daysOld(t.doneAt) <= 3
    })
    .filter((t) => !searchTerm || t.title.toLowerCase().includes(searchTerm.toLowerCase()))
    .sort((a, b) =>
      state.activeTab === 'doing' ? (a.date < b.date ? -1 : 1) : (b.doneAt || '') < (a.doneAt || '') ? 1 : -1,
    )

  const body = mount.querySelector('#taskListBody')
  const emptyMsgs = {
    doing: '🎉 暂无进行中的任务，把上面的通知粘进来试试',
    done: '最近 3 天完成的任务会显示在这里',
    history: '完成超过 3 天的任务会自动归入历史清单',
  }
  const emptyTip = mount.querySelector('#emptyTip')
  emptyTip.hidden = Boolean(list.length)
  emptyTip.textContent = searchTerm ? `没有找到与“${searchTerm}”匹配的任务` : emptyMsgs[state.activeTab] || '暂无任务'

  body.innerHTML = list
    .map((t) => {
      const open = expanded.has(t.id)
      const steps = Array.isArray(t.steps) ? t.steps : []
      const doneSteps = steps.filter((s) => s.done).length
      return `
    <article class="task-row ${t.done ? 'done-row' : ''} ${state.focusDate === t.date ? 'focus-row' : ''}" data-task-id="${t.id}">
      <div class="task-main">
        <button class="task-arrow ${open ? 'open' : ''}" data-expand="${t.id}" type="button" aria-expanded="${open}" aria-label="${open ? '收起任务' : '展开任务'}">▸</button>
        <div class="task-content">
          <div class="task-title-line">
            <button class="task-title" data-expand="${t.id}" type="button" aria-expanded="${open}">${escapeHtml(t.title)}</button>
            <button class="task-edit" data-edit="${t.id}" type="button" aria-label="修改任务名称" title="改名">✏️</button>
          </div>
          <div class="task-meta">
            <span class="task-date">${t.done ? '' : escapeHtml(t.date)}</span>
            <span class="task-left">${t.done ? `<span class="done-at">完成于 ${escapeHtml(t.doneAt || '')}</span>` : leftTag(t)}</span>
          </div>
        </div>
        <div class="task-actions">
          ${
            t.done
              ? `<button class="btn btn-ghost btn-sm" data-undo="${t.id}" type="button" title="误触了？点这里恢复">撤销</button>`
              : `<button class="btn btn-primary btn-sm" data-done="${t.id}" type="button">完成</button>`
          }
          ${state.activeTab === 'history' ? `<button class="btn btn-ghost btn-sm btn-icon" data-del="${t.id}" type="button" title="删除">🗑</button>` : ''}
        </div>
      </div>
      ${
        open
          ? `
      <div class="task-detail">
        ${t.desc ? `<div class="detail-line"><b>要求：</b><span class="detail-text">${escapeHtml(t.desc)}</span></div>` : ''}
        <div class="detail-line"><b>截止：</b>${escapeHtml(t.date)}</div>
        <div class="detail-line detail-sub">子任务（${doneSteps}/${steps.length}）</div>
        <ul class="step-chk">
          ${steps
            .map(
              (
                s,
                i,
              ) => `<li><label class="step-label"><input type="checkbox" data-step="${t.id}" data-sid="${s.id}" ${s.done ? 'checked' : ''}> <span>${escapeHtml(s.title)}</span></label>
            <span class="step-actions">
              <button class="step-mv" data-up="${t.id}" data-sid="${s.id}" ${i === 0 ? 'disabled' : ''} type="button" aria-label="上移子任务">↑</button>
              <button class="step-mv" data-down="${t.id}" data-sid="${s.id}" ${i === steps.length - 1 ? 'disabled' : ''} type="button" aria-label="下移子任务">↓</button>
              <button class="step-del" data-delsep="${t.id}" data-sid="${s.id}" type="button" aria-label="删除子任务">×</button>
            </span></li>`,
            )
            .join('')}
          ${steps.length === 0 ? '<li class="detail-empty">还没有子任务，在下面加一条</li>' : ''}
        </ul>
        <div class="add-step-row">
          <input type="text" placeholder="加一条子任务/备注，回车确认" data-addstep="${t.id}" class="add-step-input" aria-label="添加子任务">
        </div>
        ${t.note ? `<div class="detail-line"><b>备注：</b><span class="detail-text">${escapeHtml(t.note)}</span></div>` : ''}
        ${t.sourceText ? `<div class="detail-line"><button class="btn btn-ghost btn-sm" data-src="${t.id}" type="button">📄 查看原文通知</button></div>` : ''}
      </div>`
          : ''
      }
    </article>`
    })
    .join('')

  // 展开/收起
  body.querySelectorAll('[data-expand]').forEach(
    (el) =>
      (el.onclick = () => {
        const id = Number(el.dataset.expand)
        expanded.has(id) ? expanded.delete(id) : expanded.add(id)
        renderTaskList(mount)
      }),
  )

  // 完成按钮
  body.querySelectorAll('[data-done]').forEach(
    (b) =>
      (b.onclick = () => {
        const t = state.tasks.find((x) => x.id === Number(b.dataset.done))
        t.done = true
        t.doneAt = new Date().toISOString().slice(0, 10)
        setState({ tasks: state.tasks })
        showToast(`已完成「${t.title}」`, 'success')
      }),
  )

  // 撤销完成（误触恢复）
  body.querySelectorAll('[data-undo]').forEach(
    (b) =>
      (b.onclick = () => {
        const t = state.tasks.find((x) => x.id === Number(b.dataset.undo))
        t.done = false
        t.doneAt = ''
        setState({ tasks: state.tasks })
        showToast('任务已恢复到进行中')
      }),
  )

  // 子任务勾选
  body.querySelectorAll('[data-step]').forEach(
    (cb) =>
      (cb.onchange = () => {
        const t = state.tasks.find((x) => x.id === Number(cb.dataset.step))
        const s = t.steps.find((x) => x.id === Number(cb.dataset.sid))
        if (s) s.done = cb.checked
        setState({ tasks: state.tasks })
      }),
  )

  // 加子任务
  body.querySelectorAll('[data-addstep]').forEach((inp) => {
    inp.onkeydown = (e) => {
      if (e.key === 'Enter' && inp.value.trim()) {
        const t = state.tasks.find((x) => x.id === Number(inp.dataset.addstep))
        if (!Array.isArray(t.steps)) t.steps = []
        t.steps.push({ id: Date.now(), title: inp.value.trim(), done: false })
        const taskId = t.id
        setState({ tasks: state.tasks })
        showToast('子任务已添加')
        requestAnimationFrame(() => mount.querySelector(`[data-addstep="${taskId}"]`)?.focus())
      }
    }
  })

  // 删除子任务
  body.querySelectorAll('[data-delsep]').forEach(
    (b) =>
      (b.onclick = () => {
        const t = state.tasks.find((x) => x.id === Number(b.dataset.delsep))
        t.steps = t.steps.filter((s) => s.id !== Number(b.dataset.sid))
        setState({ tasks: state.tasks })
      }),
  )

  // 子任务上下移动
  function moveStep(taskId, sid, dir) {
    const t = state.tasks.find((x) => x.id === taskId)
    const i = t.steps.findIndex((s) => s.id === sid)
    const j = i + dir
    if (i < 0 || j < 0 || j >= t.steps.length) return
    const [x] = t.steps.splice(i, 1)
    t.steps.splice(j, 0, x)
    setState({ tasks: state.tasks })
  }
  body
    .querySelectorAll('[data-up]')
    .forEach((b) => (b.onclick = () => moveStep(Number(b.dataset.up), Number(b.dataset.sid), -1)))
  body
    .querySelectorAll('[data-down]')
    .forEach((b) => (b.onclick = () => moveStep(Number(b.dataset.down), Number(b.dataset.sid), 1)))

  // 点击改名按钮
  body.querySelectorAll('[data-edit]').forEach(
    (el) =>
      (el.onclick = (e) => {
        e.stopPropagation()
        const id = Number(el.dataset.edit)
        const titleEl = el.parentElement.querySelector('.task-title')
        const old = titleEl.textContent
        const input = document.createElement('input')
        input.value = old
        input.className = 'inline-edit'
        titleEl.replaceWith(input)
        el.style.display = 'none'
        input.focus()
        input.select()
        let finished = false
        const save = () => {
          if (finished) return
          finished = true
          const v = input.value.trim()
          if (v) {
            const t = state.tasks.find((x) => x.id === id)
            if (t) t.title = v
          }
          setState({ tasks: state.tasks })
          showToast('任务名称已更新')
        }
        input.onblur = save
        input.onkeydown = (e) => {
          if (e.key === 'Enter') input.blur()
          if (e.key === 'Escape') {
            finished = true
            renderTaskList(mount)
          }
        }
      }),
  )

  mount.querySelectorAll('.tabs button').forEach(
    (b) =>
      (b.onclick = () => {
        setState({ activeTab: b.dataset.tab })
      }),
  )

  // 搜索
  mount.querySelector('#taskSearch').oninput = (e) => {
    searchTerm = e.target.value
    renderTaskList(mount)
    mount.querySelector('#taskSearch').focus()
    mount.querySelector('#taskSearch').setSelectionRange(searchTerm.length, searchTerm.length)
  }

  // 删除单条
  body.querySelectorAll('[data-del]').forEach(
    (b) =>
      (b.onclick = () => {
        state.tasks = state.tasks.filter((x) => x.id !== Number(b.dataset.del))
        setState({ tasks: state.tasks })
        showToast('任务已删除')
      }),
  )

  // 查看原文通知
  body.querySelectorAll('[data-src]').forEach(
    (b) =>
      (b.onclick = () => {
        const t = state.tasks.find((x) => x.id === Number(b.dataset.src))
        if (!t || !t.sourceText) return
        let mask = document.getElementById('srcMask')
        if (!mask) {
          mask = document.createElement('div')
          mask.id = 'srcMask'
          mask.className = 'mask'
          mask.innerHTML = `<div class="modal">
        <h3>📄 原文通知</h3>
        <div class="src-quote-modal" id="srcQuote"></div>
        <div class="modal-foot"><button class="btn btn-primary" id="srcClose">关闭</button></div>
      </div>`
          document.body.appendChild(mask)
          mask.querySelector('#srcClose').onclick = () => closeModal(mask)
        }
        mask.querySelector('#srcQuote').textContent = t.sourceText
        openModal(mask, { initialFocus: '#srcClose' })
      }),
  )

  function openConfirmDialog({ title, message, confirmText, onConfirm }) {
    let mask = document.getElementById('confirmActionMask')
    if (!mask) {
      mask = document.createElement('div')
      mask.id = 'confirmActionMask'
      mask.className = 'mask'
      mask.innerHTML = `<div class="modal">
        <div class="modal-kicker">请确认操作</div>
        <h3 id="confirmActionTitle"></h3>
        <p class="modal-copy" id="confirmActionMessage"></p>
        <div class="modal-foot">
          <button class="btn btn-ghost" id="confirmActionCancel" type="button">取消</button>
          <button class="btn btn-primary" id="confirmActionSubmit" type="button"></button>
        </div>
      </div>`
      document.body.appendChild(mask)
      mask.querySelector('#confirmActionCancel').onclick = () => closeModal(mask)
    }
    mask.querySelector('#confirmActionTitle').textContent = title
    mask.querySelector('#confirmActionMessage').textContent = message
    const submit = mask.querySelector('#confirmActionSubmit')
    submit.textContent = confirmText
    submit.onclick = () => {
      closeModal(mask)
      onConfirm()
    }
    openModal(mask, { initialFocus: '#confirmActionCancel' })
  }

  // 清空全部历史
  const clr = mount.querySelector('#clearHistory')
  if (clr)
    clr.onclick = () => {
      openConfirmDialog({
        title: '清空全部历史清单？',
        message: '完成超过 3 天的任务会从这里移除，此操作不可恢复。',
        confirmText: '清空历史',
        onConfirm: () => {
          state.tasks = state.tasks.filter((t) => !(t.done && daysOld(t.doneAt) > 3))
          setState({ tasks: state.tasks })
          showToast('历史清单已清空')
        },
      })
    }

  // 下载清单 CSV（前端本地生成）
  mount.querySelector('#downloadList').onclick = () => {
    try {
      const rows = [['标题', '截止日期', '状态', '备注']]
      state.tasks.forEach((t) => {
        rows.push([t.title, t.date, t.done ? '已完成' : '进行中', t.note || ''])
      })
      const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'tasks.csv'
      a.click()
      URL.revokeObjectURL(url)
      showToast('清单已导出', 'success')
    } catch (error) {
      showToast(userErrorMessage(error, '导出失败，请稍后重试。'), 'error')
    }
  }
}
