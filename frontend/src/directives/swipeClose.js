// Директива v-swipe-close="closeFn" — мобильный жест «смахнуть шторку вниз».
// Вешается на сам элемент шторки (.modal / .sheet): палец тянет её за собой,
// после порога по расстоянию или скорости — шторка уезжает вниз и закрывается,
// иначе пружинит обратно. Пока элемент смонтирован, прокрутка фона заблокирована.

const MOBILE_QUERY = '(max-width: 768px)'
const DISMISS_DISTANCE = 96 // путь вниз (px), после которого отпускание закрывает
const DISMISS_VELOCITY = 0.55 // px/ms — быстрый флик закрывает и с меньшего пути
const DRAG_START_SLOP = 8 // px до распознавания жеста (чтобы не мешать тапам)

// Между точкой касания и шторкой есть прокрученный контейнер —
// значит жест должен скроллить контент, а не тянуть шторку.
function hasScrolledAncestor(target, root) {
  for (let node = target; node && node !== root; node = node.parentElement) {
    if (node.scrollTop > 0) return true
  }
  return root.scrollTop > 0
}

// Модалок может быть несколько (шторка поверх шторки) — считаем открытые.
let scrollLocks = 0

function lockBodyScroll() {
  if (++scrollLocks === 1) document.body.style.overflow = 'hidden'
}

function unlockBodyScroll() {
  if (--scrollLocks <= 0) {
    scrollLocks = 0
    document.body.style.overflow = ''
  }
}

const states = new WeakMap()

export default {
  mounted(el, binding) {
    const state = {
      close: binding.value,
      tracking: false,
      dragging: false,
      canDrag: false,
      closing: false,
      startY: 0,
      lastY: 0,
      lastT: 0,
      velocity: 0,
    }

    state.onTouchStart = (event) => {
      if (state.closing || event.touches.length !== 1) return
      if (!window.matchMedia(MOBILE_QUERY).matches) return
      state.tracking = true
      state.dragging = false
      state.canDrag = !hasScrolledAncestor(event.target, el)
      state.startY = state.lastY = event.touches[0].clientY
      state.lastT = event.timeStamp
      state.velocity = 0
    }

    state.onTouchMove = (event) => {
      if (!state.tracking || state.closing) return
      const y = event.touches[0].clientY
      const dy = y - state.startY
      const dt = event.timeStamp - state.lastT
      if (dt > 0) state.velocity = (y - state.lastY) / dt
      state.lastY = y
      state.lastT = event.timeStamp

      if (!state.dragging) {
        if (dy > DRAG_START_SLOP && state.canDrag) {
          state.dragging = true
          // Тянем от точки распознавания жеста — шторка не прыгает под пальцем.
          state.startY = y
          el.style.transition = 'none'
        } else if (dy < -DRAG_START_SLOP) {
          state.tracking = false // жест вверх — это скролл контента, не мешаем
        }
        return
      }

      event.preventDefault()
      el.style.transform = `translateY(${Math.max(0, y - state.startY)}px)`
    }

    state.onTouchEnd = () => {
      if (!state.dragging) {
        state.tracking = false
        return
      }
      state.tracking = false
      state.dragging = false

      const offset = Math.max(0, state.lastY - state.startY)
      const isFlick = offset > DRAG_START_SLOP * 3 && state.velocity > DISMISS_VELOCITY
      if (offset > DISMISS_DISTANCE || isFlick) {
        state.closing = true
        el.style.transition = 'transform 0.2s ease-in'
        el.style.transform = 'translateY(110%)'
        const backdrop = el.parentElement
        if (backdrop) {
          backdrop.style.transition = 'opacity 0.2s ease'
          backdrop.style.opacity = '0'
        }
        setTimeout(() => state.close?.(), 180)
      } else {
        el.style.transition = 'transform 0.25s cubic-bezier(0.16, 1, 0.3, 1)'
        el.style.transform = ''
      }
    }

    el.addEventListener('touchstart', state.onTouchStart, { passive: true })
    el.addEventListener('touchmove', state.onTouchMove, { passive: false })
    el.addEventListener('touchend', state.onTouchEnd, { passive: true })
    el.addEventListener('touchcancel', state.onTouchEnd, { passive: true })
    states.set(el, state)
    lockBodyScroll()
  },

  updated(el, binding) {
    const state = states.get(el)
    if (state) state.close = binding.value
  },

  unmounted(el) {
    const state = states.get(el)
    if (state) {
      el.removeEventListener('touchstart', state.onTouchStart)
      el.removeEventListener('touchmove', state.onTouchMove)
      el.removeEventListener('touchend', state.onTouchEnd)
      el.removeEventListener('touchcancel', state.onTouchEnd)
      states.delete(el)
    }
    unlockBodyScroll()
  },
}
