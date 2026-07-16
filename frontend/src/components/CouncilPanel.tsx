import { useState } from 'react'
import { Camera, Clock, FileCheck, Gauge, Gavel } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'
import { RiskBadge } from './RiskBadge'
import type { CouncilAgentKey } from '../types'

const AGENTS: { key: CouncilAgentKey; label: string; Icon: typeof Gauge }[] = [
  { key: 'processSafetyEngineer', label: 'Process Safety Engineer', Icon: Gauge },
  { key: 'permitControlOfficer', label: 'Permit Control Officer', Icon: FileCheck },
  { key: 'shiftOperations', label: 'Shift Operations', Icon: Clock },
  { key: 'siteSafetyObserver', label: 'Site Safety Observer', Icon: Camera },
]

const STAGE_LABEL: Record<string, string> = {
  idle: 'Standing by',
  convening: 'Council convening…',
  deliberating: 'Awaiting Safety Officer input…',
  verdict_reached: 'Verdict reached',
}

export function CouncilPanel() {
  const verdict = useCorrixStore((s) => s.verdict)
  const councilStage = useCorrixStore((s) => s.councilStage)
  const overridePaused = useCorrixStore((s) => s.overridePaused)
  const submitOverrideNote = useCorrixStore((s) => s.submitOverrideNote)
  const liveEvidence = useCorrixStore((s) => s.liveEvidence)
  const connectionMode = useCorrixStore((s) => s.connectionMode)
  const [noteText, setNoteText] = useState('')

  return (
    <section className="glass-panel flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text-primary)]">
          Safety Council
        </h2>
        <span className="text-xs text-[var(--color-text-secondary)]">
          {STAGE_LABEL[councilStage]}
        </span>
      </div>

      <div className="grid grid-cols-5 gap-2">
        {AGENTS.map((agent) => (
          <div
            key={agent.key}
            className="flex flex-col items-center gap-1 rounded-[var(--radius-control)] bg-white/[0.03] py-3"
            title={agent.label}
          >
            <agent.Icon
              size={20}
              className={
                councilStage === 'convening'
                  ? 'animate-pulse text-[var(--color-accent)]'
                  : 'text-[var(--color-text-secondary)]'
              }
              aria-hidden="true"
            />
            <span className="text-center text-[10px] leading-tight text-[var(--color-text-secondary)]">
              {agent.label}
            </span>
          </div>
        ))}
        <div
          className="flex flex-col items-center gap-1 rounded-[var(--radius-control)] py-3"
          style={{ backgroundColor: 'color-mix(in srgb, var(--color-accent) 12%, transparent)' }}
          title="Chair"
        >
          <Gavel size={20} className="text-[var(--color-accent)]" aria-hidden="true" />
          <span className="text-center text-[10px] leading-tight text-[var(--color-accent)]">
            Chair
          </span>
        </div>
      </div>

      {!verdict && liveEvidence && (
        <div className="flex flex-col gap-2 rounded-[var(--radius-control)] bg-white/[0.03] p-4">
          <ul className="flex flex-col gap-1.5 text-xs text-[var(--color-text-secondary)]">
            {AGENTS.map((agent) => (
              <li key={agent.key} className="flex gap-2">
                <agent.Icon size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
                <span>{liveEvidence[agent.key]}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {verdict && (
        <div className="flex flex-col gap-3 rounded-[var(--radius-control)] bg-white/[0.03] p-4">
          <div className="flex items-center justify-between">
            <RiskBadge level={verdict.riskLevel} size="lg" />
            <span className="font-mono-data text-xs text-[var(--color-text-secondary)]">
              confidence {Math.round(verdict.confidence * 100)}%
            </span>
          </div>

          <ul className="flex flex-col gap-1.5 text-xs text-[var(--color-text-secondary)]">
            {AGENTS.map((agent) => (
              <li key={agent.key} className="flex gap-2">
                <agent.Icon size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
                <span>{verdict.council[agent.key]}</span>
              </li>
            ))}
          </ul>

          <p className="text-sm text-[var(--color-text-primary)]">{verdict.explanation}</p>

          <div className="flex items-center justify-between rounded-[var(--radius-control)] bg-white/[0.04] px-3 py-2 font-mono-data text-xs text-[var(--color-text-secondary)]">
            <span>Time to critical</span>
            <span className="text-[var(--color-text-primary)]">
              {verdict.timeToCritical.medianMinutes} min (
              {verdict.timeToCritical.iqrLowMinutes}–{verdict.timeToCritical.iqrHighMinutes} IQR) ·{' '}
              {Math.round(verdict.timeToCritical.escalationProbability * 100)}% escalation
            </span>
          </div>

          <p className="rounded-[var(--radius-control)] border-l-2 border-[var(--color-accent)] bg-white/[0.03] px-3 py-2 text-sm text-[var(--color-text-primary)]">
            {verdict.recommendedAction}
          </p>
        </div>
      )}

      {overridePaused && (
        <div className="flex flex-col gap-2 rounded-[var(--radius-control)] border border-[var(--color-accent)]/40 bg-white/[0.03] p-3">
          <p className="text-xs text-[var(--color-text-secondary)]">
            {connectionMode === 'live'
              ? 'Council deliberating. Add a note within the window to override, or it resolves automatically.'
              : 'Council paused. Add a note for the Chair before resuming.'}
          </p>
          <textarea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            rows={2}
            placeholder="e.g. Permit P-2291 was already suspended manually 5 minutes ago…"
            className="rounded-[var(--radius-control)] bg-white/[0.04] p-2 text-sm text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-secondary)]"
          />
          <button
            type="button"
            onClick={() => {
              submitOverrideNote(noteText)
              setNoteText('')
            }}
            disabled={!noteText.trim()}
            className="self-end rounded-[var(--radius-control)] px-3 py-1.5 text-xs font-medium text-[var(--color-accent)] disabled:opacity-40"
            style={{ backgroundColor: 'color-mix(in srgb, var(--color-accent) 18%, transparent)' }}
          >
            Resume Council
          </button>
        </div>
      )}
    </section>
  )
}
