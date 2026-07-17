import { useMemo, useState } from 'react'
import DeckGL from '@deck.gl/react'
import { OrthographicView } from '@deck.gl/core'
import { PathLayer, PolygonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import { Box, Users } from 'lucide-react'
import { PLANT_ZONES, ZONE_BOUNDS } from '../data/plantLayout'
import { useCorrixStore } from '../store/useCorrixStore'
import { riskColorHex } from './RiskBadge'
import type { RiskLevel } from '../types'

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

export function PlantHeatmap() {
  const zoneRisk = useCorrixStore((s) => s.zoneRisk)
  const workers = useCorrixStore((s) => s.workers)
  const evacuationRoute = useCorrixStore((s) => s.verdict?.evacuationRoute ?? null)
  const [isometric, setIsometric] = useState(false)

  const zoneLayer = useMemo(
    () =>
      new PolygonLayer({
        id: 'zones',
        data: PLANT_ZONES,
        getPolygon: (z) => z.polygon,
        getFillColor: (z) => riskColorHex(zoneRisk[z.id] ?? 'SAFE'),
        getLineColor: [234, 241, 247, 120],
        getLineWidth: 1,
        lineWidthUnits: 'pixels',
        filled: true,
        stroked: true,
        pickable: true,
        updateTriggers: {
          getFillColor: [zoneRisk],
        },
        transitions: {
          getFillColor: { duration: 600, easing: (t: number) => t * (2 - t) },
        },
      }),
    [zoneRisk],
  )

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
    })
  }, [workers])

  const evacuationRouteLayer = useMemo(() => {
    if (!evacuationRoute || evacuationRoute.length < 2) return null
    const zoneById = new Map(PLANT_ZONES.map((z) => [z.id, z]))
    const path = evacuationRoute
      .map((zoneId) => zoneById.get(zoneId)?.centroid)
      .filter((c): c is [number, number] => c !== undefined)
    if (path.length < 2) return null

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
  }, [evacuationRoute])

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

        <button
          type="button"
          onClick={() => setIsometric((v) => !v)}
          className="flex shrink-0 items-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          style={{ backgroundColor: 'rgba(255,255,255,0.06)' }}
        >
          <Box size={13} aria-hidden="true" />
          {isometric ? 'Flat view' : 'Isometric view'}
        </button>
      </div>

      <div
        className="h-full w-full transition-transform duration-500"
        style={{
          transform: isometric ? ISOMETRIC_TRANSFORM : 'none',
          transformStyle: 'preserve-3d',
        }}
      >
        <DeckGL
          views={new OrthographicView({ id: 'plant' })}
          initialViewState={INITIAL_VIEW_STATE}
          controller={true}
          layers={[zoneLayer, zoneLabelLayer, zoneRiskGlyphLayer, evacuationRouteLayer, workerLayer].filter(
            Boolean,
          )}
          style={{ position: 'relative', width: '100%', height: '100%' }}
        />
      </div>
    </section>
  )
}
