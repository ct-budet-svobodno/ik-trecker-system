import apiClient from './client'

export async function fetchTasks() {
  const response = await apiClient.get('/tasks')
  return response.data
}

export async function createTask(payload) {
  const response = await apiClient.post('/tasks', payload)
  return response.data
}

export async function updateTask(taskId, payload) {
  const response = await apiClient.patch(`/tasks/${taskId}`, payload)
  return response.data
}
