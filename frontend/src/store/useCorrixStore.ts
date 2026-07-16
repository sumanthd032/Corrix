import { create } from 'zustand'
import type {
  AlertFeedEntry,
  CouncilStage,
  CouncilVerdict,
  RegulatoryChatMessage,
  RiskLevel,
  WorkerMarker,
} from '../types'
import {
  MOCK_ALERTS,
  MOCK_CHAT_HISTORY,
  MOCK_VERDICT,
  MOCK_WORKERS,
  MOCK_ZONE_RISK,
} from '../data/mockData'

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

export const useCorrixStore = create<CorrixState>((set) => ({
  scenarioId: 'S1',
  zoneRisk: MOCK_ZONE_RISK,
  workers: MOCK_WORKERS,
  verdict: MOCK_VERDICT,
  councilStage: 'verdict_reached',
  alerts: MOCK_ALERTS,
  chatHistory: MOCK_CHAT_HISTORY,
  overridePaused: false,
  overrideNote: '',

  setScenario: (scenarioId) => set({ scenarioId }),
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
