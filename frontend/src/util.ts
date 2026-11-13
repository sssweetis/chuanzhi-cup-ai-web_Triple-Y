export type ToastType = 'info' | 'success' | 'error'

export function escapeHtml(value: unknown): string {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

let toastTimer = 0

export function showToast(message: string, type: ToastType = 'info'): void {
  let toast = document.getElementById('appToast')
  if (!toast) {
    toast = document.createElement('div')
    toast.id = 'appToast'
    toast.className = 'toast'
    toast.setAttribute('role', 'status')
    toast.setAttribute('aria-live', 'polite')
    document.body.appendChild(toast)
  }
  clearTimeout(toastTimer)
  toast.className = `toast toast-${type}`
  toast.textContent = message
  requestAnimationFrame(() => toast?.classList.add('show'))
  toastTimer = window.setTimeout(() => toast?.classList.remove('show'), 2600)
}

export function setButtonBusy(button: HTMLButtonElement | null, busy: boolean, label = '处理中…'): void {
  if (!button) return
  if (busy) {
    if (!button.dataset.idleHtml) button.dataset.idleHtml = button.innerHTML
    button.disabled = true
    button.classList.add('is-loading')
    button.setAttribute('aria-busy', 'true')
    button.innerHTML = `<span class="spinner" aria-hidden="true"></span>${escapeHtml(label)}`
    return
  }
  button.disabled = false
  button.classList.remove('is-loading')
  button.removeAttribute('aria-busy')
  if (button.dataset.idleHtml) {
    button.innerHTML = button.dataset.idleHtml
    delete button.dataset.idleHtml
  }
}

const modalReturnFocus = new WeakMap<HTMLElement, HTMLElement>()
let modalAccessibilityReady = false

function focusableElements(root: HTMLElement): HTMLElement[] {
  return Array.from(
    root.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => !element.hasAttribute('hidden') && element.offsetParent !== null)
}

export function openModal(mask: HTMLElement, options: { initialFocus?: HTMLElement | string | null } = {}): void {
  if (!mask.classList.contains('show') && document.activeElement instanceof HTMLElement) {
    modalReturnFocus.set(mask, document.activeElement)
  }
  const modal = mask.querySelector<HTMLElement>('.modal')
  modal?.setAttribute('role', 'dialog')
  modal?.setAttribute('aria-modal', 'true')
  mask.classList.add('show')
  const target =
    typeof options.initialFocus === 'string'
      ? mask.querySelector<HTMLElement>(options.initialFocus)
      : options.initialFocus
  requestAnimationFrame(() => {
    const fallback = modal ? focusableElements(modal)[0] : null
    ;(target || fallback || modal)?.focus()
  })
}

export function closeModal(mask: HTMLElement | null): void {
  if (!mask) return
  mask.classList.remove('show')
  const target = modalReturnFocus.get(mask)
  modalReturnFocus.delete(mask)
  if (target && document.contains(target)) requestAnimationFrame(() => target.focus())
}

export function closeTopModal(): void {
  const masks = document.querySelectorAll<HTMLElement>('.mask.show')
  if (masks.length) closeModal(masks[masks.length - 1])
}

export function initModalA11y(): void {
  if (modalAccessibilityReady) return
  modalAccessibilityReady = true
  document.addEventListener('click', (event) => {
    const target = event.target as HTMLElement
    if (target.classList.contains('mask')) closeModal(target)
  })
  document.addEventListener('keydown', (event) => {
    const activeMask = document.querySelector<HTMLElement>('.mask.show')
    if (!activeMask) return
    if (event.key === 'Escape') {
      event.preventDefault()
      closeModal(activeMask)
      return
    }
    if (event.key !== 'Tab') return
    const modal = activeMask.querySelector<HTMLElement>('.modal')
    if (!modal) return
    const focusable = focusableElements(modal)
    if (!focusable.length) {
      event.preventDefault()
      modal.focus()
      return
    }
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  })
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    const input = document.createElement('textarea')
    input.value = text
    input.setAttribute('readonly', '')
    input.style.position = 'fixed'
    input.style.opacity = '0'
    document.body.appendChild(input)
    input.select()
    const copied = document.execCommand('copy')
    input.remove()
    return copied
  }
}

export function wait(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}
