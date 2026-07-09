import apiClient from './client'

export async function fetchLeadershipNotes() {
  const response = await apiClient.get('/leadership-notes')
  return response.data
}

export async function createLeadershipNote(payload) {
  const response = await apiClient.post('/leadership-notes', payload)
  return response.data
}

export async function deleteLeadershipNote(noteId) {
  await apiClient.delete(`/leadership-notes/${noteId}`)
}
