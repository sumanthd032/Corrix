import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'

/**
 * A global, prominent "the system is working" cue for the slow, asynchronous
 * operations, so the user is never left wondering whether something is
 * happening. A thin indeterminate bar at the very top plus a large labeled
 * card, centered, with a spinning accent ring, a live elapsed timer, and a
 * reassuring line (the demo backend is a small free-tier server, so a real
 * Council convening can take a few seconds). Reads the store-level async
 * states; the shorter local actions (incident PDF, what-if) carry their own
 * spinners.
 */
export function ActivityBar() {
  const councilStage = useCorrixStore((s) => s.councilStage)
  const chatPending = useCorrixStore((s) => s.chatPending)

  let title = ''
  if (councilStage === 'convening') title = 'Safety Council convening'
  else if (councilStage === 'deliberating') title = 'Council deliberating'
  else if (chatPending) title = 'Searching the regulatory corpus'

  const detail =
    councilStage === 'deliberating' ? 'Override window open, the agents are reasoning' : chatPending && councilStage ? 'and searching the regulatory corpus' : ''

  const busy = title.length > 0

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
    }, 200)
    return () => clearInterval(id)
    // Restart the timer only when the busy period toggles on, not on every
    // title change within one operation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy])

  const reassurance =
    elapsed > 12
      ? 'Still working. The reasoning runs live on a small demo server, so hang tight, this is real, not canned.'
      : elapsed > 4
        ? 'This can take a few seconds on the free-tier demo server. The reasoning is running live.'
        : 'Working, this is live reasoning, not a canned response.'

  return (
    <AnimatePresence>
      {busy && (
        <>
          <motion.div
            key="bar"
            className="pointer-events-none fixed inset-x-0 top-0 z-[70] h-[3px] overflow-hidden"
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
            key="card"
            initial={{ opacity: 0, y: 14, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 14, scale: 0.96 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="pointer-events-none fixed bottom-8 left-1/2 z-[70] flex w-full max-w-[440px] -translate-x-1/2 items-center gap-4 rounded-2xl border px-5 py-4 backdrop-blur-md"
            style={{
              background: 'color-mix(in srgb, var(--color-surface-1) 94%, transparent)',
              borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)',
              boxShadow: '0 0 0 1px color-mix(in srgb, var(--color-accent) 20%, transparent), 0 18px 48px -12px color-mix(in srgb, var(--color-accent) 35%, transparent), var(--shadow-raised)',
            }}
            role="status"
            aria-live="polite"
          >
            {/* Spinning accent ring around a steady core, reads as active from across the room. */}
            <div className="relative grid h-11 w-11 shrink-0 place-items-center">
              <span
                className="absolute inset-0 rounded-full"
                style={{
                  background: 'conic-gradient(from 0deg, transparent, var(--color-accent))',
                  animation: 'spin 1.1s linear infinite',
                  WebkitMask: 'radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 3px))',
                  mask: 'radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 3px))',
                }}
                aria-hidden="true"
              />
              <Loader2 size={18} className="animate-spin text-[var(--color-accent)]" aria-hidden="true" />
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2">
                <span className="truncate font-display text-[15px] font-semibold text-[var(--color-text-primary)]">
                  {title}
                </span>
                <span className="tnum ml-auto shrink-0 text-sm font-semibold text-[var(--color-accent)]">
                  {elapsed.toFixed(0)}s
                </span>
              </div>
              {detail && (
                <div className="mt-0.5 truncate text-xs text-[var(--color-text-secondary)]">{detail}</div>
              )}
              <AnimatePresence mode="wait">
                <motion.div
                  key={reassurance}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.25 }}
                  className="mt-1 text-[11px] leading-snug text-[var(--color-text-tertiary)]"
                >
                  {reassurance}
                </motion.div>
              </AnimatePresence>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
