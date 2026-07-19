import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  BarChart3,
  ChevronDown,
  CircleAlert,
  Download,
  Loader2,
  PauseCircle,
  Radio,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'
import { CounterfactualReplayModal } from './CounterfactualReplayModal'
import { EvaluationReportModal } from './EvaluationReportModal'

const BUTTON_MOTION = {
  whileHover: { y: -1, transition: { duration: 0.15 } },
  whileTap: { scale: 0.96 },
}

const SCENARIOS = [
  { id: 'S1', label: 'S1 · Anchor (Ladle Bay)' },
  { id: 'S2', label: 'S2 · Confined Space' },
  { id: 'S3', label: 'S3 · Maintenance / Gas' },
  { id: 'S4', label: 'S4 · Hot Work / Gas' },
  { id: 'S5', label: 'S5 · Silent Drift (Near-Miss)' },
]

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type ReportRequestState = 'idle' | 'loading' | 'error'

/** Shared tactical action-chip styling: bordered, graphite, cyan on hover. */
const chipClass =
  'flex items-center gap-1.5 rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-3 py-1.5 text-sm text-[var(--color-text-secondary)] transition-colors hover:border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] hover:text-[var(--color-text-primary)] disabled:opacity-40 disabled:hover:border-[var(--color-hairline)]'

