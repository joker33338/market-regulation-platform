<template>
  <div class="page">
    <header class="page-header"><div><h1 class="page-title">入库与发布</h1><p class="page-desc">审核通过的资料自动准备入库；核对待发布清单后确认发布。</p></div><el-button @click="router.push('/documents')">返回文件工作台</el-button></header>
    <el-alert type="info" :closable="false" title="审核通过后仍保留发布确认。已准备的候选不会自动对外生效。" />
    <el-card shadow="never" class="jobs-card">
      <div class="jobs-toolbar"><h2>资料处理记录</h2><div><el-button type="primary" :disabled="!isAdminIdentity || publishing" @click="prepareBatch(true)">准备全部待发布资料</el-button><el-button v-if="selected.size" :disabled="!isAdminIdentity || publishing" @click="prepareBatch(false)">准备选中的 {{selected.size}} 份</el-button></div><el-button :loading="jobs.loading.value" @click="jobs.load()">刷新</el-button></div>
      <AsyncPanel :state="jobs.state.value" :error="jobs.error.value" empty-text="尚无入库准备记录。请在文件工作台确认资料类别和名称，系统将等待审核并自动构建候选。" @retry="jobs.load()">
        <div class="jobs-table"><el-table ref="jobTable" :data="jobs.data.value?.list || []" row-key="job_id" @selection-change="selectionChanged"><el-table-column type="selection" width="44" :selectable="(row:KnowledgeJob)=>row.status==='awaiting_publish'" />
          <el-table-column label="资料名称" min-width="240"><template #default="{row}"><strong>{{row.title}}</strong></template></el-table-column>
          <el-table-column label="目标库" width="120"><template #default="{row}">{{row.document_type==='case'?'处罚案例库':'法规库'}}</template></el-table-column>
          <el-table-column label="当前步骤" width="160"><template #default="{row}">{{jobLabels[row.status] || '状态待核实'}}</template></el-table-column>
          <el-table-column label="处理提示" min-width="200"><template #default="{row}">{{jobHint(row)}}</template></el-table-column>
          <el-table-column label="操作" width="200" fixed="right"><template #default="{row}">
            <el-button text @click="openFile(row)">查看文件</el-button>
            <el-button v-if="row.status==='awaiting_publish'" text type="primary" :disabled="!isAdminIdentity || publishing" @click="prepareBatch(false,row.job_id)">确认发布</el-button>
            <el-button v-if="row.status==='published'" text type="primary" @click="router.push({path:row.document_type==='case'?'/library/cases':'/library/laws',query:{kb_version:row.published_version || row.kb_version}})">查看发布结果</el-button>
          </template></el-table-column>
        </el-table></div>
      </AsyncPanel>
      <el-pagination v-model:current-page="page" :total="jobs.data.value?.total || 0" :page-size="20" layout="total, prev, pager, next" @current-change="jobs.load()" />
    </el-card>
    <el-dialog v-model="releaseDialog" title="确认本次发布清单" width="min(760px, 94vw)" :close-on-click-modal="false">
      <template v-if="manifest">
        <p>本次 {{manifest.document_count}} 份资料：法规 {{manifest.category_counts.law || 0}} 份，处罚案例 {{manifest.category_counts.case || 0}} 份。</p>
        <p>仅发布下列清单中的资料，原有已发布内容继续保留。其他待审核、失败或之后完成的资料不会自动加入。</p>
        <el-table :data="manifestRows" max-height="320"><el-table-column prop="title" label="资料名称" min-width="240"/><el-table-column label="目标库" width="120"><template #default="{row}">{{row.document_type==='case'?'处罚案例库':'法规库'}}</template></el-table-column></el-table>
        <el-pagination v-model:current-page="manifestPage" :total="manifest.document_count" :page-size="20" layout="total, prev, pager, next" @current-change="loadManifestPage" />
      </template>
      <template #footer><el-button :disabled="publishing" @click="releaseDialog=false">暂不发布</el-button><el-button type="primary" :loading="publishing" @click="publishBatch">确认发布这份清单</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { isAdminIdentity, principal } from '@/api/principal'
