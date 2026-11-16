<template>
  <div class="login-wrap">
    <el-card shadow="never" class="login-card">
      <div class="login-brand">
        <div class="login-mark">市</div>
        <h1>市场监管法规知识库平台</h1>
        <p>智能文档解析 · 法规结构化 · 知识检索</p>
      </div>

      <el-tabs v-model="mode">
        <!-- ① 账号密码登录（v0.2.3 draft-4；当前 8180 v0.2.2 未加载该接口，提交后如实报错） -->
        <el-tab-pane label="账号登录" name="password">
          <el-form label-position="top" @submit.prevent>
            <el-form-item label="用户名" for="login-username">
              <el-input
                id="login-username" v-model="username" aria-label="用户名" maxlength="64"
                size="large"
                placeholder="请输入用户名"
                autocomplete="username"
                @keyup.enter="loginByPassword"
              />
            </el-form-item>
            <el-form-item label="密码" for="login-password">
              <el-input
                id="login-password" v-model="password" aria-label="密码" maxlength="256"
                type="password"
                size="large"
                show-password
                placeholder="请输入密码"
                autocomplete="current-password"
                @keyup.enter="loginByPassword"
              />
            </el-form-item>
          </el-form>
          <el-button type="primary" size="large" style="width: 100%" :loading="loading" :disabled="!canPasswordLogin" @click="loginByPassword">
            登录
          </el-button>
          <div class="mode-note">
            使用管理员分配的账号登录。登录失败时请核对用户名和密码，或联系管理员；多次失败后请稍后重试。
          </div>
        </el-tab-pane>

        <!-- ② 既有 API Token 模式（8180 v0.2.2 唯一可用） -->
        <el-tab-pane label="访问凭证登录" name="token">
          <el-input
            v-model="token"
            type="password"
            show-password
            size="large"
            placeholder="API Token（≥32 位，由管理员在 PARSING_API_TOKENS_JSON 配置）"
            @keyup.enter="loginByToken"
          />
          <el-button type="primary" size="large" style="width: 100%; margin-top: 14px" :loading="loading" @click="loginByToken">
            验证并进入
          </el-button>
          <div class="mode-note">
            兼容既有独立 Token：旧 Token 无服务端会话撤销，登出仅清除本机会话；
            账号登录接口由 v0.2.3 draft-4 提供，当前服务未加载时会如实返回错误，不回退演示数据。
          </div>
        </el-tab-pane>
      </el-tabs>

      <details class="login-security"><summary>登录与凭证安全说明</summary>
        <p><b>开发期</b>：Token / Bearer 仅存于内存 + sessionStorage（会话级），关闭标签页即失效，不写 localStorage、不打印日志。</p>
        <p><b>生产环境</b>：应使用服务端安全会话（HttpOnly Cookie / BFF），前端不长期持有访问 Token。</p>
        <p>MinerU 官方 API Key 与数据库口令只存在于 FastAPI 后端，浏览器绝不接触。</p>
      </details>
      <el-alert type="warning" :closable="false" style="margin-top: 14px"
        :title="releaseStatus.alertTitle" :description="releaseStatus.qaScope + '；页面业务数据均来自真实接口，未就绪或出错时显示明确异常态，不回退演示数据。'" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { releaseStatus } from '@/config/release'
import { toApiError } from '@/api/errors'

const router = useRouter()
const store = useAppStore()

const mode = ref<'password' | 'token'>('password')
const username = ref('')
const password = ref('')
const token = ref('')
const loading = ref(false)

const canPasswordLogin = computed(() =>
  username.value.trim().length >= 3 && password.value.length >= 1 && !loading.value
)

/** 密码只在内存短暂停留：请求发出后立即清空输入框 */
async function loginByPassword() {
  if (!canPasswordLogin.value) return
  loading.value = true
  try {
    const principalId = await store.passwordLogin(username.value.trim(), password.value)
    password.value = ''
    if (principalId) {
      ElMessage.success(`登录成功：${principalId}`)
    } else {
      ElMessage.success('登录成功，身份以 GET /api/auth/me 确认为准')
    }
    router.push('/dashboard')
  } catch (err) {
    password.value = ''
    const e = toApiError(err)
    if (e.status === 401) {
      ElMessage.error('登录失败（401）：用户名或密码不正确；连续失败会触发限流')
    } else if (e.status === 404) {
      ElMessage.error('当前服务未提供账号登录（404）：需 v0.2.3 draft-4 契约；请改用 API Token 登录')
    } else if (e.status === 429) {
      ElMessage.error('登录尝试过于频繁（429）：请稍后再试')
    } else {
      ElMessage.error(`登录失败：${e.hint}`)
    }
  } finally {
    loading.value = false
  }
}

async function loginByToken() {
  if (token.value.length < 32) {
    ElMessage.warning('Token 长度不足 32 位')
    return
  }
  if (loading.value) return
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
.login-wrap { min-height: 100dvh; padding:24px 12px; display: flex; align-items: center; justify-content: center; background: var(--mr-navy); }
.login-card { width: 460px; max-width:100%; }
.login-brand { text-align: center; margin-bottom: 24px; }
.login-mark { width: 48px; height: 48px; margin: 0 auto 12px; border-radius: 10px; background: var(--mr-primary); color: #fff; font-size: 22px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.login-brand h1 { font-size: 18px; margin: 0 0 6px; }
.login-brand p { margin: 0; color: var(--mr-text-2); font-size: 13px; }
.mode-note { margin-top: 12px; font-size: 12px; color: var(--mr-text-2); line-height: 1.8; }
.login-security { margin-top: 14px; padding: 10px 12px; background: #f5f9ff; border: 1px solid #d5e5ff; border-radius: var(--mr-radius); }
.login-security p { margin: 4px 0; font-size: 12px; color: var(--mr-text-2); line-height: 1.7; }
.login-security b { color: #1e40af; }
@media(max-width:600px) { .login-wrap { align-items:flex-start; } .login-brand { margin-bottom:16px; } }
</style>
