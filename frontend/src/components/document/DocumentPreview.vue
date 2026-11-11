<template>
  <div class="dp">
    <div class="dp-toolbar">
      <span class="dp-page-num num">
        第 {{ page }} / {{ kind === 'pdf' ? (totalPages || '—') : 1 }} 页
      </span>
      <div class="dp-controls">
        <el-button size="small" :disabled="!canPage || page <= 1" @click="changePage(page - 1)">上一页</el-button>
        <el-input-number
          v-model="innerPage"
          :min="1"
          :max="Math.max(totalPages, 1)"
          :disabled="!canPage"
          size="small"
          style="width: 100px"
          @change="changePage"
        />
        <el-button size="small" :disabled="!canPage || page >= totalPages" @click="changePage(page + 1)">下一页</el-button>
        <el-select v-model="zoom" size="small" :disabled="state !== 'ready'" style="width: 92px">
          <el-option v-for="z in [75, 100, 125, 150, 200]" :key="z" :label="`${z}%`" :value="z" />
        </el-select>
        <el-button v-if="state === 'ready'" size="small" :loading="downloading" @click="download">下载原件</el-button>
      </div>
    </div>

    <div v-if="sha256" class="dp-integrity" :class="{ bad: !integrityOk }">
      <span>SHA256（后端 X-SHA256）：<code>{{ sha256.slice(0, 24) }}{{ sha256.length > 24 ? '…' : '' }}</code></span>
      <span v-if="expectedSha256">{{ integrityOk ? '与文档记录一致' : '与文档记录不一致，已阻断预览' }}</span>
    </div>

    <div class="dp-body">
      <div v-if="state === 'loading'" v-loading="true" class="dp-loading">
        <span class="dp-tip">正在通过认证接口读取原始文件字节…</span>
      </div>

      <div v-else-if="state === 'ready' && kind === 'pdf'" class="dp-viewer">
        <!-- Blob URL 来自认证 Axios ArrayBuffer；绝不把需要 Token 的接口地址直接塞进 iframe -->
        <iframe :src="viewerUrl" title="原始 PDF 预览" class="dp-frame" />
      </div>

      <div v-else-if="state === 'ready' && kind === 'image'" class="dp-viewer dp-image">
        <img :src="sourceUrl || ''" :alt="fileName || '原始图片'" :style="{ width: zoom + '%' }" />
      </div>

      <div v-else-if="state === 'ready' && kind === 'docx'" class="dp-unavailable">
        <el-icon size="42" color="var(--mr-text-3)"><Document /></el-icon>
        <h3>Word 文档按后端契约以附件方式提供</h3>
        <p>后端 `/source` 对 .docx 返回 `Content-Disposition: attachment`，且明确不提供 Word→PDF 转换。前端不做格式转换，请点击「下载原件」在本地查看。</p>
        <p class="dp-note">原始证据文件只读，任何审核动作都不会改写原始字节。</p>
      </div>

      <div v-else class="dp-unavailable">
        <el-icon size="42" color="var(--mr-text-3)"><Document /></el-icon>
        <h3>{{ titleOf(state) }}</h3>
        <p>{{ errorHint || hintOf(state) }}</p>
        <code v-if="fileId">{{ SOURCE_FILE_API }}</code>
        <div class="dp-actions">
          <el-button size="small" @click="loadSource">重新加载</el-button>
        </div>
        <p class="dp-note">
          文件来源唯一：后端 owner 隔离的原始文件接口。不使用 artifact.bin（MinerU 产物）冒充原文，不提供本地选文件预览，不伪造页面或页码。
        </p>
      </div>
    </div>

    <div class="dp-thumbs">
      <div
        v-for="p in thumbPages"
        :key="p"
        class="dp-thumb num"
        :class="{ active: p === page, disabled: !canPage }"
        @click="canPage && changePage(p)"
      >{{ p }}</div>
      <span v-if="state === 'ready' && kind === 'image'" class="dp-thumb-note">图片文件无多页</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Document } from '@element-plus/icons-vue'
import {
  getSourceFile, createSourceUrl, revokeSourceUrl, downloadSourceFile,
  isValidFileId, SOURCE_FILE_API, type SourceKind
} from '@/api/documentFiles'
import { toApiError, notifyApiError } from '@/api/errors'
import { hasToken } from '@/api/client'
import { contractState } from '@/api/dataSource'

