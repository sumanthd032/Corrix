import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, ArrowLeft, ArrowRight, Loader2, Plus, Rocket, ShieldCheck, Trash2, Users, X } from 'lucide-react'
import {
  ZoneGraphEditor,
  type WizardZone,
  type WizardZoneAdjacencyEdge,
  type ZonePosition,
} from './ZoneGraphEditor'
import { CsvDataUploadStep } from './CsvDataUploadStep'

/**
 * The Bring Your Own Factory onboarding wizard, per
 * CORRIX_REAL_DATA_BUILD_PLAN.md Steps 11-13: identity, zones (the
 * zone/adjacency graph editor), workforce, permits, and review (POSTs
 * the assembled FactoryProfile to POST /api/factory). Five stops
 * matching CORRIX_REAL_DATA.md §2's product order, plus a sixth
 * "Upload data" stop when the user picks the CSV data source, since the
 * factory has to exist (Step 3's endpoint) before a file can be
 * attached to it (Step 9's endpoint).
 *
 * `workerCount`/`badgePrefix` are collected here per CORRIX_REAL_DATA.md
 * §2 Step 3 but have no home in FactoryProfile's persisted schema yet;
 * they inform the Virtual Sensor Panel's badge scaffolding later, not
 * this POST payload.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const INDUSTRIES = [
  { value: 'steel', label: 'Steel' },
  { value: 'chemical', label: 'Chemical' },
  { value: 'refinery', label: 'Refinery' },
  { value: 'mining', label: 'Mining' },
  { value: 'cement', label: 'Cement' },
  { value: 'other', label: 'Other' },
] as const

const PERMIT_TYPES = [
  { value: 'hot_work', label: 'Hot work' },
  { value: 'cold_work', label: 'Cold work' },
  { value: 'confined_space_entry', label: 'Confined space entry' },
  { value: 'lifting_operation', label: 'Lifting operation' },
  { value: 'electrical_isolation', label: 'Electrical isolation' },
] as const

const BASE_STEP_LABELS = ['Identity', 'Zones', 'Workforce', 'Permits', 'Review'] as const

function stepLabelsFor(dataSource: 'csv' | 'mqtt'): readonly string[] {
  return dataSource === 'csv' ? [...BASE_STEP_LABELS, 'Upload data'] : BASE_STEP_LABELS
}

export interface WizardShiftEntry {
  shiftId: string
  startTime: string
  endTime: string
  changeoverWindowMinutes: number
  zoneIds: string
}

export interface WizardData {
  name: string
  industry: string
  location: string
  zones: WizardZone[]
  adjacency: WizardZoneAdjacencyEdge[]
  zonePositions: Record<string, ZonePosition>
  workerCount: string
  badgePrefix: string
  shifts: WizardShiftEntry[]
  permitTypesInUse: string[]
  otherPermitText: string
  dataSource: 'csv' | 'mqtt'
}

const emptyShift = (): WizardShiftEntry => ({
  shiftId: `shift-${Math.random().toString(36).slice(2, 8)}`,
  startTime: '06:00',
  endTime: '14:00',
  changeoverWindowMinutes: 15,
  zoneIds: '',
})

const initialWizardData: WizardData = {
  name: '',
  industry: '',
  location: '',
  zones: [],
  adjacency: [],
  zonePositions: {},
  workerCount: '',
  badgePrefix: '',
  shifts: [emptyShift()],
  permitTypesInUse: [],
  otherPermitText: '',
  dataSource: 'csv',
}

function fieldLabelClass() {
  return 'eyebrow'
}

function inputClass() {
  return 'mt-1.5 w-full rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none transition-colors focus:border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] placeholder:text-[var(--color-text-tertiary)]'
}

function canAdvance(step: number, data: WizardData): boolean {
  if (step === 1) return data.name.trim().length > 0 && data.industry.length > 0
  if (step === 2) return data.zones.length > 0
  if (step === 3) {
    const workerCountValid = Number(data.workerCount) > 0
    const shiftsValid = data.shifts.every((s) => s.startTime && s.endTime && s.changeoverWindowMinutes > 0)
    return workerCountValid && data.badgePrefix.trim().length > 0 && data.shifts.length > 0 && shiftsValid
  }
  if (step === 4) return data.permitTypesInUse.length > 0 || data.otherPermitText.trim().length > 0
  return true
}

function StepIdentity({ data, setData }: { data: WizardData; setData: (d: WizardData) => void }) {
  return (
    <div className="flex flex-col gap-4">
      <label className="block">
        <span className={fieldLabelClass()}>Factory name</span>
        <input
          type="text"
          value={data.name}
          onChange={(e) => setData({ ...data, name: e.target.value })}
          placeholder="e.g. Rourkela Integrated Steel Plant"
          className={inputClass()}
          autoFocus
        />
      </label>

      <div>
        <span className={fieldLabelClass()}>Industry vertical</span>
        <div className="mt-1.5 grid grid-cols-2 gap-2 sm:grid-cols-3">
          {INDUSTRIES.map((ind) => (
            <button
              key={ind.value}
              type="button"
              onClick={() => setData({ ...data, industry: ind.value })}
              className="rounded-[var(--radius-control)] border px-3 py-2 text-left text-sm transition-colors"
              style={
                data.industry === ind.value
                  ? { borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)', color: 'var(--color-accent)' }
                  : { borderColor: 'var(--color-hairline)', color: 'var(--color-text-secondary)' }
              }
            >
              {ind.label}
            </button>
          ))}
        </div>
      </div>

      <label className="block">
        <span className={fieldLabelClass()}>Location (optional)</span>
        <input
          type="text"
          value={data.location}
          onChange={(e) => setData({ ...data, location: e.target.value })}
          placeholder="e.g. Rourkela, Odisha"
          className={inputClass()}
        />
      </label>
    </div>
  )
}

function StepWorkforce({ data, setData }: { data: WizardData; setData: (d: WizardData) => void }) {
  const updateShift = (index: number, patch: Partial<WizardShiftEntry>) => {
    const shifts = data.shifts.map((s, i) => (i === index ? { ...s, ...patch } : s))
    setData({ ...data, shifts })
  }
  const addShift = () => setData({ ...data, shifts: [...data.shifts, emptyShift()] })
  const removeShift = (index: number) => setData({ ...data, shifts: data.shifts.filter((_, i) => i !== index) })

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4">
        <label className="block">
          <span className={fieldLabelClass()}>Worker count</span>
          <input
            type="number"
            min={1}
            value={data.workerCount}
            onChange={(e) => setData({ ...data, workerCount: e.target.value })}
            placeholder="e.g. 120"
            className={inputClass()}
            autoFocus
          />
        </label>
        <label className="block">
          <span className={fieldLabelClass()}>Badge ID prefix</span>
          <input
            type="text"
            value={data.badgePrefix}
            onChange={(e) => setData({ ...data, badgePrefix: e.target.value })}
            placeholder="e.g. W-BG"
            className={inputClass()}
          />
        </label>
      </div>

      <div>
        <div className="flex items-center justify-between">
          <span className={fieldLabelClass()}>Shift pattern</span>
          <button
            type="button"
            onClick={addShift}
            className="flex items-center gap-1 rounded-[var(--radius-control)] px-2 py-1 text-xs font-medium text-[var(--color-accent)] hover:bg-[var(--color-accent-dim)]"
          >
            <Plus size={13} aria-hidden="true" />
            Add shift
          </button>
        </div>

        <div className="mt-2 flex flex-col gap-2">
          {data.shifts.map((shift, i) => (
            <div key={shift.shiftId} className="tactical-tile grid grid-cols-[1fr_1fr_1fr_1.4fr_auto] items-end gap-2 p-2.5">
              <label className="block">
                <span className="text-[10px] text-[var(--color-text-tertiary)]">Start</span>
                <input
                  type="time"
                  value={shift.startTime}
                  onChange={(e) => updateShift(i, { startTime: e.target.value })}
                  className={inputClass()}
                />
              </label>
              <label className="block">
                <span className="text-[10px] text-[var(--color-text-tertiary)]">End</span>
                <input
                  type="time"
                  value={shift.endTime}
                  onChange={(e) => updateShift(i, { endTime: e.target.value })}
                  className={inputClass()}
                />
              </label>
              <label className="block">
                <span className="text-[10px] text-[var(--color-text-tertiary)]">Changeover (min)</span>
                <input
                  type="number"
                  min={1}
                  value={shift.changeoverWindowMinutes}
                  onChange={(e) => updateShift(i, { changeoverWindowMinutes: Number(e.target.value) })}
                  className={inputClass()}
                />
              </label>
              <label className="block">
                <span className="text-[10px] text-[var(--color-text-tertiary)]">Zone IDs (comma-separated)</span>
                <input
                  type="text"
                  value={shift.zoneIds}
                  onChange={(e) => updateShift(i, { zoneIds: e.target.value })}
                  placeholder="assigned once zones exist"
                  className={inputClass()}
                />
              </label>
              <button
                type="button"
                onClick={() => removeShift(i)}
                disabled={data.shifts.length === 1}
                className="mb-0.5 rounded-[var(--radius-control)] p-2 text-[var(--color-text-tertiary)] hover:text-[var(--color-risk-critical)] disabled:opacity-30"
                aria-label="Remove shift"
              >
                <Trash2 size={15} aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function StepPermits({ data, setData }: { data: WizardData; setData: (d: WizardData) => void }) {
  const toggle = (value: string) => {
    const has = data.permitTypesInUse.includes(value)
    setData({
      ...data,
      permitTypesInUse: has ? data.permitTypesInUse.filter((v) => v !== value) : [...data.permitTypesInUse, value],
    })
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <span className={fieldLabelClass()}>Permit types in use</span>
        <div className="mt-1.5 flex flex-col gap-2">
          {PERMIT_TYPES.map((p) => {
            const checked = data.permitTypesInUse.includes(p.value)
            return (
              <label
                key={p.value}
                className="flex cursor-pointer items-center gap-2.5 rounded-[var(--radius-control)] border px-3 py-2 text-sm"
                style={
                  checked
                    ? { borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }
                    : { borderColor: 'var(--color-hairline)' }
                }
              >
                <input type="checkbox" checked={checked} onChange={() => toggle(p.value)} className="sr-only" />
                <ShieldCheck
                  size={15}
                  aria-hidden="true"
                  style={{ color: checked ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }}
                />
                <span style={{ color: checked ? 'var(--color-accent)' : 'var(--color-text-secondary)' }}>{p.label}</span>
              </label>
            )
          })}
        </div>
      </div>

      <label className="block">
        <span className={fieldLabelClass()}>Other (free text)</span>
        <input
          type="text"
          value={data.otherPermitText}
          onChange={(e) => setData({ ...data, otherPermitText: e.target.value })}
          placeholder="e.g. crane operation permit"
          className={inputClass()}
        />
        <span className="mt-1 block text-[11px] text-[var(--color-text-tertiary)]">
          Stored and flagged as an unmapped permit type, so the Council always receives a value it recognizes.
        </span>
      </label>
    </div>
  )
}

interface FactoryPayload {
  factory_id: string
  name: string
  industry: string
  location: string | null
  layout: { zones: WizardZone[]; adjacency: WizardZoneAdjacencyEdge[] }
  permit_types_in_use: string[]
  shift_pattern: {
    shift_id: string
    start_time: string
    end_time: string
    changeover_window_minutes: number
    zones: string[]
  }[]
  data_source: 'csv' | 'mqtt'
  created_at: string
}

function slugify(name: string): string {
  const base = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-+|-+$)/g, '')
  const suffix = Math.random().toString(36).slice(2, 8)
  return `${base || 'factory'}-${suffix}`
}

/** Combines a wizard shift's HH:MM fields with today's date into full
 * ISO datetimes, rolling the end time to the next day for an overnight
 * shift (end <= start). ShiftRecord models a single dated interval, not
 * a repeating pattern, so "today" stands in for the recurring shift's
 * reference day. */
