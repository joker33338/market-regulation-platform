/**
 * 发布状态 —— 全站展示文案的事实来源（v0.2.2 正式运行）
 *
 * 2026-11-12 纠偏：下方 2026-11-11 运行期复核记录为联调阶段的历史事实，保留用于追溯；
 * 页面可见文案已按正式集成后的实际能力更新，不再标注「只读」。
 *
 * 事实依据：
 *  - docs/integration/frontend-api-contract.md（契约版本 frontend-api-v0.2.2-1）
 *  - docs/integration/v0.2.2-local-runtime-handoff.md（8180 已重建为候选镜像、health=healthy）
 *  - 后端分支 feat/backend-api-v0.2.2 @ 4fc4cf124a120762593064676ea5f8dbe2394119
 *  - 前端 docs/frontend-api-integration-report.md（七页面真实浏览器联调记录）
 *
 * 2026-11-11 运行期复核：活动 8180 实例返回 info.version=0.2.2-api-candidate、
 * 22 个 OpenAPI 路径；本机用私有会话凭证在真实浏览器（Edge headless / CDP）完成
 * 七页面渲染与交互联调，约定只读接口全部成功返回并渲染真实业务数据。
 *
 * 边界（不得越界宣称）：
 *  - 正式审核写入、入库批次/发布/回滚、结构化日志仍无 HTTP 接口，按钮保持禁用；
 *  - 上传、创建任务、恢复/取消等写链路按用户约束未执行，不属于本轮验证范围；
 *  - 独立 QA 验收与生产部署尚未进行；public 知识库无 ACTIVE 版本，检索返回 unpublished。
 */
export const releaseStatus = {
  version: 'v0.2.2',
  /** 后端 v0.2.1 MVP 有限范围 QA 结论（历史结论，不覆盖 v0.2.2 新接口） */
  backendQa: 'PASS',
  qaDate: '2026-11-11',
  qaDecisionFile: 'docs/qa/v0.2.1/final-release-decision.md',
  qaScope: 'v0.2.1 后端 MVP 有限范围验收；不含 v0.2.2 新接口、独立 QA 全验收与生产部署',
  /** 后端契约与运行期一致：同一源码 SHA 构建的活动镜像 */
  backendContractSha: '4fc4cf124a120762593064676ea5f8dbe2394119',
  backendContractBranch: 'feat/backend-api-v0.2.2',
  frontendBaseSha: '5dd44b97710db0d3bdb84bcec6e1624dd70205dc',
  contractVersion: 'frontend-api-v0.2.2-1',
  /** 运行期事实（来自本地运行交接文档 + 实测 /api/openapi.json） */
  runtimeImage: 'market-regulation-workbench:candidate-v022-4fc4cf124a12',
  runtimeContractVersion: '0.2.2-api-candidate',
  runtimeOpenApiPaths: 22,
  runtimeVerifiedAt: '2026-11-11',
  /** 顶栏 / 页头短标签（2026-11-12 纠偏：不再使用联调阶段的「只读」字样） */
  shortLabel: 'v0.2.2 正式运行 · 真实 API',
  /** 详细告警 */
  alertTitle: 'v0.2.2 已对接真实接口，部分写入能力仍待后端提供',
  alertDescription:
    'v0.2.2 正式镜像由 FastAPI 同源托管前端页面与 /api；七个页面的业务数据全部来自后端真实响应，无 DEMO / Mock 回退。文件上传、创建解析任务、任务恢复与取消、下载原件、法规检索、原文预览等已接真实 API。审核写入、入库批次/发布/回滚、结构化日志及检索的部分筛选字段，当前运行期 OpenAPI 契约尚未加载对应接口，相关按钮保持禁用并标注「待后端支持」，不伪造成功。v0.2.3 源码契约已交付但尚未部署，前端一律按运行期探测结果判定，不提前解锁。所有 /api/* 请求需要 Bearer 会话凭证；未配置或凭证失效时显示明确的未认证/无权限态，不隐藏错误。',
  /** 独立前端只读联调是否完成：运行期契约 + 真实 Token + 浏览器逐页验证 */
  frontendIntegrated: true,
  /** 接口契约复核结论 */
  apiContractReview: '22 个 OpenAPI 路径（复用 8 + 新增 14）＋ 1 个认证探测端点 · 按方法列举 24 行 · 8 组能力明确不支持'
} as const
