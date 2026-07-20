import { useMemo } from 'react'
import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
import {
  ArrowLeft, Camera, Clock, Database, FileCheck, Gauge, MapPin, ShieldCheck, Sparkles, X,
} from 'lucide-react'

/**
 * "Behind the data": a full-screen page explaining exactly how every number
 * on the dashboard is produced, what is genuinely real versus calibrated
 * simulation, and how the gas simulation works, drawn from
 * CORRIX_DATA_METHODOLOGY.md. Opened from the top bar.
 */

function seeded(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 0xffffffff
  }
}

// A deterministic OU gas series with an injected ramp, illustrating a leak
// pushing a noisy baseline signal past the 10% LEL alarm line.
function gasCurve(rampAt: number, n = 120): number[] {
  const rng = seeded(7)
  const k = 0.16, sigma = 0.55, baseline = 2
  let c = baseline
  const out: number[] = []
  for (let t = 0; t < n; t++) {
    const source = t > rampAt ? (t - rampAt) * 0.3 : 0
    c += k * (baseline + source - c) + sigma * (rng() - 0.5)
    out.push(Math.max(0, c))
  }
  return out
}

function CurvePath({ pts, w, h, max, color, fill }: { pts: number[]; w: number; h: number; max: number; color: string; fill?: boolean }) {
  const d = pts
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${(i / (pts.length - 1)) * w},${h - (Math.min(v, max) / max) * h}`)
    .join(' ')
  return (
    <>
      {fill && <path d={`${d} L${w},${h} L0,${h} Z`} fill={`${color}22`} />}
      <path d={d} fill="none" stroke={color} strokeWidth="2" />
    </>
  )
}

const STREAMS = [
  { Icon: Gauge, name: 'Gas & process sensors', how: 'An Ornstein-Uhlenbeck process: a value that hovers around a calibrated baseline with realistic noise, plus an injectable leak. Measured in %LEL.' },
  { Icon: FileCheck, name: 'Permit-to-work records', how: 'Generated permits with realistic background traffic, plus a scenario-specific permit injected into the affected zone.' },
  { Icon: Clock, name: 'Shift schedules', how: 'Rosters and changeover timing, so "right before a shift change" is a real, scheduled moment, not a label.' },
  { Icon: Camera, name: 'Computer vision', how: 'Genuinely real: a YOLO forward pass on an actual site clip detects people and PPE, correlated against the worker-location stream.' },
  { Icon: MapPin, name: 'Worker location', how: 'Zone-level badge pings, kept consistent with each scenario\'s permit and shift context.' },
]

const REAL = ['LLM reasoning (Groq + Gemini)', 'Neo4j GraphRAG retrieval', 'YOLO computer vision', 'MCP integration, both directions', 'Monte Carlo forecaster', 'The evaluation methodology']
const SIM = ['Gas & process readings', 'Permit-to-work records', 'Shift schedules', 'Worker-location pings']

export function DataInsights({ onClose }: { onClose: () => void }) {
  const curve = useMemo(() => gasCurve(46), [])
  const shapes = useMemo(
    () => ({
      ramp: gasCurve(20, 60),
      // step-decay: rises then decays
      step: (() => { const a = gasCurve(6, 60); return a.map((v, i) => (i > 26 ? Math.max(2, v - (i - 26) * 0.22) : v)) })(),
      plateau: (() => { const a = gasCurve(8, 60); return a.map((v, i) => (i > 24 && i < 42 ? Math.min(v, 9) : i >= 42 ? v : v)) })(),
    }),
    [],
  )

  return createPortal(
    <motion.div
      className="fixed inset-0 z-[90] overflow-y-auto"
      style={{ background: 'var(--color-base)' }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <div className="ambient-backdrop pointer-events-none fixed inset-0 -z-10" aria-hidden="true" />

      {/* Top bar */}
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-[var(--color-hairline)] bg-[var(--color-base)]/85 px-6 py-3 backdrop-blur">
        <button
          type="button"
          onClick={onClose}
          className="flex items-center gap-2 rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-3 py-1.5 text-sm text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)]"
        >
          <ArrowLeft size={15} aria-hidden="true" />
          Back to command center
        </button>
        <div className="ml-2 flex items-center gap-2">
          <Database size={15} className="text-[var(--color-accent)]" aria-hidden="true" />
          <span className="font-display text-sm font-semibold tracking-wide">Behind the Data</span>
        </div>
        <button type="button" onClick={onClose} className="ml-auto p-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]" aria-label="Close">
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      <div className="mx-auto max-w-5xl px-6 pb-24">
        {/* Hero */}
        <section className="py-14">
          <span className="eyebrow">Data & methodology</span>
          <h1 className="mt-3 max-w-3xl font-display text-4xl font-semibold leading-tight tracking-tight text-[var(--color-text-primary)]">
            Exactly how every number on the dashboard is produced.
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-relaxed text-[var(--color-text-secondary)]">
            Corrix is deliberate about what is genuinely real and what is calibrated simulation. Nothing here is hand-waved: the reasoning is real, the sensor streams are physics-informed simulation, and the simulation itself is validated against a real industrial dataset.
          </p>
        </section>

        {/* Real vs simulated */}
        <section className="grid gap-4 md:grid-cols-2">
          <div className="glass-panel corner-frame p-6">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} style={{ color: 'var(--color-risk-safe)' }} aria-hidden="true" />
              <h2 className="font-display text-base font-semibold" style={{ color: 'var(--color-risk-safe)' }}>Genuinely real</h2>
            </div>
            <ul className="mt-4 flex flex-col gap-2.5">
              {REAL.map((r) => (
                <li key={r} className="flex items-center gap-2.5 text-sm text-[var(--color-text-primary)]">
                  <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: 'var(--color-risk-safe)' }} />
                  {r}
                </li>
              ))}
            </ul>
          </div>
          <div className="glass-panel corner-frame p-6">
            <div className="flex items-center gap-2">
              <Sparkles size={16} style={{ color: 'var(--color-risk-caution)' }} aria-hidden="true" />
              <h2 className="font-display text-base font-semibold" style={{ color: 'var(--color-risk-caution)' }}>Calibrated simulation</h2>
            </div>
            <ul className="mt-4 flex flex-col gap-2.5">
              {SIM.map((r) => (
                <li key={r} className="flex items-center gap-2.5 text-sm text-[var(--color-text-primary)]">
                  <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: 'var(--color-risk-caution)' }} />
                  {r}
                </li>
              ))}
            </ul>
            <p className="mt-4 text-xs leading-relaxed text-[var(--color-text-tertiary)]">
              Simulated because no public real Indian plant SCADA dataset exists. The alternative, quietly using a foreign dataset and calling it real, is exactly the kind of thing Corrix refuses to do.
            </p>
          </div>
        </section>

        {/* The five streams */}
        <section className="pt-16">
          <span className="eyebrow">The five streams</span>
          <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight">Five normally-siloed data sources</h2>
          <div className="mt-6 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {STREAMS.map(({ Icon, name, how }) => (
              <div key={name} className="tactical-tile p-5">
                <div className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-control)]" style={{ background: 'var(--color-accent-dim)' }}>
                  <Icon size={17} className="text-[var(--color-accent)]" aria-hidden="true" />
                </div>
                <h3 className="mt-3 font-display text-sm font-semibold text-[var(--color-text-primary)]">{name}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--color-text-secondary)]">{how}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How the gas sim works */}
        <section className="pt-16">
          <span className="eyebrow">How the simulation works</span>
          <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight">A physics-informed gas process</h2>
          <div className="mt-6 grid gap-5 lg:grid-cols-[1.3fr_1fr]">
            <div className="glass-panel corner-frame p-6">
              <div className="mb-2 flex items-center justify-between">
                <span className="eyebrow">Gas concentration · %LEL</span>
                <span className="flex items-center gap-1.5 tnum text-[11px]" style={{ color: 'var(--color-risk-high)' }}>
                  <span className="inline-block h-0.5 w-4" style={{ background: 'var(--color-risk-high)' }} /> 10% LEL alarm
                </span>
              </div>
              <svg viewBox="0 0 520 200" className="w-full">
                {[0, 1, 2, 3].map((i) => (
                  <line key={i} x1="0" y1={(i / 3) * 180} x2="520" y2={(i / 3) * 180} stroke="rgba(125,162,194,0.08)" />
                ))}
                {/* alarm line at 10% LEL (max 20) */}
                <line x1="0" y1={180 - (10 / 20) * 180} x2="520" y2={180 - (10 / 20) * 180} stroke="var(--color-risk-high)" strokeWidth="1.2" strokeDasharray="5 5" opacity="0.8" />
                <g transform="translate(0,10)">
                  <CurvePath pts={curve} w={520} h={180} max={20} color="var(--color-accent)" fill />
                </g>
              </svg>
              <p className="mt-3 text-[13px] leading-relaxed text-[var(--color-text-secondary)]">
                An Ornstein-Uhlenbeck process keeps the reading hovering around a calibrated baseline with realistic noise. An injected leak term then pushes it up until it crosses the alarm threshold. It is stepped with Euler-Maruyama, the exact same <code className="font-mono-data text-[var(--color-accent)]">step()</code> function the live time-to-critical forecaster reuses, so the forecast is consistent with the signal.
              </p>
            </div>
            <div className="flex flex-col gap-3">
              {[
                { name: 'Ramp', pts: shapes.ramp, desc: 'A steady rise, like a slow accumulation.' },
                { name: 'Step-decay', pts: shapes.step, desc: 'A spike that vents and decays back down.' },
                { name: 'Ramp-with-plateau', pts: shapes.plateau, desc: 'Rises, holds, then a second compounding push.' },
              ].map((s) => (
                <div key={s.name} className="tactical-tile flex items-center gap-4 p-4">
                  <svg viewBox="0 0 120 44" className="h-11 w-28 shrink-0">
                    <CurvePath pts={s.pts} w={120} h={44} max={16} color="var(--color-accent)" />
                  </svg>
                  <div>
                    <div className="font-mono-data text-xs font-semibold text-[var(--color-text-primary)]">{s.name}</div>
                    <div className="text-[12px] leading-snug text-[var(--color-text-secondary)]">{s.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Grounded + validated */}
        <section className="pt-16">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="glass-panel corner-frame p-6">
              <span className="eyebrow">Grounded in a real incident</span>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-secondary)]">
                The anchor scenario is modeled on the June 8, 2025 Visakhapatnam Steel Plant incident, a real, verifiable compound-risk event, not an invented one.
              </p>
            </div>
            <div className="glass-panel corner-frame p-6">
              <span className="eyebrow">Validated against real data</span>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-secondary)]">
                The simulator's noise-to-signal ratio was measured against the real SWaT industrial dataset and falls inside its observed range.
              </p>
              <div className="mt-4 flex items-end gap-6">
                <div>
                  <div className="tnum text-2xl font-semibold" style={{ color: 'var(--color-risk-safe)' }}>0.043–0.055</div>
                  <div className="eyebrow mt-1">Corrix</div>
                </div>
                <div className="pb-1 text-[var(--color-text-tertiary)]">inside</div>
                <div>
                  <div className="tnum text-2xl font-semibold text-[var(--color-text-primary)]">0.012–0.117</div>
                  <div className="eyebrow mt-1">SWaT range</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Determinism */}
        <section className="pt-16">
          <div className="glass-panel corner-frame flex flex-col gap-3 p-6 md:flex-row md:items-center">
            <div className="flex-1">
              <span className="eyebrow">Deterministic & reproducible</span>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-secondary)]">
                Every scenario is seeded, so it produces exactly the same data on every run. The library pairs each positive scenario with matched negative controls (a normal day with the same generators), so the evaluation numbers are honest, not cherry-picked.
              </p>
            </div>
            <div className="flex gap-3">
              <div className="tactical-tile px-5 py-4 text-center">
                <div className="tnum text-2xl font-semibold text-[var(--color-text-primary)]">5</div>
                <div className="eyebrow mt-1">scenarios</div>
              </div>
              <div className="tactical-tile px-5 py-4 text-center">
                <div className="tnum text-2xl font-semibold text-[var(--color-text-primary)]">25</div>
                <div className="eyebrow mt-1">controls</div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </motion.div>,
    document.body,
  )
}
