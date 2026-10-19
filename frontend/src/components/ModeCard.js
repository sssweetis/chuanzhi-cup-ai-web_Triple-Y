// 按后端返回的 Matter 对象 + enabled_sections 渲染（A 给的字段细则）
const MODE_LABEL = { simple: '极简', standard: '标准', complex: '完整流程' }
// 优先级配色：low 灰 / medium 蓝 / high 橙 / urgent 红
const PRIORITY_CLS = { low: 'p-low', medium: 'p-mid', high: 'p-high', urgent: 'p-urgent' }
const PRIORITY_LABEL = { low: '低', medium: '普通', high: '较急', urgent: '紧急' }
// 材料状态
const MAT_STATUS = { pending: '未准备', uploaded: '已上传', submitted: '已提交', approved: '已通过', rejected: '已驳回' }
const MAT_STATUS_CLS = { pending: 'st-pending', uploaded: 'st-mid', submitted: 'st-mid', approved: 'st-ok', rejected: 'st-bad' }
const STEP_STATUS = { not_started: '未开始', pending: '待处理', in_progress: '进行中', completed: '已完成', done: '已完成' }

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const p = n => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}月${d.getDate()}日 ${p(d.getHours())}:${p(d.getMinutes())}`
}
// 倒计时：due_at - 当前时间 → “还剩 9 天 3 小时”
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
function targetName(t) {
  if (!t) return ''
  return typeof t === 'string' ? t : (t.name || '')
}

export function renderMatter(m) {
  if (!m) return ''
  let html = ''

  // ===== summary：标题区 =====
  if (hasSection(m, 'summary')) {
    html += `<div class="mc-head">`
    html += `<span class="mode-chip">${MODE_LABEL[m.mode] || m.mode}</span>`
    if (m.complexity_score != null) html += `<span class="score-chip">复杂度 ${m.complexity_score}</span>`
    if (m.category) html += `<span class="cat-chip">${m.category}</span>`
    if (m.priority && m.priority !== 'low') html += `<span class="p-chip ${PRIORITY_CLS[m.priority] || ''}">${PRIORITY_LABEL[m.priority] || m.priority}</span>`
    html += `<h1 class="mc-title">${m.title || '未命名任务'}</h1>`
    if (m.background) html += `<div class="mc-bg">${m.background}</div>`
    const t = targetName(m.target)
    if (t) html += `<div class="mc-row">面向：${t}</div>`
    if (m.status) html += `<div class="mc-row">状态：<span class="st-badge st-mid">${STEP_STATUS[m.status] || m.status}</span></div>`
    html += `</div>`
  }

  // ===== schedule：倒计时卡片 =====
  if (hasSection(m, 'schedule') && m.deadline) {
    const due = m.deadline.due_at
    html += `<div class="ddl-card">
      <div class="ddl-label">${m.deadline.label || '截止时间'}</div>
      <div class="ddl-time">${due ? fmtTime(due) : ''}</div>
      ${due ? `<div class="ddl-count">${countdown(due)}</div>` : ''}
      ${m.deadline.start_at ? `<div class="ddl-start">开始：${fmtTime(m.deadline.start_at)}</div>` : ''}
    </div>`
    if (Array.isArray(m.reminders) && m.reminders.length) {
      const r = m.reminders[0]
      const ch = (r.channels || []).join(' / ')
      html += `<div class="mc-row">提醒：提前 ${Math.round(r.offset_minutes / 60)} 小时（${ch}）</div>`
    }
    if (m.default_location) html += `<div class="mc-row">地点：${m.default_location.name || ''}</div>`
  }

  // ===== content：要点 + 附件 =====
  if (hasSection(m, 'content')) {
    if (Array.isArray(m.key_points) && m.key_points.length) {
      html += `<div class="mc-sub">注意事项</div><ul class="mc-list">${m.key_points.map(k => `<li>${k}</li>`).join('')}</ul>`
    }
    if (Array.isArray(m.attachments) && m.attachments.length) {
      html += `<div class="mc-sub">附件</div><div class="att-row">${m.attachments.map(a => {
        const url = a.attachment_url
        return url
          ? `<a class="btn btn-ghost btn-sm" href="${url}" target="_blank" rel="noopener">⬇ ${a.attachment_name}</a>`
          : `<span class="btn btn-ghost btn-sm" style="opacity:.6">📎 ${a.attachment_name}</span>`
      }).join('')}</div>`
    }
  }

  // ===== steps：流程步骤 =====
  if (hasSection(m, 'steps') && Array.isArray(m.step_list) && m.step_list.length) {
    const matMap = {}
    ;(m.materials || []).forEach(x => { matMap[x.material_id] = x.material_name })
    html += `<div class="mc-sub">流程（${m.step_list.length} 步）</div><ol class="mc-steps">`
    m.step_list.forEach((s, i) => {
      let dueAt = s.due_at
      if (!dueAt && s.due_at_inherited_from === 'overall' && m.deadline) dueAt = m.deadline.due_at
      const mats = Array.isArray(s.materials) && s.materials.length
        ? `<div class="mc-row">材料：${s.materials.map(id => matMap[id] || id).join('、')}</div>` : ''
      const dep = Array.isArray(s.dependencies) && s.dependencies.length
        ? `<div class="dep">需先完成：${s.dependencies.map(d => {
            const dstep = m.step_list.find(x => x.step_id === d.step_id)
            return dstep ? dstep.title : d.step_id
          }).join('、')}</div>` : ''
      const owner = s.owner ? `<div class="mc-row">负责人：${s.owner.name}</div>` : ''
      const review = s.review && s.review.required ? `<div class="dep">需审核：${s.review.reviewer ? s.review.reviewer.name : ''}</div>` : ''
      const subs = Array.isArray(s.sub_step_list) && s.sub_step_list.length
        ? `<ul class="substeps">${s.sub_step_list.map(sub => `<li>${sub.title} <span class="st-badge st-pending">${STEP_STATUS[sub.status] || sub.status || ''}</span></li>`).join('')}</ul>` : ''
      const done = s.status === 'completed' || s.status === 'done'
      html += `<li>
        <span class="step-dot">${i + 1}</span>
        <span class="step-title">${s.title}</span>
        <span class="st-badge ${done ? 'st-ok' : 'st-pending'}">${STEP_STATUS[s.status] || s.status || ''}</span>
        ${dueAt ? `<span class="step-due">${fmtTime(dueAt)}</span>` : ''}
        ${owner}${review}${mats}${dep}${subs}
      </li>`
    })
    html += `</ol>`
  }

  // ===== materials：材料清单 =====
  if (hasSection(m, 'materials') && Array.isArray(m.materials) && m.materials.length) {
    const attMap = {}
    ;(m.attachments || []).forEach(a => { attMap[a.attachment_id] = a })
    html += `<div class="mc-sub">材料清单（${m.materials.length} 项）</div><ul class="mc-list">`
    m.materials.forEach(mat => {
      const att = attMap[mat.template_attachment_id]
      const url = att && att.attachment_url
      const typeTag = mat.material_type === 'optional' ? '<span class="type-tag opt">可选</span>' : '<span class="type-tag req">必填</span>'
      const tpl = url ? ` <a class="tpl-link" href="${url}" target="_blank" rel="noopener">下载模板</a>` : ''
      html += `<li><label class="chk"><input type="checkbox" data-mat="${mat.material_id}">
        <b>${mat.material_name}</b> ${typeTag}
        <span class="st-badge ${MAT_STATUS_CLS[mat.status] || 'st-pending'}">${MAT_STATUS[mat.status] || mat.status || ''}</span>
        ${tpl}
      </label></li>`
    })
    html += `</ul>`
  }

  // ===== warnings：分级预警 =====
  if (hasSection(m, 'warnings') && Array.isArray(m.warning_list) && m.warning_list.length) {
    html += m.warning_list.map(w => `<div class="warn warn-${w.severity || 'medium'}">
      <div>${w.message}</div>
      ${w.action && w.action.suggestion ? `<div class="warn-sug">建议：${w.action.suggestion}</div>` : ''}
    </div>`).join('')
  }

  // ===== governance：协作 =====
  if (hasSection(m, 'governance')) {
    const people = []
    if (m.owner) people.push('负责人：' + (m.owner.name || ''))
    if (Array.isArray(m.assignees) && m.assignees.length) people.push('参与人：' + m.assignees.map(a => a.name).join('、'))
    if (people.length) html += `<div class="mc-sub">协作</div>${people.map(p => `<div class="mc-row">${p}</div>`).join('')}`
  }

  // ===== source：原文出处 =====
  if (hasSection(m, 'source') && Array.isArray(m.sources) && m.sources.length) {
    html += `<details class="src-detail"><summary>原文出处（${m.sources.length}）</summary>`
    html += m.sources.map(s => `<div class="src-quote">${s.page != null ? `<span class="page-tag">第 ${s.page} 页</span>` : ''}“${s.quote}”</div>`).join('')
    html += `</details>`
  }

  return html || '<div class="ph">未从通知中提取到可展示内容</div>'
}
