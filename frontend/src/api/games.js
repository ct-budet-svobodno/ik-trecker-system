import apiClient from './client'

export async function fetchPokerGames() {
  const response = await apiClient.get('/games/poker')
  return response.data
}

export async function fetchOpenPokerGames() {
  const response = await apiClient.get('/games/poker/open')
  return response.data
}

export async function createPokerGame() {
  const response = await apiClient.post('/games/poker')
  return response.data
}

export async function fetchPokerGame(code) {
  const response = await apiClient.get(`/games/poker/${code}`)
  return response.data
}

export async function pokerLobbyAction(code, action) {
  const response = await apiClient.post(`/games/poker/${code}/${action}`)
  return response.data
}

export async function pokerNextHand(code, version) {
  const response = await apiClient.post(`/games/poker/${code}/next`, { version })
  return response.data
}

export async function sendPokerMove(code, move) {
  const response = await apiClient.post(`/games/poker/${code}/move`, move)
  return response.data
}

export async function fetchDurakGames() {
  const response = await apiClient.get('/games/durak')
  return response.data
}

export async function createDurakGame(vsBot) {
  const response = await apiClient.post('/games/durak', { vs_bot: vsBot })
  return response.data
}

export async function fetchDurakGame(code) {
  const response = await apiClient.get(`/games/durak/${code}`)
  return response.data
}

export async function joinDurakGame(code) {
  const response = await apiClient.post(`/games/durak/${code}/join`, {})
  return response.data
}

// move: { action: 'attack'|'defend'|'take'|'finish'|'resign', card?, target?, version }
export async function sendDurakMove(code, move) {
  const response = await apiClient.post(`/games/durak/${code}/move`, move)
  return response.data
}

export async function readyDurakGame(code) {
  const response = await apiClient.post(`/games/durak/${code}/ready`)
  return response.data
}

// Закрыть лобби, пока не сел соперник.
export async function cancelDurakGame(code) {
  const response = await apiClient.post(`/games/durak/${code}/cancel`)
  return response.data
}

// Выйти из лобби до старта: место снова свободно для другого.
export async function leaveDurakGame(code) {
  const response = await apiClient.post(`/games/durak/${code}/leave`)
  return response.data
}

// Опубликовать приглашение в чате актива (от имени бота).
export async function inviteDurakToChat(code) {
  const response = await apiClient.post(`/games/durak/${code}/invite-chat`)
  return response.data
}

// ── Морской бой ──

export async function fetchSeaGames() {
  const response = await apiClient.get('/games/sea')
  return response.data
}

export async function createSeaGame(vsBot) {
  const response = await apiClient.post('/games/sea', { vs_bot: vsBot })
  return response.data
}

export async function fetchSeaGame(code) {
  const response = await apiClient.get(`/games/sea/${code}`)
  return response.data
}

export async function joinSeaGame(code) {
  const response = await apiClient.post(`/games/sea/${code}/join`, {})
  return response.data
}

// move: { action: 'place'|'fire'|'resign', ships?, cell?, version }
export async function sendSeaMove(code, move) {
  const response = await apiClient.post(`/games/sea/${code}/move`, move)
  return response.data
}

export async function readySeaGame(code) {
  const response = await apiClient.post(`/games/sea/${code}/ready`)
  return response.data
}

// Закрыть лобби, пока не сел соперник.
export async function cancelSeaGame(code) {
  const response = await apiClient.post(`/games/sea/${code}/cancel`)
  return response.data
}

export async function inviteSeaToChat(code) {
  const response = await apiClient.post(`/games/sea/${code}/invite-chat`)
  return response.data
}

// ── Бункер ──

export async function fetchBunkerGames() {
  const response = await apiClient.get('/games/bunker')
  return response.data
}

export async function createBunkerGame() {
  const response = await apiClient.post('/games/bunker')
  return response.data
}

export async function fetchBunkerGame(code) {
  const response = await apiClient.get(`/games/bunker/${code}`)
  return response.data
}

// action: 'join' | 'leave' | 'start' | 'invite-chat'
export async function bunkerLobbyAction(code, action) {
  const response = await apiClient.post(`/games/bunker/${code}/${action}`)
  return response.data
}

// move: { action: 'reveal'|'vote'|'advance'|'stop', category?, target?, version }
export async function sendBunkerMove(code, move) {
  const response = await apiClient.post(`/games/bunker/${code}/move`, move)
  return response.data
}

// Столы для очной игры (только админ): { title, tags: [строки с тегами], host_tag? }
export async function fetchBunkerTables() {
  const response = await apiClient.get('/games/bunker/tables')
  return response.data
}

export async function createBunkerTable(table) {
  const response = await apiClient.post('/games/bunker/tables', table)
  return response.data
}

export async function updateBunkerTable(code, table) {
  const response = await apiClient.put(`/games/bunker/tables/${code}`, table)
  return response.data
}

export async function startBunkerTable(code) {
  const response = await apiClient.post(`/games/bunker/tables/${code}/start`)
  return response.data
}

export async function cancelBunkerTable(code) {
  const response = await apiClient.delete(`/games/bunker/tables/${code}`)
  return response.data
}

// Столы из админки, за которые можно сесть самому (карты не розданы, есть место).
export async function fetchOpenBunkerTables() {
  const response = await apiClient.get('/games/bunker/open-tables')
  return response.data
}
