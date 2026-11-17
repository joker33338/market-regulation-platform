<template>
  <el-dialog :model-value="modelValue" title="确认批量审核范围" width="min(620px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @update:model-value="emit('update:modelValue',$event)">
    <p>本次 {{snapshot?.count ?? selected.length}} 份文件。仅对当前确认的解析结果和审核版本生效，状态变化的文件会单独失败。</p>
    <el-form label-position="top" :disabled="busy">
      <el-form-item label="审核操作"><el-radio-group v-model="action"><el-radio-button label="approve">审核通过</el-radio-button><el-radio-button label="reject">退回处理</el-radio-button></el-radio-group></el-form-item>
      <el-form-item :label="action==='reject'?'退回原因（必填）':'审核备注（可选）'"><el-input v-model="reason" type="textarea" :rows="3" maxlength="2000" aria-label="批量审核说明"/></el-form-item>
      <el-checkbox v-model="attested">我已核对所选文档的原件与识别正文，确认执行上述操作</el-checkbox>
    </el-form>
    <p>提交后后台逐项执行，关闭页面不会取消已提交任务。审核通过后仍需准备候选和确认发布。</p>
    <template #footer><el-button :disabled="busy" @click="emit('update:modelValue',false)">取消</el-button><el-button type="primary" :disabled="!attested || action==='reject' && !reason.trim()" :loading="busy" @click="submit">确认提交批量审核</el-button></template>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref,watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createReviewBatch,appendReviewTargets,type ReviewTarget,type WorkbenchDocument,type SelectionSnapshot,type ReviewBatchStatus } from '@/api/workbench'
import { notifyApiError } from '@/api/errors'
const props=defineProps<{modelValue:boolean;selected:WorkbenchDocument[];snapshot:SelectionSnapshot|null}>()
const emit=defineEmits<{(e:'update:modelValue',value:boolean):void;(e:'submitted',value:ReviewBatchStatus):void}>()
const action=ref<'approve'|'reject'>('approve'),reason=ref(''),attested=ref(false),busy=ref(false)
let key='',signature=''
watch(()=>props.modelValue,open=>{if(open){attested.value=false;key=crypto.randomUUID();signature=''}})
async function submit(){
  if(busy.value || !attested.value)return
  busy.value=true
  try{
    let targets:ReviewTarget[]=[]
    if(!props.snapshot){
      if(props.selected.some(row=>!row.parse_id || row.review_version==null)){ElMessage.warning('所选范围包含尚不能审核的文件，请筛选待审核资料后重选');return}
      targets=props.selected.map(row=>({file_id:row.file_id,parse_id:row.parse_id!,expected_review_version:row.review_version!,expected_sha256:row.sha256}))
    }
    const current=JSON.stringify([action.value,reason.value,targets,props.snapshot?.selection_id])
    if(signature && signature!==current)key=crypto.randomUUID()
    signature=current
    let result=await createReviewBatch({action:action.value,reason:reason.value,attested:true,
      targets:targets.slice(0,100),selection_id:props.snapshot?.selection_id || null},key)
    for(let offset=100;offset<targets.length;offset+=100)result=await appendReviewTargets(result.batch_id,targets.slice(offset,offset+100))
    emit('submitted',result);emit('update:modelValue',false)
    ElMessage.info('批量审核已提交，请查看真实完成与失败统计')
  }catch(error){notifyApiError(error,'批量审核提交未完成，请核对范围后重试')}
  finally{busy.value=false}
}
</script>
<style scoped>p{line-height:1.7;color:var(--mr-text-secondary)}:deep(.el-checkbox){white-space:normal;height:auto;align-items:flex-start}:deep(.el-checkbox__label){white-space:normal;line-height:1.6}</style>
