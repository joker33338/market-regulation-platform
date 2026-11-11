<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">首页工作台</h1>
        <p class="page-desc">
          文档解析与法规入库全局概览
          <el-tag size="small" type="success" effect="plain" style="margin-left: 8px">{{ releaseStatus.shortLabel }}</el-tag>
        </p>
      </div>
      <div class="header-tags">
        <el-tag type="success" effect="plain">真实接口 /api/stats/overview</el-tag>
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain">{{ contractLabel[contractState] }}</el-tag>
        <span class="days-control">
          <span>统计窗口</span>
          <el-input-number v-model="days" :min="1" :max="366" :step="1" size="small" controls-position="right" style="width: 110px" />
          <span>天</span>
        </span>
        <el-button size="small" :loading="stats.loading.value" @click="stats.load()">刷新统计</el-button>
      </div>
    </div>

    <!-- 口径说明：三种来源范围不同，禁止相加 -->
    <div class="scope-note">
      <el-icon><InfoFilled /></el-icon>
      <span>
        <b>uploads</b>（当前用户全部上传元数据，全量）、<b>tasks</b>（窗口内 SQLite 任务）、
        <b>parsed_documents</b>（document_review 全历史回执）来源与范围不同，<b>禁止相加</b>；
        <b>engine_file_selections</b> 是文件引擎选择次数，不保证等于任务数；
        <b>created_daily</b> 是真实任务创建日计数，不是处理耗时或成功数。
        DB 不可用时 <code>available=false</code>、计数为 <code>null</code>，页面显示「暂无数据」而非 0。
      </span>
    </div>

    <el-alert v-if="distributionMismatch" type="error" :closable="false" style="margin-bottom: 12px"
      :title="`真实统计一致性告警：${distributionMismatch}`"
      description="契约要求 status_distribution 之和等于 tasks.total。此处仅报告后端真实返回值的差异，不做任何自动修正或补数。" />

    <AsyncPanel :state="stats.state.value" :error="stats.error.value" empty-text="后端未返回统计数据" @retry="stats.load()">
      <div class="window-note">
        生成时间 {{ formatTime(stats.data.value?.generated_at || '') }} ·
        窗口 {{ formatTime(stats.data.value?.window.since || '') }} ~ {{ formatTime(stats.data.value?.window.until || '') }} ·
        数据源 uploads={{ stats.data.value?.uploads.source || '—' }} / tasks={{ stats.data.value?.tasks.source || '—' }} /
        parsed_documents={{ stats.data.value?.parsed_documents.source || '—' }}
      </div>

      <div class="card-grid stat-grid">
        <StatCard label="上传文件总数" :value="stats.data.value?.uploads.total ?? 0" scope="全量" hint="· 当前用户上传元数据" real />
        <StatCard label="解析任务总数" :value="stats.data.value?.tasks.total ?? 0" :scope="`近 ${days} 天`" hint="· SQLite 任务" color="var(--mr-primary)" real />
        <StatCard label="已解析文档" :value="parsedTotal" scope="全历史" hint="· document_review 回执" color="var(--mr-st-success)" real />
        <StatCard label="需人工复核" :value="reviewTotal" scope="全历史" hint="· document_review 回执" color="var(--mr-st-warning)" real />
      </div>

      <div class="card-grid" style="grid-template-columns: 2fr 1fr; margin-top: 16px">
        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <span>任务创建日趋势（近 {{ days }} 天）<span class="real-badge">REAL</span></span>
              <span class="card-sub">created_daily · 真实任务创建日计数</span>
            </div>
          </template>
          <ChartBox v-if="dailyEntries.length" :option="trendOption" height="260px" />
          <el-empty v-else :image-size="60" description="后端未返回 created_daily 数据，不生成模拟趋势" />
        </el-card>
        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <span>文件引擎选择次数 <span class="real-badge">REAL</span></span>
              <span class="card-sub">engine_file_selections · 不等于任务数</span>
            </div>
          </template>
          <ChartBox v-if="engineEntries.length" :option="engineOption" height="260px" />
          <el-empty v-else :image-size="60" description="后端未返回引擎选择统计，不生成模拟分布" />
        </el-card>
      </div>

      <div class="card-grid" style="grid-template-columns: 1fr 1fr 1fr; margin-top: 16px">
        <el-card shadow="never">
          <template #header><div class="card-head"><span>任务状态分布 <span class="real-badge">REAL</span></span><span class="card-sub">status_distribution 原始键</span></div></template>
          <el-table v-if="statusEntries.length" :data="statusEntries" size="small" border>
            <el-table-column prop="key" label="状态（后端原始值）" min-width="160" show-overflow-tooltip />
            <el-table-column prop="value" label="任务数" width="90" align="right" />
          </el-table>
          <el-empty v-else :image-size="54" description="后端未返回状态分布" />
          <div class="mr-disabled-hint" style="margin-top: 8px">合计 {{ distributionSum }} / tasks.total {{ stats.data.value?.tasks.total ?? 0 }}</div>
        </el-card>

        <el-card shadow="never">
          <template #header><div class="card-head"><span>最近任务 <span class="real-badge">REAL</span></span><span class="card-sub">recent_tasks</span></div></template>
          <el-table v-if="recentTasks.length" :data="recentTasks" size="small">
            <el-table-column prop="taskId" label="task_id" min-width="140" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="110" />
            <el-table-column prop="fileCount" label="文件数" width="70" align="right" />
            <el-table-column prop="createdAt" label="创建时间" width="150" />
          </el-table>
          <el-empty v-else :image-size="54" description="窗口内暂无任务（后端返回空列表）" />
        </el-card>

        <el-card shadow="never">
          <template #header><div class="card-head"><span>已移除的演示指标</span><span class="card-sub">后端无对应真实字段</span></div></template>
          <div class="removed-list">
            <div v-for="m in removedMetrics" :key="m" class="removed-item">{{ m }}</div>
          </div>
          <div class="mr-disabled-hint" style="margin-top: 10px">
            待人工审核数量、已入库法规数、解析成功率、待处理任务清单、最近入库记录均无真实 HTTP 数据源；
            v0.2.2 起不再以 DEMO 形式呈现，需后端补齐接口后方可恢复。
          </div>
        </el-card>
      </div>
    </AsyncPanel>

    <!-- 系统组件状态：GET /api/system/health 真实五态 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>系统运行状态 <span class="real-badge">REAL</span></span>
          <span class="card-sub">
            GET /api/system/health · 总体 {{ health.data.value?.status || '—' }}
            <el-button text size="small" type="primary" style="margin-left: 8px" @click="health.load()">刷新探测</el-button>
          </span>
        </div>
      </template>
      <AsyncPanel :state="health.state.value" :error="health.error.value" empty-text="后端未返回组件状态" @retry="health.load()">
        <div class="component-row">
          <div v-for="c in componentRows" :key="c.name" class="component-item">
            <span class="status-dot" :style="{ background: stateColorOf(c.state) }" />
            <div class="component-text">
              <span class="component-name">{{ c.name }}</span>
              <span class="component-note">
                <b :class="`mr-state-${c.state}`">{{ c.state }}</b>
                <span>{{ c.check || '后端未返回检查说明' }}</span>
              </span>
              <span v-if="c.modelReady !== undefined || c.configured !== undefined" class="component-extra">
                <span v-if="c.modelReady !== undefined">model_ready={{ c.modelReady }}</span>
                <span v-if="c.configured !== undefined">configured={{ c.configured }}</span>
              </span>
            </div>
          </div>
        </div>
        <div class="mr-disabled-hint" style="margin-top: 10px">
          仅 fastapi（请求被处理）、task_store / postgresql（只读查询成功）可为 ONLINE；本地模型仅文件检查 → UNKNOWN，
          MinerU 仅配置检查 → UNKNOWN / NOT_CONFIGURED。响应不含 DSN、Token、模型路径或异常堆栈；前端不主动调用 MinerU 云端。
        </div>
      </AsyncPanel>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { InfoFilled } from '@element-plus/icons-vue'
