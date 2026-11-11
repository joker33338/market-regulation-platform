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
          运行期路径数 <b class="num">{{ contractMeta.pathCount }}</b> ·
          探测时间 <b>{{ formatTime(contractMeta.probedAt) }}</b>
        </span>
      </div>
      <el-alert type="info" :closable="false" style="margin-top: 12px"
        :title="contractMeta.hint"
        description="匿名 /openapi.json 被后端显式关闭；认证端点 GET /api/openapi.json 需要 Bearer Token。源码分支与离线快照只说明契约已交付，七个页面是否渲染真实数据一律以本探测结果为准；未就绪显示明确异常态，不回退 DEMO。" />
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
            契约 {{ CONTRACT_ROUTES.length }} 行 · 明确不支持 {{ MISSING_CAPABILITIES.length }} 组 ·
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

    <!-- 无真实 HTTP 数据源的模块：一律空态 -->
    <div class="card-grid" style="grid-template-columns: repeat(3, 1fr); margin-top: 16px">
      <el-card v-for="m in missingModules" :key="m.title" shadow="never">
        <template #header><div class="card-head"><span>{{ m.title }}</span><span class="card-sub">接口未实现</span></div></template>
        <el-empty :image-size="54" :description="m.hint">
          <span class="mr-disabled-hint">{{ m.api }}</span>
        </el-empty>
      </el-card>
    </div>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header><div class="card-head"><span>操作审计日志</span><span class="card-sub">后端未实现审计写入与查询接口</span></div></template>
      <el-empty :image-size="54" description="无真实审计数据（接口未接入）">
        <span class="mr-disabled-hint">
          GET /api/system/audit-logs 未实现；v0.2.2 起不再展示演示操作记录，避免把未发生的操作伪装成已留痕。
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
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAppStore } from '@/stores/app'
import { useAsyncData } from '@/composables/useAsyncData'
import { tokenStorageMode } from '@/api/client'
import { getSystemHealth } from '@/api/frontend'
import {
  contractState, contractMeta, contractLabel, probeContract,
  CONTRACT_ROUTES, MISSING_CAPABILITIES
} from '@/api/dataSource'
import { releaseStatus } from '@/config/release'
import type { ComponentState, HealthResponse } from '@/api/types'

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
  { title: '系统资源', hint: '接口未实现', api: 'GET /api/system/resources' },
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
    await health.load()
  } finally {
    probing.value = false
  }
}

function formatTime(v: string) { return v ? String(v).replace('T', ' ').slice(0, 19) : '—' }

onMounted(() => {
  if (store.token) void store.probeBackend()
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
