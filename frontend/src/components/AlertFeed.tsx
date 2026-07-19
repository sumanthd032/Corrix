import { AnimatePresence, motion } from 'framer-motion'
import { Radio } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'
import { RiskBadge } from './RiskBadge'

function relativeTime(isoTimestamp: string): string {
  const deltaMs = Date.now() - new Date(isoTimestamp).getTime()
  const minutes = Math.round(deltaMs / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes === 1) return '1 min ago'
  return `${minutes} min ago`
}

const RISK_ACCENT: Record<string, string> = {
  SAFE: 'var(--color-risk-safe)',
  CAUTION: 'var(--color-risk-caution)',
  HIGH: 'var(--color-risk-high)',
  CRITICAL: 'var(--color-risk-critical)',
}

export function AlertFeed() {
  const alerts = useCorrixStore((s) => s.alerts)

  return (
    <section className="glass-panel flex flex-col gap-3 p-4">
      <div className="flex items-center gap-2">
        <Radio size={15} className="text-[var(--color-accent)]" aria-hidden="true" />
        <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text-primary)]">
          Alert &amp; Explanation Feed
        </h2>
      </div>

      {alerts.length === 0 ? (
        <p className="rounded-[var(--radius-control)] border border-dashed border-[var(--color-hairline)] px-3 py-4 text-center text-xs text-[var(--color-text-tertiary)]">
          No alerts. All zones within limits.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          <AnimatePresence initial={false}>
            {alerts.map((alert, i) => (
              <motion.li
                key={alert.id}
                layout
                initial={{ opacity: 0, y: -12, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.3, delay: i === 0 ? 0 : 0.03 * i, ease: 'easeOut' }}
                className="flex flex-col gap-1 overflow-hidden rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/50 p-3"
                style={{ borderLeft: `2px solid ${RISK_ACCENT[alert.riskLevel] ?? 'var(--color-hairline)'}` }}
                whileHover={{ backgroundColor: 'color-mix(in srgb, var(--color-surface-3) 60%, transparent)' }}
              >
                <div className="flex items-center justify-between">
                  <RiskBadge level={alert.riskLevel} size="sm" />
                  <span className="tnum text-[10px] text-[var(--color-text-tertiary)]">
                    {alert.zoneId} · {relativeTime(alert.timestamp)}
                  </span>
                </div>
                <p className="text-sm leading-snug text-[var(--color-text-primary)]">{alert.summary}</p>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </section>
  )
}
