import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
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

interface MemoryLoopReport {
  before: PipelineMetrics
  after: PipelineMetrics
  nExemplarsStored: number
  falseNegativeRateChange: number | null
}

interface SwatTagFit {
  tag: string
  nSamples?: number
  meanReversionRate: number
  noiseToSignalRatio: number
  residualSkew: number
  residualKurtosis: number
}

interface SwatValidation {
  swatTags: SwatTagFit[]
  ourSimulatorConfigs: SwatTagFit[]
  swatNoiseToSignalRange: [number, number]
  ourNoiseToSignalRange: [number, number]
  ourNoiseToSignalFallsWithinSwatRange: boolean
}

interface EvaluationReport {
  generatedAt: string
  baseline: PipelineMetrics
  pipeline: PipelineMetrics
  calibrationBins: CalibrationBin[]
  memoryLoop: MemoryLoopReport | null
  swatValidation: SwatValidation | null
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'loaded'; report: EvaluationReport }

function pct(value: number | null): string {
  return value === null ? 'N/A' : `${Math.round(value * 100)}%`
}

function minutes(value: number | null): string {
  return value === null ? 'N/A' : `${value.toFixed(1)} min`
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

function MemoryLoopSection({ memoryLoop }: { memoryLoop: MemoryLoopReport }) {
  const { before, after, nExemplarsStored, falseNegativeRateChange } = memoryLoop
  const improved = falseNegativeRateChange !== null && falseNegativeRateChange < 0
  return (
    <div className="flex flex-col gap-3 rounded-[var(--radius-control)] bg-white/[0.03] p-4">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
        Self-improving memory loop (held-out only)
      </h3>
      <p className="text-xs text-[var(--color-text-secondary)]">
        {nExemplarsStored} exemplar(s) stored from population-split misses. False-negative rate
        on scenarios the memory loop never saw:{' '}
        <span className="font-mono-data text-[var(--color-text-primary)]">
          {pct(before.falseNegativeRate)} → {pct(after.falseNegativeRate)}
        </span>{' '}
        <span
          style={{
            color: improved ? '#33c98b' : 'var(--color-risk-caution)',
          }}
        >
          ({improved ? 'improved' : 'no improvement'})
        </span>
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <MetricsCard title="Before (no exemplars)" metrics={before} />
        <MetricsCard title="After (retrieval trigger active)" metrics={after} />
      </div>
      <p className="text-[10px] text-[var(--color-text-secondary)]">
        The retrieval trigger carries a real, disclosed false-positive risk on some negative
        controls whose own noise happens to resemble a stored exemplar. This shows up above as a
        higher false-positive rate after population, not hidden.
      </p>
    </div>
  )
}

function SwatValidationSection({ swat }: { swat: SwatValidation }) {
  return (
    <div className="flex flex-col gap-3 rounded-[var(--radius-control)] bg-white/[0.03] p-4">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
        External validation against SWaT (real industrial dataset)
      </h3>
      <p className="text-xs text-[var(--color-text-secondary)]">
        Noise-to-signal ratio range, SWaT (real):{' '}
        <span className="font-mono-data text-[var(--color-text-primary)]">
          {swat.swatNoiseToSignalRange[0].toFixed(3)}–{swat.swatNoiseToSignalRange[1].toFixed(3)}
        </span>{' '}
        · ours:{' '}
        <span className="font-mono-data text-[var(--color-text-primary)]">
          {swat.ourNoiseToSignalRange[0].toFixed(3)}–{swat.ourNoiseToSignalRange[1].toFixed(3)}
        </span>{' '}
        <span style={{ color: swat.ourNoiseToSignalFallsWithinSwatRange ? '#33c98b' : 'var(--color-risk-caution)' }}>
          ({swat.ourNoiseToSignalFallsWithinSwatRange ? 'within range' : 'outside range'})
        </span>
      </p>
      <div className="overflow-x-auto">
        <table className="w-full font-mono-data text-[11px]">
          <thead>
            <tr className="text-left text-[var(--color-text-secondary)]">
              <th className="pr-3 pb-1">Source</th>
              <th className="pr-3 pb-1">k' /min</th>
              <th className="pr-3 pb-1">noise/signal</th>
              <th className="pr-3 pb-1">skew</th>
              <th className="pb-1">kurtosis</th>
            </tr>
          </thead>
          <tbody className="text-[var(--color-text-primary)]">
            {swat.swatTags.map((t) => (
              <tr key={`swat-${t.tag}`}>
                <td className="pr-3">SWaT {t.tag}</td>
                <td className="pr-3">{t.meanReversionRate.toFixed(4)}</td>
                <td className="pr-3">{t.noiseToSignalRatio.toFixed(4)}</td>
                <td className="pr-3">{t.residualSkew.toFixed(2)}</td>
                <td>{t.residualKurtosis.toFixed(1)}</td>
              </tr>
            ))}
            {swat.ourSimulatorConfigs.map((t) => (
              <tr key={`ours-${t.tag}`} className="text-[var(--color-accent)]">
                <td className="pr-3">Ours: {t.tag}</td>
                <td className="pr-3">{t.meanReversionRate.toFixed(4)}</td>
                <td className="pr-3">{t.noiseToSignalRatio.toFixed(4)}</td>
                <td className="pr-3">{t.residualSkew.toFixed(2)}</td>
                <td>{t.residualKurtosis.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[10px] text-[var(--color-text-secondary)]">
        Real, disclosed limitation: SWaT's residual kurtosis is far higher than ours. Real
        industrial sensors show heavy-tailed spikes (likely actuator switching), while our OU
        process produces genuinely Gaussian noise. This validates the noise-to-signal scale, not
        the tail shape.
      </p>
    </div>
  )
}

/** A hand-rolled SVG reliability diagram. No charting library needed for
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
          <text x={size / 2} y={size - 6} textAnchor="middle" fontSize={9} fill="#93a6bb">
            predicted confidence
          </text>
          <text
            x={10} y={size / 2} textAnchor="middle" fontSize={9} fill="#93a6bb"
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
                stroke="#2dd4e8"
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
            {state.report.memoryLoop && <MemoryLoopSection memoryLoop={state.report.memoryLoop} />}
            {state.report.swatValidation && <SwatValidationSection swat={state.report.swatValidation} />}
          </>
        )}
      </motion.div>
    </motion.div>,
    document.body,
  )
}
