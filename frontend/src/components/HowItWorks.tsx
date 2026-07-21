import { useState, type ReactElement } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, X } from 'lucide-react'

/**
 * A completely visual "how it works" walkthrough for the landing page.
 * Five stages, sensors to answer, each with a diagram and one caption
 * that pairs plain-language framing with the real technical detail.
 * Rendered inside the landing (`.corrix-landing`) so it inherits the
 * landing's tokens.
 */

const CY = '#2dd4e8'
const CY2 = '#5ce6f5'
const HIGH = '#ff8a3d'
const VI = '#8b5cf6'
const DIM = '#33526a'
const INK = '#93a6bb'

function label(x: number, y: number, text: string, anchor: 'start' | 'middle' | 'end' = 'middle') {
  return (
    <text x={x} y={y} textAnchor={anchor} fontSize="11" fontFamily="IBM Plex Mono, monospace" fill={INK}>
      {text}
    </text>
  )
}

function SensorsVisual() {
  const pins: [number, number, string, string][] = [
    [120, 96, 'gas', 'Gas sensor'],
    [320, 96, 'permit', 'Permit log'],
    [220, 150, 'shift', 'Shift clock'],
    [120, 214, 'camera', 'Camera'],
    [320, 214, 'badge', 'Worker badge'],
  ]
  return (
    <svg viewBox="0 0 440 320">
      <rect x="70" y="60" width="300" height="200" rx="12" fill="rgba(45,212,232,0.04)" stroke={DIM} strokeWidth="1.2" />
      {[110, 150, 190, 230, 270].map((y) => (
        <line key={y} x1="70" y1={y} x2="370" y2={y} stroke="rgba(45,212,232,0.06)" />
      ))}
      {label(220, 48, 'ONE PLANT · MANY SENSORS')}
      {pins.map(([x, y, , text], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r="9" fill="rgba(45,212,232,0.15)" stroke={CY} strokeWidth="1.5">
            <animate attributeName="r" values="9;13;9" dur="2.2s" begin={`${i * 0.3}s`} repeatCount="indefinite" />
            <animate attributeName="opacity" values="1;.4;1" dur="2.2s" begin={`${i * 0.3}s`} repeatCount="indefinite" />
          </circle>
          <circle cx={x} cy={y} r="3.5" fill={CY2} />
          {label(x, y + 26, text)}
        </g>
      ))}
    </svg>
  )
}

function FlowVisual() {
  const sources = ['Gas', 'Permits', 'Shifts', 'Cameras', 'Badges']
  const hub: [number, number] = [340, 160]
  return (
    <svg viewBox="0 0 440 320">
      {sources.map((s, i) => {
        const y = 60 + i * 50
        const path = `M110,${y} C210,${y} 250,160 ${hub[0]},${hub[1]}`
        return (
          <g key={s}>
            <path d={path} fill="none" stroke={DIM} strokeWidth="1.3" strokeDasharray="4 5" opacity="0.7">
              <animate attributeName="stroke-dashoffset" values="0;-18" dur="1.2s" repeatCount="indefinite" />
            </path>
            <circle r="3" fill={CY2}>
              <animateMotion dur="1.8s" begin={`${i * 0.28}s`} repeatCount="indefinite" path={path} />
            </circle>
            <rect x="30" y={y - 13} width="72" height="26" rx="6" fill="rgba(19,28,38,0.9)" stroke={DIM} />
            <text x="66" y={y + 4} textAnchor="middle" fontSize="11" fontFamily="IBM Plex Mono, monospace" fill={INK}>{s}</text>
          </g>
        )
      })}
      <circle cx={hub[0]} cy={hub[1]} r="30" fill="rgba(45,212,232,0.12)" stroke={CY} strokeWidth="1.6" />
      <text x={hub[0]} y={hub[1] + 4} textAnchor="middle" fontSize="12" fontFamily="Space Grotesk, sans-serif" fontWeight="600" fill={CY2}>CORRIX</text>
      {label(hub[0], hub[1] + 52, 'ALL FIVE, IN ONE PLACE')}
    </svg>
  )
}

