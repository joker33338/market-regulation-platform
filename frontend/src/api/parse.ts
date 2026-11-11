import client from './client'
import type {
  CreateTaskPayload,
  ParseServiceInfo,
  ParseTask,
  TaskResults,
  UploadResponse
} from './types'

/**
 * 真实后端接口 —— 全部对应 qa_core/document_parsing/mineru_api.py 的 9 个路由（+ 无鉴权根页面）
 * 契约来源：路由源码 + 后端自带参考客户端 parsing_upload.html
 * 2026-11-11 复核：f4a0af8 / 3129479 / 843c64d / 5dd44b9 四个提交的路由定义一致，
 * 仍为 9 个 API，契约零变化；后端 MVP 已通过有限范围 QA，但不含独立前端全联调，
 * 因此页面不标记任何能力为「正式可用」，未接入接口仍保持禁用。
 */

/** 上传约束（对齐 mineru_service.py 的后缀白名单与 mineru_config.py 的大小限制） */
export const UPLOAD_LIMIT_BYTES = 100 * 1024 * 1024
export const UPLOAD_ALLOWED_EXT = ['.pdf', '.docx', '.png', '.jpg', '.jpeg'] as const
export const MAX_FILES_PER_TASK = 20

/** GET /api/parse/info 服务信息（唯一真实探活） */
export function getParseInfo(): Promise<ParseServiceInfo> {
  return client.get<ParseServiceInfo>('/api/parse/info').then((r) => r.data)
}

/**
 * POST /api/parse/files
 * 后端读取 request.stream() 的原始字节并校验文件头魔数，绝不能用 multipart/form-data。
 * query 传 file_name；body 直接是 File 二进制流。
 */
export function uploadFile(file: File, onProgress?: (percent: number) => void): Promise<UploadResponse> {
  return client
    .post<UploadResponse>('/api/parse/files', file, {
      params: { file_name: file.name },
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      }
    })
    .then((r) => r.data)
}

/** POST /api/parse/tasks 创建解析任务（后端返回完整 public(task)，不是 { task_id }） */
export function createParseTask(
  payload: CreateTaskPayload,
  idempotencyKey?: string
): Promise<ParseTask> {
  return client
    .post<ParseTask>('/api/parse/tasks', payload, {
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined
    })
    .then((r) => r.data)
}

/** GET /api/parse/tasks/{task_id} 任务详情（状态 / 引擎选择 / 回退原因 / 审核标记） */
export function getParseTask(taskId: string): Promise<ParseTask> {
  return client.get<ParseTask>(`/api/parse/tasks/${encodeURIComponent(taskId)}`).then((r) => r.data)
}

/**
 * GET /api/parse/tasks/{task_id}/errors
 * 注意：后端仍返回 public(task)，并非独立错误列表；错误详情在 files[].error 中。
 */
export function getParseTaskErrors(taskId: string): Promise<ParseTask> {
  return client
    .get<ParseTask>(`/api/parse/tasks/${encodeURIComponent(taskId)}/errors`)
    .then((r) => r.data)
}

/** POST /api/parse/tasks/{task_id}/resume 重试 */
export function resumeParseTask(taskId: string): Promise<ParseTask> {
  return client
    .post<ParseTask>(`/api/parse/tasks/${encodeURIComponent(taskId)}/resume`)
    .then((r) => r.data)
}

/** POST /api/parse/tasks/{task_id}/cancel 取消 */
export function cancelParseTask(taskId: string): Promise<ParseTask> {
  return client
    .post<ParseTask>(`/api/parse/tasks/${encodeURIComponent(taskId)}/cancel`)
    .then((r) => r.data)
}

/** GET /api/parse/tasks/{task_id}/results 标准化结果 */
export function getParseTaskResults(taskId: string): Promise<TaskResults> {
  return client
    .get<TaskResults>(`/api/parse/tasks/${encodeURIComponent(taskId)}/results`)
    .then((r) => r.data)
}

/**
 * GET /api/parse/tasks/{task_id}/files/{file_id}/artifact
 * 返回 artifact.bin 二进制（MinerU 解析产物归档），**不是原始证据文件**。
 * 后端不接受 kind 参数，须按二进制接收。
 */
export function getFileArtifact(taskId: string, fileId: string): Promise<ArrayBuffer> {
  return client
    .get(`/api/parse/tasks/${encodeURIComponent(taskId)}/files/${encodeURIComponent(fileId)}/artifact`, {
      responseType: 'arraybuffer'
    })
    .then((r) => r.data as ArrayBuffer)
}
