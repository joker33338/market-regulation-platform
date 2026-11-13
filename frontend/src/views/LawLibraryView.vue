<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">法规库</h1>
        <p class="page-desc">已发布法规版本只读浏览 · 章节 / 条款 / 条款正文（原始 OCR 文本未经人工核验）</p>
      </div>
      <div class="header-tags">
        <el-tag type="success" effect="plain">真实接口 GET /api/library/laws</el-tag>
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain">{{ contractLabel[contractState] }}</el-tag>
        <el-tag :type="lawRouteReady ? 'success' : 'warning'" effect="plain">
          {{ lawRouteReady ? '列表接口已加载' : '列表接口未加载' }}
        </el-tag>
      </div>
    </div>

    <!-- 法规库与案例库的差异：不渲染也不发送 violation；详情为章节 / 条款 / 条款正文 -->
    <LibraryBrowser kind="law" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import LibraryBrowser from '@/components/LibraryBrowser.vue'
import { contractLabel, contractState, hasLawLibraryList } from '@/api/dataSource'

/**
 * 法规库（v0.2.3 draft-5，只读）
 * - 与处罚案例库同属「法规知识库」导航组，共用 LibraryBrowser 骨架；
 * - 本页筛选仅 query / kb_version(ADMIN) / page / page_size，不渲染也不发送 violation
 *   （法规库传 violation 会返回 422 violation_filter_case_only）；
 * - 详情子列表为 chapters / articles，并可由条款行进入 articles/{article_id} 条款正文；
 *   不提供处罚依据引用，也不从 law_version_id 推导 doc_version_id。
 * - 运行期未加载 GET /api/library/laws 时，页面禁用且不发起任何业务请求。
 */
const lawRouteReady = computed(() => hasLawLibraryList())
</script>

<style scoped>
.header-tags { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
</style>
