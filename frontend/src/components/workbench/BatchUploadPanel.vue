<template>
  <el-card shadow="never">
    <div class="upload-heading">
      <div><h2>添加文件</h2><p>支持文件和文件夹；上传完成的文件自动排队解析，整批数量不设固定上限。</p></div>
      <div class="upload-actions">
        <el-button :disabled="busy || !enabled" @click="filesInput?.click()">选择文件</el-button>
        <el-button :disabled="busy || !enabled" @click="folderInput?.click()">选择文件夹</el-button>
      </div>
    </div>
    <input ref="filesInput" hidden type="file" multiple :accept="accept" @change="choose" />
    <input ref="folderInput" hidden type="file" multiple webkitdirectory @change="choose" />
    <div v-if="items.length" class="upload-content">
      <el-input v-model="batchName" aria-label="批次名称" placeholder="批次名称，便于后续查找" :disabled="busy || !!batch" />
      <el-select v-model="category" aria-label="整批资料类别" :disabled="busy || !!batch"><el-option label="稍后逐份确认类别" value=""/><el-option label="整批确认为法规" value="law"/><el-option label="整批确认为处罚案例" value="case"/></el-select>
      <p v-if="category">本批沿用文件名作为资料名称；解析发现多篇资料时仍会停下，要求核对拆分范围。审核和发布仍需确认。</p>
      <p role="status">已选择 {{ items.length }} 份 · 已提交 {{ submitted }} 份 · 需处理 {{ failed }} 份</p>
      <div class="upload-files">
        <div v-for="(item,index) in items" :key="index" class="upload-row">
          <span :title="item.relativePath">{{ item.relativePath }}</span>
          <span>{{ item.message || '待上传' }}</span>
          <el-progress v-if="item.state === 'uploading'" :percentage="item.percent" :show-text="false" />
        </div>
      </div>
      <div class="upload-actions">
        <el-button type="primary" :disabled="!enabled || !pendingCount" :loading="busy" @click="start">上传并开始处理（{{ pendingCount }}）</el-button>
        <el-button :disabled="busy" @click="clear">重新选择</el-button>
      </div>
    </div>
    <p v-if="!enabled" class="upload-note">当前服务尚未启用新版批量处理。文件上传入口暂不可用，请等待服务更新。</p>
    <p v-if="busy" class="upload-note">正在上传，请保持页面打开；已提交的后台解析任务不受关闭页面影响。</p>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadFile, UPLOAD_ALLOWED_EXT, UPLOAD_LIMIT_BYTES } from '@/api/parse'
import { appendBatchFile, createFileBatch, prepareKnowledgeFile, type FileBatch } from '@/api/workbench'
import { notifyApiError } from '@/api/errors'

