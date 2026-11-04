<script setup>
import { computed, defineAsyncComponent, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppTabBar from './components/AppTabBar.vue'
import { useAuthStore } from './stores/auth'
import { telegramApp } from './utils/telegram'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

// В Telegram у вложенных экранов (карточка поста, партия) — системная кнопка «Назад».
const NESTED_ROUTES = ['editorial-post', 'durak', 'sea']
const tg = telegramApp()
if (tg) {
  tg.BackButton.onClick(() => {
    if (window.history.state?.back) router.back()
    else router.push({ name: 'tasks' })
  })
  watch(
    () => route.name,
    (name) => (NESTED_ROUTES.includes(name) ? tg.BackButton.show() : tg.BackButton.hide()),
    { immediate: true },
  )
}

// Переключатель тестовых ролей — только в dev: в прод-сборке ветка вырезается
// вместе с импортом компонента.
const DevRoleSwitcher = import.meta.env.DEV
  ? defineAsyncComponent(() => import('./components/DevRoleSwitcher.vue'))
  : null

// Нижний таб-бар (мобильные): везде, кроме логина.
const showTabBar = computed(
  () => authStore.isAuthenticated && !['login', 'join'].includes(route.name),
)
</script>

<template>
  <RouterView />
  <AppTabBar v-if="showTabBar" />
  <DevRoleSwitcher v-if="DevRoleSwitcher" />
</template>
