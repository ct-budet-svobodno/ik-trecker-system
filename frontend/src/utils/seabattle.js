// Морской бой 10×10: расстановка на клиенте. Правила те же, что на сервере
// (backend/app/games/seabattle.py) — сервер всё равно перепроверит флот.

export const N = 10
export const FLEET = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1]
export const LETTERS = 'АБВГДЕЖЗИК'

export const rowOf = (cell) => Math.floor(cell / N)
export const colOf = (cell) => cell % N

// Клетки корабля от носа вправо/вниз; null — вылезает за поле.
export function shipCells(start, size, vertical) {
  if (vertical) {
    if (rowOf(start) + size > N) return null
    return Array.from({ length: size }, (_, i) => start + i * N)
  }
  if (colOf(start) + size > N) return null
  return Array.from({ length: size }, (_, i) => start + i)
}

// Клетки и все 8 соседей: там другой корабль стоять не может.
export function halo(cells) {
  const out = new Set()
  for (const cell of cells) {
    for (let dr = -1; dr <= 1; dr++) {
      for (let dc = -1; dc <= 1; dc++) {
        const r = rowOf(cell) + dr
        const c = colOf(cell) + dc
        if (r >= 0 && r < N && c >= 0 && c < N) out.add(r * N + c)
      }
    }
  }
  return out
}

export function canPlace(ships, cells) {
  if (!cells) return false
  const blocked = halo(ships.flat())
  return cells.every((c) => !blocked.has(c))
}

// Поставить корабль носом в cell; у края поля сдвигаем назад, чтобы влез.
export function fitShip(cell, size, vertical) {
  const r = rowOf(cell)
  const c = colOf(cell)
  const start = vertical ? Math.min(r, N - size) * N + c : r * N + Math.min(c, N - size)
  return shipCells(start, size, vertical)
}

// Какие длины ещё не расставлены (с повторами).
export function remainingSizes(ships) {
  const left = [...FLEET]
  for (const ship of ships) left.splice(left.indexOf(ship.length), 1)
  return left
}

export function randomFleet() {
  for (;;) {
    const ships = []
    for (const size of FLEET) {
      const options = []
      for (let start = 0; start < N * N; start++) {
        for (const vertical of [false, true]) {
          const cells = shipCells(start, size, vertical)
          if (cells && canPlace(ships, cells)) options.push(cells)
        }
      }
      if (!options.length) break
      ships.push(options[Math.floor(Math.random() * options.length)])
    }
    if (ships.length === FLEET.length) return ships
  }
}

export function cellLabel(cell) {
  return `${LETTERS[colOf(cell)]}${rowOf(cell) + 1}`
}
