/**
 * 注释性文字统一折叠：默认只显示一个「说明 ▾」入口，点击展开原文，再点收起。
 *
 * 设计取舍：
 * - 用 document 级事件委托，不修改任何页面模板，Vue 重渲染 / 路由切换后依然生效；
 * - 折叠样式见 styles/index.css，同样不依赖模板改动；
 * - 错误提示（el-alert--error）与含按钮、链接、输入框的说明块不参与折叠，
 *   避免把「重试」「刷新」等真实操作入口一起藏掉；
 * - 展开状态只存在于当前 DOM，不写 localStorage，刷新后恢复默认收起。
 */

const TEXT_SELECTOR = '.mr-disabled-hint, .hint-text, .action-hint, .card-sub, .source-hint, .page-desc, .dp-note'
const INTERACTIVE_SELECTOR = 'button, a, .el-button, input, select, textarea, [role="button"]'

function hasInteractive(el: Element): boolean {
  return !!el.querySelector(INTERACTIVE_SELECTOR)
}

function toggleNote(el: Element): void {
  el.classList.toggle('is-note-open')
}

export function setupNoteToggle(): void {
  document.addEventListener('click', (event) => {
    const target = event.target
    if (!(target instanceof Element)) return
    // 点到真实控件时交还给控件本身，不触发折叠
    if (target.closest(INTERACTIVE_SELECTOR)) return

    const textBlock = target.closest(TEXT_SELECTOR)
    if (textBlock && !hasInteractive(textBlock)) {
      toggleNote(textBlock)
      return
    }

    const alert = target.closest('.el-alert:not(.el-alert--error)')
    if (!alert) return
    if (!alert.querySelector('.el-alert__description') || hasInteractive(alert)) return
    toggleNote(alert)
  })
}
