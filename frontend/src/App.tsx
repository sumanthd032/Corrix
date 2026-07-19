import { useState } from 'react'
import { TopControlBar } from './components/TopControlBar'
import { TelemetryStrip } from './components/TelemetryStrip'
import { PlantHeatmap } from './components/PlantHeatmap'
import { CouncilPanel } from './components/CouncilPanel'
import { AlertFeed } from './components/AlertFeed'
import { RegulatoryChatDrawer } from './components/RegulatoryChatDrawer'
import { BootSequence, shouldShowBootSequence } from './components/BootSequence'
import { CriticalTakeover } from './components/CriticalTakeover'
import { useScenarioSocket } from './lib/useScenarioSocket'

function App() {
  useScenarioSocket()
  const [booting, setBooting] = useState(shouldShowBootSequence)

  return (
    <div className="relative flex h-screen flex-col gap-2.5 p-2.5">
      <div className="ambient-backdrop pointer-events-none fixed inset-0 -z-10" aria-hidden="true" />
      {booting && <BootSequence onComplete={() => setBooting(false)} />}
      <CriticalTakeover />

      <TopControlBar />
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
    </div>
  )
}

export default App
