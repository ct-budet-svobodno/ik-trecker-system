import apiClient from './client'

// ── Получатель ──

export async function fetchMySurveys() {
  const response = await apiClient.get('/surveys/my')
  return response.data
}

export async function fetchSurveyToFill(surveyId) {
  const response = await apiClient.get(`/surveys/${surveyId}/fill`)
  return response.data
}

// answers: { [id вопроса]: строка | число | массив строк }
export async function submitSurveyResponse(surveyId, answers) {
  const response = await apiClient.put(`/surveys/${surveyId}/response`, { answers })
  return response.data
}

// ── Админ ──

export async function fetchSurveys() {
  const response = await apiClient.get('/surveys')
  return response.data
}

export async function fetchSurvey(surveyId) {
  const response = await apiClient.get(`/surveys/${surveyId}`)
  return response.data
}

// payload: { title, description, questions: [{ id, type, title, hint, required, options, max }] }
export async function createSurvey(payload) {
  const response = await apiClient.post('/surveys', payload)
  return response.data
}

export async function updateSurvey(surveyId, payload) {
  const response = await apiClient.put(`/surveys/${surveyId}`, payload)
  return response.data
}

export async function deleteSurvey(surveyId) {
  await apiClient.delete(`/surveys/${surveyId}`)
}

export async function sendSurvey(surveyId, userIds) {
  const response = await apiClient.post(`/surveys/${surveyId}/send`, { user_ids: userIds })
  return response.data
}

export async function remindSurvey(surveyId) {
  const response = await apiClient.post(`/surveys/${surveyId}/remind`)
  return response.data
}

// status: 'open' | 'closed'
export async function setSurveyStatus(surveyId, status) {
  const response = await apiClient.post(`/surveys/${surveyId}/status`, { status })
  return response.data
}
