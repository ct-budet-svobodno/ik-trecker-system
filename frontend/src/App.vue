<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AppTabBar from './components/AppTabBar.vue'
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()
const route = useRoute()

// Нижний таб-бар (мобильные): везде, кроме логина.
const showTabBar = computed(() => authStore.isAuthenticated && route.name !== 'login')
</script>

<template>
  <RouterView />
  <AppTabBar v-if="showTabBar" />
</template>
