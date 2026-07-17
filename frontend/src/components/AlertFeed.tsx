import { AnimatePresence, motion } from 'framer-motion'
import { useCorrixStore } from '../store/useCorrixStore'
import { RiskBadge } from './RiskBadge'

function relativeTime(isoTimestamp: string): string {
  const deltaMs = Date.now() - new Date(isoTimestamp).getTime()
  const minutes = Math.round(deltaMs / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes === 1) return '1 min ago'
  return `${minutes} min ago`
}

export function AlertFeed() {
  const alerts = useCorrixStore((s) => s.alerts)

  return (
    <section className="glass-panel flex flex-col gap-3 p-5">
      <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text-primary)]">
        Alert &amp; Explanation Feed
      </h2>

      {alerts.length === 0 ? (
        <p className="text-sm text-[var(--color-text-secondary)]">No alerts yet.</p>
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
                className="flex flex-col gap-1 rounded-[var(--radius-control)] bg-white/[0.03] p-3"
                whileHover={{ backgroundColor: 'rgba(255,255,255,0.05)' }}
              >
                <div className="flex items-center justify-between">
                  <RiskBadge level={alert.riskLevel} size="sm" />
                  <span className="font-mono-data text-[10px] text-[var(--color-text-secondary)]">
                    {alert.zoneId} · {relativeTime(alert.timestamp)}
                  </span>
                </div>
                <p className="text-sm text-[var(--color-text-primary)]">{alert.summary}</p>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </section>
  )
}
