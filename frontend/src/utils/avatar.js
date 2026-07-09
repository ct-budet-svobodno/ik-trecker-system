const PALETTE = ['#6c3bff', '#2dd4bf', '#f97362', '#fbbf24', '#60a5fa', '#a78bfa']

export function getInitials(fullName) {
  if (!fullName) return '?'
  return fullName
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function getAvatarColor(userId) {
  if (userId == null) return '#3a3a45'
  return PALETTE[userId % PALETTE.length]
}
