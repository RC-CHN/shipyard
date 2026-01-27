import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', requiresAuth: false, hideLayout: true }
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/dashboard/index.vue'),
    meta: { title: '仪表盘', requiresAuth: true }
  },
  {
    path: '/ships',
    name: 'Ships',
    component: () => import('@/views/ships/index.vue'),
    meta: { title: '容器管理', requiresAuth: true }
  },
  {
    path: '/ships/create',
    name: 'CreateShip',
    component: () => import('@/views/ship-create/index.vue'),
    meta: { title: '创建容器', requiresAuth: true }
  },
  {
    path: '/ships/:id',
    name: 'ShipDetail',
    component: () => import('@/views/ship-detail/index.vue'),
    meta: { title: '容器详情', requiresAuth: true }
  },
  {
    path: '/sessions',
    name: 'Sessions',
    component: () => import('@/views/sessions/index.vue'),
    meta: { title: '会话管理', requiresAuth: true }
  },
  {
    path: '/sessions/:id',
    name: 'SessionDetail',
    component: () => import('@/views/session-detail/index.vue'),
    meta: { title: '会话详情', requiresAuth: true }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/settings/index.vue'),
    meta: { title: '系统设置', requiresAuth: true }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/not-found/index.vue'),
    meta: { title: '页面未找到' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 导航守卫
router.beforeEach((to, _from, next) => {
  // 更新页面标题
  document.title = `${to.meta.title || 'Bay Dashboard'} - Bay Dashboard`
  
  // 检查是否需要认证
  if (to.meta.requiresAuth) {
    const settingsStore = useSettingsStore()
    if (!settingsStore.isAuthenticated) {
      // 未认证，跳转到登录页
      next({ name: 'Login', query: { redirect: to.fullPath } })
      return
    }
  }
  
  // 如果已经登录并尝试访问登录页，重定向到首页
  if (to.name === 'Login') {
    const settingsStore = useSettingsStore()
    if (settingsStore.isAuthenticated) {
      next({ name: 'Dashboard' })
      return
    }
  }
  
  next()
})

export default router
