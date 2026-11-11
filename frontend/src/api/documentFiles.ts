import client from './client'

/**
 * 原始文件源适配层（v0.2.2 真实实现）
 *
 * 唯一来源：GET /api/parse/files/{file_id}/source
 *  - 后端按 owner 隔离，校验 SHA256 与字节数，不一致返回 409；支持 Range（206/416）
 *  - 响应头 X-SHA256 为后端计算的真实摘要；不得用 artifact.bin 冒充原始证据
 *  - PDF / 图片 inline、DOCX attachment；后端不提供 Word→PDF 转换
 *
 * 安全约束：
 *  - 通过认证 Axios 取 ArrayBuffer → 创建 Blob URL → 浏览器渲染/下载
 *  - 绝不把需要 Bearer Token 的接口地址直接塞进无请求头的 iframe / img
 *  - Blob URL 在切换文件或离开页面时必须 revoke
 */

export const SOURCE_FILE_API = 'GET /api/parse/files/{file_id}/source'

export type SourceKind = 'pdf' | 'image' | 'docx' | 'other'

export interface SourceFile {
  data: ArrayBuffer
  /** 后端 X-SHA256 响应头；与上传/详情的 sha256 应一致 */
  sha256: string
  contentType: string
  size: number
  kind: SourceKind
}

const EXT_KIND: Record<string, SourceKind> = {
  '.pdf': 'pdf',
  '.png': 'image',
  '.jpg': 'image',
  '.jpeg': 'image',
  '.docx': 'docx'
}

const EXT_MIME: Record<string, string> = {
  '.pdf': 'application/pdf',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

export function sourceKindOf(fileName: string): SourceKind {
  const i = fileName.lastIndexOf('.')
  return i < 0 ? 'other' : EXT_KIND[fileName.slice(i).toLowerCase()] || 'other'
}

export function sourceMimeOf(fileName: string): string {
  const i = fileName.lastIndexOf('.')
  return (i >= 0 && EXT_MIME[fileName.slice(i).toLowerCase()]) || 'application/octet-stream'
}

export function isValidFileId(fileId: string): boolean {
  return /^[0-9a-f]{32}$/.test(fileId)
}

/** 读取原始文件字节；任何失败都抛出 ApiError，由上层 AsyncPanel 呈现真实状态 */
export async function getSourceFile(fileId: string, fileName = '', signal?: AbortSignal): Promise<SourceFile> {
  if (!isValidFileId(fileId)) {
    throw new Error('无效的上传文件 ID（应为 32 位十六进制），禁止拼接推导 ID')
  }
  const res = await client.get<ArrayBuffer>(
    `/api/parse/files/${encodeURIComponent(fileId)}/source`,
    { responseType: 'arraybuffer', ...(signal ? { signal } : {}) }
  )
  const headers = res.headers as Record<string, unknown>
  const sha256 = String(headers['x-sha256'] || headers['X-SHA256'] || '')
  const contentType = String(headers['content-type'] || headers['Content-Type'] || sourceMimeOf(fileName))
  const data = res.data as ArrayBuffer
  return {
    data,
    sha256,
    contentType: contentType.split(';')[0],
    size: data.byteLength,
    kind: sourceKindOf(fileName)
  }
}

/** HEAD 预检：读取 X-SHA256 与大小，不下载正文（后端已注册 HEAD 路由） */
export async function headSourceFile(fileId: string, signal?: AbortSignal): Promise<{ sha256: string }> {
  const res = await client.head(`/api/parse/files/${encodeURIComponent(fileId)}/source`, signal ? { signal } : {})
  const headers = res.headers as Record<string, unknown>
  return { sha256: String(headers['x-sha256'] || headers['X-SHA256'] || '') }
}

export function createSourceUrl(file: SourceFile): string {
  return URL.createObjectURL(new Blob([file.data], { type: file.contentType }))
}

export function revokeSourceUrl(url: string) {
  if (url) URL.revokeObjectURL(url)
}

/** 授权下载：字节来自认证请求，download 文件名由前端按后端给出的原始文件名设置 */
export async function downloadSourceFile(fileId: string, fileName: string, signal?: AbortSignal): Promise<void> {
  const file = await getSourceFile(fileId, fileName, signal)
  const url = createSourceUrl(file)
  try {
    const a = document.createElement('a')
    a.href = url
    a.download = fileName || `${fileId}.bin`
    document.body.appendChild(a)
    a.click()
    a.remove()
  } finally {
    // 给浏览器一点时间发起下载，再撤销临时 URL
    window.setTimeout(() => revokeSourceUrl(url), 3000)
  }
}
