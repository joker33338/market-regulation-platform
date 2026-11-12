<template>
  <div class="async-panel">
    <div v-if="state === 'loading'" class="ap-loading" v-loading="true">
      <span class="ap-loading-text">{{ loadingText }}</span>
    </div>

    <el-alert
      v-else-if="state === 'no-permission'"
      type="warning"
      :closable="false"
      show-icon
      title="未认证 / 无权限"
      :description="error || '所有 /api/* 请求需要 Bearer Token；请在系统监控页配置有效会话凭证。后端按 owner 隔离数据，跨用户访问返回 404。'"
    >
      <template #default>
        <div class="ap-actions">
          <el-button size="small" @click="emit('retry')">配置后重试</el-button>
        </div>
      </template>
    </el-alert>

    <el-alert
      v-else-if="state === 'outdated'"
      type="warning"
      :closable="false"
      show-icon
      title="后端服务未加载 v0.2.2 契约"
      description="运行期探测 /api/openapi.json 失败或缺少新增路由：活动 8180 实例仍可能是 v0.2.1 旧镜像。按后端交付约定，切换候选镜像需用户明确授权；本页不会用离线快照、Mock 或 DEMO 冒充真实响应。"
    >
      <template #default>
        <p v-if="error" class="ap-detail">{{ error }}</p>
        <div class="ap-actions">
          <el-button size="small" @click="emit('retry')">重新探测</el-button>
        </div>
      </template>
    </el-alert>

    <el-alert
      v-else-if="state === 'unavailable'"
      type="error"
      :closable="false"
      show-icon
      title="服务不可达 / 暂不可用"
      :description="error || '后端服务未响应或返回 5xx，请确认 8180 端口、Vite 代理与服务状态。'"
    >
      <template #default>
        <div class="ap-actions">
          <el-button size="small" @click="emit('retry')">重试</el-button>
        </div>
      </template>
    </el-alert>

    <el-alert
      v-else-if="state === 'error'"
      type="error"
      :closable="false"
      show-icon
      title="请求失败"
      :description="error || '接口返回错误，未展示任何替代数据。'"
    >
      <template #default>
        <div class="ap-actions">
          <el-button size="small" @click="emit('retry')">重试</el-button>
        </div>
      </template>
    </el-alert>

    <div v-else-if="state === 'empty'" class="ap-empty">
      <slot name="empty">
        <el-empty :image-size="70" :description="emptyText || '暂无数据'">
          <el-button size="small" @click="emit('retry')">刷新</el-button>
        </el-empty>
      </slot>
    </div>

    <slot v-else />
  </div>
</template>

<script setup lang="ts">
import type { LoadState } from '@/api/types'

/**
 * 七页面统一状态面板
 * 只呈现真实状态：无 DEMO 回退、无假成功、无无限加载；所有异常态都带「重试」反馈。
 */
withDefaults(
  defineProps<{
    state: LoadState
    error?: string
    emptyText?: string
    loadingText?: string
  }>(),
  { error: '', emptyText: '暂无数据', loadingText: '正在从后端加载真实数据…' }
)

const emit = defineEmits<{ (e: 'retry'): void }>()
</script>

<style scoped>
.ap-loading {
  position: relative;
  min-height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ap-loading-text {
  font-size: 12px;
  color: var(--mr-text-3);
  padding-top: 28px;
}
.ap-actions {
  margin-top: 8px;
}
.ap-detail {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  word-break: break-all;
}
.ap-empty {
  padding: 8px 0;
}
</style>
