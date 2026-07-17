/** Mirrors backend/app/schemas, kept in sync manually until Step 9
 * wires a live WebSocket feed and these can be generated from the
 * backend's own Pydantic schemas. */

export type RiskLevel = 'SAFE' | 'CAUTION' | 'HIGH' | 'CRITICAL'
export type TriggerReason = 'rule_threshold' | 'novelty' | 'memory_retrieval'

export interface TimeToCriticalForecast {
  medianMinutes: number
  iqrLowMinutes: number
  iqrHighMinutes: number
  escalationProbability: number
  horizonMinutes: number
}

export interface CouncilEvidence {
  processSafetyEngineer: string
  permitControlOfficer: string
  shiftOperations: string
  siteSafetyObserver: string
}

export interface CouncilVerdict {
  zoneId: string
  scenarioId: string | null
  triggerReason: TriggerReason
  timestamp: string
  council: CouncilEvidence
  riskLevel: RiskLevel
  confidence: number
  compoundFlag: boolean
  timeToCritical: TimeToCriticalForecast
  explanation: string
  recommendedAction: string
  /** Ordered zone IDs from the affected zone to the nearest assembly
   * point, risk-weighted so it avoids other elevated-risk zones (Step 8).
   * Only present on HIGH/CRITICAL verdicts where a route exists. */
  evacuationRoute: string[] | null
}

export interface WorkerMarker {
  badgeId: string
  zoneId: string
  /** Deterministic per-badge jitter offset within the zone polygon, in
   * plant-meter units, so co-located workers are visually distinct. */
  jitter: [number, number]
}

export type CouncilAgentKey = keyof CouncilEvidence

export interface AlertFeedEntry {
  id: string
  timestamp: string
  zoneId: string
  riskLevel: RiskLevel
  summary: string
}

export type CouncilStage = 'idle' | 'convening' | 'deliberating' | 'verdict_reached'

export interface EroFiredEvent {
  zoneId: string
  deliveredOk: boolean
  evidenceHash: string
  firedAt: string
}

export interface RegulatoryChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  citations?: {
    framework: string
    sourceDocument: string
    sectionNumber: string
    isSupplementary: boolean
  }[]
}
