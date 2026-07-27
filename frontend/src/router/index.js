import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
  },
  {
    path: '/',
    name: 'tasks',
    component: () => import('../views/TasksView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/calendar',
    name: 'calendar',
    component: () => import('../views/CalendarView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('../views/UsersAdminView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/leadership-timeline',
    name: 'leadership-timeline',
    component: () => import('../views/LeadershipTimelineView.vue'),
    meta: { requiresAuth: true, requiresManager: true },
  },
  {
    path: '/editorial',
    name: 'editorial',
    component: () => import('../views/EditorialView.vue'),
    meta: { requiresAuth: true, requiresEditorial: true },
  },
  {
    path: '/zavod',
    name: 'zavod',
    component: () => import('../views/ZavodView.vue'),
    meta: { requiresAuth: true, requiresZavod: true },
  },
  {
    // Карточка поста доступна и назначенному исполнителю без вкладки Редакции —
    // права проверяет бэкенд (403 → редирект в календарь).
    path: '/editorial/:id',
    name: 'editorial-post',
    component: () => import('../views/EditorialPostView.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return { name: 'tasks' }
  }
  if (to.meta.requiresManager && !authStore.isManagerOrAdmin) {
    return { name: 'tasks' }
  }
  if (to.meta.requiresEditorial && !authStore.isEditorial) {
    return { name: 'tasks' }
  }
  if (to.meta.requiresZavod && !authStore.isZavod) {
    return { name: 'tasks' }
  }
  if (to.name === 'login' && authStore.isAuthenticated) {
    return { name: 'tasks' }
  }
  return true
})

export default router
