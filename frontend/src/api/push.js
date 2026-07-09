import apiClient from './client'

export async function fetchVapidPublicKey() {
  const response = await apiClient.get('/push/public-key')
  return response.data.public_key
}

export async function savePushSubscription(subscriptionJson) {
  await apiClient.post('/push/subscriptions', subscriptionJson)
}

export async function deletePushSubscription(endpoint) {
  await apiClient.delete('/push/subscriptions', { data: { endpoint } })
}
