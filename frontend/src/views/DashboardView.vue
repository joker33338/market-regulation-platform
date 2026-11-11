<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">首页工作台</h1>
        <p class="page-desc">
          文档解析与法规入库全局概览
          <el-tag size="small" type="warning" effect="plain" style="margin-left: 8px">{{ releaseStatus.shortLabel }}</el-tag>
        </p>
      </div>
      <DemoBadge v-if="isDemo" />
    </div>

    <!-- 统一统计口径：明确区分文件数与解析任务数 -->
    <div class="scope-note">
      <el-icon><InfoFilled /></el-icon>
      <span>
        统一口径：近 <b>{{ stats.rangeDays }}</b> 天 ·
        解析任务总数 <b class="num">{{ stats.totalTasks }}</b> = 成功
        <b class="num">{{ stats.succeeded }}</b> + 失败 <b class="num">{{ stats.failed }}</b>
        + 执行中 <b class="num">{{ stats.running }}</b>；
        文件数 <b class="num">{{ stats.totalFiles }}</b> 独立统计，不与任务数相加。
      </span>
      <DemoBadge v-if="isDemo" />
    </div>
    <el-alert
      v-if="consistencyIssues.length"
      type="error"
      :closable="false"
      style="margin-bottom: 12px"
      :title="`统计口径自检未通过：${consistencyIssues.join('；')}`"
    />

    <div class="card-grid stat-grid">
      <StatCard label="文档总数（文件）" :value="stats.totalFiles" scope="全量" hint="上传文件记录数" :demo="isDemo" :real="!isDemo" />
      <StatCard label="待解析 / 执行中" :value="stats.running" :scope="nearDays" hint="解析任务" color="var(--mr-st-pending)" :demo="isDemo" :real="!isDemo" />
      <StatCard label="解析成功" :value="stats.succeeded" :scope="nearDays" hint="解析任务" color="var(--mr-st-success)" :demo="isDemo" :real="!isDemo" />
      <StatCard label="解析失败" :value="stats.failed" :scope="nearDays" hint="解析任务" color="var(--mr-st-danger)" :demo="isDemo" :real="!isDemo" />
      <StatCard label="待人工审核" :value="stats.pendingReview" :scope="nearDays" color="var(--mr-st-warning)" :demo="isDemo" :real="!isDemo" />
      <StatCard label="已入库法规" :value="stats.ingestedRegulations" scope="全量" color="var(--mr-st-review)" :demo="isDemo" :real="!isDemo" />
    </div>

    <div class="card-grid" style="grid-template-columns: 2fr 1fr; margin-top: 16px">
      <el-card shadow="never">
        <template #header>
          <div class="card-head"><span>文档处理趋势（近 {{ stats.rangeDays }} 天）</span><DemoBadge v-if="isDemo" /></div>
        </template>
        <ChartBox :option="trendOption" height="260px" />
      </el-card>
      <el-card shadow="never">
        <template #header>
          <div class="card-head"><span>OCR 引擎调用分布</span><DemoBadge v-if="isDemo" /></div>
        </template>
        <ChartBox :option="engineOption" height="260px" />
      </el-card>
    </div>

    <div class="card-grid" style="grid-template-columns: 1fr 1fr 1fr; margin-top: 16px">
      <el-card shadow="never">
        <template #header><div class="card-head"><span>解析成功率</span><DemoBadge v-if="isDemo" /></div></template>
        <div v-for="row in successRate" :key="row.name" class="rate-row">
          <span class="rate-name">{{ row.name }}</span>
          <el-progress :percentage="row.value" :stroke-width="10" :color="rateColor(row.value)" style="flex: 1" />
          <span class="rate-detail num">{{ row.stat.succeeded }}/{{ row.stat.taskCount }}</span>
        </div>
      </el-card>
      <el-card shadow="never">
        <template #header><div class="card-head"><span>待处理任务</span><DemoBadge v-if="isDemo" /></div></template>
        <el-table :data="pendingTasks" size="small" :show-header="false">
          <el-table-column prop="name" show-overflow-tooltip />
          <el-table-column width="90" align="right">
            <template #default="{ row }"><StatusTag :status="row.status" /></template>
          </el-table-column>
        </el-table>
      </el-card>
      <el-card shadow="never">
        <template #header><div class="card-head"><span>最近入库记录</span><DemoBadge v-if="isDemo" /></div></template>
        <el-table :data="recent" size="small" :show-header="false">
          <el-table-column prop="name" show-overflow-tooltip />
          <el-table-column width="110" align="right">
            <template #default="{ row }"><span class="num" style="color: var(--mr-text-3); font-size: 12px">{{ row.version }}</span></template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>系统运行状态 <span class="card-sub">仅 FastAPI 为真实探测</span></span>
          <el-button text size="small" type="primary" @click="probe">刷新探测</el-button>
        </div>
      </template>
      <div class="component-row">
        <div v-for="c in components" :key="c.name" class="component-item">
          <span class="status-dot" :style="{ background: statusColor(c) }" />
          <div class="component-text">
            <span class="component-name">{{ c.name }}</span>
            <span class="component-note">
              <b :class="`mr-state-${effectiveState(c)}`">{{ effectiveState(c) }}</b>
              <span>{{ c.note }}</span>
              <DemoBadge v-if="c.source === 'demo'" />
            </span>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { InfoFilled } from '@element-plus/icons-vue'
