// Карта — число suit*13 + (rank-2), как в backend/app/games/durak.py.
// ︎ — текстовое начертание масти: иначе iOS рисует эмодзи.
const SUITS = ['♠︎', '♥︎', '♦︎', '♣︎']
const SUIT_NAMES = ['пики', 'черви', 'бубны', 'трефы']
const RANK_LABELS = { 11: 'В', 12: 'Д', 13: 'К', 14: 'Т' }

export function suitOf(card) {
  return Math.floor(card / 13)
}

export function rankOf(card) {
  return (card % 13) + 2
}

export function rankLabel(card) {
  const rank = rankOf(card)
  return RANK_LABELS[rank] ?? String(rank)
}

export function suitSymbol(suit) {
  return SUITS[suit]
}

export function suitName(suit) {
  return SUIT_NAMES[suit]
}

export function isRed(suit) {
  return suit === 1 || suit === 2
}
