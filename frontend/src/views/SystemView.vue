<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">系统监控</h1>
        <p class="page-desc">服务状态（五态）、API Token 配置、接口调用与操作审计</p>
      </div>
      <el-tag type="warning" effect="plain">{{ releaseStatus.shortLabel }}</el-tag>
    </div>

    <!-- FastAPI：唯一真实探测 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>后端解析服务（FastAPI · 127.0.0.1:8180）<span class="real-badge">REAL</span></span>
          <el-button size="small" @click="store.probeBackend()">重新探测</el-button>
        </div>
      </template>
      <div class="conn-row">
        <span class="mr-state-tag" :class="`mr-state-${store.apiState}`">
          <span class="status-dot" :style="{ background: stateColor }" />{{ store.apiState }}
        </span>
        <span class="conn-note">{{ stateLabel }}</span>
      </div>
      <el-descriptions v-if="store.serviceInfo" :column="3" border size="small" style="margin-top: 12px">
        <el-descriptions-item label="provider">{{ store.serviceInfo.provider }}</el-descriptions-item>
        <el-descriptions-item label="mode">{{ store.serviceInfo.mode }}</el-descriptions-item>
        <el-descriptions-item label="enabled">{{ store.serviceInfo.enabled }}</el-descriptions-item>
        <el-descriptions-item label="dual_engine_enabled">{{ store.serviceInfo.dual_engine_enabled }}</el-descriptions-item>
        <el-descriptions-item label="database_enabled">{{ store.serviceInfo.database_enabled }}</el-descriptions-item>
        <el-descriptions-item label="字段来源">GET /api/parse/info</el-descriptions-item>
      </el-descriptions>
      <div v-else class="mr-disabled-hint" style="margin-top: 10px">
        尚未成功探测 /api/parse/info。后端不返回 version / environment 字段，本页不再展示不存在的版本与环境信息。
      </div>

      <el-divider />

      <div class="token-form">
        <el-input
          v-model="tokenInput"
          type="password"
          show-password
          placeholder="粘贴 PARSING_API_TOKENS_JSON 中配置的 Token（≥32 位）"
          style="max-width: 480px"
          @keyup.enter="saveToken"
        />
        <el-button type="primary" @click="saveToken">保存并验证</el-button>
      </div>
      <div class="security-note">
        <div><b>开发期</b>：Token 仅存于<b>内存 + sessionStorage（会话级）</b>，关闭标签页即失效；不写 localStorage、不打印到控制台或日志；请求经 Vite 代理直达后端。</div>
        <div><b>生产环境</b>：应由服务端下发安全会话（HttpOnly Cookie / BFF），前端不长期持有访问 Token。</div>
        <div><b>密钥边界</b>：MinerU 官方 API Key、数据库口令一律只存在 FastAPI 后端，浏览器绝不接触；当前存储方式：{{ tokenStorageMode }}。</div>
      </div>
    </el-card>

    <!-- 六组件五态 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>组件状态</span>
          <span class="card-sub">只有真实探测成功才允许 ONLINE · 其余为 UNKNOWN / NOT_CONFIGURED</span>
        </div>
      </template>
      <el-table :data="componentRows" size="default">
        <el-table-column prop="name" label="组件" width="160" />
        <el-table-column label="状态" width="170">
          <template #default="{ row }">
            <span class="mr-state-tag" :class="`mr-state-${effectiveState(row)}`">
              <span class="status-dot" :style="{ background: stateColorOf(effectiveState(row)) }" />
              {{ effectiveState(row) }}
            </span>
            <DemoBadge v-if="!row.realProbe" />
          </template>
        </el-table-column>
        <el-table-column prop="deploy" label="部署方式" width="180" />
        <el-table-column prop="note" label="说明" />
      </el-table>
    </el-card>

    <!-- 接口接入状态总览：计数直接来自 apiCapabilities，不伪造探测结果 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>接口接入状态总览 <span class="real-badge">REAL</span></span>
          <span class="card-sub">
            已接入 {{ realCount }} 个 · 待交付 {{ pendingCount }} 组 · 契约复核 2026-11-11（{{ releaseStatus.apiContractReview }}）
          </span>
        </div>
      </template>
      <el-tabs v-model="apiTab">
        <el-tab-pane :label="`已接入（${realCount}）`" name="real">
          <el-table :data="realApiRows" size="small">
            <el-table-column prop="method" label="方法" width="80" />
            <el-table-column prop="path" label="路径" min-width="290" />
            <el-table-column prop="page" label="使用页面" min-width="180" />
            <el-table-column label="来源" width="100">
              <template #default><span class="real-badge">REAL</span></template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`待交付（${pendingCount}）`" name="pending">
          <el-table :data="pendingApiRows" size="small">
            <el-table-column label="优先级" width="90">
              <template #default="{ row }">
                <el-tag :type="row.priority === 'P0' ? 'danger' : 'info'" size="small" effect="plain">{{ row.priority }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="path" label="建议接口" min-width="300" show-overflow-tooltip />
            <el-table-column prop="usage" label="解锁能力" min-width="220" show-overflow-tooltip />
            <el-table-column label="状态" width="100">
              <template #default><span class="mr-disabled-hint">未接入</span></template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
      <div class="mr-disabled-hint" style="margin-top: 10px">
        本表计数取自前端能力开关 apiCapabilities，仅反映后端路由源码事实；不代表这些接口已在运行中的实例上探测成功（探活需要有效 Token）。
        完整字段契约见 frontend/docs/frontend-api-mapping.md 与 backend-api-requirements.md。
      </div>
    </el-card>

    <!-- 系统资源 / 接口调用 / 错误日志：接口未接入，明确标注 -->
    <div class="card-grid" style="grid-template-columns: repeat(3, 1fr); margin-top: 16px">
      <el-card v-for="m in missingModules" :key="m.title" shadow="never">
        <template #header>
          <div class="card-head"><span>{{ m.title }}</span><DemoBadge /></div>
        </template>
        <el-empty :image-size="54" :description="m.hint">
          <span class="mr-disabled-hint">{{ m.api }}</span>
        </el-empty>
      </el-card>
    </div>

    <!-- 操作审计 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>操作审计日志 <DemoBadge /></span>
          <span class="card-sub">后端审计接口未接入，以下为演示记录，不代表真实发生的操作</span>
        </div>
      </template>
      <el-table :data="auditLog" size="small">
        <el-table-column prop="time" label="时间" width="160" />
        <el-table-column prop="operator" label="操作人" width="100" />
        <el-table-column prop="action" label="操作" width="130" />
        <el-table-column prop="target" label="对象" min-width="240" show-overflow-tooltip />
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <span :style="{ color: row.result === '成功' ? 'var(--mr-st-success)' : 'var(--mr-st-danger)' }">{{ row.result }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="来源 IP" width="120" />
      </el-table>
    </el-card>

    <el-alert
      type="warning"
      :closable="false"
      style="margin-top: 16px"
      :title="releaseStatus.alertTitle"
      :description="releaseStatus.alertDescription"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import DemoBadge from '@/components/DemoBadge.vue'
import { useAppStore } from '@/stores/app'
import { tokenStorageMode } from '@/api/client'
import { apiCapabilities } from '@/api/dataSource'
import { releaseStatus } from '@/config/release'
import { fetchAuditLog, type AuditRecord } from '@/api/mock/system'
import type { ComponentState } from '@/api/types'

const store = useAppStore()
const tokenInput = ref(store.token)
const auditLog = ref<AuditRecord[]>([])

const STATE_COLOR: Record<ComponentState, string> = {
  ONLINE: 'var(--mr-state-online)',
  OFFLINE: 'var(--mr-state-offline)',
  NOT_CONFIGURED: 'var(--mr-state-not-configured)',
  UNKNOWN: 'var(--mr-state-unknown)',
  ERROR: 'var(--mr-state-error)'
}

function stateColorOf(s: ComponentState): string {
  return STATE_COLOR[s]
}
const stateColor = computed(() => STATE_COLOR[store.apiState])
const stateLabel = computed(() => {
  if (store.apiState === 'ONLINE') return '真实探活成功（/api/parse/info 返回 200）'
  if (store.apiState === 'OFFLINE') return '探活失败 — 请确认 scripts/start_parsing_app.ps1 已运行、Token 有效'
  return '尚未探测（未配置 Token 或未发起请求）'
})

interface ComponentRow {
  name: string
  state: ComponentState
  realProbe: boolean
  deploy: string
  note: string
}
const componentRows: ComponentRow[] = [
  { name: 'FastAPI', state: 'UNKNOWN', realProbe: true, deploy: '本地 8180 端口', note: '解析 API 主服务，真实探活' },
  { name: 'PostgreSQL', state: 'UNKNOWN', realProbe: false, deploy: 'Docker compose', note: '无探活接口，状态未知' },
  { name: 'PaddleOCR', state: 'UNKNOWN', realProbe: false, deploy: '本地模型', note: '无探活接口，状态未知' },
  { name: 'PP-StructureV3', state: 'UNKNOWN', realProbe: false, deploy: '本地模型', note: '无探活接口，状态未知' },
  { name: 'MinerU API', state: 'NOT_CONFIGURED', realProbe: false, deploy: '官方云端（仅后端调用）', note: '未从前端配置凭证，不得标为在线' },
  { name: 'BGE-M3', state: 'UNKNOWN', realProbe: false, deploy: '本地模型', note: '无探活接口，状态未知' }
]

function effectiveState(row: ComponentRow): ComponentState {
  return row.realProbe ? store.apiState : row.state
}

const missingModules = [
  { title: '系统资源', hint: '接口未接入', api: 'GET /api/system/resources' },
  { title: '接口调用记录', hint: '接口未接入', api: 'GET /api/system/api-logs' },
  { title: '错误日志', hint: '接口未接入', api: 'GET /api/system/error-logs' }
]

/** 接口接入总览：计数取自能力开关，行数据来自 2026-11-11 复核的路由源码 */
const apiTab = ref('real')
const realCount = computed(() => Object.values(apiCapabilities).filter(Boolean).length)
const pendingCount = computed(() => Object.values(apiCapabilities).filter((v) => !v).length)

interface ApiRow { method: string; path: string; page: string }
const realApiRows: ApiRow[] = [
  { method: 'GET', path: '/api/parse/info', page: '工作台 / 解析中心 / 系统监控' },
  { method: 'POST', path: '/api/parse/files', page: '文档管理（上传）' },
  { method: 'POST', path: '/api/parse/tasks', page: '智能解析中心' },
  { method: 'GET', path: '/api/parse/tasks/{task_id}', page: '解析中心 / 文档管理' },
  { method: 'GET', path: '/api/parse/tasks/{task_id}/errors', page: '智能解析中心' },
  { method: 'POST', path: '/api/parse/tasks/{task_id}/resume', page: '智能解析中心' },
  { method: 'POST', path: '/api/parse/tasks/{task_id}/cancel', page: '智能解析中心' },
  { method: 'GET', path: '/api/parse/tasks/{task_id}/results', page: '智能解析中心' },
  { method: 'GET', path: '/api/parse/tasks/{task_id}/files/{file_id}/artifact', page: '智能解析中心' }
]

interface PendingApiRow { priority: 'P0' | 'P1'; path: string; usage: string }
const pendingApiRows: PendingApiRow[] = [
  { priority: 'P0', path: 'GET /api/parse/files/{file_id}/source', usage: '原始文件真实预览、缩略图、下载' },
  { priority: 'P0', path: 'GET /api/documents（+ /{id}、/parse-history）', usage: '文档列表、搜索筛选分页、详情与解析历史' },
  { priority: 'P0', path: 'GET /api/review/{doc_id}', usage: '审核详情与原始解析结果读取' },
  { priority: 'P0', path: 'POST /api/review/{doc_id}/*（4 个写操作）', usage: '审核通过 / 退回 / 标记错误 / 保存修订' },
  { priority: 'P1', path: 'GET /api/parse/tasks', usage: '解析任务列表与分页' },
  { priority: 'P1', path: 'GET /api/parse/tasks/{task_id}/logs', usage: '结构化任务日志（四阶段）' },
  { priority: 'P1', path: 'GET /api/parse/engines/status', usage: '三引擎真实五态' },
  { priority: 'P1', path: 'GET /api/stats/overview + /trend', usage: '首页统计与趋势脱离 DEMO' },
  { priority: 'P1', path: 'GET/POST /api/ingestion/*（5 个）', usage: '入库预检、批次、阶段状态、版本阻断' },
  { priority: 'P1', path: 'POST /api/knowledge/search', usage: '法规检索与可追溯引用' },
  { priority: 'P1', path: 'GET /api/system/health 等', usage: '六组件五态、资源与三类日志' }
]

async function saveToken() {
  if (!tokenInput.value || tokenInput.value.length < 32) {
    ElMessage.warning('Token 长度不足 32 位，请检查后重试')
    return
  }
  await store.saveToken(tokenInput.value)
  if (store.apiState === 'ONLINE') {
    ElMessage.success('Token 有效，后端连接成功')
  } else {
    ElMessage.warning('Token 已保存到当前会话，但未能连接后端，请确认服务已启动')
  }
}

onMounted(async () => {
  if (store.token) store.probeBackend()
  const { data } = await fetchAuditLog()
  auditLog.value = data
})
</script>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); }
.conn-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.conn-note { font-size: 13px; color: var(--mr-text-2); }
.token-form { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.security-note {
  margin-top: 12px; padding: 12px 14px; border: 1px solid #d5e5ff;
  background: #f5f9ff; border-radius: var(--mr-radius);
  font-size: 12px; color: var(--mr-text-2); line-height: 1.9;
}
.security-note b { color: #1e40af; }
@media (max-width: 1366px) {
  .security-note { line-height: 1.7; }
}
</style>
