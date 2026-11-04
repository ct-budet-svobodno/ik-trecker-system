import apiClient from './client'

export async function fetchEvents() {
  const response = await apiClient.get('/events')
  return response.data
}

export async function createEvent(payload) {
  const response = await apiClient.post('/events', payload)
  return response.data
}

export async function updateEvent(eventId, payload) {
  const response = await apiClient.patch(`/events/${eventId}`, payload)
  return response.data
}

// status: 'going' | 'not_going' | null (снять ответ)
export async function setEventRsvp(eventId, status) {
  const response = await apiClient.put(`/events/${eventId}/rsvp`, { status })
  return response.data
}

export async function deleteEvent(eventId) {
  await apiClient.delete(`/events/${eventId}`)
}
