import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Camera, Clock, FileCheck, Gauge, Gavel, Scale } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'
import { RiskBadge } from './RiskBadge'
import { CouncilScene3D } from './CouncilScene3D'
import type { CouncilAgentKey, TriggerReason } from '../types'

const AGENTS: { key: CouncilAgentKey; label: string; short: string; Icon: typeof Gauge }[] = [
  { key: 'processSafetyEngineer', label: 'Process Safety Engineer', short: 'Process', Icon: Gauge },
  { key: 'permitControlOfficer', label: 'Permit Control Officer', short: 'Permit', Icon: FileCheck },
  { key: 'shiftOperations', label: 'Shift Operations', short: 'Shift', Icon: Clock },
  { key: 'siteSafetyObserver', label: 'Site Safety Observer', short: 'Observer', Icon: Camera },
]

const STAGE: Record<string, { label: string; color: string }> = {
  idle: { label: 'Standby', color: 'var(--color-text-tertiary)' },
  convening: { label: 'Convening', color: 'var(--color-accent)' },
  deliberating: { label: 'Deliberating', color: 'var(--color-risk-caution)' },
  verdict_reached: { label: 'Verdict', color: 'var(--color-accent)' },
}

const TRIGGER_LABEL: Record<TriggerReason, string> = {
  rule_threshold: 'Rule / Threshold',
  novelty: 'Novelty Detector',
  memory_retrieval: 'Memory Retrieval',
}

