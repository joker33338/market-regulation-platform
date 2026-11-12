<template>
  <span class="status-tag">
    <span class="status-dot" :style="{ background: color }" />
    <span>{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * 文档生命周期状态标签
 * 颜色语义与 CSS token 一一对应，全站统一
 */
const props = defineProps<{ status: string }>()

const MAP: Record<string, { label: string; color: string }> = {
  pending:        { label: '待解析',   color: 'var(--mr-st-pending)' },
  parsing:        { label: '解析中',   color: 'var(--mr-st-running)' },
  running:        { label: '执行中',   color: 'var(--mr-st-running)' },
  success:        { label: '解析成功', color: 'var(--mr-st-success)' },
  succeeded:      { label: '解析成功', color: 'var(--mr-st-success)' },
  completed:      { label: '已完成',   color: 'var(--mr-st-success)' },
  partial:        { label: '部分成功', color: 'var(--mr-st-warning)' },
  failed:         { label: '解析失败', color: 'var(--mr-st-danger)' },
  timed_out:      { label: '超时',     color: 'var(--mr-st-danger)' },
  reviewing:      { label: '待审核',   color: 'var(--mr-st-warning)' },
  pending_review: { label: '待审核',   color: 'var(--mr-st-warning)' },
  reviewed:       { label: '已审核',   color: 'var(--mr-st-review)' },
  ingested:       { label: '已入库',   color: 'var(--mr-st-success)' },
  blocked:        { label: '阻塞',     color: 'var(--mr-state-error)' },
  cancelled:      { label: '已取消',   color: 'var(--mr-st-pending)' },
  canceled:       { label: '已取消',   color: 'var(--mr-st-pending)' }
}

const label = computed(() => MAP[props.status]?.label ?? props.status)
const color = computed(() => MAP[props.status]?.color ?? 'var(--mr-st-pending)')
</script>

<style scoped>
.status-tag {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  white-space: nowrap;
}
</style>
