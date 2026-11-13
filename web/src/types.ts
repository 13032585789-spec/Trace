// Mirrors the shared tool-result format agreed between developer A and B.

export interface Source {
  file: string
  page: number
  bbox: [number, number, number, number] // x0, y0, x1, y1 in pixels of the /drawing PNG
  label?: string
}

export interface Item {
  id?: string
  guid?: string // IFC elements: used to highlight in 3D
  category?: string
  name?: string
  storey?: string
  space_id?: string
  space_name?: string
}

export interface Evidence {
  tool: string
  value: number | string | null
  unit?: string | null
  items: Item[]
  sources: Source[]
  method?: string
  warnings?: string[]
}

export interface AskResponse {
  answer_text: string
  evidence: Evidence[]
  tool_calls: { name: string; args: Record<string, unknown> }[]
}

export interface DatasetQuestion {
  path: string
  question: string
  answer: number | string
  unit: string | null
  type: string
}

export type Role = '' | 'architect' | 'electrician'
