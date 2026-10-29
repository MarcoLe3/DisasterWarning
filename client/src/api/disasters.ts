import type { Disaster } from '../types'

export async function fetchDisasters(): Promise<Disaster[]> {
  const res = await fetch('/api/disasters')
  if (!res.ok) throw new Error(`Failed to load disasters (${res.status})`)
  return res.json()
}
