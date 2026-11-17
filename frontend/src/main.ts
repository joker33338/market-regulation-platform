import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './styles/index.css'
import App from './App.vue'
import router from './router'
import { setupNoteToggle } from './utils/noteToggle'
import { installLoginNavigation } from './router/authNavigation'
import { useAppStore } from './stores/app'
import { hasToken } from './api/client'
import { onAuthStateChange } from './api/authEvents'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
const session = useAppStore(pinia)
// 在首次路由导航之前安装，避免匿名用户先进入工作台。
installLoginNavigation(router, { hasToken, clearSession: () => session.clearLocalSession(), subscribe: onAuthStateChange })
app.use(router)
app.use(ElementPlus, { locale: zhCn })
setupNoteToggle()
app.mount('#app')
