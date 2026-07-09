import apiClient from './client'

export async function fetchPosts({ dateFrom, dateTo }) {
  const response = await apiClient.get('/editorial-posts', {
    params: { date_from: dateFrom, date_to: dateTo },
  })
  return response.data
}

export async function fetchMyPosts() {
  const response = await apiClient.get('/editorial-posts/mine')
  return response.data
}

export async function fetchPost(postId) {
  const response = await apiClient.get(`/editorial-posts/${postId}`)
  return response.data
}

export async function createPost(payload) {
  const response = await apiClient.post('/editorial-posts', payload)
  return response.data
}

export async function updatePost(postId, payload) {
  const response = await apiClient.patch(`/editorial-posts/${postId}`, payload)
  return response.data
}

export async function deletePost(postId) {
  await apiClient.delete(`/editorial-posts/${postId}`)
}

export async function assignRole(postId, role, userId = null) {
  const response = await apiClient.post(`/editorial-posts/${postId}/assign`, {
    role,
    user_id: userId,
  })
  return response.data
}

export async function unassignRole(postId, role) {
  const response = await apiClient.delete(`/editorial-posts/${postId}/assign/${role}`)
  return response.data
}

export async function addComment(postId, payload) {
  const response = await apiClient.post(`/editorial-posts/${postId}/comments`, payload)
  return response.data
}

export async function resolveComment(postId, commentId, resolved) {
  const response = await apiClient.patch(
    `/editorial-posts/${postId}/comments/${commentId}`,
    { resolved },
  )
  return response.data
}

export async function deleteComment(postId, commentId) {
  const response = await apiClient.delete(`/editorial-posts/${postId}/comments/${commentId}`)
  return response.data
}
