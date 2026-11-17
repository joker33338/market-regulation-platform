<template>
  <el-dialog :model-value="modelValue" title="确认资料信息与入库范围" width="min(960px, 96vw)" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @update:model-value="emit('update:modelValue',$event)">
    <p>本次 {{target ? 1 : snapshot?.count ?? selected.length}} 份原文件。审核通过后自动准备候选，发布仍需确认。</p>
    <el-alert v-if="suggestionError" type="warning" :closable="false" :title="suggestionError" />
    <el-alert v-if="failedNames.length" type="warning" :closable="false" :title="'尚未提交 '+failedNames.length+' 条，成功项已保留；再次提交仅重试未成功项。'"><ul><li v-for="name in failedNames" :key="name">{{name}}</li></ul></el-alert>
    <div v-loading="suggesting">
      <el-form label-position="top" :disabled="busy">
        <el-form-item v-if="target && suggestions?.segments.length" label="如何整理这份文件">
          <el-radio-group v-model="mode"><el-radio-button label="split">按篇分别入库</el-radio-button><el-radio-button label="whole">整份作为一条资料</el-radio-button></el-radio-group>
        </el-form-item>
        <template v-if="mode==='whole'">
          <el-form-item label="资料类别（请核对）"><el-select v-model="kind" placeholder="请选择法规或处罚案例" aria-label="确认资料类别"><el-option label="法规" value="law"/><el-option label="处罚案例" value="case"/></el-select></el-form-item>
          <el-form-item v-if="target" label="资料名称"><el-input v-model="title" maxlength="256" aria-label="资料名称"/></el-form-item>
          <p v-else>批量沿用各文件当前显示的名称；发现多篇资料时会停下，要求逐份确认拆分。</p>
        </template>
        <template v-else>
          <el-alert type="warning" :closable="false" title="标题与边界仅为建议。请核对目录页、引文及每篇正文，确认后才生成条目。" />
          <div v-for="(part,index) in parts" :key="index" class="part-row">
            <el-checkbox v-model="part.selected" :aria-label="'选择第'+(index+1)+'篇'" />
            <el-input v-model="part.title" :aria-label="'第'+(index+1)+'篇标题'" maxlength="256"/>
            <el-select v-model="part.document_type" :aria-label="'第'+(index+1)+'篇类别'"><el-option label="法规" value="law"/><el-option label="处罚案例" value="case"/></el-select>
            <span class="part-range">第 {{part.page_start}}–{{part.page_end}} 页</span><el-button :type="editing===index?'primary':'default'" @click="editing=index">调整范围</el-button>
          </div>
          <div class="range-actions"><el-button @click="addPart">增加一篇</el-button><el-button :disabled="editing<0" @mousedown.prevent @click="useSelectedText">用下方选中文字设定第 {{editing+1}} 篇范围</el-button></div>
          <div v-if="editing>=0" class="range-actions"><el-button @mousedown.prevent @click="useSelectedText('start')">用选中文字设置起点</el-button><el-button @mousedown.prevent @click="useSelectedText('end')">用选中文字设置终点</el-button><span>可翻到其他正文段继续设置另一端；范围含起点至终点间的全部正文。</span></div>
        </template>
      </el-form>
      <el-tabs v-if="target && suggestions" v-model="previewTab">
        <el-tab-pane label="识别正文与范围核对" name="text">
          <p v-if="mode==='split'">先点击“调整范围”，再选中该篇完整文字，并点击“用选中文字设定范围”。</p>
          <div class="range-actions"><el-button :disabled="!suggestions.text_start" @click="moveText(-1)">上一段正文</el-button><span>第 {{Math.floor(suggestions.text_start/20000)+1}} / {{Math.max(1,Math.ceil(suggestions.total_characters/20000))}} 段</span><el-button :disabled="suggestions.text_start+20000>=suggestions.total_characters" @click="moveText(1)">下一段正文</el-button></div>
          <pre ref="sourceElement" class="scope-text" tabindex="0">{{suggestions.source_text}}</pre>
        </el-tab-pane>
        <el-tab-pane label="原文件对照" name="original"><DocumentPreview :file-id="target.file_id" :file-name="target.file_name" :expected-sha256="target.sha256" v-model:page="originalPage"/></el-tab-pane>
      </el-tabs>
      <el-button v-if="target && suggestions && !suggestions.segments.length && mode==='whole'" text @click="startManualSplit">这份文件有多篇资料，手动设置范围</el-button>
    </div>
    <template #footer><el-button :disabled="busy" @click="emit('update:modelValue',false)">取消</el-button><el-button type="primary" :disabled="!valid || suggesting" :loading="busy" @click="submit">确认并交给后台处理</el-button></template>
  </el-dialog>
