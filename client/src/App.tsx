import { useEffect, useState } from 'react'
import { fetchDisasters } from './api/disasters'
import DisasterList from './components/DisasterList'
import DisasterMap from './components/DisasterMap'
import type { Disaster } from './types'
import './App.css'

function App() {
  const [disasters, setDisasters] = useState<Disaster[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchDisasters()
      .then(setDisasters)
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>DisasterWarning</h1>
        {error && <p className="error">{error}</p>}
        <DisasterList disasters={disasters} selectedId={selectedId} onSelect={setSelectedId} />
      </aside>
      <main className="map">
        <DisasterMap disasters={disasters} selectedId={selectedId} onSelect={setSelectedId} />
      </main>
    </div>
  )
}

export default App
