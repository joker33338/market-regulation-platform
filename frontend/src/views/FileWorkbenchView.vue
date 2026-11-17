<template>
  <div class="page file-workbench">
    <header class="page-header">
      <div><h1 class="page-title">文件处理工作台</h1><p class="page-desc">从上传到入库，集中查看每份文件的进度和下一步。</p></div>
      <el-button @click="router.push('/documents/advanced')">更多文件操作</el-button>
    </header>
    <BatchUploadPanel v-if="principal" :key="principal.principal_id" :enabled="batchEnabled" @submitted="scheduleRefresh" />
    <el-alert v-if="reviewBatch" type="info" :closable="false" :title="'本批审核：成功 '+(reviewBatch.counts.completed || 0)+' 份，失败 '+(reviewBatch.counts.failed || 0)+' 份，待处理 '+((reviewBatch.counts.queued || 0)+(reviewBatch.counts.running || 0))+' 份'"><el-button text @click="reviewResultsOpen=true">查看逐项结果</el-button></el-alert>
    <el-card shadow="never" class="files-card">
      <div class="stage-filters" aria-label="按处理阶段筛选">
        <el-button :type="query.stage === '' ? 'primary' : 'default'" @click="changeStage('')">全部文件</el-button>
        <el-button v-for="stage in stages" :key="stage" :type="query.stage === stage ? 'primary' : 'default'" @click="changeStage(stage)">
          {{ stageLabels[stage] }} {{ list.data.value?.summary[stage] || 0 }}
        </el-button>
      </div>
      <form class="file-filters" @submit.prevent="applyFilters">
        <el-input v-model="draftKeyword" clearable aria-label="搜索文件" placeholder="搜索文件名、资料标题、文号或案号" />
        <el-select v-model="draftCategory" clearable aria-label="资料类别" placeholder="全部资料类别">
          <el-option label="法规" value="law" /><el-option label="处罚案例" value="case" /><el-option label="归类待确认" value="unconfirmed" />
        </el-select>
        <el-select v-model="draftBatch" clearable filterable aria-label="上传批次" placeholder="全部上传批次">
          <el-option v-for="batch in list.data.value?.batches || []" :key="batch.batch_id" :label="batch.name" :value="batch.batch_id" />
        </el-select>
        <el-date-picker v-model="draftDates" type="daterange" start-placeholder="上传开始日期" end-placeholder="上传结束日期" range-separator="至" aria-label="上传日期范围" />
        <el-button type="primary" native-type="submit">查询</el-button>
        <el-button @click="resetFilters">清空筛选</el-button>
        <el-button @click="saveFilter">保存常用筛选</el-button>
        <el-button v-if="hasSavedFilter" @click="restoreFilter">使用常用筛选</el-button>
      </form>
      <div class="applied-filters" role="status">
        <span>当前范围：{{ query.keyword || '全部关键词' }} · {{ categoryLabel(query.category) }} · {{ stageLabels[query.stage] || '全部状态' }}</span>
        <el-button text @click="list.load()">刷新</el-button>
      </div>
      <el-alert v-if="list.data.value && (list.data.value.summary.state_unavailable || rows.some(row => row.parse_id) && !list.data.value.availability.review_ledger)"
        type="warning" :closable="false" title="部分业务状态暂不可用，待核实状态不会当作已审核或已发布。" />
      <div class="selection-actions"><el-button :disabled="!list.data.value?.total || selectionBusy" :loading="selectionBusy" @click="selectAllMatches">选择全部筛选结果（{{ list.data.value?.total || 0 }}）</el-button></div>
      <div v-if="selected.size || allSelected" class="selection-bar">
        <span>已选 {{ allSelected?.count ?? selected.size }} 份（{{ allSelected ? '全部匹配的固定范围' : '跨页保留' }}）</span>
        <el-button :loading="downloadBusy" @click="downloadSelected">下载选中原件</el-button>
        <el-button type="primary" plain :disabled="!prepareEnabled" @click="openPrepare()">批量确认归类并准备入库</el-button><el-button v-if="canBulkReview" @click="bulkReviewOpen=true">批量审核</el-button>
        <el-button @click="clearSelection">取消选择</el-button>
      </div>
      <AsyncPanel :state="list.state.value" :error="list.error.value" empty-text="当前条件下没有文件，可调整或清空筛选。" @retry="list.load()">
        <div class="table-wrap">
          <el-table ref="table" :data="rows" row-key="file_id" @selection-change="selectionChanged" @row-dblclick="openFile">
            <el-table-column type="selection" width="44" :selectable="() => !allSelected" />
            <el-table-column label="文件 / 资料名称" min-width="260">
              <template #default="{ row }"><button class="file-link" @click="openFile(row)">{{ row.title }}</button><div v-if="row.title !== row.file_name" class="secondary">{{ row.file_name }}</div><div v-if="row.child_document_count > 1" class="secondary">{{row.child_document_count}} 篇资料 · 已发布 {{row.published_document_count || 0}} 篇</div></template>
            </el-table-column>
            <el-table-column label="类别" width="110"><template #default="{ row }">{{ categoryLabel(row.category) }}</template></el-table-column>
            <el-table-column label="处理进度" width="130"><template #default="{ row }"><el-tag effect="plain">{{ stageLabels[row.stage] || '状态待核实' }}</el-tag></template></el-table-column>
            <el-table-column label="上传时间" width="170"><template #default="{ row }">{{ formatTime(row.uploaded_at) }}</template></el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }"><el-button text type="primary" @click="openFile(row)">查看</el-button><el-button v-if="row.stage === 'uploaded'" text type="primary" :disabled="!batchEnabled || actionBusy" @click="startParsing(row)">开始解析</el-button><el-button v-else-if="row.stage==='awaiting_classification'" text type="primary" :disabled="!prepareEnabled" @click="openPrepare(row)">确认资料</el-button><el-button v-else-if="row.stage==='awaiting_publish'" text type="primary" @click="router.push({path:'/knowledge/ingestion',query:{file:row.file_id}})">查看待发布资料</el-button><el-button v-else-if="row.parse_id" text @click="reviewFile(row)">查看审核</el-button></template>
            </el-table-column>
          </el-table>
        </div>
      </AsyncPanel>
      <el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" :page-sizes="[20,50,100]"
        :total="list.data.value?.total || 0" layout="total, sizes, prev, pager, next" background
        @current-change="changePage" @size-change="changeSize" />
    </el-card>
    <el-drawer v-model="drawer" title="文件查看" size="min(1080px, 96vw)" :close-on-click-modal="false">
      <template v-if="current">
        <div class="preview-toolbar"><strong>{{ current.title }}</strong><div><el-button :disabled="previewNavigating || currentIndex < 0 || currentIndex===0 && query.page<=1" @click="navigateFile(-1)">上一份</el-button><el-button :disabled="previewNavigating || currentIndex < 0 || currentIndex===rows.length-1 && query.page*query.page_size>=(list.data.value?.total || 0)" @click="navigateFile(1)">下一份</el-button></div></div>
        <p class="preview-stage">{{ stageLabels[current.stage] }} · {{ categoryLabel(current.category) }}</p>
        <div class="preview-actions">
          <el-button v-if="current.stage === 'uploaded'" type="primary" :disabled="!batchEnabled || actionBusy" @click="startParsing(current)">开始解析</el-button>
          <el-button v-if="current.stage === 'needs_attention'" :disabled="!batchEnabled || actionBusy" @click="startParsing(current,true)">重新解析并保留历史</el-button><el-button v-if="current.latest_task_id" @click="router.push({path:'/parsing',query:{task:current.latest_task_id}})">查看解析进度</el-button>
          <el-button v-if="current.parse_id" type="primary" plain @click="reviewFile(current)">查看与审核正文</el-button>
          <el-button :disabled="!prepareEnabled" @click="openPrepare(current)">确认归类并准备入库</el-button><el-button v-if="current.child_document_count" @click="router.push({path:'/knowledge/ingestion',query:{file:current.file_id}})">查看这份文件的全部资料</el-button>
        </div>
        <el-alert v-if="current.blocked_reason" type="warning" :closable="false"  :title="blockedHint(current.blocked_reason)" />
        <DocumentPreview :key="current.file_id" :file-id="current.file_id" :file-name="current.file_name" :expected-sha256="current.sha256" v-model:page="previewPage" />
        <el-collapse><el-collapse-item title="来源与处理标识" name="source"><p>文件标识：{{ current.file_id }}</p><p>解析标识：{{ current.parse_id || '尚未生成' }}</p><p>审核版本：{{ current.review_version ?? '尚未取得' }}</p></el-collapse-item></el-collapse>
      </template>
    </el-drawer>
    <ReviewBatchResults v-model="reviewResultsOpen" :batch-id="reviewBatch?.batch_id || ''" />
    <BulkReviewDialog v-model="bulkReviewOpen" :selected="[...selected.values()]" :snapshot="allSelected" @submitted="observeReviewBatch" />
    <PrepareDocumentsDialog v-model="prepareDialog" :target="prepareOne" :selected="[...selected.values()]" :snapshot="allSelected" @done="list.load()" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AsyncPanel from '@/components/AsyncPanel.vue'
