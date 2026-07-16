import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { AlertTriangle, Loader2, X } from 'lucide-react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

interface PipelineMetrics {
  pipeline: 'baseline' | 'pipeline'
  nSkipped: number
  nPositive: number
  nNegative: number
  truePositives: number
  falseNegatives: number
  falsePositives: number
  trueNegatives: number
  precision: number | null
  recall: number | null
  falseNegativeRate: number | null
  falsePositiveRate: number | null
  meanLeadTimeMinutes: number | null
}

interface CalibrationBin {
  binLow: number
  binHigh: number
  n: number
  meanPredictedConfidence: number | null
  empiricalAccuracy: number | null
}

interface EvaluationReport {
  generatedAt: string
  baseline: PipelineMetrics
  pipeline: PipelineMetrics
  calibrationBins: CalibrationBin[]
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'loaded'; report: EvaluationReport }

function pct(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

function minutes(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)} min`
}

function MetricsCard({ title, metrics }: { title: string; metrics: PipelineMetrics }) {
  return (
    <div className="flex flex-col gap-3 rounded-[var(--radius-control)] bg-white/[0.03] p-4">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">{title}</h3>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 font-mono-data text-xs">
        {[
          ['Precision', pct(metrics.precision)],
          ['Recall', pct(metrics.recall)],
          ['False-negative rate', pct(metrics.falseNegativeRate)],
          ['False-positive rate', pct(metrics.falsePositiveRate)],
          ['Mean lead time', minutes(metrics.meanLeadTimeMinutes)],
          ['Skipped (quota)', String(metrics.nSkipped)],
        ].map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-2">
            <dt className="text-[var(--color-text-secondary)]">{label}</dt>
            <dd className="text-[var(--color-text-primary)]">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="font-mono-data text-[10px] text-[var(--color-text-secondary)]">
        {metrics.truePositives} TP · {metrics.falseNegatives} FN · {metrics.falsePositives} FP ·{' '}
        {metrics.trueNegatives} TN (n={metrics.nPositive + metrics.nNegative})
      </p>
    </div>
  )
}

/** A hand-rolled SVG reliability diagram — no charting library needed for
 * one scatter plot against a reference diagonal. Point radius scales with
 * the bin's sample count so a bin with n=1 doesn't visually overstate a
 * bin with n=8. */
function ReliabilityDiagram({ bins }: { bins: CalibrationBin[] }) {
  const scored = bins.filter((b) => b.n > 0)
  const size = 260
  const pad = 28
  const plot = size - pad * 2
  const toX = (v: number) => pad + v * plot
  const toY = (v: number) => size - pad - v * plot
  const maxN = Math.max(1, ...scored.map((b) => b.n))

  return (
    <div className="flex flex-col gap-2 rounded-[var(--radius-control)] bg-white/[0.03] p-4">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
        Confidence calibration (held-out only)
      </h3>
      {scored.length === 0 ? (
        <p className="py-8 text-center text-xs text-[var(--color-text-secondary)]">
          No held-out verdicts with a stated confidence yet.
        </p>
      ) : (
        <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[320px] self-center">
          <line
            x1={toX(0)} y1={toY(0)} x2={toX(1)} y2={toY(1)}
            stroke="rgba(234,241,247,0.25)" strokeWidth={1} strokeDasharray="4 4"
          />
          <line x1={pad} y1={size - pad} x2={size - pad} y2={size - pad} stroke="rgba(234,241,247,0.3)" strokeWidth={1} />
          <line x1={pad} y1={pad} x2={pad} y2={size - pad} stroke="rgba(234,241,247,0.3)" strokeWidth={1} />
          <text x={size / 2} y={size - 6} textAnchor="middle" fontSize={9} fill="#8fa3b8">
            predicted confidence
          </text>
          <text
            x={10} y={size / 2} textAnchor="middle" fontSize={9} fill="#8fa3b8"
            transform={`rotate(-90 10 ${size / 2})`}
          >
            empirical accuracy
          </text>
          {scored.map((b) => {
            const x = toX(b.meanPredictedConfidence ?? 0)
            const y = toY(b.empiricalAccuracy ?? 0)
            const r = 3 + 5 * (b.n / maxN)
            return (
              <circle
                key={b.binLow}
                cx={x} cy={y} r={r}
                fill="rgba(0,180,216,0.75)"
                stroke="#00b4d8"
              >
                <title>
                  [{b.binLow.toFixed(1)}-{b.binHigh.toFixed(1)}) · n={b.n} · accuracy{' '}
                  {pct(b.empiricalAccuracy)}
                </title>
              </circle>
            )
          })}
        </svg>
      )}
      <p className="text-center text-[10px] text-[var(--color-text-secondary)]">
        Dot size reflects sample count per bin · dashed line is perfect calibration
      </p>
    </div>
  )
}

export function EvaluationReportModal({ onClose }: { onClose: () => void }) {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE_URL}/api/evaluation/report`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(body.detail ?? `HTTP ${res.status}`)
        }
        return res.json() as Promise<EvaluationReport>
      })
      .then((report) => {
        if (!cancelled) setState({ status: 'loaded', report })
      })
      .catch((err: Error) => {
        if (!cancelled) setState({ status: 'error', message: err.message })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="glass-panel flex max-h-[85vh] w-full max-w-2xl flex-col gap-4 overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text-primary)]">
            Evaluation Report
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

        {state.status === 'loading' && (
          <div className="flex flex-col items-center gap-2 py-16 text-[var(--color-text-secondary)]">
            <Loader2 size={20} className="animate-spin" aria-hidden="true" />
            <p className="text-sm">Loading evaluation results…</p>
          </div>
        )}

        {state.status === 'error' && (
          <div className="flex flex-col items-center gap-2 py-16 text-center text-[var(--color-text-secondary)]">
            <AlertTriangle size={20} className="text-[var(--color-risk-caution)]" aria-hidden="true" />
            <p className="text-sm">{state.message}</p>
          </div>
        )}

        {state.status === 'loaded' && (
          <>
            <p className="font-mono-data text-[10px] text-[var(--color-text-secondary)]">
              Generated {new Date(state.report.generatedAt).toLocaleString()} · full scenario
              library (S1–S5 + negative controls)
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <MetricsCard title="Baseline (rule/threshold only)" metrics={state.report.baseline} />
              <MetricsCard title="Full pipeline (+ novelty, real Council)" metrics={state.report.pipeline} />
            </div>
            <ReliabilityDiagram bins={state.report.calibrationBins} />
          </>
        )}
      </div>
    </div>,
    document.body,
  )
}