export function CouncilPanel() {
  const verdict = useCorrixStore((s) => s.verdict)
  const councilStage = useCorrixStore((s) => s.councilStage)
  const overridePaused = useCorrixStore((s) => s.overridePaused)
  const submitOverrideNote = useCorrixStore((s) => s.submitOverrideNote)
  const liveEvidence = useCorrixStore((s) => s.liveEvidence)
  const connectionMode = useCorrixStore((s) => s.connectionMode)
  const overrideFocusNonce = useCorrixStore((s) => s.overrideFocusNonce)
  const [noteText, setNoteText] = useState('')
  const noteRef = useRef<HTMLTextAreaElement>(null)

  // When the top-bar Override control is used in live mode, bring the note
  // field into view and focus it (the field itself lives here, in the
  // panel, and only during the deliberation window).
  useEffect(() => {
    if (overrideFocusNonce > 0 && noteRef.current) {
      noteRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
      noteRef.current.focus()
    }
  }, [overrideFocusNonce])

  const stage = STAGE[councilStage] ?? STAGE.idle
  const isActive = councilStage === 'convening' || councilStage === 'deliberating'

  return (
    <section className="glass-panel corner-frame flex flex-col gap-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Gavel size={15} className="text-[var(--color-accent-secondary)]" aria-hidden="true" />
          <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text-primary)]">
            Safety Council
          </h2>
        </div>
        <span
          className="flex items-center gap-1.5 rounded-[var(--radius-sharp)] border px-2 py-1 eyebrow"
          style={{
            color: stage.color,
            borderColor: `color-mix(in srgb, ${stage.color} 40%, transparent)`,
          }}
        >
          <motion.span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: stage.color }}
            animate={isActive ? { opacity: [1, 0.3, 1] } : { opacity: 1 }}
            transition={isActive ? { duration: 1.1, repeat: Infinity } : undefined}
          />
          {stage.label}
        </span>
      </div>

      {/* Agent stations */}
      <div className="grid grid-cols-5 gap-1.5">
        {AGENTS.map((agent) => (
          <div
            key={agent.key}
            className="tactical-tile flex flex-col items-center gap-1.5 py-2.5"
            title={agent.label}
          >
            <agent.Icon
              size={17}
              className={councilStage === 'convening' ? 'text-[var(--color-accent)]' : 'text-[var(--color-text-secondary)]'}
              style={councilStage === 'convening' ? { filter: 'drop-shadow(0 0 6px var(--color-accent))' } : undefined}
              aria-hidden="true"
            />
            <span className="text-center text-[9px] font-medium leading-tight text-[var(--color-text-tertiary)]">
              {agent.short}
            </span>
          </div>
        ))}
        <div
          className="flex flex-col items-center gap-1.5 rounded-[var(--radius-control)] border py-2.5 transition-shadow"
          style={{
            borderColor: 'color-mix(in srgb, var(--color-accent-secondary) 40%, transparent)',
            backgroundColor: 'color-mix(in srgb, var(--color-accent-secondary) 12%, transparent)',
            boxShadow: isActive ? 'var(--shadow-glow-violet)' : 'none',
          }}
          title="Chair (synthesis)"
        >
          <Gavel size={17} className="text-[var(--color-accent-secondary)]" aria-hidden="true" />
          <span className="text-center text-[9px] font-medium leading-tight text-[var(--color-accent-secondary)]">
            Chair
          </span>
        </div>
      </div>

      {/* Fusion core (3D convening) */}
      <div
        className="corner-frame relative overflow-hidden rounded-[var(--radius-control)] border border-[var(--color-hairline)]"
        style={{ background: 'color-mix(in srgb, var(--color-base) 65%, transparent)' }}
      >
        <span className="eyebrow absolute left-3 top-2 z-10">Fusion Core</span>
        <CouncilScene3D stage={councilStage} riskLevel={verdict?.riskLevel} />
      </div>

      {/* Live evidence, before a verdict lands */}
      {!verdict && liveEvidence && (
        <div className="flex flex-col gap-2 rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/50 p-3">
          <span className="eyebrow">Incoming evidence</span>
          <ul className="flex flex-col gap-2 text-xs text-[var(--color-text-secondary)]">
            {AGENTS.map((agent) => (
              <li key={agent.key} className="flex gap-2">
                <agent.Icon size={13} className="mt-0.5 shrink-0 text-[var(--color-accent)]" aria-hidden="true" />
                <span>{liveEvidence[agent.key]}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Verdict */}
      <AnimatePresence>
        {verdict && (
          <motion.div
            key="verdict"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35 }}
            className="flex flex-col gap-3 rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/50 p-4"
          >
            <div className="flex items-center justify-between">
              <RiskBadge level={verdict.riskLevel} size="lg" />
              <div className="flex items-center gap-2">
                {verdict.compoundFlag && (
                  <span
                    className="rounded-[var(--radius-sharp)] px-1.5 py-0.5 eyebrow"
                    style={{
                      color: `var(--color-risk-${verdict.riskLevel.toLowerCase()})`,
                      backgroundColor: `color-mix(in srgb, var(--color-risk-${verdict.riskLevel.toLowerCase()}) 16%, transparent)`,
                    }}
                  >
                    compound
                  </span>
                )}
                <span className="tnum text-xs text-[var(--color-text-secondary)]">
                  {Math.round(verdict.confidence * 100)}% conf
                </span>
              </div>
            </div>

            {/* Trigger tell */}
            <div className="flex items-center gap-1.5 eyebrow">
              <span className="text-[var(--color-text-tertiary)]">Trigger</span>
              <span
                className="rounded-[var(--radius-sharp)] px-1.5 py-0.5"
                style={{ color: 'var(--color-accent)', backgroundColor: 'var(--color-accent-dim)' }}
              >
                {TRIGGER_LABEL[verdict.triggerReason]}
              </span>
            </div>

            <ul className="flex flex-col gap-1.5 text-xs text-[var(--color-text-secondary)]">
              {AGENTS.map((agent) => (
                <li key={agent.key} className="flex gap-2">
                  <agent.Icon size={13} className="mt-0.5 shrink-0 text-[var(--color-text-tertiary)]" aria-hidden="true" />
                  <span>{verdict.council[agent.key]}</span>
                </li>
              ))}
            </ul>

            <p className="text-sm leading-relaxed text-[var(--color-text-primary)]">{verdict.explanation}</p>

            <div className="flex items-center justify-between rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-base)]/40 px-3 py-2">
              <span className="eyebrow">Time to critical</span>
              <span className="tnum text-xs text-[var(--color-text-primary)]">
                {verdict.timeToCritical.medianMinutes} min ({verdict.timeToCritical.iqrLowMinutes}–
                {verdict.timeToCritical.iqrHighMinutes}) · {Math.round(verdict.timeToCritical.escalationProbability * 100)}%
              </span>
            </div>

            <p
              className="rounded-[var(--radius-control)] border-l-2 px-3 py-2 text-sm text-[var(--color-text-primary)]"
              style={{ borderColor: 'var(--color-accent)', background: 'var(--color-accent-dim)' }}
            >
              {verdict.recommendedAction}
            </p>

            {verdict.regulatoryCitations && verdict.regulatoryCitations.length > 0 && (
              <div className="flex flex-col gap-1.5 border-t border-[var(--color-hairline)] pt-3">
                <span className="flex items-center gap-1.5 eyebrow">
                  <Scale size={11} aria-hidden="true" />
                  Regulatory basis
                </span>
                {verdict.regulatoryCitations.map((c) => (
                  <div
                    key={`${c.framework}-${c.sectionNumber}`}
                    className="tnum text-[11px] leading-snug text-[var(--color-accent)]"
                  >
                    {c.isSupplementary && (
                      <span className="mr-1 text-[var(--color-risk-caution)]">[supp]</span>
                    )}
                    {c.sourceDocument} §{c.sectionNumber}
                    <span className="text-[var(--color-text-tertiary)]"> · {c.sectionTitle}</span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Override */}
      {overridePaused && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="flex flex-col gap-2 overflow-hidden rounded-[var(--radius-control)] border p-3"
          style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 40%, transparent)', background: 'var(--color-accent-dim)' }}
        >
          <p className="text-xs text-[var(--color-text-secondary)]">
            {connectionMode === 'live'
              ? 'Council deliberating. Add a note within the window to override, or it resolves automatically.'
              : 'Council paused. Add a note for the Chair before resuming.'}
          </p>
          <textarea
            ref={noteRef}
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            rows={2}
            placeholder="e.g. Permit P-2291 was already suspended manually 5 minutes ago…"
            className="rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-base)]/50 p-2 text-sm text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-tertiary)]"
          />
          <button
            type="button"
            onClick={() => {
              submitOverrideNote(noteText)
              setNoteText('')
            }}
            disabled={!noteText.trim()}
            className="self-end rounded-[var(--radius-control)] border px-3 py-1.5 text-xs font-medium text-[var(--color-accent)] disabled:opacity-40"
            style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
          >
            Resume Council
          </button>
        </motion.div>
      )}
    </section>
  )
}
