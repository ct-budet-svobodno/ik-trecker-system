import { defineStore } from 'pinia'

import {
  carryOverTodos,
  createPersonalTodo,
  deletePersonalTodo,
  fetchOverdueTodos,
  fetchPersonalTodos,
  updatePersonalTodo,
} from '../api/personalTodos'
import { addDays, dayKey } from '../utils/dateKey'

function today() {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

// Личный список на день: пункты видит только их владелец.
export const useMyDayStore = defineStore('myDay', {
  state: () => ({
    day: today(),
    items: [],
    // Невыполненное из прошлых дней — показываем только на «сегодня».
    overdue: [],
    isLoading: false,
    loadError: '',
  }),

  getters: {
    dayKey: (state) => dayKey(state.day),
    isToday: (state) => dayKey(state.day) === dayKey(today()),
    doneCount: (state) => state.items.filter((item) => item.done).length,
  },

  actions: {
    async load() {
      this.isLoading = true
      this.loadError = ''
      try {
        const key = this.dayKey
        const [items, overdue] = await Promise.all([
          fetchPersonalTodos(key),
          this.isToday ? fetchOverdueTodos(key) : Promise.resolve([]),
        ])
        // Пока шёл запрос, день могли переключить — устаревший ответ не показываем.
        if (key !== this.dayKey) return
        this.items = items
        this.overdue = overdue
      } catch {
        this.loadError = 'Не удалось загрузить список'
      } finally {
        this.isLoading = false
      }
    },

    async shiftDay(delta) {
      this.day = addDays(this.day, delta)
      await this.load()
    },

    async goToToday() {
      this.day = today()
      await this.load()
    },

    async add(title) {
      const item = await createPersonalTodo({ title, date: this.dayKey })
      this.items.push(item)
    },

    async edit(todoId, payload) {
      const updated = await updatePersonalTodo(todoId, payload)
      const index = this.items.findIndex((item) => item.id === todoId)
      if (index !== -1) this.items[index] = updated
      return updated
    },

    async toggle(item) {
      // Отмечаем сразу, не дожидаясь сервера; при ошибке возвращаем как было.
      const previous = item.done
      item.done = !previous
      try {
        await updatePersonalTodo(item.id, { done: item.done })
      } catch (err) {
        item.done = previous
        throw err
      }
    },

    async moveToNextDay(item) {
      await updatePersonalTodo(item.id, { date: dayKey(addDays(this.day, 1)) })
      this.items = this.items.filter((it) => it.id !== item.id)
    },

    async carryOver() {
      this.items = await carryOverTodos(this.dayKey)
      this.overdue = []
    },

    async remove(todoId) {
      await deletePersonalTodo(todoId)
      this.items = this.items.filter((item) => item.id !== todoId)
    },
  },
})
