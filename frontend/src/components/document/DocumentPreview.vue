<template>
  <div class="dp">
    <div class="dp-toolbar">
      <span class="dp-page-num num">第 {{ page }} / {{ totalPages || '—' }} 页</span>
      <div class="dp-controls">
        <el-button size="small" :disabled="!ready || page <= 1" @click="changePage(page - 1)">上一页</el-button>
        <el-input-number
          v-model="innerPage"
          :min="1"
          :max="Math.max(totalPages, 1)"
          :disabled="!ready"
          size="small"
          style="width: 100px"
          @change="changePage"
        />
        <el-button size="small" :disabled="!ready || page >= totalPages" @click="changePage(page + 1)">下一页</el-button>
        <el-select v-model="zoom" size="small" :disabled="!ready" style="width: 92px">
          <el-option v-for="z in [75, 100, 125, 150, 200]" :key="z" :label="`${z}%`" :value="z" />
        </el-select>
      </div>
    </div>

    <div class="dp-body">
      <div v-if="checking" v-loading="true" class="dp-loading" />
      <div v-else-if="!ready" class="dp-unavailable">
        <el-icon size="46" color="var(--mr-text-3)"><Document /></el-icon>
        <h3>原始文件预览未接入</h3>
        <p>{{ reason }}</p>
        <code>{{ api }}</code>
        <p class="dp-note">
          后端原始文件接口交付、且前端启用 PDF.js / Word 预览组件后，本区域将自动渲染真实文件，
          支持缩放、页码跳转、缩略图、文本层，并与右侧解析结果按页对照。
          当前不提供本地选文件预览，也不会用解析产物冒充原始证据文件。
        </p>
      </div>
      <div v-else class="dp-unavailable">
        <p>文件已获取，但渲染器尚未启用（需引入 pdfjs-dist / @vue-office/docx）。</p>
        <p class="dp-note">原始结果保持只读，任何审核动作都不会改写原始文件字节。</p>
      </div>
    </div>

    <div class="dp-thumbs">
      <div
        v-for="p in thumbPages"
        :key="p"
        class="dp-thumb num"
        :class="{ active: p === page, disabled: !ready }"
        @click="ready && changePage(p)"
      >{{ p }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Document } from '@element-plus/icons-vue'
import { getSourceFile, SOURCE_FILE_API, sourceFileAvailable } from '@/api/documentFiles'

/**
 * 文档预览统一入口（审核中心左侧）
 * 唯一文件来源：api/documentFiles.ts 的可插拔适配层。
 * 接口未交付时一律显示「未接入」，不占位假装、不本地选文件、不使用 artifact.bin。
 */
const props = withDefaults(
  defineProps<{
    fileId?: string
    page: number
    totalPages?: number
  }>(),
  { fileId: '', totalPages: 0 }
)

const emit = defineEmits<{ (e: 'update:page', value: number): void }>()

const ready = ref(false)
const checking = ref(true)
const reason = ref('')
const api = ref(SOURCE_FILE_API)
const zoom = ref(100)
const innerPage = ref(props.page)

watch(
  () => props.page,
  (v) => {
    innerPage.value = v
  }
)

const thumbPages = computed(() => {
  const total = Math.max(props.totalPages, 1)
  const cur = Math.min(Math.max(props.page, 1), total)
  const start = Math.max(1, Math.min(cur - 3, total - 7))
  return Array.from({ length: Math.min(8, total) }, (_, i) => start + i)
})

function changePage(v: number | null | undefined) {
  if (typeof v !== 'number') return
  const p = Math.min(Math.max(Math.round(v), 1), Math.max(props.totalPages, 1))
  innerPage.value = p
  emit('update:page', p)
}

onMounted(async () => {
  // sourceFileAvailable() 为 false 时直接短路，不发起任何伪造请求
  if (!sourceFileAvailable()) {
    reason.value = '原始文件读取接口尚未接入，无法通过后端获取 PDF / Word / 图片进行真实预览'
    api.value = SOURCE_FILE_API
    checking.value = false
    return
  }
  const res = await getSourceFile(props.fileId)
  ready.value = res.available
  reason.value = res.available ? '' : res.reason
  api.value = res.available ? '' : res.api
  checking.value = false
})
</script>

<style scoped>
.dp {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.dp-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--mr-line);
  flex-shrink: 0;
}
.dp-page-num {
  font-size: 13px;
  color: var(--mr-text-2);
}
.dp-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dp-body {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eef1f6;
  overflow: auto;
  padding: 20px;
}
.dp-loading {
  width: 100%;
  height: 200px;
}
.dp-unavailable {
  text-align: center;
  color: var(--mr-text-2);
  max-width: 480px;
}
.dp-unavailable h3 {
  margin: 12px 0 8px;
  font-size: 15px;
  color: var(--mr-text-1);
}
.dp-unavailable p {
  margin: 6px 0;
  font-size: 13px;
  line-height: 1.7;
}
.dp-unavailable code {
  display: inline-block;
  font-size: 12px;
  background: #fff;
  border: 1px solid var(--mr-line);
  border-radius: 4px;
  padding: 4px 8px;
  color: #92400e;
}
.dp-note {
  margin-top: 14px !important;
  font-size: 12px !important;
  color: var(--mr-text-3);
  text-align: left;
}
.dp-thumbs {
  display: flex;
  gap: 6px;
  padding: 10px 14px;
  border-top: 1px solid var(--mr-line);
  overflow-x: auto;
  flex-shrink: 0;
}
.dp-thumb {
  width: 36px;
  height: 48px;
  flex-shrink: 0;
  border: 1px solid var(--mr-line);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--mr-text-2);
  cursor: pointer;
  background: #fff;
}
.dp-thumb.active {
  border-color: var(--mr-primary);
  color: var(--mr-primary);
  font-weight: 600;
}
.dp-thumb.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
