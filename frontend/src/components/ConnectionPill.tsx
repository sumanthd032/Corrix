import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Loader2, Wifi, WifiOff } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'
import { Tooltip } from './Tooltip'

/**
 * The backend connection indicator. Prominent and amber when the backend
 * engine isn't reachable, so it's obvious the dashboard is on demo data;
 * hovering explains what to do. A short grace period after mount avoids
 * flashing the warning during the normal moment before the WebSocket
 * connects on a healthy load.
 */
const GRACE_MS = 4000

export function ConnectionPill() {
  const mode = useCorrixStore((s) => s.connectionMode)
  const [graceOver, setGraceOver] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setGraceOver(true), GRACE_MS)
    return () => clearTimeout(t)
  }, [])

  const state: 'live' | 'connecting' | 'offline' =
    mode === 'live' ? 'live' : graceOver ? 'offline' : 'connecting'

  if (state === 'live') {
    return (
      <Tooltip
        label="Live backend connected"
        hint="Real scenario stream and a real Safety Council, streamed over a WebSocket."
      >
        <span
          className="flex items-center gap-1.5 rounded-[var(--radius-sharp)] border px-2 py-1 eyebrow"
          style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', color: 'var(--color-accent)' }}
        >
          <Wifi size={12} aria-hidden="true" />
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: 'var(--color-accent)' }} />
          LIVE
        </span>
      </Tooltip>
    )
  }

  if (state === 'connecting') {
    return (
      <Tooltip label="Connecting" hint="Reaching the backend engine…">
        <span
          className="flex items-center gap-1.5 rounded-[var(--radius-sharp)] border border-[var(--color-hairline)] px-2 py-1 eyebrow text-[var(--color-text-tertiary)]"
        >
          <Loader2 size={12} className="animate-spin" aria-hidden="true" />
          Connecting
        </span>
      </Tooltip>
    )
  }

  return (
    <Tooltip
      label="Backend engine not connected"
      hint="The backend engine isn't connected. Wait a moment for it to come online, or carry on with the built-in demo flow — the dashboard runs on representative data until it reconnects."
    >
      <motion.span
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 400, damping: 18 }}
        className="flex items-center gap-1.5 rounded-[var(--radius-sharp)] border px-2 py-1 eyebrow"
        style={{
          borderColor: 'color-mix(in srgb, var(--color-risk-caution) 55%, transparent)',
          color: 'var(--color-risk-caution)',
          backgroundColor: 'color-mix(in srgb, var(--color-risk-caution) 12%, transparent)',
          boxShadow: '0 0 20px -6px color-mix(in srgb, var(--color-risk-caution) 60%, transparent)',
        }}
      >
        <WifiOff size={12} aria-hidden="true" />
        <motion.span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: 'var(--color-risk-caution)' }}
          animate={{ opacity: [1, 0.25, 1] }}
          transition={{ duration: 1.2, repeat: Infinity }}
        />
        Backend offline
      </motion.span>
    </Tooltip>
  )
}
