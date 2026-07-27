import { defineStore } from 'pinia'

import { fetchMe, login as loginRequest } from '../api/auth'
import { clearToken, getToken, setToken } from '../api/tokenStorage'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: getToken(),
    user: null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
    isAdmin: (state) => state.user?.role === 'admin',
    isManagerOrAdmin: (state) => ['admin', 'manager'].includes(state.user?.role),
    // Тройка: админ или пользователь с должностью руководства.
    isLeadership: (state) => state.user?.role === 'admin' || !!state.user?.leadership_position,
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
    },

    async fetchCurrentUser() {
      this.user = await fetchMe()
    },

    async restoreSession() {
      if (!this.token) return
      try {
        await this.fetchCurrentUser()
      } catch {
        this.logout()
      }
    },

    logout() {
      this.token = null
      this.user = null
      clearToken()
    },
  },
})
