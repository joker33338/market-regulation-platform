import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layout/AppLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '首页工作台' }
      },
      {
        path: 'documents',
        name: 'Documents',
        component: () => import('@/views/DocumentsView.vue'),
        meta: { title: '文档管理' }
      },
      {
        path: 'parsing',
        name: 'Parsing',
        component: () => import('@/views/ParsingView.vue'),
        meta: { title: '智能解析中心' }
      },
      {
        path: 'review',
        name: 'Review',
        component: () => import('@/views/ReviewView.vue'),
        meta: { title: '文档审核中心' }
      },
      {
        path: 'knowledge/ingestion',
        name: 'Ingestion',
        component: () => import('@/views/IngestionView.vue'),
        meta: { title: '知识库入库管理' }
      },
      {
        path: 'knowledge/search',
        name: 'KnowledgeSearch',
        component: () => import('@/views/SearchView.vue'),
        meta: { title: '法规知识检索' }
      },
      {
        path: 'library/laws',
        name: 'LawLibrary',
        component: () => import('@/views/LawLibraryView.vue'),
        meta: { title: '法规库' }
      },
      {
        path: 'library/cases',
        name: 'CaseLibrary',
        component: () => import('@/views/CaseLibraryView.vue'),
        meta: { title: '处罚案例库' }
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('@/views/SystemView.vue'),
        meta: { title: '系统监控' }
      },
      {
        path: 'admin/accounts',
        name: 'Accounts',
        component: () => import('@/views/AccountsView.vue'),
        meta: { title: '账号与权限管理' }
      }
    ]
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.afterEach((to) => {
  document.title = to.meta.title
    ? `${to.meta.title as string} · 市场监管法规知识库平台`
    : '市场监管法规知识库平台'
})

export default router
