// 10/18 用户情况填写：字段已和 C 对齐
// POST /api/check 收 { notification_id, profile: {team_size, has_doc, has_video, has_teacher_confirm},
//                     checked_material_ids: string[] }
import { checkProfile } from '../api.js'

const MATERIALS = [
  { id: 'm1', name: '作品演示视频（≤3 分钟）' },
  { id: 'm2', name: '项目说明文档（PPT）' },
  { id: 'm3', name: '成绩单复印件' },
  { id: 'm4', name: '报名表' }
]

export function renderCheckForm(mount, notificationId = 'demo-notice') {
  mount.innerHTML = `
    <div class="card">
      <div class="list-title">我们队的情况（10/18）</div>
      <div class="sub">勾选已具备的材料，后端据此算出"已准备 / 缺少 / 需要确认"</div>
      <div class="field"><label>团队人数</label><input type="number" id="fTeamSize" value="3" min="1" max="10"></div>
      <div class="field"><label>是否已有说明文档</label>
        <select id="fHasDoc"><option value="yes">有</option><option value="no">没有</option><option value="unknown">不确定</option></select>
      </div>
      <div class="field"><label>是否已有演示视频</label>
        <select id="fHasVideo"><option value="no">没有</option><option value="yes">有</option><option value="unknown">不确定</option></select>
      </div>
      <div class="field"><label>是否需要指导老师签字</label>
        <select id="fHasTeacher"><option value="unknown">不确定</option><option value="yes">需要</option><option value="no">不需要</option></select>
      </div>
      <div class="field"><label>已备材料</label>
        ${MATERIALS.map(m => `<label class="chk"><input type="checkbox" value="${m.id}"> ${m.name}</label>`).join('')}
      </div>
      <div class="in-foot">
        <button class="btn btn-primary" id="checkBtn">提交核对</button>
      </div>
      <div id="checkResult"></div>
    </div>`

  mount.querySelector('#checkBtn').onclick = async () => {
    const checked = Array.from(mount.querySelectorAll('input[type=checkbox]:checked')).map(c => c.value)
    const payload = {
      notification_id: notificationId,
      profile: {
        team_size: Number(mount.querySelector('#fTeamSize').value),
        has_doc: mount.querySelector('#fHasDoc').value === 'yes',
        has_video: mount.querySelector('#fHasVideo').value === 'yes',
        has_teacher_confirm: mount.querySelector('#fHasTeacher').value === 'unknown' ? null : mount.querySelector('#fHasTeacher').value === 'yes'
      },
      checked_material_ids: checked
    }
    const box = mount.querySelector('#checkResult')
    box.textContent = '核对中…'
    try {
      const res = await checkProfile(payload)
      box.innerHTML = `<pre class="api-raw">${JSON.stringify(res, null, 2)}</pre>`
    } catch (err) {
      box.innerHTML = `<div class="error-box">${err.message}</div>`
    }
  }
}