defineProps<{ enabled: boolean }>()
const emit = defineEmits<{ (e: 'submitted'): void }>()
interface UploadItem {
  file: File; relativePath: string; state: 'pending' | 'uploading' | 'submitted' | 'failed' | 'unsupported' | 'duplicate'
  percent: number; message: string; fileId?: string; hash?: string
}
const accept = UPLOAD_ALLOWED_EXT.join(',')
const filesInput = ref<HTMLInputElement>()
const folderInput = ref<HTMLInputElement>()
const items = ref<UploadItem[]>([])
const batchName = ref('')
const category=ref<''|'law'|'case'>('')
const batch = ref<FileBatch | null>(null)
const busy = ref(false)
const key = ref(crypto.randomUUID())
const controller = new AbortController()
onBeforeUnmount(() => controller.abort())
const submitted = computed(() => items.value.filter(i => i.state === 'submitted').length)
const failed = computed(() => items.value.filter(i => ['failed', 'unsupported'].includes(i.state)).length)
const pendingCount = computed(() => items.value.filter(i => ['pending', 'failed'].includes(i.state)).length)
function choose(event: Event) {
  const input = event.target as HTMLInputElement
  const chosen = Array.from(input.files || [])
  items.value = chosen.map(file => {
    const allowed = UPLOAD_ALLOWED_EXT.some(ext => file.name.toLowerCase().endsWith(ext))
    const valid = allowed && file.size > 0 && file.size <= UPLOAD_LIMIT_BYTES && (file.webkitRelativePath || file.name).length<=1024
    return { file, relativePath: file.webkitRelativePath || file.name,
      state: valid ? 'pending' : 'unsupported', percent: 0,
      message: valid ? '' : allowed ? '文件为空、超过单文件大小限制或目录名称过长' : '格式不支持' }
  })
  batchName.value = chosen[0]?.webkitRelativePath.split('/')[0] || `文件批次 ${new Date().toLocaleString()}`
  batch.value = null
  key.value = crypto.randomUUID()
  input.value = ''
}
function clear() { items.value = []; batch.value = null; key.value = crypto.randomUUID() }
async function start() {
  if (busy.value) return
  busy.value = true
  try {
    if (!batch.value) batch.value = await createFileBatch(batchName.value.trim() || '文件批次', key.value)
    const pending = items.value.filter(i => ['pending', 'failed'].includes(i.state))
    const seen = new Set(items.value.filter(i => i.state === 'submitted' && i.hash).map(i => i.hash!))
    let next = 0
    async function run() {
      while (next < pending.length && !controller.signal.aborted) {
        const item = pending[next++]
        item.state = 'uploading'
        item.message = '上传中'
        try {
          if (!item.hash) {
            const digest = await crypto.subtle.digest('SHA-256', await item.file.arrayBuffer())
            item.hash = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('')
          }
          if (seen.has(item.hash) && !item.fileId) {
            item.state = 'duplicate'; item.message = '本批内容重复，已跳过'; continue
          }
          seen.add(item.hash)
          if (!item.fileId) {
            const result = await uploadFile(item.file, percent => { item.percent = percent }, controller.signal)
            item.fileId = result.file_id
          }
          const registered=await appendBatchFile(batch.value!.operation_id, item.fileId, item.relativePath)
          const accepted=registered.files.find(file=>file.file_id===item.fileId)
          item.state=accepted?.status==='duplicate'?'duplicate':'submitted'
          item.message=accepted?.status==='duplicate'?'内容重复，后台未重复解析':'已提交后台处理'
          if(category.value && item.state==='submitted'){
            try{await prepareKnowledgeFile({file_id:item.fileId,sha256:item.hash!,parse_id:null},item.file.name.replace(/\.[^.]+$/,''),category.value,'upload-prepare-'+item.fileId)
              item.message='已排队解析，并保存资料归类确认'}
            catch{item.message='已排队解析；归类确认未保存，请在工作台确认'}
          }
          emit('submitted')
        } catch {
          seen.delete(item.hash || '')
          item.state = 'failed'; item.message = item.fileId ? '上传已完成，提交结果待确认；可重试' : '上传失败，可重试'
        }
      }
    }
    await Promise.all([run(), run()])
    if (!controller.signal.aborted) ElMessage.info('本批上传已结束，请查看已提交与需处理数量')
  } catch (error) { notifyApiError(error, '无法创建处理批次') }
  finally { busy.value = false }
}
</script>

<style scoped>
.upload-heading,.upload-actions { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
h2 { margin:0; font-size:16px; color:var(--mr-text); }
p { font-size:13px; color:var(--mr-text-secondary); line-height:1.6; }
.upload-content { display:grid; gap:12px; margin-top:16px; }
.upload-content>.el-input { max-width:400px; }
.upload-content p { margin:0; }
.upload-files { max-height:240px; overflow:auto; border:1px solid var(--mr-line); border-radius:4px; }
.upload-row { display:grid; grid-template-columns:minmax(0,1fr) auto; padding:8px 12px; gap:8px; border-bottom:1px solid var(--mr-line); font-size:13px; }
.upload-row>span:first-child { overflow-wrap:anywhere; }
.upload-row :deep(.el-progress) { grid-column:1/-1; }
.upload-note { margin-bottom:0; }
@media(max-width:600px) { .upload-row { grid-template-columns:minmax(0,1fr); } .upload-actions { width:100%; } }
</style>
