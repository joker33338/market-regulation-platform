import { apiCapabilities } from './dataSource'

/**
 * 原始文件源适配层 —— 全站唯一入口
 *
 * 后端目前**没有**任何返回原始 PDF / Word / 图片的接口：
 * artifact.bin 是 MinerU 解析产物归档（mineru_artifacts.py），不是原始证据文件，
 * 严禁用于预览或下载冒充。
 *
 * 接口交付后：
 *  1) 把 apiCapabilities.sourceFile 置 true
 *  2) 在下方 getSourceFile() 内改为 GET /api/parse/files/{file_id}/source
 *     （responseType: 'arraybuffer'，校验响应头 X-SHA256 与上传时一致）
 *  3) 预览组件无需改动，自动启用真实渲染
 */
export const SOURCE_FILE_API = 'GET /api/parse/files/{file_id}/source'

export interface SourceFile {
  data: ArrayBuffer
  sha256: string
  fileName: string
  contentType: string
}

export type SourceFileResult =
  | { available: true; file: SourceFile }
  | { available: false; api: string; reason: string }

export async function getSourceFile(fileId: string): Promise<SourceFileResult> {
  if (!apiCapabilities.sourceFile) {
    return {
      available: false,
      api: SOURCE_FILE_API,
      reason: '原始文件读取接口尚未接入，无法通过后端获取 PDF / Word / 图片进行真实预览'
    }
  }
  // 接口已声明但前端适配实现待接入（接口交付时在此补 HTTP 请求）
  void fileId
  return {
    available: false,
    api: SOURCE_FILE_API,
    reason: '接口已交付，但前端文件源适配实现尚未启用'
  }
}

/** 原始文件下载与预览共用同一数据源；接口未接入时一律不可用 */
export const sourceFileAvailable = () => apiCapabilities.sourceFile
