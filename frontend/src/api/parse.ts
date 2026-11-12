import client from './client'
import type {
  CreateTaskPayload, ParseServiceInfo, ParseTask, TaskResults, UploadResponse
} from './types'

/**
 * 复用接口（9 个）—— 对应 qa_core/document_parsing/mineru_api.py 既有路由。
 * v0.2.2 复核：新增只读接口见 frontend.ts；本文件的 9 个契约在
 * feat/backend-api-v0.2.2 @ 4fc4cf1 中保持不变（仅补 OpenAPI 描述，不改行为）。
 *
 * 契约来源：docs/integration/frontend-api-contract.md + frontend-openapi.json
 * + 后端自带参考客户端 parsing_upload.html。
 * 运行期是否加载由 /api/openapi.json 探测决定，本文件不假设服务已切换。
 */

/** 上传约束（对齐 mineru_service.py 的后缀白名单与 mineru_config.py 的大小限制） */
export const UPLOAD_LIMIT_BYTES = 100 * 1024 * 1024
export const UPLOAD_ALLOWED_EXT = ['.pdf', '.docx', '.png', '.jpg', '.jpeg'] as const
export const MAX_FILES_PER_TASK = 20

function signalOf(signal?: AbortSignal) {
  return signal ? { signal } : {}
}

/** GET /api/parse/info 服务信息（旧接口真实探活） */
export function getParseInfo(signal?: AbortSignal): Promise<ParseServiceInfo> {
  return client.get<ParseServiceInfo>('/api/parse/info', signalOf(signal)).then((r) => r.data)
}

/**
 * POST /api/parse/files
 * 后端读取 request.stream() 的原始字节并校验文件头魔数，绝不能用 multipart/form-data。
 * query 传 file_name；body 直接是 File 二进制流。进度取 Axios 真实 onUploadProgress 事件。
 */
export function uploadFile(
  file: File,
  onProgress?: (percent: number) => void,
  signal?: AbortSignal
): Promise<UploadResponse> {
  return client
    .post<UploadResponse>('/api/parse/files', file, {
      params: { file_name: file.name },
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** POST /api/parse/tasks 创建解析任务（后端返回完整 public(task)，不是 { task_id }） */
export function createParseTask(
  payload: CreateTaskPayload,
  idempotencyKey: string,
  signal?: AbortSignal
): Promise<ParseTask> {
  return client
    .post<ParseTask>('/api/parse/tasks', payload, {
      headers: { 'Idempotency-Key': idempotencyKey },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** GET /api/parse/tasks/{task_id} 任务详情（状态 / 引擎选择 / 回退原因 / 审核标记） */
export function getParseTask(taskId: string, signal?: AbortSignal): Promise<ParseTask> {
  return client
    .get<ParseTask>(`/api/parse/tasks/${encodeURIComponent(taskId)}`, signalOf(signal))
    .then((r) => r.data)
}

/**
 * GET /api/parse/tasks/{task_id}/errors
 * 后端仍返回 public(task)，并非独立错误列表；错误详情在 files[].error 中。
 */
export function getParseTaskErrors(taskId: string, signal?: AbortSignal): Promise<ParseTask> {
  return client
    .get<ParseTask>(`/api/parse/tasks/${encodeURIComponent(taskId)}/errors`, signalOf(signal))
    .then((r) => r.data)
}

/** POST /api/parse/tasks/{task_id}/resume 重试 */
export function resumeParseTask(taskId: string, signal?: AbortSignal): Promise<ParseTask> {
  return client
    .post<ParseTask>(`/api/parse/tasks/${encodeURIComponent(taskId)}/resume`, undefined, signalOf(signal))
    .then((r) => r.data)
}

/** POST /api/parse/tasks/{task_id}/cancel 取消 */
export function cancelParseTask(taskId: string, signal?: AbortSignal): Promise<ParseTask> {
  return client
    .post<ParseTask>(`/api/parse/tasks/${encodeURIComponent(taskId)}/cancel`, undefined, signalOf(signal))
    .then((r) => r.data)
}

/** GET /api/parse/tasks/{task_id}/results 标准化结果 */
export function getParseTaskResults(taskId: string, signal?: AbortSignal): Promise<TaskResults> {
  return client
    .get<TaskResults>(`/api/parse/tasks/${encodeURIComponent(taskId)}/results`, signalOf(signal))
    .then((r) => r.data)
}

/**
 * GET /api/parse/tasks/{task_id}/files/{file_id}/artifact
 * 返回 artifact.bin 二进制（MinerU 解析产物归档），**不是原始证据文件**。
 * 原始文件请使用 documentFiles.ts 的 /source 接口。
 */
export function getFileArtifact(taskId: string, fileId: string, signal?: AbortSignal): Promise<ArrayBuffer> {
  return client
    .get(`/api/parse/tasks/${encodeURIComponent(taskId)}/files/${encodeURIComponent(fileId)}/artifact`, {
      responseType: 'arraybuffer',
      ...signalOf(signal)
    })
    .then((r) => r.data as ArrayBuffer)
}
