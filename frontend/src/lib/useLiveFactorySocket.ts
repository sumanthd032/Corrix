import { useEffect, useRef } from 'react'
import { useCorrixStore } from '../store/useCorrixStore'
import type { CouncilEvidence, CouncilVerdict, RiskLevel } from '../types'

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? 'ws://localhost:8000'

interface ServerMessage {
  type:
    | 'tick'
    | 'council_convening'
    | 'deliberating'
    | 'verdict'
    | 'ero_fired'
    | 'council_error'
    | 'replay_complete'
    | 'error'
  zoneRisk?: Record<string, RiskLevel>
  workers?: Record<string, string>
  council?: CouncilEvidence
  verdict?: CouncilVerdict
  zoneId?: string
  deliveredOk?: boolean
  evidenceHash?: string
  firedAt?: string
  message?: string
}

/** Connects to the live-factory WebSocket (app/api/live_factory_websocket.py,
 * Step 8) for a given factory, driving the exact same Zustand store
 * actions useScenarioSocket.ts already drives. The store doesn't know
 * or care whether a tick/verdict came from a scripted scenario or a
 * real ingested factory stream; only a new socket hook speaking the
 * live-factory message shapes is needed.
 *
 * Unlike the scenario socket, this does not reconnect after a graceful
 * `replay_complete`: a CSV replay is a one-shot run, not a continuous
 * stream, and blindly reconnecting would silently re-run the same file
 * and re-convene the Council in a loop. It still reconnects with
 * backoff after an abnormal drop (network blip, backend restart),
 * matching the scenario socket's resilience for that case. */
export function useLiveFactorySocket(factoryId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!factoryId) return

    let cancelled = false
    let replayComplete = false
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let backoffMs = 1500

    const connect = () => {
      if (cancelled) return
      const ws = new WebSocket(`${WS_BASE_URL}/ws/live-factory`)
      wsRef.current = ws

      ws.onopen = () => {
        if (cancelled) return
        backoffMs = 1500 // reset backoff on a successful connection
        const store = useCorrixStore.getState()
        store.setConnectionMode('live')
        store.setLiveOverrideSender((note: string) => {
          ws.send(JSON.stringify({ type: 'override', note }))
        })
        store.beginLivePlayback()
        ws.send(JSON.stringify({ type: 'connect', factory_id: factoryId }))
      }

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data) as ServerMessage
        const store = useCorrixStore.getState()
        switch (msg.type) {
          case 'tick':
            store.applyLiveTick(msg.zoneRisk ?? {}, msg.workers ?? {})
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
          case 'council_error':
            store.applyCouncilError(msg.message ?? 'The Safety Council could not complete its deliberation.')
            break
          case 'error':
            store.applyCouncilError(msg.message ?? 'The live factory connection reported an error.')
            break
          case 'replay_complete':
            replayComplete = true
            break
        }
      }

      ws.onclose = () => {
        if (cancelled) return
        const store = useCorrixStore.getState()
        store.setConnectionMode('mock')
        store.setLiveOverrideSender(null)
        if (replayComplete) return
        reconnectTimer = setTimeout(connect, backoffMs)
        backoffMs = Math.min(backoffMs * 1.6, 10000)
      }
      ws.onerror = () => ws.close()
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [factoryId])
}