export function TopControlBar() {
  const scenarioId = useCorrixStore((s) => s.scenarioId)
  const setScenario = useCorrixStore((s) => s.setScenario)
  const overridePaused = useCorrixStore((s) => s.overridePaused)
  const pauseForOverride = useCorrixStore((s) => s.pauseForOverride)
  const requestOverrideFocus = useCorrixStore((s) => s.requestOverrideFocus)
  const councilStage = useCorrixStore((s) => s.councilStage)
  const connectionMode = useCorrixStore((s) => s.connectionMode)
  const triggerOpenChallenge = useCorrixStore((s) => s.triggerOpenChallenge)
  const openChallengeLabel = useCorrixStore((s) => s.openChallengeLabel)
  const eroFired = useCorrixStore((s) => s.eroFired)
  const verdict = useCorrixStore((s) => s.verdict)
  const [reportOpen, setReportOpen] = useState(false)
  const [replayOpen, setReplayOpen] = useState(false)
  const [incidentReportState, setIncidentReportState] = useState<ReportRequestState>('idle')

  const downloadIncidentReport = async () => {
    if (!verdict || incidentReportState === 'loading') return
    setIncidentReportState('loading')
    try {
      const response = await fetch(`${API_BASE_URL}/api/incident-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          verdict,
          eroAlert: eroFired && eroFired.zoneId === verdict.zoneId ? eroFired : null,
        }),
      })
      if (!response.ok) throw new Error(`Report request failed (${response.status})`)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `corrix-incident-report-${verdict.zoneId}.pdf`
      link.click()
      URL.revokeObjectURL(url)
      setIncidentReportState('idle')
    } catch {
      setIncidentReportState('error')
      setTimeout(() => setIncidentReportState('idle'), 4000)
    }
  }

  return (
    <motion.header
      className="glass-panel flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5"
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
    >
      {/* Wordmark + live status */}
      <div className="flex items-center gap-3 pr-3">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-6 w-6 items-center justify-center">
            <span
              className="absolute inset-0 rounded-[var(--radius-sharp)] border"
              style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 55%, transparent)' }}
              aria-hidden="true"
            />
            <span
              className="h-2 w-2 rounded-full animate-pulse"
              style={{ backgroundColor: 'var(--color-accent)', boxShadow: 'var(--shadow-glow-accent)' }}
              aria-hidden="true"
            />
          </span>
          <div className="flex flex-col leading-none">
            <h1 className="font-display text-base font-semibold tracking-[0.14em] text-[var(--color-text-primary)]">
              CORRIX
            </h1>
            <span className="eyebrow mt-0.5">Compound Risk Ops</span>
          </div>
        </div>
        <span
          className="flex items-center gap-1.5 rounded-[var(--radius-sharp)] border px-2 py-1 eyebrow"
          style={{
            borderColor:
              connectionMode === 'live'
                ? 'color-mix(in srgb, var(--color-accent) 45%, transparent)'
                : 'var(--color-hairline)',
            color: connectionMode === 'live' ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
          }}
          title={
            connectionMode === 'live'
              ? 'Connected to the live backend: real scenario stream and Safety Council'
              : 'Backend unreachable, showing mock data'
          }
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: connectionMode === 'live' ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }}
          />
          {connectionMode === 'live' ? 'LIVE' : 'MOCK'}
        </span>
      </div>

      {/* Scenario selector */}
      <div className="relative flex items-center">
        <span className="eyebrow mr-2 hidden sm:inline">Scenario</span>
        <div className="relative">
          <select
            value={scenarioId}
            onChange={(e) => setScenario(e.target.value)}
            className="appearance-none rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] py-1.5 pl-3 pr-8 font-mono-data text-xs text-[var(--color-text-primary)] outline-none transition-colors hover:border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)]"
          >
            {SCENARIOS.map((s) => (
              <option key={s.id} value={s.id} className="bg-[var(--color-base)] font-mono-data">
                {s.label}
              </option>
            ))}
          </select>
          <ChevronDown
            size={14}
            className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)]"
            aria-hidden="true"
          />
        </div>
      </div>

      <motion.button {...BUTTON_MOTION} type="button" onClick={() => setReplayOpen(true)} className={chipClass}>
        <Radio size={15} aria-hidden="true" />
        Replay
      </motion.button>

      <motion.button
        {...BUTTON_MOTION}
        type="button"
        onClick={triggerOpenChallenge}
        disabled={connectionMode !== 'live'}
        title={
          connectionMode !== 'live'
            ? 'Requires the live backend, which draws and runs an unscripted evidence combination live'
            : 'Draw one of the curated Open Challenge combinations and run it live'
        }
        className={chipClass}
      >
        <Sparkles size={15} aria-hidden="true" />
        Open Challenge
        {openChallengeLabel && (
          <span className="ml-1 max-w-[180px] truncate font-mono-data text-[10px] text-[var(--color-accent)]">
            {openChallengeLabel}
          </span>
        )}
      </motion.button>

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <motion.button {...BUTTON_MOTION} type="button" onClick={() => setReportOpen(true)} className={chipClass}>
          <BarChart3 size={15} aria-hidden="true" />
          Evaluation
        </motion.button>

        <motion.button
          {...BUTTON_MOTION}
          type="button"
          onClick={downloadIncidentReport}
          disabled={!verdict || incidentReportState === 'loading'}
          title={!verdict ? 'No verdict available yet to report on' : 'Download a PDF incident report for the current verdict'}
          className={chipClass}
        >
          {incidentReportState === 'loading' ? (
            <Loader2 size={15} className="animate-spin" aria-hidden="true" />
          ) : incidentReportState === 'error' ? (
            <CircleAlert size={15} style={{ color: 'var(--color-risk-critical)' }} aria-hidden="true" />
          ) : (
            <Download size={15} aria-hidden="true" />
          )}
          {incidentReportState === 'error' ? 'Report failed' : 'Incident Report'}
        </motion.button>

        <motion.span
          key={eroFired ? `${eroFired.zoneId}-${eroFired.deliveredOk}` : 'idle'}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          className="flex items-center gap-1.5 rounded-[var(--radius-control)] border px-2.5 py-1.5 text-xs"
          style={{
            borderColor: eroFired
              ? eroFired.deliveredOk
                ? 'color-mix(in srgb, var(--color-accent) 45%, transparent)'
                : 'color-mix(in srgb, var(--color-risk-critical) 55%, transparent)'
              : 'var(--color-hairline)',
            color: eroFired
              ? eroFired.deliveredOk
                ? 'var(--color-accent)'
                : 'var(--color-risk-critical)'
              : 'var(--color-text-tertiary)',
          }}
          title={
            eroFired
              ? `Evidence hash: ${eroFired.evidenceHash}\nFired at: ${eroFired.firedAt}`
              : 'No CRITICAL verdict has fired the Emergency Response Orchestrator yet'
          }
        >
          <ShieldAlert size={14} aria-hidden="true" />
          {eroFired
            ? eroFired.deliveredOk
              ? `ERO · Zone ${eroFired.zoneId}`
              : `ERO · Zone ${eroFired.zoneId} (failed)`
            : 'ERO idle'}
        </motion.span>

        <motion.button
          {...BUTTON_MOTION}
          type="button"
          onClick={connectionMode === 'live' ? requestOverrideFocus : pauseForOverride}
          disabled={
            connectionMode === 'live'
              ? councilStage !== 'deliberating'
              : overridePaused || councilStage !== 'verdict_reached'
          }
          title={
            connectionMode === 'live'
              ? councilStage === 'deliberating'
                ? 'Jump to the override note field while the Council is deliberating'
                : 'Available only while the Council is deliberating (the live override window)'
              : 'Add a Safety Officer note to the current verdict'
          }
          className="flex items-center gap-1.5 rounded-[var(--radius-control)] border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-40"
          style={{
            borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)',
            backgroundColor: 'var(--color-accent-dim)',
            color: 'var(--color-accent)',
          }}
        >
          <PauseCircle size={15} aria-hidden="true" />
          Override
        </motion.button>
      </div>

      <AnimatePresence>
        {reportOpen && <EvaluationReportModal onClose={() => setReportOpen(false)} />}
        {replayOpen && <CounterfactualReplayModal onClose={() => setReplayOpen(false)} />}
      </AnimatePresence>
    </motion.header>
  )
}
