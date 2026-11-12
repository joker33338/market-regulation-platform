/**
 * 【DEMO】工作台数据 —— 全部从唯一统计快照 mock/stats.ts 派生
 * 后端暂无：统计聚合 / 趋势 / 引擎分布 / 健康检查聚合接口
 * 真实接口交付后替换数据源即可，页面无需改动。
 */
import type { ComponentState, DataSource } from '../types'
import { demoResult } from '../dataSource'
import {
  STATS_RANGE_DAYS,
  demoUnifiedStats,
  engineSuccessRate,
  type EngineStat
} from './stats'

export interface DashboardStats {
  rangeDays: number
  totalFiles: number       // 文件数（上传记录）
  totalTasks: number       // 解析任务数
  succeeded: number
  failed: number
  running: number
  pendingReview: number
  ingestedRegulations: number
}

export interface TrendPoint {
  date: string
  uploaded: number
  parsed: number   // 当日解析成功任务数
  failed: number   // 当日解析失败任务数
}

export interface EngineDistribution {
  engine: string
  count: number
}

/** 系统组件五态：只有真实探测成功才允许 ONLINE */
export interface ComponentStatus {
  name: string
  state: ComponentState
  note: string
  source: DataSource
  /** 是否具备真实探活能力（当前仅 FastAPI /api/parse/info） */
  realProbe: boolean
}

const S = demoUnifiedStats

export const demoStats: DashboardStats = {
  rangeDays: S.rangeDays,
  totalFiles: S.totalFiles,
  totalTasks: S.totalTasks,
  succeeded: S.succeeded,
  failed: S.failed,
  running: S.running,
  pendingReview: S.pendingReview,
  ingestedRegulations: S.ingestedRegulations
}

/**
 * 近 14 天固定序列（不使用随机数，避免刷新后数字跳动）。
 * parsed 合计 = 1053 = 总成功数；failed 合计 = 51 = 总失败数，与统计卡同口径。
 */
const PARSED = [72, 68, 75, 80, 71, 66, 78, 82, 74, 69, 77, 81, 79, 81]
const FAILED = [4, 3, 5, 4, 2, 6, 3, 4, 5, 2, 4, 3, 4, 2]
const UPLOADED = [88, 79, 92, 96, 84, 80, 93, 98, 90, 82, 94, 97, 95, 96]

export const demoTrend: TrendPoint[] = PARSED.map((parsed, i) => {
  const d = new Date(Date.now() - (STATS_RANGE_DAYS - 1 - i) * 86400000)
  return {
    date: `${d.getMonth() + 1}/${d.getDate()}`,
    uploaded: UPLOADED[i],
    parsed,
    failed: FAILED[i]
  }
})

export const demoEngineDist: EngineDistribution[] = S.engines.map((e) => ({
  engine: e.engine,
  count: e.taskCount
}))

/** 成功率由成功数 / 任务数实时计算，不再手写与统计矛盾的数字 */
export const demoSuccessRate: Array<{ name: string; value: number; stat: EngineStat }> =
  S.engines.map((e) => ({ name: e.engine, value: engineSuccessRate(e), stat: e }))

export const demoRecentIngestion = [
  { name: '市场监督管理行政处罚程序规定', version: 'v2026.11', articles: 86, time: '2026-11-09 10:24', status: '已入库' },
  { name: '网络交易监督管理办法', version: 'v2026.11', articles: 64, time: '2026-11-08 16:02', status: '已入库' },
  { name: '广告绝对化用语执法指南', version: 'v2026.11', articles: 21, time: '2026-11-08 11:47', status: '已入库' },
  { name: '食品安全抽样检验管理办法', version: 'v2026.10', articles: 58, time: '2026-11-07 15:31', status: '待审核' }
]

export const demoComponentStatus: ComponentStatus[] = [
  { name: 'FastAPI', state: 'UNKNOWN', note: '真实探活 /api/parse/info', source: 'real', realProbe: true },
  { name: 'PostgreSQL', state: 'UNKNOWN', note: '暂无探活接口', source: 'demo', realProbe: false },
  { name: 'PaddleOCR', state: 'UNKNOWN', note: '暂无探活接口', source: 'demo', realProbe: false },
  { name: 'PP-StructureV3', state: 'UNKNOWN', note: '暂无探活接口', source: 'demo', realProbe: false },
  { name: 'MinerU API', state: 'NOT_CONFIGURED', note: '未配置凭证时不得标为在线', source: 'demo', realProbe: false },
  { name: 'BGE-M3', state: 'UNKNOWN', note: '暂无探活接口', source: 'demo', realProbe: false }
]

export function fetchDashboardStats() {
  return Promise.resolve(demoResult(demoStats))
}

export function fetchTrend() {
  return Promise.resolve(demoResult(demoTrend))
}
