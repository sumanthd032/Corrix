import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, Loader2, Radio } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'

/**
 * The initial-connection reassurance. The very first WebSocket connect can
 * take 10 to 20 seconds on the small free-tier backend (CPU throttle plus the
 * model warmup), and during that window the dashboard is on demo data. Without
 * a cue a viewer assumes it is broken. This shows a prominent, non-blocking
 * banner at the top while the backend is connecting for the first time, with a
 * live elapsed timer and an escalating message, then a brief "connected"
 * confirmation once the live stream is up. It never appears again after the
 * first successful connect (a later drop is the ConnectionPill's job).
 */
export function ConnectingOverlay() {
  const mode = useCorrixStore((s) => s.connectionMode)
  const hasEverConnected = useCorrixStore((s) => s.hasEverConnected)

  const [elapsed, setElapsed] = useState(0)
  const [dismissed, setDismissed] = useState(false)
  const [justConnected, setJustConnected] = useState(false)
  const startRef = useRef(performance.now())

  // Tick while we have not yet connected for the first time.
  useEffect(() => {
    if (hasEverConnected) return
    const id = setInterval(() => {
      setElapsed((performance.now() - startRef.current) / 1000)
    }, 200)
    return () => clearInterval(id)
  }, [hasEverConnected])

  // On the first successful connect, show a short confirmation, then hide.
  useEffect(() => {
    if (mode === 'live' && hasEverConnected) {
      setJustConnected(true)
      const t = setTimeout(() => setJustConnected(false), 2600)
      return () => clearTimeout(t)
    }
  }, [mode, hasEverConnected])

  const connecting = !hasEverConnected && !dismissed
  const show = connecting || justConnected

  const message = justConnected
    ? 'Connected to the live backend. The reasoning and verdicts are now real.'
    : elapsed > 20
      ? 'Taking a little longer than usual. It will connect on its own, and the dashboard already works on demo data meanwhile.'
      : elapsed > 8
        ? 'Still reaching the backend. It runs on a small free-tier server, so the first connection can take up to 20 seconds.'
        : 'This can take 10 to 20 seconds on the free-tier demo server. Nothing is broken.'

  return createPortal(
    <AnimatePresence>
      {show && (
        <motion.div
          key="connect"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -16 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          className="fixed left-1/2 top-4 z-[80] flex w-full max-w-[460px] -translate-x-1/2 items-center gap-3.5 rounded-2xl border px-5 py-3.5 backdrop-blur-md"
          style={{
            background: 'color-mix(in srgb, var(--color-surface-1) 94%, transparent)',
            borderColor: justConnected
              ? 'color-mix(in srgb, var(--color-accent) 55%, transparent)'
              : 'color-mix(in srgb, var(--color-accent) 40%, transparent)',
            boxShadow:
              '0 0 0 1px color-mix(in srgb, var(--color-accent) 18%, transparent), 0 18px 48px -14px color-mix(in srgb, var(--color-accent) 40%, transparent), var(--shadow-raised)',
          }}
          role="status"
          aria-live="polite"
        >
          {justConnected ? (
            <CheckCircle2 size={22} className="shrink-0 text-[var(--color-accent)]" aria-hidden="true" />
          ) : (
            <div className="relative grid h-9 w-9 shrink-0 place-items-center">
              <Radio size={16} className="text-[var(--color-accent)]" aria-hidden="true" />
              <motion.span
                className="absolute inset-0 rounded-full border"
                style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 50%, transparent)' }}
                animate={{ scale: [1, 1.5], opacity: [0.7, 0] }}
                transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
                aria-hidden="true"
              />
            </div>
          )}

          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2">
              <span className="truncate font-display text-sm font-semibold text-[var(--color-text-primary)]">
                {justConnected ? 'Live backend connected' : 'Connecting to the live backend'}
              </span>
              {connecting && (
                <span className="tnum ml-auto shrink-0 flex items-center gap-1 text-xs font-semibold text-[var(--color-accent)]">
                  <Loader2 size={11} className="animate-spin" aria-hidden="true" />
                  {elapsed.toFixed(0)}s
                </span>
              )}
            </div>
            <div className="mt-0.5 text-[11px] leading-snug text-[var(--color-text-tertiary)]">{message}</div>
          </div>

          {connecting && elapsed > 8 && (
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="shrink-0 self-start text-[11px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"
            >
              Hide
            </button>
          )}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}