import StatCard from '@/components/StatCard.vue'
import ChartBox from '@/components/ChartBox.vue'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { getStatsOverview, getSystemHealth } from '@/api/frontend'
import { contractState, contractLabel } from '@/api/dataSource'
import { releaseStatus } from '@/config/release'
import type { ComponentState, HealthResponse, StatsResponse } from '@/api/types'

/**
 * v0.2.2 首页工作台
 * - 统计唯一来源 GET /api/stats/overview?days=N；uploads/tasks/parsed_documents 三组范围不同，禁止相加
 * - 组件状态唯一来源 GET /api/system/health，五态按后端 state 归一化，不把 HTTP 200 当作所有底层服务正常
 * - available=false / null 显示「暂无数据」，不显示 0；图表无数据时空态，不生成模拟序列
 * - 零 DEMO 业务结果；接口未就绪由 AsyncPanel 统一呈现 no-permission / outdated / unavailable / error
 */
const days = ref(14)

const stats = useAsyncData<StatsResponse>((signal) => getStatsOverview(days.value, signal))
const health = useAsyncData<HealthResponse>((signal) => getSystemHealth(signal))

const parsedTotal = computed<number | string>(() => {
  const p = stats.data.value?.parsed_documents
  if (!p || !p.available || p.total == null) return '暂无数据'
  return p.total
})
const reviewTotal = computed<number | string>(() => {
  const p = stats.data.value?.parsed_documents
  if (!p || !p.available || p.requires_review == null) return '暂无数据'
  return p.requires_review
})