function shiftToIsoRange(startTime: string, endTime: string): { start: string; end: string } {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const [startHour, startMinute] = startTime.split(':').map(Number)
  const start = new Date(today)
  start.setHours(startHour, startMinute, 0, 0)

  const [endHour, endMinute] = endTime.split(':').map(Number)
  const end = new Date(today)
  end.setHours(endHour, endMinute, 0, 0)
  if (end.getTime() <= start.getTime()) end.setDate(end.getDate() + 1)

  return { start: start.toISOString(), end: end.toISOString() }
}

function buildFactoryPayload(data: WizardData): FactoryPayload {
  const permit_types_in_use = [
    ...data.permitTypesInUse,
    ...(data.otherPermitText.trim() ? ['unmapped_permit_type'] : []),
  ]

  const shift_pattern = data.shifts.map((s) => {
    const { start, end } = shiftToIsoRange(s.startTime, s.endTime)
    return {
      shift_id: s.shiftId,
      start_time: start,
      end_time: end,
      changeover_window_minutes: s.changeoverWindowMinutes,
      zones: s.zoneIds
        .split(',')
        .map((z) => z.trim())
        .filter(Boolean),
    }
  })

  return {
    factory_id: slugify(data.name),
    name: data.name,
    industry: data.industry,
    location: data.location.trim() || null,
    layout: { zones: data.zones, adjacency: data.adjacency },
    permit_types_in_use,
    shift_pattern,
    data_source: data.dataSource,
    created_at: new Date().toISOString(),
  }
}

