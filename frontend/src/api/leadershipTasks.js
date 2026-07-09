import apiClient from './client'

export async function fetchLeadershipTasks({ dateFrom, dateTo }) {
  const response = await apiClient.get('/leadership-tasks', {
    params: { date_from: dateFrom, date_to: dateTo },
  })
  return response.data
}

export async function createLeadershipTask(payload) {
  const response = await apiClient.post('/leadership-tasks', payload)
  return response.data
}

export async function updateLeadershipTask(taskId, payload) {
  const response = await apiClient.patch(`/leadership-tasks/${taskId}`, payload)
  return response.data
}

export async function deleteLeadershipTask(taskId) {
  await apiClient.delete(`/leadership-tasks/${taskId}`)
}
