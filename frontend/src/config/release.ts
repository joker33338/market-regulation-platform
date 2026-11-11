/**
 * 发布状态 —— 全站唯一事实来源（v0.2.2）
 *
 * 事实依据：
 *  - docs/integration/frontend-api-contract.md（契约版本 frontend-api-v0.2.2-1）
 *  - docs/integration/frontend-api-gap-report.md（后端自评 BACKEND_API_PARTIAL）
 *  - docs/integration/v0.2.2-git-commit-plan.md（8 个模块提交，28 项定向测试通过）
 *  - 后端分支 feat/backend-api-v0.2.2 @ 4fc4cf124a120762593064676ea5f8dbe2394119
 *
 * 边界：后端源码与离线契约已交付，但活动 8180 实例仍是 v0.2.1 旧镜像（新接口实测 404），
 * 且尚未提供联调 Token。前端不得宣称已联调通过、不得把 DEMO 当真实数据、不得解除写操作禁用。
 */
export const releaseStatus = {
  version: 'v0.2.2',
  /** 后端 v0.2.1 MVP 有限范围 QA 结论（历史结论，不覆盖 v0.2.2 新接口） */
  backendQa: 'PASS',
  qaDate: '2026-11-11',
  qaDecisionFile: 'docs/qa/v0.2.1/final-release-decision.md',
  qaScope: 'v0.2.1 后端 MVP 有限范围验收；不含 v0.2.2 新接口、独立前端全联调与生产部署',
  /** 后端契约源码交付状态 */
  backendContractSha: '4fc4cf124a120762593064676ea5f8dbe2394119',
  backendContractBranch: 'feat/backend-api-v0.2.2',
  frontendBaseSha: '5dd44b97710db0d3bdb84bcec6e1624dd70205dc',
  contractVersion: 'frontend-api-v0.2.2-1',
  /** 顶栏 / 页头短标签 */
  shortLabel: 'v0.2.2 契约已交付 · 待运行期联调',
  /** 详细告警 */
  alertTitle: 'v0.2.2 只读接口契约已交付，活动服务尚未切换',
  alertDescription:
    '后端已实现 22 条 HTTP 路径并通过 28 项定向测试，但 127.0.0.1:8180 当前仍运行 v0.2.1 旧镜像，新接口实测 404。前端以运行期 /api/openapi.json 探测为准，未就绪时显示明确异常态，不回退 DEMO、不伪造业务结果。正式审核写入、入库发布/回滚仍无接口，按钮保持禁用。',
  /** 独立前端全联调是否完成：需服务切换 + Token + 浏览器验证 */
  frontendIntegrated: false,
  /** 接口契约复核结论 */
  apiContractReview: '22 条真实路径（复用 9 + 新增 15）· 8 组能力明确不支持'
} as const
