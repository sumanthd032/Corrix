import { Suspense, type ReactNode } from 'react'
import { Canvas, type CanvasProps } from '@react-three/fiber'

/**
 * Every 3D moment in the app (the boot sequence, the Council centerpiece,
 * the plant scene) mounts through this one wrapper so the renderer is
 * configured identically everywhere: capped device-pixel-ratio (a 3x+
 * phone/retina factor buys negligible visual gain here and costs real
 * frame time across three separate mount points), no shadow map unless a
 * scene opts in, and a transparent clear color so the scene always
 * composites over the app's own dark background rather than fighting it
 * with its own opaque fill.
 */
export function Scene3DCanvas({
  children,
  camera,
  className,
  eventSource,
  ...rest
}: {
  children: ReactNode
  camera?: CanvasProps['camera']
  className?: string
  eventSource?: CanvasProps['eventSource']
} & Omit<CanvasProps, 'children' | 'camera' | 'className' | 'eventSource'>) {
  return (
    <Canvas
      className={className}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      shadows={false}
      camera={camera ?? { position: [0, 0, 10], fov: 45 }}
      eventSource={eventSource}
      {...rest}
    >
      <Suspense fallback={null}>{children}</Suspense>
    </Canvas>
  )
}
