import { useMemo, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { Activity, Clock3, Gauge, ShieldCheck, Users } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'
import { PLANT_ZONES } from '../data/plantLayout'
import type { RiskLevel } from '../types'

/**
 * The command center's top telemetry rail: the "is everything okay?"
 * answer in one glance. Every value here is derived from real store
 * state (verdict, zone risk, worker positions), never a fabricated
 * sensor figure, so nothing on screen claims a measurement the system
 * doesn't actually have.
 */

const RISK_ORDER: Record<RiskLevel, number> = { SAFE: 0, CAUTION: 1, HIGH: 2, CRITICAL: 3 }
const RISK_LEVELS: RiskLevel[] = ['SAFE', 'CAUTION', 'HIGH', 'CRITICAL']

function Tile({
  eyebrow,
  Icon,
  children,
  accent,
  glow,
}: {
  eyebrow: string
  Icon: typeof Gauge
  children: ReactNode
  accent?: string
  glow?: boolean
}) {
  return (
    <div
      className="tactical-tile relative flex min-w-0 flex-1 flex-col justify-between gap-2 px-4 py-3"
      style={glow && accent ? { boxShadow: `0 0 0 1px ${accent}, 0 0 24px -6px ${accent}` } : undefined}
    >
      <div className="flex items-center gap-1.5 eyebrow">
        <Icon size={12} style={{ color: accent ?? 'var(--color-text-tertiary)' }} aria-hidden="true" />
        {eyebrow}
      </div>
      {children}
    </div>
  )
}

export function TelemetryStrip() {
  const verdict = useCorrixStore((s) => s.verdict)
  const zoneRisk = useCorrixStore((s) => s.zoneRisk)
  const workers = useCorrixStore((s) => s.workers)
  const connectionMode = useCorrixStore((s) => s.connectionMode)
  const councilStage = useCorrixStore((s) => s.councilStage)

  const distribution = useMemo(() => {
    const counts: Record<RiskLevel, number> = { SAFE: 0, CAUTION: 0, HIGH: 0, CRITICAL: 0 }
    for (const z of PLANT_ZONES) counts[zoneRisk[z.id] ?? 'SAFE']++
    return counts
  }, [zoneRisk])

  const elevated = distribution.HIGH + distribution.CRITICAL
  const occupiedZones = useMemo(() => new Set(workers.map((w) => w.zoneId)).size, [workers])

  const topRisk: RiskLevel = useMemo(() => {
    let top: RiskLevel = 'SAFE'
    for (const z of PLANT_ZONES) {
      const lvl = zoneRisk[z.id] ?? 'SAFE'
      if (RISK_ORDER[lvl] > RISK_ORDER[top]) top = lvl
    }
    return top
  }, [zoneRisk])

  const riskLevel = verdict?.riskLevel ?? topRisk
  const riskColor = `var(--color-risk-${riskLevel.toLowerCase()})`
  const isElevated = RISK_ORDER[riskLevel] >= 2

  const ttc = verdict?.timeToCritical

  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-5">
      {/* Compound risk */}
      <Tile eyebrow="Compound Risk" Icon={ShieldCheck} accent={riskColor} glow={isElevated}>
        <div className="flex items-baseline gap-2">
          <motion.span
            key={riskLevel}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="font-display text-2xl font-semibold leading-none"
            style={{ color: isElevated ? riskColor : 'var(--color-text-primary)' }}
          >
            {isElevated ? riskLevel : 'NOMINAL'}
          </motion.span>
          {verdict?.compoundFlag && (
            <span
              className="rounded-[var(--radius-sharp)] px-1.5 py-0.5 eyebrow"
              style={{ color: riskColor, backgroundColor: `color-mix(in srgb, ${riskColor} 16%, transparent)` }}
            >
              compound
            </span>
          )}
        </div>
        <span className="tnum text-[11px] text-[var(--color-text-tertiary)]">
          {verdict
            ? `zone ${verdict.zoneId}`
            : isElevated
              ? `${elevated} zone${elevated === 1 ? '' : 's'} above threshold`
              : 'all zones within limits'}
        </span>
      </Tile>

      {/* Time to critical */}
      <Tile eyebrow="Time to Critical" Icon={Clock3} accent={ttc ? riskColor : undefined}>
        <div className="flex items-baseline gap-1">
          <span
            className="tnum text-2xl font-semibold leading-none"
            style={{ color: ttc ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)' }}
          >
            {ttc ? ttc.medianMinutes.toFixed(0) : '—'}
          </span>
          {ttc && <span className="eyebrow">min</span>}
        </div>
        <span className="tnum text-[11px] text-[var(--color-text-tertiary)]">
          {ttc
            ? `${ttc.iqrLowMinutes.toFixed(0)}–${ttc.iqrHighMinutes.toFixed(0)} IQR · ${Math.round(ttc.escalationProbability * 100)}% esc`
            : 'no active forecast'}
        </span>
      </Tile>

      {/* Confidence */}
      <Tile eyebrow="Council Confidence" Icon={Gauge} accent={verdict ? 'var(--color-accent)' : undefined}>
        <div className="flex items-baseline gap-1">
          <span
            className="tnum text-2xl font-semibold leading-none"
            style={{ color: verdict ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)' }}
          >
            {verdict ? Math.round(verdict.confidence * 100) : '—'}
          </span>
          {verdict && <span className="eyebrow">%</span>}
        </div>
        <div className="h-1 w-full overflow-hidden rounded-full bg-[var(--color-surface-3)]">
          <motion.div
            className="h-full rounded-full"
            style={{ backgroundColor: 'var(--color-accent)' }}
            initial={{ width: 0 }}
            animate={{ width: verdict ? `${Math.round(verdict.confidence * 100)}%` : '0%' }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          />
        </div>
      </Tile>

      {/* Workers */}
      <Tile eyebrow="Workers On Site" Icon={Users} accent="var(--color-accent)">
        <div className="flex items-baseline gap-1">
          <span className="tnum text-2xl font-semibold leading-none text-[var(--color-text-primary)]">
            {workers.length}
          </span>
        </div>
        <span className="tnum text-[11px] text-[var(--color-text-tertiary)]">
          across {occupiedZones} zone{occupiedZones === 1 ? '' : 's'}
        </span>
      </Tile>

      {/* Zone status distribution */}
      <Tile
        eyebrow="Zone Status"
        Icon={Activity}
        accent={elevated > 0 ? 'var(--color-risk-high)' : undefined}
      >
        <div className="flex items-baseline gap-1">
          <span
            className="tnum text-2xl font-semibold leading-none"
            style={{ color: elevated > 0 ? 'var(--color-risk-high)' : 'var(--color-text-primary)' }}
          >
            {elevated}
          </span>
          <span className="eyebrow">/ {PLANT_ZONES.length} elevated</span>
        </div>
        <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-surface-3)]">
          {RISK_LEVELS.map((lvl) => {
            const count = distribution[lvl]
            if (count === 0) return null
            return (
              <motion.div
                key={lvl}
                layout
                className="h-full"
                style={{
                  width: `${(count / PLANT_ZONES.length) * 100}%`,
                  backgroundColor:
                    lvl === 'SAFE' ? 'var(--color-text-tertiary)' : `var(--color-risk-${lvl.toLowerCase()})`,
                  opacity: lvl === 'SAFE' ? 0.5 : 1,
                }}
              />
            )
          })}
        </div>
      </Tile>

      {/* Hide the 5th tile visually paired: keep grid clean. A system status
          mini-line sits under the strip via connectionMode/council below. */}
      <div className="col-span-2 flex items-center gap-4 px-1 md:col-span-3 xl:col-span-5">
        <span className="flex items-center gap-1.5 eyebrow">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: connectionMode === 'live' ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }}
          />
          {connectionMode === 'live' ? 'Link live' : 'Mock data'}
        </span>
        <span className="eyebrow text-[var(--color-text-tertiary)]">
          Council: {councilStage.replace('_', ' ')}
        </span>
      </div>
    </div>
  )
}