import DocumentPreview from '@/components/document/DocumentPreview.vue'
import BatchUploadPanel from '@/components/workbench/BatchUploadPanel.vue'
import PrepareDocumentsDialog from '@/components/workbench/PrepareDocumentsDialog.vue'
import BulkReviewDialog from '@/components/workbench/BulkReviewDialog.vue'
import ReviewBatchResults from '@/components/workbench/ReviewBatchResults.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { contractState, hasRuntimeMethod } from '@/api/dataSource'
import { principal } from '@/api/principal'
import { downloadSourceFile } from '@/api/documentFiles'
import { notifyApiError } from '@/api/errors'
import { appendBatchFile, createFileBatch, listWorkbenchDocuments, stageLabels, type WorkbenchDocument, type WorkbenchPage, type WorkbenchQuery, selectMatchingFiles, selectionFiles, type SelectionSnapshot,type ReviewBatchStatus,reviewBatchStatus } from '@/api/workbench'

const route = useRoute(), router = useRouter()
const stages = ['processing', 'awaiting_review', 'awaiting_classification','ready_to_build', 'awaiting_publish', 'published', 'needs_attention']
function initialQuery(): WorkbenchQuery {
  return { page: Math.max(1, Number(route.query.page) || 1), page_size: [20,50,100].includes(Number(route.query.page_size)) ? Number(route.query.page_size) : 20,
    keyword: String(route.query.keyword || ''), stage: String(route.query.stage || ''), category: String(route.query.category || ''),
    doc_type: '', batch_id: String(route.query.batch_id || ''), date_from: String(route.query.date_from || ''), date_to: String(route.query.date_to || '') }
}
const query = ref<WorkbenchQuery>(initialQuery())
const draftKeyword = ref(query.value.keyword), draftCategory = ref(query.value.category)
const draftBatch=ref(query.value.batch_id)
const draftDates = ref<Date[] | null>(query.value.date_from && query.value.date_to ? [new Date(query.value.date_from), new Date(query.value.date_to)] : null)
const list = useAsyncData<WorkbenchPage>(signal => listWorkbenchDocuments(query.value, signal))
const rows = computed(() => list.data.value?.list || [])
let openedRouteFile=''
let restoredPosition=false
function positionKey(){return 'mrp-file-position:'+principal.value?.principal_id+':'+route.fullPath}
function rememberPosition(){const content=document.getElementById('main-content');if(content)sessionStorage.setItem(positionKey(),String(content.scrollTop))}
watch(()=>list.state.value,async state=>{
  if(restoredPosition || !['ready','empty'].includes(state))return
  restoredPosition=true;await nextTick()
  const top=Number(sessionStorage.getItem(positionKey()) || 0)
  if(top>0)document.getElementById('main-content')?.scrollTo({top,behavior:'instant' as ScrollBehavior})
})
onBeforeUnmount(rememberPosition)
watch(rows, currentRows => {
  const file=String(route.query.file || '')
  if(file && file!==openedRouteFile) {
    const row=currentRows.find(row=>row.file_id===file)
    if(row) { openedRouteFile=file; nextTick(()=>openFile(row)) }
  }
})
const batchEnabled = computed(() => contractState.value === 'ready' &&
  hasRuntimeMethod('POST','/api/workbench/batches') && hasRuntimeMethod('POST','/api/workbench/batches/{batch_id}/files'))
