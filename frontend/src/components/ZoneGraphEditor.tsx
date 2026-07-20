import { useRef, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'

/**
 * The zone & adjacency graph editor, per CORRIX_REAL_DATA_BUILD_PLAN.md
 * Step 12: the wizard's best visual moment, and the exact input
 * `find_evacuation_route`/`predict_risk_propagation` need. Plain SVG +
 * onMouseDown/Move/Up, no new library. `zones`/`adjacency` use the
 * exact same field names as `app/schemas/zone.py`'s `Zone`/
 * `ZoneAdjacencyEdge`, so Step 13's POST needs no mapping layer;
 * `positions` is purely an editor concern and never sent to the
 * backend.
 */

export type HazardClass = 'low' | 'medium' | 'high'

export interface WizardZone {
  zone_id: string
  name: string
  hazard_class: HazardClass
  primary_role: string
  is_confined_space: boolean
  is_assembly_point: boolean
}

export interface WizardZoneAdjacencyEdge {
  zone_a: string
  zone_b: string
}

export interface ZonePosition {
  x: number
  y: number
}

const CANVAS_WIDTH = 560
const CANVAS_HEIGHT = 300
const NODE_RADIUS = 24
const PORT_OFFSET = 17
const PORT_RADIUS = 6

const HAZARD_COLOR: Record<HazardClass, string> = {
  low: 'var(--color-risk-safe)',
  medium: 'var(--color-risk-caution)',
  high: 'var(--color-risk-high)',
}

function toSvgPoint(svg: SVGSVGElement, clientX: number, clientY: number): { x: number; y: number } {
  const pt = svg.createSVGPoint()
  pt.x = clientX
  pt.y = clientY
  const ctm = svg.getScreenCTM()
  if (!ctm) return { x: clientX, y: clientY }
  const transformed = pt.matrixTransform(ctm.inverse())
  return { x: transformed.x, y: transformed.y }
}

function defaultPositionFor(index: number): ZonePosition {
  const col = index % 4
  const row = Math.floor(index / 4)
  return { x: 90 + col * 130, y: 70 + row * 100 }
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

let zoneCounter = 0

function nextZoneId(existing: WizardZone[]): string {
  zoneCounter += 1
  const candidate = `Z${zoneCounter}`
  if (existing.some((z) => z.zone_id === candidate)) return nextZoneId(existing)
  return candidate
}

export interface ZoneGraphEditorProps {
  zones: WizardZone[]
  adjacency: WizardZoneAdjacencyEdge[]
  positions: Record<string, ZonePosition>
  onChange: (next: {
    zones: WizardZone[]
    adjacency: WizardZoneAdjacencyEdge[]
    positions: Record<string, ZonePosition>
  }) => void
}

export function ZoneGraphEditor({ zones, adjacency, positions, onChange }: ZoneGraphEditorProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null)
  const [draggingZoneId, setDraggingZoneId] = useState<string | null>(null)
  const [edgeDraft, setEdgeDraft] = useState<{ from: string; pos: ZonePosition } | null>(null)

  const selectedZone = zones.find((z) => z.zone_id === selectedZoneId) ?? null

  const addZone = () => {
    const zone_id = nextZoneId(zones)
    const zone: WizardZone = {
      zone_id,
      name: `New Zone ${zones.length + 1}`,
      hazard_class: 'medium',
      primary_role: '',
      is_confined_space: false,
      is_assembly_point: false,
    }
    onChange({
      zones: [...zones, zone],
      adjacency,
      positions: { ...positions, [zone_id]: defaultPositionFor(zones.length) },
    })
    setSelectedZoneId(zone_id)
  }

  const updateZone = (zone_id: string, patch: Partial<WizardZone>) => {
    onChange({
      zones: zones.map((z) => (z.zone_id === zone_id ? { ...z, ...patch } : z)),
      adjacency,
      positions,
    })
  }

  const deleteZone = (zone_id: string) => {
    const { [zone_id]: _removed, ...restPositions } = positions
    onChange({
      zones: zones.filter((z) => z.zone_id !== zone_id),
      adjacency: adjacency.filter((e) => e.zone_a !== zone_id && e.zone_b !== zone_id),
      positions: restPositions,
    })
    setSelectedZoneId(null)
  }

  const deleteEdge = (index: number) => {
    onChange({ zones, adjacency: adjacency.filter((_, i) => i !== index), positions })
  }

  const handleNodeMouseDown = (zone_id: string) => (e: React.MouseEvent) => {
    e.stopPropagation()
    setSelectedZoneId(zone_id)
    setDraggingZoneId(zone_id)
  }

  const handlePortMouseDown = (zone_id: string) => (e: React.MouseEvent) => {
    e.stopPropagation()
    const svg = svgRef.current
    if (!svg) return
    const pos = toSvgPoint(svg, e.clientX, e.clientY)
    setEdgeDraft({ from: zone_id, pos })
  }

  const handleSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current
    if (!svg) return
    const pos = toSvgPoint(svg, e.clientX, e.clientY)

    if (draggingZoneId) {
      onChange({
        zones,
        adjacency,
        positions: {
          ...positions,
          [draggingZoneId]: {
            x: clamp(pos.x, NODE_RADIUS, CANVAS_WIDTH - NODE_RADIUS),
            y: clamp(pos.y, NODE_RADIUS, CANVAS_HEIGHT - NODE_RADIUS),
          },
        },
      })
      return
    }
    if (edgeDraft) {
      setEdgeDraft({ ...edgeDraft, pos })
    }
  }

  const handleNodeMouseUp = (zone_id: string) => (e: React.MouseEvent) => {
    e.stopPropagation()
    if (edgeDraft && edgeDraft.from !== zone_id) {
      const alreadyExists = adjacency.some(
        (edge) =>
          (edge.zone_a === edgeDraft.from && edge.zone_b === zone_id) ||
          (edge.zone_a === zone_id && edge.zone_b === edgeDraft.from),
      )
      if (!alreadyExists) {
        onChange({ zones, adjacency: [...adjacency, { zone_a: edgeDraft.from, zone_b: zone_id }], positions })
      }
    }
    setDraggingZoneId(null)
    setEdgeDraft(null)
  }

  const endInteraction = () => {
    setDraggingZoneId(null)
    setEdgeDraft(null)
  }

  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <span className="eyebrow">Zone &amp; adjacency graph</span>
          <button
            type="button"
            onClick={addZone}
            className="flex items-center gap-1 rounded-[var(--radius-control)] px-2 py-1 text-xs font-medium text-[var(--color-accent)] hover:bg-[var(--color-accent-dim)]"
          >
            <Plus size={13} aria-hidden="true" />
            Add zone
          </button>
        </div>
        <p className="mt-1 text-[11px] text-[var(--color-text-tertiary)]">
          Drag a zone to move it. Drag from the small dot to connect two zones. Click a connection to delete it.
        </p>

        <svg
          ref={svgRef}
          viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
          className="bg-blueprint-grid mt-2 w-full touch-none rounded-[var(--radius-panel)] border border-[var(--color-hairline)]"
          style={{ height: CANVAS_HEIGHT, backgroundColor: 'var(--color-surface-1)' }}
          onMouseMove={handleSvgMouseMove}
          onMouseUp={endInteraction}
          onMouseLeave={endInteraction}
        >
          {adjacency.map((edge, i) => {
            const a = positions[edge.zone_a]
            const b = positions[edge.zone_b]
            if (!a || !b) return null
            return (
              <g key={`${edge.zone_a}-${edge.zone_b}-${i}`}>
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--color-accent)" strokeWidth={1.5} opacity={0.65} />
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke="transparent"
                  strokeWidth={14}
                  className="cursor-pointer"
                  onClick={() => deleteEdge(i)}
                />
              </g>
            )
          })}

          {edgeDraft && positions[edgeDraft.from] && (
            <line
              x1={positions[edgeDraft.from].x}
              y1={positions[edgeDraft.from].y}
              x2={edgeDraft.pos.x}
              y2={edgeDraft.pos.y}
              stroke="var(--color-accent)"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              opacity={0.8}
            />
          )}

          {zones.map((zone) => {
            const pos = positions[zone.zone_id] ?? { x: 40, y: 40 }
            const isSelected = zone.zone_id === selectedZoneId
            return (
              <g key={zone.zone_id}>
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={NODE_RADIUS}
                  fill="var(--color-surface-2)"
                  stroke={isSelected ? 'var(--color-accent)' : HAZARD_COLOR[zone.hazard_class]}
                  strokeWidth={isSelected ? 2.5 : 2}
                  className="cursor-grab active:cursor-grabbing"
                  onMouseDown={handleNodeMouseDown(zone.zone_id)}
                  onMouseUp={handleNodeMouseUp(zone.zone_id)}
                />
                <text
                  x={pos.x}
                  y={pos.y}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize={10}
                  fill="var(--color-text-primary)"
                  className="pointer-events-none select-none"
                >
                  {zone.zone_id}
                </text>
                <text
                  x={pos.x}
                  y={pos.y + NODE_RADIUS + 12}
                  textAnchor="middle"
                  fontSize={9}
                  fill="var(--color-text-tertiary)"
                  className="pointer-events-none select-none"
                >
                  {zone.name.length > 16 ? `${zone.name.slice(0, 15)}…` : zone.name}
                </text>
                <circle
                  cx={pos.x + PORT_OFFSET}
                  cy={pos.y + PORT_OFFSET}
                  r={PORT_RADIUS}
                  fill="var(--color-accent)"
                  className="cursor-crosshair"
                  onMouseDown={handlePortMouseDown(zone.zone_id)}
                />
              </g>
            )
          })}
        </svg>
      </div>

      <div className="tactical-tile w-full shrink-0 p-3 sm:w-52">
        {selectedZone ? (
          <div className="flex flex-col gap-2.5">
            <div className="flex items-center justify-between">
              <span className="eyebrow">{selectedZone.zone_id}</span>
              <button
                type="button"
                onClick={() => deleteZone(selectedZone.zone_id)}
                className="rounded-[var(--radius-control)] p-1 text-[var(--color-text-tertiary)] hover:text-[var(--color-risk-critical)]"
                aria-label="Delete zone"
              >
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </div>

            <label className="block">
              <span className="text-[10px] text-[var(--color-text-tertiary)]">Name</span>
              <input
                type="text"
                value={selectedZone.name}
                onChange={(e) => updateZone(selectedZone.zone_id, { name: e.target.value })}
                className="mt-1 w-full rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-2 py-1.5 text-xs text-[var(--color-text-primary)] outline-none focus:border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)]"
              />
            </label>

            <label className="block">
              <span className="text-[10px] text-[var(--color-text-tertiary)]">Hazard class</span>
              <select
                value={selectedZone.hazard_class}
                onChange={(e) => updateZone(selectedZone.zone_id, { hazard_class: e.target.value as HazardClass })}
                className="mt-1 w-full rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-2 py-1.5 text-xs text-[var(--color-text-primary)] outline-none focus:border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)]"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>

            <label className="block">
              <span className="text-[10px] text-[var(--color-text-tertiary)]">Primary role</span>
              <input
                type="text"
                value={selectedZone.primary_role}
                onChange={(e) => updateZone(selectedZone.zone_id, { primary_role: e.target.value })}
                placeholder="e.g. casting"
                className="mt-1 w-full rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-2 py-1.5 text-xs text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-tertiary)] focus:border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)]"
              />
            </label>

            <label className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
              <input
                type="checkbox"
                checked={selectedZone.is_confined_space}
                onChange={(e) => updateZone(selectedZone.zone_id, { is_confined_space: e.target.checked })}
              />
              Confined space
            </label>
            <label className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
              <input
                type="checkbox"
                checked={selectedZone.is_assembly_point}
                onChange={(e) => updateZone(selectedZone.zone_id, { is_assembly_point: e.target.checked })}
              />
              Assembly point
            </label>
          </div>
        ) : (
          <p className="text-xs text-[var(--color-text-tertiary)]">
            {zones.length === 0 ? 'Add a zone to begin.' : 'Select a zone to edit its details.'}
          </p>
        )}
      </div>
    </div>
  )
}
