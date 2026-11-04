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

// Напомнить исполнителям поручения (только автор, не чаще раза в 30 минут).
export async function remindTask(taskId) {
  const response = await apiClient.post(`/tasks/${taskId}/remind`)
  return response.data
}

export async function deleteTask(taskId) {
  await apiClient.delete(`/tasks/${taskId}`)
}

// ── Обсуждение ТЗ ──

export async function fetchTaskComments(taskId) {
  const response = await apiClient.get(`/tasks/${taskId}/comments`)
  return response.data
}

export async function addTaskComment(taskId, body, parentId = null) {
  const response = await apiClient.post(`/tasks/${taskId}/comments`, { body, parent_id: parentId })
  return response.data
}

export async function deleteTaskComment(taskId, commentId) {
  await apiClient.delete(`/tasks/${taskId}/comments/${commentId}`)
}
