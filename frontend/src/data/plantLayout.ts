/**
 * Synthetic 2D plant layout for the heatmap, mirroring the eight zones
 * and adjacency graph authored in the backend
 * (data/layout/plant_layout.json, Step 2). Coordinates are a schematic
 * arrangement for the dashboard, not a literal architectural drawing;
 * the adjacency graph itself (used for evacuation routing, Step 8)
 * doesn't depend on zones visually touching on screen.
 *
 * Units are arbitrary "plant meters" consumed directly by deck.gl's
 * OrthographicView (no real-world lat/lng; this is an industrial
 * facility, not a map).
 */

export type HazardClass = 'low' | 'medium' | 'high'

export interface PlantZone {
  id: string
  name: string
  hazardClass: HazardClass
  isConfinedSpace: boolean
  isAssemblyPoint: boolean
  /** Polygon corners, clockwise, in plant-meter units. */
  polygon: [number, number][]
  centroid: [number, number]
}

function rectZone(
  id: string,
  name: string,
  hazardClass: HazardClass,
  x: number,
  y: number,
  width: number,
  height: number,
  options: { isConfinedSpace?: boolean; isAssemblyPoint?: boolean } = {},
): PlantZone {
  return {
    id,
    name,
    hazardClass,
    isConfinedSpace: options.isConfinedSpace ?? false,
    isAssemblyPoint: options.isAssemblyPoint ?? false,
    polygon: [
      [x, y],
      [x + width, y],
      [x + width, y + height],
      [x, y + height],
    ],
    centroid: [x + width / 2, y + height / 2],
  }
}

export const PLANT_ZONES: PlantZone[] = [
  rectZone('Z6', 'Quenching Tower / Slag Pit', 'medium', 0, 130, 50, 50),
  rectZone('Z1', 'SMS-2 Ladle Bay / Casting Floor', 'high', 70, 130, 50, 50),
  rectZone('Z5', 'Raw Material / Scrap Yard', 'medium', 140, 130, 50, 50),
  rectZone('Z7', 'Gas Collection Vault', 'high', 0, 60, 50, 50, { isConfinedSpace: true }),
  rectZone('Z3', 'Maintenance Bay', 'medium', 70, 60, 50, 50),
  rectZone('Z2', 'Gas Collection Main', 'high', 140, 60, 50, 50),
  rectZone('Z4', 'Control Room', 'low', 210, 60, 50, 50, { isAssemblyPoint: true }),
  rectZone('Z8', 'Perimeter / Walkway', 'low', 0, 0, 260, 40, { isAssemblyPoint: true }),
]

export const PLANT_ADJACENCY: [string, string][] = [
  ['Z1', 'Z3'],
  ['Z1', 'Z6'],
  ['Z1', 'Z5'],
  ['Z2', 'Z3'],
  ['Z2', 'Z7'],
  ['Z3', 'Z5'],
  ['Z3', 'Z4'],
  ['Z4', 'Z8'],
  ['Z5', 'Z8'],
  ['Z6', 'Z8'],
  ['Z7', 'Z8'],
]

export const ZONE_BOUNDS = { minX: 0, minY: 0, maxX: 260, maxY: 180 }

/**
 * Dynamic layout for a user-onboarded Bring Your Own Factory zone
 * graph, per CORRIX_REAL_DATA_BUILD_PLAN.md Step 14. Produces the
 * exact same `PlantZone[]` shape `PLANT_ZONES` above already produces,
 * so `PlantHeatmap.tsx`'s rendering logic needs zero changes; only the
 * live console (Step 16) needs to pass this instead of the static
 * import as its data source, since `PlantHeatmap.tsx` currently
 * imports `PLANT_ZONES` directly rather than taking zones as a prop.
 *
 * A lightweight force-directed layout (repulsion between every pair of
 * zones, spring attraction along adjacency edges), not a physically
 * accurate floor plan — legible and non-overlapping is the bar, and
 * clustering connected zones together reads better than an
 * adjacency-blind grid for a graph the user just drew. Seeded from the
 * zone IDs so the same graph always lays out identically instead of
 * jumping around on every re-render.
 */

interface FactoryZoneInput {
  zone_id: string
  name: string
  hazard_class: HazardClass
  is_confined_space: boolean
  is_assembly_point: boolean
}

interface FactoryAdjacencyEdgeInput {
  zone_a: string
  zone_b: string
}

const LAYOUT_CELL_SIZE = 50
const LAYOUT_WIDTH = ZONE_BOUNDS.maxX
const LAYOUT_HEIGHT = ZONE_BOUNDS.maxY
const LAYOUT_ITERATIONS = 220
const REPULSION_STRENGTH = 2200
const SPRING_REST_LENGTH = 90
const SPRING_STRENGTH = 0.02
const VELOCITY_DAMPING = 0.85