const selected = ref(new Map<string,WorkbenchDocument>())
const table = ref<{toggleRowSelection:(row:WorkbenchDocument,selected:boolean)=>void;clearSelection:()=>void}>()
const allSelected=ref<SelectionSnapshot|null>(null), selectionBusy=ref(false)
function clearSelection() { selected.value=new Map(); allSelected.value=null; table.value?.clearSelection() }
async function selectAllMatches() {
  selectionBusy.value=true
  try {
    const snapshot=await selectMatchingFiles(query.value,crypto.randomUUID())
    selected.value=new Map(); allSelected.value=snapshot; table.value?.clearSelection()
    ElMessage.success(`已固定选择 ${snapshot.count} 份文件，后续新增文件不包含在此次选择中`)
  } catch(error) { notifyApiError(error,'无法选择全部匹配文件') }
  finally { selectionBusy.value=false }
}
let syncingSelection = false
watch(rows, async currentRows => {
  syncingSelection = true
  await nextTick()
  table.value?.clearSelection()
  currentRows.forEach(row => { if(selected.value.has(row.file_id)) table.value?.toggleRowSelection(row,true) })
  syncingSelection = false
})
function selectionChanged(selection: WorkbenchDocument[]) {
  if(syncingSelection || allSelected.value || list.loading.value) return
  const next = new Map(selected.value)
  rows.value.forEach(row => next.delete(row.file_id))
  selection.forEach(row => next.set(row.file_id,row))
  selected.value = next
}
async function confirmFilterChange() {
  if(!selected.value.size && !allSelected.value) return true
  try { await ElMessageBox.confirm('改变筛选会清空跨页选择，是否继续？','确认筛选范围',{type:'warning'}); clearSelection(); return true }
  catch { return false }
}
function rememberQuery() {
  void router.replace({ query: Object.fromEntries(Object.entries(query.value).filter(([,v]) => v !== '')) })
}
async function applyFilters() {
  if(!await confirmFilterChange()) return
  const dates = draftDates.value
  const end = dates?.[1] ? new Date(dates[1]) : null
  end?.setHours(23,59,59,999)
  query.value = {...query.value,page:1,keyword:draftKeyword.value.trim(),category:draftCategory.value,batch_id:draftBatch.value,
    date_from:dates?.[0]?.toISOString() || '',date_to:end?.toISOString() || ''}
  rememberQuery(); await list.load()
}
async function resetFilters() {
  if(!await confirmFilterChange()) return
  draftKeyword.value=''; draftCategory.value=''; draftBatch.value=''; draftDates.value=null
  query.value={...query.value,page:1,keyword:'',category:'',stage:'',batch_id:'',date_from:'',date_to:''}
  rememberQuery(); await list.load()
}
async function changeStage(stage:string) {
  if(!await confirmFilterChange()) return
  query.value.stage=stage; query.value.page=1; rememberQuery(); await list.load()
}
function changePage() { rememberQuery(); void list.load() }
function changeSize() { query.value.page=1; rememberQuery(); void list.load() }
const savedKey = computed(() => `mrp-file-filters:${principal.value?.principal_id || 'unconfirmed'}`)
const hasSavedFilter = ref(false)
watch(savedKey, key => { hasSavedFilter.value=!!localStorage.getItem(key); clearSelection() },{immediate:true})
function saveFilter() {
  if(!principal.value) return
  localStorage.setItem(savedKey.value,JSON.stringify({...query.value,page:1}))
  hasSavedFilter.value=true; ElMessage.success('常用筛选已保存到本机')
}
async function restoreFilter() {
  if(!await confirmFilterChange()) return
  try {
    const saved=JSON.parse(localStorage.getItem(savedKey.value) || 'null')
    if(!saved || typeof saved.keyword!=='string') return
    query.value={...initialQuery(),...saved,page:1}
    draftKeyword.value=query.value.keyword; draftCategory.value=query.value.category; draftBatch.value=query.value.batch_id
    draftDates.value=query.value.date_from && query.value.date_to ? [new Date(query.value.date_from),new Date(query.value.date_to)] : null
    rememberQuery(); await list.load()
  } catch { ElMessage.warning('保存的筛选无法读取，请重新设置') }
}
const drawer=ref(false), current=ref<WorkbenchDocument|null>(null), previewPage=ref(1)
const currentIndex=computed(() => rows.value.findIndex(row => row.file_id===current.value?.file_id))
function openFile(row?:WorkbenchDocument) { if(!row)return; current.value=row; previewPage.value=1; drawer.value=true }
const previewNavigating=ref(false)
async function navigateFile(direction:number){
  if(previewNavigating.value)return
  const next=currentIndex.value+direction
  if(next>=0 && next<rows.value.length){openFile(rows.value[next]);return}
  previewNavigating.value=true
  try{
    query.value.page+=direction;rememberQuery();await list.load()
    if(rows.value.length)openFile(direction>0?rows.value[0]:rows.value[rows.value.length-1])
    else ElMessage.warning('下一页暂未能读取，当前文件仍保留')
  }finally{previewNavigating.value=false}
}
function reviewFile(row:WorkbenchDocument) { rememberPosition();if(row.parse_id) void router.push({path:'/review',query:{parse:row.parse_id,return_to:route.fullPath}}) }
function categoryLabel(value:string) { return ({law:'法规',case:'处罚案例',unconfirmed:'归类待确认'} as Record<string,string>)[value] || '全部类别' }
function blockedHint(code:string){
  return ({source_scope_confirmation_required:'这份文件可能包含多篇资料，请确认拆分范围',reviewed_revision_export_required:'历史修订需要按整页正文重新确认',
    source_scope_changed:'正文已变化，请重新确认拆分范围',library_reviewed_text_schema_upgrade_required:'审核正文的数据库支持尚未启用，请联系管理员',
    source_owner_unresolved:'历史文件归属暂无法核实，请联系管理员',ingestion_quality_blocked:'正文或表格未通过完整性检查，请核对原件后处理',
    review_source_changed:'解析结果已变化，需要重新核对和审核'} as Record<string,string>)[code] || '资料尚未通过入库检查，请核对原件、正文和审核状态'
}
function formatTime(value:string) { return new Date(value).toLocaleString() }
const bulkReviewOpen=ref(false),reviewResultsOpen=ref(false),reviewBatch=ref<ReviewBatchStatus|null>(null)
const canBulkReview=computed(()=>hasRuntimeMethod('POST','/api/workbench/review-batches') &&
  principal.value?.roles.some(role=>role==='ADMIN' || role==='REVIEWER'))
