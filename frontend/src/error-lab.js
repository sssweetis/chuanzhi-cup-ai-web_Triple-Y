// @ts-nocheck -- 调试页通过 URL 参数选择场景，运行时已校验场景白名单。
import './error-lab.css'
import { AppError, ERROR_SCENARIOS, renderErrorState } from './errors.js'

const scenarioCodes = Object.keys(ERROR_SCENARIOS)
const query = new URLSearchParams(location.search)
const requested = query.get('scenario')
const activeCode = scenarioCodes.includes(requested) ? requested : scenarioCodes[0]

const nav = document.getElementById('errorNav')
nav.innerHTML = scenarioCodes
  .map(
    (code, index) => `
  <a href="?scenario=${code}" class="${code === activeCode ? 'is-active' : ''}">
    <span>${String(index + 1).padStart(2, '0')}</span>${ERROR_SCENARIOS[code].title}
  </a>
`,
  )
  .join('')

const canvas = document.getElementById('errorCanvas')
const error = new AppError({ code: activeCode, requestId: `TY-DEMO-${activeCode.toUpperCase()}` })
renderErrorState(canvas, error, {
  onContinue: () => {},
  onRetry: () => {},
  onEdit: () => {},
  onReupload: () => {},
  onHelp: () => {},
})
