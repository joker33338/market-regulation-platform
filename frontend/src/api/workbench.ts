import client from './client'
import type { DocumentInfo, ListResponse, ReviewQueue } from './types'

export interface WorkbenchDocument extends DocumentInfo {
  title: string
  number: string | null
  category: 'law' | 'case' | 'unconfirmed'
  stage: string
  parse_id: string | null
  review_version: number | null
  blocked_reason: string | null
  child_document_count?: number
  published_document_count?: number
}
export interface WorkbenchQuery {
  page: number
  page_size: number
  keyword: string
  stage: string
  category: string
  doc_type: string
  batch_id: string
  date_from: string
  date_to: string
}
export interface WorkbenchPage extends ListResponse<WorkbenchDocument> {
  summary: Record<string, number>
  availability: { postgres: boolean; review_ledger: boolean }
  batches: { batch_id: string; name: string; count: number }[]
}
export interface FileBatch {
  operation_id: string
  name: string
  created_at: string
  files: { file_id: string; relative_path?: string; status: string; task_id?: string; error_code?: string }[]
}
export const stageLabels: Record<string, string> = {
  uploaded: '待开始解析', processing: '处理中', awaiting_review: '待审核',
  awaiting_classification:'待确认资料',ready_to_build: '待构建', awaiting_publish: '待发布', published: '已发布',
  needs_attention: '需处理', state_unavailable: '状态待核实'
}
export function listWorkbenchDocuments(params: WorkbenchQuery, signal?: AbortSignal) {
  return client.get<WorkbenchPage>('/api/workbench/documents', { params: { ...params, date_from: params.date_from || undefined, date_to: params.date_to || undefined }, signal }).then(r => r.data)
}
export function createFileBatch(name: string, key: string) {
  return client.post<FileBatch>('/api/workbench/batches', { name }, { headers: { 'Idempotency-Key': key } }).then(r => r.data)
}
export function appendBatchFile(batchId: string, fileId: string, relativePath: string) {
  return client.post<FileBatch>(`/api/workbench/batches/${encodeURIComponent(batchId)}/files`,
    { files: [{ file_id: fileId, relative_path: relativePath }] }).then(r => r.data)
}

export interface SelectionSnapshot { selection_id: string; count: number; expires_at: number }
export function selectMatchingFiles(query: WorkbenchQuery, key: string) {
  const { page, page_size, ...filters } = query
  return client.post<SelectionSnapshot>('/api/workbench/selections',
    { ...filters, date_from: filters.date_from || null, date_to: filters.date_to || null },
    { headers: { 'Idempotency-Key': key } }).then(r => r.data)
}
export function selectionFiles(id: string, page: number) {
  return client.get<ListResponse<{file_id:string;file_name:string;sha256:string;parse_id:string|null;review_version:number|null}>>(
    `/api/workbench/selections/${encodeURIComponent(id)}/files`, { params:{page,page_size:100} }).then(r => r.data)
}

export interface KnowledgeJob {
  job_id:string;file_id:string;title:string;document_type:'law'|'case';status:string
  created_at:string;updated_at:string|null;error_code:string|null;kb_version:string;published_version?:string|null
}
export type KnowledgeJobPage=ListResponse<KnowledgeJob>
export const jobLabels:Record<string,string>={queued:'等待后台处理',awaiting_parse:'等待解析',awaiting_review:'待审核',
  awaiting_admin:'待管理员接手',building:'正在构建候选',awaiting_publish:'待发布',published:'已执行发布',needs_attention:'需处理'}
export function prepareKnowledgeFile(row: Pick<WorkbenchDocument,'file_id'|'sha256'|'parse_id'>,title:string,documentType:'law'|'case',key:string,extra:{source_range?:SourceRange;whole_file_confirmed?:boolean}={}) {
  return client.post<KnowledgeJob>(`/api/workbench/documents/${encodeURIComponent(row.file_id)}/prepare`,
    {title,document_type:documentType,expected_sha256:row.sha256,source_parse_id:row.parse_id || null,...extra},
    {headers:{'Idempotency-Key':key}}).then(r=>r.data)
}
export function listKnowledgeJobs(page:number,signal?:AbortSignal,fileId?:string) {
  return client.get<KnowledgeJobPage>('/api/workbench/jobs',{params:{page,page_size:20,file_id:fileId || undefined},signal}).then(r=>r.data)
}
export function checkKnowledgeJob(id:string) {
  return client.get<{publish_eligible:boolean;active_version:string|null}>(`/api/workbench/jobs/${encodeURIComponent(id)}/check`).then(r=>r.data)
}
export function publishKnowledgeJob(id:string,expectedActive:string|null,key:string) {
  return client.post<KnowledgeJob>(`/api/workbench/jobs/${encodeURIComponent(id)}/publish`,
    {expected_active_version:expectedActive},{headers:{'Idempotency-Key':key}}).then(r=>r.data)
}

