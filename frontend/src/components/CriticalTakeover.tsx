import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { OctagonAlert } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'
import { usePrefersReducedMotion } from '../lib/usePrefersReducedMotion'
import type { RiskLevel } from '../types'

const VISIBLE_MS = 2600

/**
 * A brief, dismissible full-viewport moment the instant a verdict first
 * resolves CRITICAL, not on every re-render of an already-critical
 * verdict. Purely a presentation layer over data that already exists
 * (verdict.riskLevel, verdict.zoneId): no new state is computed here.
 */
export function CriticalTakeover() {
  const verdict = useCorrixStore((s) => s.verdict)
  const reducedMotion = usePrefersReducedMotion()
  const [show, setShow] = useState(false)
  const prevRisk = useRef<RiskLevel | null>(null)

  useEffect(() => {
    const current = verdict?.riskLevel ?? null
    if (current === 'CRITICAL' && prevRisk.current !== 'CRITICAL' && !reducedMotion) {
      setShow(true)
      const timer = setTimeout(() => setShow(false), VISIBLE_MS)
      prevRisk.current = current
      return () => clearTimeout(timer)
    }
    prevRisk.current = current
  }, [verdict, reducedMotion])

  return (
    <AnimatePresence>
      {show && verdict && (
        <motion.div
          className="fixed inset-0 z-[90] flex cursor-pointer items-center justify-center"
          onClick={() => setShow(false)}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
        >
          <motion.div
            className="pointer-events-none absolute inset-0"
            animate={{
              boxShadow: [
                'inset 0 0 120px 20px rgba(214,40,40,0.35)',
                'inset 0 0 200px 40px rgba(214,40,40,0.55)',
                'inset 0 0 120px 20px rgba(214,40,40,0.35)',
              ],
            }}
            transition={{ duration: 1.1, repeat: Infinity, ease: 'easeInOut' }}
          />

          <motion.div
            className="glass-panel flex flex-col items-center gap-3 px-10 py-8"
            style={{ boxShadow: 'var(--shadow-glow-critical-strong)' }}
            initial={{ scale: 1.5, opacity: 0, rotate: -3 }}
            animate={{ scale: 1, opacity: 1, rotate: 0 }}
            exit={{ scale: 0.9, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 260, damping: 18 }}
          >
            <OctagonAlert size={56} style={{ color: 'var(--color-risk-critical)' }} aria-hidden="true" />
            <p
              className="font-display text-4xl font-bold tracking-tight"
              style={{ color: 'var(--color-risk-critical)' }}
            >
              CRITICAL
            </p>
            <p className="font-mono-data text-sm text-[var(--color-text-secondary)]">
              Zone {verdict.zoneId} · {Math.round(verdict.confidence * 100)}% confidence
            </p>
            <p className="max-w-md text-center text-sm text-[var(--color-text-primary)]">
              {verdict.recommendedAction}
            </p>
            <span className="mt-1 font-mono-data text-[10px] text-[var(--color-text-tertiary)]">
              click anywhere to dismiss
            </span>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
