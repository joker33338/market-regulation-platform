<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">法规知识检索</h1>
        <p class="page-desc">BGE-M3 向量检索 · 法条级定位 · 版本可追溯（法律依据必须可追溯）</p>
      </div>
      <DemoBadge />
    </div>

    <!-- 接口未接入：禁止伪造法条原文与生成式结论 -->
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="检索接口未接入 · 未提供任何法律依据"
      description="后端 qa_core/retrieval/ 仅有服务层，无检索 HTTP 接口。为遵守「禁止伪造法律原文、不能让前端编造法规结论」，本页不返回任何法条文本或检索结论；下方仅展示接口交付后的结果字段契约。"
    />

    <el-card shadow="never" style="margin-top: 16px">
      <div class="search-bar">
        <el-input
          v-model="query"
          size="large"
          placeholder="检索接口未接入，暂不可查询"
          disabled
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-tooltip :content="disabledHint" placement="top">
          <span><el-button type="primary" size="large" disabled>检索</el-button></span>
        </el-tooltip>
      </div>
      <div class="filter-row">
        <el-select v-model="filters.kbVersion" size="small" placeholder="法规版本" disabled style="width: 130px" />
        <el-select v-model="filters.authority" size="small" placeholder="发布机关" disabled style="width: 200px" />
        <el-select v-model="filters.effectiveOnly" size="small" placeholder="生效状态" disabled style="width: 130px" />
        <el-checkbox v-model="filters.semantic" size="small" disabled>语义检索</el-checkbox>
        <el-checkbox v-model="filters.hybrid" size="small" disabled>混合检索（后端真实支持时启用）</el-checkbox>
        <span class="mr-disabled-hint">{{ disabledHint }}</span>
      </div>
    </el-card>

    <!-- 未检索到相关依据 -->
    <el-card shadow="never" style="margin-top: 16px">
      <el-empty description="未检索到相关依据（检索接口未接入）">
        <template #default>
          <p class="empty-note">
            无可靠检索依据时，本页不会生成任何法规名称、条号、原文或结论。
            接口交付后，结果将包含下列字段，且每条命中都可追溯到来源文件与原始分数。
          </p>
        </template>
      </el-empty>
    </el-card>

    <!-- 结果字段契约（不含任何法条内容） -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>检索结果字段契约（接口交付后启用）</span>
          <span class="card-sub">POST /api/knowledge/search</span>
        </div>
      </template>
      <div class="field-grid">
        <el-tag v-for="f in RESULT_FIELDS" :key="f" effect="plain" size="small">{{ f }}</el-tag>
      </div>
      <el-divider />
      <div class="mode-grid">
        <div><b>自然语言检索</b><span>输入监管业务问题，返回相关法条与依据</span></div>
        <div><b>关键词检索</b><span>按法规名称、条号、文号精确匹配</span></div>
        <div><b>语义检索</b><span>BGE-M3 向量召回，展示原始分数</span></div>
        <div><b>混合检索</b><span>仅当后端真实支持时启用，前端不模拟</span></div>
      </div>
      <div class="mr-disabled-hint" style="margin-top: 12px">
        接口未接入期间，筛选器、检索按钮与结果区全部禁用，不出现「演示命中」或伪造的相关度分数。
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import DemoBadge from '@/components/DemoBadge.vue'
import { RESULT_FIELDS } from '@/api/mock/search'
import { unimplementedHint } from '@/api/dataSource'

const disabledHint = unimplementedHint('POST /api/knowledge/search')
const query = ref('')
const filters = ref({
  kbVersion: '',
  authority: '',
  effectiveOnly: '',
  semantic: false,
  hybrid: false
})
</script>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); }
.search-bar { display: flex; gap: 12px; }
.filter-row { display: flex; align-items: center; gap: 12px; margin-top: 12px; flex-wrap: wrap; }
.empty-note { max-width: 560px; margin: 0 auto; color: var(--mr-text-2); font-size: 13px; line-height: 1.8; }
.field-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.mode-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.mode-grid > div { padding: 10px 12px; border: 1px solid var(--mr-line); border-radius: 6px; background: #fafbfe; display: flex; flex-direction: column; gap: 4px; }
.mode-grid b { font-size: 13px; }
.mode-grid span { font-size: 12px; color: var(--mr-text-2); }
@media (max-width: 1366px) {
  .mode-grid { grid-template-columns: 1fr; }
}
</style>
