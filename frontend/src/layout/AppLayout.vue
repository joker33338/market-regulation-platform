<template>
  <div class="layout">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <el-drawer v-model="navOpen" title="页面导航" direction="ltr" size="min(288px, 90vw)" class="mobile-navigation" @closed="navTrigger?.focus()">
      <AppNavigation @navigate="navOpen = false" />
    </el-drawer>
    <!-- 左侧固定导航：深海军蓝 -->
    <aside class="sidebar">
      <AppNavigation />
    </aside>

    <!-- 右侧主区域 -->
    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <button ref="navTrigger" class="nav-toggle" aria-label="打开页面导航" :aria-expanded="navOpen" @click="navOpen = true"><el-icon><Menu /></el-icon></button>
          <span class="system-name">{{ route.meta.title || '市场监管工作台' }}</span>
        </div>
        <div class="topbar-right">
          <button class="backend-status" aria-label="重新检查解析服务状态" @click="probe">
            <span class="status-dot" :style="{ background: backendColor }" />
            解析服务：{{ backendLabel }}
          </button>
          <el-dropdown>
            <button class="user-chip" aria-label="账户菜单">
              <el-icon><UserFilled /></el-icon>
              {{ identityChip }}
              <el-icon><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>当前登录人员：{{ principalIdText }}</el-dropdown-item>
                <el-dropdown-item disabled>业务数据归属：{{ principalOwnerText }}</el-dropdown-item>
                <el-dropdown-item disabled>角色：{{ principalRoleText }}</el-dropdown-item>
                <el-dropdown-item disabled>审核范围：{{ principalScopeText }}</el-dropdown-item>
                <el-dropdown-item disabled>登录方式：{{ store.authMode === 'password' ? '账号密码（服务端会话）' : 'API Token（独立凭证）' }}</el-dropdown-item>
                <el-dropdown-item divided @click="refreshIdentity">重新确认身份（GET /api/auth/me）</el-dropdown-item>
                <el-dropdown-item @click="goSystem">API Token 配置</el-dropdown-item>
                <el-dropdown-item divided @click="logout">{{ store.authMode === 'password' ? '退出登录（撤销会话）' : '清除 Token' }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main id="main-content" class="content" tabindex="-1">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Menu, UserFilled, ArrowDown } from '@element-plus/icons-vue'
import AppNavigation from './AppNavigation.vue'
import { useAppStore } from '@/stores/app'
import { releaseStatus } from '@/config/release'
import {
  principal, principalState, loadPrincipal,
  principalRoleText, principalOwnerText, principalScopeText
} from '@/api/principal'

const route = useRoute()
const router = useRouter()
const store = useAppStore()

const navOpen = ref(false)
const navTrigger = ref<HTMLButtonElement | null>(null)
watch(() => route.path, () => { navOpen.value = false })

/** 顶栏只展示后端确认的当前登录人员与角色，不再把 owner 显示成「审核员」 */
const identityChip = computed(() => {
  if (!store.token) return '未配置 Token'
  if (principalState.value === 'ready' && principal.value) {
    return principalRoleText.value.replace('ADMIN', '管理员').replace('REVIEWER', '审核人员').replace('USER', '普通用户')
  }
  return '身份未确认'
})
const principalIdText = computed(() => principal.value?.principal_id || '未确认')

function refreshIdentity() {
  void loadPrincipal(true)
}

const backendLabel = computed(() => {
  if (store.apiOnline === 'online') return '在线'
  if (store.apiOnline === 'offline') return '离线'
  return '未知'
})
const backendColor = computed(() => {
  if (store.apiOnline === 'online') return 'var(--mr-st-success)'
  if (store.apiOnline === 'offline') return 'var(--mr-st-danger)'
  return 'var(--mr-st-pending)'
})

function probe() {
  store.probeBackend()
}
function goSystem() {
  router.push('/system')
}

/**
 * 退出登录：账号会话先尝试服务端撤销（POST /api/auth/logout，仅 draft-4 新会话支持）；
 * 旧独立 Token（409）或网络失败只清本机会话，并如实提示，不宣称服务端已撤销。
 */
async function logout() {
  const wasPassword = store.authMode === 'password'
  const revoked = await store.logout()
  if (wasPassword) {
    if (revoked) ElMessage.success('会话已在服务端撤销，本地凭证已清除')
    else ElMessage.warning('已清除本机会话；服务端撤销未确认（旧 Token 不支持或网络失败）')
  } else {
    ElMessage.success('已清除本机会话凭证（旧独立 Token 不支持服务端撤销）')
  }
  router.push('/login')
}

onMounted(() => {
  if (!store.token) return
  store.probeBackend()
  // 页面刷新后重新向后端确认身份；不使用任何本地缓存的旧角色/范围
  if (principalState.value !== 'ready') void loadPrincipal(true)
})
</script>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ---------- 侧边导航 ---------- */
.sidebar {
  width: var(--mr-sidebar-w);
  flex-shrink: 0;
  background: var(--mr-navy);
  display: flex;
  flex-direction: column;
}
/* ---------- 顶部栏 ---------- */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.topbar {
  height: var(--mr-header-h);
  background: var(--mr-surface);
  border-bottom: 1px solid var(--mr-line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
}
.system-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--mr-text-1);
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 18px;
}
.backend-status {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  color: var(--mr-text-2);
  cursor: pointer;
}
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--mr-text-1);
}

.content {
  flex: 1;
  overflow-y: auto;
}

.topbar-left { display:flex; align-items:center; gap:12px; min-width:0; }
.system-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.user-chip { max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.backend-status,.user-chip,.nav-toggle { border:0; background:transparent; font:inherit; padding:8px; border-radius:6px; }
.nav-toggle { display:none; align-items:center; justify-content:center; color:var(--mr-text-1); font-size:20px; cursor:pointer; }
.content { min-width:0; scroll-behavior:smooth; }
@media (max-width:1023px) { .sidebar { display:none; } .nav-toggle { display:inline-flex; } .topbar { padding:0 12px; } .topbar-right { gap:8px; } }
@media (max-width:600px) { .backend-status { display:none; } .user-chip { max-width:130px; font-size:12px; } .system-name { font-size:13px; } }
</style>
