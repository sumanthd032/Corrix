import { useEffect, useState } from 'react'
import { OVERRIDE_WINDOW_MS, useCorrixStore } from '../store/useCorrixStore'

export interface OverrideCountdown {
  /** True while a live override window is open and counting down. */
  active: boolean
  /** Whole seconds remaining in the window (0 once it has closed). */
  remaining: number
  /** 0 to 1, how much of the window is left, for a progress bar. */
  fraction: number
  /** True once the window has elapsed but the verdict has not yet arrived,
   * i.e. the Chair is now ruling. */
  chairRuling: boolean
}

/**
 * Drives the visible countdown for the Safety Officer Override window from the
 * store's deliberationDeadline. Ticks a few times a second only while a window
 * is open, so the deliberate 8s pause reads as a step with a clock on it,
 * not unexplained lag. Returns inactive when no live window is open.
 */
export function useOverrideCountdown(): OverrideCountdown {
  const deadline = useCorrixStore((s) => s.deliberationDeadline)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (deadline == null) return
    setNow(Date.now())
    const id = setInterval(() => setNow(Date.now()), 200)
    return () => clearInterval(id)
  }, [deadline])

  if (deadline == null) {
    return { active: false, remaining: 0, fraction: 0, chairRuling: false }
  }

  const msLeft = deadline - now
  const remaining = Math.max(0, Math.ceil(msLeft / 1000))
  const fraction = Math.max(0, Math.min(1, msLeft / OVERRIDE_WINDOW_MS))
  return {
    active: true,
    remaining,
    fraction,
    chairRuling: msLeft <= 0,
  }
}
