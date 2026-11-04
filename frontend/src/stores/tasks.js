import { defineStore } from 'pinia'

import { fetchDirections } from '../api/directions'
import { deleteTask, fetchTasks, remindTask, updateTask } from '../api/tasks'

export const useTasksStore = defineStore('tasks', {
  state: () => ({
    tasks: [],
    directions: [],
    isLoading: false,
    loadError: '',
  }),

  actions: {
    async loadAll({ force = false } = {}) {
      if (this.isLoading) return
      if (!force && this.tasks.length > 0) return
      this.isLoading = true
      this.loadError = ''
      try {
        const [directionsData, tasksData] = await Promise.all([fetchDirections(), fetchTasks()])
        this.directions = directionsData
        this.tasks = tasksData
      } catch {
        this.loadError = 'Не удалось загрузить задачи'
      } finally {
        this.isLoading = false
      }
    },

    addTask(task) {
      this.tasks.unshift(task)
    },

    // Правка ТЗ/поручения целиком (форма «Изменить»).
    async updateFields(taskId, payload) {
      const updated = await updateTask(taskId, payload)
      const task = this.tasks.find((t) => t.id === taskId)
      if (task) Object.assign(task, updated)
      return updated
    },

    async removeTask(taskId) {
      await deleteTask(taskId)
      this.tasks = this.tasks.filter((t) => t.id !== taskId)
    },

    // Счётчик комментариев на карточке — без перезагрузки всего списка.
    setCommentsCount(taskId, count) {
      const task = this.tasks.find((t) => t.id === taskId)
      if (task) task.comments_count = count
    },

    async remind(taskId) {
      const updated = await remindTask(taskId)
      const task = this.tasks.find((t) => t.id === taskId)
      if (task) Object.assign(task, updated)
    },

    async setTaskStatus(taskId, status) {
      const task = this.tasks.find((t) => t.id === taskId)
      if (!task) return
      const previousStatus = task.status
      task.status = status
      try {
        const updated = await updateTask(taskId, { status })
        Object.assign(task, updated)
      } catch (err) {
        task.status = previousStatus
        throw err
      }
    },
  },
})
