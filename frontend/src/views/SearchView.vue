<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">知识检索</h1>
        <p class="page-desc">public ACTIVE 知识库 · 法条级定位 · 结果以后端真实返回为准（前端不生成任何法律原文）</p>
      </div>
      <div class="header-tags">
        <el-tag type="success" effect="plain">真实接口 /api/knowledge/search</el-tag>
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain">{{ contractLabel[contractState] }}</el-tag>
      </div>
    </div>

    <el-alert
      type="info"
      :closable="false"
      class="scope-notice"
      title="检索范围与真实性边界"
      description="draft-4：仅检索已发布版本（ACTIVE / ARCHIVED 且有发布记录），未发布候选不开放；默认无 ACTIVE 时合法返回 unpublished / 空列表。keyword_match 与 rrf 只是排序分，不是法律准确率，后端不提供 AI 问答或生成式结论。机关 / 效力按已有文档元数据精确过滤，缺少来源字段即无匹配，不推断法律事实；响应 applied_filters 是后端实际生效的筛选。请求体只允许契约声明的字段，额外字段会被 422 拒绝。" />

    <!-- 检索输入：只暴露后端契约支持的参数 -->
    <el-card shadow="never" style="margin-top: 16px">
      <div class="search-bar">
        <el-input
          v-model="query"
          size="large"
          placeholder="输入资料名称、章节或业务关键词" aria-label="检索关键词" maxlength="2000"
          clearable
          @keyup.enter="runSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" size="large" :disabled="!canSearch" :loading="search.loading.value" @click="runSearch">检索</el-button>
        <el-button size="large" @click="clearQuery">重置</el-button>
      </div>
      <div class="filter-row" role="group" aria-label="检索筛选条件">
        <el-select v-if="searchFilterEnabled('document_type')" v-model="documentType" aria-label="检索资料类别" size="small" style="width:160px"><el-option label="法规" value="law"/><el-option label="处罚案例" value="case"/><el-option label="全部授权资料" value="all"/></el-select>
        <el-select v-model="mode" aria-label="检索方式" size="small" style="width: 200px">
          <el-option label="keyword（关键词，不加载模型）" value="keyword" />
          <el-option label="hybrid（BGE-M3 混合检索）" value="hybrid" />
        </el-select>
        <span class="limit-label">返回条数</span>
        <el-input-number v-model="limit" aria-label="返回条数" :min="1" :max="50" :step="1" size="small" controls-position="right" style="width: 110px" />
        <el-tooltip v-for="f in SEARCH_FILTERS" :key="f.key" :content="filterTooltip(f)" placement="top">
          <span>
            <el-input
              v-model="filterValues[f.key]" :aria-label="f.label" :maxlength="f.key === 'kbVersion' ? 128 : f.key === 'issuingAuthority' ? 200 : 80"
              :placeholder="f.label"
              clearable
              size="small"
              style="width: 168px"
              :disabled="!searchFilterEnabled(f.field)"
              @keyup.enter="runSearch"
            />
          </span>
        </el-tooltip>
        <span class="mr-disabled-hint">{{ filterHint }}</span>
      </div>
      <div class="mr-disabled-hint" style="margin-top: 8px">
        hybrid 模式要求本地向量模型签名与 ACTIVE 版本一致，单进程并发受限时后端返回 429；页面如实显示错误态，不降级为模拟结果。
      </div>
    </el-card>

    <p v-if="filtersDirty" class="filter-feedback" role="status">筛选条件已修改，请点击检索应用。下方仍为上次提交的结果。</p>

    <!-- 结果区：尚未检索 / unpublished / 无命中 / 真实命中 分别明确呈现 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>检索结果 <span class="real-badge">REAL</span></span>
          <span class="card-sub">
            <template v-if="search.data.value">
              状态 {{ search.data.value.status }} · kb_version {{ search.data.value.kb_version || '—' }} ·
              模式 {{ search.data.value.mode }} · 命中 {{ search.data.value.count }} · 来源 {{ search.data.value.source }}
            </template>
            <template v-else>尚未发起检索</template>
          </span>
        </div>
      </template>

      <p v-if="submittedQuery" class="filter-feedback">已提交查询：{{ submittedQuery }} · {{ submittedMode === 'hybrid' ? '混合检索' : '关键词检索' }} · 最多 {{ submittedLimit }} 条</p>
      <div v-if="appliedFiltersText" class="applied-filters">后端实际生效筛选 <code class="mono">{{ appliedFiltersText }}</code></div>
      <AsyncPanel :state="search.state.value" :error="search.error.value" @retry="runSearch">
        <template #empty>
          <el-empty :image-size="70" :description="emptyDescription">
            <p class="empty-note">
              <template v-if="!submittedQuery">
                请输入检索词并点击「检索」；结果只来自 POST /api/knowledge/search 的真实响应，本页不生成任何法规原文。
              </template>
              <template v-else>
                本页不会生成任何资料名称、条号、原文或结论；接口异常时显示错误态而非空结果，不会以演示数据填充。
              </template>
            </p>
            <el-button size="small" :disabled="!canSearch" @click="runSearch">
              {{ submittedQuery ? '重新检索' : '发起检索' }}
            </el-button>
          </el-empty>
        </template>


        <el-alert type="success" :closable="false" style="margin-bottom: 12px"
          title="以下法条文本与元数据均来自后端真实响应"
          description="article_text 按不可信纯文本渲染（不使用 v-html、不执行 HTML / 脚本）；raw_score 仅作排序参考，不得解释为法律适用结论。引用时请结合 source 元数据与 kb_version 追溯原文。" />

        <div v-for="(hit, i) in hits" :key="`${hit.chunk_id}-${i}`" class="hit-card">
          <div class="hit-head">
            <span class="hit-index num">{{ i + 1 }}</span>
            <b>{{ hit.regulation_name || '〔后端未返回资料名称〕' }}</b>
            <el-tag v-if="hit.article_no" size="small" effect="plain">{{ hit.article_no }}</el-tag>
            <el-tag v-if="hit.chapter" size="small" type="info" effect="plain">{{ hit.chapter }}</el-tag>
            <span class="hit-score">
              {{ hit.score_kind }}：<b class="num">{{ hit.raw_score ?? '—' }}</b>
            </span>
          </div>
          <pre class="hit-text">{{ hit.article_text || '〔后端未返回该条法条原文，前端不补写〕' }}</pre>
          <div class="hit-meta">
            <span>kb_version：<code class="mono">{{ hit.kb_version || '—' }}</code></span>
            <span>chunk_id：<code class="mono">{{ hit.chunk_id || '—' }}</code></span>
            <span>doc_version_id：<code class="mono">{{ hit.doc_version_id || '—' }}</code></span>
          </div>
          <el-collapse v-if="hasSource(hit)">
            <el-collapse-item title="source 溯源元数据（后端原始字段）">
              <pre class="result-pre">{{ asJson(hit.source) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </AsyncPanel>
    </el-card>

    <!-- 结果字段契约说明（不含任何法条内容） -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>结果字段契约</span>
          <span class="card-sub">POST /api/knowledge/search · 字段以运行期契约为准</span>
        </div>
      </template>
      <div class="field-grid">
        <el-tag v-for="f in RESULT_FIELDS" :key="f" effect="plain" size="small">{{ f }}</el-tag>
      </div>
      <el-divider />
      <div class="mode-grid">
        <div><b>keyword 模式</b><span>复用关键词检索，不加载向量模型，返回 keyword_match 标记</span></div>
        <div><b>hybrid 模式</b><span>复用 BGE-M3 混合检索，返回 rrf 融合排序分；模型签名须与 ACTIVE 一致</span></div>
        <div><b>unpublished</b><span>public 知识库无 ACTIVE 版本时返回空列表，页面显示「尚未发布」而非伪造命中</span></div>
        <div><b>不支持</b><span>AI 问答、生成式结论、semantic-only、未发布候选版本检索与契约未声明的筛选参数</span></div>
      </div>
      <div class="mr-disabled-hint" style="margin-top: 12px">
        请求体遵循 additionalProperties=false：只发送契约声明的字段，额外字段一律 422。
        draft-4 的 kb_version / issuing_authority / effective_status 仅在 GET /api/system/capabilities
        的 search_filters 声明后才可填写并随请求发送；未声明时输入框禁用，绝不偷偷带上未支持的参数。
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { searchKnowledge } from '@/api/frontend'
import { contractState, contractLabel, probeContract } from '@/api/dataSource'
import {
  loadCapabilities, searchFilterEnabled, capabilitiesState, runtimeCapabilities
} from '@/api/ops'
import type { SearchRequest, SearchResponse, SearchHit } from '@/api/types'

/**
 * v0.2.2 法规检索 / v0.2.3 draft-4 筛选扩展
 * - 唯一数据源 POST /api/knowledge/search（仅已发布 ACTIVE / ARCHIVED 版本）
 * - 请求体严格遵循运行期契约；新筛选只有被 /api/system/capabilities 声明后才发送
 * - 法条原文只渲染后端 article_text，纯文本 <pre>，禁止 v-html
 * - 尚未检索 / unpublished / 空列表 / 接口异常 / 未认证 / 契约未加载 分别呈现，绝不伪造法条
 */
const query = ref('')
const submittedQuery = ref('')
const documentType=ref<'law'|'case'|'all'>('law'),submittedDocumentType=ref<'law'|'case'|'all'>('law')
const mode = ref<SearchRequest['mode']>('keyword')
const limit = ref(8)
const submittedMode = ref<SearchRequest['mode']>('keyword')
const submittedLimit = ref(8)
const filtersDirty = computed(() => !!submittedQuery.value && (query.value.trim() !== submittedQuery.value || mode.value !== submittedMode.value || documentType.value !== submittedDocumentType.value || limit.value !== submittedLimit.value || JSON.stringify(activeFilters()) !== JSON.stringify(submittedFilters.value)))

/* draft-4 新筛选：key 为 UI 状态，field 为后端能力声明 / 请求体字段名 */
type FilterKey = 'kbVersion' | 'issuingAuthority' | 'effectiveStatus'
interface SearchFilterDef { key: FilterKey; field: string; label: string }
const SEARCH_FILTERS: SearchFilterDef[] = [
  { key: 'kbVersion', field: 'kb_version', label: '已发布版本（留空使用当前版本）' },
  { key: 'issuingAuthority', field: 'issuing_authority', label: '发布机关' },
  { key: 'effectiveStatus', field: 'effective_status', label: '效力状态' }
]
const filterValues = reactive<Record<FilterKey, string>>({
  kbVersion: '', issuingAuthority: '', effectiveStatus: ''
})
/** 提交时冻结筛选快照，避免「结果已返回但输入框被改动」造成展示口径不一致 */
const submittedFilters = ref<Partial<Record<FilterKey, string>>>({})

function activeFilters(): Partial<Record<FilterKey, string>> {
  const out: Partial<Record<FilterKey, string>> = {}
  for (const f of SEARCH_FILTERS) {
    const v = filterValues[f.key].trim()
    if (v && searchFilterEnabled(f.field)) out[f.key] = v
  }
  return out
}

const filterHint = computed(() => {
  if (contractState.value !== 'ready') return '运行期契约未就绪：筛选输入暂不可用'
  if (capabilitiesState.value === 'error') return 'GET /api/system/capabilities 未返回能力声明，筛选保持禁用'
  if (!runtimeCapabilities.value) return '正在读取运行期能力声明…'
  const n = SEARCH_FILTERS.filter((f) => searchFilterEnabled(f.field)).length
  return n
    ? `运行期已声明 ${n} 项筛选；未声明的字段不会随请求发送`
    : '运行期能力声明未包含任何检索筛选字段，输入框保持禁用'
})

function filterTooltip(f: SearchFilterDef): string {
  return searchFilterEnabled(f.field)
    ? `${f.field} 已被运行期能力声明，随检索请求发送（后端 applied_filters 回显实际生效值）`
    : `${f.field} 未被运行期 GET /api/system/capabilities 声明，按契约不得发送，输入框保持禁用`
}

const appliedFiltersText = computed(() => {
  const a = search.data.value?.applied_filters
  return a && Object.keys(a).length ? JSON.stringify(a) : ''
})

const RESULT_FIELDS = [
  'chunk_id', 'doc_version_id', 'regulation_name', 'article_no', 'article_text',
  'chapter', 'kb_version', 'raw_score', 'score_kind', 'source',
  'status', 'count', 'mode', 'kb_version（响应级）', 'source（响应级）', 'applied_filters'
]

const canSearch = computed(() =>
  !!query.value.trim() && !search.loading.value && limit.value >= 1 && limit.value <= 50
)

const search = useAsyncData<SearchResponse>(
  (signal) => searchKnowledge(
    { query: submittedQuery.value, mode: submittedMode.value, limit: submittedLimit.value, ...submittedFilters.value,...(searchFilterEnabled('document_type')?{documentType:submittedDocumentType.value}:{}) },
    signal
  ),
  { immediate: false }
)
search.state.value = 'empty'

/** 初始态只是「尚未发起检索」，不得冒充「后端返回空列表」 */
const emptyDescription = computed(() => {
  if (!submittedQuery.value) return '尚未发起检索'
  if (search.data.value?.status === 'unpublished') {
    return '知识库尚未发布：public schema 无 ACTIVE 版本，后端返回 status=unpublished'
  }
  return '未检索到相关依据（后端返回空列表）'
})

/** 直接刷新本页时探测运行期契约并读取能力声明；未声明筛选字段时输入框保持禁用 */
onMounted(async () => {
  if (contractState.value !== 'ready') await probeContract()
  if (contractState.value === 'ready') await loadCapabilities()
})

function runSearch() {
  if (!canSearch.value) return
  submittedQuery.value = query.value.trim()
  submittedFilters.value = activeFilters()
  submittedMode.value = mode.value
  submittedDocumentType.value=documentType.value
  submittedLimit.value = limit.value
  void search.load()
}

function clearQuery() {
  query.value = ''
  mode.value = 'keyword'
  documentType.value='law'
  limit.value = 8
  search.error.value = ''
  submittedQuery.value = ''
  submittedFilters.value = {}
  for (const f of SEARCH_FILTERS) filterValues[f.key] = ''
  search.cancel()
  search.data.value = null
  search.state.value = 'empty'
}

const hits = computed<SearchHit[]>(() => search.data.value?.list || [])

function hasSource(hit: SearchHit): boolean {
  return !!hit.source && typeof hit.source === 'object' && Object.keys(hit.source).length > 0
}

function asJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2)
}
</script>