let reviewPoll:ReturnType<typeof setTimeout>|undefined
async function observeReviewBatch(value:ReviewBatchStatus){
  clearTimeout(reviewPoll);reviewBatch.value=value
  if(principal.value)sessionStorage.setItem('mrp-review-batch:'+principal.value.principal_id,value.batch_id)
  if(!value.counts.queued && !value.counts.running){await list.load();return}
  reviewPoll=setTimeout(async()=>{
    try{await observeReviewBatch(await reviewBatchStatus(value.batch_id))}
    catch(error){notifyApiError(error,'审核进度暂时无法读取，请刷新核对')}
  },1500)
}
onBeforeUnmount(()=>clearTimeout(reviewPoll))
const prepareEnabled=computed(()=>contractState.value==='ready' && hasRuntimeMethod('POST','/api/workbench/documents/{file_id}/prepare'))
const prepareDialog=ref(false),prepareOne=ref<WorkbenchDocument|null>(null)
function openPrepare(row?:WorkbenchDocument) {prepareOne.value=row || null;prepareDialog.value=true}
const authScopeKey=computed(()=>principal.value?JSON.stringify([principal.value.principal_id,principal.value.roles,principal.value.review_owner_scopes,principal.value.credential_status]):'')
watch(authScopeKey,(next,previous)=>{
  if(previous && next!==previous){list.cancel();list.data.value=null;selected.value=new Map();allSelected.value=null;drawer.value=false;prepareDialog.value=false;bulkReviewOpen.value=false;reviewResultsOpen.value=false;clearTimeout(reviewPoll);reviewBatch.value=null;if(next)void list.load()}
  if(principal.value){
    const id=sessionStorage.getItem('mrp-review-batch:'+principal.value.principal_id)
    if(id && /^[a-f0-9]{64}$/.test(id))void reviewBatchStatus(id).then(observeReviewBatch).catch(()=>{})
  }
},{immediate:true})
const actionBusy=ref(false), downloadBusy=ref(false)
async function startParsing(row:WorkbenchDocument,retry=false) {
  if(retry){try{await ElMessageBox.confirm('将创建新的解析结果，保留原文件和历史结果；完成后需要重新审核。','确认重新解析')}catch{return}}
  if(actionBusy.value)return
  actionBusy.value=true
  try {
    const batch=await createFileBatch(`解析：${row.file_name}`,retry?crypto.randomUUID():`initial-parse-${row.file_id}`)
    await appendBatchFile(batch.operation_id,row.file_id,row.file_name)
    ElMessage.success('已加入后台解析队列'); await list.load()
  } catch(error) { notifyApiError(error,'提交解析失败') }
  finally { actionBusy.value=false }
}
async function downloadSelected() {
  if(downloadBusy.value)return
  downloadBusy.value=true
  let succeeded=0
  try {
    if(allSelected.value) {
      const snapshot=allSelected.value
      await ElMessageBox.confirm(`将下载此次固定选择的 ${snapshot.count} 份原件，是否继续？`,'确认批量下载')
      for(let page=1;page<=Math.ceil(snapshot.count/100);page++) {
        const result=await selectionFiles(snapshot.selection_id,page)
        for(const row of result.list) { await downloadSourceFile(row.file_id,row.file_name); succeeded++ }
      }
    } else {
      for(const row of selected.value.values()) { await downloadSourceFile(row.file_id,row.file_name); succeeded++ }
    }
    ElMessage.success(`已下载 ${succeeded} 份原件`)
  } catch(error) { notifyApiError(error,`已下载 ${succeeded} 份，其余下载未完成`) }
  finally { downloadBusy.value=false }
}
let refreshTimer:ReturnType<typeof setTimeout>|undefined
function scheduleRefresh() { clearTimeout(refreshTimer); refreshTimer=setTimeout(() => { void list.load() },500) }
let disposed=false,quietLoading=false
const statusPoll=setInterval(async()=>{
  if(disposed || quietLoading || document.hidden || list.loading.value || !list.data.value || !['ready','empty'].includes(list.state.value) || !principal.value)return
  const active=['processing','ready_to_build','awaiting_review','awaiting_classification']
  if(!active.some(stage=>list.data.value?.summary[stage]))return
  const signature=JSON.stringify(query.value),scope=authScopeKey.value
  quietLoading=true
  try{
    const result=await listWorkbenchDocuments({...query.value})
    if(!disposed && !list.loading.value && signature===JSON.stringify(query.value) && scope===authScopeKey.value){
      list.data.value=result;list.state.value=result.list.length?'ready':'empty'
      if(current.value){const fresh=result.list.find(row=>row.file_id===current.value?.file_id);if(fresh)current.value=fresh}
    }
  }catch{/* 保留最后一次成功结果，手动刷新仍呈现真实错误。 */}
  finally{quietLoading=false}
},5000)
onBeforeUnmount(() => {disposed=true;clearTimeout(refreshTimer);clearInterval(statusPoll)})
</script>

