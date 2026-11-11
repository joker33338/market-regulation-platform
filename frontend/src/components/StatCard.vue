<template>
  <el-card shadow="never" class="stat-card" :body-style="{ padding: '18px 20px' }">
    <div class="stat-head">
      <span class="stat-label">{{ label }}</span>
      <span style="display: inline-flex; gap: 4px; align-items: center">
        <span v-if="real" class="real-badge">REAL</span>
        <DemoBadge v-if="demo" />
      </span>
    </div>
    <div class="stat-value num" :style="color ? { color } : undefined">
      {{ formatted }}
    </div>
    <div v-if="hint || scope" class="stat-hint">
      <span v-if="scope" class="stat-scope">{{ scope }}</span>{{ hint }}
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DemoBadge from './DemoBadge.vue'

const props = defineProps<{
  label: string
  value: number
  hint?: string
  color?: string
  /** DEMO 数据必须置 demo=true，徽章贴近数值显示 */
  demo?: boolean
  /** 真实接口数据置 real=true */
  real?: boolean
  /** 统计时间范围，如「近 14 天」——所有统计卡必须同口径 */
  scope?: string
}>()

const formatted = computed(() => props.value.toLocaleString('zh-CN'))
</script>

<style scoped>
.stat-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.stat-label {
  font-size: 13px;
  color: var(--mr-text-2);
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-hint {
  font-size: 12px;
  color: var(--mr-text-3);
}
</style>
