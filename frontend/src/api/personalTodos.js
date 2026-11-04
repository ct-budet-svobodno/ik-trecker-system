import apiClient from './client'

export async function fetchPersonalTodos(date) {
  const response = await apiClient.get('/personal-todos', { params: { date } })
  return response.data
}

export async function fetchOverdueTodos(before) {
  const response = await apiClient.get('/personal-todos/overdue', { params: { before } })
  return response.data
}

export async function createPersonalTodo(payload) {
  const response = await apiClient.post('/personal-todos', payload)
  return response.data
}

export async function updatePersonalTodo(todoId, payload) {
  const response = await apiClient.patch(`/personal-todos/${todoId}`, payload)
  return response.data
}

export async function carryOverTodos(date) {
  const response = await apiClient.post('/personal-todos/carry-over', { date })
  return response.data
}

export async function deletePersonalTodo(todoId) {
  await apiClient.delete(`/personal-todos/${todoId}`)
}
