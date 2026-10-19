import { state, setState } from '../state.js'

export function openUserModal() {
  let mask = document.getElementById('userMask')
  if (!mask) {
    mask = document.createElement('div')
    mask.id = 'userMask'
    mask.className = 'mask'
    mask.innerHTML = `
      <div class="modal">
        <h3>个人中心</h3>
        <div class="field"><label>登录账号</label><input id="fAccount"></div>
        <div class="field"><label>登录密码（演示版本地保存）</label><input id="fPassword" type="password"></div>
        <div class="field"><label>昵称</label><input id="fNick"></div>
        <div class="modal-foot">
          <button class="btn btn-ghost" id="cancelModal">取消</button>
          <button class="btn btn-primary" id="saveModal">保存</button>
        </div>
      </div>`
    document.body.appendChild(mask)
  }
  mask.classList.add('show')
  mask.querySelector('#fAccount').value = state.profile.account
  mask.querySelector('#fPassword').value = state.profile.password
  mask.querySelector('#fNick').value = state.profile.nick
  mask.querySelector('#cancelModal').onclick = () => mask.classList.remove('show')
  mask.querySelector('#saveModal').onclick = () => {
    setState({ profile: {
      ...state.profile,
      account: mask.querySelector('#fAccount').value.trim() || 'triple',
      password: mask.querySelector('#fPassword').value,
      nick: mask.querySelector('#fNick').value.trim() || 'Triple'
    }})
    mask.classList.remove('show')
  }
}
