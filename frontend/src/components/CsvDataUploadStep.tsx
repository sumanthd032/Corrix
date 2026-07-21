import { useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Download, FileText, Loader2, SkipForward, UploadCloud } from 'lucide-react'
import type { WizardZone } from './ZoneGraphEditor'

/**
 * Step 6 of the Bring Your Own Factory wizard, shown only when the user
 * picked "Upload historian CSV" as their data source in Review. Uploads
 * to the real backend endpoints (`POST /api/factory/{factory_id}/
 * csv-upload`, `.../permit-upload`, `.../badge-upload`), using the
 * exact `column_map` shapes `app/ingestion/csv_ingest.py`,
 * `permit_ingest.py`, and `badge_ingest.py` require.
 *
 * Three data streams, not one: Corrix's pitch is gas + permit +
 * shift/badge fused into one compound-risk verdict, and the Council
 * only ever sees real permits/workers if a real PermitRecord/
 * BadgePingEvent reaches it. A factory that only uploads gas readings
 * gets a real gas signal but the Council still reports "no active
 * permits" / "no workers detected" for every convening. Gas is
 * required (it's what drives the trigger); permit and badge logs are
 * optional and skippable, since not every factory has both digitized.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const GAS_TYPES = ['O2', 'CO', 'H2S', 'LEL'] as const
const PERMIT_TYPE_VALUES = ['hot_work', 'cold_work', 'confined_space_entry', 'lifting_operation', 'electrical_isolation'] as const
const BADGE_EVENT_TYPES = ['zone_entry', 'zone_exit', 'heartbeat'] as const

interface LogicalField {
  key: string
  label: string
  required: boolean
  hints: readonly string[]
}

function splitCsvLine(line: string): string[] {
  return line.split(',').map((cell) => cell.trim())
}

function parseCsvPreview(text: string): { headers: string[]; rows: string[][] } {
  const lines = text.split(/\r\n|\n/).filter((l) => l.trim().length > 0)
  if (lines.length === 0) return { headers: [], rows: [] }
  return { headers: splitCsvLine(lines[0]), rows: lines.slice(1, 6).map(splitCsvLine) }
}

function detectColumn(headers: string[], hints: readonly string[]): string {
  const lower = headers.map((h) => h.toLowerCase())
  for (const hint of hints) {
    const idx = lower.indexOf(hint)
    if (idx !== -1) return headers[idx]
  }
  return ''
}

function downloadTextFile(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function isoAt(base: Date, offsetMinutes: number): string {
  return new Date(base.getTime() + offsetMinutes * 60_000).toISOString().replace(/\.\d+Z$/, 'Z')
}

function generateGasSampleCsv(zones: WizardZone[]): string {
  const sampleZones = zones.length > 0 ? zones : [{ zone_id: 'Z1' } as WizardZone]
  const rows: string[] = ['timestamp,zone_id,concentration,gas']
  const baseTime = new Date()
  baseTime.setSeconds(0, 0)
  sampleZones.forEach((zone, zi) => {
    const gas = GAS_TYPES[zi % GAS_TYPES.length]
    for (let i = 0; i < 6; i++) {
      const jitter = Math.sin(i + zi) * 0.4
      const baseline = gas === 'O2' ? 20.9 : gas === 'CO' ? 22 : gas === 'H2S' ? 2 : 5
      rows.push(`${isoAt(baseTime, i)},${zone.zone_id},${(baseline + jitter).toFixed(2)},${gas}`)
    }
  })
  return rows.join('\n') + '\n'
}

function generatePermitSampleCsv(zones: WizardZone[], permitTypesInUse: string[]): string {
  const sampleZones = zones.length > 0 ? zones : [{ zone_id: 'Z1' } as WizardZone]
  const types = permitTypesInUse.length > 0 ? permitTypesInUse : ['hot_work']
  const rows: string[] = ['permit_id,type,zone_id,issued_by,start_time,end_time,status']
  const baseTime = new Date()
  baseTime.setSeconds(0, 0)
  sampleZones.slice(0, 3).forEach((zone, i) => {
    const type = PERMIT_TYPE_VALUES.includes(types[i % types.length] as (typeof PERMIT_TYPE_VALUES)[number])
      ? types[i % types.length]
      : 'hot_work'
    rows.push(
      `P-${1000 + i},${type},${zone.zone_id},Shift Supervisor,${isoAt(baseTime, -5)},${isoAt(baseTime, 55)},active`,
    )
  })
  return rows.join('\n') + '\n'
}

function generateBadgeSampleCsv(zones: WizardZone[], badgePrefix: string): string {
  const sampleZones = zones.length > 0 ? zones : [{ zone_id: 'Z1' } as WizardZone]
  const prefix = badgePrefix.trim() || 'W-BG'
  const rows: string[] = ['timestamp,badge_id,zone_id,event_type']
  const baseTime = new Date()
  baseTime.setSeconds(0, 0)
  sampleZones.slice(0, 3).forEach((zone, i) => {
    const badgeId = `${prefix}-${String(i + 1).padStart(3, '0')}`
    rows.push(`${isoAt(baseTime, 0)},${badgeId},${zone.zone_id},zone_entry`)
    rows.push(`${isoAt(baseTime, 90)},${badgeId},${zone.zone_id},zone_exit`)
  })
  return rows.join('\n') + '\n'
}

type UploadState =
  | { status: 'idle' }
  | { status: 'uploading' }
  | { status: 'error'; message: string }
  | { status: 'success'; rowsIngested: number }
  | { status: 'skipped' }

function UploaderCard({
  title,
  required,
  formatSpec,
  logicalFields,
  sampleCsv,
  sampleFilename,
  endpointPath,
  speedMultiplier,
  onDone,
}: {
  title: string
  required: boolean
  formatSpec: React.ReactNode
  logicalFields: LogicalField[]
  sampleCsv: string
  sampleFilename: string
  endpointPath: string
  speedMultiplier: number
  onDone: (status: 'success' | 'skipped') => void
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [headers, setHeaders] = useState<string[]>([])
  const [previewRows, setPreviewRows] = useState<string[][]>([])
  const [columnMap, setColumnMap] = useState<Record<string, string>>({})
  const [uploadState, setUploadState] = useState<UploadState>({ status: 'idle' })
  const [parseError, setParseError] = useState<string | null>(null)

  const handleFile = async (selected: File) => {
    setParseError(null)
    setUploadState({ status: 'idle' })
    setFile(selected)
    try {
      const text = await selected.text()
      const { headers: parsedHeaders, rows } = parseCsvPreview(text)
      if (parsedHeaders.length === 0) {
        setParseError('This file has no header row. Add a header row naming each column, then re-upload.')
        setHeaders([])
        setPreviewRows([])
        setColumnMap({})
        return
      }
      setHeaders(parsedHeaders)
      setPreviewRows(rows)
      const detected: Record<string, string> = {}
      for (const field of logicalFields) {
        const match = detectColumn(parsedHeaders, field.hints)
        if (match) detected[field.key] = match
      }
      setColumnMap(detected)
    } catch {
      setParseError('Could not read this file as text. Confirm it is a plain CSV, not an Excel workbook.')
    }
  }

  const missingRequired = logicalFields.filter((f) => f.required && !columnMap[f.key])
  const canUpload = file !== null && missingRequired.length === 0 && uploadState.status !== 'uploading'

  const upload = async () => {
    if (!file || !canUpload) return
    setUploadState({ status: 'uploading' })
    try {
      const map: Record<string, string> = {}
      for (const field of logicalFields) {
        const column = columnMap[field.key]
        if (column) map[field.key] = column
      }
      const formData = new FormData()
      formData.append('file', file)
      formData.append('column_map', JSON.stringify(map))
      formData.append('speed_multiplier', String(speedMultiplier))

      const response = await fetch(`${API_BASE_URL}${endpointPath}`, { method: 'POST', body: formData })
      const body = await response.json()
      if (!response.ok) {
        setUploadState({
          status: 'error',
          message: typeof body.detail === 'string' ? body.detail : 'The upload was rejected.',
        })
        return
      }
      setUploadState({ status: 'success', rowsIngested: body.rowsIngested })
      onDone('success')
    } catch {
      setUploadState({
        status: 'error',
        message: 'Could not reach the backend to upload the file. Confirm it is running and reachable.',
      })
    }
  }

  const done = uploadState.status === 'success' || uploadState.status === 'skipped'

  return (
    <div className="tactical-tile flex flex-col gap-3 p-3.5" style={done ? { opacity: 0.65 } : undefined}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-[var(--color-text-primary)]">{title}</span>
          {required ? (
            <span className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--color-risk-critical)' }}>Required</span>
          ) : (
            <span className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">Optional</span>
          )}
        </div>
        {!required && !done && (
          <button
            type="button"
            onClick={() => {
              setUploadState({ status: 'skipped' })
              onDone('skipped')
            }}
            className="flex items-center gap-1 rounded-[var(--radius-control)] px-2 py-1 text-xs text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
          >
            <SkipForward size={12} aria-hidden="true" />
            I don't have this data
          </button>
        )}
      </div>

      {!done && (
        <>
          <div className="text-xs text-[var(--color-text-secondary)]">{formatSpec}</div>
          <button
            type="button"
            onClick={() => downloadTextFile(sampleFilename, sampleCsv)}
            className="flex w-fit items-center gap-1.5 rounded-[var(--radius-control)] px-2 py-1 text-xs font-medium text-[var(--color-accent)] hover:bg-[var(--color-accent-dim)]"
          >
            <Download size={13} aria-hidden="true" />
            Download a sample shaped for your factory
          </button>

          <div
            className="flex cursor-pointer flex-col items-center gap-1.5 rounded-[var(--radius-control)] border border-dashed border-[var(--color-hairline)] p-4 text-center"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              const dropped = e.dataTransfer.files?.[0]
              if (dropped) void handleFile(dropped)
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => {
                const selected = e.target.files?.[0]
                if (selected) void handleFile(selected)
              }}
            />
            {file ? (
              <>
                <FileText size={18} className="text-[var(--color-accent)]" aria-hidden="true" />
                <span className="text-xs text-[var(--color-text-primary)]">{file.name}</span>
                <span className="text-[10px] text-[var(--color-text-tertiary)]">Click or drop to replace</span>
              </>
            ) : (
              <>
                <UploadCloud size={18} className="text-[var(--color-text-tertiary)]" aria-hidden="true" />
                <span className="text-xs text-[var(--color-text-secondary)]">Click to choose a CSV, or drop it here</span>
              </>
            )}
          </div>
          {parseError && (
            <p className="text-xs" style={{ color: 'var(--color-risk-critical)' }}>{parseError}</p>
          )}

          {headers.length > 0 && (
            <>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {logicalFields.map((field) => (
                  <label key={field.key} className="block">
                    <span className="text-[10px] text-[var(--color-text-tertiary)]">
                      {field.label}
                      {field.required && <span style={{ color: 'var(--color-risk-critical)' }}> *</span>}
                    </span>
                    <select
                      value={columnMap[field.key] ?? ''}
                      onChange={(e) => setColumnMap({ ...columnMap, [field.key]: e.target.value })}
                      className="mt-1 w-full rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-2 py-1.5 text-xs text-[var(--color-text-primary)] outline-none"
                    >
                      <option value="">{field.required ? 'Select a column' : 'None'}</option>
                      {headers.map((h) => (
                        <option key={h} value={h}>{h}</option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>

              {previewRows.length > 0 && (
                <div className="overflow-x-auto rounded-[var(--radius-control)] border border-[var(--color-hairline)] p-1.5">
                  <table className="w-full text-left text-[10px]">
                    <thead>
                      <tr>
                        {headers.map((h) => (
                          <th key={h} className="px-1.5 py-1 font-medium text-[var(--color-text-tertiary)]">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {previewRows.map((row, i) => (
                        <tr key={i} className="border-t border-[var(--color-hairline)]">
                          {row.map((cell, j) => (
                            <td key={j} className="px-1.5 py-1 text-[var(--color-text-secondary)]">{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {uploadState.status === 'error' && (
            <div
              className="flex items-start gap-2 rounded-[var(--radius-control)] border px-2.5 py-2 text-xs"
              style={{ borderColor: 'color-mix(in srgb, var(--color-risk-critical) 45%, transparent)', color: 'var(--color-risk-critical)' }}
            >
              <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span>{uploadState.message}</span>
            </div>
          )}

          <button
            type="button"
            onClick={upload}
            disabled={!canUpload}
            className="flex items-center justify-center gap-1.5 self-end rounded-[var(--radius-control)] border px-3 py-1.5 text-xs font-medium text-[var(--color-accent)] disabled:opacity-30"
            style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
          >
            {uploadState.status === 'uploading' ? (
              <Loader2 size={13} className="animate-spin" aria-hidden="true" />
            ) : (
              <UploadCloud size={13} aria-hidden="true" />
            )}
            {uploadState.status === 'uploading' ? 'Uploading…' : 'Upload'}
          </button>
        </>
      )}

      {uploadState.status === 'success' && (
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-risk-safe)' }}>
          <CheckCircle2 size={13} aria-hidden="true" />
          <span>{uploadState.rowsIngested} rows uploaded.</span>
        </div>
      )}
      {uploadState.status === 'skipped' && (
        <div className="flex items-center gap-2 text-xs text-[var(--color-text-tertiary)]">
          <SkipForward size={13} aria-hidden="true" />
          <span>Skipped — the Council will report no data for this signal until you add it later.</span>
        </div>
      )}
    </div>
  )
}

export function CsvDataUploadStep({
  factoryId,
  zones,
  permitTypesInUse,
  badgePrefix,
  onUploaded,
}: {
  factoryId: string
  zones: WizardZone[]
  permitTypesInUse: string[]
  badgePrefix: string
  onUploaded: (factoryId: string) => void
}) {
  const [speedMultiplier, setSpeedMultiplier] = useState(30)
  const [gasDone, setGasDone] = useState(false)
  const [permitDone, setPermitDone] = useState(false)
  const [badgeDone, setBadgeDone] = useState(false)

  const zoneIds = zones.map((z) => z.zone_id)
  const gasSample = useMemo(() => generateGasSampleCsv(zones), [zones])
  const permitSample = useMemo(() => generatePermitSampleCsv(zones, permitTypesInUse), [zones, permitTypesInUse])
  const badgeSample = useMemo(() => generateBadgeSampleCsv(zones, badgePrefix), [zones, badgePrefix])

  const allDone = gasDone && permitDone && badgeDone

  const zoneChips =
    zoneIds.length > 0 ? (
      zoneIds.map((id) => (
        <span key={id} className="mr-1 inline-block rounded-[var(--radius-pill)] border border-[var(--color-hairline)] px-1.5 py-0.5 text-[11px]">
          {id}
        </span>
      ))
    ) : (
      <span className="text-[var(--color-text-tertiary)]">no zones defined yet</span>
    )

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-[var(--color-text-secondary)]">
        Corrix fuses three signals into one compound-risk verdict: gas readings, active permits, and who's
        in each zone. Upload each stream your factory tracks below — gas is required to drive the live
        feed, the other two are optional but make every verdict reflect your real permits and real
        workforce instead of "no data on file."
      </p>

      <label className="block w-56">
        <span className="text-[10px] text-[var(--color-text-tertiary)]">Playback speed multiplier (applies to all uploads)</span>
        <input
          type="number"
          min={1}
          value={speedMultiplier}
          onChange={(e) => setSpeedMultiplier(Number(e.target.value))}
          className="mt-1 w-full rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-2 py-1.5 text-sm text-[var(--color-text-primary)] outline-none"
        />
        <span className="mt-1 block text-[11px] text-[var(--color-text-tertiary)]">
          1x replays at real historian pace; 30x (default) is watchable in a live demo. Keep it the same
          across all three uploads so gas, permit, and badge events stay correlated in time.
        </span>
      </label>

      <UploaderCard
        title="Gas readings"
        required
        formatSpec={
          <ul className="flex flex-col gap-1">
            <li><b className="text-[var(--color-text-primary)]">Timestamp</b> — any format pandas can parse</li>
            <li><b className="text-[var(--color-text-primary)]">Zone</b> — must match one of: {zoneChips}</li>
            <li><b className="text-[var(--color-text-primary)]">Gas concentration</b> — numeric</li>
            <li><b className="text-[var(--color-text-primary)]">Gas type</b> — one of {GAS_TYPES.map((g) => <code key={g} className="mr-1">{g}</code>)} (case-sensitive)</li>
            <li><b className="text-[var(--color-text-primary)]">Unit</b> — optional, defaults to <code>ppm</code></li>
          </ul>
        }
        logicalFields={[
          { key: 'timestamp', label: 'Timestamp', required: true, hints: ['timestamp', 'ts', 'time', 'datetime'] },
          { key: 'zone', label: 'Zone ID', required: true, hints: ['zone', 'zone_id', 'zoneid'] },
          { key: 'gas_concentration', label: 'Gas concentration', required: true, hints: ['gas_concentration', 'concentration', 'conc', 'value', 'reading'] },
          { key: 'gas_type', label: 'Gas type', required: true, hints: ['gas_type', 'gas', 'type'] },
          { key: 'unit', label: 'Unit', required: false, hints: ['unit', 'units'] },
        ]}
        sampleCsv={gasSample}
        sampleFilename={`${factoryId}-gas-sample.csv`}
        endpointPath={`/api/factory/${factoryId}/csv-upload`}
        speedMultiplier={speedMultiplier}
        onDone={() => setGasDone(true)}
      />

      <UploaderCard
        title="Permit log"
        required={false}
        formatSpec={
          <ul className="flex flex-col gap-1">
            <li><b className="text-[var(--color-text-primary)]">Permit ID</b> — any unique string</li>
            <li><b className="text-[var(--color-text-primary)]">Type</b> — one of {PERMIT_TYPE_VALUES.map((t) => <code key={t} className="mr-1">{t}</code>)}</li>
            <li><b className="text-[var(--color-text-primary)]">Zone</b> — must match one of: {zoneChips}</li>
            <li><b className="text-[var(--color-text-primary)]">Issued by</b> — free text</li>
            <li><b className="text-[var(--color-text-primary)]">Start time / End time</b> — any format pandas can parse</li>
            <li><b className="text-[var(--color-text-primary)]">Status</b> — one of <code>active</code>, <code>closed</code>, <code>suspended</code></li>
          </ul>
        }
        logicalFields={[
          { key: 'permit_id', label: 'Permit ID', required: true, hints: ['permit_id', 'id', 'permit'] },
          { key: 'type', label: 'Type', required: true, hints: ['type', 'permit_type'] },
          { key: 'zone', label: 'Zone ID', required: true, hints: ['zone', 'zone_id', 'zoneid'] },
          { key: 'issued_by', label: 'Issued by', required: true, hints: ['issued_by', 'issuer', 'issued by'] },
          { key: 'start_time', label: 'Start time', required: true, hints: ['start_time', 'start', 'starttime'] },
          { key: 'end_time', label: 'End time', required: true, hints: ['end_time', 'end', 'endtime'] },
          { key: 'status', label: 'Status', required: true, hints: ['status', 'state'] },
          { key: 'linked_checklist_id', label: 'Checklist ID', required: false, hints: ['linked_checklist_id', 'checklist', 'checklist_id'] },
        ]}
        sampleCsv={permitSample}
        sampleFilename={`${factoryId}-permits-sample.csv`}
        endpointPath={`/api/factory/${factoryId}/permit-upload`}
        speedMultiplier={speedMultiplier}
        onDone={() => setPermitDone(true)}
      />

      <UploaderCard
        title="Badge / turnstile log"
        required={false}
        formatSpec={
          <ul className="flex flex-col gap-1">
            <li><b className="text-[var(--color-text-primary)]">Timestamp</b> — any format pandas can parse</li>
            <li><b className="text-[var(--color-text-primary)]">Badge ID</b> — any string</li>
            <li><b className="text-[var(--color-text-primary)]">Zone</b> — must match one of: {zoneChips}</li>
            <li><b className="text-[var(--color-text-primary)]">Event type</b> — one of {BADGE_EVENT_TYPES.map((e) => <code key={e} className="mr-1">{e}</code>)}</li>
          </ul>
        }
        logicalFields={[
          { key: 'timestamp', label: 'Timestamp', required: true, hints: ['timestamp', 'ts', 'time', 'datetime'] },
          { key: 'badge_id', label: 'Badge ID', required: true, hints: ['badge_id', 'badge', 'badgeid'] },
          { key: 'zone', label: 'Zone ID', required: true, hints: ['zone', 'zone_id', 'zoneid'] },
          { key: 'event_type', label: 'Event type', required: true, hints: ['event_type', 'event', 'eventtype'] },
        ]}
        sampleCsv={badgeSample}
        sampleFilename={`${factoryId}-badges-sample.csv`}
        endpointPath={`/api/factory/${factoryId}/badge-upload`}
        speedMultiplier={speedMultiplier}
        onDone={() => setBadgeDone(true)}
      />

      <button
        type="button"
        onClick={() => onUploaded(factoryId)}
        disabled={!allDone}
        className="flex items-center justify-center gap-1.5 self-end rounded-[var(--radius-control)] border px-4 py-2 text-sm font-medium text-[var(--color-accent)] disabled:opacity-30"
        style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
      >
        <CheckCircle2 size={15} aria-hidden="true" />
        Enter the Live Command Center
      </button>
    </div>
  )
}
