import { useState } from 'react'
import App from './App'
import { LandingPage } from './components/LandingPage'

/**
 * Top-level view switch: the marketing landing page, then the dashboard.
 * The dashboard (App) is only mounted once the user launches the demo, so
 * its live WebSocket and boot sequence don't run behind the landing page.
 * `justEntered` tells the dashboard this is a fresh demo entry, which is
 * what kicks off presenter mode the first time.
 */
export function Root() {
  const [entered, setEntered] = useState(false)

  if (!entered) return <LandingPage onLaunch={() => setEntered(true)} />
  return <App justEntered />
}
