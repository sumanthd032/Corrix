import { useState } from 'react'
import App from './App'
import { LandingPage } from './components/LandingPage'
import { OnboardingWizard } from './components/OnboardingWizard'
import { LiveCommandCenter } from './components/LiveCommandCenter'

type View = 'landing' | 'onboarding' | 'demo-console' | 'live-console'

/**
 * Top-level view switch: the marketing landing page, then either the
 * synthetic demo dashboard (App) or, via "Get Started," the Bring Your
 * Own Factory onboarding wizard and its own live console. The demo
 * dashboard is only mounted once the user launches it, so its live
 * WebSocket and boot sequence don't run behind the landing page.
 * Because the dashboard mounts only on launch, its own first-mount is
 * the "fresh demo entry" that kicks off presenter mode.
 */
export function Root() {
  const [view, setView] = useState<View>('landing')
  const [liveFactoryId, setLiveFactoryId] = useState<string | null>(null)

  if (view === 'landing') {
    return (
      <LandingPage
        onLaunch={() => setView('demo-console')}
        onGetStarted={() => setView('onboarding')}
      />
    )
  }
  if (view === 'onboarding') {
    return (
      <OnboardingWizard
        onExit={() => setView('landing')}
        onLaunched={(factoryId) => {
          setLiveFactoryId(factoryId)
          setView('live-console')
        }}
      />
    )
  }
  if (view === 'live-console') {
    // liveFactoryId is always set together with this view in onLaunched
    // above; the null case is unreachable in practice but keeps this
    // branch honest rather than silently falling through to <App />.
    if (!liveFactoryId) return <div>No factory to display.</div>
    return <LiveCommandCenter factoryId={liveFactoryId} />
  }
  return <App /> // view === 'demo-console'
}
