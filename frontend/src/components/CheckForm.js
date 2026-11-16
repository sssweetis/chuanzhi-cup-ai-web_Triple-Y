// 材料核对：界面仅保留材料勾选，隐藏字段使用已确认的本地默认 profile。
// @ts-nocheck -- 渐进迁移：待材料核对接口类型补齐后移除。
import { state } from '../state.js'
import { checkProfile } from '../api2.js'
import { escapeHtml, setButtonBusy } from '../util.js'
import { userErrorMessage } from '../errors.js'

export function renderCheckForm(mount) {
  const materials = Array.isArray(state.analyzeResult?.materials)
    ? state.analyzeResult.materials
        .filter((material) => material?.material_id && material?.material_name)
        .map((material) => ({ id: material.material_id, name: material.material_name }))
    : []

  if (!materials.length) {
    mount.innerHTML = `
      <div class="card check-card">
        <div class="list-title">材料核对</div>
        <div class="empty check-empty">当前通知还没有提取到材料，完成解析后会显示在这里。</div>
      </div>`
    return
  }

  mount.innerHTML = `
    <div class="card check-card">
      <div class="list-title">材料核对</div>
      <div class="sub">勾选已经准备好的材料，系统会整理成"已准备 / 缺少 / 需要确认"</div>
      <div class="field"><label>团队人数</label><input type="number" id="fPeopleCount" value="3" min="1" max="10"></div>
      <div class="field"><label>年级</label>
        <select id="fGrade">
          <option value="freshman">大一</option>
          <option value="sophomore_plus" selected>大二及以上</option>
        </select>
      </div>
      <div class="field"><label>是否已有说明文档</label>
        <select id="fHasDoc"><option value="unknown">不确定</option><option value="yes">有</option><option value="no">没有</option></select>
      </div>
      <div class="field"><label>是否已有演示视频</label>
        <select id="fHasVideo"><option value="unknown">不确定</option><option value="yes">有</option><option value="no">没有</option></select>
      </div>
      <div class="field"><label>是否需要指导老师签字</label>
        <select id="fHasTeacher"><option value="unknown">不确定</option><option value="yes">需要</option><option value="no">不需要</option></select>
      </div>
      <div class="field"><label>已备材料</label>
        ${materials.map((m) => `<label class="chk"><input type="checkbox" value="${escapeHtml(m.id)}"> <span>${escapeHtml(m.name)}</span></label>`).join('')}
      </div>
      <div class="in-foot">
        <button class="btn btn-primary" id="checkBtn">提交核对</button>
      </div>
      <div id="checkResult"></div>
    </div>`

  function renderBuckets(b) {
    const row = (cls, label, items, emoji) =>
      items && items.length
        ? `<div class="bucket ${cls}"><div class="bucket-head">${emoji} ${label}（${items.length}）</div><ul>${items.map((i) => `<li>${escapeHtml(i)}</li>`).join('')}</ul></div>`
        : `<div class="bucket ${cls}"><div class="bucket-head">${emoji} ${label}（0）</div><div class="bucket-empty">无</div></div>`
    return `<div class="buckets">
      ${row('b-ok', '已准备', b.ready, '✅')}
      ${row('b-bad', '缺少', b.missing, '❌')}
      ${row('b-warn', '需要确认', b.needConfirm, '❓')}
    </div>`
  }

  mount.querySelector('#checkBtn').onclick = async () => {
    const checked = Array.from(mount.querySelectorAll('input[type=checkbox]:checked')).map((c) => c.value)
    const profile = {
      people_count: Number(mount.querySelector('#fPeopleCount').value) || 3,
      grade: mount.querySelector('#fGrade').value,
    }
    const hasDoc = mount.querySelector('#fHasDoc').value
    const hasVideo = mount.querySelector('#fHasVideo').value
    const hasTeacherConfirm = mount.querySelector('#fHasTeacher').value
    if (hasDoc !== 'unknown') profile.has_doc = hasDoc === 'yes'
    if (hasVideo !== 'unknown') profile.has_video = hasVideo === 'yes'
    if (hasTeacherConfirm !== 'unknown') profile.has_teacher_confirm = hasTeacherConfirm === 'yes'

    const box = mount.querySelector('#checkResult')
    const btn = mount.querySelector('#checkBtn')
    setButtonBusy(btn, true, '核对中…')
    box.innerHTML =
      '<div class="loading-inline"><span class="spinner spinner-dark" aria-hidden="true"></span><span>正在核对材料…</span></div>'
    try {
      const body = { profile, checked_material_ids: checked }
      if (state.analyzeResult) body.matter = state.analyzeResult
      else {
        const text = localStorage.getItem('zhiban-input') || ''
        if (text) body.text = text
      }
      const res = await checkProfile(body)
      const ready = Array.isArray(res.ready) && res.ready.length ? res.ready : res.checked || []
      const buckets = {
        ready,
        missing: [...(res.missing_required || []), ...(res.missing_optional || [])],
        needConfirm: [...(res.need_confirm || []), ...(res.profile_issues || [])],
      }
      box.innerHTML = renderBuckets(buckets)
    } catch (err) {
      // 后端没通：本地兜底
      const ready = [],
        missing = [],
        needConfirm = []
      materials.forEach((m) => (checked.includes(m.id) ? ready : missing).push(m.name))
      box.innerHTML =
        renderBuckets({ ready, missing, needConfirm }) +
        `<div class="error-box compact">核对服务暂时不可用，以上为本地分类。${escapeHtml(userErrorMessage(err, '请稍后重试。'))}</div>`
    } finally {
      setButtonBusy(btn, false)
    }
  }
}
