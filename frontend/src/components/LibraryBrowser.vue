<template>
  <div class="lib-browser">
    <!-- 状态播报：加载 / 取消 / 空态 / 错误 / 门控态共用 aria-live -->
    <div class="lib-live" aria-live="polite" aria-atomic="true">{{ liveText }}</div>

    <!-- 请求取消：独立状态，绝不与合法空态或错误态共用渲染分支 -->
    <div v-if="canceledNotice" class="lib-cancel-note" aria-live="polite">
      <el-alert type="info" :closable="false" title="请求已取消" :description="canceledNotice">
        <el-button size="small" :disabled="gate !== 'ready'" @click="runList">重新查询</el-button>
      </el-alert>
    </div>

    <!-- 筛选条：未通过门控时「文字说明 + 控件 disabled」双重可辨 -->
    <el-card shadow="never" class="lib-filter-card">
      <div class="lib-filter-row">
        <span class="lib-filter-label">query（≤200）</span>
        <el-input v-model="draft.query" size="small" maxlength="200" clearable :disabled="!canQuery"
          placeholder="标题 / 关键词（原样提交后端）" style="width: 210px" @keyup.enter="applyFilters" />
        <template v-if="isCase">
          <span class="lib-filter-label">violation（≤200，仅案例库）</span>
          <el-input v-model="draft.violation" size="small" maxlength="200" clearable :disabled="!canQuery"
            placeholder="违法行为" style="width: 190px" @keyup.enter="applyFilters" />
        </template>
        <span class="lib-filter-label">kb_version（≤128）</span>
        <el-input v-model="draft.kbVersion" size="small" maxlength="128" clearable
          :disabled="!canQuery || !isAdminIdentity" placeholder="仅 ADMIN 可显式选择版本" style="width: 200px"
          @keyup.enter="applyFilters" />
        <span class="lib-filter-label">page_size（1..100）</span>
        <el-input-number v-model="pageSize" :min="1" :max="100" :step="1" size="small"
          controls-position="right" :disabled="!canQuery" style="width: 110px" />
        <el-button size="small" type="primary" :disabled="!canQuery" @click="applyFilters">查询</el-button>
        <el-button size="small" :disabled="!canQuery" @click="resetFilters">清空筛选</el-button>
        <el-button size="small" :disabled="!canQuery" @click="runList">刷新</el-button>
      </div>
      <div class="mr-disabled-hint">{{ filterHint }}</div>
    </el-card>

    <!-- 运行期状态表：8 条 GET 方法级门控结果，静态契约信息，不发起任何业务请求 -->
    <el-card shadow="never" class="lib-routes-card">
      <template #header>
        <div class="card-head">
          <span>draft-5 运行期接口状态 <span class="real-badge">REAL</span></span>
          <span class="card-sub">GET /api/openapi.json 方法级探测 · 路径存在 ≠ 方法可用</span>
        </div>
      </template>
      <div class="lib-scroll-x">
        <el-table class="lib-table" :data="routeRows" size="small">
          <el-table-column prop="method" label="方法" width="80" />
          <el-table-column prop="path" label="路径" min-width="330" show-overflow-tooltip />
          <el-table-column prop="page" label="用途" min-width="180" show-overflow-tooltip />
          <el-table-column label="运行期状态" width="130">
            <template #default="{ row }">
              <el-tag size="small" effect="plain"
                :type="row.status === 'loaded' ? 'success' : row.status === 'missing' ? 'warning' : 'info'">
                {{ row.statusText }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="mr-disabled-hint" style="margin-top: 8px">
        draft-5 的 CapabilitiesResponse 未新增 library 字段，两页可用性只能靠
        hasRuntimeMethod('GET', path) 逐条判定；未加载时页面不发起请求、不展示演示数据。
        仅 ACTIVE / ARCHIVED 且有发布历史的版本可见：管理员全局、普通用户本人、审核员仅授权 owner。
      </div>
    </el-card>

    <!-- 列表 -->
    <el-card shadow="never" class="lib-list-card">
      <template #header>
        <div class="card-head">
          <span>{{ listTitle }} <span class="real-badge">REAL</span></span>
          <span class="card-sub">{{ listMeta }}</span>
        </div>
      </template>

      <!-- 401：错误态常显（el-alert--error 不参与注释折叠） -->
      <el-alert v-if="gate === 'contract-401'" type="error" :closable="false" show-icon
        title="未认证 / 无权限（401）" :description="COPY.contract401">
        <template #default>
          <div class="lib-gate-actions"><el-button size="small" @click="reprobe">重新探测</el-button></div>
        </template>
      </el-alert>

      <!-- 未配置凭证 / 契约未就绪 / 路由未加载：各自独立的门控卡片 -->
      <div v-else-if="gate !== 'ready'" class="lib-gate" aria-live="polite">
        <div class="lib-gate-head">
          <el-tag type="warning" effect="plain">{{ gateTagText }}</el-tag>
          <span class="lib-gate-title">{{ gateTitle }}</span>
        </div>
        <p class="lib-lead">{{ gateLead }}</p>
        <div class="mr-disabled-hint">{{ gateNote }}</div>
        <div class="lib-gate-actions">
          <el-button size="small" disabled>查询（当前不可用）</el-button>
          <el-button size="small" disabled>刷新（当前不可用）</el-button>
          <el-button v-if="gate === 'contract-not-ready' || gate === 'contract-pending'" size="small" @click="reprobe">重新探测</el-button>
        </div>
      </div>

      <template v-else>
        <AsyncPanel :state="panelState" :error="panelError" loading-text="正在从后端加载真实数据…" @retry="runList">
          <template #empty>
            <!-- 合法空态 unpublished：独立分支、独立文案，不是错误 -->
            <div v-if="isEmptyUnpublished" class="lib-empty-unpublished">
              <el-alert type="info" :closable="false" title="合法空态：status=unpublished" :description="COPY.unpublished">
                <el-button size="small" @click="resetFilters">清空筛选并重新查询</el-button>
              </el-alert>
              <el-empty :image-size="70" description="后端返回 status=unpublished / 空列表（不是错误）" />
            </div>
            <!-- ready 空：另一条渲染分支、另一套文案，绝不复用 -->
            <div v-else class="lib-empty-ready">
              <el-empty :image-size="70" :description="COPY.readyEmpty">
                <el-button size="small" @click="resetFilters">清空筛选条件后重新查询</el-button>
              </el-empty>
            </div>
          </template>

          <div v-if="list.data.value" class="lib-scroll-x">
            <el-table class="lib-table" :data="list.data.value.list" size="small" max-height="420"
              @row-click="onRowClick">
              <el-table-column v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label"
                :min-width="col.minWidth" :width="col.width" show-overflow-tooltip>
                <template #default="{ row }">
                  <template v-if="col.prop === 'verification_status'">
                    <el-tag size="small" effect="plain" :type="verificationTagType(row.verification_status)">
                      {{ row.verification_status }}
                    </el-tag>
                  </template>
                  <template v-else-if="col.prop === 'kb_version'">
                    <code class="mono">{{ fmt(row.kb_version) }}</code>
                  </template>
                  <template v-else-if="col.prop === '__action'">
                    <el-button text size="small" type="primary" :disabled="!canQuery"
                      @click.stop="openDetail(row, $event)">详情</el-button>
                  </template>
                  <template v-else>{{ fmt(row[col.prop]) }}</template>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div class="lib-pager">
            <el-pagination v-model:current-page="page" :page-size="safePageSize" :total="list.data.value?.total || 0"
              layout="total, prev, pager, next" small background :disabled="!canQuery" @current-change="runList" />
          </div>
          <div class="mr-disabled-hint" style="margin-top: 8px">
            doc_version_id 只来自列表响应的行；点击行或「详情」打开只读抽屉，详情不注册独立路由。
            分页 total / page / page_size 均来自后端响应，前端不伪造分页，也不缓存上一身份的数据。
            核验状态 pending = 待核验、verified = 已核验；自动提取 / pending 不标成已核验。
          </div>
        </AsyncPanel>
      </template>
    </el-card>

    <!-- 详情抽屉：不注册独立路由，关闭即清空，焦点回到触发行 -->
    <el-drawer v-model="drawer" :title="drawerTitle" size="720px" @close="onDrawerClose">
      <AsyncPanel :state="detailPanel.state" :error="detailPanel.error" @retry="detail.load()">
        <template v-if="detail.data.value">
          <el-descriptions :column="2" border size="small" class="lib-desc">
            <el-descriptions-item v-for="f in recordFields" :key="f.label" :label="f.label">
              <template v-if="f.key === 'verification_status'">
                <el-tag size="small" effect="plain" :type="verificationTagType(f.value)">{{ f.value }}</el-tag>
              </template>
              <template v-else>{{ fmt(f.value) }}</template>
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </AsyncPanel>

      <template v-if="detail.data.value">
        <!-- 原始 OCR 文本：纯文本 <pre>，禁止 v-html，与人工核验字段分框 -->
        <div class="lib-box lib-drawer-section">
          <div class="lib-box-title">原始 OCR 文本（text_status={{ detail.data.value.text_status }}）</div>
          <div class="mr-disabled-hint">{{ COPY.ocr }}</div>
          <pre class="lib-pre">{{ detail.data.value.original_text || COPY.nullField }}</pre>
        </div>

        <!-- 人工核验的结构化字段：与 OCR 单独分框 -->
        <div class="lib-box lib-drawer-section">
          <div class="lib-box-title">{{ isCase ? '人工核验的结构化字段（案例）' : '人工核验的结构化字段' }}</div>
          <template v-if="isCase">
            <div class="lib-field-grid">
              <div v-for="f in caseFields" :key="f.key" class="lib-field">
                <span class="lib-field-key">{{ f.label }}</span>
                <span class="lib-field-val">{{ f.value }}</span>
              </div>
            </div>
            <div class="mr-disabled-hint">{{ COPY.penalty }}</div>
            <div class="lib-box-title" style="margin-top: 10px">field_sources（后端原始字段）</div>
            <pre class="lib-pre">{{ pretty(caseStructured.field_sources) }}</pre>
          </template>
          <template v-else>
            <div v-if="detail.data.value.structured" class="lib-field-grid">
              <div v-for="f in genericStructuredFields" :key="f.key" class="lib-field">
                <span class="lib-field-key">{{ f.key }}</span>
                <span class="lib-field-val">{{ f.value }}</span>
              </div>
            </div>
            <div v-else class="lib-null">{{ COPY.nullField }}</div>
          </template>
          <div class="mr-disabled-hint">
            structured 为 null 或字段为 null 时显示「—（后端未返回，前端不补写）」，前端不补写、不推断；
            penalty_amount 是后端返回的精确十进制字符串，禁止数值转换、四舍五入或近似显示。
          </div>
        </div>

        <!-- 原始证据文件：source_url 仍需 Bearer，只走认证 Axios → Blob URL -->
        <div class="lib-box lib-drawer-section">
          <div class="lib-box-title">原始证据文件</div>
          <div class="source-hint">
            后端返回 source_url：<code class="mono">{{ detail.data.value.source_url }}</code>。该地址仍需 Bearer，
            绝不能直接塞进 iframe / img；原件字节由认证 Axios 读取后生成 Blob URL，切换对象或关闭抽屉时 revoke。
            source_file_id 来自列表行，不拼接推导。
          </div>
          <div class="lib-source-actions">
            <el-button size="small" :loading="sourceLoading" @click="viewSource">查看原件</el-button>
            <el-button size="small" @click="downloadOriginal">下载原件</el-button>
            <el-button v-if="sourceUrl" size="small" @click="releaseSource">关闭预览并释放 Blob URL</el-button>
          </div>
          <el-alert v-if="sourceError" type="error" :closable="false" title="原件读取失败" :description="sourceError" />
          <div v-if="sourceUrl" class="lib-source-frame">
            <iframe v-if="sourceKind === 'pdf'" :src="sourceUrl" title="原始 PDF 预览（已认证 Blob URL）" />
            <img v-else-if="sourceKind === 'image'" :src="sourceUrl" alt="原始图片预览（已认证 Blob URL）" />
            <div v-else class="lib-source-fallback">该格式后端仅支持授权下载，不提供内联预览。</div>
          </div>
        </div>

        <!-- 子列表：法规库 = 章节 / 条款（可进条款正文）；案例库 = 处罚依据引用 -->
        <div class="lib-box lib-drawer-section">
          <div class="lib-box-title">{{ isCase ? '处罚依据引用（references）' : '章节 / 条款' }}</div>
          <el-tabs v-model="activeTab" @tab-change="onTabChange">
            <el-tab-pane v-if="!isCase" label="章节（chapters）" name="chapters" />
            <el-tab-pane v-if="!isCase" label="条款（articles）" name="articles" />
            <el-tab-pane v-if="isCase" label="处罚依据引用（references）" name="references" />
          </el-tabs>
          <div class="mr-disabled-hint">{{ partsHint }}</div>
          <template v-if="partsRouteReady">
            <AsyncPanel :state="partsPanel.state" :error="partsPanel.error"
              empty-text="后端未返回子列表记录" @retry="loadCurrentParts">
              <div class="lib-scroll-x">
                <el-table class="lib-table" :data="partRows" size="small" max-height="260">
                  <template v-if="activeTab === 'chapters'">
                    <el-table-column prop="chapter_id" label="chapter_id" min-width="180" show-overflow-tooltip />
                    <el-table-column label="number" min-width="110"><template #default="{ row }">{{ fmt(row.number) }}</template></el-table-column>
                    <el-table-column label="title" min-width="200"><template #default="{ row }">{{ fmt(row.title) }}</template></el-table-column>
                    <el-table-column label="ordinal" width="100"><template #default="{ row }">{{ fmt(row.ordinal) }}</template></el-table-column>
                  </template>
                  <template v-else-if="activeTab === 'articles'">
                    <el-table-column prop="article_id" label="article_id" min-width="180" show-overflow-tooltip />
                    <el-table-column label="chapter_id" min-width="150"><template #default="{ row }">{{ fmt(row.chapter_id) }}</template></el-table-column>
                    <el-table-column label="number" min-width="100"><template #default="{ row }">{{ fmt(row.number) }}</template></el-table-column>
                    <el-table-column label="title" min-width="180"><template #default="{ row }">{{ fmt(row.title) }}</template></el-table-column>
                    <el-table-column label="ordinal" width="90"><template #default="{ row }">{{ fmt(row.ordinal) }}</template></el-table-column>
                    <el-table-column label="操作" width="110" fixed="right">
                      <template #default="{ row }">
                        <el-button text size="small" type="primary" :disabled="!articleRouteReady"
                          @click="openArticle(row)">条款正文</el-button>
                      </template>
                    </el-table-column>
                  </template>
                  <template v-else>
                    <el-table-column prop="reference_id" label="reference_id" min-width="160" show-overflow-tooltip />
                    <el-table-column label="law_version_id" min-width="150"><template #default="{ row }">{{ fmt(row.law_version_id) }}</template></el-table-column>
                    <el-table-column label="article_id" min-width="150"><template #default="{ row }">{{ fmt(row.article_id) }}</template></el-table-column>
                    <el-table-column label="citation" min-width="200"><template #default="{ row }">{{ fmt(row.citation) }}</template></el-table-column>
                    <el-table-column label="source" min-width="120"><template #default="{ row }">{{ fmt(row.source) }}</template></el-table-column>
                    <el-table-column label="method" min-width="120"><template #default="{ row }">{{ fmt(row.method) }}</template></el-table-column>
                    <el-table-column label="核验状态" width="120">
                      <template #default="{ row }">
                        <el-tag size="small" effect="plain" :type="verificationTagType(row.verification_status)">
                          {{ fmt(row.verification_status) }}
                        </el-tag>
                      </template>
                    </el-table-column>
                  </template>
                </el-table>
              </div>
              <div class="lib-pager">
                <el-pagination v-model:current-page="partPage" :page-size="partPageSize"
                  :total="parts.data.value?.total || 0" layout="total, prev, pager, next" small background
                  @current-change="loadCurrentParts" />
              </div>
            </AsyncPanel>
          </template>
          <div v-else class="lib-gate-mini">
            <el-tag type="warning" effect="plain">运行期未加载该子接口</el-tag>
            <p class="lib-lead">GET {{ currentPartsPath }} 未在运行期契约中声明，本页不发起该子列表请求，也不展示演示数据。</p>
          </div>
        </div>

        <!-- 条款正文：仅法规库；doc_version_id 取自列表行、article_id 取自条款行 -->
        <div v-if="!isCase" class="lib-box lib-drawer-section">
          <div class="lib-box-title">条款正文（GET /api/library/laws/{doc_version_id}/articles/{article_id}）</div>
          <div v-if="!articleRouteReady" class="lib-gate-mini">
            <el-tag type="warning" effect="plain">运行期未加载条款正文接口</el-tag>
            <p class="lib-lead">该接口未在运行期契约中声明，本页不发起条款正文请求。</p>
          </div>
          <template v-else>
            <div v-if="!activeArticleId" class="mr-disabled-hint">
              点击上方「条款」列表里的「条款正文」按钮，加载后端按 raw_start / raw_end 切片后的原文；前端不自行截取原文。
            </div>
            <AsyncPanel :state="articlePanel.state" :error="articlePanel.error"
              empty-text="后端未返回条款正文" @retry="articleBody.load()">
              <template v-if="articleBody.data.value">
                <div class="lib-field-grid">
                  <div v-for="f in articleFields" :key="f.key" class="lib-field">
                    <span class="lib-field-key">{{ f.label }}</span>
                    <span class="lib-field-val">{{ f.value }}</span>
                  </div>
                </div>
                <div class="mr-disabled-hint">{{ COPY.charRange }}</div>
                <div class="lib-box-title" style="margin-top: 10px">原始 OCR 文本（后端已按字符范围切片）</div>
                <div class="mr-disabled-hint">{{ COPY.ocr }}</div>
                <pre class="lib-pre">{{ articleBody.data.value.original_text || COPY.nullField }}</pre>
              </template>
            </AsyncPanel>
          </template>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { useAppStore } from '@/stores/app'
import { hasToken } from '@/api/client'
import { apiErrorHint } from '@/api/errors'
import {
  contractLabel, contractMeta, contractState, hasLibraryRoute, probeContract
} from '@/api/dataSource'
import { isAdminIdentity, principal } from '@/api/principal'
import {
  createSourceUrl, downloadSourceFile, getSourceFile, isValidFileId, revokeSourceUrl,
  type SourceKind
} from '@/api/documentFiles'
import {
  LIBRARY_ARTICLE_PATH, LIBRARY_ARTICLES_PATH, LIBRARY_CHAPTERS_PATH, LIBRARY_LIST_PATHS,
  LIBRARY_REFERENCES_PATH, LIBRARY_ROUTES, getLibraryArticle, getLibraryCase, getLibraryLaw,
  listLibraryArticles, listLibraryCases, listLibraryChapters, listLibraryLaws, listLibraryReferences
} from '@/api/library'
import type {
  LibraryArticle, LibraryArticleStructured, LibraryCaseStructured, LibraryChapter,
  LibraryDetail, LibraryKind, LibraryList, LibraryParts, LibraryQuery, LibraryRecord,
  LibraryReference, LoadState
} from '@/api/types'

/**
 * v0.2.3 draft-5 法规库 / 处罚案例库共用只读骨架。
 *
 * 状态机（互不复用）：
 *  未配置凭证 / 契约探测中 / 契约未就绪 / 401 / 路由未加载（禁用，不发请求）
 *  → 已加载-unpublished（合法空态）/ 已加载-ready 但空 / ready 有数据
 *  → 401 / 404 / 422 / 503（el-alert type=error 常显）/ 加载中 / 请求取消。
 *
 * 门控：useAsyncData({ immediate: false }) + watch(routeReady)；routeReady =
 * hasRuntimeMethod('GET', 列表路径)。未加载时渲染自定义卡片，不用 AsyncPanel 的
 * outdated 分支（那是「运行期探测失败」，本例是探测成功但路由未声明）。
 * 404/422/503 在 api/library.ts 内归一化为 kind='error'，不误报 outdated。
 *
 * 差异由 kind 决定：法规库不渲染也不发送 violation，详情含章节 / 条款 / 条款正文；
 * 案例库多 violation 筛选，详情含处罚依据引用与案例结构化字段（含精确十进制罚款金额）。
 */
const props = defineProps<{ kind: LibraryKind }>()

const isCase = computed(() => props.kind === 'case')
const listPath = computed(() => LIBRARY_LIST_PATHS[props.kind])
const store = useAppStore()

/** 契约文案（Phase 2 定稿，直接使用，不改写） */
const COPY = {
  notLoaded: (path: string) =>
    `运行期未加载该接口（GET ${path}）：活动实例仍是旧契约，本页不发起请求、不展示演示数据。切换镜像须经授权并由 Agent C 交付候选。`,
  unpublished: '当前 public 知识库无 ACTIVE 版本，后端合法返回 status=unpublished / 空列表。这不是错误，也不代表"没有法规"，只是尚未发布可检索版本。',
  readyEmpty: '本次筛选没有匹配的记录。可清空筛选条件后重新查询。',
  ocr: '以下为原始 OCR 文本（text_status=ocr_not_manually_verified），未经人工核验，不得作为法律事实引用；人工核验的结构化字段在下方单独展示。',
  charRange: 'raw_start / raw_end 是零基、左闭右开的字符范围（非字节偏移），由后端按条款定位切片，前端不自行截取原文。',
  nullField: '—（后端未返回，前端不补写）',
  penalty: '罚款金额为后端返回的精确十进制字符串，未做数值转换或四舍五入。',
  notConfigured: '未配置 API Token / 会话凭证：所有 /api/* 请求会被后端拒绝（401），本页不发起请求。请在系统监控页配置有效会话凭证。',
  contract401: '未认证 / 无权限（401）：凭证无效、被停用 / 撤销或已过期。已清除本页列表与详情状态，请重新配置有效会话凭证后重试。'
}

/** null / 空值如实显示，不补写、不推断；绝不把 null 当空数据错误 */
function fmt(value: unknown): string {
  if (value === null || value === undefined || value === '') return COPY.nullField
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
function pretty(value: unknown): string {
  if (value === null || value === undefined || value === '') return COPY.nullField
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

/** pending = info、verified = success；其余一律 warning，绝不把待核验标成已核验 */
function verificationTagType(value: unknown): 'info' | 'success' | 'warning' {
  if (value === 'verified') return 'success'
  if (value === 'pending') return 'info'
  return 'warning'
}

/* ───────── 运行期门控 ───────── */

const hasCredential = computed(() => !!store.token || hasToken())
const routeReady = computed(() => hasLibraryRoute(listPath.value))

type Gate =
  | 'no-token' | 'contract-pending' | 'contract-not-ready' | 'contract-401'
  | 'route-not-loaded' | 'ready'

const gate = computed<Gate>(() => {
  if (!hasCredential.value) return 'no-token'
  if (routeReady.value) return 'ready'
  if (contractState.value === 'unknown') return 'contract-pending'
  if (contractState.value === 'no-permission') return 'contract-401'
  if (contractState.value === 'ready') return 'route-not-loaded'
  return 'contract-not-ready'
})

const gateTagText = computed(() => ({
  'no-token': '未配置凭证',
  'contract-pending': '契约探测中',
  'contract-not-ready': '契约未就绪',
  'contract-401': '未认证',
  'route-not-loaded': '接口未加载',
  ready: ''
}[gate.value]))

const gateTitle = computed(() => ({
  'no-token': '未配置会话凭证',
  'contract-pending': '运行期契约探测中',
  'contract-not-ready': '运行期契约未就绪',
  'contract-401': '未认证 / 无权限',
  'route-not-loaded': '运行期未加载该接口',
  ready: ''
}[gate.value]))

const gateLead = computed(() => {
  switch (gate.value) {
    case 'no-token': return COPY.notConfigured
    case 'contract-pending':
      return '正在等待运行期 GET /api/openapi.json 探测结果；探测完成前本页不发起任何业务请求，也不展示演示数据。'
    case 'contract-not-ready':
      return `运行期契约未就绪（${contractLabel.value[contractState.value]}）：${contractMeta.value.hint}。本页不发起业务请求。`
    case 'route-not-loaded': return COPY.notLoaded(listPath.value)
    default: return ''
  }
})

const gateNote = computed(() =>
  '状态语义严格分离：接口未加载 = 警告标签 + 控件禁用；unpublished 是合法空态（不是错误）；' +
  '401 / 404 / 422 / 503 是错误态常显。禁用态同时提供文字说明与控件 disabled，不只靠颜色；' +
  '本页不把自动提取 / pending 标成已核验，不把后端空数组当错误。'
)

/** 只有门控通过才允许查询；加载中仍可改筛选，由 useAsyncData 用 AbortSignal 取消上一次请求 */
const canQuery = computed(() => gate.value === 'ready')

function routeStatus(path: string): 'loaded' | 'missing' | 'unknown' {
  if (contractState.value !== 'ready') return 'unknown'
  return hasLibraryRoute(path) ? 'loaded' : 'missing'
}
const routeRows = computed(() => LIBRARY_ROUTES.map((route) => {
  const status = routeStatus(route.path)
  return {
    method: route.method,
    path: route.path,
    page: route.page,
    status,
    statusText: status === 'loaded' ? '已加载' : status === 'missing' ? '未加载' : '未探测'
  }
}))

/* ───────── 筛选白名单 ───────── */

const draft = reactive({ query: '', violation: '', kbVersion: '' })
const applied = ref<{ query?: string; violation?: string; kbVersion?: string }>({})
const page = ref(1)
const pageSize = ref(20)

/** 非 ADMIN 一律不发送 kb_version（传了会 403） */
const effectiveKb = computed(() => (isAdminIdentity.value ? applied.value.kbVersion : undefined))
/** el-input-number 清空时可能给出非数值；这里统一收敛到 1..100，避免非法 page_size 触发 422 */
const safePageSize = computed(() =>
  typeof pageSize.value === 'number' && Number.isFinite(pageSize.value)
    ? Math.min(Math.max(Math.floor(pageSize.value), 1), 100)
    : 20
)

const filterHint = computed(() => {
  const parts: string[] = []
  if (isCase.value) {
    parts.push('案例库支持 violation（≤200 字符）；其它参数均为契约白名单字段，空值一律不发送。')
  } else {
    parts.push('法规库不渲染也不发送 violation 参数（后端会返回 422 violation_filter_case_only）；筛选仅 query / kb_version / page / page_size。')
  }
  parts.push(isAdminIdentity.value
    ? '当前身份为 ADMIN：可显式填写 kb_version（1..128）。'
    : '仅 ADMIN 可显式选择版本：kb_version 输入已禁用，其他角色传了会返回 403。')
  parts.push('page_size 限制 1..100；请求参数用白名单构造，空值一律 undefined 不发送（避免 422）。')
  parts.push('禁用态同时提供文字说明与控件 disabled，不只靠颜色。')
  return parts.join(' ')
})

function buildQuery(): LibraryQuery {
  return {
    page: page.value,
    pageSize: safePageSize.value,
    query: applied.value.query,
    violation: isCase.value ? applied.value.violation : undefined,
    kbVersion: effectiveKb.value
  }
}

const list = useAsyncData<LibraryList>(
  (signal) => (isCase.value ? listLibraryCases(buildQuery(), signal) : listLibraryLaws(buildQuery(), signal)),
  { immediate: false }
)

const panelState = computed<LoadState>(() => {
  const s = list.state.value
  return s === 'no-permission' || s === 'outdated' ? 'error' : s
})
const panelError = computed(() => list.error.value ||
  (list.state.value === 'no-permission'
    ? '未认证 / 无权限（401 / 403）：凭证无效或当前身份无权访问，请重新配置有效会话凭证。'
    : ''))

const isEmptyUnpublished = computed(() => list.data.value?.status === 'unpublished')

function runList() {
  canceledNotice.value = ''
  if (!routeReady.value || !hasCredential.value) return
  void list.load()
}

function applyFilters() {
  if (!canQuery.value) return
  page.value = 1
  applied.value = {
    query: draft.query.trim() || undefined,
    violation: isCase.value ? (draft.violation.trim() || undefined) : undefined,
    kbVersion: isAdminIdentity.value ? (draft.kbVersion.trim() || undefined) : undefined
  }
  runList()
}

function resetFilters() {
  draft.query = ''
  draft.violation = ''
  draft.kbVersion = ''
  applied.value = {}
  page.value = 1
  if (canQuery.value) runList()
}

async function reprobe() {
  if (!hasToken()) return
  await probeContract(true)
}

/* ───────── 列表呈现 ───────── */

interface LibColumn { prop: string; label: string; minWidth?: number; width?: number }
const columns = computed<LibColumn[]>(() => [
  { prop: 'title', label: isCase.value ? '案例标题' : '法规标题', minWidth: 240 },
  { prop: 'number', label: isCase.value ? '案号' : '文号', minWidth: 140 },
  { prop: 'category', label: '分类', minWidth: 120 },
  ...(isCase.value
    ? [{ prop: 'published_on', label: '发布时间', minWidth: 140 }]
    : [{ prop: 'authority', label: '发布机关', minWidth: 160 }, { prop: 'effective_status', label: '效力状态', minWidth: 120 }]),
  { prop: 'verification_status', label: '核验状态', width: 120 },
  { prop: 'kb_version', label: 'kb_version', width: 150 },
  { prop: '__action', label: '操作', width: 90 }
])

const listTitle = computed(() => (isCase.value ? '处罚案例列表' : '法规列表'))
const listMeta = computed(() => {
  const d = list.data.value
  return d
    ? `GET ${listPath.value} · status=${d.status} · kb_version=${d.kb_version || '—'} · total=${d.total} · page=${d.page}/${d.page_size}`
    : `GET ${listPath.value} · 尚未加载`
})

/* ───────── 详情 / 子列表 / 条款正文 ───────── */

const drawer = ref(false)
const activeRecord = ref<LibraryRecord | null>(null)
const activeTab = ref<'chapters' | 'articles' | 'references'>(isCase.value ? 'references' : 'chapters')
const partPage = ref(1)
const partPageSize = 20
const activeArticleId = ref('')
let triggerEl: HTMLElement | null = null

const currentPartsPath = computed(() => {
  if (isCase.value) return LIBRARY_REFERENCES_PATH
  return activeTab.value === 'chapters' ? LIBRARY_CHAPTERS_PATH : LIBRARY_ARTICLES_PATH
})
const partsRouteReady = computed(() => hasLibraryRoute(currentPartsPath.value))
const articleRouteReady = computed(() => hasLibraryRoute(LIBRARY_ARTICLE_PATH))

const detail = useAsyncData<LibraryDetail>((signal) => {
  const id = activeRecord.value?.doc_version_id || ''
  const q = { kbVersion: effectiveKb.value }
  return isCase.value ? getLibraryCase(id, q, signal) : getLibraryLaw(id, q, signal)
}, { immediate: false })

const parts = useAsyncData<LibraryParts<LibraryChapter | LibraryArticle | LibraryReference>>((signal) => {
  const id = activeRecord.value?.doc_version_id || ''
  const q = { page: partPage.value, pageSize: partPageSize, kbVersion: effectiveKb.value }
  if (isCase.value) return listLibraryReferences(id, q, signal)
  return activeTab.value === 'chapters'
    ? listLibraryChapters(id, q, signal)
    : listLibraryArticles(id, q, signal)
}, { immediate: false })

const articleBody = useAsyncData<LibraryDetail>((signal) =>
  getLibraryArticle(activeRecord.value?.doc_version_id || '', activeArticleId.value,
    { kbVersion: effectiveKb.value }, signal),
  { immediate: false }
)

/** 401 / 403 / 404 等一律走 AsyncPanel 的 error（type=error 常显）分支，不用 outdated */
function toErrorPanel(state: LoadState, error: string): { state: LoadState; error: string } {
  if (state === 'no-permission' || state === 'outdated') {
    return {
      state: 'error',
      error: error || '未认证 / 无权限或资源不存在（401 / 403 / 404）：以统一错误态呈现，不隐藏错误。'
    }
  }
  return { state, error }
}
const detailPanel = computed(() => toErrorPanel(detail.state.value, detail.error.value))
const partsPanel = computed(() => toErrorPanel(parts.state.value, parts.error.value))
const articlePanel = computed(() => toErrorPanel(articleBody.state.value, articleBody.error.value))

const partRows = computed(() => (parts.data.value?.list || []) as unknown as Record<string, unknown>[])
const partsHint = computed(() => isCase.value
  ? '引用列表仅展示后端返回的 citation / source / method / verification_status；law_version_id 不是 doc_version_id，本页不据此拼接条款正文请求。子列表分页来自后端 LibraryParts。'
  : '章节 / 条款分页来自后端 LibraryParts；条款正文的 doc_version_id 取自列表行、article_id 取自条款行，均由后端返回，不拼接推导。')

function rememberTrigger(el: HTMLElement | null) {
  if (!el) return
  triggerEl = el
  if (el.tabIndex < 0) el.tabIndex = -1
}

function resetDrawerData() {
  detail.cancel()
  parts.cancel()
  articleBody.cancel()
  releaseSource()
  activeArticleId.value = ''
  partPage.value = 1
  detail.data.value = null; detail.error.value = ''; detail.state.value = 'empty'
  parts.data.value = null; parts.error.value = ''; parts.state.value = 'empty'
  articleBody.data.value = null; articleBody.error.value = ''; articleBody.state.value = 'empty'
  sourceError.value = ''
}

function loadCurrentParts() {
  if (!drawer.value || !activeRecord.value || !partsRouteReady.value) return
  void parts.load()
}

function openDetail(row: LibraryRecord, event?: MouseEvent) {
  if (!row || !row.doc_version_id || !canQuery.value) return
  if (event) rememberTrigger(event.currentTarget as HTMLElement | null)
  resetDrawerData()
  activeRecord.value = row
  activeTab.value = isCase.value ? 'references' : 'chapters'
  drawer.value = true
  void detail.load()
  loadCurrentParts()
}

function onRowClick(row: LibraryRecord, _column: unknown, event: MouseEvent) {
  // 行内「详情」按钮已 @click.stop；这里再兜底一次，避免焦点回到行而不是按钮
  if ((event?.target as HTMLElement | null)?.closest('button')) return
  rememberTrigger((event?.target as HTMLElement | null)?.closest('.el-table__row') as HTMLElement | null)
  openDetail(row)
}

function onTabChange() {
  partPage.value = 1
  activeArticleId.value = ''
  parts.cancel()
  articleBody.cancel()
  parts.data.value = null; parts.error.value = ''; parts.state.value = 'empty'
  articleBody.data.value = null; articleBody.error.value = ''; articleBody.state.value = 'empty'
  loadCurrentParts()
}

function openArticle(row: Record<string, unknown>) {
  if (!articleRouteReady.value) return
  const id = String(row.article_id || '')
  if (!id) return
  activeArticleId.value = id
  void articleBody.load()
}

function onDrawerClose() {
  resetDrawerData()
  activeRecord.value = null
  drawer.value = false
  const el = triggerEl
  triggerEl = null
  if (el) void nextTick(() => el.focus())
}

const recordFields = computed(() => {
  const r = activeRecord.value
  if (!r) return []
  const entries: Array<[string, string, unknown]> = [
    ['doc_version_id', 'doc_version_id', r.doc_version_id],
    ['kind', 'kind', r.kind],
    ['title', 'title', r.title],
    ['number', 'number（文号 / 案号）', r.number],
    ['category', 'category', r.category],
    ['authority', 'authority（发布机关）', r.authority],
    ['published_on', 'published_on', r.published_on],
    ['effective_on', 'effective_on', r.effective_on],
    ['repealed_on', 'repealed_on', r.repealed_on],
    ['effective_status', 'effective_status', r.effective_status],
    ['verification_status', 'verification_status（核验状态）', r.verification_status],
    ['owner_id', 'owner_id', r.owner_id],
    ['document_id', 'document_id', r.document_id],
    ['source_file_id', 'source_file_id', r.source_file_id],
    ['parse_id', 'parse_id', r.parse_id],
    ['kb_version', 'kb_version', r.kb_version]
  ]
  return entries.map(([key, label, value]) => ({ key, label, value }))
})

const caseStructured = computed(() => (detail.data.value?.structured || {}) as LibraryCaseStructured)
const caseFields = computed(() => {
  const s = caseStructured.value
  return [
    { key: 'region', label: 'region（地域）', value: fmt(s.region) },
    { key: 'violation', label: 'violation（违法行为）', value: fmt(s.violation) },
    { key: 'facts', label: 'facts（事实）', value: fmt(s.facts) },
    { key: 'investigation', label: 'investigation（调查）', value: fmt(s.investigation) },
    { key: 'evidence_summary', label: 'evidence_summary（证据摘要）', value: fmt(s.evidence_summary) },
    { key: 'penalty_type', label: 'penalty_type（处罚类型）', value: fmt(s.penalty_type) },
    { key: 'penalty_amount', label: 'penalty_amount（精确十进制字符串）', value: fmt(s.penalty_amount) },
    { key: 'penalty_result', label: 'penalty_result（处罚结果）', value: fmt(s.penalty_result) }
  ]
})
const genericStructuredFields = computed(() =>
  Object.entries(detail.data.value?.structured || {}).map(([key, value]) => ({ key, value: pretty(value) }))
)

const articleFields = computed(() => {
  const s = (articleBody.data.value?.structured || {}) as LibraryArticleStructured
  return [
    { key: 'article_id', label: 'article_id', value: fmt(s.article_id) },
    { key: 'chapter_id', label: 'chapter_id', value: fmt(s.chapter_id) },
    { key: 'number', label: 'number', value: fmt(s.number) },
    { key: 'title', label: 'title', value: fmt(s.title) },
    { key: 'ordinal', label: 'ordinal', value: fmt(s.ordinal) },
    { key: 'raw_start', label: 'raw_start（字符位置，零基）', value: fmt(s.raw_start) },
    { key: 'raw_end', label: 'raw_end（字符位置，左闭右开）', value: fmt(s.raw_end) },
    { key: 'page_start', label: 'page_start', value: fmt(s.page_start) },
    { key: 'page_end', label: 'page_end', value: fmt(s.page_end) },
    { key: 'chunk_ids', label: 'chunk_ids[]', value: pretty(s.chunk_ids) }
  ]
})

const drawerTitle = computed(() =>
  `${isCase.value ? '处罚案例详情' : '法规详情'} · ${activeRecord.value?.title || ''}`
)

/* ───────── 原始证据文件（Blob URL 生命周期） ───────── */

const sourceUrl = ref('')
const sourceKind = ref<SourceKind>('other')
const sourceError = ref('')
const sourceLoading = ref(false)
let sourceCtrl: AbortController | null = null

function releaseSource() {
  if (sourceCtrl) { sourceCtrl.abort(); sourceCtrl = null }
  if (sourceUrl.value) { revokeSourceUrl(sourceUrl.value); sourceUrl.value = '' }
  sourceKind.value = 'other'
  sourceLoading.value = false
}

async function viewSource() {
  releaseSource()
  sourceError.value = ''
  const rec = activeRecord.value
  const d = detail.data.value
  if (!rec || !d) return
  if (!isValidFileId(rec.source_file_id)) {
    sourceError.value = 'source_file_id 不是合规的上传文件 ID（后端未返回合规值），不拼接推导 ID，未发起原件请求'
    return
  }
  const ctrl = new AbortController()
  sourceCtrl = ctrl
  sourceLoading.value = true
  try {
    // 认证 Axios ArrayBuffer → Blob URL；source_url 绝不直接塞进 iframe / img
    const file = await getSourceFile(rec.source_file_id, d.original_file_name, ctrl.signal)
    if (ctrl.signal.aborted) return
    sourceUrl.value = createSourceUrl(file)
    sourceKind.value = file.kind
  } catch (err) {
    if (ctrl.signal.aborted) return
    sourceError.value = apiErrorHint(err)
  } finally {
    if (sourceCtrl === ctrl) { sourceCtrl = null; sourceLoading.value = false }
  }
}

async function downloadOriginal() {
  const rec = activeRecord.value
  const d = detail.data.value
  if (!rec || !d) return
  try {
    await downloadSourceFile(rec.source_file_id, d.original_file_name || rec.source_file_id)
  } catch (err) {
    sourceError.value = apiErrorHint(err)
  }
}

/* ───────── 身份 / 凭证变化时清空，避免跨身份残留 ───────── */

const canceledNotice = ref('')

function resetBrowser(reason: string) {
  list.cancel()
  resetDrawerData()
  drawer.value = false
  activeRecord.value = null
  triggerEl = null
  list.data.value = null
  list.error.value = ''
  list.state.value = 'empty'
  canceledNotice.value = `${reason}：上一次请求已取消，列表与详情状态已清空，不保留上一身份的数据。`
}

/** routeReady 变 false（凭证失效 / 契约回退 / 路由撤销）时清空并取消在途请求 */
watch(routeReady, (ok, was) => {
  if (ok) runList()
  else if (was) resetBrowser('运行期契约或路由不再可用')
}, { immediate: true })

/** 身份切换（非首次确认）：清空并按新身份重新查询 */
watch(() => principal.value?.principal_id ?? '', (now, was) => {
  if (!was || !now || now === was) return
  resetBrowser('当前登录身份已切换')
  if (routeReady.value) runList()
})

watch(() => store.token, (token) => {
  if (!token) resetBrowser('会话凭证已清除')
})

const liveText = computed(() => {
  switch (gate.value) {
    case 'no-token': return '未配置凭证：未发起请求'
    case 'contract-pending': return '运行期契约探测中'
    case 'contract-401': return '401 未认证 / 无权限'
    case 'contract-not-ready': return '运行期契约未就绪'
    case 'route-not-loaded': return '运行期未加载该接口：本页不发起请求'
    default: break
  }
  if (canceledNotice.value) return `请求已取消：${canceledNotice.value}`
  if (list.loading.value) return '正在从后端加载真实数据…'
  if (list.state.value === 'empty') {
    return isEmptyUnpublished.value ? '合法空态：status=unpublished' : '本次筛选没有匹配的记录'
  }
  if (list.state.value === 'ready') return `已加载 ${list.data.value?.list.length || 0} 条真实记录`
  return `请求失败：${panelError.value}`
})

/** 直接刷新本页时先探测运行期契约，避免 contractState=unknown 导致门控死锁 */
onMounted(async () => {
  if (!hasToken()) return
  if (contractState.value !== 'ready') await probeContract()
})

onBeforeUnmount(() => {
  releaseSource()
  triggerEl = null
})
</script>
