import { defineStore } from 'pinia'

import { createEvent, deleteEvent, fetchEvents, updateEvent } from '../api/events'

export const useEventsStore = defineStore('events', {
  state: () => ({
    events: [],
    isLoading: false,
    loadError: '',
  }),

  actions: {
    async loadAll({ force = false } = {}) {
      if (this.isLoading) return
      if (!force && this.events.length > 0) return
      this.isLoading = true
      this.loadError = ''
      try {
        this.events = await fetchEvents()
      } catch {
        this.loadError = 'Не удалось загрузить мероприятия'
      } finally {
        this.isLoading = false
      }
    },

    async addEvent(payload) {
      const event = await createEvent(payload)
      this.events.push(event)
      return event
    },

    async editEvent(eventId, payload) {
      const updated = await updateEvent(eventId, payload)
      const index = this.events.findIndex((e) => e.id === eventId)
      if (index !== -1) this.events[index] = updated
      return updated
    },

    async removeEvent(eventId) {
      await deleteEvent(eventId)
      this.events = this.events.filter((e) => e.id !== eventId)
    },
  },
})
