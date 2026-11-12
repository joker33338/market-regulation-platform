/**
 * 【DEMO】知识库入库管理
 * 后端现状：qa_core/indexing/（清洗 / 法条结构化 / 切分 / 向量化）与
 * qa_core/governance/kb_versions.py 只有服务层与 CLI（scripts/ingest_legal_documents.py），
 * 无 HTTP 接口。本文件仅用于界面演示，页面必须标 DEMO 且**禁止任何写入动作**。
 */
import type { BatchState, DataSource } from '../types'
import { demoResult } from '../dataSource'

export interface PipelineStage {
  key: string
  name: string
  total: number
  success: number
  failed: number
  running?: string
  avgSeconds: number
  lastError?: string
}

export interface RegulationRecord {
  id: string
  name: string
  authority: string
  docNumber: string
  publishDate: string
  effectiveDate: string
  expiryDate?: string | null
  articleCount: number
  kbVersion: string
  status: '已入库' | '入库中' | '入库失败' | '待入库' | '阻塞'
  batchId: string
}

export interface IngestionBatch {
  batchId: string
  startedAt: string
  documentCount: number
  /** 四态：已完成 / 执行中 / 失败 / 阻塞 */
  status: BatchState
  successCount: number
  failedCount: number
  operator: string
  blockedReason?: string
}

/** 入库前检查：blocking=true 且 passed=false 时整批必须阻断 */
export interface PrecheckItem {
  key: string
  name: string
  passed: boolean
  detail: string
  blocking: boolean
}

export interface VersionCheck {
  consistent: boolean
  expectedVersion: string
  actualVersion: string
  blockedBatchIds: string[]
  checkedAt: string
}

export const demoPipeline: PipelineStage[] = [
  { key: 'parsed', name: '文档解析完成', total: 58, success: 55, failed: 3, avgSeconds: 42.6 },
  { key: 'clean', name: '法律文本清洗', total: 55, success: 54, failed: 1, avgSeconds: 3.2 },
  { key: 'structure', name: '法规结构识别', total: 54, success: 52, failed: 2, avgSeconds: 6.8 },
  { key: 'chunk', name: '法条切分', total: 52, success: 52, failed: 0, avgSeconds: 4.1 },
  { key: 'embed', name: 'BGE-M3 向量化', total: 52, success: 50, failed: 2, running: '网络交易监督管理办法 第32-41条', avgSeconds: 18.4 },
  { key: 'write', name: 'PostgreSQL 写入', total: 50, success: 50, failed: 0, avgSeconds: 2.7 },
  { key: 'verify', name: '入库结果检查', total: 50, success: 49, failed: 1, avgSeconds: 1.5, lastError: 'kb_version 校验和不一致（1 批次）' }
]

export const demoRegulations: RegulationRecord[] = [
  {
    id: 'reg-001', name: '市场监督管理行政处罚程序规定', authority: '国家市场监督管理总局',
    docNumber: '总局令第42号', publishDate: '2021-07-15', effectiveDate: '2021-09-01', expiryDate: null,
    articleCount: 86, kbVersion: 'v2026.11', status: '已入库', batchId: 'B20261109-01'
  },
  {
    id: 'reg-002', name: '网络交易监督管理办法', authority: '国家市场监督管理总局',
    docNumber: '总局令第37号', publishDate: '2021-03-15', effectiveDate: '2021-05-01', expiryDate: null,
    articleCount: 64, kbVersion: 'v2026.11', status: '已入库', batchId: 'B20261109-01'
  },
  {
    id: 'reg-003', name: '中华人民共和国反垄断法（2022修正）', authority: '全国人民代表大会常务委员会',
    docNumber: '主席令第112号', publishDate: '2022-06-24', effectiveDate: '2022-08-01', expiryDate: null,
    articleCount: 70, kbVersion: 'v2026.11', status: '入库中', batchId: 'B20261109-02'
  },
  {
    id: 'reg-004', name: '广告绝对化用语执法指南', authority: '国家市场监督管理总局',
    docNumber: '公告2023年第6号', publishDate: '2023-02-24', effectiveDate: '2023-02-24', expiryDate: null,
    articleCount: 21, kbVersion: 'v2026.10', status: '阻塞', batchId: 'B20261108-03'
  },
  {
    id: 'reg-005', name: '食品安全抽样检验管理办法', authority: '国家市场监督管理总局',
    docNumber: '总局令第15号', publishDate: '2019-08-08', effectiveDate: '2019-10-01', expiryDate: '2025-12-31',
    articleCount: 58, kbVersion: 'v2026.10', status: '待入库', batchId: '—'
  }
]

export const demoBatches: IngestionBatch[] = [
  { batchId: 'B20261110-01', startedAt: '2026-11-10 08:55', documentCount: 4, status: '阻塞', successCount: 0, failedCount: 0, operator: 'system', blockedReason: 'kb_version 不一致：期望 v2026.11，实际 v2026.10' },
  { batchId: 'B20261109-02', startedAt: '2026-11-09 13:40', documentCount: 6, status: '执行中', successCount: 4, failedCount: 0, operator: 'system' },
  { batchId: 'B20261109-01', startedAt: '2026-11-09 09:15', documentCount: 12, status: '已完成', successCount: 12, failedCount: 0, operator: 'system' },
  { batchId: 'B20261108-03', startedAt: '2026-11-08 16:20', documentCount: 8, status: '失败', successCount: 7, failedCount: 1, operator: 'system' }
]

/** kb_version 不一致 → 必须显示整批阻断状态 */
export const demoVersionCheck: VersionCheck = {
  consistent: false,
  expectedVersion: 'v2026.11',
  actualVersion: 'v2026.10',
  blockedBatchIds: ['B20261110-01', 'B20261108-03'],
  checkedAt: '2026-11-10 09:12'
}

export const demoPrecheck: PrecheckItem[] = [
  { key: 'parsed', name: '文档解析完成', passed: true, detail: '58 份中 55 份解析成功', blocking: false },
  { key: 'clean', name: '法律文本清洗', passed: true, detail: '55 份完成清洗', blocking: false },
  { key: 'review', name: '人工审核状态', passed: true, detail: '待审核 0 份（DEMO）', blocking: false },
  { key: 'sha', name: '原始文件 SHA256 校验', passed: true, detail: '全部与上传时一致（DEMO）', blocking: false },
  { key: 'duplicate', name: '重复批次检查', passed: false, detail: 'B20261108-03 与已有批次指纹重复', blocking: true },
  { key: 'version', name: 'kb_version 一致性', passed: false, detail: '期望 v2026.11，实际 v2026.10', blocking: true },
  { key: 'auth', name: '批次授权', passed: false, detail: '授权接口未接入，无法验证操作权限', blocking: true }
]

export function fetchPipeline() {
  return Promise.resolve(demoResult(demoPipeline))
}

export function fetchRegulations() {
  return Promise.resolve(demoResult(demoRegulations))
}

export function fetchBatches() {
  return Promise.resolve(demoResult(demoBatches))
}

export function fetchVersionCheck() {
  return Promise.resolve(demoResult(demoVersionCheck))
}

export function fetchPrecheck() {
  return Promise.resolve(demoResult(demoPrecheck))
}