</template>
<script setup lang="ts">
import { computed,ref,watch } from 'vue'
import { ElMessage } from 'element-plus'
import DocumentPreview from '@/components/document/DocumentPreview.vue'
import { fileSuggestions,prepareKnowledgeFile,selectionFiles,type SourceSuggestion,type SourceSegment,type SelectionSnapshot,type WorkbenchDocument } from '@/api/workbench'
import { notifyApiError, toApiError } from '@/api/errors'
const props=defineProps<{modelValue:boolean;target:WorkbenchDocument|null;selected:WorkbenchDocument[];snapshot:SelectionSnapshot|null}>()
const emit=defineEmits<{(e:'update:modelValue',value:boolean):void;(e:'done'):void}>()
const title=ref(''),kind=ref<''|'law'|'case'>(''),mode=ref<'whole'|'split'>('whole'),suggesting=ref(false),busy=ref(false)
const suggestions=ref<SourceSuggestion|null>(null),suggestionError=ref(''),parts=ref<(SourceSegment&{selected:boolean})[]>([])
const editing=ref(-1),sourceElement=ref<HTMLElement>(),previewTab=ref('text'),originalPage=ref(1)
let generation=0
const keys=new Map<string,string>()
const completed=new Set<string>(),failedNames=ref<string[]>([])
watch(()=>props.modelValue,async open=>{
  const current=++generation
  suggesting.value=false
  if(!open)return
  failedNames.value=[]
  title.value=props.target?.title || ''
  kind.value=props.target?.category==='law' || props.target?.category==='case'?props.target.category:''
  mode.value='whole';suggestions.value=null;parts.value=[];editing.value=-1;suggestionError.value='';previewTab.value='text';originalPage.value=1
  if(!props.target?.parse_id)return
  suggesting.value=true
  try{
    const result=await fileSuggestions(props.target.file_id)
    if(current!==generation)return
    suggestions.value=result
    if(!kind.value && result.suggested_type)kind.value=result.suggested_type
    parts.value=result.segments.map(part=>({...part,selected:true}))
    if(parts.value.length>1)mode.value='split'
  }catch{if(current===generation)suggestionError.value='范围建议暂不可用，请核对解析和修订状态。原有文件仍保留。'}
  finally{if(current===generation)suggesting.value=false}
})
const valid=computed(()=>mode.value==='whole'?!!kind.value && (!props.target || !!title.value.trim()):
  parts.value.some(part=>part.selected) && parts.value.filter(part=>part.selected).every(part=>part.title.trim() && part.start<part.end))
