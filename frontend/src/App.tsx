import { useEffect, useState } from 'react'
import { TopControlBar } from './components/TopControlBar'
import { PlantHeatmap } from './components/PlantHeatmap'
import { CouncilPanel } from './components/CouncilPanel'
import { AlertFeed } from './components/AlertFeed'
import { RegulatoryChatDrawer } from './components/RegulatoryChatDrawer'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

function useBackendStatus() {
  const [connected, setConnected] = useState<boolean | null>(null)

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => setConnected(res.ok))
      .catch(() => setConnected(false))
  }, [])

  return connected
}

function App() {
  const backendConnected = useBackendStatus()

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
        title={backendConnected ? 'Backend reachable' : 'Backend unreachable — showing mock data'}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: backendConnected ? '#2e7d32' : '#8fa3b8' }}
        />
        {backendConnected === null ? 'checking backend…' : backendConnected ? 'backend live' : 'mock data'}
      </span>
    </div>
  )
}

export default App
