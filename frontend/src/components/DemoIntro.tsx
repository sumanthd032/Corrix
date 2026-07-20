import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
import { Clock, Database, Play, Wifi, WifiOff } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'

/**
 * A very short context note shown once when the demo is first entered,
 * before the guided tour: what the demo is, whether the live backend is
 * connected, and how the data is sourced (the real-vs-simulated split).
 */
export function DemoIntro({ onStartTour, onSkip }: { onStartTour: () => void; onSkip: () => void }) {
  const connectionMode = useCorrixStore((s) => s.connectionMode)
  const live = connectionMode === 'live'

  return createPortal(
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className="glass-panel corner-frame w-full max-w-md p-6"
        role="dialog"
        aria-label="About this demo"
      >
        <span className="eyebrow">Live demo</span>
        <h2 className="mt-2 font-display text-xl font-semibold text-[var(--color-text-primary)]">
          Welcome to the Corrix command center
        </h2>

        <div className="mt-4 flex flex-col gap-3">
          <div className="flex gap-3">
            <Play size={16} className="mt-0.5 shrink-0 text-[var(--color-accent)]" aria-hidden="true" />
            <p className="text-sm leading-relaxed text-[var(--color-text-secondary)]">
              This is the real product. Pick a scenario and watch a compound risk get caught end to end, in under thirty seconds.
            </p>
          </div>
          <div className="flex gap-3">
            {live ? (
              <Wifi size={16} className="mt-0.5 shrink-0 text-[var(--color-accent)]" aria-hidden="true" />
            ) : (
              <WifiOff size={16} className="mt-0.5 shrink-0 text-[var(--color-text-tertiary)]" aria-hidden="true" />
            )}
            <p className="text-sm leading-relaxed text-[var(--color-text-secondary)]">
              {live ? (
                <>Connected to the <span className="text-[var(--color-accent)]">live backend</span>, so the reasoning and verdicts you will see are real, streamed over a WebSocket.</>
              ) : (
                <>Running on built-in demo data, the live backend is not reachable right now, so the dashboard shows a representative snapshot.</>
              )}
            </p>
          </div>
          <div className="flex gap-3">
            <Database size={16} className="mt-0.5 shrink-0 text-[var(--color-accent)]" aria-hidden="true" />
            <p className="text-sm leading-relaxed text-[var(--color-text-secondary)]">
              The AI reasoning, regulatory search, and computer vision are genuinely real. The plant sensor streams are calibrated simulation, validated against a real industrial dataset.
            </p>
          </div>
        </div>

        <div
          className="mt-4 flex gap-3 rounded-[var(--radius-control)] border p-3"
          style={{
            borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)',
            background: 'var(--color-accent-dim)',
            boxShadow: '0 0 22px -10px color-mix(in srgb, var(--color-accent) 60%, transparent)',
          }}
        >
          <Clock size={17} className="mt-0.5 shrink-0 text-[var(--color-accent)]" aria-hidden="true" />
          <p className="text-sm leading-relaxed text-[var(--color-text-secondary)]">
            <span className="font-semibold text-[var(--color-text-primary)]">First run is slow.</span>{' '}
            The first scenario warms up the models on this small free-tier server, so the first result can take{' '}
            <span className="font-semibold text-[var(--color-accent)]">20 to 30 seconds</span>. Every run after that is quicker. The reasoning is real, not canned, so the wait is genuine work.
          </p>
        </div>

        <div className="mt-6 flex items-center gap-3">
          <button
            type="button"
            onClick={onSkip}
            className="text-xs text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"
          >
            Skip
          </button>
          <button
            type="button"
            onClick={onStartTour}
            className="ml-auto flex items-center gap-1.5 rounded-[var(--radius-control)] border px-4 py-2 text-sm font-medium text-[var(--color-accent)]"
            style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
          >
            Start the tour
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
          </button>
        </div>
      </motion.div>
    </div>,
    document.body,
  )
}
