import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import { Grid, Line, OrbitControls, Text } from '@react-three/drei'
import { Scene3DCanvas } from './Scene3DCanvas'
import { riskColorHex } from './RiskBadge'
import { PLANT_ZONES, ZONE_BOUNDS, type HazardClass } from '../data/plantLayout'
import type { RiskLevel, WorkerMarker } from '../types'

const SCALE = 0.045
const OFFSET_X = ((ZONE_BOUNDS.minX + ZONE_BOUNDS.maxX) / 2) * SCALE
const OFFSET_Z = ((ZONE_BOUNDS.minY + ZONE_BOUNDS.maxY) / 2) * SCALE
const ELEVATED_RISK: RiskLevel[] = ['HIGH', 'CRITICAL']

const ZONE_HEIGHT: Record<HazardClass, number> = {
  low: 0.32,
  medium: 0.58,
  high: 0.92,
}

function toScene(x: number, y: number): [number, number] {
  return [x * SCALE - OFFSET_X, y * SCALE - OFFSET_Z]
}

function riskColor(level: RiskLevel): THREE.Color {
  const [r, g, b] = riskColorHex(level)
  return new THREE.Color(r / 255, g / 255, b / 255)
}

interface ZoneGeometry {
  id: string
  sceneX: number
  sceneZ: number
  width: number
  depth: number
  height: number
  isAssemblyPoint: boolean
}

const ZONE_GEOMETRY: ZoneGeometry[] = PLANT_ZONES.map((zone) => {
  const xs = zone.polygon.map((p) => p[0])
  const ys = zone.polygon.map((p) => p[1])
  const [sceneX, sceneZ] = toScene(zone.centroid[0], zone.centroid[1])
  return {
    id: zone.id,
    sceneX,
    sceneZ,
    width: (Math.max(...xs) - Math.min(...xs)) * SCALE,
    depth: (Math.max(...ys) - Math.min(...ys)) * SCALE,
    height: ZONE_HEIGHT[zone.hazardClass],
    isAssemblyPoint: zone.isAssemblyPoint,
  }
})

const MAX_ZONE_HEIGHT = Math.max(...ZONE_GEOMETRY.map((z) => z.height))
const ROUTE_Y = MAX_ZONE_HEIGHT + 0.35

function ZoneBuilding({ zone, risk }: { zone: ZoneGeometry; risk: RiskLevel }) {
  const materialRef = useRef<THREE.MeshStandardMaterial>(null)
  const active = ELEVATED_RISK.includes(risk)

  useFrame(({ clock }) => {
    if (!materialRef.current) return
    const color = riskColor(risk)
    materialRef.current.color.copy(color)
    materialRef.current.emissive.copy(color)
    if (active) {
      const pulse = 0.5 + 0.5 * Math.sin(clock.getElapsedTime() * 2.2)
      materialRef.current.emissiveIntensity = 0.5 + pulse * 0.9
    } else {
      materialRef.current.emissiveIntensity = 0.18
    }
  })

  return (
    <group position={[zone.sceneX, 0, zone.sceneZ]}>
      <mesh position={[0, zone.height / 2, 0]}>
        <boxGeometry args={[zone.width * 0.94, zone.height, zone.depth * 0.94]} />
        <meshStandardMaterial
          ref={materialRef}
          color={riskColor(risk)}
          emissive={riskColor(risk)}
          roughness={0.5}
          metalness={0.2}
          transparent
          opacity={0.82}
        />
      </mesh>
      <lineSegments position={[0, zone.height / 2, 0]}>
        <edgesGeometry args={[new THREE.BoxGeometry(zone.width * 0.94, zone.height, zone.depth * 0.94)]} />
        <lineBasicMaterial color="#eaf1f7" transparent opacity={0.35} />
      </lineSegments>
      {zone.isAssemblyPoint && (
        <mesh position={[0, zone.height + 0.12, 0]}>
          <coneGeometry args={[0.06, 0.14, 4]} />
          <meshStandardMaterial color="#2e7d32" emissive="#2e7d32" emissiveIntensity={0.8} />
        </mesh>
      )}
      <Text
        position={[0, zone.height + 0.28, 0]}
        fontSize={0.16}
        color="#8fa3b8"
        anchorX="center"
        anchorY="middle"
      >
        {zone.id}
      </Text>
    </group>
  )
}

