/** 折叠说明支持键盘操作；错误和包含真实操作的块保持展开。 */
const TEXT = '.mr-disabled-hint, .hint-text, .action-hint, .card-sub, .source-hint, .dp-note'
const CONTROLS = 'button, a, input, select, textarea, .el-button, [role="button"]'
export function setupNoteToggle(): void {
  const root = document.getElementById('app')
  if (!root) return
  function decorate() {
    const blocks = [...root!.querySelectorAll(TEXT), ...root!.querySelectorAll('.el-alert:not(.el-alert--error):has(.el-alert__description)')]
    for (const el of blocks) {
      if (el.querySelector(CONTROLS) || el.closest('.el-alert--error')) continue
      el.setAttribute('data-mr-note', '')
      el.setAttribute('role', 'button')
      el.setAttribute('tabindex', '0')
      el.setAttribute('aria-expanded', String(el.classList.contains('is-note-open')))
      el.setAttribute('aria-label', '展开或收起说明')
    }
  }
  function toggle(el: Element) { el.classList.toggle('is-note-open'); el.setAttribute('aria-expanded', String(el.classList.contains('is-note-open'))) }
  root.addEventListener('click', event => {
    const target = event.target
    if (!(target instanceof Element)) return
    const note = target.closest('[data-mr-note]')
    if (!note || note.querySelector(CONTROLS)) return
    const control = target.closest(CONTROLS)
    if (control && control !== note) return
    toggle(note)
  })
  root.addEventListener('keydown', event => {
    if ((event.key === 'Enter' || event.key === ' ') && event.target instanceof Element && event.target.matches('[data-mr-note]')) { event.preventDefault(); toggle(event.target) }
  })
  new MutationObserver(decorate).observe(root, { childList: true, subtree: true })
  decorate()
}
