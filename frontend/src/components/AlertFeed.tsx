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
          {alerts.map((alert) => (
            <li
              key={alert.id}
              className="flex flex-col gap-1 rounded-[var(--radius-control)] bg-white/[0.03] p-3"
            >
              <div className="flex items-center justify-between">
                <RiskBadge level={alert.riskLevel} size="sm" />
                <span className="font-mono-data text-[10px] text-[var(--color-text-secondary)]">
                  {alert.zoneId} · {relativeTime(alert.timestamp)}
                </span>
              </div>
              <p className="text-sm text-[var(--color-text-primary)]">{alert.summary}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
