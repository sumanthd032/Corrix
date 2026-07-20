import { create } from 'zustand'
import type {
  AlertFeedEntry,
  CouncilEvidence,
  CouncilStage,
  CouncilVerdict,
  EroFiredEvent,
  RegulatoryChatMessage,
  RiskLevel,
  WorkerMarker,
} from '../types'
import { MOCK_CHAT_HISTORY, scenarioMock } from '../data/mockData'
import { jitterForBadge } from '../lib/jitter'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/** The Safety Officer Override window, in ms. Matches the backend's
 * OVERRIDE_WINDOW_SECONDS (app/api/websocket.py): the Council genuinely pauses
 * for this long between the four agents reporting and the Chair ruling, so a
 * human can veto. Surfaced as a live countdown so the pause reads as a
 * deliberate step, not lag. */
export const OVERRIDE_WINDOW_MS = 8000

type ConnectionMode = 'mock' | 'live'

interface CorrixState {
  scenarioId: string
  zoneRisk: Record<string, RiskLevel>
  workers: WorkerMarker[]
  verdict: CouncilVerdict | null
  councilStage: CouncilStage
  alerts: AlertFeedEntry[]
  chatHistory: RegulatoryChatMessage[]
  chatPending: boolean
  overridePaused: boolean
  overrideNote: string
  /** Timestamp (ms) when the live override window closes and the Chair rules,
   * or null when no window is open. Drives the override countdown. Only set in
   * live mode, where the pause is real and timed; mock-mode override waits on
   * the user, so it has no deadline. */
  deliberationDeadline: number | null
  /** Bumped when the top-bar Override control asks the Council panel to
   * bring its note field into view and focus it (used in live mode,
   * where the note is entered in the panel during the deliberation
   * window, not in a top-bar popover). */
  overrideFocusNonce: number

  connectionMode: ConnectionMode
  /** True once the live backend has connected at least once this session.
   * Lets the UI tell an initial connect (slow on the free-tier server, not a
   * failure) apart from a mid-session drop (a real problem worth flagging). */
  hasEverConnected: boolean
  liveEvidence: CouncilEvidence | null
  liveOverrideSender: ((note: string) => void) | null
  openChallengeSender: (() => void) | null
  openChallengeLabel: string | null
  eroFired: EroFiredEvent | null

  setScenario: (scenarioId: string) => void
  setCouncilStage: (stage: CouncilStage) => void
  pauseForOverride: () => void
  requestOverrideFocus: () => void
  submitOverrideNote: (note: string) => void
  sendChatMessage: (text: string) => Promise<void>
  triggerOpenChallenge: () => void

  setConnectionMode: (mode: ConnectionMode) => void
  setLiveOverrideSender: (fn: ((note: string) => void) | null) => void
  setOpenChallengeSender: (fn: (() => void) | null) => void
  setOpenChallengeLabel: (label: string | null) => void
  beginLivePlayback: () => void
  applyLiveTick: (zoneRisk: Record<string, RiskLevel>, workerZones: Record<string, string>) => void
  startLiveConvening: () => void
  applyLiveDeliberating: (evidence: CouncilEvidence) => void
  applyLiveVerdict: (verdict: CouncilVerdict) => void
  applyEroFired: (event: EroFiredEvent) => void
  applyCouncilError: (message: string) => void
}

const initialMock = scenarioMock('S1')

