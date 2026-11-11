/**
 * 与后端 qa_core/document_parsing/mineru_api.py 对齐的类型定义。
 * 事实来源：路由源码 + 后端自带参考客户端 qa_core/document_parsing/parsing_upload.html
 * 注意：后端 create_app() 设置 openapi_url=None，/openapi.json 不可用，无法以 OpenAPI 为准。
 */

/** 任务内单文件状态（对应 mineru_api.public 的 files 项） */
export interface ParseFileItem {
  file_id: string
  file_name: string
  sha256: string
  database_parse_id?: string | null
  /** 引擎选择由后端返回，前端不得自行判断 */
  selected_engine?: 'paddle' | 'ppstructure' | 'mineru' | string | null
  requires_review?: boolean
  fallback_reason?: string | null
  status: string
  error?: { code?: string; message?: string } | string | null
}

/** 解析任务（对应 mineru_api.public） */
export interface ParseTask {
  task_id: string
  status: string
  mode: string
  cancel_requested: boolean
  cancel_scope?: string | null
  provider: string
  created_at: string
  completed_at?: string | null
  error?: string | null
  files: ParseFileItem[]
}

/** POST /api/parse/files 真实响应：201 { file_id, sha256, bytes } */
export interface UploadResponse {
  file_id: string
  sha256: string
  bytes: number
}

/** GET /api/parse/info 真实响应（后端不返回 version / environment） */
export interface ParseServiceInfo {
  mode: string
  provider: string
  enabled: boolean
  database_enabled: boolean
  dual_engine_enabled: boolean
}

/** POST /api/parse/tasks 请求体白名单字段（多传字段会被后端拒绝） */
export interface CreateTaskPayload {
  file_ids: string[]
  strategy?: string
  allow_cloud_fallback?: boolean
  sensitive?: boolean
}

/** GET /api/parse/tasks/{id}/results 响应 */
export interface TaskResults {
  task_id: string
  status: string
  results: Array<{ file_id: string; document: Record<string, unknown> }>
}

/** 后端任务终止态（参考 parsing_upload.html 的轮询终止条件） */
export const TERMINAL_TASK_STATUS = [
  'completed',
  'partial',
  'failed',
  'canceled',
  'timed_out'
] as const

export function isTerminalStatus(status: string): boolean {
  return (TERMINAL_TASK_STATUS as readonly string[]).includes(status)
}

/** 系统组件五态：仅真实探测成功才允许 ONLINE */
export type ComponentState = 'ONLINE' | 'OFFLINE' | 'NOT_CONFIGURED' | 'UNKNOWN' | 'ERROR'

/** 入库批次四态 */
export type BatchState = '已完成' | '执行中' | '失败' | '阻塞'

/** 数据源标记：real=后端真实接口，demo=演示数据（页面必须显著标 DEMO） */
export type DataSource = 'real' | 'demo'
