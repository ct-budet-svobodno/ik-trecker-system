import { defineStore } from 'pinia'

// Лёгкое UI-состояние оболочки. Свёрнутость сайдбара запоминаем в localStorage,
// чтобы выбор сохранялся между переходами и перезагрузкой.
export const useUiStore = defineStore('ui', {
  state: () => ({
    sidebarCollapsed: localStorage.getItem('sidebarCollapsed') === '1',
  }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
      localStorage.setItem('sidebarCollapsed', this.sidebarCollapsed ? '1' : '0')
    },
  },
})
