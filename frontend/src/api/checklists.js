import apiClient from './client'

// Чек-листы «Найди того, кто…» (только админ).
export async function fetchChecklists() {
  const response = await apiClient.get('/checklists')
  return response.data
}

export async function prepareChecklists(facts) {
  const response = await apiClient.post('/checklists/prepare', { facts })
  return response.data
}

export async function uploadChecklistImage(cardId, blob) {
  const form = new FormData()
  form.append('image', blob, `checklist-${cardId}.jpg`)
  await apiClient.put(`/checklists/cards/${cardId}/image`, form)
}

// Картинка листа или присланное фото (slot 1–3) — Blob для показа.
export async function fetchChecklistFile(cardId, slot = null) {
  const path = slot ? `photo/${slot}` : 'image'
  const response = await apiClient.get(`/checklists/cards/${cardId}/${path}`, { responseType: 'blob' })
  return response.data
}

export async function sendChecklists() {
  const response = await apiClient.post('/checklists/send')
  return response.data
}

// Отправить только свой лист — проверить всю цепочку на себе.
export async function sendTestChecklist() {
  const response = await apiClient.post('/checklists/send-test')
  return response.data
}

// Лист по тегу: { card, needs_image } — новый лист админка рисует сама.
export async function checklistByTag(username) {
  const response = await apiClient.post('/checklists/by-tag', { username })
  return response.data
}

export async function sendOneChecklist(cardId) {
  const response = await apiClient.post(`/checklists/cards/${cardId}/send`)
  return response.data
}

export async function resetChecklists() {
  const response = await apiClient.post('/checklists/reset')
  return response.data
}
