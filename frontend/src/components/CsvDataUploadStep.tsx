import { useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Download, FileText, Loader2, UploadCloud } from 'lucide-react'
import type { WizardZone } from './ZoneGraphEditor'

/**
 * Step 6 of the Bring Your Own Factory wizard, shown only when the user
 * picked "Upload historian CSV" as their data source in Review. Closes
 * the gap left after CORRIX_REAL_DATA_BUILD_PLAN.md Step 9: previously
 * the historian CSV could only reach the backend via a direct API call,
 * with no in-app upload screen. This component uploads to the real
 * `POST /api/factory/{factory_id}/csv-upload` endpoint (Step 9), using
 * the exact `column_map` shape `app/ingestion/csv_ingest.py` requires.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const GAS_TYPES = ['O2', 'CO', 'H2S', 'LEL'] as const

const LOGICAL_FIELDS = [
  { key: 'timestamp', label: 'Timestamp', required: true, hints: ['timestamp', 'ts', 'time', 'datetime'] },
  { key: 'zone', label: 'Zone ID', required: true, hints: ['zone', 'zone_id', 'zoneid'] },
  {
    key: 'gas_concentration',
    label: 'Gas concentration',
    required: true,
    hints: ['gas_concentration', 'concentration', 'conc', 'value', 'reading'],
  },
  { key: 'gas_type', label: 'Gas type', required: true, hints: ['gas_type', 'gas', 'type'] },
  { key: 'unit', label: 'Unit', required: false, hints: ['unit', 'units'] },
] as const

type LogicalKey = (typeof LOGICAL_FIELDS)[number]['key']

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

function generateSampleCsv(zones: WizardZone[]): string {
  const sampleZones = zones.length > 0 ? zones : [{ zone_id: 'Z1' } as WizardZone]
  const header = 'timestamp,zone_id,concentration,gas'
  const rows: string[] = [header]
  const gasForZone = (i: number) => GAS_TYPES[i % GAS_TYPES.length]
  const baseTime = new Date()
  baseTime.setSeconds(0, 0)
  sampleZones.forEach((zone, zi) => {
    const gas = gasForZone(zi)
    for (let i = 0; i < 6; i++) {
      const ts = new Date(baseTime.getTime() + i * 60_000).toISOString().replace(/\.\d+Z$/, 'Z')
      const jitter = (Math.sin(i + zi) * 0.4).toFixed(2)
      const baseline = gas === 'O2' ? 20.9 : gas === 'CO' ? 22 : gas === 'H2S' ? 2 : 5
      rows.push(`${ts},${zone.zone_id},${(baseline + Number(jitter)).toFixed(2)},${gas}`)
    }
  })
  return rows.join('\n') + '\n'
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

type UploadState =
  | { status: 'idle' }
  | { status: 'uploading' }
  | { status: 'error'; message: string }
  | { status: 'success'; rowsIngested: number }

export function CsvDataUploadStep({
  factoryId,
  zones,
  onUploaded,
}: {
  factoryId: string
  zones: WizardZone[]
  onUploaded: (factoryId: string) => void
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [headers, setHeaders] = useState<string[]>([])
  const [previewRows, setPreviewRows] = useState<string[][]>([])
  const [columnMap, setColumnMap] = useState<Partial<Record<LogicalKey, string>>>({})
  const [speedMultiplier, setSpeedMultiplier] = useState(30)
  const [uploadState, setUploadState] = useState<UploadState>({ status: 'idle' })
  const [parseError, setParseError] = useState<string | null>(null)

  const zoneIds = zones.map((z) => z.zone_id)

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
      const detected: Partial<Record<LogicalKey, string>> = {}
      for (const field of LOGICAL_FIELDS) {
        const match = detectColumn(parsedHeaders, field.hints)
        if (match) detected[field.key] = match
      }
      setColumnMap(detected)
    } catch {
      setParseError('Could not read this file as text. Confirm it is a plain CSV, not an Excel workbook.')
    }
  }

  const missingRequired = LOGICAL_FIELDS.filter((f) => f.required && !columnMap[f.key])
  const canUpload = file !== null && missingRequired.length === 0 && uploadState.status !== 'uploading'

  const upload = async () => {
    if (!file || !canUpload) return
    setUploadState({ status: 'uploading' })
    try {
      const map: Record<string, string> = {}
      for (const field of LOGICAL_FIELDS) {
        const column = columnMap[field.key]
        if (column) map[field.key] = column
      }
      const formData = new FormData()
      formData.append('file', file)
      formData.append('column_map', JSON.stringify(map))
      formData.append('speed_multiplier', String(speedMultiplier))

      const response = await fetch(`${API_BASE_URL}/api/factory/${factoryId}/csv-upload`, {
        method: 'POST',
        body: formData,
      })
      const body = await response.json()
      if (!response.ok) {
        setUploadState({
          status: 'error',
          message: typeof body.detail === 'string' ? body.detail : 'The upload was rejected.',
        })
        return
      }
      setUploadState({ status: 'success', rowsIngested: body.rowsIngested })
      onUploaded(factoryId)
    } catch {
      setUploadState({
        status: 'error',
        message: 'Could not reach the backend to upload the file. Confirm it is running and reachable.',
      })
    }
  }

  const sampleCsv = useMemo(() => generateSampleCsv(zones), [zones])

  return (
    <div className="flex flex-col gap-4">
      <div>
        <span className="eyebrow">Required format</span>
        <div className="tactical-tile mt-1.5 flex flex-col gap-2 p-3 text-sm">
          <p className="text-[var(--color-text-secondary)]">
            A plain CSV with a header row and one reading per row. Columns can be named anything, you'll
            map them below.
          </p>
          <ul className="flex flex-col gap-1 text-[var(--color-text-secondary)]">
            <li><b className="text-[var(--color-text-primary)]">Timestamp</b> — any format pandas can parse (e.g. <code>2026-07-21T06:00:00Z</code>)</li>
            <li>
              <b className="text-[var(--color-text-primary)]">Zone</b> — must match one of your zone IDs from
              Step 2:{' '}
              {zoneIds.length > 0 ? (
                zoneIds.map((id) => (
                  <span key={id} className="mr-1 inline-block rounded-[var(--radius-pill)] border border-[var(--color-hairline)] px-1.5 py-0.5 text-[11px]">
                    {id}
                  </span>
                ))
              ) : (
                <span className="text-[var(--color-text-tertiary)]">no zones defined yet</span>
              )}
            </li>
            <li>
              <b className="text-[var(--color-text-primary)]">Gas concentration</b> — numeric
            </li>
            <li>
              <b className="text-[var(--color-text-primary)]">Gas type</b> — one of{' '}
              {GAS_TYPES.map((g) => (
                <code key={g} className="mr-1">{g}</code>
              ))}
              (case-sensitive)
            </li>
            <li>
              <b className="text-[var(--color-text-primary)]">Unit</b> — optional, defaults to <code>ppm</code>
            </li>
          </ul>
          <button
            type="button"
            onClick={() => downloadTextFile(`${factoryId}-sample.csv`, sampleCsv)}
            className="mt-1 flex w-fit items-center gap-1.5 rounded-[var(--radius-control)] px-2 py-1 text-xs font-medium text-[var(--color-accent)] hover:bg-[var(--color-accent-dim)]"
          >
            <Download size={13} aria-hidden="true" />
            Download a sample CSV shaped for your zones
          </button>
        </div>
      </div>

      <div>
        <span className="eyebrow">Your file</span>
        <div
          className="tactical-tile mt-1.5 flex cursor-pointer flex-col items-center gap-2 border-dashed p-6 text-center"
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
              <FileText size={22} className="text-[var(--color-accent)]" aria-hidden="true" />
              <span className="text-sm text-[var(--color-text-primary)]">{file.name}</span>
              <span className="text-[11px] text-[var(--color-text-tertiary)]">Click or drop to replace</span>
            </>
          ) : (
            <>
              <UploadCloud size={22} className="text-[var(--color-text-tertiary)]" aria-hidden="true" />
              <span className="text-sm text-[var(--color-text-secondary)]">Click to choose a CSV, or drop it here</span>
            </>
          )}
        </div>
        {parseError && (
          <p className="mt-1.5 text-xs" style={{ color: 'var(--color-risk-critical)' }}>{parseError}</p>
        )}
      </div>

      {headers.length > 0 && (
        <div>
          <span className="eyebrow">Column mapping</span>
          <div className="tactical-tile mt-1.5 grid grid-cols-2 gap-3 p-3 sm:grid-cols-3">
            {LOGICAL_FIELDS.map((field) => (
              <label key={field.key} className="block">
                <span className="text-[10px] text-[var(--color-text-tertiary)]">
                  {field.label}
                  {field.required && <span style={{ color: 'var(--color-risk-critical)' }}> *</span>}
                </span>
                <select
                  value={columnMap[field.key] ?? ''}
                  onChange={(e) => setColumnMap({ ...columnMap, [field.key]: e.target.value })}
                  className="mt-1 w-full rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-2 py-1.5 text-sm text-[var(--color-text-primary)] outline-none"
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
            <div className="tactical-tile mt-2 overflow-x-auto p-2">
              <table className="w-full text-left text-[11px]">
                <thead>
                  <tr>
                    {headers.map((h) => (
                      <th key={h} className="px-2 py-1 font-medium text-[var(--color-text-tertiary)]">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row, i) => (
                    <tr key={i} className="border-t border-[var(--color-hairline)]">
                      {row.map((cell, j) => (
                        <td key={j} className="px-2 py-1 text-[var(--color-text-secondary)]">{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <label className="mt-3 block w-48">
            <span className="text-[10px] text-[var(--color-text-tertiary)]">Playback speed multiplier</span>
            <input
              type="number"
              min={1}
              value={speedMultiplier}
              onChange={(e) => setSpeedMultiplier(Number(e.target.value))}
              className="mt-1 w-full rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-2 py-1.5 text-sm text-[var(--color-text-primary)] outline-none"
            />
            <span className="mt-1 block text-[11px] text-[var(--color-text-tertiary)]">
              1x replays at the historian's real pace; 30x (default) is watchable in a live demo.
            </span>
          </label>
        </div>
      )}

      {uploadState.status === 'error' && (
        <div
          className="flex items-start gap-2 rounded-[var(--radius-control)] border px-3 py-2 text-xs"
          style={{ borderColor: 'color-mix(in srgb, var(--color-risk-critical) 45%, transparent)', color: 'var(--color-risk-critical)' }}
        >
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>{uploadState.message}</span>
        </div>
      )}

      {uploadState.status === 'success' && (
        <div
          className="flex items-center gap-2 rounded-[var(--radius-control)] border px-3 py-2 text-xs"
          style={{ borderColor: 'color-mix(in srgb, var(--color-risk-safe) 45%, transparent)', color: 'var(--color-risk-safe)' }}
        >
          <CheckCircle2 size={14} aria-hidden="true" />
          <span>{uploadState.rowsIngested} readings ingested. Entering the Live Command Center…</span>
        </div>
      )}

      <button
        type="button"
        onClick={upload}
        disabled={!canUpload}
        className="flex items-center justify-center gap-1.5 self-end rounded-[var(--radius-control)] border px-4 py-2 text-sm font-medium text-[var(--color-accent)] disabled:opacity-30"
        style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
      >
        {uploadState.status === 'uploading' ? (
          <Loader2 size={15} className="animate-spin" aria-hidden="true" />
        ) : (
          <UploadCloud size={15} aria-hidden="true" />
        )}
        {uploadState.status === 'uploading' ? 'Uploading…' : 'Upload & launch'}
      </button>
    </div>
  )
}
