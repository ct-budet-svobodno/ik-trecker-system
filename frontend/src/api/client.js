import axios from 'axios'

import { clearToken, getToken } from './tokenStorage'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
})

apiClient.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Вход через Telegram сам разбирается с 401/404 — без принудительного перехода на /login.
    const isTelegramAuth = error.config?.url?.startsWith('/auth/telegram')
    if (error.response?.status === 401 && !isTelegramAuth) {
      clearToken()
      if (window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)

export default apiClient
