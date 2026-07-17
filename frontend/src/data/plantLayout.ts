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
