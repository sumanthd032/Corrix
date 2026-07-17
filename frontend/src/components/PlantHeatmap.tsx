import { useEffect, useMemo, useRef, useState } from 'react'
import DeckGL from '@deck.gl/react'
import { OrthographicView } from '@deck.gl/core'
import { PathLayer, PolygonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import { Box, Boxes, Square, Users } from 'lucide-react'
import { PLANT_ZONES, ZONE_BOUNDS } from '../data/plantLayout'
import { useCorrixStore } from '../store/useCorrixStore'
import { riskColorHex } from './RiskBadge'
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
 * deuteranopia/protanopia simulation of the rendered heatmap, which
 * showed SAFE (green) and CAUTION (yellow) fills becoming nearly
 * indistinguishable from each other. The side panels already pair color
 * with a distinct Lucide icon (RiskBadge); the map itself needs its own
 * shape cue since it's pure fill color otherwise. Rendered via TextLayer
 * so it works inside deck.gl's own canvas, not a DOM overlay that would
 * need to be kept in sync with the projection on every pan/zoom.
 */
const RISK_GLYPH: Record<RiskLevel, string> = {
  SAFE: '●',
  CAUTION: '▲',
  HIGH: '♦',
  CRITICAL: '■',
}

const INITIAL_VIEW_STATE = {
  target: [
    (ZONE_BOUNDS.minX + ZONE_BOUNDS.maxX) / 2,
    (ZONE_BOUNDS.minY + ZONE_BOUNDS.maxY) / 2,
    0,
  ] as [number, number, number],
  zoom: 2.1,
}

/** Isometric mode is a CSS transform on the canvas wrapper, additive,
 * never load-bearing: the flat 2D view stays the tested default. */
const ISOMETRIC_TRANSFORM = 'rotateX(55deg) rotateZ(-45deg) scale(0.9)'

/** Zones at this risk or above get the gas-dispersion particle cloud and
 * the pulsing border. There is no gas-specific signal exposed to the
 * frontend (zoneRisk is a single risk level per zone, not per hazard
 * type), so risk level stands in for "an active gas reading" here; this
 * is a decorative signature moment, not a claim about what triggered it. */
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

/** Deterministic per-zone particle field, seeded off the zone id so the
 * same zone always gets the same drift pattern instead of reshuffling on
 * every re-render (a plain Math.random() field would look like static,
 * not a drifting cloud). */
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

/** Returns the leading sub-path of `points` covering `progress` (0-1) of
 * its total length, cut exactly at that length rather than at the
 * nearest vertex, so the draw-in reads as a smooth line growing rather
 * than a path snapping between fixed waypoints. */
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

export function PlantHeatmap() {
  const zoneRisk = useCorrixStore((s) => s.zoneRisk)
  const workers = useCorrixStore((s) => s.workers)
  const evacuationRoute = useCorrixStore((s) => s.verdict?.evacuationRoute ?? null)
  const [viewMode, setViewMode] = useState<ViewMode>('flat')
  const [now, setNow] = useState(() => performance.now())

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

  // Single animation clock driving the gas cloud, the pulsing zone
  // borders, and the evacuation-route draw-in. Self-stops once nothing
  // is left to animate rather than running a perpetual 60fps loop.
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

  const zoneLayer = useMemo(
    () =>
      new PolygonLayer({
        id: 'zones',
        data: PLANT_ZONES,
        getPolygon: (z) => z.polygon,
        getFillColor: (z) => riskColorHex(zoneRisk[z.id] ?? 'SAFE'),
        getLineColor: (z) => {
          if (!activeRiskZoneIds.has(z.id)) return [234, 241, 247, 120]
          const [r, g, b] = riskColorHex(zoneRisk[z.id] ?? 'SAFE')
          return [r, g, b, Math.round(160 + pulse * 90)]
        },
        getLineWidth: (z) => (activeRiskZoneIds.has(z.id) ? 2 + pulse * 3 : 1),
        lineWidthUnits: 'pixels',
        filled: true,
        stroked: true,
        pickable: true,
        updateTriggers: {
          getFillColor: [zoneRisk],
          getLineColor: [activeRiskZoneIds, pulse],
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
      // A pale sulfurous haze, deliberately not one of the risk-level
      // colors: a CRITICAL zone's fill is already deep red, and particles
      // drawn in that same red would disappear into it. This needs to
      // read as gas sitting on top of the risk color, at any level.
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

  const zoneLabelLayer = useMemo(
    () =>
      new TextLayer({
        id: 'zone-labels',
        data: PLANT_ZONES,
        getPosition: (z) => [z.centroid[0], z.centroid[1] - 8] as [number, number],
        getText: (z) => z.id,
        getSize: 13,
        getColor: [234, 241, 247, 220],
        fontFamily: 'IBM Plex Mono, monospace',
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'center',
      }),
    [],
  )

  const zoneRiskGlyphLayer = useMemo(
    () =>
      new TextLayer({
        id: 'zone-risk-glyphs',
        data: PLANT_ZONES,
        getPosition: (z) => [z.centroid[0], z.centroid[1] + 12] as [number, number],
        getText: (z) => RISK_GLYPH[zoneRisk[z.id] ?? 'SAFE'],
        getSize: 24,
        getColor: [11, 16, 21, 235],
        fontWeight: 700,
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'center',
        // deck.gl's TextLayer only rasterizes an ASCII default character
        // set; these Unicode shape glyphs must be listed explicitly or
        // they silently fail to render (confirmed via a "Missing
        // character" console warning during verification).
        characterSet: Object.values(RISK_GLYPH),
        updateTriggers: {
          getText: [zoneRisk],
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
      getFillColor: [0, 180, 216, 230],
      getLineColor: [11, 16, 21, 255],
      lineWidthMinPixels: 1,
      stroked: true,
      getRadius: 3,
      radiusMinPixels: 4,
      radiusMaxPixels: 8,
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
      getColor: [255, 196, 0, 235],
      getWidth: 4,
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evacuationRoute, routeProgress])

  return (
    <section className="glass-panel relative min-h-[320px] flex-1 overflow-hidden">
      <div className="absolute left-4 right-4 top-4 z-10 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-sm font-semibold tracking-wide text-[var(--color-text-primary)]">
            Geospatial Safety Heatmap
          </h2>
          <span className="flex items-center gap-1 font-mono-data text-[11px] text-[var(--color-text-secondary)]">
            <Users size={12} aria-hidden="true" />
            {workers.length} tracked
          </span>
          {evacuationRouteLayer && (
            <span
              className="flex items-center gap-1.5 font-mono-data text-[11px]"
              style={{ color: 'rgb(255, 196, 0)' }}
            >
              <span
                className="h-1.5 w-4 rounded-full"
                style={{ backgroundColor: 'rgb(255, 196, 0)' }}
                aria-hidden="true"
              />
              Evacuation route: {evacuationRoute!.join(' → ')}
            </span>
          )}
        </div>

        <div
          className="flex shrink-0 gap-0.5 rounded-[var(--radius-control)] p-0.5"
          style={{ backgroundColor: 'rgba(255,255,255,0.06)' }}
          role="group"
          aria-label="Heatmap view mode"
        >
          {VIEW_MODES.map(({ mode, label, Icon }) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewMode(mode)}
              aria-pressed={viewMode === mode}
              className="flex items-center gap-1.5 rounded-[6px] px-2.5 py-1 text-xs transition-colors"
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

      {viewMode === '3d' ? (
        <PlantScene3D zoneRisk={zoneRisk} workers={workers} evacuationRoute={evacuationRoute} />
      ) : (
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
              zoneLayer,
              zoneLabelLayer,
              zoneRiskGlyphLayer,
              gasLayer,
              evacuationRouteLayer,
              workerLayer,
            ].filter(Boolean)}
            style={{ position: 'relative', width: '100%', height: '100%' }}
          />
        </div>
      )}
    </section>
  )
}
