/**
 * 【DEMO】文档审核中心
 * 后端现状：qa_core/indexing/ocr_review.py 只有服务层，无审核读写 HTTP 接口。
 * 页面为**只读预览**；4 个审核写操作一律禁用。
 *
 * 展示文本为版式占位内容，**不是任何法规原文、也不代表真实 OCR 结果**，
 * 避免前端编造法律条文。真实内容来自 GET /api/parse/tasks/{id}/results。
 */
import type { DataSource } from '../types'
import { demoResult } from '../dataSource'

export interface ReviewItem {
  docId: string
  fileName: string
  sha256: string
  engine: string
  parsedAt: string
  pages: number
  confidence: number
  tableCount: number
  charCount: number
  markdown: string
  jsonResult: string
  /** 按页关联：右侧结果按页码定位（接口数据须带 page 字段） */
  pagesResult: Array<{ page: number; text: string; tables: number }>
}

export const demoReviewDoc: ReviewItem = {
  docId: 'doc-1001',
  fileName: '市场监督管理行政处罚程序规定.pdf',
  sha256: '3a9f1c2e7b8d4a05e6f1c2d3b4a59687706f5e4d3c2b1a0987654321fedcba98',
  engine: 'PP-StructureV3',
  parsedAt: '2026-11-09 10:24:16',
  pages: 24,
  confidence: 0.934,
  tableCount: 6,
  charCount: 41_862,
  markdown: [
    '> 【DEMO 占位文本】以下内容仅用于展示解析结果的版式与按页关联交互，',
    '> 不是任何法规原文，也不代表真实 OCR 识别结果。',
    '> 真实内容应由后端 GET /api/parse/tasks/{id}/results 返回。',
    '',
    '# 〈文档标题占位〉',
    '',
    '## 第一章 〈章标题占位〉',
    '',
    '第一条 〔此处展示后端返回的该页解析文本〕',
    '',
    '第二条 〔此处展示后端返回的该页解析文本〕',
    '',
    '## 第二章 〈章标题占位〉',
    '',
    '第三条 〔此处展示后端返回的该页解析文本〕'
  ].join('\n'),
  jsonResult: JSON.stringify(
    {
      _demo_notice: '结构示例，非真实解析结果，不含任何法规条文',
      doc_id: 'doc-1001',
      engine: 'pp_structure_v3',
      pages: 24,
      blocks: [
        { type: 'title', text: '〈标题占位〉', page: 1, confidence: 0.98 },
        { type: 'heading', text: '〈章节占位〉', page: 1, confidence: 0.97 },
        { type: 'paragraph', text: '〈正文占位〉', page: 1, confidence: 0.95 },
        { type: 'table', rows: 8, cols: 4, page: 5, confidence: 0.89 }
      ]
    },
    null,
    2
  ),
  pagesResult: Array.from({ length: 24 }, (_, i) => ({
    page: i + 1,
    text: `〔第 ${i + 1} 页解析文本占位〕真实内容由后端 results 接口返回。`,
    tables: i === 4 || i === 6 || i === 11 ? 1 : 0
  }))
}

export function fetchReviewDoc(): Promise<{ data: ReviewItem; source: DataSource }> {
  return Promise.resolve(demoResult(demoReviewDoc))
}
