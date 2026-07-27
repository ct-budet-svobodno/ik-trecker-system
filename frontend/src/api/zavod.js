import apiClient from './client'

// Люди для назначения ответственных. Отдельный эндпоинт, а не GET /users:
// тот закрыт для рядового сотрудника, а назначать в ZAVOD могут все допущенные.
export async function fetchAssignableUsers() {
  const response = await apiClient.get('/zavod/users')
  return response.data
}

export async function fetchBoards() {
  const response = await apiClient.get('/zavod/boards')
  return response.data
}

export async function createBoard(title) {
  const response = await apiClient.post('/zavod/boards', { title })
  return response.data
}

export async function renameBoard(boardId, title) {
  const response = await apiClient.patch(`/zavod/boards/${boardId}`, { title })
  return response.data
}

export async function deleteBoard(boardId) {
  await apiClient.delete(`/zavod/boards/${boardId}`)
}

// Доска целиком: карточки и связи одним запросом.
export async function fetchBoard(boardId) {
  const response = await apiClient.get(`/zavod/boards/${boardId}`)
  return response.data
}

export async function createNode(boardId, payload) {
  const response = await apiClient.post(`/zavod/boards/${boardId}/nodes`, payload)
  return response.data
}

export async function updateNode(nodeId, payload) {
  const response = await apiClient.patch(`/zavod/nodes/${nodeId}`, payload)
  return response.data
}

export async function deleteNode(nodeId) {
  await apiClient.delete(`/zavod/nodes/${nodeId}`)
}

// Пакетное перетаскивание выделенной группы — один запрос вместо пачки PATCH.
export async function moveNodes(boardId, moves) {
  const response = await apiClient.post(`/zavod/boards/${boardId}/nodes/move`, { moves })
  return response.data
}

export async function createEdge(boardId, sourceId, targetId) {
  const response = await apiClient.post(`/zavod/boards/${boardId}/edges`, {
    source_id: sourceId,
    target_id: targetId,
  })
  return response.data
}

export async function deleteEdge(edgeId) {
  await apiClient.delete(`/zavod/edges/${edgeId}`)
}