export const useCorrixStore = create<CorrixState>((set, get) => ({
  scenarioId: 'S1',
  zoneRisk: initialMock.zoneRisk,
  workers: initialMock.workers,
  verdict: initialMock.verdict,
  councilStage: 'verdict_reached',
  alerts: initialMock.alerts,
  chatHistory: MOCK_CHAT_HISTORY,
  chatPending: false,
  overridePaused: false,
  overrideNote: '',
  deliberationDeadline: null,
  overrideFocusNonce: 0,

  connectionMode: 'mock',
  hasEverConnected: false,
  liveEvidence: null,
  liveOverrideSender: null,
  openChallengeSender: null,
  openChallengeLabel: null,
  eroFired: null,

  setScenario: (scenarioId) => {
    if (get().connectionMode === 'live') {
      // live mode: the WebSocket hook owns state transitions once it
      // sees this change (it watches scenarioId and sends "start").
      set({ scenarioId, councilStage: 'idle', verdict: null, liveEvidence: null, overridePaused: false })
      return
    }
    const mock = scenarioMock(scenarioId)
    set({
      scenarioId,
      zoneRisk: mock.zoneRisk,
      workers: mock.workers,
      verdict: mock.verdict,
      alerts: mock.alerts,
      councilStage: 'verdict_reached',
      overridePaused: false,
    })
  },
  setCouncilStage: (stage) => set({ councilStage: stage }),
  pauseForOverride: () => {
    // In live mode the graph only actually pauses at its own real
    // interrupt point (applyLiveDeliberating, driven by the backend).
    // Manually forcing this state here would show an override control
    // with nothing real behind it to resume.
    if (get().connectionMode === 'live') return
    set({ overridePaused: true, councilStage: 'deliberating' })
  },
  requestOverrideFocus: () => set((s) => ({ overrideFocusNonce: s.overrideFocusNonce + 1 })),
  submitOverrideNote: (note) => {
    const sender = get().liveOverrideSender
    if (get().connectionMode === 'live' && sender) {
      sender(note)
      set({ overridePaused: false, overrideNote: note, deliberationDeadline: null })
      return
    }
    set((state) => ({
      overridePaused: false,
      overrideNote: note,
      councilStage: 'verdict_reached',
      verdict: state.verdict
        ? {
            ...state.verdict,
            recommendedAction: `${state.verdict.recommendedAction} (Officer note incorporated: "${note}")`,
          }
        : state.verdict,
    }))
  },
  sendChatMessage: async (text) => {
    const userMessageId = `msg-${Date.now()}-user`
    set((state) => ({
      chatHistory: [...state.chatHistory, { id: userMessageId, role: 'user', text }],
      chatPending: true,
    }))
    try {
      const response = await fetch(`${API_BASE_URL}/api/regulatory-chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text }),
      })
      if (!response.ok) throw new Error(`Regulatory chat request failed (${response.status})`)
      const data: { answer: string; citations: RegulatoryChatMessage['citations'] } =
        await response.json()
      set((state) => ({
        chatHistory: [
          ...state.chatHistory,
          { id: `${userMessageId}-reply`, role: 'assistant', text: data.answer, citations: data.citations },
        ],
        chatPending: false,
      }))
    } catch {
      set((state) => ({
        chatHistory: [
          ...state.chatHistory,
          {
            id: `${userMessageId}-error`,
            role: 'assistant',
            text: 'Could not reach the Regulatory Intelligence backend for a real answer. Confirm the backend is running and reachable, then try again.',
          },
        ],
        chatPending: false,
      }))
    }
  },
  triggerOpenChallenge: () => {
    const sender = get().openChallengeSender
    if (get().connectionMode === 'live' && sender) {
      sender()
    }
  },

  setConnectionMode: (mode) =>
    set(mode === 'live' ? { connectionMode: mode, hasEverConnected: true } : { connectionMode: mode }),
  setLiveOverrideSender: (fn) => set({ liveOverrideSender: fn }),
  setOpenChallengeSender: (fn) => set({ openChallengeSender: fn }),
  setOpenChallengeLabel: (label) => set({ openChallengeLabel: label }),
  beginLivePlayback: () =>
    set({
      verdict: null,
      liveEvidence: null,
      overridePaused: false,
      deliberationDeadline: null,
      councilStage: 'idle',
      openChallengeLabel: null,
      eroFired: null,
      // Drop the leftover mock alerts so the feed reflects this live run
      // as its own events arrive, rather than showing stale placeholders.
      alerts: [],
    }),
  applyLiveTick: (zoneRisk, workerZones) => {
    const workers: WorkerMarker[] = Object.entries(workerZones).map(([badgeId, zoneId]) => ({
      badgeId,
      zoneId,
      jitter: jitterForBadge(badgeId),
    }))
    set({ zoneRisk, workers })
  },
  startLiveConvening: () => set({ councilStage: 'convening', liveEvidence: null, verdict: null }),
  applyLiveDeliberating: (evidence) =>
    set({
      councilStage: 'deliberating',
      liveEvidence: evidence,
      overridePaused: true,
      deliberationDeadline: Date.now() + OVERRIDE_WINDOW_MS,
    }),
  applyLiveVerdict: (verdict) =>
    set((state) => ({
      councilStage: 'verdict_reached',
      verdict,
      liveEvidence: null,
      overridePaused: false,
      deliberationDeadline: null,
      alerts: [
        {
          id: `alert-verdict-${Date.now()}`,
          timestamp: new Date().toISOString(),
          zoneId: verdict.zoneId,
          riskLevel: verdict.riskLevel,
          summary: verdict.explanation,
        },
        ...state.alerts,
      ].slice(0, 20),
    })),
  applyEroFired: (event) =>
    set((state) => ({
      eroFired: event,
      alerts: [
        {
          id: `alert-ero-${Date.now()}`,
          timestamp: new Date().toISOString(),
          zoneId: event.zoneId,
          riskLevel: 'CRITICAL' as const,
          summary: event.deliveredOk
            ? `Emergency Response Orchestrator fired: a real alert was dispatched for Zone ${event.zoneId}.`
            : `Emergency Response Orchestrator fired for Zone ${event.zoneId}, but delivery failed.`,
        },
        ...state.alerts,
      ].slice(0, 20),
    })),
  applyCouncilError: (message) =>
    set((state) => ({
      councilStage: 'idle',
      overridePaused: false,
      deliberationDeadline: null,
      alerts: [
        {
          id: `alert-error-${Date.now()}`,
          timestamp: new Date().toISOString(),
          zoneId: state.verdict?.zoneId ?? state.scenarioId,
          riskLevel: 'CAUTION',
          summary: message,
        },
        ...state.alerts,
      ],
    })),
}))
