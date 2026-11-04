import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import './fonts'
import './style.css'
import swipeClose from './directives/swipeClose'
import { useAuthStore } from './stores/auth'
import { registerServiceWorker } from './utils/pushClient'
import { initTelegram, telegramApp } from './utils/telegram'

const app = createApp(App)

app.use(createPinia())

// Мобильный жест: шторки/модалки смахиваются вниз.
app.directive('swipe-close', swipeClose)

// SW нужен для PWA (установка на главный экран) и приёма пушей.
registerServiceWorker()

const authStore = useAuthStore()
// В Telegram сначала подключаем его скрипт: из него берётся подпись для входа.
// Роутер подключаем после восстановления сессии: гард по ролям запускается
// уже при установке роутера, и без пользователя он уводил бы с /users и
// таймлайна на главную при обновлении страницы.
// Мини-апп открыт ссылкой t.me/<бот>?startapp=<параметр> (приглашение из чата,
// кнопка из бота): до установки роутера подменяем адрес, чтобы он сразу открыл
// нужный экран (а гард при необходимости увёл на вход и вернул сюда после).
// durak_<код> / sea_<код> / bunker_<код> — партия, play_<игра>_bot|human — новая партия,
// games — раздел «Игры», link_<код> — привязать Telegram к аккаунту.
const START_ROUTES = [
  [/^play_(durak|sea)_(bot|human)$/, (kind, vs) => `/games/${kind}/new?vs=${vs}`],
  [/^durak_([A-Za-z0-9]{4,16})$/, (code) => `/games/durak/${code.toUpperCase()}`],
  [/^sea_([A-Za-z0-9]{4,16})$/, (code) => `/games/sea/${code.toUpperCase()}`],
  [/^bunker_([A-Za-z0-9]{4,16})$/, (code) => `/games/bunker/${code.toUpperCase()}`],
  [/^games$/, () => '/games'],
  // Привязка существующего аккаунта: ссылка «Подключить Telegram» из веб-версии.
  [/^link_([A-Za-z0-9]{4,32})$/, (code) => `/join?link=${code}`],
]

// Куда вести по параметру запуска (null — никуда, обычный запуск).
function startParamPath() {
  const param = telegramApp()?.initDataUnsafe?.start_param ?? ''
  if (window.location.pathname !== '/') return null
  for (const [pattern, path] of START_ROUTES) {
    const match = pattern.exec(param)
    if (match) return path(...match.slice(1))
  }
  return null
}

let startPath = null

initTelegram()
  .then(() => {
    startPath = startParamPath()
    // Адрес меняем до восстановления сессии: гард и редирект после входа
    // должны видеть уже нужную страницу.
    if (startPath) window.history.replaceState(window.history.state, '', startPath)
    return authStore.restoreSession()
  })
  .finally(() => {
    app.use(router)
    // Роутер запомнил адрес ещё при создании (до replaceState выше) и сам
    // открыл бы главную — переходим на нужную страницу явно.
    if (startPath) router.replace(startPath)
    app.mount('#app')
  })
