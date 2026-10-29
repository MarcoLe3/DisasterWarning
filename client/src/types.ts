export type DisasterType =
  | 'fire'
  | 'flood'
  | 'earthquake'
  | 'hurricane'
  | 'tornado'
  | 'other'

export type LocationPrecision =
  | 'address'
  | 'neighborhood'
  | 'city'
  | 'county'
  | 'state'
  | 'country'

export interface SourcePost {
  platform: string
  url: string
  caption: string
  posted_at: string
}

export interface SpreadPoint {
  timestamp: string
  radius_km: number
}

export interface Disaster {
  id: string
  type: DisasterType
  title: string
  location: string
  precision: LocationPrecision
  lat: number
  lng: number
  severity: number
  spread: SpreadPoint[]
  sources: SourcePost[]
}
