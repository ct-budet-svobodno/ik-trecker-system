import apiClient from './client'

export async function fetchUsers() {
  const response = await apiClient.get('/users')
  return response.data
}

export async function fetchChecklistAssignees() {
  const response = await apiClient.get('/users/checklist-assignees')
  return response.data
}

export async function createUser(payload) {
  const response = await apiClient.post('/users', payload)
  return response.data
}

export async function updateUser(userId, payload) {
  const response = await apiClient.patch(`/users/${userId}`, payload)
  return response.data
}

// Подтянуть анкеты из бота: кого нет в трекере — завести (только админ).
export async function importFromBot() {
  const response = await apiClient.post('/users/import-from-bot')
  return response.data
}

// ── Заявки из мини-аппа (только админ) ──

export async function fetchRegistrations() {
  const response = await apiClient.get('/users/registrations')
  return response.data
}

export async function approveRegistration(userId) {
  const response = await apiClient.post(`/users/${userId}/approve`)
  return response.data
}

export async function rejectRegistration(userId) {
  const response = await apiClient.post(`/users/${userId}/reject`)
  return response.data
}

// Фото из анкеты отдаётся с авторизацией — берём как blob и показываем через objectURL.
export async function fetchProfilePhoto(userId, slot) {
  const response = await apiClient.get(`/users/${userId}/photo/${slot}`, { responseType: 'blob' })
  return response.data
}
