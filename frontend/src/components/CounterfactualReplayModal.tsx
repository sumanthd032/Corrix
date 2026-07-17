import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
import { AlertTriangle, Loader2, X } from 'lucide-react'
import { RiskBadge } from './RiskBadge'
import type { RiskLevel } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const SCENARIOS = [
  { id: 'S1', label: 'S1: Anchor (Ladle Bay)' },
  { id: 'S2', label: 'S2: Confined Space' },
  { id: 'S3', label: 'S3: Maintenance / Gas' },
  { id: 'S4', label: 'S4: Hot Work / Gas' },
]

interface ReplayFrame {
  minute: number
  corrixRiskLevel: RiskLevel
  legacyRiskLevel: RiskLevel
}

interface ReplayTimeline {
  scenarioId: string
  seed: number
  zoneId: string
  corrixFirstEscalationMinute: number | null
  legacyFirstEscalationMinute: number | null
  frames: ReplayFrame[]
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'loaded'; timeline: ReplayTimeline }

export function CounterfactualReplayModal({ onClose }: { onClose: () => void }) {
  const [scenarioId, setScenarioId] = useState('S1')
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [frameIndex, setFrameIndex] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })
    fetch(`${API_BASE_URL}/api/replay/${scenarioId}`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(body.detail ?? `HTTP ${res.status}`)
        }
        return res.json() as Promise<ReplayTimeline>
      })
      .then((timeline) => {
        if (cancelled) return
        setState({ status: 'loaded', timeline })
        setFrameIndex(0)
      })
      .catch((err: Error) => {
        if (!cancelled) setState({ status: 'error', message: err.message })
      })
    return () => {
      cancelled = true
    }
  }, [scenarioId])

  const frame = useMemo(() => {
    if (state.status !== 'loaded') return null
    return state.timeline.frames[frameIndex] ?? null
  }, [state, frameIndex])

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
          <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text-primary)]">
            Counterfactual Replay
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[var(--radius-control)] p-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
            aria-label="Close"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <label className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
          Scenario
          <select
            value={scenarioId}
            onChange={(e) => setScenarioId(e.target.value)}
            className="glass-panel rounded-[var(--radius-control)] border-0 bg-transparent px-2 py-1 text-[var(--color-text-primary)] outline-none"
          >
            {SCENARIOS.map((s) => (
              <option key={s.id} value={s.id} className="bg-[var(--color-base)]">
                {s.label}
              </option>
            ))}
          </select>
        </label>

        {state.status === 'loading' && (
          <div className="flex flex-col items-center gap-2 py-16 text-[var(--color-text-secondary)]">
            <Loader2 size={20} className="animate-spin" aria-hidden="true" />
            <p className="text-sm">Loading replay timeline…</p>
          </div>
        )}

        {state.status === 'error' && (
          <div className="flex flex-col items-center gap-2 py-16 text-center text-[var(--color-text-secondary)]">
            <AlertTriangle size={20} className="text-[var(--color-risk-caution)]" aria-hidden="true" />
            <p className="text-sm">{state.message}</p>
          </div>
        )}

        {state.status === 'loaded' && frame && (
          <>
            <p className="font-mono-data text-[10px] text-[var(--color-text-secondary)]">
              Zone {state.timeline.zoneId} · seed {state.timeline.seed} ·{' '}
              {state.timeline.corrixFirstEscalationMinute !== null &&
              state.timeline.legacyFirstEscalationMinute !== null
                ? state.timeline.corrixFirstEscalationMinute < state.timeline.legacyFirstEscalationMinute
                  ? `Corrix caught this ${(
                      state.timeline.legacyFirstEscalationMinute -
                      state.timeline.corrixFirstEscalationMinute
                    ).toFixed(0)} minute(s) earlier than a legacy, single-signal system would have`
                  : 'Corrix and a legacy system escalate at the same moment for this scenario'
                : 'Neither path escalates in this window'}
            </p>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col items-center gap-2 rounded-[var(--radius-control)] bg-white/[0.03] p-4">
                <h3 className="text-xs font-semibold text-[var(--color-text-secondary)]">
                  Legacy (single-signal only)
                </h3>
                <RiskBadge level={frame.legacyRiskLevel} size="lg" />
              </div>
              <div
                className="flex flex-col items-center gap-2 rounded-[var(--radius-control)] p-4"
                style={{ backgroundColor: 'color-mix(in srgb, var(--color-accent) 10%, transparent)' }}
              >
                <h3 className="text-xs font-semibold text-[var(--color-accent)]">Corrix (compound-aware)</h3>
                <RiskBadge level={frame.corrixRiskLevel} size="lg" />
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <input
                type="range"
                min={0}
                max={state.timeline.frames.length - 1}
                value={frameIndex}
                onChange={(e) => setFrameIndex(Number(e.target.value))}
                className="w-full accent-[var(--color-accent)]"
              />
              <p className="text-center font-mono-data text-xs text-[var(--color-text-secondary)]">
                minute {frame.minute.toFixed(0)} of{' '}
                {state.timeline.frames[state.timeline.frames.length - 1].minute.toFixed(0)}
              </p>
            </div>
          </>
        )}
      </motion.div>
    </motion.div>,
    document.body,
  )
}
