import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'

/**
 * A global "the system is working" cue for the slow, asynchronous
 * operations, so the user is never left wondering whether something is
 * happening. A thin indeterminate bar at the very top plus a labeled chip
 * with a live elapsed timer and, once an operation runs long, a reassuring
 * message (the demo backend is a small free-tier server, so a real Council
 * convening can take a few seconds). Reads the store-level async states; the
 * shorter local actions (incident PDF, what-if) carry their own spinners.
 */
export function ActivityBar() {
  const councilStage = useCorrixStore((s) => s.councilStage)
  const chatPending = useCorrixStore((s) => s.chatPending)

  const messages: string[] = []
  if (councilStage === 'convening') messages.push('Safety Council convening')
  else if (councilStage === 'deliberating') messages.push('Council deliberating, override window open')
  if (chatPending) messages.push('Searching the regulatory corpus')

  const busy = messages.length > 0

  // Elapsed timer, reset whenever a new busy period starts.
  const [elapsed, setElapsed] = useState(0)
  const startRef = useRef<number | null>(null)
  useEffect(() => {
    if (!busy) {
      startRef.current = null
      setElapsed(0)
      return
    }
    startRef.current = performance.now()
    setElapsed(0)
    const id = setInterval(() => {
      if (startRef.current != null) setElapsed((performance.now() - startRef.current) / 1000)
    }, 250)
    return () => clearInterval(id)
    // Restart the timer only when the busy period toggles on, not on every
    // message change within one operation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy])

  const reassurance =
    elapsed > 12
      ? 'Still working. The reasoning runs live on a small demo server, hang tight.'
      : elapsed > 5
        ? 'This can take a few seconds on the demo server.'
        : null

  return (
    <AnimatePresence>
      {busy && (
        <>
          <motion.div
            key="bar"
            className="pointer-events-none fixed inset-x-0 top-0 z-[60] h-[3px] overflow-hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div
              className="h-full w-1/3"
              style={{
                background: 'linear-gradient(90deg, transparent, var(--color-accent), transparent)',
                animation: 'hud-sweep 1.1s ease-in-out infinite',
              }}
            />
          </motion.div>

          <motion.div
            key="chip"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.2 }}
            className="pointer-events-none fixed bottom-4 left-1/2 z-[60] flex max-w-[92vw] -translate-x-1/2 flex-col items-center gap-1 rounded-2xl border border-[var(--color-hairline)] px-4 py-2.5 text-center backdrop-blur"
            style={{ background: 'color-mix(in srgb, var(--color-surface-1) 92%, transparent)', boxShadow: 'var(--shadow-raised)' }}
            role="status"
            aria-live="polite"
          >
            <span className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
              <Loader2 size={13} className="animate-spin text-[var(--color-accent)]" aria-hidden="true" />
              {messages.join(' · ')}…
              <span className="tnum text-[var(--color-text-tertiary)]">{elapsed.toFixed(0)}s</span>
            </span>
            <AnimatePresence>
              {reassurance && (
                <motion.span
                  key={reassurance}
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="text-[11px] text-[var(--color-text-tertiary)]"
                >
                  {reassurance}
                </motion.span>
              )}
            </AnimatePresence>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
