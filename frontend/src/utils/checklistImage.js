// Картинка чек-листа «Найди того, кто…» по макету Штаб'26-27: розовая сетка,
// заголовок «Чек-лист» и три повёрнутые голубые карточки с номерами.
// Рисуем на canvas в браузере админа и загружаем JPEG на бэкенд — так текст
// набирается фирменными шрифтами трекера без отрисовки на сервере.

const W = 1678
const H = 1131
const BLUE = '#2F32CA'
const INK = '#1E1F5C'
const BASE = '/checklist/'

// Координаты — из макета (px исходника). Текст пункта — в рамке карточки,
// ниже номера, с её наклоном.
const LAYOUT = {
  grid: [
    { src: 'grid-left.svg', x: 0, y: 0 },
    { src: 'grid-right.svg', x: 839, y: 0 },
  ],
  title: { src: 'title.svg', x: 836, y: 74 },
  cards: [
    {
      card: { src: 'card-1.svg', x: 222, y: 88 },
      frame: { src: 'frame-1.svg', x: 268, y: 112 },
      num: { src: 'num-1.svg', x: 276, y: 132 },
      text: { cx: 505, cy: 384, w: 370, h: 190, angle: -1.7 },
    },
    {
      card: { src: 'card-2.svg', x: 916, y: 386 },
      frame: { src: 'frame-2.svg', x: 958, y: 428 },
      num: { src: 'num-2.svg', x: 984, y: 432 },
      text: { cx: 1203, cy: 698, w: 370, h: 190, angle: 3 },
    },
    {
      card: { src: 'card-3.svg', x: 152, y: 600 },
      frame: { src: 'frame-3.svg', x: 228, y: 646 },
      num: { src: 'num-3.svg', x: 206, y: 732 },
      text: { cx: 505, cy: 946, w: 350, h: 160, angle: -12.7 },
    },
  ],
  footer: { x: W - 72, y: H - 70 },
}

const imageCache = new Map()

function loadImage(src) {
  if (!imageCache.has(src)) {
    imageCache.set(
      src,
      new Promise((resolve, reject) => {
        const img = new Image()
        img.onload = () => resolve(img)
        img.onerror = () => reject(new Error(`Не загрузилась картинка ${src}`))
        img.src = BASE + src
      }),
    )
  }
  return imageCache.get(src)
}

async function ready() {
  const sources = [
    ...LAYOUT.grid.map((g) => g.src),
    LAYOUT.title.src,
    ...LAYOUT.cards.flatMap((c) => [c.card.src, c.frame.src, c.num.src]),
  ]
  await Promise.all([
    ...sources.map(loadImage),
    document.fonts.load('600 40px "Golos Text"'),
    document.fonts.load('500 24px "Golos Text"'),
    document.fonts.load('500 30px "Unbounded"'),
  ])
}

// Перенос по словам; если не влезает в высоту — уменьшаем шрифт.
function fitText(ctx, text, maxWidth, maxHeight) {
  for (let size = 46; size >= 22; size -= 2) {
    ctx.font = `600 ${size}px "Golos Text"`
    const lines = []
    let line = ''
    for (const word of text.split(/\s+/)) {
      const probe = line ? `${line} ${word}` : word
      if (ctx.measureText(probe).width <= maxWidth || !line) {
        line = probe
      } else {
        lines.push(line)
        line = word
      }
    }
    if (line) lines.push(line)
    const lineHeight = Math.round(size * 1.18)
    const widest = Math.max(...lines.map((l) => ctx.measureText(l).width))
    if (lines.length * lineHeight <= maxHeight && widest <= maxWidth) return { size, lines, lineHeight }
  }
  ctx.font = '600 22px "Golos Text"'
  return { size: 22, lines: [text], lineHeight: 26 }
}

function drawFact(ctx, fact, box) {
  ctx.save()
  ctx.translate(box.cx, box.cy)
  ctx.rotate((box.angle * Math.PI) / 180)
  const left = -box.w / 2
  const top = -box.h / 2

  ctx.fillStyle = BLUE
  ctx.font = '500 24px "Golos Text"'
  ctx.textBaseline = 'top'
  ctx.fillText('Сфоткайся с', left, top)

  const labelGap = 38
  const { lines, lineHeight } = fitText(ctx, fact, box.w, box.h - labelGap)
  ctx.fillStyle = INK
  lines.forEach((line, i) => ctx.fillText(line, left, top + labelGap + i * lineHeight))
  ctx.restore()
}

function place(ctx, img, item) {
  ctx.drawImage(img, item.x, item.y, img.naturalWidth || img.width, img.naturalHeight || img.height)
}

// card: { number, full_name, facts: [3] } → Blob (image/jpeg)
export async function renderChecklist(card) {
  await ready()
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')

  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, W, H)
  for (const g of LAYOUT.grid) place(ctx, await loadImage(g.src), g)
  place(ctx, await loadImage(LAYOUT.title.src), LAYOUT.title)

  for (const [i, c] of LAYOUT.cards.entries()) {
    place(ctx, await loadImage(c.card.src), c.card)
    place(ctx, await loadImage(c.frame.src), c.frame)
    place(ctx, await loadImage(c.num.src), c.num)
    drawFact(ctx, card.facts[i] ?? '', c.text)
  }

  // Подпись: чей лист — пригодится, если картинку перешлют.
  ctx.textAlign = 'right'
  ctx.textBaseline = 'alphabetic'
  ctx.fillStyle = INK
  ctx.font = '500 30px "Unbounded"'
  ctx.fillText(`№${card.number}`, LAYOUT.footer.x, LAYOUT.footer.y - 44)
  ctx.font = '500 28px "Golos Text"'
  ctx.fillText(card.full_name, LAYOUT.footer.x, LAYOUT.footer.y)

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Не удалось собрать картинку'))), 'image/jpeg', 0.9)
  })
}