function hashSeed(str: string): number {
  let h = 2166136261
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

/** Mulberry32, a small seeded PRNG: deterministic given the same seed,
 * unlike Math.random(), so the same zone set lays out identically
 * every time. */
function mulberry32(seed: number): () => number {
  let state = seed
  return () => {
    state = (state + 0x6d2b79f5) | 0
    let t = Math.imul(state ^ (state >>> 15), 1 | state)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function layoutFromZones(
  zones: FactoryZoneInput[],
  adjacency: FactoryAdjacencyEdgeInput[],
): PlantZone[] {
  if (zones.length === 0) return []

  const margin = LAYOUT_CELL_SIZE / 2 + 10
  const rng = mulberry32(hashSeed(zones.map((z) => z.zone_id).join(',')) || 1)

  const positions = new Map<string, [number, number]>()
  const velocities = new Map<string, [number, number]>()
  zones.forEach((zone, i) => {
    const angle = (i / zones.length) * Math.PI * 2
    const radius = (Math.min(LAYOUT_WIDTH, LAYOUT_HEIGHT) / 2 - margin) * (0.4 + rng() * 0.3)
    positions.set(zone.zone_id, [
      LAYOUT_WIDTH / 2 + Math.cos(angle) * radius,
      LAYOUT_HEIGHT / 2 + Math.sin(angle) * radius,
    ])
    velocities.set(zone.zone_id, [0, 0])
  })

  const zoneIds = new Set(zones.map((z) => z.zone_id))
  const edges = adjacency.filter((e) => zoneIds.has(e.zone_a) && zoneIds.has(e.zone_b))

  for (let iteration = 0; iteration < LAYOUT_ITERATIONS; iteration++) {
    const forces = new Map<string, [number, number]>(zones.map((z) => [z.zone_id, [0, 0]]))

    for (let i = 0; i < zones.length; i++) {
      for (let j = i + 1; j < zones.length; j++) {
        const idA = zones[i].zone_id
        const idB = zones[j].zone_id
        const [ax, ay] = positions.get(idA)!
        const [bx, by] = positions.get(idB)!
        const dx = ax - bx
        const dy = ay - by
        const distSq = Math.max(1, dx * dx + dy * dy)
        const dist = Math.sqrt(distSq)
        const force = REPULSION_STRENGTH / distSq
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        const [faX, faY] = forces.get(idA)!
        forces.set(idA, [faX + fx, faY + fy])
        const [fbX, fbY] = forces.get(idB)!
        forces.set(idB, [fbX - fx, fbY - fy])
      }
    }

    for (const edge of edges) {
      const [ax, ay] = positions.get(edge.zone_a)!
      const [bx, by] = positions.get(edge.zone_b)!
      const dx = bx - ax
      const dy = by - ay
      const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy))
      const force = (dist - SPRING_REST_LENGTH) * SPRING_STRENGTH
      const fx = (dx / dist) * force
      const fy = (dy / dist) * force
      const [faX, faY] = forces.get(edge.zone_a)!
      forces.set(edge.zone_a, [faX + fx, faY + fy])
      const [fbX, fbY] = forces.get(edge.zone_b)!
      forces.set(edge.zone_b, [fbX - fx, fbY - fy])
    }

    for (const zone of zones) {
      const id = zone.zone_id
      const [vx, vy] = velocities.get(id)!
      const [fx, fy] = forces.get(id)!
      const nextVelocity: [number, number] = [(vx + fx) * VELOCITY_DAMPING, (vy + fy) * VELOCITY_DAMPING]
      velocities.set(id, nextVelocity)
      const [px, py] = positions.get(id)!
      positions.set(id, [
        clamp(px + nextVelocity[0], margin, LAYOUT_WIDTH - margin),
        clamp(py + nextVelocity[1], margin, LAYOUT_HEIGHT - margin),
      ])
    }
  }

  const half = LAYOUT_CELL_SIZE / 2
  return zones.map((zone) => {
    const [cx, cy] = positions.get(zone.zone_id)!
    return {
      id: zone.zone_id,
      name: zone.name,
      hazardClass: zone.hazard_class,
      isConfinedSpace: zone.is_confined_space,
      isAssemblyPoint: zone.is_assembly_point,
      polygon: [
        [cx - half, cy - half],
        [cx + half, cy - half],
        [cx + half, cy + half],
        [cx - half, cy + half],
      ],
      centroid: [cx, cy],
    }
  })
}