<style scoped>
.files-card { margin-top:16px; }
.stage-filters,.file-filters,.selection-bar,.applied-filters,.preview-toolbar,.preview-actions { display:flex;align-items:center;gap:12px;flex-wrap:wrap; }
.stage-filters { margin-bottom:16px; }
.stage-filters :deep(.el-button+.el-button) { margin-left:0; }
.file-filters { padding:16px 0; border-top:1px solid var(--mr-line); }
.file-filters>.el-input { width:300px; }
.file-filters>.el-select { width:160px; }
.file-filters :deep(.el-date-editor) { max-width:100%; }
.applied-filters { justify-content:space-between;color:var(--mr-text-secondary);font-size:13px; }
.selection-bar { padding:12px;background:var(--mr-bg);margin:12px 0; }
.file-link { padding:0;border:0;background:transparent;text-align:left;color:var(--mr-primary);cursor:pointer;font:inherit;overflow-wrap:anywhere; }
.secondary { color:var(--mr-text-secondary);font-size:12px;margin-top:4px; }
.table-wrap { overflow:auto; }
.el-pagination { margin-top:16px;max-width:100%;overflow:auto; }
.preview-toolbar { justify-content:space-between; }
.preview-toolbar>strong { overflow-wrap:anywhere; }
.preview-stage { color:var(--mr-text-secondary); }
.preview-actions { margin-bottom:16px; }
:deep(.dp) { min-height:480px; }
@media(max-width:600px) {
  .file-filters>.el-input,.file-filters>.el-select { width:100%; }
  .file-filters :deep(.el-date-editor) { width:100%; }
  .stage-filters { gap:8px; flex-wrap:nowrap; overflow:auto; padding-bottom:4px; }
  .stage-filters :deep(.el-button) { flex-shrink:0; }
  :deep(.el-card__body) { padding:12px; }
}
</style>
