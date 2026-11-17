import type { Router } from 'vue-router'

interface SessionNavigation {
  hasToken: () => boolean
  clearSession: () => void
  subscribe: (listener: (status: number) => void) => () => void
}

/** 只返回已注册的站内页面，拒绝外链、反斜线、控制字符及登录循环。 */
export function safeLoginReturn(router: Pick<Router, 'resolve'>, value: unknown): string {
  if (typeof value !== 'string' || value.length > 4096 || !value.startsWith('/') ||
      value.startsWith('//') || /[\\\u0000-\u001f\u007f]/.test(value)) return '/dashboard'
  try {
    const resolved = router.resolve(value)
    return resolved.matched.length && resolved.name !== 'Login' ? resolved.fullPath : '/dashboard'
  } catch {
    return '/dashboard'
  }
}

/** 前端只负责登录入口，真实身份、角色和数据范围仍由后端逐请求校验。 */
export function installLoginNavigation(router: Router, session: SessionNavigation): () => void {
  const removeGuard = router.beforeEach(to => {
    if (to.name === 'Login' || session.hasToken()) return true
    return { name: 'Login', query: { redirect: safeLoginReturn(router, to.fullPath) }, replace: true }
  })
  const unsubscribe = session.subscribe(status => {
    // 403表示动作权限不足，503表示暂不可用，都不能冒充凭证失效而强制退出。
    if (status !== 401) return
    const current = router.currentRoute.value
    session.clearSession()
    if (current.name !== 'Login') {
      void router.replace({ name: 'Login', query: {
        redirect: safeLoginReturn(router, current.fullPath), reason: 'expired'
      } }).catch(() => { /* 新导航取消旧导航时，后续导航仍会经过登录守卫。 */ })
    }
  })
  return () => { removeGuard(); unsubscribe() }
}
