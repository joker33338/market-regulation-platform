/**
 * Phase 2 §5 文案清单（定稿，直接使用）。
 *
 * 页面状态一律由 useLibraryQuery 按 status + code 映射后取这里的统一文案；
 * 不直接展示统一错误层的 hint 原文，避免把与 draft-5 契约语义冲突的全局文案带进这两页。
 * 门控态 / 错误态 / 合法空态由 L1 页面级状态区承载，L2 AsyncPanel 只接三态。
 */

export const LIB_COPY = {
  /** 运行期路由未加载：path 用实际 OpenAPI 模板路径代入 */
  gate: (path: string) =>
    `运行期未加载该接口（GET ${path}），入口已禁用，未发起请求；请确认活动实例已加载 v0.2.3 draft-5 契约。`,
  noToken:
    '未配置会话凭证：所有 /api/* 请求需要 Bearer，入口已禁用、未发起请求；请在系统监控页配置有效凭证。',
  contract:
    '运行期契约未就绪：GET /api/openapi.json 探测未通过，入口已禁用、未发起请求；请确认后端服务可达后重试。',
  unpublished:
    '知识库尚未发布：当前 public 知识库无 ACTIVE 版本，后端返回 status=unpublished（合法 200 空结果）。这是正常状态，不是错误；发布后刷新即可。',
  empty:
    '未找到符合条件的数据（后端返回空列表）。可清空筛选或返回，不会以演示数据填充。',
  notFound404:
    '未找到该对象，或它不在当前身份的可见范围内。出于安全考虑不区分「不存在」与「无权访问」，请返回列表重新选择。',
  auth401:
    '未认证或无权访问（401 / 403）：凭证无效、被停用 / 撤销，或当前身份无权访问。已清空本页数据，请重新配置有效凭证。',
  invalid422:
    '请求参数不被接受（422）：请检查分页与筛选参数；空值一律不发送。',
  invalid422Violation:
    '请求参数不被接受（422，violation_filter_case_only）：violation 仅案例库支持，法规库不得发送该参数。',
  schema503:
    '已发布版本存在，但新库 Schema 未安装（library_schema_not_installed）。这不是空数据，请联系管理员完成安装后重试。',
  unavailable:
    '后端服务暂不可用或请求失败：未展示任何替代数据，请稍后重试。',
  canceled:
    '请求已取消：未展示任何数据。可重新查询或返回列表。',
  ocr:
    '以下为 OCR 自动识别原文，尚未经人工核验（ocr_not_manually_verified），不得作为法律适用依据；请以人工核验字段与原件为准。',
  charRange:
    'raw_start / raw_end 为零基、左闭右开的字符范围 [start, end)，后端据此切片原文；前端不重新切分、不推断页码边界。',
  penalty:
    '罚款金额按后端原样十进制字符串展示，不做数值格式化、不四舍五入、不补币种。',
  nullField:
    '该字段后端未返回（null），前端不补写、不推断、不以 0 或「无」代替。',
  /** null 在表格 / 字段里的短展示（原任务书 §7 口径） */
  nullShort: '—（后端未返回，前端不补写）',
  /** 原件读取失败：统一文案，不外泄统一错误层 hint 原文 */
  sourceError:
    '原件读取失败：请确认原件可用且当前身份有权访问（不展示后端原文）。',
  stateNote:
    '状态语义严格分离：契约 / 路由未加载 = 警告标签 + 控件禁用；unpublished 是合法空态（不是错误）；401 / 404 / 422 / 503 是错误态常显。禁用态同时提供文字说明与控件 disabled，不只靠颜色；本页不把自动提取 / pending 标成已核验，不把后端空数组当错误。',
  filterNote: (isCase: boolean, isAdmin: boolean) => {
    const parts: string[] = []
    parts.push(isCase
      ? '案例库支持 violation（≤200 字符）；其它参数均为契约白名单字段，空值一律不发送。'
      : '法规库整体隐藏 violation 控件，也不发送该参数（后端会返回 422 violation_filter_case_only）；筛选仅 query / kb_version / page / page_size。')
    parts.push(isAdmin
      ? '当前身份为 ADMIN：提供 kb_version（1..128）显式选版。'
      : '仅 ADMIN 可显式选择版本：kb_version 控件不提供，其他角色传了会返回 403。')
    parts.push('筛选提交时冻结筛选快照；分页只透传 page / page_size，total 取后端响应，size-change 归 1，不切片、不累计。')
    parts.push('禁用态同时提供文字说明与控件 disabled，不只靠颜色。')
    return parts.join(' ')
  }
} as const

/** 核验状态：pending = 待核验(info)，verified = 已核验(success)，其余如实显示且不得标成已核验 */
export function verificationLabel(value: unknown): string {
  if (value === 'verified') return '已核验（verified）'
  if (value === 'pending') return '待核验（pending）'
  return value == null || value === '' ? LIB_COPY.nullShort : `${value}（未标注核验状态）`
}

export function verificationTagType(value: unknown): 'info' | 'success' | 'warning' {
  if (value === 'verified') return 'success'
  if (value === 'pending') return 'info'
  return 'warning'
}
