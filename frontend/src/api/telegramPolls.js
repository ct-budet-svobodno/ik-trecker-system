import api from './client'

export const fetchPolls = async () => (await api.get('/telegram-polls')).data
export const createPoll = async (payload) => (await api.post('/telegram-polls', payload)).data
export const fetchPoll = async (id) => (await api.get(`/telegram-polls/${id}`)).data
export const closePoll = async (id) => (await api.put(`/telegram-polls/${id}/closed`)).data

export const addPollChat = async (chat_id) => (await api.post('/telegram-polls/chats', { chat_id })).data
