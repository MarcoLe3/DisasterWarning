import { Circle, MapContainer, Popup, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { DISASTER_COLORS } from '../colors'
import type { Disaster } from '../types'

interface Props {
  disasters: Disaster[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export default function DisasterMap({ disasters, selectedId, onSelect }: Props) {
  return (
    <MapContainer center={[39.5, -98.35]} zoom={4} style={{ height: '100%', width: '100%' }}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {disasters.map((d) => {
        const color = DISASTER_COLORS[d.type]
        // Draw each spread snapshot as a ring, oldest = faintest
        return d.spread.map((s, i) => (
          <Circle
            key={`${d.id}-${i}`}
            center={[d.lat, d.lng]}
            radius={s.radius_km * 1000}
            pathOptions={{
              color,
              weight: d.id === selectedId ? 3 : 1,
              fillOpacity: 0.08 + (0.25 * (i + 1)) / d.spread.length,
            }}
            eventHandlers={{ click: () => onSelect(d.id) }}
          >
            <Popup>
              <strong>{d.title}</strong>
              <br />
              {d.location} · {s.radius_km} km · {new Date(s.timestamp).toLocaleString()}
            </Popup>
          </Circle>
        ))
      })}
    </MapContainer>
  )
}
