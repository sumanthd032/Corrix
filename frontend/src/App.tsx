import { useEffect, useState } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

interface HealthResponse {
  status: string
  service: string
}

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`backend returned ${res.status}`)
        return res.json() as Promise<HealthResponse>
      })
      .then(setHealth)
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <main>
      <h1>Corrix</h1>
      <p>Backend round trip check ({API_BASE_URL}/health):</p>
      {error && <p role="alert">error: {error}</p>}
      {!error && !health && <p>connecting...</p>}
      {health && (
        <p>
          status: {health.status}, service: {health.service}
        </p>
      )}
    </main>
  )
}

export default App
