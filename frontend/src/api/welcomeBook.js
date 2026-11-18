import apiClient from './client'

export async function fetchWelcomeBook() {
  return (await apiClient.get('/welcome-book')).data
}

export async function fetchWelcomeBookPdf() {
  return (await apiClient.get('/welcome-book/pdf', { responseType: 'arraybuffer' })).data
}

export async function uploadWelcomeBook(file, onUploadProgress) {
  return (await apiClient.put('/welcome-book', file, {
    headers: { 'Content-Type': 'application/pdf' },
    onUploadProgress,
  })).data
}

export async function saveWelcomeBookProgress(version, page) {
  await apiClient.put('/welcome-book/progress', { version, page })
}

export async function fetchWelcomeBookReaders() {
  return (await apiClient.get('/welcome-book/readers')).data
}
