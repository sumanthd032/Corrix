import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { usePrefersReducedMotion } from '../lib/usePrefersReducedMotion'

const BOOT_LINES = [
  'Plant layout and zone-adjacency graph',
  'Sensor Stream, Permit/Shift, and Worker Location MCP servers',
  'Regulatory Intelligence substrate (Neo4j GraphRAG)',
  'Safety Council: 5 agents + Chair, LangGraph-orchestrated',
  'Joint-evidence novelty detector calibrated',
  'Time-to-Critical forecaster, Monte Carlo rollout ready',
]

const WORDMARK = 'CORRIX'
const SESSION_KEY = 'corrix-boot-shown'
const LINE_INTERVAL_MS = 220
const LINES_DONE_AT_MS = LINE_INTERVAL_MS * BOOT_LINES.length
const WORDMARK_AT_MS = LINES_DONE_AT_MS + 300
const AUTO_COMPLETE_MS = WORDMARK_AT_MS + 1500

export function shouldShowBootSequence(): boolean {
  if (typeof window === 'undefined') return false
  return window.sessionStorage.getItem(SESSION_KEY) !== '1'
}

export function BootSequence({ onComplete }: { onComplete: () => void }) {
  const reducedMotion = usePrefersReducedMotion()
  const [visibleLines, setVisibleLines] = useState(0)
  const [showWordmark, setShowWordmark] = useState(false)
  const [dismissing, setDismissing] = useState(false)

  const finish = () => {
    window.sessionStorage.setItem(SESSION_KEY, '1')
    setDismissing(true)
    setTimeout(onComplete, 400)
  }

  useEffect(() => {
    if (reducedMotion) {
      window.sessionStorage.setItem(SESSION_KEY, '1')
      onComplete()
      return
    }

    const lineTimers = BOOT_LINES.map((_, i) =>
      setTimeout(() => setVisibleLines(i + 1), LINE_INTERVAL_MS * (i + 1)),
    )
    const wordmarkTimer = setTimeout(() => setShowWordmark(true), WORDMARK_AT_MS)
    const autoTimer = setTimeout(finish, AUTO_COMPLETE_MS)

    return () => {
      lineTimers.forEach(clearTimeout)
      clearTimeout(wordmarkTimer)
      clearTimeout(autoTimer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reducedMotion])

  if (reducedMotion) return null

  return (
    <AnimatePresence>
      {!dismissing && (
        <motion.div
          className="bg-blueprint-grid fixed inset-0 z-[100] flex cursor-pointer flex-col items-center justify-center overflow-hidden"
          style={{ backgroundColor: 'var(--color-base)' }}
          onClick={finish}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        >
          <div className="bg-scanlines pointer-events-none absolute inset-0" aria-hidden="true" />

          <motion.div
            className="pointer-events-none absolute left-0 right-0 h-24"
            style={{
              background:
                'linear-gradient(to bottom, transparent, color-mix(in srgb, var(--color-accent) 12%, transparent), transparent)',
            }}
            initial={{ top: '-10%' }}
            animate={{ top: '110%' }}
            transition={{ duration: 2.2, ease: 'linear', repeat: Infinity }}
            aria-hidden="true"
          />

          <div className="relative flex w-full max-w-lg flex-col items-center gap-8 px-6">
            <div className="flex w-full flex-col gap-1.5 font-mono-data text-[11px] text-[var(--color-text-secondary)]">
              {BOOT_LINES.map((line, i) => (
                <motion.div
                  key={line}
                  className="flex items-center gap-2"
                  initial={{ opacity: 0, x: -8 }}
                  animate={i < visibleLines ? { opacity: 1, x: 0 } : {}}
                  transition={{ duration: 0.25 }}
                >
                  <span style={{ color: i < visibleLines ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }}>
                    {i < visibleLines ? '◆' : '◇'}
                  </span>
                  <span>{line}</span>
                </motion.div>
              ))}
            </div>

            <div className="h-px w-full overflow-hidden bg-white/[0.06]">
              <motion.div
                className="h-full"
                style={{ backgroundColor: 'var(--color-accent)' }}
                initial={{ width: '0%' }}
                animate={{ width: `${(visibleLines / BOOT_LINES.length) * 100}%` }}
                transition={{ duration: 0.2 }}
              />
            </div>

            <AnimatePresence>
              {showWordmark && (
                <motion.div
                  className="flex flex-col items-center gap-3"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <div className="flex" style={{ textShadow: 'var(--shadow-glow-accent-strong)' }}>
                    {WORDMARK.split('').map((letter, i) => (
                      <motion.span
                        key={i}
                        className="font-display text-6xl font-bold tracking-tight"
                        style={{ color: 'var(--color-text-primary)' }}
                        initial={{ opacity: 0, y: 16, filter: 'blur(6px)' }}
                        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                        transition={{ duration: 0.4, delay: i * 0.06, ease: 'easeOut' }}
                      >
                        {letter}
                      </motion.span>
                    ))}
                  </div>
                  <motion.p
                    className="font-mono-data text-xs tracking-[0.2em]"
                    style={{ color: 'var(--color-text-secondary)' }}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.6 }}
                  >
                    ALL SYSTEMS NOMINAL
                  </motion.p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <span className="absolute bottom-6 font-mono-data text-[10px] text-[var(--color-text-tertiary)]">
            click anywhere to skip
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
