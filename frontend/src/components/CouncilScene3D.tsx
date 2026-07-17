import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import { Scene3DCanvas } from './Scene3DCanvas'
import { riskColorHex } from './RiskBadge'
import { usePrefersReducedMotion } from '../lib/usePrefersReducedMotion'
import type { CouncilStage, RiskLevel } from '../types'

const ACCENT = new THREE.Color('#00b4d8')
const VIOLET = new THREE.Color('#8b5cf6')
const AMBER = new THREE.Color('#f2c94c')
const DIM = new THREE.Color('#2a3a4a')

/** Left to right, matching CouncilPanel's own AGENTS order, so a viewer's
 * eye maps position to role the same way in both the icon legend above
 * and this scene. */
const AGENT_X = [-3, -1, 1, 3]
const CHAIR_POSITION: [number, number, number] = [0, 1.3, -1.4]

function riskColor(level: RiskLevel): THREE.Color {
  const [r, g, b] = riskColorHex(level)
  return new THREE.Color(r / 255, g / 255, b / 255)
}

function AgentNode({ x, index, stage }: { x: number; index: number; stage: CouncilStage }) {
  const meshRef = useRef<THREE.Mesh>(null)
  const materialRef = useRef<THREE.MeshStandardMaterial>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const bob = Math.sin(t * 0.6 + index) * 0.06
    if (meshRef.current) {
      meshRef.current.position.y = bob
      meshRef.current.rotation.y = t * 0.3
    }
    if (materialRef.current) {
      const active = stage === 'convening'
      const pulse = active ? 0.5 + 0.5 * Math.sin(t * 3 - index * 0.9) : 0.15
      materialRef.current.emissiveIntensity = active ? 0.6 + pulse * 1.4 : 0.35
      materialRef.current.color.copy(active ? ACCENT : DIM)
      materialRef.current.emissive.copy(ACCENT)
    }
  })

  return (
    <mesh ref={meshRef} position={[x, 0, 0]}>
      <icosahedronGeometry args={[0.34, 0]} />
      <meshStandardMaterial ref={materialRef} color={ACCENT} emissive={ACCENT} roughness={0.35} metalness={0.4} />
    </mesh>
  )
}

function ChairNode({ stage, riskLevel }: { stage: CouncilStage; riskLevel?: RiskLevel }) {
  const meshRef = useRef<THREE.Mesh>(null)
  const materialRef = useRef<THREE.MeshStandardMaterial>(null)
  const verdictSince = useRef<number | null>(null)
  const prevStage = useRef(stage)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (prevStage.current !== stage) {
      if (stage === 'verdict_reached') verdictSince.current = t
      prevStage.current = stage
    }

    if (meshRef.current) {
      meshRef.current.rotation.y = t * 0.5
      meshRef.current.rotation.x = Math.sin(t * 0.4) * 0.1
      let scale = 1
      if (stage === 'verdict_reached' && verdictSince.current !== null) {
        const age = t - verdictSince.current
        scale = 1 + Math.max(0, 0.4 - age * 0.8) * (1 - Math.cos(age * 18)) * 0.5
      }
      meshRef.current.scale.setScalar(scale)
    }

    if (materialRef.current) {
      let color = VIOLET
      let intensity = 0.5 + Math.sin(t * 1.2) * 0.15
      if (stage === 'convening') {
        intensity = 0.7 + 0.4 * Math.sin(t * 3.4)
      } else if (stage === 'deliberating') {
        color = AMBER
        intensity = 0.6 + 0.4 * Math.sin(t * 5)
      } else if (stage === 'verdict_reached' && riskLevel) {
        color = riskColor(riskLevel)
        intensity = 0.9
      }
      materialRef.current.color.copy(color)
      materialRef.current.emissive.copy(color)
      materialRef.current.emissiveIntensity = intensity
    }
  })

  return (
    <mesh ref={meshRef} position={CHAIR_POSITION}>
      <octahedronGeometry args={[0.5, 0]} />
      <meshStandardMaterial ref={materialRef} color={VIOLET} emissive={VIOLET} roughness={0.25} metalness={0.5} />
    </mesh>
  )
}

function SignalBeams({ stage }: { stage: CouncilStage }) {
  const particleRefs = useRef<(THREE.Mesh | null)[]>([])

  useFrame(({ clock }) => {
    if (stage !== 'convening') return
    const t = clock.getElapsedTime()
    AGENT_X.forEach((x, i) => {
      const mesh = particleRefs.current[i]
      if (!mesh) return
      const cycle = 1.1
      const localT = ((t * 0.55 + i * 0.22) % cycle) / cycle
      const from = new THREE.Vector3(x, 0, 0)
      const to = new THREE.Vector3(...CHAIR_POSITION)
      mesh.position.lerpVectors(from, to, localT)
      const mat = mesh.material as THREE.MeshStandardMaterial
      mat.emissiveIntensity = Math.sin(localT * Math.PI) * 1.8
      mesh.visible = true
    })
  })

  if (stage !== 'convening') return null

  return (
    <>
      {AGENT_X.map((_, i) => (
        <mesh key={i} ref={(el) => { particleRefs.current[i] = el }}>
          <sphereGeometry args={[0.07, 8, 8]} />
          <meshStandardMaterial color={ACCENT} emissive={ACCENT} emissiveIntensity={1} />
        </mesh>
      ))}
    </>
  )
}

function SceneContents({ stage, riskLevel }: { stage: CouncilStage; riskLevel?: RiskLevel }) {
  const groupRef = useRef<THREE.Group>(null)

  useFrame(({ clock }) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = Math.sin(clock.getElapsedTime() * 0.08) * 0.15
    }
  })

  return (
    <group ref={groupRef}>
      <ambientLight intensity={0.4} />
      <pointLight position={[0, 2, 3]} intensity={20} color="#eaf1f7" />
      {AGENT_X.map((x, i) => (
        <AgentNode key={i} x={x} index={i} stage={stage} />
      ))}
      <ChairNode stage={stage} riskLevel={riskLevel} />
      <SignalBeams stage={stage} />
    </group>
  )
}

function StaticFallback({ stage, riskLevel }: { stage: CouncilStage; riskLevel?: RiskLevel }) {
  const chairColor =
    stage === 'verdict_reached' && riskLevel
      ? `rgb(${riskColorHex(riskLevel).slice(0, 3).join(',')})`
      : 'var(--color-accent-secondary)'
  return (
    <div className="flex h-[150px] w-full items-center justify-center gap-6">
      {AGENT_X.map((_, i) => (
        <span
          key={i}
          className="h-3 w-3 rounded-full"
          style={{
            backgroundColor: stage === 'convening' ? 'var(--color-accent)' : 'var(--color-panel-border)',
          }}
        />
      ))}
      <span className="h-4 w-4 rounded-sm" style={{ backgroundColor: chairColor }} />
    </div>
  )
}

export function CouncilScene3D({ stage, riskLevel }: { stage: CouncilStage; riskLevel?: RiskLevel }) {
  const reducedMotion = usePrefersReducedMotion()
  const camera = useMemo(() => ({ position: [0, 1.0, 6] as [number, number, number], fov: 38 }), [])

  if (reducedMotion) return <StaticFallback stage={stage} riskLevel={riskLevel} />

  return (
    <div className="h-[150px] w-full">
      <Scene3DCanvas camera={camera}>
        <SceneContents stage={stage} riskLevel={riskLevel} />
        <EffectComposer>
          <Bloom intensity={1.1} luminanceThreshold={0.15} luminanceSmoothing={0.4} mipmapBlur />
        </EffectComposer>
      </Scene3DCanvas>
    </div>
  )
}
