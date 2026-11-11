<template>
  <div class="login-wrap">
    <el-card shadow="never" class="login-card">
      <div class="login-brand">
        <div class="login-mark">市</div>
        <h1>市场监管法规知识库平台</h1>
        <p>智能文档解析 · 法规结构化 · 知识检索</p>
      </div>
      <el-input
        v-model="token"
        type="password"
        show-password
        size="large"
        placeholder="API Token（≥32 位，由管理员在 PARSING_API_TOKENS_JSON 配置）"
        @keyup.enter="login"
      />
      <el-button type="primary" size="large" style="width: 100%; margin-top: 14px" :loading="loading" @click="login">
        验证并进入
      </el-button>
      <div class="login-security">
        <p><b>开发期</b>：Token 仅存于内存 + sessionStorage（会话级），关闭标签页即失效，不写 localStorage、不打印日志。</p>
        <p><b>生产环境</b>：应使用服务端安全会话（HttpOnly Cookie / BFF），前端不长期持有访问 Token。</p>
        <p>MinerU 官方 API Key 与数据库口令只存在于 FastAPI 后端，浏览器绝不接触。</p>
      </div>
      <el-alert type="warning" :closable="false" style="margin-top: 14px"
        :title="releaseStatus.alertTitle" :description="releaseStatus.qaScope + '；页面业务数据均来自真实接口，未就绪或出错时显示明确异常态，不回退演示数据。'" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { releaseStatus } from '@/config/release'

const router = useRouter()
const store = useAppStore()
const token = ref('')
const loading = ref(false)

async function login() {
  if (token.value.length < 32) {
    ElMessage.warning('Token 长度不足 32 位')
    return
  }
  loading.value = true
  try {
    await store.saveToken(token.value)
    if (store.apiState === 'ONLINE') {
      router.push('/dashboard')
    } else {
      ElMessage.warning('Token 已保存到当前会话，但后端未响应；页面将显示异常态，不会回退演示数据')
      router.push('/dashboard')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--mr-navy); }
.login-card { width: 460px; }
.login-brand { text-align: center; margin-bottom: 24px; }
.login-mark { width: 48px; height: 48px; margin: 0 auto 12px; border-radius: 10px; background: var(--mr-primary); color: #fff; font-size: 22px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.login-brand h1 { font-size: 18px; margin: 0 0 6px; }
.login-brand p { margin: 0; color: var(--mr-text-2); font-size: 13px; }
.login-security { margin-top: 14px; padding: 10px 12px; background: #f5f9ff; border: 1px solid #d5e5ff; border-radius: var(--mr-radius); }
.login-security p { margin: 4px 0; font-size: 12px; color: var(--mr-text-2); line-height: 1.7; }
.login-security b { color: #1e40af; }
</style>