function WorkerMarkers({ workers }: { workers: WorkerMarker[] }) {
  const zoneById = useMemo(() => new Map(ZONE_GEOMETRY.map((z) => [z.id, z])), [])

  return (
    <>
      {workers.map((w) => {
        const zone = zoneById.get(w.zoneId)
        if (!zone) return null
        const x = zone.sceneX + w.jitter[0] * SCALE
        const z = zone.sceneZ + w.jitter[1] * SCALE
        return (
          <mesh key={w.badgeId} position={[x, zone.height + 0.1, z]}>
            <sphereGeometry args={[0.045, 8, 8]} />
            <meshStandardMaterial color="#00b4d8" emissive="#00b4d8" emissiveIntensity={1.1} />
          </mesh>
        )
      })}
    </>
  )
}

function EvacuationRoute({ route }: { route: string[] }) {
  const zoneById = useMemo(() => new Map(ZONE_GEOMETRY.map((z) => [z.id, z])), [])
  const particleRef = useRef<THREE.Mesh>(null)

  const points = useMemo(
    () =>
      route
        .map((id) => zoneById.get(id))
        .filter((z): z is ZoneGeometry => z !== undefined)
        .map((z) => new THREE.Vector3(z.sceneX, ROUTE_Y, z.sceneZ)),
    [route, zoneById],
  )

  const totalLength = useMemo(() => {
    let len = 0
    for (let i = 1; i < points.length; i++) len += points[i].distanceTo(points[i - 1])
    return len
  }, [points])

  useFrame(({ clock }) => {
    if (!particleRef.current || points.length < 2) return
    const cycle = 2.6
    const t = ((clock.getElapsedTime() % cycle) / cycle) * totalLength
    let remaining = t
    for (let i = 1; i < points.length; i++) {
      const segLen = points[i].distanceTo(points[i - 1])
      if (remaining <= segLen || i === points.length - 1) {
        const localT = segLen === 0 ? 0 : remaining / segLen
        particleRef.current.position.lerpVectors(points[i - 1], points[i], Math.min(1, localT))
        break
      }
      remaining -= segLen
    }
  })

  if (points.length < 2) return null

  return (
    <>
      <Line points={points} color="#ffc400" lineWidth={2.5} transparent opacity={0.85} />
      <mesh ref={particleRef}>
        <sphereGeometry args={[0.06, 8, 8]} />
        <meshStandardMaterial color="#ffc400" emissive="#ffc400" emissiveIntensity={1.4} />
      </mesh>
    </>
  )
}

function SceneContents({
  zoneRisk,
  workers,
  evacuationRoute,
}: {
  zoneRisk: Record<string, RiskLevel>
  workers: WorkerMarker[]
  evacuationRoute: string[] | null
}) {
  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight position={[6, 10, 4]} intensity={1.4} color="#eaf1f7" />
      <pointLight position={[0, 4, 0]} intensity={8} color="#00b4d8" />

      <Grid
        position={[0, -0.01, 0]}
        args={[20, 14]}
        cellSize={0.5}
        cellColor="#1f3a5f"
        sectionSize={2}
        sectionColor="#00b4d8"
        fadeDistance={18}
        fadeStrength={1.2}
        infiniteGrid
      />

      {ZONE_GEOMETRY.map((zone) => (
        <ZoneBuilding key={zone.id} zone={zone} risk={zoneRisk[zone.id] ?? 'SAFE'} />
      ))}

      <WorkerMarkers workers={workers} />
      {evacuationRoute && evacuationRoute.length > 1 && <EvacuationRoute route={evacuationRoute} />}

      <OrbitControls
        makeDefault
        enablePan={false}
        minDistance={6}
        maxDistance={22}
        minPolarAngle={0.15}
        maxPolarAngle={Math.PI / 2 - 0.05}
        autoRotate
        autoRotateSpeed={0.5}
      />
    </>
  )
}

export function PlantScene3D({
  zoneRisk,
  workers,
  evacuationRoute,
}: {
  zoneRisk: Record<string, RiskLevel>
  workers: WorkerMarker[]
  evacuationRoute: string[] | null
}) {
  return (
    <div className="h-full w-full">
      <Scene3DCanvas camera={{ position: [7.5, 8, 9], fov: 42 }}>
        <SceneContents zoneRisk={zoneRisk} workers={workers} evacuationRoute={evacuationRoute} />
        <EffectComposer>
          <Bloom intensity={0.9} luminanceThreshold={0.25} luminanceSmoothing={0.4} mipmapBlur />
        </EffectComposer>
      </Scene3DCanvas>
    </div>
  )
}