function addPart(){
  if(!suggestions.value)return
  parts.value.push({title:'',document_type:kind.value || 'law',start:suggestions.value.text_start,end:suggestions.value.text_start+Array.from(suggestions.value.source_text).length,
    expected_text_sha256:suggestions.value.text_sha256,requires_confirmation:true,page_start:1,page_end:1,selected:true})
  editing.value=parts.value.length-1
}
function startManualSplit(){mode.value='split';addPart()}
function useSelectedText(boundary?:'start'|'end'){
  const selection=window.getSelection(),element=sourceElement.value,data=suggestions.value
  if(!selection?.rangeCount || !element || !data || editing.value<0)return
  const range=selection.getRangeAt(0)
  if(!element.contains(range.startContainer) || !element.contains(range.endContainer)){ElMessage.warning('请只在识别正文区域选择文字');return}
  const prefix=range.cloneRange();prefix.selectNodeContents(element);prefix.setEnd(range.startContainer,range.startOffset)
  const before=prefix.toString(),selected=range.toString()
  if(!selected.trim() || data.source_text.slice(before.length,before.length+selected.length)!==selected){ElMessage.warning('文字位置无法可靠确认，请重新选择');return}
  const start=data.text_start+Array.from(before).length,end=start+Array.from(selected).length
  const part=parts.value[editing.value]
  if(boundary!=='end'){part.start=start;part.page_start=data.page_offset+before.split('\f').length}
  if(boundary!=='start'){part.end=end;part.page_end=data.page_offset+(before+selected).split('\f').length}
  ElMessage.success('已更新该篇的正文范围')
}
async function moveText(direction:number){
  if(!props.target || !suggestions.value || suggesting.value)return
  suggesting.value=true
  const current=generation
  try{const result=await fileSuggestions(props.target.file_id,Math.max(0,suggestions.value.text_start+direction*20000));if(current===generation)suggestions.value=result}
  catch(error){notifyApiError(error,'正文分段读取失败')}
  finally{if(current===generation)suggesting.value=false}
}
async function submit(){
  if(busy.value || !valid.value)return
  busy.value=true
  let succeeded=0
  failedNames.value=[]
  async function send(row:Pick<WorkbenchDocument,'file_id'|'sha256'|'parse_id'>,name:string,category:'law'|'case',scope?:SourceSegment){
    const extra=scope?{source_range:{start:scope.start,end:scope.end,expected_text_sha256:scope.expected_text_sha256}}:{whole_file_confirmed:!!props.target}
    const signature=JSON.stringify([row.file_id,row.sha256,row.parse_id,name,category,extra])
    const key=keys.get(signature) || crypto.randomUUID();keys.set(signature,key)
    if(completed.has(signature))return
    try{await prepareKnowledgeFile(row,name,category,key,extra);completed.add(signature);succeeded++}
    catch(error){const code=toApiError(error).code;failedNames.value.push(name+(code==='source_scope_overlap'?'：范围与已有待处理条目重叠，请核对':code==='published_source_change_requires_replacement'?'：已有发布记录，范围或类别变更需要专门更正流程':'：尚未提交，请核对状态后重试'))}
  }
  try{
    if(props.target){
      if(mode.value==='split'){
        const chosen=parts.value.filter(part=>part.selected).sort((a,b)=>a.start-b.start)
        if(chosen.some((part,index)=>index>0 && part.start<chosen[index-1].end)){ElMessage.warning('不同篇目的范围存在重叠，请调整后确认');return}
        for(const part of chosen)await send(props.target,part.title.trim(),part.document_type,part)
      }else await send(props.target,title.value.trim(),kind.value as 'law'|'case')
    }else if(props.snapshot){
      for(let page=1;page<=Math.ceil(props.snapshot.count/100);page++){
        const result=await selectionFiles(props.snapshot.selection_id,page)
        for(const row of result.list)await send(row,row.file_name.replace(/\.[^.]+$/,''),kind.value as 'law'|'case')
      }
    }else for(const row of props.selected)await send(row,row.title,kind.value as 'law'|'case')
    emit('done')
    if(failedNames.value.length){ElMessage.warning('已提交 '+succeeded+' 条，其他条目尚未完成，请重试');return}
    emit('update:modelValue',false)
    ElMessage.success('已提交 '+succeeded+' 条资料，可在“入库与发布”查看后台进度')
  }catch(error){notifyApiError(error,'已提交 '+succeeded+' 条，其余尚未完成；重试将核对同一请求')}
  finally{busy.value=false}
}
</script>
<style scoped>
.part-row{display:grid;grid-template-columns:auto minmax(120px,1fr) 120px auto auto;gap:8px;margin-top:12px;align-items:center}
.range-actions{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}
.scope-text{max-height:360px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;padding:12px;border:1px solid var(--mr-line);font:inherit;line-height:1.8}
.part-range{font-size:12px;color:var(--mr-text-secondary)}
p{line-height:1.7;color:var(--mr-text-secondary)}
@media(max-width:600px){.part-row{grid-template-columns:auto minmax(0,1fr)}.part-row>.el-select,.part-row>.el-button{grid-column:2}}
</style>
