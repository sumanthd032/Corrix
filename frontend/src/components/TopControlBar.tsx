import { Download, PauseCircle, Radio, ShieldAlert, Sparkles } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'

const SCENARIOS = [
  { id: 'S1', label: 'S1 — Anchor (Ladle Bay)' },
  { id: 'S2', label: 'S2 — Confined Space' },
  { id: 'S3', label: 'S3 — Maintenance / Gas' },
  { id: 'S4', label: 'S4 — Hot Work / Gas' },
]

export function TopControlBar() {
  const scenarioId = useCorrixStore((s) => s.scenarioId)
  const setScenario = useCorrixStore((s) => s.setScenario)
  const overridePaused = useCorrixStore((s) => s.overridePaused)
  const pauseForOverride = useCorrixStore((s) => s.pauseForOverride)
  const councilStage = useCorrixStore((s) => s.councilStage)

  return (
    <header className="glass-panel flex items-center gap-4 px-5 py-3">
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

      <button
        type="button"
        className="flex items-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
      >
        <Radio size={15} aria-hidden="true" />
        Counterfactual Replay
      </button>

      <button
        type="button"
        className="flex items-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
      >
        <Sparkles size={15} aria-hidden="true" />
        Open Challenge
      </button>

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          className="flex items-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
        >
          <Download size={15} aria-hidden="true" />
          Incident Report
        </button>

        <span className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
          <ShieldAlert size={14} aria-hidden="true" />
          ERO idle
        </span>

        <button
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
        </button>
      </div>
    </header>
  )
}
