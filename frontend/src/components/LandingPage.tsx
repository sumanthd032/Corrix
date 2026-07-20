import { useEffect, useRef, useState } from 'react'
import { HowItWorks } from './HowItWorks'
import './LandingPage.css'

/**
 * The Corrix marketing landing page. Renders full-screen before the
 * dashboard; the "Launch live demo" buttons call `onLaunch` to enter the
 * existing synthetic demo, unchanged. "Get Started" calls `onGetStarted`
 * to enter the Bring Your Own Factory onboarding wizard instead, a
 * fully separate flow off the same landing page. Self-contained styles
 * are scoped under `.corrix-landing` (LandingPage.css) so its generic
 * class names don't touch the dashboard.
 */
export function LandingPage({
  onLaunch,
  onGetStarted,
}: {
  onLaunch: () => void
  onGetStarted: () => void
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const [howOpen, setHowOpen] = useState(false)
  const [noteOpen, setNoteOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  // Mobile guard: the interactive demo and the walkthrough modal both need
  // more room than a phone screen gives them, so on mobile the CTAs open a
  // blocking note instead of the real action.
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    setIsMobile(mq.matches)
    const onChange = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const guardLaunch = () => {
    if (isMobile) { setNoteOpen(true); return }
    onLaunch()
  }
  const guardHowItWorks = () => {
    if (isMobile) { setNoteOpen(true); return }
    setHowOpen(true)
  }
  const guardGetStarted = () => {
    if (isMobile) { setNoteOpen(true); return }
    onGetStarted()
  }

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    // Ambient canvas: perspective grid + drifting gas particles.
    const canvas = canvasRef.current
    let raf = 0
    let onResize: (() => void) | null = null
    if (canvas) {
      const ctx = canvas.getContext('2d')!
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      let w = 0, h = 0
      let parts: { x: number; y: number; r: number; vx: number; vy: number; a: number }[] = []
      const resize = () => {
        w = canvas.clientWidth
        h = canvas.clientHeight
        canvas.width = w * dpr
        canvas.height = h * dpr
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
        parts = Array.from({ length: Math.min(46, Math.floor(w / 26)) }, () => ({
          x: Math.random() * w,
          y: Math.random() * h,
          r: 14 + Math.random() * 46,
          vx: (Math.random() - 0.5) * 0.16,
          vy: -(0.05 + Math.random() * 0.18),
          a: 0.02 + Math.random() * 0.05,
        }))
      }
      const grid = () => {
        ctx.strokeStyle = 'rgba(45,212,232,0.05)'
        ctx.lineWidth = 1
        const hz = h * 0.62, vp = w * 0.5
        for (let i = -10; i <= 10; i++) {
          const x = vp + i * (w * 0.12)
          ctx.beginPath(); ctx.moveTo(x, hz); ctx.lineTo(vp + i * (w * 0.5), h + 40); ctx.stroke()
        }
        for (let j = 0; j < 9; j++) {
          const t = j / 9, y = hz + Math.pow(t, 1.8) * (h - hz)
          ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
        }
      }
      const frame = () => {
        ctx.clearRect(0, 0, w, h)
        grid()
        for (const p of parts) {
          p.x += p.vx; p.y += p.vy
          if (p.y < -60) { p.y = h + 40; p.x = Math.random() * w }
          const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r)
          g.addColorStop(0, `rgba(120,200,220,${p.a})`)
          g.addColorStop(1, 'rgba(120,200,220,0)')
          ctx.fillStyle = g
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 7); ctx.fill()
        }
        if (!reduced) raf = requestAnimationFrame(frame)
      }
      onResize = resize
      window.addEventListener('resize', resize)
      resize()
      if (reduced) { ctx.clearRect(0, 0, w, h); grid() } else frame()
    }

    // Scroll reveals.
    const els = rootRef.current?.querySelectorAll('.reveal') ?? []
    let io: IntersectionObserver | null = null
    if (reduced) {
      els.forEach((e) => e.classList.add('in'))
    } else {
      io = new IntersectionObserver(
        (ents) => ents.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io!.unobserve(e.target) } }),
        { threshold: 0.15 },
      )
      els.forEach((e) => io!.observe(e))
    }

    return () => {
      cancelAnimationFrame(raf)
      if (onResize) window.removeEventListener('resize', onResize)
      io?.disconnect()
    }
  }, [])

  const tickerRows = [
    'Z1 LADLE BAY 13.8% LEL ▲', 'Z2 GAS MAIN 04.7%', 'Z3 MAINT nominal', 'Z4 CONTROL nominal',
    'Z5 SCRAP nominal', 'Z6 QUENCH 02.1%', 'Z7 GAS VAULT 05.2%', 'Z8 PERIMETER nominal',
    'COUNCIL verdict reached', 'TTC 12 min',
  ].join('  ·  ')

  return (
    <div className="corrix-landing" ref={rootRef}>
      <nav>
        <div className="container nav-in">
          <div className="brand"><span className="m"><i /></span><b>CORRIX</b></div>
          <div className="nav-links">
            <a href="#problem">The problem</a>
            <a href="#capabilities" onClick={(e) => { e.preventDefault(); guardHowItWorks() }}>How it works</a>
            <a href="#capabilities">Capabilities</a>
            <a href="#proof">Evidence</a>
          </div>
          <div className="nav-cta">
            <button type="button" className="btn btn-ghost" onClick={guardGetStarted}>Get Started</button>
            <button type="button" className="btn btn-primary" onClick={guardLaunch}>
              Launch live demo
              <svg className="ar" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
            </button>
          </div>
        </div>
      </nav>

      <header className="hero">
        <canvas id="amb" ref={canvasRef} />
        <div className="hero-glow" />
        <div className="container">
          <div className="hero-grid">
            <div>
              <span className="status-pill"><span className="d" />LIVE · MONITORING 8 ZONES</span>
              <h1>Three routine signals.<br />One <span className="grad">compound risk.</span></h1>
              <p className="lede">
                A rising gas reading is routine. A hot-work permit is routine. Together, right before a
                shift changeover, they are the failure mode no single safety system is built to catch.
                Corrix is the correlation layer that catches it, with minutes of lead time and full
                explainable reasoning.
              </p>
              <div className="hero-cta">
                <button type="button" className="btn btn-primary" onClick={guardLaunch}>
                  Launch live demo
                  <svg className="ar" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
                </button>
                <button type="button" className="btn btn-ghost" onClick={guardHowItWorks}>See how it works</button>
                <button type="button" className="btn btn-ghost" onClick={guardGetStarted}>Get Started</button>
              </div>
              <div className="ticker">
                <span className="lbl">LIVE FEED</span>
                <div className="stream"><span>{tickerRows}{'  ·  '}{tickerRows}</span></div>
              </div>
            </div>

            <div className="fusion reveal">
              <div className="f-head"><span className="ld" /> LIVE · ZONE Z1 · LADLE BAY · T-00:09 TO CHANGEOVER</div>
              <div className="signals">
                <div className="sig">
                  <div className="k"><svg viewBox="0 0 24 24"><path d="M12 3a9 9 0 1 0 9 9" /><path d="M12 12l4-2" /></svg>Gas</div>
                  <div className="v tnum">13.8% <span className="arw">▲</span></div>
                </div>
                <div className="sig">
                  <div className="k"><svg viewBox="0 0 24 24"><path d="M6 3h9l3 3v15H6z" /><path d="M9 8h6M9 12h6" /></svg>Permit</div>
                  <div className="v tnum">P-2291</div>
                </div>
                <div className="sig">
                  <div className="k"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>Shift</div>
                  <div className="v tnum">00:09</div>
                </div>
              </div>
              <svg className="funnel" viewBox="0 0 400 104" preserveAspectRatio="none">
                <path d="M66,4 C66,60 200,44 200,96" fill="none" stroke="#2dd4e8" strokeWidth="1.6" strokeDasharray="4 6" opacity=".55" style={{ animation: 'l-flow 1.3s linear infinite' }} />
                <path d="M200,4 L200,96" fill="none" stroke="#2dd4e8" strokeWidth="1.6" strokeDasharray="4 6" opacity=".55" style={{ animation: 'l-flow 1.3s linear infinite' }} />
                <path d="M334,4 C334,60 200,44 200,96" fill="none" stroke="#2dd4e8" strokeWidth="1.6" strokeDasharray="4 6" opacity=".55" style={{ animation: 'l-flow 1.3s linear infinite' }} />
                <circle r="3" fill="#5ce6f5"><animateMotion dur="1.5s" repeatCount="indefinite" path="M66,4 C66,60 200,44 200,96" /></circle>
                <circle r="3" fill="#5ce6f5"><animateMotion dur="1.5s" begin=".5s" repeatCount="indefinite" path="M200,4 L200,96" /></circle>
                <circle r="3" fill="#5ce6f5"><animateMotion dur="1.5s" begin="1s" repeatCount="indefinite" path="M334,4 C334,60 200,44 200,96" /></circle>
              </svg>
              <div className="verdict-bar">
                <span className="diamond" />
                <span className="txt">COMPOUND RISK · HIGH</span>
                <span className="conf">conf 87%</span>
              </div>
            </div>
          </div>

          <div className="metrics reveal">
            <div className="metric"><div className="n tnum">5</div><div className="l">data streams fused into one verdict</div></div>
            <div className="metric"><div className="n tnum">&lt;30s</div><div className="l">from trigger to explained verdict</div></div>
            <div className="metric"><div className="n tnum">3</div><div className="l">real regulatory frameworks, cited</div></div>
            <div className="metric"><div className="n tnum">100%</div><div className="l">baseline precision on the labeled library</div></div>
          </div>
        </div>
      </header>

      <section className="blk" id="problem">
        <div className="container">
          <div className="sec-head reveal">
            <span className="eyebrow">The blind spot</span>
            <h2>No single system correlates the facts in time.</h2>
            <p>Every reading below is individually ordinary. Their combination is the failure mode Corrix exists to close.</p>
          </div>
          <div className="clauses reveal">
            <div className="clause routine"><span className="tag">Routine</span><h3>A rising gas reading</h3><p>Gas trending up in the collection main. The sensor team sees a curve, not an emergency.</p></div>
            <div className="clause routine"><span className="tag">Routine</span><h3>An active hot-work permit</h3><p>A permit issued for the same zone. The permit office sees valid paperwork.</p></div>
            <div className="clause risk"><span className="tag">Compound risk</span><h3>Both, before a changeover, with a worker present</h3><p>Now it is a compound risk. No existing system holds all four facts at once, so nobody raises the alarm.</p></div>
          </div>
        </div>
      </section>

      <section className="blk" id="capabilities">
        <div className="container">
          <div className="sec-head reveal"><span className="eyebrow">Capabilities</span><h2>Beyond a dashboard with alerts.</h2></div>
          <div className="bento reveal">
            <div className="card span2">
              <div className="ic"><svg viewBox="0 0 24 24"><path d="M3 21h18M6 21V10l6-4 6 4v11" /></svg></div>
              <h3>The Safety Council</h3>
              <p>Five specialized agents orchestrated as a LangGraph state machine, with a real human-in-the-loop interrupt: the Council pauses mid-reasoning for a safety officer's note before the Chair decides. The silo constraint is enforced at the architecture level, not just claimed.</p>
              <span className="chip">LangGraph · Groq + Gemini failover</span>
            </div>
            <div className="card"><div className="ic"><svg viewBox="0 0 24 24"><path d="M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" /></svg></div><h3>Joint-Evidence Novelty Detector</h3><p>Catches compound risks that match no scripted pattern, proven live via an unrehearsed Open Challenge.</p></div>
            <div className="card"><div className="ic"><svg viewBox="0 0 24 24"><path d="M4 5a2 2 0 0 1 2-2h10l4 4v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" /><path d="M9 8h6M9 12h6" /></svg></div><h3>Regulatory Intelligence</h3><p>A Neo4j GraphRAG layer over real OISD, Factories Act 1948, and DGMS text. Every verdict cites the clause it sits on.</p></div>
            <div className="card"><div className="ic"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg></div><h3>Time-to-Critical forecasting</h3><p>A per-zone probability band via Monte Carlo rollout, reusing the simulator's own step function, not a bare countdown.</p></div>
            <div className="card"><div className="ic"><svg viewBox="0 0 24 24"><path d="M3 12h4l2 6 4-14 2 8h6" /></svg></div><h3>Spatial risk propagation</h3><p>Predicts where a compound risk could spread across the adjacency graph if it isn't contained.</p></div>
            <div className="card"><div className="ic"><svg viewBox="0 0 24 24"><path d="M12 3a9 9 0 1 0 9 9" /><path d="M12 12l5-3" /></svg></div><h3>Self-improving memory loop</h3><p>Learns from its own past misses, with the improvement measured only on a held-out set it never trained on.</p></div>
          </div>
        </div>
      </section>

      <section className="blk" id="proof">
        <div className="container">
          <div className="honesty reveal">
            <div>
              <span className="eyebrow">Radical honesty</span>
              <h2>We tell you exactly what is real and what is simulated.</h2>
              <p>The reasoning, the regulatory retrieval, the computer vision, and the evaluation methodology are genuinely real. The sensor streams are calibrated simulation, because no public real Indian plant SCADA dataset exists, validated against the SWaT industrial dataset (noise-to-signal 0.043–0.055, inside SWaT's own 0.012–0.117 range). The held-out memory loop moves the false-negative rate from 30% to 0%.</p>
            </div>
            <div className="split">
              <div className="row real"><b>Real</b> LLM reasoning · GraphRAG · YOLO vision · MCP · Monte Carlo</div>
              <div className="row sim"><b>Simulated</b> gas, permit, shift, worker-location streams</div>
              <div className="row real"><b>Validated</b> against the real SWaT industrial dataset</div>
            </div>
          </div>
        </div>
      </section>

      <section className="blk">
        <div className="container">
          <div className="sec-head reveal" style={{ marginBottom: 26 }}><span className="eyebrow">Built on</span><h2 style={{ fontSize: 26 }}>Real infrastructure, end to end.</h2></div>
          <div className="tech reveal">
            <span>LangGraph</span><span>Groq (primary)</span><span>Gemini (failover)</span><span>Neo4j AuraDB · vector search</span><span>sentence-transformers</span><span>Ultralytics YOLO11n</span><span>Model Context Protocol</span><span>FastAPI · WebSocket</span><span>React · deck.gl · Three.js</span>
          </div>
        </div>
      </section>

      <section className="blk">
        <div className="container">
          <div className="cta reveal">
            <span className="eyebrow">See it live</span>
            <h2>Watch a compound risk get caught.</h2>
            <p>Run a real scenario end to end: the Council convenes, reaches an explained verdict, forecasts time-to-critical, and routes an evacuation, in under thirty seconds.</p>
            <button type="button" className="btn btn-primary" onClick={guardLaunch} style={{ fontSize: 16, padding: '14px 26px' }}>
              Launch live demo
              <svg className="ar" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
            </button>
          </div>
        </div>
      </section>

      <footer>
        <div className="container foot-in">
          <div className="brand"><span className="m"><i /></span><b style={{ fontSize: 15 }}>CORRIX</b></div>
          <span className="muted">The correlation layer industrial safety never had.</span>
          <span className="sp" />
          <span className="muted">Compound Risk Operations · 2026</span>
        </div>
      </footer>

      {howOpen && <HowItWorks onClose={() => setHowOpen(false)} />}

      {noteOpen && (
        <div className="desktop-note-overlay" role="dialog" aria-modal="true" aria-label="Desktop recommended">
          <div className="desktop-note">
            <span className="d" />
            <p>The live demo and the walkthrough are built for a larger screen. Recommended: use a desktop for the best experience.</p>
            <button type="button" className="btn btn-primary" onClick={() => setNoteOpen(false)}>Understood</button>
          </div>
        </div>
      )}
    </div>
  )
}
