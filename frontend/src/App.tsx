import { useEffect, useState } from 'react'
import { TopControlBar } from './components/TopControlBar'
import { TelemetryStrip } from './components/TelemetryStrip'
import { PlantHeatmap } from './components/PlantHeatmap'
import { CouncilPanel } from './components/CouncilPanel'
import { AlertFeed } from './components/AlertFeed'
import { RegulatoryChatDrawer } from './components/RegulatoryChatDrawer'
import { BootSequence, shouldShowBootSequence } from './components/BootSequence'
import { CriticalTakeover } from './components/CriticalTakeover'
import { PresenterMode } from './components/PresenterMode'
import { useScenarioSocket } from './lib/useScenarioSocket'

const TOUR_FLAG = 'corrix_tour_shown'

function App({ justEntered = false }: { justEntered?: boolean }) {
  useScenarioSocket()
  const [booting, setBooting] = useState(shouldShowBootSequence)
  const [tourActive, setTourActive] = useState(false)

  // Kick off the guided tour once, the first time the demo is entered in
  // this session, after the boot sequence has finished.
  useEffect(() => {
    if (booting || !justEntered) return
    if (sessionStorage.getItem(TOUR_FLAG)) return
    const t = setTimeout(() => setTourActive(true), 500)
    return () => clearTimeout(t)
  }, [booting, justEntered])

  const endTour = () => {
    sessionStorage.setItem(TOUR_FLAG, '1')
    setTourActive(false)
  }

  return (
    <div className="relative flex h-screen flex-col gap-2.5 p-2.5">
      <div className="ambient-backdrop pointer-events-none fixed inset-0 -z-10" aria-hidden="true" />
      {booting && <BootSequence onComplete={() => setBooting(false)} />}
      <CriticalTakeover />

      <TopControlBar onStartTour={() => setTourActive(true)} />
      <TelemetryStrip />

      <div className="flex min-h-0 flex-1 flex-col gap-2.5 lg:flex-row">
        <div className="flex min-h-0 flex-1 flex-col gap-2.5">
          <PlantHeatmap />
          <RegulatoryChatDrawer />
        </div>

        <div className="thin-scroll flex w-full shrink-0 flex-col gap-2.5 overflow-y-auto lg:w-[400px]">
          <CouncilPanel />
          <AlertFeed />
        </div>
      </div>

      {tourActive && <PresenterMode onClose={endTour} />}
    </div>
  )
}

export default App