/**
 * 文档预览统一入口（审核中心左侧）—— v0.2.2 真实实现
 * PDF 用浏览器内置 PDF viewer 渲染 iframe（Blob URL），图片用 <img>，DOCX 按后端契约仅授权下载。
 * 不新增 pdfjs-dist / vue-office 依赖，符合「优先复用已安装能力、不大规模更换组件库」。
 */
type ViewState = 'idle' | 'loading' | 'ready' | 'no-permission' | 'outdated' | 'unavailable' | 'error' | 'empty'

const props = withDefaults(
  defineProps<{
    fileId?: string
    fileName?: string
    expectedSha256?: string
    page: number
    totalPages?: number
  }>(),
  { fileId: '', fileName: '', expectedSha256: '', totalPages: 0 }
)

const emit = defineEmits<{ (e: 'update:page', value: number): void }>()

const state = ref<ViewState>('idle')
const errorHint = ref('')
const sourceUrl = ref('')
const sha256 = ref('')
const kind = ref<SourceKind>('other')
const zoom = ref(100)
const innerPage = ref(props.page)
const downloading = ref(false)
let controller: AbortController | null = null

const integrityOk = computed(() => !props.expectedSha256 || !sha256.value || props.expectedSha256 === sha256.value)
const canPage = computed(() => state.value === 'ready' && kind.value === 'pdf' && integrityOk.value)
const viewerUrl = computed(() =>
  sourceUrl.value ? `${sourceUrl.value}#page=${innerPage.value}&zoom=${zoom.value}` : ''
)

const thumbPages = computed(() => {
  const total = Math.max(props.totalPages, 1)
  const cur = Math.min(Math.max(props.page, 1), total)
  const start = Math.max(1, Math.min(cur - 3, total - 7))
  return Array.from({ length: Math.min(8, total) }, (_, i) => start + i)
})

function titleOf(s: ViewState): string {
  return s === 'no-permission' ? '未认证 / 无权限'
    : s === 'outdated' ? '原始文件接口在当前后端实例不可用'
      : s === 'unavailable' ? '服务不可达'
        : s === 'empty' ? '未选择原始文件'
          : '原始文件加载失败'
}

function hintOf(s: ViewState): string {
  return s === 'no-permission' ? '请在系统监控页配置 API Token 后重试。'
    : s === 'outdated' ? '活动 8180 实例可能仍是 v0.2.1 旧镜像，未加载 /source 路由。'
      : s === 'unavailable' ? '后端服务未响应或返回 5xx，请检查服务状态。'
        : s === 'empty' ? '该审核记录未提供 source_file_id，无法定位原始上传文件。'
          : '请重新加载；不会用解析产物或演示页面替代原始证据。'
}

function releaseUrl() {
  if (sourceUrl.value) {
    revokeSourceUrl(sourceUrl.value)
    sourceUrl.value = ''
  }
}

async function loadSource() {
  if (controller) controller.abort()
  controller = null
  releaseUrl()
  sha256.value = ''
  errorHint.value = ''

  if (!props.fileId) {
    state.value = 'empty'
    return
  }
  if (!isValidFileId(props.fileId)) {
    state.value = 'error'
    errorHint.value = '无效的上传文件 ID（应为 32 位十六进制），禁止拼接推导 ID'
    return
  }
  if (!hasToken()) {
    state.value = 'no-permission'
    return
  }
  if (contractState.value !== 'ready' && contractState.value !== 'unknown') {
    state.value = contractState.value === 'no-permission' ? 'no-permission' : 'outdated'
    errorHint.value = '运行期契约探测未通过，未发起原始文件请求'
    return
  }

  state.value = 'loading'
  const ctrl = new AbortController()
  controller = ctrl
  try {
    const file = await getSourceFile(props.fileId, props.fileName, ctrl.signal)
    if (ctrl.signal.aborted) return
    sha256.value = file.sha256
    kind.value = file.kind
    if (!integrityOk.value) {
      state.value = 'error'
      errorHint.value = '后端返回的 X-SHA256 与文档记录不一致（完整性校验失败），已阻断预览'
      return
    }
    sourceUrl.value = createSourceUrl(file)
    state.value = 'ready'
  } catch (err) {
    if (ctrl.signal.aborted) return
    const e = toApiError(err)
    if (e.kind === 'canceled') return
    errorHint.value = e.hint
    state.value = e.kind === 'no-permission' ? 'no-permission'
      : e.kind === 'outdated' || e.kind === 'not-found' ? 'outdated'
        : e.kind === 'unavailable' ? 'unavailable' : 'error'
  } finally {
    if (controller === ctrl) controller = null
  }
}

