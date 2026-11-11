<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">知识库入库管理</h1>
        <p class="page-desc">离线入库流水线：从解析完成到 PostgreSQL 落库的全过程可视化</p>
      </div>
      <div style="display: flex; gap: 8px; align-items: center">
        <el-tooltip :content="disabledHint" placement="top">
          <span><el-button type="primary" disabled>发起入库批次</el-button></span>
        </el-tooltip>
        <DemoBadge />
      </div>
    </div>

    <!-- kb_version 不一致 → 整批阻断 -->
    <el-alert
      v-if="versionCheck && !versionCheck.consistent"
      type="error"
      :closable="false"
      class="block-banner"
      show-icon
    >
      <template #title>
        <b>入库已阻断：kb_version 版本不一致</b>
      </template>
      <template #default>
        期望版本 <b class="num">{{ versionCheck.expectedVersion }}</b>，
        实际检出 <b class="num">{{ versionCheck.actualVersion }}</b>；
        受阻批次：<b>{{ versionCheck.blockedBatchIds.join('、') || '—' }}</b>。
        检查时间 {{ versionCheck.checkedAt }}（DEMO）。
        版本一致性未通过前，禁止发起任何入库或数据库写入动作。
      </template>
    </el-alert>
    <div class="mr-disabled-hint" style="margin-bottom: 12px">{{ disabledHint }}</div>

    <!-- 入库前检查 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>入库前检查 <DemoBadge /></span>
          <span class="card-sub">{{ blockingCount }} 项阻断 · 接口未接入，结果仅供界面演示</span>
        </div>
      </template>
      <div class="check-grid">
        <div v-for="c in precheck" :key="c.key" class="check-item" :class="{ 'check-bad': !c.passed }">
          <el-icon :color="c.passed ? 'var(--mr-st-success)' : 'var(--mr-state-error)'">
            <CircleCheckFilled v-if="c.passed" /><CircleCloseFilled v-else />
          </el-icon>
          <div class="check-text">
            <div class="check-name">
              {{ c.name }}
              <el-tag v-if="c.blocking" size="small" type="danger" effect="plain">阻断项</el-tag>
            </div>
            <div class="check-detail">{{ c.detail }}</div>
          </div>
        </div>
      </div>
      <div class="mr-disabled-hint" style="margin-top: 12px">
        批次授权、重复批次检查、版本一致性校验的真实结果需后端
        <code>POST /api/ingestion/precheck</code> 与 <code>GET /api/ingestion/version-check</code>；
        当前前端不执行任何数据库写入。
      </div>
    </el-card>

    <!-- 七阶段流水线 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>入库流水线（当前批次 B20261109-02）<DemoBadge /></span>
          <el-tag size="small" type="primary" effect="plain">执行中（DEMO）</el-tag>
        </div>
      </template>
      <div class="pipeline">
        <div v-for="(stage, i) in pipeline" :key="stage.key" class="stage-wrap">
          <div class="stage" :class="stageClass(stage)">
            <div class="stage-name">{{ stage.name }}</div>
            <div class="stage-nums">
              <span class="num ok">{{ stage.success }} 成功</span>
              <span class="num" :class="{ bad: stage.failed > 0 }">{{ stage.failed }} 失败</span>
            </div>
            <el-progress
              :percentage="stage.total ? Math.round((stage.success + stage.failed) / stage.total * 100) : 0"
              :stroke-width="6"
              :status="stage.failed > 0 ? 'exception' : undefined"
              :color="stage.failed > 0 ? '#d64545' : '#2fa06b'"
            />
            <div class="stage-meta num">{{ stage.total }} 任务 · 均耗时 {{ stage.avgSeconds }}s</div>
            <div v-if="stage.running" class="stage-running">
              <el-icon class="is-loading" size="12"><Loading /></el-icon>{{ stage.running }}
            </div>
            <div v-if="stage.lastError" class="stage-error" @click="showError(stage)">{{ stage.lastError }}</div>
          </div>
          <div v-if="i < pipeline.length - 1" class="stage-arrow">→</div>
        </div>
      </div>
    </el-card>

    <!-- 批次 + 法规数据 -->
    <div class="card-grid" style="grid-template-columns: 1fr 2fr; margin-top: 16px">
      <el-card shadow="never">
        <template #header><div class="card-head"><span>入库批次 <DemoBadge /></span><span class="card-sub">四态</span></div></template>
        <el-table :data="batches" size="small" highlight-current-row @current-change="onBatchSelect">
          <el-table-column prop="batchId" label="批次号" width="130" />
          <el-table-column prop="startedAt" label="开始时间" width="130" />
          <el-table-column label="成功/失败" width="90">
            <template #default="{ row }">
              <span class="num">
                <span style="color: var(--mr-st-success)">{{ row.successCount }}</span>
                <span style="color: var(--mr-text-3)"> / </span>
                <span :style="{ color: row.failedCount ? 'var(--mr-st-danger)' : 'var(--mr-text-3)' }">{{ row.failedCount }}</span>
              </span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="batchTagType(row.status)" effect="plain">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="blockedBatch" class="block-detail">
          <b>阻断原因：</b>{{ blockedBatch.blockedReason }}
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <span>法规数据 <DemoBadge /></span>
            <el-input v-model="regKeyword" placeholder="搜索法规名称 / 文号" clearable size="small" style="width: 220px" />
          </div>
        </template>
        <el-table :data="filteredRegulations" size="small">
          <el-table-column prop="name" label="法规名称" min-width="200" show-overflow-tooltip />
          <el-table-column prop="authority" label="发布机关" width="170" show-overflow-tooltip />
          <el-table-column prop="docNumber" label="文号" width="130" />
          <el-table-column prop="effectiveDate" label="生效日期" width="100" />
          <el-table-column label="失效日期" width="100">
            <template #default="{ row }">{{ row.expiryDate || '现行有效' }}</template>
          </el-table-column>
          <el-table-column prop="articleCount" label="法条数" width="80" align="right">
            <template #default="{ row }"><span class="num">{{ row.articleCount }}</span></template>
          </el-table-column>
          <el-table-column prop="kbVersion" label="版本" width="95" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" effect="plain" :type="regTagType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }"><el-button text size="small" type="primary" @click="openRecord(row)">记录</el-button></template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-drawer v-model="drawer" title="入库记录（DEMO）" size="480px">
      <template v-if="currentReg">
        <el-alert type="warning" :closable="false" style="margin-bottom: 14px"
          title="演示数据" description="入库记录查询接口未接入，以下字段用于展示追溯信息结构，不代表真实落库结果。" />
        <el-descriptions :column="1" border>
          <el-descriptions-item label="法规名称">{{ currentReg.name }}</el-descriptions-item>
          <el-descriptions-item label="发布机关">{{ currentReg.authority }}</el-descriptions-item>
          <el-descriptions-item label="文号">{{ currentReg.docNumber }}</el-descriptions-item>
          <el-descriptions-item label="发布时间">{{ currentReg.publishDate }}</el-descriptions-item>
          <el-descriptions-item label="生效日期">{{ currentReg.effectiveDate }}</el-descriptions-item>
          <el-descriptions-item label="失效日期">{{ currentReg.expiryDate || '现行有效' }}</el-descriptions-item>
          <el-descriptions-item label="法条数量">{{ currentReg.articleCount }}</el-descriptions-item>
          <el-descriptions-item label="入库版本">{{ currentReg.kbVersion }}</el-descriptions-item>
          <el-descriptions-item label="所属批次">{{ currentReg.batchId }}</el-descriptions-item>
          <el-descriptions-item label="数据状态">{{ currentReg.status }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import DemoBadge from '@/components/DemoBadge.vue'
import { unimplementedHint } from '@/api/dataSource'
import {
  fetchPipeline, fetchRegulations, fetchBatches, fetchVersionCheck, fetchPrecheck,
  type PipelineStage, type RegulationRecord, type IngestionBatch, type VersionCheck, type PrecheckItem
} from '@/api/mock/ingestion'

const disabledHint = unimplementedHint('POST /api/ingestion/precheck + /api/ingestion/batches（含批次授权）')

const pipeline = ref<PipelineStage[]>([])
const regulations = ref<RegulationRecord[]>([])
const batches = ref<IngestionBatch[]>([])
const precheck = ref<PrecheckItem[]>([])
const versionCheck = ref<VersionCheck | null>(null)
const regKeyword = ref('')
const drawer = ref(false)
const currentReg = ref<RegulationRecord | null>(null)

const blockingCount = computed(() => precheck.value.filter((c) => c.blocking && !c.passed).length)
const blockedBatch = computed(() => batches.value.find((b) => b.status === '阻塞') || null)
const filteredRegulations = computed(() => {
  if (!regKeyword.value) return regulations.value
  const k = regKeyword.value
  return regulations.value.filter((r) => r.name.includes(k) || r.docNumber.includes(k))
})

function stageClass(stage: PipelineStage) {
  return {
    'stage-failed': stage.failed > 0 && !stage.running,
    'stage-running': !!stage.running,
    'stage-done': stage.failed === 0 && stage.success === stage.total && stage.total > 0
  }
}

function batchTagType(s: string): string {
  return s === '已完成' ? 'success' : s === '执行中' ? 'primary' : s === '阻塞' ? 'danger' : 'danger'
}

function regTagType(s: string): string {
  return s === '已入库' ? 'success' : s === '入库中' ? 'primary' : s === '阻塞' ? 'danger' : s === '入库失败' ? 'danger' : 'info'
}

function showError(stage: PipelineStage) {
  ElMessageBox.alert(stage.lastError || '无错误详情', `${stage.name} · 错误日志（DEMO）`, { confirmButtonText: '知道了' })
}

function onBatchSelect(row: IngestionBatch) {
  if (!row) return
  ElMessage.info(`已查看批次 ${row.batchId}（DEMO 数据不联动刷新，也不触发任何写入）`)
}

function openRecord(row: RegulationRecord) {
  currentReg.value = row
  drawer.value = true
}

onMounted(async () => {
  const [p, r, b, v, c] = await Promise.all([
    fetchPipeline(), fetchRegulations(), fetchBatches(), fetchVersionCheck(), fetchPrecheck()
  ])
  pipeline.value = p.data
  regulations.value = r.data
  batches.value = b.data
  versionCheck.value = v.data
  precheck.value = c.data
})
</script>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); }
.block-banner { margin-bottom: 12px; }
.check-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.check-item { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border: 1px solid var(--mr-line); border-radius: 6px; background: #fafbfe; }
.check-bad { border-color: #fecaca; background: #fef2f2; }
.check-text { min-width: 0; }
.check-name { font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.check-detail { font-size: 12px; color: var(--mr-text-2); margin-top: 3px; }
.block-detail { margin-top: 12px; padding: 8px 10px; font-size: 12px; color: var(--mr-state-error); background: #fef2f2; border-radius: 4px; }
.pipeline { display: flex; align-items: stretch; gap: 0; overflow-x: auto; padding: 4px 0; }
.stage-wrap { display: flex; align-items: center; flex: 1; min-width: 150px; }
.stage { flex: 1; border: 1px solid var(--mr-line); border-radius: var(--mr-radius); padding: 12px; background: #fafbfe; display: flex; flex-direction: column; gap: 6px; }
.stage-done { border-color: #bbf7d0; background: #f0fdf4; }
.stage-failed { border-color: #fecaca; background: #fef2f2; }
.stage-running { border-color: var(--mr-primary); background: #eff6ff; }
.stage-name { font-weight: 600; font-size: 13px; }
.stage-nums { display: flex; gap: 10px; font-size: 12px; }
.stage-nums .ok { color: var(--mr-st-success); }
.stage-nums .bad { color: var(--mr-st-danger); }
.stage-meta { font-size: 11px; color: var(--mr-text-3); }
.stage-running-text { font-size: 11px; color: var(--mr-primary); display: flex; align-items: center; gap: 4px; }
.stage-error { font-size: 11px; color: var(--mr-st-danger); cursor: pointer; text-decoration: underline; }
.stage-arrow { padding: 0 6px; color: var(--mr-text-3); flex-shrink: 0; }
@media (max-width: 1366px) {
  .check-grid { grid-template-columns: 1fr; }
}
</style>
