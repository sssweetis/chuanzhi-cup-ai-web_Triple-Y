// 按 A 的 UI 建议稿版式渲染：emoji 分区标题 + 标题右侧优先级徽章
// 仍遵守 5 条规则：只画 enabled_sections、步骤按索引、dependencies 连线、材料模板跳转、出处悬浮
const PRIORITY_LABEL = { low: '低优先级', medium: '中优先级', high: '高优先级', urgent: '紧急' }
const PRIORITY_CLS = { low: 'p-low', medium: 'p-mid', high: 'p-high', urgent: 'p-urgent' }
const MAT_STATUS = { pending: '未准备', uploaded: '已上传', submitted: '已提交', approved: '已通过', rejected: '已驳回' }
const MAT_STATUS_CLS = { pending: 'st-pending', uploaded: 'st-mid', submitted: 'st-mid', approved: 'st-ok', rejected: 'st-bad' }
const STEP_STATUS = { not_started: '未开始', pending: '待处理', in_progress: '进行中', completed: '已完成', done: '已完成' }
const STEP_NUM = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩']

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
function countdown(iso) {
  if (!iso) return ''
  const diff = new Date(iso) - new Date()
  if (diff <= 0) return '已到期'
  const days = Math.floor(diff / 86400000)
  const hours = Math.floor((diff % 86400000) / 3600000)
  return days > 0 ? `还剩 ${days} 天 ${hours} 小时` : `还剩 ${hours} 小时`
}
function hasSection(m, key) {
  return Array.isArray(m.enabled_sections) && m.enabled_sections.includes(key)
}
function tip(quote, type, id) {
  if (!quote && !type) return ''
  return `<button class="src-btn" data-quote="${(quote || '').replace(/"/g, '&quot;')}" data-type="${type || ''}" data-id="${id || ''}">出处</button>`
}
// 分区小标题：📋 材料清单 这种 emoji + 标题的形式
function sec(emoji, text) {
  return `<div class="mc-sec"><span class="mc-sec-emoji">${emoji}</span>${text}</div>`
}

export function renderMatter(m) {
  if (!m) return ''
  try { return _render(m) } catch { return '<div class="ph">解析结果格式异常</div>' }
}

