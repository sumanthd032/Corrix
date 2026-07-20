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
import { DemoIntro } from './components/DemoIntro'
import { ActivityBar } from './components/ActivityBar'
import { DataInsights } from './components/DataInsights'
import { ProjectAssistant } from './components/ProjectAssistant'
import { useScenarioSocket } from './lib/useScenarioSocket'

const TOUR_FLAG = 'corrix_tour_shown'

function App() {
  useScenarioSocket()
  const [booting, setBooting] = useState(shouldShowBootSequence)
  const [introActive, setIntroActive] = useState(false)
  const [tourActive, setTourActive] = useState(false)
  const [insightsOpen, setInsightsOpen] = useState(false)

  // On the first demo entry of a session (App is only mounted when the
  // demo is launched), after boot finishes, show a short context note,
  // which then leads into the guided tour.
  useEffect(() => {
    if (booting) return
    if (sessionStorage.getItem(TOUR_FLAG)) return
    const t = setTimeout(() => setIntroActive(true), 500)
    return () => clearTimeout(t)
  }, [booting])

  const startTour = () => {
    setIntroActive(false)
    setTourActive(true)
  }
  const skipIntro = () => {
    sessionStorage.setItem(TOUR_FLAG, '1')
    setIntroActive(false)
  }
  const endTour = () => {
    sessionStorage.setItem(TOUR_FLAG, '1')
    setTourActive(false)
  }

  return (
    <div className="relative flex h-screen flex-col gap-2.5 p-2.5">
      <div className="ambient-backdrop pointer-events-none fixed inset-0 -z-10" aria-hidden="true" />
      {booting && <BootSequence onComplete={() => setBooting(false)} />}
      <CriticalTakeover />
      <ActivityBar />

      <TopControlBar onStartTour={() => setTourActive(true)} onOpenInsights={() => setInsightsOpen(true)} />
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

      {introActive && <DemoIntro onStartTour={startTour} onSkip={skipIntro} />}
      {tourActive && <PresenterMode onClose={endTour} />}
      {insightsOpen && <DataInsights onClose={() => setInsightsOpen(false)} />}
      <ProjectAssistant />
    </div>
  )
}

export default App
