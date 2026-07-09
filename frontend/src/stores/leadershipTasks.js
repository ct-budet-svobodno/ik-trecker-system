import { defineStore } from 'pinia'

import {
  createLeadershipTask,
  deleteLeadershipTask,
  fetchLeadershipTasks,
  updateLeadershipTask,
} from '../api/leadershipTasks'
import { addDays, dayKey, startOfWeek } from '../utils/dateKey'

export const useLeadershipTasksStore = defineStore('leadershipTasks', {
  state: () => ({
    items: [],
    weekStart: startOfWeek(new Date()), // понедельник текущей недели
    isLoading: false,
    loadError: '',
  }),

  getters: {
    weekDays(state) {
      return Array.from({ length: 7 }, (_, i) => addDays(state.weekStart, i))
    },
  },

  actions: {
    async load() {
      this.isLoading = true
      this.loadError = ''
      try {
        const days = this.weekDays
        this.items = await fetchLeadershipTasks({
          dateFrom: dayKey(days[0]),
          dateTo: dayKey(days[days.length - 1]),
        })
      } catch {
        this.loadError = 'Не удалось загрузить таймлайн руководства'
      } finally {
        this.isLoading = false
      }
    },

    async shiftWeek(deltaWeeks) {
      this.weekStart = addDays(this.weekStart, deltaWeeks * 7)
      await this.load()
    },

    async goToCurrentWeek() {
      this.weekStart = startOfWeek(new Date())
      await this.load()
    },

    async add(payload) {
      const item = await createLeadershipTask(payload)
      this.items.push(item)
      return item
    },

    async edit(taskId, payload) {
      const updated = await updateLeadershipTask(taskId, payload)
      const index = this.items.findIndex((t) => t.id === taskId)
      if (index !== -1) this.items[index] = updated
      return updated
    },

    async toggleDone(task) {
      const next = task.status === 'done' ? 'todo' : 'done'
      return this.edit(task.id, { status: next })
    },

    async remove(taskId) {
      await deleteLeadershipTask(taskId)
      this.items = this.items.filter((t) => t.id !== taskId)
    },
  },
})
