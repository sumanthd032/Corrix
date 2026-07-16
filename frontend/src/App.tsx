import { TopControlBar } from './components/TopControlBar'
import { PlantHeatmap } from './components/PlantHeatmap'
import { CouncilPanel } from './components/CouncilPanel'
import { AlertFeed } from './components/AlertFeed'
import { RegulatoryChatDrawer } from './components/RegulatoryChatDrawer'
import { useScenarioSocket } from './lib/useScenarioSocket'
import { useCorrixStore } from './store/useCorrixStore'

function App() {
  useScenarioSocket()
  const connectionMode = useCorrixStore((s) => s.connectionMode)

  return (
    <div className="flex h-screen flex-col gap-3 p-3">
      <TopControlBar />

      <div className="flex min-h-0 flex-1 gap-3">
        <PlantHeatmap />

        <div className="flex w-[380px] shrink-0 flex-col gap-3 overflow-y-auto">
          <CouncilPanel />
          <AlertFeed />
        </div>
      </div>

      <RegulatoryChatDrawer />

      <span
        className="fixed bottom-2 left-2 flex items-center gap-1 font-mono-data text-[10px] text-[var(--color-text-secondary)]"
        title={
          connectionMode === 'live'
            ? 'Connected to the live backend — real scenario stream and Safety Council'
            : 'Backend unreachable — showing mock data'
        }
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: connectionMode === 'live' ? '#2e7d32' : '#8fa3b8' }}
        />
        {connectionMode === 'live' ? 'backend live' : 'mock data'}
      </span>
    </div>
  )
}

export default App
