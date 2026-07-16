import { create } from 'zustand'
import type {
  AlertFeedEntry,
  CouncilStage,
  CouncilVerdict,
  RegulatoryChatMessage,
  RiskLevel,
  WorkerMarker,
} from '../types'
import { MOCK_CHAT_HISTORY, scenarioMock } from '../data/mockData'

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

  setScenario: (scenarioId: string) => void
  setCouncilStage: (stage: CouncilStage) => void
  pauseForOverride: () => void
  submitOverrideNote: (note: string) => void
  sendChatMessage: (text: string) => void
}

const initialMock = scenarioMock('S1')

export const useCorrixStore = create<CorrixState>((set) => ({
  scenarioId: 'S1',
  zoneRisk: initialMock.zoneRisk,
  workers: initialMock.workers,
  verdict: initialMock.verdict,
  councilStage: 'verdict_reached',
  alerts: initialMock.alerts,
  chatHistory: MOCK_CHAT_HISTORY,
  overridePaused: false,
  overrideNote: '',

  setScenario: (scenarioId) => {
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
  pauseForOverride: () => set({ overridePaused: true, councilStage: 'deliberating' }),
  submitOverrideNote: (note) =>
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
    })),
  sendChatMessage: (text) =>
    set((state) => ({
      chatHistory: [
        ...state.chatHistory,
        { id: `msg-${state.chatHistory.length + 1}`, role: 'user', text },
      ],
    })),
}))
