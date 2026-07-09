import apiClient from './client'

export async function fetchUsers() {
  const response = await apiClient.get('/users')
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
