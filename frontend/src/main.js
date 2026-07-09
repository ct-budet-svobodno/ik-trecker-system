import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import './style.css'
import { useAuthStore } from './stores/auth'
import { registerServiceWorker } from './utils/pushClient'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// SW нужен для PWA (установка на главный экран) и приёма пушей.
registerServiceWorker()

const authStore = useAuthStore()
authStore.restoreSession().finally(() => {
  app.mount('#app')
})