<style scoped>
.header-tags { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.scope-notice { margin-bottom: 0; }
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; gap: 12px; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); }
.search-bar { display: flex; gap: 12px; }
.filter-row { display: flex; align-items: center; gap: 12px; margin-top: 12px; flex-wrap: wrap; }
.limit-label { font-size: 12px; color: var(--mr-text-2); }
.empty-note { max-width: 620px; margin: 0 auto 8px; color: var(--mr-text-2); font-size: 13px; line-height: 1.8; }
.applied-filters { font-size: 12px; color: var(--mr-text-2); margin-bottom: 10px; }
.field-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.mode-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.mode-grid > div { padding: 10px 12px; border: 1px solid var(--mr-line); border-radius: 6px; background: #fafbfe; display: flex; flex-direction: column; gap: 4px; }
.mode-grid b { font-size: 13px; }
.mode-grid span { font-size: 12px; color: var(--mr-text-2); }
.hit-card { border: 1px solid var(--mr-line); border-radius: 6px; background: #fafbfe; padding: 12px; margin-bottom: 12px; }
.hit-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; }
.hit-index { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; background: var(--mr-primary); color: #fff; font-size: 12px; }
.hit-score { margin-left: auto; font-size: 12px; color: var(--mr-text-2); }
.hit-text { font-family: var(--mr-font); font-size: 13px; line-height: 1.9; white-space: pre-wrap; word-break: break-word; margin: 10px 0; padding: 10px; background: #fff; border: 1px solid var(--mr-line); border-radius: 4px; }
.hit-meta { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12px; color: var(--mr-text-2); }
.mono { font-family: monospace; font-size: 12px; }
.result-pre { font-family: var(--mr-font); font-size: 12px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; margin: 0; }
@media (max-width: 1366px) {
  .mode-grid { grid-template-columns: 1fr; }
}
</style>
