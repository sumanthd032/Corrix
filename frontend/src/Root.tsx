import { useState } from 'react'
import App from './App'
import { LandingPage } from './components/LandingPage'
import { OnboardingWizard } from './components/OnboardingWizard'

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
  if (view === 'live-console') return <div>Live console coming soon (factory {liveFactoryId})</div>
  return <App /> // view === 'demo-console'
}
