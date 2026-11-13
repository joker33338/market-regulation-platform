<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">处罚案例库</h1>
        <p class="page-desc">已发布处罚案例只读浏览 · 违法行为筛选 / 处罚依据引用 / 精确十进制罚款金额</p>
      </div>
      <div class="header-tags">
        <el-tag type="success" effect="plain">真实接口 GET /api/library/cases</el-tag>
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain">{{ contractLabel[contractState] }}</el-tag>
        <el-tag :type="caseRouteReady ? 'success' : 'warning'" effect="plain">
          {{ caseRouteReady ? '列表接口已加载' : '列表接口未加载' }}
        </el-tag>
      </div>
    </div>

    <!-- 案例库与法规库的差异：多 violation 筛选；详情为处罚依据引用 + 案例结构化字段 -->
    <LibraryBrowser kind="case" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import LibraryBrowser from '@/components/LibraryBrowser.vue'
import { contractLabel, contractState, hasCaseLibraryList } from '@/api/dataSource'

/**
 * 处罚案例库（v0.2.3 draft-5，只读）
 * - 与法规库同属「法规知识库」导航组，共用 LibraryBrowser 骨架；
 * - 本页额外提供 violation（≤200 字符）筛选，法规库不支持该参数；
 * - 详情子列表为 references（处罚依据引用），结构化字段含 penalty_amount：
 *   它是后端返回的精确十进制字符串或 null，禁止 Number() / toFixed / 近似显示；
 *   引用里的 law_version_id 不是 doc_version_id，本页不拼接条款正文请求。
 * - 运行期未加载 GET /api/library/cases 时，页面禁用且不发起任何业务请求。
 */
const caseRouteReady = computed(() => hasCaseLibraryList())
</script>

<style scoped>
.header-tags { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
</style>
