import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import { isTelegram } from '../utils/telegram'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
  },
  {
    // Мини-апп без привязанного Telegram: анкета вместо логина, потом —
    // ожидание одобрения. ?link=<код> — привязка существующего аккаунта.
    path: '/join',
    name: 'join',
    component: () => import('../views/JoinView.vue'),
  },
  {
    // Главная: ближайшие мероприятия, мои задачи, «Мой день» — коротко.
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
    meta: { requiresAuth: true },
    // Доска раньше жила на «/»: старые ссылки из уведомлений (/?task=…,
    // /?private=1) ведём на неё.
    beforeEnter: (to) =>
      ['task', 'private', 'all', 'direction'].some((key) => key in to.query)
        ? { name: 'tasks', query: to.query }
        : true,
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: () => import('../views/TasksView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/my-day',
    name: 'my-day',
    component: () => import('../views/MyDayView.vue'),
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
    path: '/checklists',
    name: 'checklists',
    component: () => import('../views/ChecklistsView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/surveys',
    name: 'surveys',
    component: () => import('../views/SurveysView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/surveys/new',
    name: 'survey-new',
    component: () => import('../views/SurveyManageView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    // Ссылка из уведомления бота — здесь человек отвечает.
    path: '/surveys/:id(\\d+)',
    name: 'survey-fill',
    component: () => import('../views/SurveyFillView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/surveys/:id(\\d+)/manage',
    name: 'survey-manage',
    component: () => import('../views/SurveyManageView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/broadcast',
    name: 'broadcast',
    component: () => import('../views/BroadcastView.vue'),
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
    path: '/games',
    name: 'games',
    component: () => import('../views/GamesView.vue'),
    meta: { requiresAuth: true },
  },
  {
    // Партия по коду — сюда же ведёт ссылка-приглашение из бота.
    path: '/games/durak/:code',
    name: 'durak',
    component: () => import('../views/DurakView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/games/sea/:code',
    name: 'sea',
    component: () => import('../views/SeaBattleView.vue'),
    meta: { requiresAuth: true },
  },
  {
    // Столы для очной игры в Бункер — заводит админ.
    path: '/games/tables',
    name: 'bunker-tables',
    component: () => import('../views/BunkerTablesView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/games/bunker/:code',
    name: 'bunker',
    component: () => import('../views/BunkerView.vue'),
    meta: { requiresAuth: true },
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
    // Без hash: в мини-аппе там лежат данные запуска Telegram, им не место в адресе.
    // В Telegram логина и пароля нет — вместо них анкета.
    return { name: isTelegram() ? 'join' : 'login', query: { redirect: to.fullPath.split('#')[0] } }
  }
  if (to.name === 'login' && isTelegram()) {
    return { name: 'join', query: to.query }
  }
  if (to.name === 'join' && authStore.isAuthenticated) {
    return to.query.redirect || { name: 'home' }
  }
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return { name: 'home' }
  }
  if (to.meta.requiresManager && !authStore.isManagerOrAdmin) {
    return { name: 'home' }
  }
  if (to.meta.requiresEditorial && !authStore.isEditorial) {
    return { name: 'home' }
  }
  if (to.meta.requiresZavod && !authStore.isZavod) {
    return { name: 'home' }
  }
  if (to.name === 'login' && authStore.isAuthenticated) {
    return { name: 'home' }
  }
  return true
})

export default router
