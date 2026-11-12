/**
 * 【DEMO】解析任务列表与引擎面板
 * 后端现状：/api/parse/tasks 只有「按 task_id 查询」，没有列表 / 分页接口。
 * 任务列表为演示数据；单任务详情、错误、重试、取消、结果均为真实接口。
 * 引擎统计统一从 mock/stats.ts 派生，禁止各页自带数字。
 */
import type { ComponentState, DataSource } from '../types'
import { demoResult } from '../dataSource'
import { demoUnifiedStats } from './stats'

export interface TaskRow {
  taskId: string
  fileName: string
  docType: string
  pages: number
  engine: 'PaddleOCR' | 'PP-StructureV3' | 'MinerU'
  stage: string
  progress: number
  startedAt: string
  elapsedSeconds: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  fallbackReason?: string
}

/** 演示任务（非真实后端数据）：真实任务请通过任务 ID 查询 */
export const demoTasks: TaskRow[] = [
  { taskId: 'T-20261109-0042', fileName: '反垄断法（2022修正）.pdf', docType: '法律法规', pages: 42, engine: 'MinerU', stage: 'MinerU 云端解析', progress: 67, startedAt: '2026-11-09 14:12', elapsedSeconds: 238, status: 'running', fallbackReason: '扫描件复杂表格，本地置信度 0.71 < 阈值 0.85' },
  { taskId: 'T-20261109-0041', fileName: '消费品召回管理暂行规定.pdf', docType: '部门规章', pages: 18, engine: 'PP-StructureV3', stage: '表格结构识别', progress: 45, startedAt: '2026-11-09 14:05', elapsedSeconds: 96, status: 'running' },
  { taskId: 'T-20261109-0040', fileName: '价格违法行为行政处罚规定.docx', docType: '法律法规', pages: 12, engine: 'PaddleOCR', stage: '结果标准化', progress: 92, startedAt: '2026-11-09 13:58', elapsedSeconds: 51, status: 'running' },
  { taskId: 'T-20261109-0039', fileName: '检验检测机构监督管理办法.pdf', docType: '部门规章', pages: 31, engine: 'PaddleOCR', stage: '已完成', progress: 100, startedAt: '2026-11-09 11:44', elapsedSeconds: 78, status: 'completed' },
  { taskId: 'T-20261109-0038', fileName: '广告绝对化用语执法指南.pdf', docType: '执法指南', pages: 9, engine: 'MinerU', stage: '云端任务失败', progress: 100, startedAt: '2026-11-09 11:26', elapsedSeconds: 402, status: 'failed', fallbackReason: 'MinerU 返回 task_expired' },
  { taskId: 'T-20261109-0037', fileName: '市场主体登记管理条例实施细则.pdf', docType: '部门规章', pages: 55, engine: 'PP-StructureV3', stage: '已完成', progress: 100, startedAt: '2026-11-09 10:32', elapsedSeconds: 187, status: 'completed' },
  { taskId: 'T-20261109-0036', fileName: '食品安全抽样检验管理办法.pdf', docType: '部门规章', pages: 27, engine: 'PaddleOCR', stage: '已完成', progress: 100, startedAt: '2026-11-09 09:48', elapsedSeconds: 64, status: 'completed' },
  { taskId: 'T-20261109-0035', fileName: '网络交易监督管理办法.pdf', docType: '部门规章', pages: 38, engine: 'MinerU', stage: '已完成', progress: 100, startedAt: '2026-11-09 09:15', elapsedSeconds: 355, status: 'completed', fallbackReason: '扫描件，本地置信度不足' }
]

export interface EnginePanel {
  engine: string
  /** 无探活接口时为 UNKNOWN，绝不伪造 ONLINE */
  state: ComponentState
  taskCount: number
  successCount: number
  failedCount: number
  avgSeconds: number
  capability: string
  source: DataSource
}

export const demoEnginePanels: EnginePanel[] = demoUnifiedStats.engines.map((e) => ({
  engine: e.engine,
  state: 'UNKNOWN' as ComponentState,
  taskCount: e.taskCount,
  successCount: e.succeeded,
  failedCount: e.failed,
  avgSeconds: e.avgSeconds,
  capability: e.capability,
  source: 'demo' as DataSource
}))

export function fetchTasks() {
  return Promise.resolve(demoResult(demoTasks, '后端暂无任务列表接口，列表为演示数据；真实任务请用任务 ID 查询'))
}

export function fetchEnginePanels() {
  return Promise.resolve(demoResult(demoEnginePanels))
}