async function download() {
  if (!props.fileId) return
  downloading.value = true
  try {
    await downloadSourceFile(props.fileId, props.fileName || props.fileId)
  } catch (err) {
    notifyApiError(err, '原始文件下载失败')
  } finally {
    downloading.value = false
  }
}

function changePage(v: number | null | undefined) {
  if (typeof v !== 'number') return
  const p = Math.min(Math.max(Math.round(v), 1), Math.max(props.totalPages, 1))
  innerPage.value = p
  emit('update:page', p)
}

watch(() => props.page, (v) => { innerPage.value = v })
watch([() => props.fileId, () => props.fileName, () => props.expectedSha256], loadSource, { immediate: true })

onBeforeUnmount(() => {
  if (controller) controller.abort()
  releaseUrl()
})
</script>

<style scoped>
.dp { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.dp-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; border-bottom: 1px solid var(--mr-line); flex-shrink: 0; gap: 8px; flex-wrap: wrap;
}
.dp-page-num { font-size: 13px; color: var(--mr-text-2); }
.dp-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dp-integrity {
  display: flex; gap: 12px; flex-wrap: wrap; padding: 6px 14px;
  font-size: 11px; color: var(--mr-text-3); background: #f8fafd; border-bottom: 1px solid var(--mr-line);
}
.dp-integrity.bad { color: var(--mr-st-danger); background: #fef2f2; }
.dp-integrity code { font-family: monospace; }
.dp-body {
  flex: 1; min-height: 0; display: flex; align-items: stretch;
  justify-content: center; background: #eef1f6; overflow: hidden;
}
.dp-loading { width: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column; }
.dp-tip { font-size: 12px; color: var(--mr-text-3); padding-top: 26px; }
.dp-viewer { width: 100%; height: 100%; }
.dp-frame { width: 100%; height: 100%; border: 0; background: #fff; }
.dp-image { overflow: auto; display: flex; align-items: flex-start; justify-content: center; padding: 16px; }
.dp-image img { max-width: none; height: auto; box-shadow: 0 2px 8px rgba(15,43,82,.12); }
.dp-unavailable { text-align: center; color: var(--mr-text-2); max-width: 500px; margin: auto; padding: 20px; }
.dp-unavailable h3 { margin: 12px 0 8px; font-size: 15px; color: var(--mr-text-1); }
.dp-unavailable p { margin: 6px 0; font-size: 13px; line-height: 1.7; }
.dp-unavailable code {
  display: inline-block; font-size: 12px; background: #fff; border: 1px solid var(--mr-line);
  border-radius: 4px; padding: 4px 8px; color: #92400e;
}
.dp-actions { margin-top: 12px; }
.dp-note { margin-top: 14px !important; font-size: 12px !important; color: var(--mr-text-3); text-align: left; }
.dp-thumbs {
  display: flex; gap: 6px; padding: 10px 14px; border-top: 1px solid var(--mr-line);
  overflow-x: auto; flex-shrink: 0; align-items: center;
}
.dp-thumb {
  width: 36px; height: 48px; flex-shrink: 0; border: 1px solid var(--mr-line); border-radius: 4px;
  display: flex; align-items: center; justify-content: center; font-size: 12px;
  color: var(--mr-text-2); cursor: pointer; background: #fff;
}
.dp-thumb.active { border-color: var(--mr-primary); color: var(--mr-primary); font-weight: 600; }
.dp-thumb.disabled { opacity: .5; cursor: not-allowed; }
.dp-thumb-note { font-size: 11px; color: var(--mr-text-3); margin-left: 8px; }
</style>
