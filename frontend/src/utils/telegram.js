// Запуск внутри Telegram Mini App. В обычном браузере всё это не используется.

const SCRIPT_URL = 'https://telegram.org/js/telegram-web-app.js'
const SESSION_FLAG = 'ik-telegram'

// Telegram передаёт данные запуска в hash адреса. После перезагрузки страницы
// hash пропадает, поэтому запоминаем сам факт запуска из Telegram в sessionStorage.
function launchedFromTelegram() {
  if (/tgWebAppData|tgWebAppPlatform/.test(window.location.hash)) {
    try {
      sessionStorage.setItem(SESSION_FLAG, '1')
    } catch {
      /* без sessionStorage просто не запомним */
    }
    return true
  }
  try {
    return sessionStorage.getItem(SESSION_FLAG) === '1'
  } catch {
    return false
  }
}

function loadScript() {
  return new Promise((resolve) => {
    const script = document.createElement('script')
    script.src = SCRIPT_URL
    script.onload = resolve
    script.onerror = resolve
    document.head.appendChild(script)
    // Не держим запуск дольше 5 секунд, если telegram.org недоступен.
    setTimeout(resolve, 5000)
  })
}

// WebApp-объект Telegram, если трекер открыт как мини-апп, иначе null.
export function telegramApp() {
  const app = window.Telegram?.WebApp
  return app?.initData ? app : null
}

export function isTelegram() {
  return telegramApp() !== null
}

export async function initTelegram() {
  if (!launchedFromTelegram()) return null
  await loadScript()
  const app = telegramApp()
  if (!app) return null

  app.ready()
  app.expand()
  // Свайп вниз закрывает мини-апп — он мешает листать списки и смахивать шторки.
  app.disableVerticalSwipes?.()
  try {
    app.setHeaderColor('#0a0a0c')
    app.setBackgroundColor('#0a0a0c')
  } catch {
    /* старые клиенты Telegram не умеют менять цвета */
  }
  document.documentElement.classList.add('in-telegram')
  return app
}
