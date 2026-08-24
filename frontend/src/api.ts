import type {
  DownloadResult,
  LlmConfig,
  LlmPreset,
  Paper,
  PaperRecord,
  SearchParams,
  TopicSearchParams,
  TopicSearchResult,
} from './types'

const BASE = '/api'

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || res.statusText)
  }
  return res.json()
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    throw new Error(await res.text())
  }
  return res.json()
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || res.statusText)
  }
  return res.json()
}

export async function searchPapers(params: SearchParams): Promise<Paper[]> {
  return post<Paper[]>('/search', params)
}

export async function searchTopic(params: TopicSearchParams): Promise<TopicSearchResult> {
  return post<TopicSearchResult>('/search/topic', params)
}

export async function downloadPapers(papers: Paper[]): Promise<DownloadResult> {
  return post<DownloadResult>('/download', { papers })
}

export async function listPapers(arxivIds?: string[]): Promise<PaperRecord[]> {
  const qs = arxivIds && arxivIds.length ? `?arxiv_ids=${arxivIds.join(',')}` : ''
  const res = await fetch(`${BASE}/papers${qs}`)
  if (!res.ok) {
    throw new Error(await res.text())
  }
  return res.json()
}

export async function getLlmPresets(): Promise<LlmPreset[]> {
  return get<LlmPreset[]>('/llm/presets')
}

export async function getLlmConfig(): Promise<LlmConfig> {
  return get<LlmConfig>('/llm/config')
}

export async function saveLlmConfig(config: Partial<LlmConfig>): Promise<LlmConfig> {
  return put<LlmConfig>('/llm/config', config)
}
