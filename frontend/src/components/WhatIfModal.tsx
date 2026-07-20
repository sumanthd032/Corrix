import { useState } from 'react'
import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Fan, Loader2, ShieldOff, Users, Wind, X } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

interface Ttc {
  medianMinutes: number
  iqrLowMinutes: number
  iqrHighMinutes: number
  escalationProbability: number
  horizonMinutes: number
}

interface WhatIfResult {
  available: boolean
  note?: string
  scenarioId?: string
  zoneId?: string
  intervention?: string
  label?: string
  before?: Ttc
  after?: Ttc
}

const INTERVENTIONS = [
  { id: 'isolate_source', label: 'Isolate the gas source', Icon: Wind },
  { id: 'increase_ventilation', label: 'Increase forced ventilation', Icon: Fan },
  { id: 'suspend_permit', label: 'Suspend the active permit', Icon: ShieldOff },
  { id: 'evacuate_zone', label: 'Evacuate the zone', Icon: Users },
]

type LoadState =
  | { status: 'idle' }
  | { status: 'loading'; intervention: string }
  | { status: 'error'; message: string }
  | { status: 'loaded'; result: WhatIfResult }

function TtcCard({ label, ttc, tone }: { label: string; ttc: Ttc; tone: 'before' | 'after' }) {
  const color = tone === 'after' ? 'var(--color-risk-safe)' : 'var(--color-risk-high)'
  return (
    <div className="flex-1 rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/50 p-4">
      <span className="eyebrow">{label}</span>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className="tnum text-3xl font-semibold" style={{ color }}>
          {ttc.medianMinutes.toFixed(0)}
        </span>
        <span className="eyebrow">min to critical</span>
      </div>
      <div className="mt-1 tnum text-[11px] text-[var(--color-text-tertiary)]">
        {ttc.iqrLowMinutes.toFixed(0)}–{ttc.iqrHighMinutes.toFixed(0)} IQR ·{' '}
        {Math.round(ttc.escalationProbability * 100)}% escalation
      </div>
    </div>
  )
}

export function WhatIfModal({ onClose }: { onClose: () => void }) {
  const scenarioId = useCorrixStore((s) => s.scenarioId)
  const [state, setState] = useState<LoadState>({ status: 'idle' })

  const run = async (intervention: string) => {
    setState({ status: 'loading', intervention })
    try {
      const res = await fetch(`${API_BASE_URL}/api/what-if`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId, intervention }),
      })
      if (!res.ok) throw new Error(`Request failed (${res.status})`)
      const result: WhatIfResult = await res.json()
      setState({ status: 'loaded', result })
    } catch {
      setState({
        status: 'error',
        message: 'Could not reach the backend to run the what-if. Confirm it is running and try again.',
      })
    }
  }

  const gained =
    state.status === 'loaded' && state.result.available && state.result.before && state.result.after
      ? state.result.after.medianMinutes - state.result.before.medianMinutes
      : 0

  return createPortal(
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
    >
      <motion.div
        className="glass-panel flex max-h-[85vh] w-full max-w-2xl flex-col gap-4 overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.94, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 8 }}
        transition={{ duration: 0.25, ease: 'easeOut' }}
      >
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text-primary)]">
              What-if Mitigation
            </h2>
            <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">
              Test an intervention on {scenarioId} and see the predicted change before acting. Source
              interventions re-run the real Monte Carlo forecaster.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[var(--radius-control)] p-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
            aria-label="Close"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {INTERVENTIONS.map(({ id, label, Icon }) => {
            const active = state.status === 'loaded' && state.result.intervention === id
            const loading = state.status === 'loading' && state.intervention === id
            return (
              <button
                key={id}
                type="button"
                onClick={() => run(id)}
                className="flex flex-col items-center gap-1.5 rounded-[var(--radius-control)] border p-3 text-center text-[11px] leading-tight transition-colors"
                style={{
                  borderColor: active
                    ? 'color-mix(in srgb, var(--color-accent) 55%, transparent)'
                    : 'var(--color-hairline)',
                  backgroundColor: active ? 'var(--color-accent-dim)' : 'var(--color-surface-2)',
                  color: active ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                }}
              >
                {loading ? (
                  <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                ) : (
                  <Icon size={16} aria-hidden="true" />
                )}
                {label}
              </button>
            )
          })}
        </div>

        {state.status === 'idle' && (
          <p className="rounded-[var(--radius-control)] border border-dashed border-[var(--color-hairline)] px-4 py-6 text-center text-xs text-[var(--color-text-tertiary)]">
            Pick an intervention above to forecast its effect.
          </p>
        )}

        {state.status === 'error' && (
          <p className="rounded-[var(--radius-control)] border border-[color-mix(in_srgb,var(--color-risk-critical)_45%,transparent)] px-4 py-3 text-xs text-[var(--color-risk-critical)]">
            {state.message}
          </p>
        )}

        {state.status === 'loaded' && !state.result.available && (
          <p className="rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/50 px-4 py-3 text-xs text-[var(--color-text-secondary)]">
            {state.result.note}
          </p>
        )}

        {state.status === 'loaded' && state.result.available && state.result.before && state.result.after && (
          <div className="flex flex-col gap-3">
            <div className="flex items-stretch gap-3">
              <TtcCard label="Now (no action)" ttc={state.result.before} tone="before" />
              <div className="flex flex-col items-center justify-center gap-1">
                <ArrowRight size={20} className="text-[var(--color-text-tertiary)]" aria-hidden="true" />
                {gained > 0.5 && (
                  <span className="tnum text-[11px] font-semibold text-[var(--color-risk-safe)]">
                    +{gained.toFixed(0)} min
                  </span>
                )}
              </div>
              <TtcCard label={`After: ${state.result.label}`} ttc={state.result.after} tone="after" />
            </div>
            <p className="rounded-[var(--radius-control)] border-l-2 border-[var(--color-accent)] bg-[var(--color-accent-dim)] px-3 py-2 text-sm leading-relaxed text-[var(--color-text-primary)]">
              {state.result.note}
            </p>
          </div>
        )}
      </motion.div>
    </motion.div>,
    document.body,
  )
}
