/**
 * 【DEMO 演示数据】文档管理列表
 * 后端暂无：文档列表/搜索/筛选/分页接口（仅有单任务查询）
 * 上传与解析任务创建为真实接口（见 api/parse.ts）
 */
import type { DataSource } from '../types'

export type DocumentStatus =
  | 'pending'      // 待解析
  | 'parsing'      // 解析中
  | 'success'      // 解析成功
  | 'failed'       // 解析失败
  | 'reviewing'    // 待审核
  | 'reviewed'     // 已审核
  | 'ingested'     // 已入库

export interface DocumentItem {
  id: string
  name: string
  docType: '法律法规' | '部门规章' | '规范性文件' | '执法指南' | '标准规范'
  fileType: 'PDF' | 'Word' | '图片'
  size: number
  sha256: string
  uploadedAt: string
  status: DocumentStatus
  engine?: string
  pages?: number
}

const NAMES: Array<[string, DocumentItem['docType']]> = [
  ['中华人民共和国反垄断法（2022修正）', '法律法规'],
  ['市场监督管理行政处罚程序规定', '部门规章'],
  ['网络交易监督管理办法', '部门规章'],
  ['广告绝对化用语执法指南', '执法指南'],
  ['食品安全抽样检验管理办法', '部门规章'],
  ['市场主体登记管理条例实施细则', '部门规章'],
  ['关于平台经济领域的反垄断指南', '规范性文件'],
  ['价格违法行为行政处罚规定', '法律法规'],
  ['消费品召回管理暂行规定', '部门规章'],
  ['市场监管总局关于加强网络直播营销活动监管的指导意见', '规范性文件'],
  ['检验检测机构监督管理办法', '部门规章'],
  ['保健食品标注警示用语指南', '标准规范']
]

function fakeSha256(seed: number): string {
  const hex = '0123456789abcdef'
  let out = ''
  let x = seed * 2654435761
  for (let i = 0; i < 64; i++) {
    x = (x ^ (x << 13)) >>> 0
    x = (x ^ (x >> 17)) >>> 0
    x = (x ^ (x << 5)) >>> 0
    out += hex[x % 16]
  }
  return out
}

const STATUS_FLOW: DocumentStatus[] = [
  'pending', 'parsing', 'success', 'failed', 'reviewing', 'reviewed', 'ingested'
]

export const demoDocuments: DocumentItem[] = NAMES.map(([name, docType], i) => {
  const day = 9 - (i % 6)
  return {
    id: `doc-${1000 + i}`,
    name,
    docType,
    fileType: i % 5 === 3 ? 'Word' : i % 7 === 5 ? '图片' : 'PDF',
    size: 380_000 + ((i * 977_123) % 8_400_000),
    sha256: fakeSha256(i + 7),
    uploadedAt: `2026-11-${String(Math.max(day, 1)).padStart(2, '0')} ${String(9 + (i % 9)).padStart(2, '0')}:${String((i * 17) % 60).padStart(2, '0')}`,
    status: STATUS_FLOW[i % STATUS_FLOW.length],
    engine: ['PaddleOCR', 'PP-StructureV3', 'MinerU'][i % 3],
    pages: 4 + ((i * 13) % 96)
  }
})

export function fetchDocuments(params: {
  keyword?: string
  docType?: string
  status?: string
  dateRange?: [string, string] | null
  page?: number
  pageSize?: number
}): Promise<{ data: { list: DocumentItem[]; total: number }; source: DataSource }> {
  let list = [...demoDocuments]
  if (params.keyword) list = list.filter((d) => d.name.includes(params.keyword!))
  if (params.docType) list = list.filter((d) => d.docType === params.docType)
  if (params.status) list = list.filter((d) => d.status === params.status)
  if (params.dateRange && params.dateRange[0]) {
    const [start, end] = params.dateRange
    list = list.filter((d) => d.uploadedAt.slice(0, 10) >= start && d.uploadedAt.slice(0, 10) <= end)
  }
  const total = list.length
  const page = params.page ?? 1
  const pageSize = params.pageSize ?? 10
  list = list.slice((page - 1) * pageSize, page * pageSize)
  return Promise.resolve({ data: { list, total }, source: 'demo' })
}