function _render(m) {
  let html = '<div class="matter-card">'

  // 顶部：标题 + 右侧优先级
  if (hasSection(m, 'summary')) {
    const prio = m.priority && m.priority !== 'low'
      ? `<span class="p-chip ${PRIORITY_CLS[m.priority] || ''}">${PRIORITY_LABEL[m.priority] || m.priority}</span>` : ''
    const cat = m.category ? `<div class="mc-cat">📌 ${m.category}</div>` : ''
    html += `<div class="mc-title-row"><h1 class="mc-title">${m.title || '未命名任务'}</h1>${prio}</div>${cat}`
  }

  // ⏰ 截止
  if (hasSection(m, 'schedule') && m.deadline && m.deadline.due_at) {
    const range = (m.deadline.start_at && m.deadline.end_at)
      ? `<div class="mc-line">📅 整体：${fmtTime(m.deadline.start_at).slice(0, 10)} ~ ${fmtTime(m.deadline.end_at).slice(0, 10)}</div>`
      : ''
    html += `<div class="mc-block">
      <div class="mc-line">⏰ 截止：${fmtTime(m.deadline.due_at)}</div>
      <div class="mc-line mc-count">${countdown(m.deadline.due_at)}</div>
      ${range}
    </div>`
    if (Array.isArray(m.reminders) && m.reminders.length) {
      const r = m.reminders[0]
      html += `<div class="mc-line">🔔 提醒：提前 ${Math.round((r.offset_minutes || 0) / 60)} 小时</div>`
    }
    if (m.default_location && m.default_location.name) {
      html += `<div class="mc-line">📍 地点：${m.default_location.name}</div>`
    }
  }

  // ✍️ 注意（key_points）
  if (hasSection(m, 'content') && Array.isArray(m.key_points) && m.key_points.length) {
    html += sec('✍️', '注意')
    html += `<ul class="mc-bullet">${m.key_points.map(k => `<li>· ${k}</li>`).join('')}</ul>`
  }

  // 🔁 流程时间线（complex 步骤，按索引排）
  if (hasSection(m, 'steps') && Array.isArray(m.step_list) && m.step_list.length) {
    const matMap = {}
    ;(m.materials || []).forEach(x => { matMap[x.material_id] = x.material_name })
    html += sec('🔁', `流程时间线（${m.step_list.length} 步）`)
    html += `<ol class="step-tree">`
    m.step_list.forEach((s, i) => {
      const num = STEP_NUM[i] || (i + 1)
      let dueAt = s.due_at
      if (!dueAt && s.due_at_inherited_from === 'overall' && m.deadline) dueAt = m.deadline.due_at
      const dueTxt = dueAt ? `（${fmtTime(dueAt).slice(5, 16)}）` : ''
      const done = s.status === 'completed' || s.status === 'done'
      const subs = Array.isArray(s.sub_step_list) && s.sub_step_list.length
        ? `<div class="tree-branch">${s.sub_step_list.map(sub => `<div class="tree-line">├ ${sub.title}</div>`).join('')}</div>` : ''
      const owner = s.owner ? `<div class="tree-line">👤 ${s.owner.name}</div>` : ''
      const review = s.review && s.review.required
        ? `<div class="tree-line tree-warn">⚠ ${s.review.reviewer ? s.review.reviewer.name + ' 审核通过才能继续' : '需审核'}</div>` : ''
      html += `<li>
        <div class="step-head"><span class="step-num">${num}</span> ${s.title} ${dueTxt}
          ${tip(s.source_ref && s.source_ref.quote, 'step', s.step_id)}
          <span class="st-badge ${done ? 'st-ok' : 'st-pending'}">${STEP_STATUS[s.status] || s.status || ''}</span>
        </div>
        ${subs}${owner}${review}
      </li>`
    })
    html += `</ol>`
  }

  // 📋 材料清单（只读展示；勾选只在下面"我们队的情况"做）
  if (hasSection(m, 'materials') && Array.isArray(m.materials) && m.materials.length) {
    const attMap = {}
    ;(m.attachments || []).forEach(a => { attMap[a.attachment_id] = a })
    html += sec('📋', `材料清单（${m.materials.length} 项）`)
    html += `<ul class="mat-list">`
    m.materials.forEach(mat => {
      const att = attMap[mat.template_attachment_id]
      const url = att && att.attachment_url
      const typeTag = mat.material_type === 'optional' ? '（可选）' : '（必填）'
      const tpl = url ? ` <a class="tpl-link" href="${url}" target="_blank" rel="noopener">[下载模板]</a>` : ''
      const st = mat.status === 'uploaded' || mat.status === 'approved' || mat.status === 'submitted'
        ? `<span class="st-badge st-ok">已准备</span>`
        : `<span class="st-badge st-pending">未准备</span>`
      html += `<li>
        <b>${mat.material_name}</b> ${typeTag} ${st}
        ${tpl} ${tip(mat.source_ref && mat.source_ref.quote, 'material', mat.material_id)}
      </li>`
    })
    html += `</ul>`
  }

  // 📎 附件
  if (hasSection(m, 'content') && Array.isArray(m.attachments) && m.attachments.length) {
    html += sec('📎', '附件')
    html += `<div class="att-row">${m.attachments.map(a =>
      a.attachment_url
        ? `<a class="btn btn-ghost btn-sm" href="${a.attachment_url}" target="_blank" rel="noopener">⬇ ${a.attachment_name}</a>`
        : `<span class="btn btn-ghost btn-sm" style="opacity:.6">📎 ${a.attachment_name}</span>`
    ).join('')}</div>`
  }

  // ⚠️ 预警
  if (hasSection(m, 'warnings') && Array.isArray(m.warning_list) && m.warning_list.length) {
    html += sec('⚠️', '预警')
    html += m.warning_list.map(w => `<div class="warn warn-${w.severity || 'medium'}">
      <div>· ${w.message}</div>
      ${w.action && w.action.suggestion ? `<div class="warn-sug">建议：${String(w.action.suggestion).replace(/^建议[：:]\s*/, '')}</div>` : ''}
    </div>`).join('')
  }

  // ❓ 需要确认（图片识别后字迹不清等）
  if (Array.isArray(m.confirmation_needed) && m.confirmation_needed.length) {
    html += sec('❓', '需要你确认')
    html += `<div class="confirm-box">${m.confirmation_needed.map(c => `<div class="confirm-item">· ${c}</div>`).join('')}</div>`
  }

  // 👥 相关人
  if (hasSection(m, 'governance')) {
    const people = []
    if (m.owner) people.push('负责人：' + (m.owner.name || ''))
    if (Array.isArray(m.assignees) && m.assignees.length) people.push('参与人：' + m.assignees.map(a => a.name).join('、'))
    if (people.length) {
      html += sec('👥', '相关人')
      html += people.map(p => `<div class="mc-line">· ${p}</div>`).join('')
    }
  }

  // 📄 原文出处
  if (hasSection(m, 'source') && Array.isArray(m.sources) && m.sources.length) {
    html += `<details class="src-detail"><summary>📄 原文出处（${m.sources.length}）</summary>`
    html += m.sources.map(s => `<div class="src-quote">${s.page != null ? `<span class="page-tag">第 ${s.page} 页</span>` : ''}“${s.quote}”</div>`).join('')
    html += `</details>`
  }

  // 🔄 原要求 / 新要求 对比（补充通知场景）
  if (m.diff && (Array.isArray(m.diff.changes) && m.diff.changes.length)) {
    html += sec('🔄', '补充通知对比')
    html += `<div class="diff-row">`
    html += `<div class="diff-col diff-old"><div class="diff-head">原要求</div>`
    ;(m.diff.old_requirements || []).forEach(r => { html += `<div class="diff-item">· ${r}</div>` })
    html += `</div>`
    html += `<div class="diff-col diff-new"><div class="diff-head">新要求</div>`
    ;(m.diff.new_requirements || []).forEach(r => { html += `<div class="diff-item">· ${r}</div>` })
    html += `</div>`
    html += `</div>`
    html += `<div class="diff-changes">`
    m.diff.changes.forEach(c => {
      const tag = c.type === 'added' ? '新增' : c.type === 'removed' ? '删除' : c.type === 'changed' ? '修改' : '提示'
      html += `<div class="diff-change diff-${c.type || 'info'}"><span class="diff-tag">${tag}</span> ${c.text || c.note || ''}</div>`
    })
    html += `</div>`
    // 受影响待办 + 确认更新按钮
    if (Array.isArray(m.diff.affected_todos) && m.diff.affected_todos.length) {
      html += `<div class="affected-box"><b>受影响的待办：</b><ul>`
      m.diff.affected_todos.forEach(t => html += `<li>· ${t}</li>`)
      html += `</ul><button class="btn btn-primary btn-sm" id="confirmUpdateBtn">确认更新任务清单</button></div>`
    }
  }

  html += '</div>'
  return html || '<div class="ph">未从通知中提取到可展示内容</div>'
}
