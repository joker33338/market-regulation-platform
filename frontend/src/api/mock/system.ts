/**
 * 【DEMO 演示数据】系统监控 / 日志 / 审计
 * 后端暂无：健康检查聚合、操作审计日志接口
 */
import type { DataSource } from '../types'

export interface AuditRecord {
  id: string
  time: string
  operator: string
  action: string
  target: string
  result: '成功' | '失败'
  ip: string
}

export const demoAuditLog: AuditRecord[] = [
  { id: 'a-1001', time: '2026-11-09 13:52:11', operator: 'liu.kai', action: '审核通过', target: '网络交易监督管理办法 第3页', result: '成功', ip: '10.12.8.21' },
  { id: 'a-1002', time: '2026-11-09 13:40:02', operator: 'system', action: '触发入库批次', target: 'B20261109-02', result: '成功', ip: '127.0.0.1' },
  { id: 'a-1003', time: '2026-11-09 11:26:48', operator: 'liu.kai', action: '重新解析', target: '广告绝对化用语执法指南.pdf', result: '成功', ip: '10.12.8.21' },
  { id: 'a-1004', time: '2026-11-09 10:03:17', operator: 'liu.kai', action: '上传文件', target: '价格违法行为行政处罚规定.docx', result: '成功', ip: '10.12.8.21' },
  { id: 'a-1005', time: '2026-11-09 09:15:44', operator: 'system', action: '入库批次完成', target: 'B20261109-01（12 文档）', result: '成功', ip: '127.0.0.1' },
  { id: 'a-1006', time: '2026-11-08 17:31:05', operator: 'liu.kai', action: '标记识别错误', target: '食品安全抽样检验管理办法 表格T-12', result: '成功', ip: '10.12.8.21' }
]

export function fetchAuditLog(): Promise<{ data: AuditRecord[]; source: DataSource }> {
  return Promise.resolve({ data: demoAuditLog, source: 'demo' })
}
