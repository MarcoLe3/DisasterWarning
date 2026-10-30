import { DISASTER_COLORS } from '../colors'
import type { Disaster } from '../types'

interface Props {
  disasters: Disaster[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export default function DisasterList({ disasters, selectedId, onSelect }: Props) {
  return (
    <ul className="disaster-list">
      {disasters.map((d) => (
        <li
          key={d.id}
          className={d.id === selectedId ? 'selected' : ''}
          onClick={() => onSelect(d.id)}
        >
          <span className="badge" style={{ background: DISASTER_COLORS[d.type] }}>
            {d.type}
          </span>
          <div className="title">{d.title}</div>
          <div className="meta">
            {d.location} ({d.precision}) · severity {d.severity}/5 · {d.sources.length} source
            {d.sources.length === 1 ? '' : 's'}
          </div>
          {d.places.length > 1 && (
            <div className="meta">Also reported as: {d.places.slice(1).join(', ')}</div>
          )}
        </li>
      ))}
    </ul>
  )
}
