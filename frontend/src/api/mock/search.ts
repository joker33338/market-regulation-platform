/**
 * 法规知识检索
 *
 * 后端现状：qa_core/retrieval/（BGE-M3 + RAG）只有服务层，没有检索 HTTP 接口。
 * 因此本层**不返回任何法条原文**：伪造法律原文或生成式结论属明确禁止行为。
 * 无可靠检索依据时，页面必须显示「未检索到相关依据（检索接口未接入）」。
 *
 * 接口交付后：把 apiCapabilities.knowledgeSearch 置 true，
 * 在 searchRegulations() 内改为 POST /api/knowledge/search，
 * 并按 SearchHit 的字段契约映射后端响应（含来源文件与原始分数）。
 */
import type { DataSource } from '../types'
import { apiCapabilities } from '../dataSource'

/** 真实检索接口就绪后，每条命中必须可追溯到来源文件与原始分数 */
export interface SearchHit {
  id: string
  regulation: string
  article: string
  content: string
  rawScore: number
  kbVersion: string
  authority: string
  effectiveDate: string
  expiryDate?: string | null
  sourceFileId: string
  sourceFileName: string
}

export interface SearchOutcome {
  hits: SearchHit[]
  source: DataSource
  elapsedMs: number
  apiAvailable: boolean
  /** 无结果时必须展示的原因，不得留空让前端自行编造 */
  reason: string
}

export function searchRegulations(_query: string): Promise<SearchOutcome> {
  void _query
  return Promise.resolve({
    hits: [],
    source: 'demo',
    elapsedMs: 0,
    apiAvailable: apiCapabilities.knowledgeSearch,
    reason: apiCapabilities.knowledgeSearch
      ? '本次检索未命中符合条件的法律依据'
      : '法规检索 HTTP 接口未接入，无法提供真实法律依据；未检索到相关依据。'
  })
}

/** 结果字段契约说明（供页面在「接口未接入」时展示，不含任何法条内容） */
export const RESULT_FIELDS = [
  '法规名称 / 条款编号 / 条款原文',
  '发布机关 / 生效日期 / 失效日期',
  '知识库版本 kb_version',
  '来源文件（source_file_id，可追溯）',
  '检索原始分数（raw_score，非前端换算）'
] as const
