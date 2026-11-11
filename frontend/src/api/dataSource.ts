import type { DataSource } from './types'

/**
 * 后端能力开关 —— 全站唯一事实来源
 *
 * true  = 已有真实 HTTP 接口（qa_core/document_parsing/mineru_api.py 中已实现）
 * false = 后端尚无接口，页面必须显示 DEMO / 禁用写操作，不得伪装成真实业务结果
 *
 * 接口交付流程：后端实现 → QA 验证 → 把对应项改为 true → 在对应适配层补实现。
 * 页面只读取本表，不各自硬编码「是否已接入」，避免状态不一致。
 *
 * 2026-11-11 复核：后端 MVP 有限范围 QA 已 PASS，但四个最新提交的 HTTP 路由仍只有
 * 下列 9 个 API，未新增任何接口（详见 docs/frontend-api-mapping.md）。
 * QA PASS ≠ 接口交付，故本表 false 项一个都不能改为 true。
 */
export const apiCapabilities = {
  // —— 已实现（真实接口，2026-11-11 复核 f4a0af8 / 3129479 / 843c64d / 5dd44b9，路由一致）——
  parseInfo: true,
  uploadFile: true,
  createParseTask: true,
  getParseTaskById: true,
  taskErrors: true,
  taskResume: true,
  taskCancel: true,
  taskResults: true,
  artifact: true,
  // —— 未实现（需后端提供，见 docs/backend-api-requirements.md）——
  sourceFile: false, // P0-1 原始文件读取（PDF/Word 真实预览的硬前提）
  documentList: false, // P0-2 文档列表
  reviewRead: false,
  reviewWrite: false, // P0-3 审核写入
  parseTaskList: false,
  parseTaskLogs: false,
  engineStatus: false,
  dashboardStats: false,
  ingestion: false,
  knowledgeSearch: false,
  systemHealth: false
} as const

export type CapabilityKey = keyof typeof apiCapabilities

export interface DataResult<T> {
  data: T
  source: DataSource
  /** DEMO 数据必须携带的说明文案 */
  note?: string
}

export const DEMO_NOTE = '后端暂无真实接口，当前为演示数据（DEMO），不代表生产运行状态'

export function demoResult<T>(data: T, note: string = DEMO_NOTE): DataResult<T> {
  return { data, source: 'demo', note }
}

export function realResult<T>(data: T): DataResult<T> {
  return { data, source: 'real' }
}

/** 页面判断「某能力是否还停留在 DEMO」 */
export function isDemo(key: CapabilityKey): boolean {
  return !apiCapabilities[key]
}

/** 写操作按钮的统一禁用说明 */
export function unimplementedHint(api: string): string {
  return `接口未接入（需后端提供 ${api}），当前不可执行`
}
