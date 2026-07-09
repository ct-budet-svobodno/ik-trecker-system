// Подписка браузера на Web Push: service worker + PushManager + наш бэкенд.
import { deletePushSubscription, fetchVapidPublicKey, savePushSubscription } from '../api/push'

export function isPushSupported() {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

// Регистрируем SW при старте приложения (без запроса разрешений).
export async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return null
  try {
    return await navigator.serviceWorker.register('/sw.js')
  } catch {
    return null
  }
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  return Uint8Array.from([...raw].map((ch) => ch.charCodeAt(0)))
}

// Текущее состояние: 'unsupported' | 'denied' | 'subscribed' | 'off'.
export async function getPushState() {
  if (!isPushSupported()) return 'unsupported'
  if (Notification.permission === 'denied') return 'denied'
  const registration = await navigator.serviceWorker.getRegistration()
  const subscription = await registration?.pushManager.getSubscription()
  return subscription ? 'subscribed' : 'off'
}

// Вызывать из клика (iOS требует жест пользователя для запроса разрешения).
export async function enablePush() {
  if (!isPushSupported()) {
    throw new Error('Браузер не поддерживает push-уведомления')
  }
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') {
    throw new Error('Уведомления запрещены в настройках браузера')
  }

  const registration =
    (await navigator.serviceWorker.getRegistration()) ?? (await registerServiceWorker())
  await navigator.serviceWorker.ready

  let subscription = await registration.pushManager.getSubscription()
  if (!subscription) {
    const publicKey = await fetchVapidPublicKey()
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    })
  }
  await savePushSubscription(subscription.toJSON())
}

export async function disablePush() {
  const registration = await navigator.serviceWorker.getRegistration()
  const subscription = await registration?.pushManager.getSubscription()
  if (!subscription) return
  await deletePushSubscription(subscription.endpoint)
  await subscription.unsubscribe()
}