const statusEntries = computed(() =>
  Object.entries(stats.data.value?.tasks.status_distribution || {})
    .map(([key, value]) => ({ key, value: Number(value) }))
    .sort((a, b) => b.value - a.value)
)
const distributionSum = computed(() => statusEntries.value.reduce((sum, x) => sum + x.value, 0))
const distributionMismatch = computed(() => {
  const total = stats.data.value?.tasks.total
  if (total == null || statusEntries.value.length === 0) return ''
  return distributionSum.value === total ? '' : `status_distribution 合计 ${distributionSum.value} ≠ tasks.total ${total}`
})

const dailyEntries = computed(() =>
  Object.entries(stats.data.value?.tasks.created_daily || {})
    .map(([date, value]) => ({ date, value: Number(value) }))
    .sort((a, b) => a.date.localeCompare(b.date))
)
const engineEntries = computed(() =>
  Object.entries(stats.data.value?.tasks.engine_file_selections || {})
    .map(([engine, value]) => ({ engine, value: Number(value) }))
    .sort((a, b) => b.value - a.value)
)
const recentTasks = computed(() =>
  (stats.data.value?.recent_tasks || []).map((t) => ({
    taskId: t.task_id,
    status: t.status,
    fileCount: t.files?.length ?? 0,
    createdAt: formatTime(t.created_at)
  }))
)

const removedMetrics = [
  '待人工审核数量（旧 DEMO）',
  '已入库法规数（旧 DEMO）',
  '分引擎解析成功率（旧 DEMO）',
  '待处理任务清单（旧 DEMO）',
  '最近入库记录（旧 DEMO）',
  '上传/解析/失败趋势（旧 DEMO）'
]

const trendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 44, right: 16, top: 18, bottom: 34 },
  xAxis: {
    type: 'category', data: dailyEntries.value.map((d) => d.date),
    axisLine: { lineStyle: { color: '#dbe3ee' } }, axisLabel: { fontSize: 11 }
  },
  yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#eef2f8' } } },
  series: [{
    name: '任务创建数', type: 'bar', barMaxWidth: 34,
    data: dailyEntries.value.map((d) => d.value),
    itemStyle: { color: '#1d6fe0', borderRadius: [3, 3, 0, 0] }
  }]
}))

const engineOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} 次（{d}%）' },
  legend: { bottom: 0, itemWidth: 12 },
  series: [{
    type: 'pie', radius: ['52%', '74%'], center: ['50%', '44%'], label: { show: false },
    data: engineEntries.value.map((e, i) => ({
      name: e.engine, value: e.value,
      itemStyle: { color: ['#1d6fe0', '#2fa06b', '#d97706', '#7c5cd6', '#d64545'][i % 5] }
    }))
  }]
}))

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

interface ComponentRow {
  name: string
  state: ComponentState
  check: string
  modelReady?: boolean
  configured?: boolean
}
const componentRows = computed<ComponentRow[]>(() =>
  Object.entries(health.data.value?.components || {}).map(([name, c]) => ({
    name,
    state: normalizeState(c.state || ''),
    check: c.check || '',
    modelReady: c.model_ready,
    configured: c.configured
  }))
)

function formatTime(v: string) { return v ? String(v).replace('T', ' ').slice(0, 19) : '—' }
</script>

<style scoped>
.header-tags { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.days-control { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--mr-text-2); }
.scope-note {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 10px 14px; margin-bottom: 12px;
  background: #eef4ff; border: 1px solid #d5e5ff;
  border-radius: var(--mr-radius); color: #1e40af;
  font-size: 12px; line-height: 1.8;
}
.scope-note code { font-family: monospace; }
.window-note { font-size: 12px; color: var(--mr-text-3); margin-bottom: 12px; line-height: 1.7; }
.stat-grid { grid-template-columns: repeat(4, 1fr); }
.card-head { display: flex; align-items: center; justify-content: space-between; font-weight: 600; gap: 12px; }
.card-sub { display: inline-flex; align-items: center; font-weight: 400; font-size: 12px; color: var(--mr-text-3); margin-left: 8px; }
.removed-list { display: flex; flex-direction: column; gap: 6px; }
.removed-item { font-size: 12px; color: var(--mr-text-2); padding: 6px 8px; background: #fafbfe; border: 1px solid var(--mr-line); border-radius: 4px; }
.component-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.component-item { display: flex; align-items: flex-start; gap: 8px; padding: 10px 12px; border: 1px solid var(--mr-line); border-radius: 6px; background: #fafbfe; font-size: 13px; }
.component-item .status-dot { margin-top: 5px; }
.component-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.component-name { font-weight: 600; }
.component-note { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; color: var(--mr-text-3); font-size: 12px; }
.component-extra { display: flex; gap: 10px; font-size: 11px; color: var(--mr-text-3); font-family: monospace; }
@media (max-width: 1440px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .component-row { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 1366px) {
  .component-row { grid-template-columns: 1fr 1fr; }
}
</style>
