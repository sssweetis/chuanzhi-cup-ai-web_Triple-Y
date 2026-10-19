// 按后端返回的 Matter 对象 + enabled_sections 渲染
// simple: summary/schedule/source ｜ standard: +content/steps/materials ｜ complex: +warnings/governance
const MODE_LABEL = { simple: '极简', standard: '标准', complex: '完整流程' }
const PRIORITY_LABEL = { urgent: '紧急', high: '较急', medium: '普通' }
const PRIORITY_CLS = { urgent: 'over', high: 'mid', medium: '' }

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const p = n => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}月${d.getDate()}日 ${p(d.getHours())}:${p(d.getMinutes())}`
}

function hasSection(matter, key) {
  return Array.isArray(matter.enabled_sections) && matter.enabled_sections.includes(key)
}

export function renderMatter(m) {
  if (!m) return ''
  let html = ''

  // summary：标题 + 模式 + 优先级
  if (hasSection(m, 'summary')) {
    html += `<div class="mode-chip">${MODE_LABEL[m.mode] || m.mode}</div>`
    if (m.priority && m.priority !== 'medium') {
      html += `<span class="left-tag ${PRIORITY_CLS[m.priority] || ''}" style="margin-left:6px">${PRIORITY_LABEL[m.priority] || m.priority}</span>`
    }
    html += `<div class="mode-title">${m.title || '未命名任务'}</div>`
    if (m.target) html += `<div class="mode-row">面向：${m.target}</div>`
  }

  // schedule：截止时间 + 提醒
  if (hasSection(m, 'schedule') && m.deadline) {
    const ddl = m.deadline.due_at ? `截止：${fmtTime(m.deadline.due_at)}` : ''
    const range = m.deadline.start_at ? `（${fmtTime(m.deadline.start_at)} 起）` : ''
    html += `<div class="mode-row">${ddl}${range}</div>`
    if (Array.isArray(m.reminders) && m.reminders.length) {
      html += `<div class="mode-sub">提醒：提前 ${Math.round(m.reminders[0].offset_minutes / 60)} 小时，App 内通知</div>`
    }
  }

  // content：要点
  if (hasSection(m, 'content') && Array.isArray(m.key_points) && m.key_points.length) {
    html += `<div class="mode-sub">注意事项</div><ul class="mode-list">${m.key_points.map(k => `<li>${k}</li>`).join('')}</ul>`
  }

  // materials：材料清单（勾选态）
  if (hasSection(m, 'materials') && Array.isArray(m.materials) && m.materials.length) {
    html += `<div class="mode-sub">材料清单（${m.materials.length} 项）</div>`
    html += `<ul class="mode-list">${m.materials.map(mat => `
      <li><label class="chk"><input type="checkbox" data-mat="${mat.material_id}"> ${mat.material_name}
        <span class="mat-src">${mat.source_ref && mat.source_ref.quote ? '（原文：' + mat.source_ref.quote + '）' : ''}</span>
      </label></li>`).join('')}</ul>`
  }

  // steps：流程步骤 + 依赖 + 子步骤
  if (hasSection(m, 'steps') && Array.isArray(m.step_list) && m.step_list.length) {
    html += `<div class="mode-sub">流程（${m.step_list.length} 步）</div><ol class="mode-steps">`
    m.step_list.forEach((s, i) => {
      const dep = Array.isArray(s.dependencies) && s.dependencies.length
        ? `<div class="dep">需先完成：${s.dependencies.map(d => {
            const dstep = m.step_list.find(x => x.step_id === d.step_id)
            return dstep ? dstep.title : d.step_id
          }).join('、')}</div>` : ''
      const owner = s.owner ? `<div class="mode-row">负责人：${s.owner.name}</div>` : ''
      const review = s.review && s.review.required ? `<div class="dep">需审核：${s.review.reviewer ? s.review.reviewer.name : ''}</div>` : ''
      const subs = Array.isArray(s.sub_step_list) && s.sub_step_list.length
        ? `<ul class="substeps">${s.sub_step_list.map(sub => `<li>↳ ${sub.title}</li>`).join('')}</ul>` : ''
      html += `<li><b>${i + 1}.</b> <span class="step-title">${s.title}</span>
        ${s.due_at ? `<span class="step-due">${fmtTime(s.due_at)}</span>` : ''}
        ${owner}${review}${dep}${subs}</li>`
    })
    html += `</ol>`
  }

  // warnings：系统预警
  if (hasSection(m, 'warnings') && Array.isArray(m.warning_list) && m.warning_list.length) {
    html += `<div class="mode-warn">${m.warning_list.map(w => w.message).join('；')}</div>`
  }

  // governance：负责人 / 审核（complex）
  if (hasSection(m, 'governance')) {
    const people = []
    if (m.owner) people.push('负责人：' + (m.owner.name || ''))
    if (Array.isArray(m.assignees) && m.assignees.length) people.push('参与人：' + m.assignees.map(a => a.name).join('、'))
    if (people.length) html += `<div class="mode-sub">协作</div>${people.map(p => `<div class="mode-row">${p}</div>`).join('')}`
  }

  // source：原文溯源
  if (hasSection(m, 'source') && Array.isArray(m.sources) && m.sources.length) {
    html += `<div class="mode-sub">原文出处</div>`
    html += m.sources.map(s => `<div class="src-quote">“${s.quote}”</div>`).join('')
  }

  return html || '<div class="ph">未从通知中提取到可展示内容</div>'
}
