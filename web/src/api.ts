import type { AskResponse, DatasetQuestion, Role } from './types'

const BASE = '/api'

export async function ask(question: string, path: string, role: Role): Promise<AskResponse> {
  const r = await fetch(`${BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, path: path || null, role: role || null }),
  })
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`)
  return r.json()
}

export async function sampleQuestions(source?: string): Promise<DatasetQuestion[]> {
  const q = new URLSearchParams({ limit: '200', ...(source ? { source } : {}) })
  const r = await fetch(`${BASE}/questions?${q}`)
  if (!r.ok) return []
  return r.json()
}

export const drawingUrl = (path: string, page = 1) =>
  `${BASE}/drawing?${new URLSearchParams({ path, page: String(page) })}`
