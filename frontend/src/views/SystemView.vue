<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">系统监控</h1>
        <p class="page-desc">真实健康检查五态 · 运行期契约探测 · API Token 会话配置 · 接口能力清单</p>
      </div>
      <el-tag type="success" effect="plain">{{ releaseStatus.shortLabel }}</el-tag>
    </div>

    <!-- 旧解析服务真实探活 + Token 会话配置 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>后端解析服务（FastAPI）<span class="real-badge">REAL</span></span>
          <el-button size="small" @click="store.probeBackend()">重新探测 /api/parse/info</el-button>
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
        <el-descriptions-item label="字段来源">GET /api/parse/info（复用旧接口）</el-descriptions-item>
      </el-descriptions>
      <div v-else class="mr-disabled-hint" style="margin-top: 10px">
        尚未成功探测 /api/parse/info。后端不返回 version / environment 字段，本页不展示不存在的版本与环境信息。
        此探活结论只代表旧解析接口，不能推断 v0.2.2 新接口是否加载。
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
        <el-button @click="store.logout()">清除会话凭证</el-button>
      </div>
      <div class="security-note">
        <div><b>开发期</b>：Token 仅存于<b>内存 + sessionStorage（会话级）</b>，关闭标签页即失效；不写 localStorage、不打印到控制台或日志；请求经 Vite 代理同源转发。</div>
        <div><b>生产环境</b>：应由服务端下发安全会话（HttpOnly Cookie / BFF），前端不长期持有访问 Token。</div>
        <div><b>密钥边界</b>：MinerU 官方 API Key、数据库口令一律只存在 FastAPI 后端，浏览器绝不接触；当前存储方式：{{ tokenStorageMode }}。</div>
      </div>
    </el-card>

    <!-- 运行期契约探测：源码已交付 ≠ 活动实例已加载 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>运行期契约探测 <span class="real-badge">REAL</span></span>
          <el-button size="small" :loading="probing" @click="reprobe">重新探测 /api/openapi.json</el-button>
        </div>
      </template>
      <div class="conn-row">
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain" size="large">
          {{ contractLabel[contractState] }}
        </el-tag>
        <span class="conn-note">
          OpenAPI 版本 <b>{{ contractMeta.version || '—' }}</b> ·
          契约名 <b>{{ contractMeta.contractVersion || '未标注' }}</b> ·
          运行期路径数 <b class="num">{{ contractMeta.pathCount }}</b> ·
          探测时间 <b>{{ formatTime(contractMeta.probedAt) }}</b>
        </span>
      </div>
      <el-alert type="info" :closable="false" style="margin-top: 12px"
        :title="contractMeta.hint"
        description="匿名 /openapi.json 被后端显式关闭；认证端点 GET /api/openapi.json 需要 Bearer Token。源码分支与离线快照只说明契约已交付，七个页面是否渲染真实数据一律以本探测结果为准；未就绪显示明确异常态，不回退 DEMO。" />
    </el-card>

    <!-- 当前登录人员：GET /api/auth/me（draft-2 新增，正式 8180 v0.2.2 未提供该接口） -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>当前登录身份 <span class="real-badge">REAL</span></span>
          <span class="card-sub">
            GET /api/auth/me · {{ principalState }}
            <el-button text size="small" type="primary" :loading="identityLoading" @click="refreshIdentity">重新确认</el-button>
          </span>
        </div>
      </template>
      <el-descriptions v-if="principal" :column="2" border size="small">
        <el-descriptions-item label="当前登录人员 principal_id">{{ principal.principal_id }}</el-descriptions-item>
        <el-descriptions-item label="业务数据归属 owner_id">{{ principal.owner_id || '无个人 owner（纯审核身份）' }}</el-descriptions-item>
        <el-descriptions-item label="角色 roles">{{ principalRoleText }}</el-descriptions-item>
        <el-descriptions-item label="凭证状态">{{ principal.credential_status }}</el-descriptions-item>
        <el-descriptions-item label="审核范围 review_owner_scopes" :span="2">{{ principalScopeText }}</el-descriptions-item>
        <el-descriptions-item label="确认时间" :span="2">{{ formatTime(principalLoadedAt) }}</el-descriptions-item>
      </el-descriptions>
      <el-alert v-else type="warning" :closable="false" :title="`身份未确认（${principalState}）`"
        :description="principalError || 'GET /api/auth/me 未返回有效身份：正式 8180 仍为 v0.2.2（22 路径），该接口只在 draft-2 隔离实例可用。'" />
      <div class="mr-disabled-hint" style="margin-top: 8px">
        principal_id 是实际操作者，owner_id 是业务数据归属，两者不能互相推导。USER 无审核写入能力，ADMIN 不隐含 REVIEWER；
        审核可见与可写范围由后端按 review_owner_scopes 与逐请求授权限定，越界返回 404。旧 owner→writers 授权说明自 draft-2 起不再适用。
      </div>
    </el-card>

    <!-- 组件五态：GET /api/system/health 真实响应 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>组件状态 <span class="real-badge">REAL</span></span>
          <span class="card-sub">
            GET /api/system/health · 总体 {{ health.data.value?.status || '—' }}
            <el-button text size="small" type="primary" style="margin-left: 8px" @click="health.load()">刷新</el-button>
          </span>
        </div>
      </template>
      <AsyncPanel :state="health.state.value" :error="health.error.value" empty-text="后端未返回组件状态" @retry="health.load()">
        <el-table :data="componentRows" size="default">
          <el-table-column prop="name" label="组件" width="160" />
          <el-table-column label="状态" width="170">
            <template #default="{ row }">
              <span class="mr-state-tag" :class="`mr-state-${row.state}`">
                <span class="status-dot" :style="{ background: stateColorOf(row.state) }" />{{ row.state }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="check" label="后端检查方式" width="220" show-overflow-tooltip />
          <el-table-column label="附加字段" width="200">
            <template #default="{ row }">
              <span class="mono">{{ row.extra || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="note" label="真实性说明" min-width="240" show-overflow-tooltip />
        </el-table>
        <div class="mr-disabled-hint" style="margin-top: 10px">
          仅 fastapi（请求被处理）、task_store 与 postgresql（只读查询成功）可为 ONLINE；本地模型仅文件检查 → UNKNOWN，
          MinerU 仅配置检查 → UNKNOWN / NOT_CONFIGURED。后端不返回 DSN、Token、模型路径或异常堆栈；
          前端不主动调用 MinerU 云端验证凭证，也不把 HTTP 200 解释为全部底层服务正常。
        </div>
      </AsyncPanel>
    </el-card>

    <!-- v0.2.2 接口能力清单：源码契约 + 明确不支持 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>接口接入状态总览 <span class="real-badge">REAL</span></span>
          <span class="card-sub">
            契约 {{ CONTRACT_ROUTES.length }} 行 · v0.2.3 新增 {{ CONTRACT_ROUTES_V023.length }} 行 · 明确不支持 {{ MISSING_CAPABILITIES.length }} 组 ·
            {{ releaseStatus.apiContractReview }}
          </span>
        </div>
      </template>
      <el-tabs v-model="apiTab">
        <el-tab-pane :label="`源码契约（${CONTRACT_ROUTES.length}）`" name="routes">
          <el-table :data="CONTRACT_ROUTES" size="small">
            <el-table-column prop="method" label="方法" width="100" />
            <el-table-column prop="path" label="路径" min-width="300" show-overflow-tooltip />
            <el-table-column prop="page" label="使用页面" min-width="220" show-overflow-tooltip />
            <el-table-column label="来源" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="row.group === 'legacy' ? 'info' : 'success'" effect="plain">
                  {{ row.group === 'legacy' ? '复用' : '新增' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="运行期" width="110">
              <template #default>
                <span :class="contractState === 'ready' ? 'run-ready' : 'run-pending'">
                  {{ contractState === 'ready' ? '契约就绪' : '待探测' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`v0.2.3 新增（${CONTRACT_ROUTES_V023.length}）`" name="v023">
          <el-table :data="CONTRACT_ROUTES_V023" size="small">
            <el-table-column prop="method" label="方法" width="100" />
            <el-table-column prop="path" label="路径" min-width="300" show-overflow-tooltip />
            <el-table-column prop="page" label="使用页面" min-width="220" show-overflow-tooltip />
            <el-table-column label="运行期" width="130">
              <template #default="{ row }">
                <span :class="runtimeHas(row.path) ? 'run-ready' : 'run-pending'">{{ runtimeHas(row.path) ? '已加载' : '未加载' }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div class="mr-disabled-hint" style="margin-top: 10px">
            源码契约依据 0.2.3-dev / frontend-api-v0.2.3-draft-2（30 路径，含 GET /api/auth/me）。draft-1（29 路径）的
            owner→writers 授权说明已不适用；运行期是否可用一律以 GET /api/openapi.json 实测路径与方法为准，
            未加载时相关功能保持禁用 / 空态，不调用不存在的接口。
          </div>
        </el-tab-pane>
        <el-tab-pane :label="`明确不支持（${MISSING_CAPABILITIES.length}）`" name="missing">
          <el-table :data="MISSING_CAPABILITIES" size="small">
            <el-table-column label="优先级" width="90">
              <template #default="{ row }">
                <el-tag :type="row.priority === 'P0' ? 'danger' : 'info'" size="small" effect="plain">{{ row.priority }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="api" label="缺失接口" min-width="320" show-overflow-tooltip />
            <el-table-column prop="usage" label="对应业务" min-width="200" show-overflow-tooltip />
            <el-table-column prop="impact" label="前端处理" min-width="260" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
      </el-tabs>
      <div class="mr-disabled-hint" style="margin-top: 10px">
        本表为源码契约清单（离线 OpenAPI 22 个路径＋1 个不出现在公开 schema 中的认证探测端点，按方法列举 {{ CONTRACT_ROUTES.length }} 行），
        <b>不代表这些接口已在活动 8180 实例上探测成功</b>。运行期结论以 /api/openapi.json 探测为准；
        详细字段契约与实测结果见 frontend/docs/frontend-api-mapping-v0.2.2.md 与 frontend-api-integration-report.md。
      </div>
    </el-card>

    <!-- v0.2.3：API 进程真实资源 + 审核审计摘要（仅运行期契约加载后才请求） -->
    <el-card v-if="v023Monitoring" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>API 进程资源 <span class="real-badge">REAL</span></span>
          <span class="card-sub">GET /api/system/resources · scope=api_process
            <el-button text size="small" type="primary" @click="resources.load()">刷新采样</el-button>
          </span>
        </div>
      </template>
      <AsyncPanel :state="resources.state.value" :error="resources.error.value" empty-text="后端未返回资源采样" @retry="resources.load()">
        <el-alert v-if="resources.data.value && !resources.data.value.available" type="warning" :closable="false"
          :title="`采样不可用：${resources.data.value.reason || '后端未给出原因'}`"
          description="失败时后端返回 available=false 与 null 指标，前端不把不可用伪装成 0 或正常。" />
        <el-descriptions v-else-if="resources.data.value" :column="3" border size="small">
          <el-descriptions-item label="memory_rss_bytes">{{ resources.data.value.memory_rss_bytes ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="cpu_user_seconds">{{ resources.data.value.cpu_user_seconds ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="cpu_system_seconds">{{ resources.data.value.cpu_system_seconds ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="uptime_seconds">{{ resources.data.value.uptime_seconds ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="threads">{{ resources.data.value.threads ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="sampled_at">{{ formatTime(resources.data.value.sampled_at) }}</el-descriptions-item>
        </el-descriptions>
      </AsyncPanel>
      <div class="mr-disabled-hint" style="margin-top: 8px">仅 API 进程真实采样：累计 CPU 秒不是利用率，不含宿主机、容器整体、GPU 或模型推理监控。</div>
    </el-card>

    <el-card v-if="v023Monitoring" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>审核审计摘要 <span class="real-badge">REAL</span></span>
          <span class="card-sub">GET /api/system/audit-logs · 按当前 principal 与审核范围
            <el-button text size="small" type="primary" @click="auditLogs.load()">刷新</el-button>
          </span>
        </div>
      </template>
      <AsyncPanel :state="auditLogs.state.value" :error="auditLogs.error.value" empty-text="当前身份范围内暂无审核事件摘要" @retry="auditLogs.load()">
        <el-table :data="auditLogs.data.value?.list || []" size="small" max-height="260">
          <el-table-column prop="action" label="动作" width="150" />
          <el-table-column prop="parse_id" label="parse_id" min-width="180" show-overflow-tooltip />
          <el-table-column label="操作者 operator_id" width="180"><template #default="{ row }">{{ identityText(row.operator_id) }}</template></el-table-column>
          <el-table-column label="文档所属人 owner_id" width="180"><template #default="{ row }">{{ identityText(row.owner_id) }}</template></el-table-column>
          <el-table-column prop="operator" label="兼容别名" width="150" show-overflow-tooltip />
          <el-table-column prop="version" label="版本" width="80" />
          <el-table-column label="时间" width="180"><template #default="{ row }">{{ formatTime(row.timestamp) }}</template></el-table-column>
        </el-table>
      </AsyncPanel>
      <div class="mr-disabled-hint" style="margin-top: 8px">只展示真实审核事件摘要（approve / reject / mark-error / save-revision），不含修订正文；不编造未发生的历史事件。旧事件 operator_id / owner_id 为 null 时显示「未知（历史记录）」，不把历史 owner 补认成具体人员。</div>
    </el-card>

    <!-- 无真实 HTTP 数据源的模块：一律空态 -->
    <div class="card-grid" style="grid-template-columns: repeat(3, 1fr); margin-top: 16px">
      <el-card v-for="m in missingModules" :key="m.title" shadow="never">
        <template #header><div class="card-head"><span>{{ m.title }}</span><span class="card-sub">接口未实现</span></div></template>
        <el-empty :image-size="54" :description="m.hint">
          <span class="mr-disabled-hint">{{ m.api }}</span>
        </el-empty>
      </el-card>
    </div>

    <el-card v-if="!v023Monitoring" shadow="never" style="margin-top: 16px">
      <template #header><div class="card-head"><span>操作审计日志</span><span class="card-sub">运行期未加载 v0.2.3 审计接口</span></div></template>
      <el-empty :image-size="54" description="无真实审计数据（运行期接口未加载）">
        <span class="mr-disabled-hint">
          当前服务的 GET /api/openapi.json 未返回 /api/system/audit-logs；不展示演示操作记录，避免把未发生的操作伪装成已留痕。
        </span>
      </el-empty>
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
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAppStore } from '@/stores/app'
import { useAsyncData } from '@/composables/useAsyncData'
import { tokenStorageMode } from '@/api/client'
import { getSystemHealth } from '@/api/frontend'
import { getProcessResources, getAuditLogs } from '@/api/reviewWrite'
import {
  contractState, contractMeta, contractLabel, probeContract,
  CONTRACT_ROUTES, CONTRACT_ROUTES_V023, MISSING_CAPABILITIES,
  hasV023Monitoring, hasRuntimeRoutes
} from '@/api/dataSource'
import { releaseStatus } from '@/config/release'
import {
  principal, principalState, principalError, principalLoadedAt,
  loadPrincipal, principalRoleText, principalScopeText, identityText
} from '@/api/principal'
import type {
  ComponentState, HealthResponse, ProcessResources, AuditLogItem, ListResponse
} from '@/api/types'

/**
 * v0.2.2 系统监控
 * - 组件五态来自 GET /api/system/health 真实响应，不再用静态表或旧接口探活推断
 * - 契约状态来自运行期 GET /api/openapi.json 探测，明确区分「源码已交付」与「活动实例已加载」
 * - 接口总览采用 CONTRACT_ROUTES / MISSING_CAPABILITIES 源码清单，计数不依赖已废弃的静态能力开关
 * - 资源监控、三类日志、操作审计均无 HTTP 实现 → 空态，零 DEMO 记录
 */
const store = useAppStore()
const tokenInput = ref(store.token)
const apiTab = ref('routes')
const probing = ref(false)

const identityLoading = ref(false)
async function refreshIdentity() {
  identityLoading.value = true
  try {
    await loadPrincipal(true)
  } finally {
    identityLoading.value = false
  }
}

const STATE_COLOR: Record<ComponentState, string> = {
  ONLINE: 'var(--mr-state-online)',
  OFFLINE: 'var(--mr-state-offline)',
  NOT_CONFIGURED: 'var(--mr-state-not-configured)',
  UNKNOWN: 'var(--mr-state-unknown)',
  ERROR: 'var(--mr-state-error)'
}
const VALID_STATES: ComponentState[] = ['ONLINE', 'OFFLINE', 'NOT_CONFIGURED', 'UNKNOWN', 'ERROR']
function normalizeState(value: string): ComponentState {
  return (VALID_STATES as string[]).includes(value) ? value as ComponentState : 'UNKNOWN'
}
function stateColorOf(s: ComponentState): string { return STATE_COLOR[s] }
const stateColor = computed(() => STATE_COLOR[store.apiState])
const stateLabel = computed(() => {
  if (store.apiState === 'ONLINE') return '真实探活成功（/api/parse/info 返回 200）；此结论不覆盖 v0.2.2 新接口'
  if (store.apiState === 'OFFLINE') return '探活失败 — 请确认 8180 服务已启动、Token 有效'
  return '尚未探测（未配置 Token 或未发起请求）'
})

const health = useAsyncData<HealthResponse>((signal) => getSystemHealth(signal))

/* v0.2.3 新增只读接口：运行期契约加载后才请求，未加载时保持空态 */
const v023Monitoring = computed(() => hasV023Monitoring())
const resources = useAsyncData<ProcessResources>(
  (signal) => getProcessResources(signal), { immediate: false }
)
const auditLogs = useAsyncData<ListResponse<AuditLogItem>>(
  (signal) => getAuditLogs({ page: 1, pageSize: 20 }, signal), { immediate: false }
)
watch(v023Monitoring, (ok) => {
  if (ok) { void resources.load(); void auditLogs.load() }
}, { immediate: true })
function runtimeHas(path: string): boolean {
  return hasRuntimeRoutes([path])
}

const CHECKABLE_ONLINE = ['fastapi', 'task_store', 'postgresql']
interface ComponentRow {
  name: string
  state: ComponentState
  check: string
  extra: string
  note: string
}
const componentRows = computed<ComponentRow[]>(() =>
  Object.entries(health.data.value?.components || {}).map(([name, c]) => {
    const flags: string[] = []
    if (c.model_ready !== undefined) flags.push(`model_ready=${c.model_ready}`)
    if (c.configured !== undefined) flags.push(`configured=${c.configured}`)
    return {
      name,
      state: normalizeState(c.state || ''),
      check: c.check || '后端未返回',
      extra: flags.join(' · '),
      note: CHECKABLE_ONLINE.includes(name)
        ? '真实只读查询成功才可为 ONLINE'
        : name === 'mineru'
          ? '仅配置检查；前端不调用云端验证'
          : '仅本地文件检查，不代表推理服务在线'
    }
  })
)

const missingModules = [
  { title: '系统资源', hint: '运行期未加载 v0.2.3 时保持空态', api: 'GET /api/system/resources（源码契约已交付）' },
  { title: '接口调用记录', hint: '接口未实现', api: 'GET /api/system/api-logs' },
  { title: '错误日志', hint: '接口未实现', api: 'GET /api/system/error-logs' }
]

async function saveToken() {
  if (!tokenInput.value || tokenInput.value.length < 32) {
    ElMessage.warning('Token 长度不足 32 位，请检查后重试')
    return
  }
  await store.saveToken(tokenInput.value)
  await health.load()
  if (store.apiState === 'ONLINE' && contractState.value === 'ready') {
    ElMessage.success('Token 有效，旧解析接口与 v0.2.2 契约均已就绪')
  } else if (store.apiState === 'ONLINE') {
    ElMessage.warning('Token 有效，但活动实例未加载 v0.2.2 契约，新接口暂不可用')
  } else {
    ElMessage.warning('Token 已保存到当前会话，但未能连接后端，请确认服务已启动')
  }
}

async function reprobe() {
  probing.value = true
  try {
    await probeContract(true)
    await Promise.all([health.load(), loadPrincipal(true)])
  } finally {
    probing.value = false
  }
}

function formatTime(v: string) { return v ? String(v).replace('T', ' ').slice(0, 19) : '—' }

onMounted(() => {
  if (store.token) void store.probeBackend()
  if (principalState.value !== 'ready') void loadPrincipal(true)
})
</script>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; gap: 12px; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); margin-left: 8px; }
.conn-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.conn-note { font-size: 13px; color: var(--mr-text-2); }
.token-form { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.security-note {
  margin-top: 12px; padding: 12px 14px; border: 1px solid #d5e5ff;
  background: #f5f9ff; border-radius: var(--mr-radius);
  font-size: 12px; color: var(--mr-text-2); line-height: 1.9;
}
.security-note b { color: #1e40af; }
.mono { font-family: monospace; font-size: 12px; }
.run-ready { color: var(--mr-state-online); font-size: 12px; }
.run-pending { color: var(--mr-state-unknown); font-size: 12px; }
@media (max-width: 1366px) {
  .security-note { line-height: 1.7; }
}
</style>
