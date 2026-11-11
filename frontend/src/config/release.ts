/**
 * 发布状态 —— 全站唯一事实来源
 *
 * 事实依据：docs/qa/v0.2.1/final-release-decision.md（2026-11-11 签发，结论 PASS）
 * 该裁决明确排除「独立前端全部联调」「生产部署」「活动旧实例切换」「Windows 整机恢复」，
 * 因此前端不得把整套系统标记为「正式可用」；后端没有新增 HTTP 接口，
 * 未接入能力继续保持 DEMO 标注与写操作禁用。
 *
 * 契约复核（2026-11-11）：f4a0af8 / 3129479 / 843c64d / 5dd44b9 四个提交的
 * mineru_api.py 路由定义逐行一致，仍为 9 个 API，仅注释中文化，契约零变化。
 */
export const releaseStatus = {
  version: 'v0.2.1',
  /** 后端 MVP 有限范围 QA 结论 */
  backendQa: 'PASS',
  qaDate: '2026-11-11',
  qaDecisionFile: 'docs/qa/v0.2.1/final-release-decision.md',
  qaScope: '后端 MVP 与本地镜像集成验收；不含独立前端全联调、生产部署、活动实例切换',
  /** 顶栏 / 页头短标签 */
  shortLabel: '后端 QA PASS · 前端待联调',
  /** 详细告警（系统监控 / 登录页） */
  alertTitle: '后端 MVP 已通过有限范围 QA（2026-11-11 PASS）',
  alertDescription:
    '该结论不含独立前端全联调与生产部署。标注 DEMO 的数据仍为演示数据，未接入接口对应的写操作保持禁用；组件状态中只有 FastAPI 为真实探测。请勿据此宣称整套系统已正式可用。',
  /** 独立前端全联调是否完成：QA 裁决明确列为后续范围 */
  frontendIntegrated: false,
  /** 接口契约复核结论 */
  apiContractReview: '四分支路由一致 · 9 个 API 契约零变化 · 无新增接口'
} as const
