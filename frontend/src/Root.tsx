import { useState } from 'react'
import App from './App'
import { LandingPage } from './components/LandingPage'

/**
 * Top-level view switch: the marketing landing page, then the dashboard.
 * The dashboard (App) is only mounted once the user launches the demo, so
 * its live WebSocket and boot sequence don't run behind the landing page.
 * Because the dashboard mounts only on launch, its own first-mount is the
 * "fresh demo entry" that kicks off presenter mode.
 */
export function Root() {
  const [entered, setEntered] = useState(false)

  if (!entered) return <LandingPage onLaunch={() => setEntered(true)} />
  return <App />
}
