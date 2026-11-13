/**
 * 认证状态广播 —— 无依赖的极小事件层，避免请求层与身份层互相 import 形成循环。
 * 只广播 HTTP 状态码，绝不携带凭证、响应正文或身份原文。
 */
type AuthListener = (status: number) => void

const listeners = new Set<AuthListener>()

export function onAuthStateChange(listener: AuthListener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function emitAuthStateChange(status: number): void {
  for (const listener of listeners) {
    try {
      listener(status)
    } catch {
      /* 单个订阅者异常不影响统一请求层 */
    }
  }
}
