import { defineStore } from 'pinia'

import { fetchDirections } from '../api/directions'
import { fetchTasks, updateTask } from '../api/tasks'

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
