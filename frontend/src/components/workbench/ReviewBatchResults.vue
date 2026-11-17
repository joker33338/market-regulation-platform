<template>
  <el-dialog :model-value="modelValue" title="本批审核逐项结果" width="min(760px, 94vw)" @update:model-value="emit('update:modelValue',$event)">
    <AsyncPanel :state="items.state.value" :error="items.error.value" empty-text="本批暂无结果" @retry="items.load()">
      <el-table :data="items.data.value?.list || []" max-height="420">
        <el-table-column label="文件" min-width="220"><template #default="{row}">{{row.file_name || '当前范围内不可见的文件'}}</template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="{row}">{{labels[row.status] || '待核实'}}</template></el-table-column>
        <el-table-column label="原因 / 下一步" min-width="240"><template #default="{row}">{{hint(row.error_code)}}</template></el-table-column>
      </el-table>
    </AsyncPanel>
    <el-pagination v-model:current-page="page" :total="items.data.value?.total || 0" :page-size="20" layout="total, prev, pager, next" @current-change="items.load()"/>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref,watch } from 'vue'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { reviewBatchItems } from '@/api/workbench'
const props=defineProps<{modelValue:boolean;batchId:string}>()
const emit=defineEmits<{(e:'update:modelValue',value:boolean):void}>()
const page=ref(1)
const items=useAsyncData(signal=>reviewBatchItems(props.batchId,page.value),{immediate:false})
items.state.value='empty'
watch(()=>props.modelValue,open=>{if(open && props.batchId){page.value=1;void items.load()}})
const labels:Record<string,string>={queued:'待处理',running:'正在审核',completed:'已完成',failed:'未完成'}
function hint(code?:string|null){
  if(!code)return '以后台真实完成状态为准'
  return ({review_version_conflict:'审核版本已变化，请重新查看正文并确认',review_source_changed:'解析结果已变化，请重新核对',
    review_write_forbidden:'当前身份不再具备审核权限',source_not_found:'文件已不可见，请刷新授权范围',document_not_found:'文件已不可见，请刷新授权范围',
    review_service_unavailable:'审核存储暂不可用，结果需核对后再重试',unauthorized:'账号或凭证已失效，请重新登录核对'} as Record<string,string>)[code] || '未通过审核门禁，请逐份打开文件核对'
}
</script>
<style scoped>.el-pagination{margin-top:16px}</style>
