import apiClient from './client'

export async function fetchDirections() {
  const response = await apiClient.get('/directions')
  return response.data
}

export async function setDirectionHeads(directionId, userIds) {
  const response = await apiClient.put(`/directions/${directionId}/heads`, { user_ids: userIds })
  return response.data
}