import { listKnowledgeJobs, jobLabels, type KnowledgeJob, type KnowledgeJobPage,createReleaseManifest,appendReleaseItems,prepareReleaseManifest,checkReleaseManifest,publishReleaseManifest,type ReleaseManifest,releaseManifestItems } from '@/api/workbench'
import { notifyApiError } from '@/api/errors'
const route=useRoute(),router=useRouter(),page=ref(1),publishing=ref(false)
const jobs=useAsyncData<KnowledgeJobPage>(signal=>listKnowledgeJobs(page.value,signal,String(route.query.file || '')))
const selected=ref(new Map<string,KnowledgeJob>()),manifest=ref<ReleaseManifest|null>(null),releaseDialog=ref(false)
const jobTable=ref<{clearSelection:()=>void;toggleRowSelection:(row:KnowledgeJob,value:boolean)=>void}>()
let selectionSync=false
watch(()=>jobs.data.value?.list,async rows=>{
  selectionSync=true;await nextTick();jobTable.value?.clearSelection()
  ;(rows || []).forEach(row=>{if(selected.value.has(row.job_id))jobTable.value?.toggleRowSelection(row,true)})
  selectionSync=false
})
function selectionChanged(rows:KnowledgeJob[]) {
  if(selectionSync || jobs.loading.value)return
  const value=new Map(selected.value)
  ;(jobs.data.value?.list || []).forEach(row=>value.delete(row.job_id))
  rows.forEach(row=>value.set(row.job_id,row))
  selected.value=value
}
async function prepareBatch(allReady:boolean,singleId?:string) {
  if(publishing.value)return
  publishing.value=true
  try {
    const ids=singleId?[singleId]:allReady?[]:[...selected.value.keys()]
    let result=await createReleaseManifest(ids.slice(0,100),crypto.randomUUID(),allReady)
    for(let offset=100;offset<ids.length;offset+=100)result=await appendReleaseItems(result.release_id,ids.slice(offset,offset+100))
    if(!result.document_count){ElMessage.info('当前没有符合条件的待发布资料');return}
    manifest.value=await prepareReleaseManifest(result.release_id)
    manifestRows.value=manifest.value.documents;manifestPage.value=1
    releaseKey=crypto.randomUUID()
    releaseDialog.value=true
  } catch(error){notifyApiError(error,'发布清单准备未完成，原有发布版本保持不变')}
  finally{publishing.value=false}
}
const manifestRows=ref<ReleaseManifest['documents']>([]),manifestPage=ref(1)
async function loadManifestPage() {
  if(!manifest.value)return
  try{manifestRows.value=(await releaseManifestItems(manifest.value.release_id,manifestPage.value)).list}
  catch(error){notifyApiError(error,'清单分页读取失败')}
}
let disposed=false,quietLoading=false
watch(()=>[principal.value?.principal_id,route.query.file],()=>{jobs.cancel();jobs.data.value=null;selected.value=new Map();manifest.value=null;releaseDialog.value=false;page.value=1;void jobs.load()})
const statusPoll=setInterval(async()=>{
  if(disposed || quietLoading || document.hidden || jobs.loading.value || !jobs.data.value || !['ready','empty'].includes(jobs.state.value))return
  if(!jobs.data.value.list.some(row=>['queued','awaiting_parse','awaiting_review','awaiting_admin','building'].includes(row.status)))return
  const currentPage=page.value,file=String(route.query.file || ''),identity=principal.value?.principal_id
  quietLoading=true
  try{
    const result=await listKnowledgeJobs(currentPage,undefined,file)
    if(!disposed && !jobs.loading.value && page.value===currentPage && String(route.query.file || '')===file && principal.value?.principal_id===identity){jobs.data.value=result;jobs.state.value=result.list.length?'ready':'empty'}
  }catch{/* 后台刷新失败不清除已有记录；刷新按钮可重新核对。 */}
  finally{quietLoading=false}
},5000)
onBeforeUnmount(()=>{disposed=true;clearInterval(statusPoll)})
let releaseKey=''
async function publishBatch() {
  if(publishing.value || !manifest.value)return
  publishing.value=true
  try {
    const check=await checkReleaseManifest(manifest.value.release_id)
    if(!check.publish_eligible){ElMessage.warning('当前发布版本已变化，请重新准备清单');return}
    const result=await publishReleaseManifest(manifest.value.release_id,manifest.value.expected_active_version,releaseKey)
    if(result.status!=='published')throw new Error('发布状态未确认')
    releaseDialog.value=false;selected.value=new Map();jobTable.value?.clearSelection()
    ElMessage.success(`本次 ${result.document_count} 份资料已发布`)
    await jobs.load()
  } catch(error){notifyApiError(error,'发布未完成，请核对结果后重试')}
  finally{publishing.value=false}
}
function openFile(row:KnowledgeJob) { void router.push({path:'/documents',query:{keyword:row.title,file:row.file_id}}) }
function jobHint(row:KnowledgeJob) {
  if(row.status==='awaiting_review')return '等待人工审核，审核通过后自动继续'
  if(row.status==='awaiting_parse')return '等待这份文件的完整解析结果'
  if(row.status==='awaiting_admin')return '等待管理员确认并接手入库'
  if(row.status==='awaiting_publish')return '候选已准备，等待管理员确认发布'
  if(row.status==='published')return '已有成功发布记录，实际当前版本以库中查询为准'
  if(row.error_code==='reviewed_revision_export_required')return '旧修订含义不明，请按整页正文重新确认后审核'
  if(row.error_code)return '处理被门禁阻断，请查看文件核对来源、审核和质量问题'
  return '系统将在后台继续处理'
}

</script>
<style scoped>
.jobs-card { margin-top:16px; }.jobs-toolbar { flex-wrap:wrap;gap:12px;display:flex;justify-content:space-between;align-items:center;margin-bottom:16px; }
h2 { margin:0;font-size:16px; }.jobs-table { overflow:auto; }.el-pagination { margin-top:16px;max-width:100%;overflow:auto; }
@media(max-width:600px){.jobs-toolbar>div{display:flex;flex-wrap:wrap;gap:8px}.jobs-toolbar :deep(.el-button+.el-button){margin-left:0}}
</style>
