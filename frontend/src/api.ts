import type {
  AnalysisLanguage,
  AnalysisRecord,
  DownloadResult,
  LlmConfig,
  LlmPreset,
  Paper,
  PaperRecord,
  ReviewRecord,
  SearchParams,
  TopicSearchParams,
  TopicSearchResult,
} from './types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function throwForStatus(res: Response): Promise<never> {
  const text = await res.text()
  let message = text
  try {
    const data = JSON.parse(text)
    if (typeof data?.detail === 'string') message = data.detail
    else if (data?.detail != null) message = JSON.stringify(data.detail)
  } catch {
    // keep raw text
  }
  throw new ApiError(res.status, message || res.statusText)
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    await throwForStatus(res)
  }
  return res.json()
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    await throwForStatus(res)
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
    await throwForStatus(res)
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

export async function analyzePaper(
  arxivId: string,
  language: AnalysisLanguage,
): Promise<{ arxiv_id: string; status: string }> {
  return post(`/analyze/${arxivId}`, { language })
}

export async function analyzeBatch(
  arxivIds: string[],
  language: AnalysisLanguage,
): Promise<{ arxiv_ids: string[]; status: string }> {
  return post('/analyze/batch', { arxiv_ids: arxivIds, language })
}

export async function getAnalysis(arxivId: string): Promise<AnalysisRecord> {
  return get<AnalysisRecord>(`/analyses/${arxivId}`)
}

export async function listAnalyses(arxivIds?: string[]): Promise<AnalysisRecord[]> {
  const qs = arxivIds && arxivIds.length ? `?arxiv_ids=${arxivIds.join(',')}` : ''
  return get<AnalysisRecord[]>(`/analyses${qs}`)
}

export async function createReview(
  arxivIds: string[],
  language: AnalysisLanguage,
): Promise<ReviewRecord> {
  return post<ReviewRecord>('/review', { arxiv_ids: arxivIds, language })
}

export async function getReview(id: number): Promise<ReviewRecord> {
  return get<ReviewRecord>(`/reviews/${id}`)
}

export async function exportAnalysisMarkdown(arxivId: string): Promise<string> {
  const res = await fetch(`${BASE}/analyses/${arxivId}/export`)
  if (!res.ok) throw new Error(await res.text())
  return res.text()
}

export async function exportReviewMarkdown(id: number): Promise<string> {
  const res = await fetch(`${BASE}/reviews/${id}/export`)
  if (!res.ok) throw new Error(await res.text())
  return res.text()
}
