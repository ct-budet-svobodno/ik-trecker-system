import { defineStore } from 'pinia'

import { fetchMe, login as loginRequest } from '../api/auth'
import { claimTelegramLinkCode, linkTelegram, loginWithTelegram } from '../api/telegram'
import { clearToken, getToken, setToken } from '../api/tokenStorage'
import { telegramApp } from '../utils/telegram'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: getToken(),
    user: null,
    // Вход из мини-аппа не удался: 'unregistered' — Telegram ни к кому не
    // привязан (показываем анкету), 'pending' / 'rejected' — анкета у админа.
    telegramStatus: null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
    isAdmin: (state) => state.user?.role === 'admin',
    isManagerOrAdmin: (state) => ['admin', 'manager'].includes(state.user?.role),
    // Тройка: админ или пользователь с должностью руководства.
    isLeadership: (state) => state.user?.role === 'admin' || !!state.user?.leadership_position,
    // Видят все личные поручения руководства, а не только свои: админы и секретарь.
    // Зеркало task_service.sees_all_private на бэке.
    seesAllPrivate: (state) =>
      state.user?.role === 'admin' || state.user?.leadership_position === 'secretary',
    // Кто видит вкладку «Редакция»: руководители, «четвёрка» и активисты СМИ/Дизайна.
    isEditorial: (state) =>
      ['admin', 'manager'].includes(state.user?.role) ||
      !!state.user?.leadership_position ||
      !!state.user?.is_editorial ||
      !!state.user?.is_editorial_reviewer,
    // Редактор Редакции: ревьюер СМИ/Дизайна или админ (создаёт посты, назначает роли).
    isEditorialEditor: (state) =>
      state.user?.role === 'admin' || !!state.user?.is_editorial_reviewer,
    // Кто видит ZAVOD: отмеченные флагом, админы и руководство.
    isZavod: (state) =>
      state.user?.role === 'admin' ||
      !!state.user?.leadership_position ||
      !!state.user?.is_zavod,
  },

  actions: {
    async login(username, password) {
      const { access_token } = await loginRequest(username, password)
      this.token = access_token
      setToken(access_token)
      await this.fetchCurrentUser()
      await this.linkTelegramIfNeeded()
    },

    // Вошли по логину внутри мини-аппа — привязываем этот Telegram к аккаунту,
    // чтобы в следующий раз пускать без пароля и слать сюда уведомления.
    async linkTelegramIfNeeded() {
      const app = telegramApp()
      if (!app || this.user?.telegram_linked) return
      try {
        this.user = await linkTelegram(app.initData)
      } catch {
        /* не привязалось — трекер работает и так */
      }
    },

    async loginWithTelegram() {
      const app = telegramApp()
      if (!app) return false
      try {
        const { access_token } = await loginWithTelegram(app.initData)
        await this.useToken(access_token)
        this.telegramStatus = null
        return true
      } catch (err) {
        const code = err.response?.data?.detail?.code
        if (err.response?.status === 404) this.telegramStatus = 'unregistered'
        else if (code === 'registration_pending') this.telegramStatus = 'pending'
        else if (code === 'registration_rejected') this.telegramStatus = 'rejected'
        return false
      }
    },

    // Привязать Telegram мини-аппа к существующему аккаунту по коду из веб-версии.
    async claimTelegram(code) {
      const app = telegramApp()
      if (!app) return false
      const { access_token } = await claimTelegramLinkCode(app.initData, code)
      await this.useToken(access_token)
      this.telegramStatus = null
      return true
    },

    async useToken(accessToken) {
      this.token = accessToken
      setToken(accessToken)
      await this.fetchCurrentUser()
    },

    async fetchCurrentUser() {
      this.user = await fetchMe()
    },

    async restoreSession() {
      if (this.token) {
        try {
          await this.fetchCurrentUser()
          await this.linkTelegramIfNeeded()
          return
        } catch {
          this.logout()
        }
      }
      // В мини-аппе пробуем войти по подписи Telegram — без логина и пароля.
      await this.loginWithTelegram()
    },

    logout() {
      this.token = null
      this.user = null
      clearToken()
    },
  },
})
