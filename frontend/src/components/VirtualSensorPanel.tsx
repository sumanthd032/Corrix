import { useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronUp, Radio, ShieldCheck } from 'lucide-react'

/**
 * The Virtual Sensor Simulator's frontend half, per
 * CORRIX_REAL_DATA_BUILD_PLAN.md Step 21: the control surface that
 * replaces hardware in the pitch. Dragging a gas slider, toggling a
 * badge, or firing a permit button calls the real
 * POST /api/virtual-sensor/{factoryId}/{zoneId}/{gas|badge|permit}
 * endpoints (Step 19), which publish over a real MQTT broker (Step
 * 17) and tick toward the target with real OU jitter (Step 19),
 * consumed by the live-factory websocket (Step 18/20) exactly like
 * any other MQTT source. This panel only ever shows the target a user
 * set, not the jittered value actually published: that's what the
 * dashboard (TelemetryStrip/PlantHeatmap) is for.
 *
 * Reuses the same collapsible-drawer idiom as RegulatoryChatDrawer.tsx
 * for visual consistency, rather than inventing a new interaction
 * pattern. Reachable from the Live Command Center itself, not just the
 * wizard, per the build plan's own emphasis: "that's the actual demo
 * moment, not the wizard step."
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const DEBOUNCE_MS = 300

const GAS_TYPES = [
  { value: 'O2', label: 'O2', min: 0, max: 25, step: 0.1, unit: '%' },
  { value: 'CO', label: 'CO', min: 0, max: 200, step: 1, unit: 'ppm' },
  { value: 'H2S', label: 'H2S', min: 0, max: 100, step: 1, unit: 'ppm' },
  { value: 'LEL', label: 'LEL', min: 0, max: 100, step: 1, unit: '%' },
] as const

const PERMIT_TYPES = [
  { value: 'hot_work', label: 'Hot work' },
  { value: 'cold_work', label: 'Cold work' },
  { value: 'confined_space_entry', label: 'Confined space entry' },
  { value: 'lifting_operation', label: 'Lifting operation' },
  { value: 'electrical_isolation', label: 'Electrical isolation' },
] as const

export interface VirtualSensorZone {
  zone_id: string
  name: string
}

function postJson(path: string, body: unknown) {
  fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).catch(() => {
    // Best-effort: a dropped virtual-sensor request just means this one
    // touch didn't publish. The panel stays interactive either way.
  })
}

export function VirtualSensorPanel({ factoryId, zones }: { factoryId: string; zones: VirtualSensorZone[] }) {
  const [open, setOpen] = useState(false)
  const [activeZoneId, setActiveZoneId] = useState(zones[0]?.zone_id ?? '')
  const [gasTargets, setGasTargets] = useState<Record<string, number>>({})
  const [badgeId, setBadgeId] = useState('W-BG-001')
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  if (zones.length === 0) return null

  const onSliderChange = (gasType: string, value: number) => {
    const key = `${activeZoneId}-${gasType}`
    setGasTargets((prev) => ({ ...prev, [key]: value }))
    if (debounceTimers.current[key]) clearTimeout(debounceTimers.current[key])
    debounceTimers.current[key] = setTimeout(() => {
      postJson(`/api/virtual-sensor/${factoryId}/${activeZoneId}/gas`, {
        gas_type: gasType,
        target_concentration: value,
      })
    }, DEBOUNCE_MS)
  }

  const toggleBadge = (entering: boolean) => {
    postJson(`/api/virtual-sensor/${factoryId}/${activeZoneId}/badge`, { badge_id: badgeId, entering })
  }

  const firePermit = (permitType: string) => {
    postJson(`/api/virtual-sensor/${factoryId}/${activeZoneId}/permit`, { permit_type: permitType })
  }

  return (
    <motion.div
      className="glass-panel relative flex flex-col overflow-visible"
      animate={{ height: open ? 380 : 48 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
    >
      <motion.button
        type="button"
        onClick={() => setOpen((v) => !v)}
        whileHover={{ backgroundColor: 'color-mix(in srgb, var(--color-surface-3) 40%, transparent)' }}
        className="flex items-center gap-2 px-4 py-3 text-sm font-semibold text-[var(--color-text-primary)]"
      >
        <Radio size={15} className="text-[var(--color-accent)]" aria-hidden="true" />
        Virtual Sensor Panel
        <span className="eyebrow ml-2 hidden sm:inline">Simulated device · real MQTT protocol</span>
        <motion.span className="ml-auto" animate={{ rotate: open ? 0 : 180 }} transition={{ duration: 0.25 }}>
          <ChevronUp size={16} className="text-[var(--color-text-tertiary)]" aria-hidden="true" />
        </motion.span>
      </motion.button>

      {open && (
        <div className="thin-scroll flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 pb-4">
          <label className="block">
            <span className="text-[10px] text-[var(--color-text-tertiary)]">Zone</span>
            <select
              value={activeZoneId}
              onChange={(e) => setActiveZoneId(e.target.value)}
              className="mt-1 w-full rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-2 py-1.5 text-sm text-[var(--color-text-primary)] outline-none"
            >
              {zones.map((z) => (
                <option key={z.zone_id} value={z.zone_id}>
                  {z.zone_id} — {z.name}
                </option>
              ))}
            </select>
          </label>

          <div>
            <span className="eyebrow">Gas concentration targets</span>
            <div className="mt-1.5 grid grid-cols-2 gap-2.5">
              {GAS_TYPES.map((g) => {
                const key = `${activeZoneId}-${g.value}`
                const value = gasTargets[key] ?? 0
                return (
                  <div key={g.value} className="tactical-tile p-2.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-[var(--color-text-secondary)]">{g.label}</span>
                      <span className="tnum text-[var(--color-text-primary)]">
                        {value.toFixed(1)} {g.unit}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={g.min}
                      max={g.max}
                      step={g.step}
                      value={value}
                      onChange={(e) => onSliderChange(g.value, Number(e.target.value))}
                      className="mt-2 w-full accent-[var(--color-accent)]"
                    />
                  </div>
                )
              })}
            </div>
          </div>

          <div>
            <span className="eyebrow">Worker badge</span>
            <div className="mt-1.5 flex items-center gap-2">
              <input
                type="text"
                value={badgeId}
                onChange={(e) => setBadgeId(e.target.value)}
                className="flex-1 rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-2 py-1.5 text-sm text-[var(--color-text-primary)] outline-none"
              />
              <button
                type="button"
                onClick={() => toggleBadge(true)}
                className="rounded-[var(--radius-control)] border px-3 py-1.5 text-xs font-medium text-[var(--color-accent)]"
                style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
              >
                Enter zone
              </button>
              <button
                type="button"
                onClick={() => toggleBadge(false)}
                className="rounded-[var(--radius-control)] border px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)]"
                style={{ borderColor: 'var(--color-hairline)' }}
              >
                Exit zone
              </button>
            </div>
          </div>

          <div>
            <span className="eyebrow">Issue a permit</span>
            <div className="mt-1.5 flex flex-wrap gap-2">
              {PERMIT_TYPES.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => firePermit(p.value)}
                  className="flex items-center gap-1.5 rounded-[var(--radius-control)] border px-2.5 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
                  style={{ borderColor: 'var(--color-hairline)' }}
                >
                  <ShieldCheck size={12} aria-hidden="true" />
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </motion.div>
  )
}
