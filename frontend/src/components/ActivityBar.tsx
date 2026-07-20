import { AnimatePresence, motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'

/**
 * A global "the system is working" cue for the slow, asynchronous
 * operations, so the user is never left wondering whether something is
 * happening. A thin indeterminate bar at the very top plus a labeled chip.
 * Reads the store-level async states (a live Council convening, a
 * regulatory lookup); the shorter local actions (incident PDF, what-if)
 * carry their own inline spinners.
 */
export function ActivityBar() {
  const councilStage = useCorrixStore((s) => s.councilStage)
  const chatPending = useCorrixStore((s) => s.chatPending)

  const messages: string[] = []
  if (councilStage === 'convening') messages.push('Safety Council convening')
  else if (councilStage === 'deliberating') messages.push('Council deliberating, override window open')
  if (chatPending) messages.push('Searching the regulatory corpus')

  const busy = messages.length > 0

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
            className="pointer-events-none fixed bottom-4 left-1/2 z-[60] flex -translate-x-1/2 items-center gap-2 rounded-full border border-[var(--color-hairline)] px-3.5 py-2 text-xs text-[var(--color-text-secondary)] backdrop-blur"
            style={{ background: 'color-mix(in srgb, var(--color-surface-1) 90%, transparent)', boxShadow: 'var(--shadow-raised)' }}
            role="status"
            aria-live="polite"
          >
            <Loader2 size={13} className="animate-spin text-[var(--color-accent)]" aria-hidden="true" />
            {messages.join(' · ')}…
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