export interface ReleaseManifest {
  release_id:string;status:string;kb_version:string;expected_active_version:string|null;document_count:number;category_counts:Record<string,number>
  documents:{job_id:string;title:string;document_type:'law'|'case';file_id:string}[]
}
export function createReleaseManifest(ids:string[],key:string,allReady=false) {
  return client.post<ReleaseManifest>('/api/workbench/releases',{job_ids:ids,all_ready:allReady},
    {headers:{'Idempotency-Key':key}}).then(r=>r.data)
}
export function appendReleaseItems(id:string,ids:string[]) {
  return client.post<ReleaseManifest>(`/api/workbench/releases/${encodeURIComponent(id)}/items`,{job_ids:ids}).then(r=>r.data)
}
export function prepareReleaseManifest(id:string) {
  return client.post<ReleaseManifest>(`/api/workbench/releases/${encodeURIComponent(id)}/prepare`,{}).then(r=>r.data)
}
export function checkReleaseManifest(id:string) {
  return client.get<{publish_eligible:boolean;active_version:string|null;manifest:ReleaseManifest}>(
    `/api/workbench/releases/${encodeURIComponent(id)}/check`).then(r=>r.data)
}
export function publishReleaseManifest(id:string,expectedActive:string|null,key:string) {
  return client.post<ReleaseManifest>(`/api/workbench/releases/${encodeURIComponent(id)}/publish`,
    {expected_active_version:expectedActive},{headers:{'Idempotency-Key':key}}).then(r=>r.data)
}

export function releaseManifestItems(id:string,page:number) {
  return client.get<ListResponse<ReleaseManifest['documents'][number]>>(
    `/api/workbench/releases/${encodeURIComponent(id)}/items`,{params:{page,page_size:20}}).then(r=>r.data)
}

export interface SourceRange {start:number;end:number;expected_text_sha256:string}
export interface SourceSegment extends SourceRange {
  title:string;document_type:'law'|'case';requires_confirmation:boolean;page_start:number;page_end:number
}
export interface SourceSuggestion {
  source_text:string;text_start:number;total_characters:number;page_offset:number;text_sha256:string;source_parse_id:string;suggested_type:'law'|'case'|null
  segments:SourceSegment[];warning:string
}
export function fileSuggestions(id:string,start=0){
  return client.get<SourceSuggestion>('/api/workbench/documents/'+encodeURIComponent(id)+'/suggestions',{params:{start,length:20000}}).then(r=>r.data)
}

export interface ReviewTarget {file_id:string;parse_id:string;expected_review_version:number;expected_sha256:string}
export interface ReviewBatchStatus {batch_id:string;action:'approve'|'reject';total:number;counts:Record<string,number>}
export function createReviewBatch(body:{action:'approve'|'reject';reason:string;attested:boolean;targets:ReviewTarget[];selection_id:string|null},key:string){
  return client.post<ReviewBatchStatus>('/api/workbench/review-batches',body,{headers:{'Idempotency-Key':key}}).then(r=>r.data)
}
export function appendReviewTargets(id:string,targets:ReviewTarget[]){
  return client.post<ReviewBatchStatus>('/api/workbench/review-batches/'+encodeURIComponent(id)+'/items',{targets}).then(r=>r.data)
}
export function reviewBatchStatus(id:string){
  return client.get<ReviewBatchStatus>('/api/workbench/review-batches/'+encodeURIComponent(id)).then(r=>r.data)
}

export interface ReviewedText {parse_id:string;review_version:number;approved:boolean;original_unchanged:boolean;pages:{page_number:number;text:string}[]}
export function reviewedText(id:string,signal?:AbortSignal){
  return client.get<ReviewedText>('/api/review/'+encodeURIComponent(id)+'/reviewed-text',{signal}).then(r=>r.data)
}
export interface ReviewBatchItem {file_id:string;file_name?:string;status:string;error_code?:string|null}
export function reviewBatchItems(id:string,page:number){
  return client.get<ListResponse<ReviewBatchItem>>('/api/workbench/review-batches/'+encodeURIComponent(id)+'/items',
    {params:{page,page_size:20}}).then(r=>r.data)
}

export function workbenchReviewQueue(page:number,pageSize:number,signal?:AbortSignal){
  return client.get<ReviewQueue>('/api/workbench/review-queue',{params:{page,page_size:pageSize},signal}).then(r=>r.data)
}
