// Ужать фото перед отправкой: снимок с телефона весит 5–10 МБ, а прокси
// пропускает около мегабайта. Длинная сторона — до maxSide, формат — JPEG.
export async function shrinkImage(file, maxSide = 1280, quality = 0.82) {
  const bitmap = await loadBitmap(file)
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close?.()
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('Не удалось обработать фото'))),
      'image/jpeg',
      quality,
    )
  })
}

// createImageBitmap учитывает поворот из EXIF (фото с телефона не ляжет набок);
// где его нет — обычная картинка.
async function loadBitmap(file) {
  if (window.createImageBitmap) {
    try {
      return await createImageBitmap(file, { imageOrientation: 'from-image' })
    } catch {
      /* старый браузер или формат — пробуем через <img> */
    }
  }
  const url = URL.createObjectURL(file)
  try {
    const img = new Image()
    img.src = url
    await img.decode()
    return img
  } finally {
    URL.revokeObjectURL(url)
  }
}
