import apiClient from './client'

// Рассылка от бота (только админ). message: { text, buttons: [{ text, url } | { text, path }] }
export async function fetchBroadcasts() {
  const response = await apiClient.get('/broadcasts')
  return response.data
}

export async function sendTestBroadcast(message) {
  await apiClient.post('/broadcasts/test', message)
}

export async function startBroadcast(message) {
  const response = await apiClient.post('/broadcasts', message)
  return response.data
}
