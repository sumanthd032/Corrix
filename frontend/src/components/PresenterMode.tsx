import { useCallback, useEffect, useLayoutEffect, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, X } from 'lucide-react'

/**
 * A guided walkthrough of the dashboard. It spotlights each key panel in
 * turn (targets carry a `data-tour` attribute) with a caption card, and
 * auto-starts the first time the demo is entered. Purely presentational:
 * it never changes app state, so a presenter can run it live without
 * disturbing a scenario.
 */
interface Step {
  selector: string | null
  title: string
  body: string
}

const STEPS: Step[] = [
  {
    selector: null,
    title: 'Welcome to Corrix',
    body: 'This is the live command center. A quick tour of what you are looking at, then you can run a real scenario.',
  },
  {
    selector: '[data-tour="telemetry"]',
    title: 'Telemetry',
    body: 'The state of the plant at a glance: compound risk, time-to-critical, council confidence, workers on site, and how many zones are elevated.',
  },
  {
    selector: '[data-tour="map"]',
    title: 'Plant schematic',
    body: 'Every zone, live. Nominal zones stay dark and only risk lights up. Toggle a real 3D view, and on a verdict you get the evacuation route and the spread-risk overlay.',
  },
  {
    selector: '[data-tour="council"]',
    title: 'The Safety Council',
    body: 'When a compound risk triggers, five agents convene and the Chair synthesizes an explained verdict, grounded in the actual regulation and with a what-if mitigation to test.',
  },
  {
    selector: '[data-tour="alerts"]',
    title: 'Alert & explanation feed',
    body: 'Every verdict and escalation lands here as it happens, most recent first.',
  },
  {
    selector: '[data-tour="regulatory"]',
    title: 'Regulatory Intelligence',
    body: 'Ask the OISD, Factories Act, and DGMS corpus directly, and get answers with real, checkable clause citations.',
  },
  {
    selector: '[data-tour="controls"]',
    title: 'Run a scenario',
    body: 'Pick a scenario up here to watch the whole thing happen live: the Council convening, the verdict, the forecast, the route. That is the best way to see Corrix work.',
  },
]

const PAD = 8
const CARD_W = 340

export function PresenterMode({ onClose }: { onClose: () => void }) {
  const [index, setIndex] = useState(0)
  const [rect, setRect] = useState<DOMRect | null>(null)
  const step = STEPS[index]
  const isLast = index === STEPS.length - 1

  const measure = useCallback(() => {
    if (!step.selector) { setRect(null); return }
    const el = document.querySelector(step.selector)
    if (!el) { setRect(null); return }
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    setRect(el.getBoundingClientRect())
  }, [step.selector])

  useLayoutEffect(() => {
    measure()
    // Re-measure shortly after, in case a scrollIntoView moved things.
    const t = setTimeout(measure, 260)
    window.addEventListener('resize', measure)
    return () => { clearTimeout(t); window.removeEventListener('resize', measure) }
  }, [measure])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowRight' || e.key === 'Enter') setIndex((i) => Math.min(i + 1, STEPS.length - 1))
      else if (e.key === 'ArrowLeft') setIndex((i) => Math.max(i - 1, 0))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // Caption card position.
  let cardStyle: CSSProperties
  if (!rect) {
    cardStyle = { left: '50%', top: '50%', transform: 'translate(-50%, -50%)' }
  } else {
    const below = rect.bottom + 200 < window.innerHeight
    const top = below ? rect.bottom + 14 : Math.max(16, rect.top - 200)
    const left = Math.min(Math.max(rect.left, 16), window.innerWidth - CARD_W - 16)
    cardStyle = { left, top }
  }

  return createPortal(
    <div className="fixed inset-0 z-[100]" style={{ pointerEvents: 'none' }}>
      {/* Dimmer + spotlight cutout */}
      {rect ? (
        <div
          style={{
            position: 'fixed',
            left: rect.left - PAD,
            top: rect.top - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
            borderRadius: 12,
            boxShadow: '0 0 0 9999px rgba(4,7,11,.74)',
            border: '1px solid color-mix(in srgb, var(--color-accent) 55%, transparent)',
            transition: 'all .3s cubic-bezier(.16,1,.3,1)',
            pointerEvents: 'none',
          }}
          aria-hidden="true"
        />
      ) : (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(4,7,11,.74)' }} aria-hidden="true" />
      )}

      {/* Caption card */}
      <motion.div
        key={index}
        role="dialog"
        aria-label="Guided tour"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: 'easeOut' }}
        className="glass-panel"
        style={{ position: 'fixed', width: CARD_W, padding: 16, pointerEvents: 'auto', ...cardStyle }}
      >
        <div className="flex items-center justify-between">
          <span className="eyebrow">
            Guided tour · {index + 1} / {STEPS.length}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[var(--radius-control)] p-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
            aria-label="End tour"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        <h3 className="mt-2 font-display text-base font-semibold text-[var(--color-text-primary)]">{step.title}</h3>
        <p className="mt-1.5 text-sm leading-relaxed text-[var(--color-text-secondary)]">{step.body}</p>

        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIndex((i) => Math.max(i - 1, 0))}
            disabled={index === 0}
            className="flex items-center gap-1 rounded-[var(--radius-control)] border border-[var(--color-hairline)] px-2.5 py-1.5 text-xs text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)] disabled:opacity-40"
          >
            <ArrowLeft size={13} aria-hidden="true" /> Back
          </button>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto rounded-[var(--radius-control)] px-2.5 py-1.5 text-xs text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"
          >
            Skip tour
          </button>
          <button
            type="button"
            onClick={() => (isLast ? onClose() : setIndex((i) => i + 1))}
            className="flex items-center gap-1 rounded-[var(--radius-control)] border px-3 py-1.5 text-xs font-medium text-[var(--color-accent)]"
            style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
          >
            {isLast ? 'Done' : 'Next'} {!isLast && <ArrowRight size={13} aria-hidden="true" />}
          </button>
        </div>
      </motion.div>
    </div>,
    document.body,
  )
}