function CompoundVisual() {
  const chips: [number, string, string][] = [
    [70, 'Gas rising', CY],
    [140, 'Hot-work permit', CY],
    [210, 'Shift change soon', CY],
  ]
  return (
    <svg viewBox="0 0 440 320">
      {chips.map(([y, t], i) => {
        const path = `M170,${y} C240,${y} 250,180 300,180`
        return (
          <g key={t}>
            <rect x="34" y={y - 15} width="140" height="30" rx="8" fill="rgba(19,28,38,0.9)" stroke={DIM} />
            <text x="104" y={y + 4} textAnchor="middle" fontSize="11.5" fontFamily="IBM Plex Mono, monospace" fill={INK}>{t}</text>
            <text x="150" y={y + 4} textAnchor="middle" fontSize="12" fill={INK}>ok</text>
            <path d={path} fill="none" stroke={DIM} strokeWidth="1.3" strokeDasharray="4 5">
              <animate attributeName="stroke-dashoffset" values="0;-18" dur="1.1s" repeatCount="indefinite" />
            </path>
            <circle r="3" fill={CY2}><animateMotion dur="1.5s" begin={`${i * 0.3}s`} repeatCount="indefinite" path={path} /></circle>
          </g>
        )
      })}
      <g>
        <rect x="248" y="150" width="150" height="60" rx="12" fill="rgba(255,138,61,0.14)" stroke={HIGH} strokeWidth="1.6">
          <animate attributeName="opacity" values="1;.6;1" dur="1.6s" repeatCount="indefinite" />
        </rect>
        <rect x="266" y="172" width="16" height="16" fill={HIGH} transform="rotate(45 274 180)" />
        <text x="330" y="176" textAnchor="middle" fontSize="12" fontFamily="Space Grotesk, sans-serif" fontWeight="600" fill={HIGH}>COMPOUND</text>
        <text x="330" y="194" textAnchor="middle" fontSize="12" fontFamily="Space Grotesk, sans-serif" fontWeight="600" fill={HIGH}>RISK</text>
      </g>
      {label(220, 40, 'EACH ONE FINE · TOGETHER DANGEROUS')}
    </svg>
  )
}

function CouncilVisual() {
  const agents: [number, number, string][] = [
    [70, 240, 'Process'],
    [160, 260, 'Permit'],
    [280, 260, 'Shift'],
    [370, 240, 'Observer'],
  ]
  const chair: [number, number] = [220, 110]
  return (
    <svg viewBox="0 0 440 320">
      {agents.map(([x, y, t], i) => {
        const path = `M${x},${y} L${chair[0]},${chair[1]}`
        return (
          <g key={t}>
            <line x1={x} y1={y} x2={chair[0]} y2={chair[1]} stroke={DIM} strokeWidth="1.2" opacity="0.6" />
            <circle r="2.6" fill={CY2}><animateMotion dur="1.6s" begin={`${i * 0.35}s`} repeatCount="indefinite" path={path} /></circle>
            <circle cx={x} cy={y} r="14" fill="rgba(14,20,28,0.95)" stroke={CY} strokeWidth="1.5" />
            {label(x, y + 30, t)}
          </g>
        )
      })}
      <circle cx={chair[0]} cy={chair[1]} r="24" fill={VI} opacity="0.9">
        <animate attributeName="r" values="24;27;24" dur="2s" repeatCount="indefinite" />
      </circle>
      <circle cx={chair[0]} cy={chair[1]} r="11" fill="#c9b6ff" />
      {label(chair[0], chair[1] - 36, 'THE CHAIR DECIDES')}
      {label(chair[0], chair[1] + 44, 'four experts · one verdict')}
    </svg>
  )
}

function VerdictVisual() {
  return (
    <svg viewBox="0 0 440 320">
      <rect x="70" y="46" width="300" height="228" rx="14" fill="rgba(19,28,38,0.85)" stroke={DIM} strokeWidth="1.2" />
      {/* risk badge */}
      <rect x="90" y="66" width="15" height="15" fill={HIGH} transform="rotate(45 97 73)" />
      <text x="120" y="80" fontSize="16" fontFamily="Space Grotesk, sans-serif" fontWeight="600" fill={HIGH}>HIGH</text>
      <text x="350" y="80" textAnchor="end" fontSize="12" fontFamily="IBM Plex Mono, monospace" fill={INK}>87% sure</text>
      <line x1="90" y1="98" x2="350" y2="98" stroke={DIM} opacity="0.5" />
      {/* time to critical bar */}
      {label(96, 122, 'Time to critical', 'start')}
      <text x="350" y="122" textAnchor="end" fontSize="12" fontFamily="IBM Plex Mono, monospace" fill="#fff">12 min</text>
      <rect x="90" y="132" width="260" height="7" rx="4" fill="#1a2530" />
      <rect x="90" y="132" width="150" height="7" rx="4" fill={HIGH}>
        <animate attributeName="width" values="80;150;80" dur="3s" repeatCount="indefinite" />
      </rect>
      {/* evacuation route */}
      {label(96, 170, 'Safest way out', 'start')}
      {['Z1', 'Z3', 'Z4'].map((z, i) => (
        <g key={z}>
          <rect x={92 + i * 70} y="180" width="46" height="26" rx="6" fill="rgba(45,212,232,0.12)" stroke={CY} />
          <text x={115 + i * 70} y="197" textAnchor="middle" fontSize="12" fontFamily="IBM Plex Mono, monospace" fill={CY2}>{z}</text>
          {i < 2 && <path d={`M${138 + i * 70},193 h20`} stroke={CY} strokeWidth="1.5" markerEnd="" />}
        </g>
      ))}
      {/* action */}
      <rect x="90" y="226" width="260" height="30" rx="7" fill="rgba(45,212,232,0.08)" stroke="rgba(45,212,232,0.3)" />
      <text x="104" y="245" fontSize="11.5" fontFamily="Inter, sans-serif" fill="#e8eff6">Suspend permit · alert supervisor</text>
      {label(220, 300, 'CLEAR ANSWER · WHAT TO DO')}
    </svg>
  )
}

