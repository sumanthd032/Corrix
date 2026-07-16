import { create } from 'zustand'
import type {
  AlertFeedEntry,
  CouncilEvidence,
  CouncilStage,
  CouncilVerdict,
  RegulatoryChatMessage,
  RiskLevel,
  WorkerMarker,
} from '../types'
import { MOCK_CHAT_HISTORY, scenarioMock } from '../data/mockData'
import { jitterForBadge } from '../lib/jitter'

type ConnectionMode = 'mock' | 'live'

interface CorrixState {
  scenarioId: string
  zoneRisk: Record<string, RiskLevel>
  workers: WorkerMarker[]
  verdict: CouncilVerdict | null
  councilStage: CouncilStage
  alerts: AlertFeedEntry[]
  chatHistory: RegulatoryChatMessage[]
  overridePaused: boolean
  overrideNote: string

  connectionMode: ConnectionMode
  liveEvidence: CouncilEvidence | null
  liveOverrideSender: ((note: string) => void) | null
  openChallengeSender: (() => void) | null
  openChallengeLabel: string | null

  setScenario: (scenarioId: string) => void
  setCouncilStage: (stage: CouncilStage) => void
  pauseForOverride: () => void
  submitOverrideNote: (note: string) => void
  sendChatMessage: (text: string) => void
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
  overridePaused: false,
  overrideNote: '',

  connectionMode: 'mock',
  liveEvidence: null,
  liveOverrideSender: null,
  openChallengeSender: null,
  openChallengeLabel: null,

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
    // interrupt point (applyLiveDeliberating, driven by the backend) —
    // manually forcing this state here would show an override control
    // with nothing real behind it to resume.
    if (get().connectionMode === 'live') return
    set({ overridePaused: true, councilStage: 'deliberating' })
  },
  submitOverrideNote: (note) => {
    const sender = get().liveOverrideSender
    if (get().connectionMode === 'live' && sender) {
      sender(note)
      set({ overridePaused: false, overrideNote: note })
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
  sendChatMessage: (text) =>
    set((state) => ({
      chatHistory: [
        ...state.chatHistory,
        { id: `msg-${state.chatHistory.length + 1}`, role: 'user', text },
      ],
    })),
  triggerOpenChallenge: () => {
    const sender = get().openChallengeSender
    if (get().connectionMode === 'live' && sender) {
      sender()
    }
  },

  setConnectionMode: (mode) => set({ connectionMode: mode }),
  setLiveOverrideSender: (fn) => set({ liveOverrideSender: fn }),
  setOpenChallengeSender: (fn) => set({ openChallengeSender: fn }),
  setOpenChallengeLabel: (label) => set({ openChallengeLabel: label }),
  beginLivePlayback: () =>
    set({
      verdict: null,
      liveEvidence: null,
      overridePaused: false,
      councilStage: 'idle',
      openChallengeLabel: null,
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
    set({ councilStage: 'deliberating', liveEvidence: evidence, overridePaused: true }),
  applyLiveVerdict: (verdict) =>
    set({ councilStage: 'verdict_reached', verdict, liveEvidence: null, overridePaused: false }),
}))