import StatCard from '@/components/StatCard.vue'
import DemoBadge from '@/components/DemoBadge.vue'
import StatusTag from '@/components/StatusTag.vue'
import ChartBox from '@/components/ChartBox.vue'
import { useAppStore } from '@/stores/app'
import { apiCapabilities } from '@/api/dataSource'
import { releaseStatus } from '@/config/release'
import { demoUnifiedStats, statsConsistencyIssues } from '@/api/mock/stats'
import {
  demoStats, demoTrend, demoEngineDist, demoSuccessRate, demoRecentIngestion,
  demoComponentStatus, type ComponentStatus
} from '@/api/mock/dashboard'
import type { ComponentState } from '@/api/types'

const store = useAppStore()
const stats = ref(demoStats)
const successRate = ref(demoSuccessRate)
const recent = ref(demoRecentIngestion)
const components = ref<ComponentStatus[]>(demoComponentStatus)

/** 统计接口未实现：无论后端是否在线，统计一律标 DEMO */
const isDemo = computed(() => !apiCapabilities.dashboardStats)
const nearDays = computed(() => `近 ${stats.value.rangeDays} 天`)
/** 单一快照自检，杜绝不同页面互相矛盾的演示统计 */
const consistencyIssues = statsConsistencyIssues(demoUnifiedStats)

const pendingTasks = ref([
  { name: '价格违法行为行政处罚规定.docx', status: 'pending' },
  { name: '消费品召回管理暂行规定.pdf', status: 'parsing' },
  { name: '检验检测机构监督管理办法.pdf', status: 'reviewing' },
  { name: '保健食品标注警示用语指南.pdf', status: 'pending' }
])

const STATE_COLOR: Record<ComponentState, string> = {
  ONLINE: 'var(--mr-state-online)',
  OFFLINE: 'var(--mr-state-offline)',
  NOT_CONFIGURED: 'var(--mr-state-not-configured)',
  UNKNOWN: 'var(--mr-state-unknown)',
  ERROR: 'var(--mr-state-error)'
}

/** 只有真实探活（/api/parse/info）能改变状态，其余组件固定 UNKNOWN / NOT_CONFIGURED */
function effectiveState(c: ComponentStatus): ComponentState {
  return c.realProbe ? store.apiState : c.state
}
function statusColor(c: ComponentStatus): string {
  return STATE_COLOR[effectiveState(c)]
}
function rateColor(v: number): string {
  return v >= 95 ? '#2fa06b' : v >= 92 ? '#1d6fe0' : '#d97706'
}

const trendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['上传', '解析成功', '解析失败'], bottom: 0, itemWidth: 12 },
  grid: { left: 40, right: 16, top: 16, bottom: 40 },
  xAxis: { type: 'category', data: demoTrend.map((t) => t.date), axisLine: { lineStyle: { color: '#dbe3ee' } } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#eef2f8' } } },
  series: [
    { name: '上传', type: 'line', smooth: true, symbol: 'none', data: demoTrend.map((t) => t.uploaded), lineStyle: { color: '#1d6fe0', width: 2 }, areaStyle: { color: 'rgba(29,111,224,0.08)' } },
    { name: '解析成功', type: 'line', smooth: true, symbol: 'none', data: demoTrend.map((t) => t.parsed), lineStyle: { color: '#2fa06b', width: 2 } },
    { name: '解析失败', type: 'line', smooth: true, symbol: 'none', data: demoTrend.map((t) => t.failed), lineStyle: { color: '#d64545', width: 2 } }
  ]
}))

const engineOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} 次（{d}%）' },
  legend: { bottom: 0, itemWidth: 12 },
  series: [{
    type: 'pie', radius: ['52%', '74%'], center: ['50%', '44%'], label: { show: false },
    data: demoEngineDist.map((e, i) => ({
      name: e.engine, value: e.count,
      itemStyle: { color: ['#1d6fe0', '#2fa06b', '#d97706'][i] }
    }))
  }]
}))

function probe() {
  store.probeBackend()
}

onMounted(probe)
</script>

<style scoped>
.scope-note {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 12px;
  background: #eef4ff;
  border: 1px solid #d5e5ff;
  border-radius: var(--mr-radius);
  color: #1e40af;
  font-size: 12px;
  line-height: 1.6;
}
.stat-grid { grid-template-columns: repeat(6, 1fr); }
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); margin-left: 8px; }
.rate-row { display: flex; align-items: center; gap: 10px; margin: 14px 0; }
.rate-name { width: 104px; font-size: 12px; color: var(--mr-text-2); }
.rate-detail { width: 64px; text-align: right; font-size: 12px; color: var(--mr-text-3); }
.component-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.component-item {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 10px 12px; border: 1px solid var(--mr-line);
  border-radius: 6px; background: #fafbfe; font-size: 13px;
}
.component-item .status-dot { margin-top: 5px; }
.component-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.component-name { font-weight: 600; }
.component-note {
  display: flex; align-items: center; flex-wrap: wrap; gap: 6px;
  color: var(--mr-text-3); font-size: 12px;
}
@media (max-width: 1440px) {
  .stat-grid { grid-template-columns: repeat(3, 1fr); }
  .component-row { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 1366px) {
  .stat-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
