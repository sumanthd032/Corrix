import { useEffect, useRef } from 'react'
import { useCorrixStore } from '../store/useCorrixStore'
import type { CouncilEvidence, CouncilVerdict, RiskLevel } from '../types'

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? 'ws://localhost:8000'

interface ServerMessage {
  type:
    | 'tick'
    | 'open_challenge_drawn'
    | 'council_convening'
    | 'deliberating'
    | 'verdict'
    | 'ero_fired'
    | 'playback_complete'
  minute?: number
  zoneRisk?: Record<string, RiskLevel>
  workers?: Record<string, string>
  council?: CouncilEvidence
  verdict?: CouncilVerdict
  label?: string
  zoneId?: string
  deliveredOk?: boolean
  evidenceHash?: string
  firedAt?: string
}

/** Connects to the live scenario WebSocket and drives the Zustand store
 * from real backend messages. Falls back to mock data (already the
 * store's default) if the connection never opens or drops. The
 * "mock data / backend live" indicator in App.tsx reflects this same
 * connection state. */
export function useScenarioSocket() {
  const scenarioId = useCorrixStore((s) => s.scenarioId)
  const wsRef = useRef<WebSocket | null>(null)
  const scenarioIdRef = useRef(scenarioId)

  useEffect(() => {
    scenarioIdRef.current = scenarioId
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      useCorrixStore.getState().beginLivePlayback()
      ws.send(JSON.stringify({ type: 'start', scenario_id: scenarioId }))
    }
  }, [scenarioId])

  useEffect(() => {
    let cancelled = false
    const ws = new WebSocket(`${WS_BASE_URL}/ws/scenario`)
    wsRef.current = ws

    ws.onopen = () => {
      if (cancelled) return
      const store = useCorrixStore.getState()
      store.setConnectionMode('live')
      store.setLiveOverrideSender((note: string) => {
        ws.send(JSON.stringify({ type: 'override', note }))
      })
      store.setOpenChallengeSender(() => {
        store.beginLivePlayback()
        ws.send(JSON.stringify({ type: 'open_challenge' }))
      })
      store.beginLivePlayback()
      ws.send(JSON.stringify({ type: 'start', scenario_id: scenarioIdRef.current }))
    }

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data) as ServerMessage
      const store = useCorrixStore.getState()
      switch (msg.type) {
        case 'tick':
          store.applyLiveTick(msg.zoneRisk ?? {}, msg.workers ?? {})
          break
        case 'open_challenge_drawn':
          if (msg.label) store.setOpenChallengeLabel(msg.label)
          break
        case 'council_convening':
          store.startLiveConvening()
          break
        case 'deliberating':
          if (msg.council) store.applyLiveDeliberating(msg.council)
          break
        case 'verdict':
          if (msg.verdict) store.applyLiveVerdict(msg.verdict)
          break
        case 'ero_fired':
          if (msg.zoneId && msg.evidenceHash && msg.firedAt) {
            store.applyEroFired({
              zoneId: msg.zoneId,
              deliveredOk: msg.deliveredOk ?? false,
              evidenceHash: msg.evidenceHash,
              firedAt: msg.firedAt,
            })
          }
          break
        case 'playback_complete':
          break
      }
    }

    const handleDrop = () => {
      const store = useCorrixStore.getState()
      store.setConnectionMode('mock')
      store.setLiveOverrideSender(null)
      store.setOpenChallengeSender(null)
    }
    ws.onclose = handleDrop
    ws.onerror = () => ws.close()

    return () => {
      cancelled = true
      ws.close()
      wsRef.current = null
    }
  }, [])
}