type SubmitState =
  | { status: 'idle' }
  | { status: 'submitting' }
  | { status: 'error'; message: string }
  | { status: 'created'; factoryId: string }
  | { status: 'success'; factoryId: string }

function summaryRow(label: string, value: string) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--color-hairline)] py-1.5 text-sm last:border-0">
      <span className="text-[var(--color-text-tertiary)]">{label}</span>
      <span className="text-[var(--color-text-primary)]">{value}</span>
    </div>
  )
}

function StepReview({
  data,
  onChangeDataSource,
  submitState,
}: {
  data: WizardData
  onChangeDataSource: (source: 'csv' | 'mqtt') => void
  submitState: SubmitState
}) {
  const industryLabel = INDUSTRIES.find((i) => i.value === data.industry)?.label ?? data.industry
  const permitLabels = data.permitTypesInUse
    .map((v) => PERMIT_TYPES.find((p) => p.value === v)?.label ?? v)
    .concat(data.otherPermitText.trim() ? [data.otherPermitText.trim()] : [])

  return (
    <div className="flex flex-col gap-4">
      <div>
        <span className="eyebrow">Identity</span>
        <div className="tactical-tile mt-1.5 p-3">
          {summaryRow('Name', data.name)}
          {summaryRow('Industry', industryLabel)}
          {summaryRow('Location', data.location.trim() || 'Not specified')}
        </div>
      </div>

      <div>
        <span className="eyebrow">Zones &amp; adjacency</span>
        <div className="tactical-tile mt-1.5 p-3">
          {summaryRow('Zones', String(data.zones.length))}
          {summaryRow('Adjacency edges', String(data.adjacency.length))}
        </div>
      </div>

      <div>
        <span className="eyebrow">Workforce</span>
        <div className="tactical-tile mt-1.5 p-3">
          {summaryRow('Worker count', data.workerCount || 'Not specified')}
          {summaryRow('Badge prefix', data.badgePrefix || 'Not specified')}
          {summaryRow('Shifts', String(data.shifts.length))}
        </div>
      </div>

      <div>
        <span className="eyebrow">Permits in use</span>
        <div className="tactical-tile mt-1.5 p-3">
          {permitLabels.length > 0 ? (
            summaryRow('Types', permitLabels.join(', '))
          ) : (
            summaryRow('Types', 'None selected')
          )}
        </div>
      </div>

      <div>
        <span className="eyebrow">Data source</span>
        <div className="mt-1.5 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => onChangeDataSource('csv')}
            className="rounded-[var(--radius-control)] border px-3 py-2 text-left text-sm transition-colors"
            style={
              data.dataSource === 'csv'
                ? { borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)', color: 'var(--color-accent)' }
                : { borderColor: 'var(--color-hairline)', color: 'var(--color-text-secondary)' }
            }
          >
            Upload historian CSV
          </button>
          <button
            type="button"
            onClick={() => onChangeDataSource('mqtt')}
            className="rounded-[var(--radius-control)] border px-3 py-2 text-left text-sm transition-colors"
            style={
              data.dataSource === 'mqtt'
                ? { borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)', color: 'var(--color-accent)' }
                : { borderColor: 'var(--color-hairline)', color: 'var(--color-text-secondary)' }
            }
          >
            Virtual IoT sensors (MQTT)
          </button>
        </div>
        <p className="mt-1.5 text-[11px] text-[var(--color-text-tertiary)]">
          {data.dataSource === 'mqtt'
            ? 'The Live Command Center opens with a virtual sensor panel: real MQTT messages over a real broker, from a simulated device.'
            : "Your factory will be created next, then you'll upload your historian CSV and map its columns before entering the Live Command Center."}
        </p>
      </div>

      {submitState.status === 'error' && (
        <div
          className="flex items-start gap-2 rounded-[var(--radius-control)] border px-3 py-2 text-xs"
          style={{ borderColor: 'color-mix(in srgb, var(--color-risk-critical) 45%, transparent)', color: 'var(--color-risk-critical)' }}
        >
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>{submitState.message}</span>
        </div>
      )}

      {submitState.status === 'created' && (
        <div
          className="flex items-center gap-2 rounded-[var(--radius-control)] border px-3 py-2 text-xs"
          style={{ borderColor: 'color-mix(in srgb, var(--color-risk-safe) 45%, transparent)', color: 'var(--color-risk-safe)' }}
        >
          <ShieldCheck size={14} aria-hidden="true" />
          <span>Factory {submitState.factoryId} created. Continuing to data upload…</span>
        </div>
      )}

      {submitState.status === 'success' && (
        <div
          className="flex items-center gap-2 rounded-[var(--radius-control)] border px-3 py-2 text-xs"
          style={{ borderColor: 'color-mix(in srgb, var(--color-risk-safe) 45%, transparent)', color: 'var(--color-risk-safe)' }}
        >
          <ShieldCheck size={14} aria-hidden="true" />
          <span>Factory {submitState.factoryId} created. Entering the Live Command Center…</span>
        </div>
      )}
    </div>
  )
}

