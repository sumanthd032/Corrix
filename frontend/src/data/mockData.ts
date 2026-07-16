import { PLANT_ZONES } from './plantLayout'
import type {
  AlertFeedEntry,
  CouncilVerdict,
  RegulatoryChatMessage,
  RiskLevel,
  WorkerMarker,
} from '../types'

/** Deterministic small jitter so the mock is stable across renders. */
function jitterFor(seed: number): [number, number] {
  const a = Math.sin(seed * 12.9898) * 43758.5453
  const b = Math.sin(seed * 78.233) * 12345.6789
  const frac = (n: number) => n - Math.floor(n)
  return [(frac(a) - 0.5) * 20, (frac(b) - 0.5) * 20]
}

export const MOCK_ZONE_RISK: Record<string, RiskLevel> = {
  Z1: 'HIGH',
  Z2: 'CAUTION',
  Z3: 'SAFE',
  Z4: 'SAFE',
  Z5: 'SAFE',
  Z6: 'SAFE',
  Z7: 'CAUTION',
  Z8: 'SAFE',
}

export const MOCK_WORKERS: WorkerMarker[] = [
  { badgeId: 'W-0142', zoneId: 'Z1', jitter: jitterFor(142) },
  { badgeId: 'W-0177', zoneId: 'Z1', jitter: jitterFor(177) },
  { badgeId: 'W-0210', zoneId: 'Z7', jitter: jitterFor(210) },
  { badgeId: 'W-0305', zoneId: 'Z3', jitter: jitterFor(305) },
  { badgeId: 'W-0417', zoneId: 'Z2', jitter: jitterFor(417) },
  { badgeId: 'W-0501', zoneId: 'Z4', jitter: jitterFor(501) },
  { badgeId: 'W-0602', zoneId: 'Z8', jitter: jitterFor(602) },
]

export const MOCK_VERDICT: CouncilVerdict = {
  zoneId: 'Z1',
  scenarioId: 'S1',
  triggerReason: 'rule_threshold',
  timestamp: new Date().toISOString(),
  council: {
    processSafetyEngineer: 'Gas readings 18% above baseline, rising',
    permitControlOfficer: 'Hot work permit P-2291 active in Zone 1',
    shiftOperations: 'Changeover begins in 12 minutes',
    siteSafetyObserver: 'Personnel detected in Zone 1 without a matching permit badge scan',
  },
  riskLevel: 'HIGH',
  confidence: 0.87,
  compoundFlag: true,
  timeToCritical: {
    medianMinutes: 18,
    iqrLowMinutes: 15,
    iqrHighMinutes: 22,
    escalationProbability: 0.68,
    horizonMinutes: 60,
  },
  explanation:
    'No single factor alone crosses a critical threshold. The combination matches the compound-risk pattern verified in the June 2025 Visakhapatnam Steel Plant SMS-2 investigation.',
  recommendedAction:
    'Suspend permit P-2291 pending gas verification; notify Zone 1 supervisor before shift handoff.',
}

export const MOCK_ALERTS: AlertFeedEntry[] = [
  {
    id: 'AL-F-0003',
    timestamp: new Date(Date.now() - 2 * 60_000).toISOString(),
    zoneId: 'Z1',
    riskLevel: 'HIGH',
    summary: 'Compound risk: active lifting permit + compliance drop + imminent changeover',
  },
  {
    id: 'AL-F-0002',
    timestamp: new Date(Date.now() - 14 * 60_000).toISOString(),
    zoneId: 'Z7',
    riskLevel: 'CAUTION',
    summary: 'Combustible gas trending upward, confined-space entry active',
  },
  {
    id: 'AL-F-0001',
    timestamp: new Date(Date.now() - 41 * 60_000).toISOString(),
    zoneId: 'Z2',
    riskLevel: 'SAFE',
    summary: 'Routine maintenance permit closed, no anomaly',
  },
]

export const MOCK_CHAT_HISTORY: RegulatoryChatMessage[] = [
  {
    id: 'msg-1',
    role: 'user',
    text: 'What precautions are required for explosive or flammable gas in a factory?',
  },
  {
    id: 'msg-2',
    role: 'assistant',
    text: 'Where a manufacturing process produces dust, gas, fume, or vapour likely to explode on ignition, all practicable measures must be taken to prevent explosion — effective enclosure of plant, removal of accumulated gas, and exclusion of ignition sources.',
    citations: [
      {
        framework: 'Factories_Act_1948',
        sourceDocument: 'The Factories Act, 1948',
        sectionNumber: '37',
        isSupplementary: false,
      },
    ],
  },
]

export const ZONE_IDS = PLANT_ZONES.map((z) => z.id)
