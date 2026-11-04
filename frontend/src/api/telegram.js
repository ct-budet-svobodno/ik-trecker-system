import apiClient from './client'

export async function loginWithTelegram(initData) {
  const response = await apiClient.post('/auth/telegram', { init_data: initData })
  return response.data
}

export async function linkTelegram(initData) {
  const response = await apiClient.post('/auth/telegram/link', { init_data: initData })
  return response.data
}

export async function unlinkTelegram() {
  const response = await apiClient.delete('/auth/telegram/link')
  return response.data
}

export async function fetchTelegramConfig() {
  const response = await apiClient.get('/auth/telegram/config')
  return response.data
}

// ── Анкета из мини-аппа (вход без логина и пароля) ──

export async function fetchRegistrationOptions() {
  const response = await apiClient.get('/auth/telegram/registration-options')
  return response.data
}

// formData: поля анкеты + init_data + photo1/photo2 (файлы).
export async function registerWithTelegram(formData) {
  const response = await apiClient.post('/auth/telegram/register', formData)
  return response.data
}

// Веб-версия: ссылка в мини-апп, которая привяжет Telegram к этому аккаунту.
export async function createTelegramLinkCode() {
  const response = await apiClient.post('/auth/telegram/link-code')
  return response.data
}

export async function claimTelegramLinkCode(initData, code) {
  const response = await apiClient.post('/auth/telegram/claim', { init_data: initData, code })
  return response.data
}
