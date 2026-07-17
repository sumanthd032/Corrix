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

const BASELINE_ZONE_RISK: Record<string, RiskLevel> = {
  Z1: 'SAFE',
  Z2: 'SAFE',
  Z3: 'SAFE',
  Z4: 'SAFE',
  Z5: 'SAFE',
  Z6: 'SAFE',
  Z7: 'SAFE',
  Z8: 'SAFE',
}

/** One mock bundle per scenario, matches the hand-crafted evidence
 * payloads and verified Chair outputs from Step 4
 * (backend/app/council/sample_payloads.py), so the shell's mock
 * behavior is consistent with what the real Council actually produces
 * for each scenario, not an arbitrary placeholder. */
interface ScenarioMock {
  zoneRisk: Record<string, RiskLevel>
  workers: WorkerMarker[]
  verdict: CouncilVerdict
  alerts: AlertFeedEntry[]
}

const SCENARIO_MOCKS: Record<string, ScenarioMock> = {
  S1: {
    zoneRisk: { ...BASELINE_ZONE_RISK, Z1: 'HIGH', Z2: 'CAUTION', Z7: 'CAUTION' },
    workers: [
      { badgeId: 'W-0142', zoneId: 'Z1', jitter: jitterFor(142) },
      { badgeId: 'W-0177', zoneId: 'Z1', jitter: jitterFor(177) },
      { badgeId: 'W-0210', zoneId: 'Z7', jitter: jitterFor(210) },
      { badgeId: 'W-0305', zoneId: 'Z3', jitter: jitterFor(305) },
      { badgeId: 'W-0417', zoneId: 'Z2', jitter: jitterFor(417) },
      { badgeId: 'W-0501', zoneId: 'Z4', jitter: jitterFor(501) },
      { badgeId: 'W-0602', zoneId: 'Z8', jitter: jitterFor(602) },
    ],
    verdict: {
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
      evacuationRoute: ['Z1', 'Z3', 'Z4'],
    },
    alerts: [
      {
        id: 'AL-F-S1-1',
        timestamp: new Date(Date.now() - 2 * 60_000).toISOString(),
        zoneId: 'Z1',
        riskLevel: 'HIGH',
        summary: 'Compound risk: active lifting permit + compliance drop + imminent changeover',
      },
      {
        id: 'AL-F-S1-2',
        timestamp: new Date(Date.now() - 14 * 60_000).toISOString(),
        zoneId: 'Z7',
        riskLevel: 'CAUTION',
        summary: 'Combustible gas trending upward, confined-space entry active',
      },
    ],
  },
  S2: {
    zoneRisk: { ...BASELINE_ZONE_RISK, Z7: 'HIGH', Z2: 'CAUTION' },
    workers: [
      { badgeId: 'W-0210', zoneId: 'Z7', jitter: jitterFor(210) },
      { badgeId: 'W-0305', zoneId: 'Z3', jitter: jitterFor(305) },
      { badgeId: 'W-0501', zoneId: 'Z4', jitter: jitterFor(501) },
      { badgeId: 'W-0602', zoneId: 'Z8', jitter: jitterFor(602) },
    ],
    verdict: {
      zoneId: 'Z7',
      scenarioId: 'S2',
      triggerReason: 'rule_threshold',
      timestamp: new Date().toISOString(),
      council: {
        processSafetyEngineer:
          'Zone 7 combustible gas at 13.8% LEL and rising, alarm threshold (10% LEL) already exceeded',
        permitControlOfficer: 'Permit P-4410 (confined_space_entry) active in Zone 7',
        shiftOperations: 'Zone 7 shift changeover begins in 5 minutes',
        siteSafetyObserver: 'Badge W-0210 entered Zone 7 approximately 2 minutes ago',
      },
      riskLevel: 'HIGH',
      confidence: 0.95,
      compoundFlag: true,
      timeToCritical: {
        medianMinutes: 9,
        iqrLowMinutes: 6,
        iqrHighMinutes: 14,
        escalationProbability: 0.74,
        horizonMinutes: 60,
      },
      explanation:
        'Rising confined-space gas, an active entry permit, an imminent changeover, and confirmed worker presence all coincide in Zone 7. This is a compound risk, not a single elevated reading.',
      recommendedAction:
        'Withdraw personnel from Zone 7 pending gas re-verification; do not begin changeover handoff until cleared.',
      evacuationRoute: ['Z7', 'Z8'],
    },
    alerts: [
      {
        id: 'AL-F-S2-1',
        timestamp: new Date(Date.now() - 3 * 60_000).toISOString(),
        zoneId: 'Z7',
        riskLevel: 'HIGH',
        summary: 'Confined-space entry during rising combustible gas, changeover imminent',
      },
    ],
  },
  S3: {
    zoneRisk: { ...BASELINE_ZONE_RISK, Z2: 'HIGH', Z3: 'CAUTION' },
    workers: [
      { badgeId: 'W-0305', zoneId: 'Z2', jitter: jitterFor(1305) },
      { badgeId: 'W-0417', zoneId: 'Z3', jitter: jitterFor(417) },
      { badgeId: 'W-0501', zoneId: 'Z4', jitter: jitterFor(501) },
    ],
    verdict: {
      zoneId: 'Z2',
      scenarioId: 'S3',
      triggerReason: 'rule_threshold',
      timestamp: new Date().toISOString(),
      council: {
        processSafetyEngineer:
          'Zone 2 combustible gas risen steadily from 2% to 12.4% LEL over 70 minutes, still climbing',
        permitControlOfficer: 'Permit P-7701 (cold_work, routine maintenance) active in Zone 2',
        shiftOperations: 'Zone 2 shift changeover begins in 20 minutes',
        siteSafetyObserver: 'Badge W-0305 present in Zone 2 for the entire maintenance window',
      },
      riskLevel: 'HIGH',
      confidence: 0.85,
      compoundFlag: true,
      timeToCritical: {
        medianMinutes: 12,
        iqrLowMinutes: 8,
        iqrHighMinutes: 18,
        escalationProbability: 0.71,
        horizonMinutes: 60,
      },
      explanation:
        'A slow, monotonic gas rise alone looks routine; combined with an active maintenance permit and continuous worker presence in the same zone, it matches the brief-named maintenance/gas co-occurrence pattern.',
      recommendedAction:
        'Suspend the maintenance permit in Zone 2 pending a fresh gas reading; do not extend the work window into changeover.',
      evacuationRoute: ['Z2', 'Z3', 'Z4'],
    },
    alerts: [
      {
        id: 'AL-F-S3-1',
        timestamp: new Date(Date.now() - 5 * 60_000).toISOString(),
        zoneId: 'Z2',
        riskLevel: 'HIGH',
        summary: 'Maintenance permit active throughout a 70-minute monotonic gas rise',
      },
    ],
  },
  S4: {
    zoneRisk: { ...BASELINE_ZONE_RISK, Z2: 'HIGH' },
    workers: [
      { badgeId: 'W-0417', zoneId: 'Z2', jitter: jitterFor(417) },
      { badgeId: 'W-0501', zoneId: 'Z4', jitter: jitterFor(501) },
    ],
    verdict: {
      zoneId: 'Z2',
      scenarioId: 'S4',
      triggerReason: 'rule_threshold',
      timestamp: new Date().toISOString(),
      council: {
        processSafetyEngineer:
          'Zone 2 gas spiked from 2% to 11.3% LEL over ~5 minutes, consistent with a discrete release, now decaying',
        permitControlOfficer: 'Permit P-9102 (hot_work) active in Zone 2, issued 10 minutes before the release',
        shiftOperations: 'Zone 2 shift changeover begins in 20 minutes',
        siteSafetyObserver: 'Badge W-0417 present in Zone 2 throughout, consistent with the active hot-work permit',
      },
      riskLevel: 'HIGH',
      confidence: 0.9,
      compoundFlag: true,
      timeToCritical: {
        medianMinutes: 6,
        iqrLowMinutes: 4,
        iqrHighMinutes: 9,
        escalationProbability: 0.66,
        horizonMinutes: 60,
      },
      explanation:
        'An active hot-work permit combined with a discrete gas release in the same zone at the same time is exactly the compound pattern the brief names. The release is already decaying, but the permit context is what makes it urgent.',
      recommendedAction:
        'Halt hot work under permit P-9102 immediately; re-verify Zone 2 atmosphere before resuming.',
      evacuationRoute: ['Z2', 'Z3', 'Z4'],
    },
    alerts: [
      {
        id: 'AL-F-S4-1',
        timestamp: new Date(Date.now() - 1 * 60_000).toISOString(),
        zoneId: 'Z2',
        riskLevel: 'HIGH',
        summary: 'Hot-work permit active during a discrete gas release in the same zone',
      },
    ],
  },
  S5: {
    zoneRisk: { ...BASELINE_ZONE_RISK, Z2: 'CAUTION' },
    workers: [{ badgeId: 'W-0512', zoneId: 'Z2', jitter: jitterFor(512) }],
    verdict: {
      zoneId: 'Z2',
      scenarioId: 'S5',
      triggerReason: 'memory_retrieval',
      timestamp: new Date().toISOString(),
      council: {
        processSafetyEngineer:
          'Zone 2 LEL reading is only mildly elevated, statistically unremarkable on its own',
        permitControlOfficer: 'No active permits currently on file for Zone 2',
        shiftOperations: 'Zone 2 shift changeover is not imminent',
        siteSafetyObserver: 'Badge W-0512 present in Zone 2',
      },
      riskLevel: 'HIGH',
      confidence: 0.74,
      compoundFlag: false,
      timeToCritical: {
        medianMinutes: 60,
        iqrLowMinutes: 60,
        iqrHighMinutes: 60,
        escalationProbability: 0.0,
        horizonMinutes: 60,
      },
      explanation:
        'No single reading crosses a threshold here, and nothing about it looks urgent in isolation. This is flagged because it closely resembles a documented past miss the memory loop stored: a slow, sub-threshold drift in this same zone that later proved to matter.',
      recommendedAction:
        'Log for review; no immediate action required, but do not dismiss the pattern match.',
      evacuationRoute: null,
    },
    alerts: [
      {
        id: 'AL-F-S5-1',
        timestamp: new Date(Date.now() - 6 * 60_000).toISOString(),
        zoneId: 'Z2',
        riskLevel: 'CAUTION',
        summary: 'Sub-threshold gas drift matched against a stored historical near-miss',
      },
    ],
  },
}

export function scenarioMock(scenarioId: string): ScenarioMock {
  return SCENARIO_MOCKS[scenarioId] ?? SCENARIO_MOCKS.S1
}

export const MOCK_CHAT_HISTORY: RegulatoryChatMessage[] = [
  {
    id: 'msg-1',
    role: 'user',
    text: 'What precautions are required for explosive or flammable gas in a factory?',
  },
  {
    id: 'msg-2',
    role: 'assistant',
    text: 'Where a manufacturing process produces dust, gas, fume, or vapour likely to explode on ignition, all practicable measures must be taken to prevent explosion: effective enclosure of plant, removal of accumulated gas, and exclusion of ignition sources.',
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
