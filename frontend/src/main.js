import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import './style.css'
import swipeClose from './directives/swipeClose'
import { useAuthStore } from './stores/auth'
import { registerServiceWorker } from './utils/pushClient'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// Мобильный жест: шторки/модалки смахиваются вниз.
app.directive('swipe-close', swipeClose)

// SW нужен для PWA (установка на главный экран) и приёма пушей.
registerServiceWorker()

const authStore = useAuthStore()
authStore.restoreSession().finally(() => {
  app.mount('#app')
})
