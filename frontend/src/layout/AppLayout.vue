<template>
  <div class="layout">
    <!-- 左侧固定导航：深海军蓝 -->
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">市</div>
        <div class="brand-text">
          <span class="brand-name">市场监管</span>
          <span class="brand-sub">法规知识库平台</span>
        </div>
      </div>

      <el-menu
        class="nav-menu"
        :default-active="activePath"
        router
        background-color="transparent"
        text-color="#b8c7dd"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon><span>首页工作台</span>
        </el-menu-item>
        <el-menu-item index="/documents">
          <el-icon><FolderOpened /></el-icon><span>文档管理</span>
        </el-menu-item>
        <el-menu-item index="/parsing">
          <el-icon><Cpu /></el-icon><span>智能解析中心</span>
        </el-menu-item>
        <el-menu-item index="/review">
          <el-icon><View /></el-icon><span>文档审核中心</span>
        </el-menu-item>
        <el-sub-menu index="knowledge">
          <template #title>
            <el-icon><Collection /></el-icon><span>法规知识库</span>
          </template>
          <el-menu-item index="/knowledge/ingestion">入库管理</el-menu-item>
          <el-menu-item index="/knowledge/search">知识检索</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/system">
          <el-icon><Setting /></el-icon><span>系统监控</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-foot">
        <el-tag size="small" type="success" effect="plain">{{ releaseStatus.shortLabel }}</el-tag>
      </div>
    </aside>

    <!-- 右侧主区域 -->
    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <span class="system-name">市场监管智能文档解析与法规知识库管理平台</span>
        </div>
        <div class="topbar-right">
          <span class="backend-status" @click="probe">
            <span class="status-dot" :style="{ background: backendColor }" />
            解析服务：{{ backendLabel }}
          </span>
          <el-dropdown>
            <span class="user-chip">
              <el-icon><UserFilled /></el-icon>
              {{ store.token ? '审核员' : '未配置 Token' }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="goSystem">API Token 配置</el-dropdown-item>
                <el-dropdown-item divided @click="logout">清除 Token</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Monitor, FolderOpened, Cpu, View, Collection, Setting, UserFilled, ArrowDown
} from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { releaseStatus } from '@/config/release'

const route = useRoute()
const router = useRouter()
const store = useAppStore()

const activePath = computed(() => route.path)

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
function logout() {
  store.logout()
}

onMounted(() => {
  if (store.token) store.probeBackend()
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
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--mr-primary);
  color: #fff;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
}
.brand-text {
  display: flex;
  flex-direction: column;
}
.brand-name {
  color: #fff;
  font-size: 15px;
  font-weight: 600;
}
.brand-sub {
  color: #8ea6c8;
  font-size: 11px;
}
.nav-menu {
  flex: 1;
  border-right: none;
  padding: 8px;
}
.nav-menu :deep(.el-menu-item),
.nav-menu :deep(.el-sub-menu__title) {
  border-radius: 6px;
  margin: 2px 0;
  height: 42px;
  line-height: 42px;
}
.nav-menu :deep(.el-menu-item:hover),
.nav-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.06);
}
.nav-menu :deep(.el-menu-item.is-active) {
  background: var(--mr-navy-active);
}
.nav-menu :deep(.el-menu) {
  background: transparent;
}
.sidebar-foot {
  padding: 14px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
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
</style>
