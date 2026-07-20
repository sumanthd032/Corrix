import { useEffect, useMemo, useState } from 'react'
import { Loader2, ShieldCheck } from 'lucide-react'
import { TopControlBar } from './TopControlBar'
import { TelemetryStrip } from './TelemetryStrip'
import { PlantHeatmap } from './PlantHeatmap'
import { CouncilPanel } from './CouncilPanel'
import { AlertFeed } from './AlertFeed'
import { ScrollColumn } from './ScrollColumn'
import { useLiveFactorySocket } from '../lib/useLiveFactorySocket'
import { layoutFromZones } from '../data/plantLayout'
import type { HazardClass } from '../data/plantLayout'

/**
 * The Bring Your Own Factory Live Command Center, per
 * CORRIX_REAL_DATA_BUILD_PLAN.md Step 16. Reuses App.tsx's exact panel
 * layout (TopControlBar, TelemetryStrip, PlantHeatmap, CouncilPanel,
 * AlertFeed), fed by Step 15's useLiveFactorySocket and Step 14's
 * layoutFromZones instead of the static demo layout. BootSequence/
 * DemoIntro (which walk through the synthetic demo's own features) are
 * replaced with a short "your factory is now live" confirmation.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

interface FactoryProfileResponse {
  factory_id: string
  name: string
  layout: {
    zones: {
      zone_id: string
      name: string
      hazard_class: HazardClass
      is_confined_space: boolean
      is_assembly_point: boolean
    }[]
    adjacency: { zone_a: string; zone_b: string }[]
  }
}

export function LiveCommandCenter({ factoryId }: { factoryId: string }) {
  useLiveFactorySocket(factoryId)
  const [profile, setProfile] = useState<FactoryProfileResponse | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [confirmationVisible, setConfirmationVisible] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE_URL}/api/factory/${factoryId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`Could not load factory ${factoryId} (status ${res.status}).`)
        return (await res.json()) as FactoryProfileResponse
      })
      .then((data) => {
        if (!cancelled) setProfile(data)
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : 'Could not load the factory.')
      })
    return () => {
      cancelled = true
    }
  }, [factoryId])

  useEffect(() => {
    if (!profile) return
    const timer = setTimeout(() => setConfirmationVisible(false), 2600)
    return () => clearTimeout(timer)
  }, [profile])

  const zones = useMemo(
    () => (profile ? layoutFromZones(profile.layout.zones, profile.layout.adjacency) : []),
    [profile],
  )

  if (loadError) {
    return (
      <div className="ambient-backdrop flex min-h-screen items-center justify-center p-4">
        <div className="glass-panel corner-frame max-w-md p-6 text-center text-sm" style={{ color: 'var(--color-risk-critical)' }}>
          {loadError}
        </div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="ambient-backdrop flex min-h-screen items-center justify-center p-4">
        <div className="glass-panel corner-frame flex flex-col items-center gap-3 p-8 text-center">
          <Loader2 size={28} className="animate-spin text-[var(--color-accent)]" aria-hidden="true" />
          <p className="text-sm text-[var(--color-text-secondary)]">Loading your factory…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="relative flex h-screen flex-col gap-2.5 p-2.5">
      <div className="ambient-backdrop pointer-events-none fixed inset-0 -z-10" aria-hidden="true" />

      <TopControlBar mode="live" />
      <TelemetryStrip zones={zones} />

      <div className="flex min-h-0 flex-1 flex-col gap-2.5 lg:flex-row">
        <div className="flex min-h-0 flex-1 flex-col gap-2.5">
          <PlantHeatmap zones={zones} />
        </div>

        <div className="flex w-full shrink-0 flex-col lg:w-[400px]">
          <ScrollColumn className="thin-scroll min-h-0 flex-1 overflow-y-auto">
            <CouncilPanel />
            <AlertFeed />
          </ScrollColumn>
        </div>
      </div>

      {confirmationVisible && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 p-4">
          <div className="glass-panel corner-frame flex flex-col items-center gap-3 p-8 text-center">
            <ShieldCheck size={32} className="text-[var(--color-accent)]" aria-hidden="true" />
            <h2 className="font-display text-lg font-semibold text-[var(--color-text-primary)]">
              Your factory is now live
            </h2>
            <p className="max-w-xs text-sm text-[var(--color-text-secondary)]">
              {profile.name} is streaming into the Safety Council. Real data in, real reasoning out.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
