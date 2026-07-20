import { useEffect, useMemo, useRef, useState } from 'react'
import DeckGL from '@deck.gl/react'
import { OrthographicView } from '@deck.gl/core'
import { LineLayer, PathLayer, PolygonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import { Box, Boxes, Radar, Square, Users } from 'lucide-react'
import { PLANT_ZONES, ZONE_BOUNDS } from '../data/plantLayout'
import { useCorrixStore } from '../store/useCorrixStore'
import { riskColorHex, zoneFillHex } from './RiskBadge'
import { PlantScene3D } from './PlantScene3D'
import type { RiskLevel } from '../types'

type ViewMode = 'flat' | 'isometric' | '3d'

const VIEW_MODES: { mode: ViewMode; label: string; Icon: typeof Square }[] = [
  { mode: 'flat', label: 'Flat', Icon: Square },
  { mode: 'isometric', label: 'Isometric', Icon: Box },
  { mode: '3d', label: '3D', Icon: Boxes },
]

/**
 * Colorblind-safe shape glyphs, one per risk level, checked against a
 * deuteranopia/protanopia simulation. The map is otherwise pure fill, so
 * it carries its own shape cue independent of the side-panel RiskBadge.
 * Rendered via TextLayer so it lives inside deck.gl's own canvas.
 */
const RISK_GLYPH: Record<RiskLevel, string> = {
  SAFE: '●',
  CAUTION: '▲',
  HIGH: '◆',
  CRITICAL: '■',
}

/** A margin of plant-meters padded around the zone bounds so the facility
 * footprint reads as ground the zones sit on, not a tight crop. */
const FOOTPRINT_PAD = 18
const FOOTPRINT: [number, number][] = [
  [ZONE_BOUNDS.minX - FOOTPRINT_PAD, ZONE_BOUNDS.minY - FOOTPRINT_PAD],
  [ZONE_BOUNDS.maxX + FOOTPRINT_PAD, ZONE_BOUNDS.minY - FOOTPRINT_PAD],
  [ZONE_BOUNDS.maxX + FOOTPRINT_PAD, ZONE_BOUNDS.maxY + FOOTPRINT_PAD],
  [ZONE_BOUNDS.minX - FOOTPRINT_PAD, ZONE_BOUNDS.maxY + FOOTPRINT_PAD],
]

const INITIAL_VIEW_STATE = {
  target: [
    (ZONE_BOUNDS.minX + ZONE_BOUNDS.maxX) / 2,
    (ZONE_BOUNDS.minY + ZONE_BOUNDS.maxY) / 2,
    0,
  ] as [number, number, number],
  zoom: 1.5,
}

/** Short, screen-legible labels for the schematic. The full facility
 * names (in plantLayout) are too long to sit inside a 50-unit cell
 * without overrunning into the next one; these keep the plant readable. */
const ZONE_SHORT_NAME: Record<string, string> = {
  Z1: 'Ladle Bay',
  Z2: 'Gas Main',
  Z3: 'Maintenance',
  Z4: 'Control Rm',
  Z5: 'Scrap Yard',
  Z6: 'Quench Pit',
  Z7: 'Gas Vault',
  Z8: 'Perimeter',
}

/** Isometric mode is a CSS transform on the canvas wrapper, additive. */
const ISOMETRIC_TRANSFORM = 'rotateX(55deg) rotateZ(-45deg) scale(0.86)'

const DISPERSION_RISK_LEVELS: RiskLevel[] = ['HIGH', 'CRITICAL']
const PARTICLES_PER_ZONE = 14
const PARTICLE_CYCLE_MS = 3200
const PULSE_PERIOD_SECONDS = 1.4
const ROUTE_DRAW_IN_MS = 1100

interface GasParticleSeed {
  angle: number
  maxDistance: number
  phaseMs: number
}

function buildGasParticles(zoneId: string): GasParticleSeed[] {
  let seed = 0
  for (let i = 0; i < zoneId.length; i++) {
    seed = (seed * 31 + zoneId.charCodeAt(i)) >>> 0
  }
  const next = () => {
    seed = (seed * 1103515245 + 12345) >>> 0
    return (seed >>> 8) / 0xffffff
  }
  return Array.from({ length: PARTICLES_PER_ZONE }, (_, i) => ({
    angle: next() * Math.PI * 2,
    maxDistance: 10 + next() * 14,
    phaseMs: (i / PARTICLES_PER_ZONE) * PARTICLE_CYCLE_MS + next() * 400,
  }))
}

function interpolatePath(
  points: [number, number][],
  progress: number,
): [number, number][] {
  if (points.length < 2 || progress >= 1) return points
  if (progress <= 0) return [points[0]]

  const segmentLengths: number[] = []
  let total = 0
  for (let i = 1; i < points.length; i++) {
    const [x0, y0] = points[i - 1]
    const [x1, y1] = points[i]
    const len = Math.hypot(x1 - x0, y1 - y0)
    segmentLengths.push(len)
    total += len
  }

  const target = total * progress
  const result: [number, number][] = [points[0]]
  let covered = 0
  for (let i = 0; i < segmentLengths.length; i++) {
    const segLen = segmentLengths[i]
    if (covered + segLen >= target) {
      const t = segLen === 0 ? 0 : (target - covered) / segLen
      const [x0, y0] = points[i]
      const [x1, y1] = points[i + 1]
      result.push([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t])
      return result
    }
    covered += segLen
    result.push(points[i + 1])
  }
  return result
}

const RISK_ORDER: Record<RiskLevel, number> = { SAFE: 0, CAUTION: 1, HIGH: 2, CRITICAL: 3 }

export function PlantHeatmap() {
  const zoneRisk = useCorrixStore((s) => s.zoneRisk)
  const workers = useCorrixStore((s) => s.workers)
  const evacuationRoute = useCorrixStore((s) => s.verdict?.evacuationRoute ?? null)
  const riskPropagation = useCorrixStore((s) => s.verdict?.riskPropagation ?? null)
  const propagationSourceId = useCorrixStore((s) => s.verdict?.zoneId ?? null)
  const [viewMode, setViewMode] = useState<ViewMode>('flat')
  const [now, setNow] = useState(() => performance.now())

  const elevatedCount = useMemo(
    () => PLANT_ZONES.filter((z) => RISK_ORDER[zoneRisk[z.id] ?? 'SAFE'] >= 2).length,
    [zoneRisk],
  )

  const activeRiskZones = useMemo(
    () => PLANT_ZONES.filter((z) => DISPERSION_RISK_LEVELS.includes(zoneRisk[z.id] ?? 'SAFE')),
    [zoneRisk],
  )
  const activeRiskZoneIds = useMemo(
    () => new Set(activeRiskZones.map((z) => z.id)),
    [activeRiskZones],
  )
  const gasParticleFields = useMemo(
    () => new Map(activeRiskZones.map((z) => [z.id, buildGasParticles(z.id)])),
    [activeRiskZones],
  )

  const routeKey = evacuationRoute ? evacuationRoute.join('>') : null
  const routeStartRef = useRef<number | null>(null)
  const prevRouteKeyRef = useRef<string | null>(null)

  useEffect(() => {
    if (routeKey !== prevRouteKeyRef.current) {
      prevRouteKeyRef.current = routeKey
      routeStartRef.current = routeKey ? performance.now() : null
    }
  }, [routeKey])

  useEffect(() => {
    if (activeRiskZoneIds.size === 0 && routeKey === null) return undefined
    let raf = 0
    let cancelled = false
    const tick = (t: number) => {
      if (cancelled) return
      setNow(t)
      const routeDrawing =
        routeStartRef.current != null && t - routeStartRef.current < ROUTE_DRAW_IN_MS
      if (activeRiskZoneIds.size > 0 || routeDrawing) {
        raf = requestAnimationFrame(tick)
      }
    }
    raf = requestAnimationFrame(tick)
    return () => {
      cancelled = true
      cancelAnimationFrame(raf)
    }
  }, [activeRiskZoneIds, routeKey])

  const pulse =
    activeRiskZoneIds.size > 0
      ? 0.5 + 0.5 * Math.sin((now / 1000) * ((2 * Math.PI) / PULSE_PERIOD_SECONDS))
      : 0

  // The facility footprint the zones sit on: a dark plant floor with a
  // faint accent hairline, so zones read as cells in a facility rather
  // than colored rectangles floating in empty space.
  const footprintLayer = useMemo(
    () =>
      new PolygonLayer({
        id: 'facility-footprint',
        data: [FOOTPRINT],
        getPolygon: (d) => d,
        getFillColor: [10, 15, 21, 235],
        getLineColor: [45, 212, 232, 55],
        getLineWidth: 1.5,
        lineWidthUnits: 'pixels',
        filled: true,
        stroked: true,
      }),
    [],
  )

  const zoneLayer = useMemo(
    () =>
      new PolygonLayer({
        id: 'zones',
        data: PLANT_ZONES,
        getPolygon: (z) => z.polygon,
        getFillColor: (z) => zoneFillHex(zoneRisk[z.id] ?? 'SAFE'),
        getLineColor: (z) => {
          const level = zoneRisk[z.id] ?? 'SAFE'
          if (!activeRiskZoneIds.has(z.id)) {
            // nominal zones: dim hairline; a faint risk tint for CAUTION
            if (level === 'CAUTION') {
              const [r, g, b] = riskColorHex(level)
              return [r, g, b, 150]
            }
            return [125, 162, 194, 90]
          }
          const [r, g, b] = riskColorHex(level)
          return [r, g, b, Math.round(180 + pulse * 75)]
        },
        getLineWidth: (z) => (activeRiskZoneIds.has(z.id) ? 2 + pulse * 3 : 1),
        lineWidthUnits: 'pixels',
        filled: true,
        stroked: true,
        pickable: true,
        updateTriggers: {
          getFillColor: [zoneRisk],
          getLineColor: [zoneRisk, activeRiskZoneIds, pulse],
          getLineWidth: [activeRiskZoneIds, pulse],
        },
        transitions: {
          getFillColor: { duration: 600, easing: (t: number) => t * (2 - t) },
        },
      }),
    [zoneRisk, activeRiskZoneIds, pulse],
  )

  const gasLayer = useMemo(() => {
    if (activeRiskZones.length === 0) return null
    const points = activeRiskZones.flatMap((zone) => {
      const field = gasParticleFields.get(zone.id) ?? []
      return field.map((p) => {
        const t = (now + p.phaseMs) % PARTICLE_CYCLE_MS
        const progress = t / PARTICLE_CYCLE_MS
        const distance = progress * p.maxDistance
        const alpha = Math.round((1 - progress) * 150)
        return {
          position: [
            zone.centroid[0] + Math.cos(p.angle) * distance,
            zone.centroid[1] + Math.sin(p.angle) * distance,
          ] as [number, number],
          color: [224, 224, 96, alpha] as [number, number, number, number],
          radius: 1.2 + progress * 2.8,
        }
      })
    })

    return new ScatterplotLayer({
      id: 'gas-dispersion',
      data: points,
      getPosition: (d) => d.position,
      getFillColor: (d) => d.color,
      getRadius: (d) => d.radius,
      radiusUnits: 'meters',
      stroked: false,
      pickable: false,
    })
  }, [activeRiskZones, gasParticleFields, now])

  // Zone ID, in a bold mono, anchored to each cell's top-left corner.
  const zoneIdLayer = useMemo(
    () =>
      new TextLayer({
        id: 'zone-ids',
        data: PLANT_ZONES,
        getPosition: (z) => [z.polygon[0][0] + 4, z.polygon[0][1] + 5] as [number, number],
        getText: (z) => z.id,
        getSize: 12,
        getColor: (z) => {
          const level = zoneRisk[z.id] ?? 'SAFE'
          if (RISK_ORDER[level] >= 1) return [...riskColorHex(level).slice(0, 3), 255] as unknown as [number, number, number, number]
          return [201, 216, 232, 220]
        },
        fontFamily: 'IBM Plex Mono, monospace',
        fontWeight: 700,
        getTextAnchor: 'start',
        getAlignmentBaseline: 'top',
        updateTriggers: { getColor: [zoneRisk] },
      }),
    [zoneRisk],
  )

  // Short zone name, small and dim, just under the ID, so the schematic
  // names the facility without overrunning the cell.
  const zoneNameLayer = useMemo(
    () =>
      new TextLayer({
        id: 'zone-names',
        data: PLANT_ZONES,
        getPosition: (z) => [z.polygon[0][0] + 4, z.polygon[0][1] + 16] as [number, number],
        getText: (z) => (ZONE_SHORT_NAME[z.id] ?? z.name).toUpperCase(),
        getSize: 9,
        sizeUnits: 'pixels',
        getColor: [147, 166, 187, 200],
        fontFamily: 'IBM Plex Mono, monospace',
        getTextAnchor: 'start',
        getAlignmentBaseline: 'top',
      }),
    [],
  )

  const zoneRiskGlyphLayer = useMemo(
    () =>
      new TextLayer({
        id: 'zone-risk-glyphs',
        data: PLANT_ZONES,
        getPosition: (z) => [z.centroid[0], z.centroid[1] + 6] as [number, number],
        getText: (z) => RISK_GLYPH[zoneRisk[z.id] ?? 'SAFE'],
        getSize: 22,
        getColor: (z) => {
          const level = zoneRisk[z.id] ?? 'SAFE'
          if (level === 'SAFE') return [91, 111, 130, 220]
          return [...riskColorHex(level).slice(0, 3), 255] as unknown as [number, number, number, number]
        },
        fontWeight: 700,
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'center',
        characterSet: Object.values(RISK_GLYPH),
        updateTriggers: {
          getText: [zoneRisk],
          getColor: [zoneRisk],
        },
      }),
    [zoneRisk],
  )

  const workerLayer = useMemo(() => {
    const zoneById = new Map(PLANT_ZONES.map((z) => [z.id, z]))
    const positioned = workers
      .map((w) => {
        const zone = zoneById.get(w.zoneId)
        if (!zone) return null
        return {
          ...w,
          position: [
            zone.centroid[0] + w.jitter[0],
            zone.centroid[1] + w.jitter[1],
          ] as [number, number],
        }
      })
      .filter((w): w is NonNullable<typeof w> => w !== null)

    return new ScatterplotLayer({
      id: 'workers',
      data: positioned,
      getPosition: (w) => w.position,
      getFillColor: [45, 212, 232, 235],
      getLineColor: [6, 9, 13, 255],
      lineWidthMinPixels: 1.5,
      stroked: true,
      getRadius: 3,
      radiusMinPixels: 3.5,
      radiusMaxPixels: 7,
      pickable: true,
      updateTriggers: {
        getPosition: [workers],
      },
      transitions: {
        getPosition: { duration: 800, easing: (t: number) => t * (2 - t) },
      },
    })
  }, [workers])

  const routeProgress = (() => {
    if (routeStartRef.current == null) return 1
    return Math.min(1, (now - routeStartRef.current) / ROUTE_DRAW_IN_MS)
  })()

  const evacuationRouteLayer = useMemo(() => {
    if (!evacuationRoute || evacuationRoute.length < 2) return null
    const zoneById = new Map(PLANT_ZONES.map((z) => [z.id, z]))
    const fullPath = evacuationRoute
      .map((zoneId) => zoneById.get(zoneId)?.centroid)
      .filter((c): c is [number, number] => c !== undefined)
    if (fullPath.length < 2) return null

    const path = interpolatePath(fullPath, routeProgress)

    return new PathLayer({
      id: 'evacuation-route',
      data: [{ path }],
      getPath: (d: { path: [number, number][] }) => d.path,
      getColor: [45, 212, 232, 240],
      getWidth: 3.5,
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evacuationRoute, routeProgress])

  // Spatial risk propagation: where the compound risk could spread next.
  const propagationData = useMemo(() => {
    if (!riskPropagation || riskPropagation.length === 0) return []
    const byId = new Map(PLANT_ZONES.map((z) => [z.id, z]))
    return riskPropagation
      .map((p) => {
        const zone = byId.get(p.zoneId)
        return zone ? { zone, score: p.score, hops: p.hops } : null
      })
      .filter((x): x is { zone: (typeof PLANT_ZONES)[number]; score: number; hops: number } => x !== null)
  }, [riskPropagation])

  const propagationSource = useMemo(
    () => PLANT_ZONES.find((z) => z.id === propagationSourceId) ?? null,
    [propagationSourceId],
  )

  const propagationLinkLayer = useMemo(() => {
    if (!propagationSource || propagationData.length === 0) return null
    return new LineLayer({
      id: 'risk-propagation-links',
      data: propagationData,
      getSourcePosition: () => propagationSource.centroid,
      getTargetPosition: (d) => d.zone.centroid,
      getColor: (d) => [255, 150, 70, Math.round(55 + d.score * 150 * (0.4 + 0.6 * pulse))],
      getWidth: (d) => 1 + d.score * 3,
      widthUnits: 'pixels',
      updateTriggers: { getColor: [pulse], getSourcePosition: [propagationSource] },
    })
  }, [propagationSource, propagationData, pulse])

  const propagationOutlineLayer = useMemo(() => {
    if (propagationData.length === 0) return null
    return new PolygonLayer({
      id: 'risk-propagation-outline',
      data: propagationData,
      getPolygon: (d) => d.zone.polygon,
      stroked: true,
      filled: true,
      getFillColor: (d) => [255, 150, 70, Math.round(12 + d.score * 38 * (0.5 + 0.5 * pulse))],
      getLineColor: (d) => [255, 170, 90, Math.round(80 + d.score * 150 * (0.4 + 0.6 * pulse))],
      getLineWidth: (d) => 1 + d.score * 2,
      lineWidthUnits: 'pixels',
      updateTriggers: { getFillColor: [pulse], getLineColor: [pulse] },
    })
  }, [propagationData, pulse])

  return (
    <section className="glass-panel corner-frame relative flex min-h-[320px] flex-1 flex-col overflow-hidden">
      {/* Header rail */}
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-[var(--color-hairline)] px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Radar size={15} className="text-[var(--color-accent)]" aria-hidden="true" />
            <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text-primary)]">
              Plant Schematic
            </h2>
          </div>
          <span className="hidden h-3 w-px bg-[var(--color-hairline-strong)] sm:block" aria-hidden="true" />
          <span className="flex items-center gap-1.5 tnum text-[11px] text-[var(--color-text-secondary)]">
            <Users size={12} aria-hidden="true" />
            {workers.length} tracked
          </span>
          <span
            className="tnum text-[11px]"
            style={{ color: elevatedCount > 0 ? 'var(--color-risk-high)' : 'var(--color-text-secondary)' }}
          >
            {elevatedCount} zone{elevatedCount === 1 ? '' : 's'} elevated
          </span>
          {evacuationRouteLayer && (
            <span className="flex items-center gap-1.5 tnum text-[11px] text-[var(--color-accent)]">
              <span className="h-1.5 w-4 rounded-full bg-[var(--color-accent)]" aria-hidden="true" />
              Evac: {evacuationRoute!.join(' → ')}
            </span>
          )}
          {propagationData.length > 0 && (
            <span
              className="flex items-center gap-1.5 tnum text-[11px]"
              style={{ color: 'rgb(255, 150, 70)' }}
              title="Zones the compound risk could spread to if uncontained, over the adjacency graph"
            >
              <span
                className="h-2 w-2"
                style={{ border: '1px solid rgb(255,170,90)', borderRadius: '2px' }}
                aria-hidden="true"
              />
              Spread risk: {propagationData.slice(0, 3).map((p) => p.zone.id).join(', ')}
            </span>
          )}
        </div>

        <div
          className="flex shrink-0 gap-0.5 rounded-[var(--radius-control)] border border-[var(--color-hairline)] p-0.5"
          role="group"
          aria-label="Plant view mode"
        >
          {VIEW_MODES.map(({ mode, label, Icon }) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewMode(mode)}
              aria-pressed={viewMode === mode}
              className="flex items-center gap-1.5 rounded-[var(--radius-sharp)] px-2.5 py-1 text-xs font-medium transition-colors"
              style={{
                backgroundColor: viewMode === mode ? 'var(--color-accent)' : 'transparent',
                color: viewMode === mode ? 'var(--color-base)' : 'var(--color-text-secondary)',
              }}
            >
              <Icon size={13} aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Map body */}
      <div className="relative min-h-0 flex-1">
        {viewMode === '3d' ? (
          <PlantScene3D zoneRisk={zoneRisk} workers={workers} evacuationRoute={evacuationRoute} />
        ) : (
          <>
            <div className="hud-grid pointer-events-none absolute inset-0 opacity-70" aria-hidden="true" />
            <div
              className="h-full w-full transition-transform duration-500"
              style={{
                transform: viewMode === 'isometric' ? ISOMETRIC_TRANSFORM : 'none',
                transformStyle: 'preserve-3d',
              }}
            >
              <DeckGL
                views={new OrthographicView({ id: 'plant' })}
                initialViewState={INITIAL_VIEW_STATE}
                controller={true}
                layers={[
                  footprintLayer,
                  zoneLayer,
                  zoneIdLayer,
                  zoneNameLayer,
                  zoneRiskGlyphLayer,
                  gasLayer,
                  propagationLinkLayer,
                  propagationOutlineLayer,
                  evacuationRouteLayer,
                  workerLayer,
                ].filter(Boolean)}
                style={{ position: 'relative', width: '100%', height: '100%', background: 'transparent' }}
              />
            </div>
          </>
        )}

        {/* Risk legend */}
        <div className="pointer-events-none absolute bottom-3 left-4 flex flex-wrap items-center gap-3">
          {(['SAFE', 'CAUTION', 'HIGH', 'CRITICAL'] as RiskLevel[]).map((level) => (
            <span key={level} className="flex items-center gap-1.5 eyebrow">
              <span
                className="inline-block h-2 w-2"
                style={{
                  backgroundColor:
                    level === 'SAFE'
                      ? 'var(--color-text-tertiary)'
                      : `var(--color-risk-${level.toLowerCase()})`,
                  clipPath:
                    level === 'CAUTION'
                      ? 'polygon(50% 0, 100% 100%, 0 100%)'
                      : level === 'HIGH'
                        ? 'polygon(50% 0, 100% 50%, 50% 100%, 0 50%)'
                        : level === 'CRITICAL'
                          ? 'none'
                          : 'circle(50%)',
                }}
                aria-hidden="true"
              />
              {level}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
