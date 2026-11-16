<template>
  <nav class="navigation" aria-label="主导航">
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
        @select="emit('navigate')"
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
          <el-menu-item index="/library/laws">法规库</el-menu-item>
          <el-menu-item index="/library/cases">处罚案例库</el-menu-item>
        </el-sub-menu>
        <el-menu-item v-if="isAdminIdentity" index="/admin/accounts">
          <el-icon><User /></el-icon><span>账号与权限</span>
        </el-menu-item>
        <el-menu-item index="/system">
          <el-icon><Setting /></el-icon><span>系统监控</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-foot">
        <el-tag size="small" type="success" effect="plain">{{ releaseStatus.shortLabel }}</el-tag>
      </div>
  </nav>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Monitor, FolderOpened, Cpu, View, Collection, Setting, User } from '@element-plus/icons-vue'
import { isAdminIdentity } from '@/api/principal'
import { releaseStatus } from '@/config/release'
const route = useRoute()
const activePath = computed(() => route.path)
const emit = defineEmits<{ (e: 'navigate'): void }>()
</script>
<style scoped>
.navigation { display:flex; flex-direction:column; height:100%; min-height:0; background:var(--mr-navy); }
.nav-menu { overflow-y:auto; min-height:0; }
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


</style>