interface Stage {
  no: string
  title: string
  copy: string
  Visual: () => ReactElement
}

const STAGES: Stage[] = [
  {
    no: 'Step 1 of 5',
    title: 'The plant is full of sensors',
    copy:
      'Across the plant, Corrix reads five live data streams: gas concentration (an Ornstein-Uhlenbeck process in percent-LEL), permit-to-work records, shift rosters and changeover timing, YOLO computer-vision PPE detection, and RFID badge worker-location pings. Each is exposed as its own Model Context Protocol server.',
    Visual: SensorsVisual,
  },
  {
    no: 'Step 2 of 5',
    title: 'All the data flows into one place',
    copy:
      'Normally each of these systems has its own screen and its own team, and they never talk to each other. Corrix pulls all five MCP servers together over a live WebSocket, so the signals that are physically siloed in a real plant are brought into one shared reasoning context.',
    Visual: FlowVisual,
  },
  {
    no: 'Step 3 of 5',
    title: 'It watches for dangerous combinations',
    copy:
      'Any single reading might be completely normal. The danger is in the combination, like gas creeping up while hot-work is happening, right before a shift change. A fast rule-and-threshold path (rolling z-score plus a deterministic permit-conflict rule) runs alongside an independent joint-evidence novelty detector (Mahalanobis distance over the fused evidence vector), so it also catches compound patterns nobody scripted in advance.',
    Visual: CompoundVisual,
  },
  {
    no: 'Step 4 of 5',
    title: 'A team of AI experts reviews it',
    copy:
      'When something looks risky, a LangGraph state machine convenes four evidence agents, each scoped to only its own data source so no single agent can see the whole picture, feeding a synthesizing Chair. A real interrupt lets a safety officer inject a note before the Chair produces the final verdict.',
    Visual: CouncilVisual,
  },
  {
    no: 'Step 5 of 5',
    title: 'You get a clear answer and what to do',
    copy:
      'The verdict carries a risk level, confidence, and compound flag, a Monte Carlo time-to-critical band, a risk-aware Dijkstra evacuation route, the regulation clause it is grounded in, and an SMTP emergency notification with a hashed evidence snapshot on a CRITICAL verdict, all with the reasoning shown.',
    Visual: VerdictVisual,
  },
]

export function HowItWorks({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0)
  const stage = STAGES[step]
  const isLast = step === STAGES.length - 1

  return (
    <div className="hiw-overlay" onClick={onClose}>
      <div className="hiw-modal" onClick={(e) => e.stopPropagation()}>
        <div className="hiw-head">
          <h2>How Corrix works</h2>
          <button type="button" className="hiw-x" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="hiw-body">
          <div className="hiw-visual">
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ duration: 0.25 }}
                style={{ width: '100%' }}
              >
                <stage.Visual />
              </motion.div>
            </AnimatePresence>
          </div>
          <div className="hiw-copy">
            <span className="stepno">{stage.no}</span>
            <h3>{stage.title}</h3>
            <AnimatePresence mode="wait">
              <motion.p
                key={step}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                {stage.copy}
              </motion.p>
            </AnimatePresence>
          </div>
        </div>

        <div className="hiw-foot">
          <div className="hiw-dots">
            {STAGES.map((_, i) => (
              <i key={i} className={i === step ? 'on' : ''} onClick={() => setStep(i)} />
            ))}
          </div>
          <div className="hiw-nav">
            <button type="button" className="hiw-btn" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>
              <ArrowLeft size={14} /> Back
            </button>
            <button
              type="button"
              className="hiw-btn primary"
              onClick={() => (isLast ? onClose() : setStep((s) => s + 1))}
            >
              {isLast ? 'Got it' : 'Next'} {!isLast && <ArrowRight size={14} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
