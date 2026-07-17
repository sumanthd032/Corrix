import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { BarChart3, CircleAlert, Download, Loader2, PauseCircle, Radio, ShieldAlert, Sparkles } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'
import { CounterfactualReplayModal } from './CounterfactualReplayModal'
import { EvaluationReportModal } from './EvaluationReportModal'

const BUTTON_MOTION = {
  whileHover: { y: -1, transition: { duration: 0.15 } },
  whileTap: { scale: 0.96 },
}

const SCENARIOS = [
  { id: 'S1', label: 'S1: Anchor (Ladle Bay)' },
  { id: 'S2', label: 'S2: Confined Space' },
  { id: 'S3', label: 'S3: Maintenance / Gas' },
  { id: 'S4', label: 'S4: Hot Work / Gas' },
  { id: 'S5', label: 'S5: Silent Drift (Near-Miss)' },
]

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type ReportRequestState = 'idle' | 'loading' | 'error'

export function TopControlBar() {
  const scenarioId = useCorrixStore((s) => s.scenarioId)
  const setScenario = useCorrixStore((s) => s.setScenario)
  const overridePaused = useCorrixStore((s) => s.overridePaused)
  const pauseForOverride = useCorrixStore((s) => s.pauseForOverride)
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
      className="glass-panel flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3"
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
    >
      <div className="flex items-center gap-2 pr-4 border-r border-white/10">
        <span
          className="h-2 w-2 rounded-full animate-pulse"
          style={{ backgroundColor: 'var(--color-accent)' }}
          aria-hidden="true"
        />
        <h1 className="text-lg tracking-tight text-[var(--color-text-primary)]">Corrix</h1>
      </div>

      <label className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
        Scenario
        <select
          value={scenarioId}
          onChange={(e) => setScenario(e.target.value)}
          className="glass-panel rounded-[var(--radius-control)] border-0 bg-transparent px-2 py-1 text-[var(--color-text-primary)] outline-none"
        >
          {SCENARIOS.map((s) => (
            <option key={s.id} value={s.id} className="bg-[var(--color-base)]">
              {s.label}
            </option>
          ))}
        </select>
      </label>

      <motion.button
        {...BUTTON_MOTION}
        type="button"
        onClick={() => setReplayOpen(true)}
        className="flex items-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
      >
        <Radio size={15} aria-hidden="true" />
        Counterfactual Replay
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
        className="flex items-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors disabled:opacity-40"
      >
        <Sparkles size={15} aria-hidden="true" />
        Open Challenge
        {openChallengeLabel && (
          <span className="ml-1 max-w-[220px] truncate font-mono-data text-[10px] text-[var(--color-accent)]">
            {openChallengeLabel}
          </span>
        )}
      </motion.button>

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <motion.button
          {...BUTTON_MOTION}
          type="button"
          onClick={() => setReportOpen(true)}
          className="flex items-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
        >
          <BarChart3 size={15} aria-hidden="true" />
          Evaluation Report
        </motion.button>

        <motion.button
          {...BUTTON_MOTION}
          type="button"
          onClick={downloadIncidentReport}
          disabled={!verdict || incidentReportState === 'loading'}
          title={!verdict ? 'No verdict available yet to report on' : 'Download a PDF incident report for the current verdict'}
          className="flex items-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors disabled:opacity-40"
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
          className="flex items-center gap-1.5 text-xs"
          style={{
            color: eroFired
              ? eroFired.deliveredOk
                ? 'var(--color-accent)'
                : 'var(--color-risk-critical)'
              : 'var(--color-text-secondary)',
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
              ? `ERO fired: Zone ${eroFired.zoneId}`
              : `ERO fired: Zone ${eroFired.zoneId} (delivery failed)`
            : 'ERO idle'}
        </motion.span>

        <motion.button
          {...BUTTON_MOTION}
          type="button"
          onClick={pauseForOverride}
          disabled={overridePaused || councilStage !== 'verdict_reached'}
          className="flex items-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-40"
          style={{
            backgroundColor: 'color-mix(in srgb, var(--color-accent) 18%, transparent)',
            color: 'var(--color-accent)',
          }}
        >
          <PauseCircle size={15} aria-hidden="true" />
          Safety Officer Override
        </motion.button>
      </div>

      <AnimatePresence>
        {reportOpen && <EvaluationReportModal onClose={() => setReportOpen(false)} />}
        {replayOpen && <CounterfactualReplayModal onClose={() => setReplayOpen(false)} />}
      </AnimatePresence>
    </motion.header>
  )
}
