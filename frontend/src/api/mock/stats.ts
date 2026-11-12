/**
 * 【DEMO】唯一统计数据源
 *
 * 所有页面（工作台 / 解析中心 / 系统监控）共用同一份快照，禁止各页自带数字。
 * 口径定义：
 *  - totalFiles：上传的**文件记录数**，与任务数分列，不相加
 *  - totalTasks：**解析任务数**；恒等式 成功 + 失败 + 执行中/待处理 = 任务总数
 *  - 引擎分布之和 = 任务总数；各引擎成功/失败之和 = 总成功/失败
 *  - 统一时间范围：近 STATS_RANGE_DAYS 天
 *
 * 真实接口（GET /api/stats/overview、/api/stats/trend）交付后，
 * 只需替换本文件的数据来源，页面无需改动。
 */
export const STATS_RANGE_DAYS = 14

export type EngineName = 'PaddleOCR' | 'PP-StructureV3' | 'MinerU'

export interface EngineStat {
  engine: EngineName
  taskCount: number
  succeeded: number
  failed: number
  avgSeconds: number
  capability: string
}

export interface UnifiedStats {
  rangeDays: number
  totalFiles: number
  totalTasks: number
  succeeded: number
  failed: number
  running: number
  pendingReview: number
  ingestedRegulations: number
  engines: EngineStat[]
}

export const demoUnifiedStats: UnifiedStats = {
  rangeDays: STATS_RANGE_DAYS,
  totalFiles: 1286,
  totalTasks: 1104,
  succeeded: 1053,
  failed: 51,
  running: 0,
  pendingReview: 58,
  ingestedRegulations: 342,
  engines: [
    {
      engine: 'PaddleOCR',
      taskCount: 712,
      succeeded: 689,
      failed: 23,
      avgSeconds: 58,
      capability: '常规文档本地解析'
    },
    {
      engine: 'PP-StructureV3',
      taskCount: 306,
      succeeded: 286,
      failed: 20,
      avgSeconds: 142,
      capability: '表格识别 / 复杂版面'
    },
    {
      engine: 'MinerU',
      taskCount: 86,
      succeeded: 78,
      failed: 8,
      avgSeconds: 331,
      capability: '复杂扫描件云端回退'
    }
  ]
}

/** 成功率按真实分子分母计算，不再手写与统计矛盾的数字 */
export function engineSuccessRate(e: EngineStat): number {
  if (!e.taskCount) return 0
  return Math.round((e.succeeded / e.taskCount) * 1000) / 10
}

/**
 * 统计一致性自检：返回所有不一致项，供开发期与回归测试使用。
 * 空数组 = 口径自洽。
 */
export function statsConsistencyIssues(s: UnifiedStats): string[] {
  const issues: string[] = []
  if (s.succeeded + s.failed + s.running !== s.totalTasks) {
    issues.push('成功 + 失败 + 执行中 ≠ 任务总数')
  }
  const taskSum = s.engines.reduce((n, e) => n + e.taskCount, 0)
  const okSum = s.engines.reduce((n, e) => n + e.succeeded, 0)
  const failSum = s.engines.reduce((n, e) => n + e.failed, 0)
  if (taskSum !== s.totalTasks) issues.push('引擎任务数之和 ≠ 任务总数')
  if (okSum !== s.succeeded) issues.push('引擎成功数之和 ≠ 总成功数')
  if (failSum !== s.failed) issues.push('引擎失败数之和 ≠ 总失败数')
  for (const e of s.engines) {
    if (e.succeeded + e.failed > e.taskCount) issues.push(`${e.engine} 成功+失败超过任务数`)
  }
  return issues
}