export function OnboardingWizard({
  onExit,
  onLaunched,
}: {
  onExit: () => void
  onLaunched: (factoryId: string) => void
}) {
  const [step, setStep] = useState(1)
  const [data, setData] = useState<WizardData>(initialWizardData)
  const [direction, setDirection] = useState(1)
  const [submitState, setSubmitState] = useState<SubmitState>({ status: 'idle' })

  const goTo = (next: number) => {
    setDirection(next > step ? 1 : -1)
    setStep(next)
  }

  const nextEnabled = canAdvance(step, data)
  const stepLabels = stepLabelsFor(data.dataSource)
  const uploadStepNum = stepLabels.length

  const changeDataSource = (source: 'csv' | 'mqtt') => {
    if (data.dataSource === source) return
    setData({ ...data, dataSource: source })
    setSubmitState({ status: 'idle' })
  }

  const createFactory = async (): Promise<string> => {
    const response = await fetch(`${API_BASE_URL}/api/factory`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildFactoryPayload(data)),
    })
    const body = await response.json()
    if (!response.ok) {
      throw new Error(typeof body.detail === 'string' ? body.detail : 'The factory could not be created.')
    }
    return body.factoryId as string
  }

  const primaryReviewAction = async () => {
    if (submitState.status === 'submitting') return

    // Factory already created for the currently selected data source
    // (e.g. the user went Back from the upload step) — don't recreate it.
    if (data.dataSource === 'csv' && submitState.status === 'created') {
      goTo(uploadStepNum)
      return
    }

    setSubmitState({ status: 'submitting' })
    try {
      const factoryId = await createFactory()
      if (data.dataSource === 'csv') {
        setSubmitState({ status: 'created', factoryId })
        goTo(uploadStepNum)
      } else {
        setSubmitState({ status: 'success', factoryId })
        onLaunched(factoryId)
      }
    } catch (err) {
      setSubmitState({
        status: 'error',
        message:
          err instanceof Error
            ? err.message
            : 'Could not reach the backend to create the factory. Confirm it is running and reachable.',
      })
    }
  }

  const handleUploaded = (factoryId: string) => {
    setSubmitState({ status: 'success', factoryId })
    onLaunched(factoryId)
  }

  return (
    <div className="ambient-backdrop relative flex min-h-screen items-center justify-center p-4">
      <div className="glass-panel corner-frame w-full max-w-4xl p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users size={16} className="text-[var(--color-accent)]" aria-hidden="true" />
            <h2 className="font-display text-base font-semibold text-[var(--color-text-primary)]">
              Bring Your Own Factory
            </h2>
          </div>
          <button
            type="button"
            onClick={onExit}
            className="rounded-[var(--radius-control)] p-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
            aria-label="Exit onboarding"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="mt-4 flex items-center gap-1.5">
          {stepLabels.map((label, i) => {
            const stepNum = i + 1
            const active = stepNum === step
            const done = stepNum < step
            return (
              <div key={label} className="flex flex-1 flex-col items-center gap-1">
                <div
                  className="h-1 w-full rounded-[var(--radius-pill)]"
                  style={{ backgroundColor: active || done ? 'var(--color-accent)' : 'var(--color-hairline)' }}
                />
                <span
                  className="text-[10px] uppercase tracking-wide"
                  style={{ color: active ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }}
                >
                  {label}
                </span>
              </div>
            )
          })}
        </div>

        <div className="mt-5 min-h-[340px] overflow-hidden">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={step}
              custom={direction}
              initial={{ opacity: 0, x: direction * 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: direction * -24 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
            >
              {step === 1 && <StepIdentity data={data} setData={setData} />}
              {step === 2 && (
                <ZoneGraphEditor
                  zones={data.zones}
                  adjacency={data.adjacency}
                  positions={data.zonePositions}
                  onChange={({ zones, adjacency, positions }) =>
                    setData({ ...data, zones, adjacency, zonePositions: positions })
                  }
                />
              )}
              {step === 3 && <StepWorkforce data={data} setData={setData} />}
              {step === 4 && <StepPermits data={data} setData={setData} />}
              {step === 5 && (
                <StepReview data={data} onChangeDataSource={changeDataSource} submitState={submitState} />
              )}
              {step === 6 && data.dataSource === 'csv' && submitState.status !== 'idle' && submitState.status !== 'submitting' && (
                <CsvDataUploadStep
                  factoryId={submitState.status === 'created' || submitState.status === 'success' ? submitState.factoryId : ''}
                  zones={data.zones}
                  permitTypesInUse={data.permitTypesInUse}
                  badgePrefix={data.badgePrefix}
                  onUploaded={handleUploaded}
                />
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        <div className="mt-5 flex items-center justify-between">
          <button
            type="button"
            onClick={() => goTo(step - 1)}
            disabled={step === 1 || submitState.status === 'submitting'}
            className="flex items-center gap-1.5 rounded-[var(--radius-control)] px-3 py-2 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] disabled:opacity-30"
          >
            <ArrowLeft size={15} aria-hidden="true" />
            Back
          </button>
          {step === 5 ? (
            <button
              type="button"
              onClick={primaryReviewAction}
              disabled={submitState.status === 'submitting' || submitState.status === 'success'}
              className="flex items-center gap-1.5 rounded-[var(--radius-control)] border px-4 py-2 text-sm font-medium text-[var(--color-accent)] disabled:opacity-30"
              style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
            >
              {submitState.status === 'submitting' ? (
                <Loader2 size={15} className="animate-spin" aria-hidden="true" />
              ) : (
                <Rocket size={15} aria-hidden="true" />
              )}
              {submitState.status === 'submitting'
                ? 'Creating…'
                : data.dataSource === 'csv'
                  ? 'Continue to data upload'
                  : 'Launch'}
            </button>
          ) : step === 6 ? null : (
            <button
              type="button"
              onClick={() => goTo(step + 1)}
              disabled={!nextEnabled}
              className="flex items-center gap-1.5 rounded-[var(--radius-control)] border px-4 py-2 text-sm font-medium text-[var(--color-accent)] disabled:opacity-30"
              style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
            >
              Next
              <ArrowRight size={15} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
