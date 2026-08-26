import type {
  AgentChatResult,
  AgentSessionDetail,
  AgentSessionItem,
  AnalysisLanguage,
  AnalysisRecord,
  CloneResult,
  DownloadResult,
  ExecResult,
  ExperimentHistoryItem,
  ExperimentRecord,
  InnovationHistoryItem,
  InnovationRecord,
  LlmConfig,
  LlmPreset,
  LlmTestResult,
  MonitorData,
  Paper,
  PaperMetadata,
  PaperRecord,
  PaperUploadResult,
  PlatformStatus,
  ReviewRecord,
  SearchHistoryDetail,
  SearchHistoryItem,
  SearchParams,
  SearchResult,
  Server,
  ServerInput,
  ServerTestResult,
  TopicSearchParams,
  TopicSearchResult,
  UploadResult,
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

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) {
    await throwForStatus(res)
  }
}

export async function searchPapers(params: SearchParams): Promise<SearchResult> {
  return post<SearchResult>('/search', params)
}

export async function searchTopic(params: TopicSearchParams): Promise<TopicSearchResult> {
  return post<TopicSearchResult>('/search/topic', params)
}

export async function downloadPapers(papers: Paper[]): Promise<DownloadResult> {
  return post<DownloadResult>('/download', { papers })
}

export async function uploadPdf(file: File): Promise<PaperUploadResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/papers/upload`, { method: 'POST', body: form })
  if (!res.ok) {
    await throwForStatus(res)
  }
  return res.json()
}

export async function confirmUpload(
  pdfToken: string,
  paper: PaperMetadata,
): Promise<PaperRecord> {
  return post<PaperRecord>('/papers/upload/confirm', { pdf_token: pdfToken, paper })
}

export async function listPapers(arxivIds?: string[]): Promise<PaperRecord[]> {
  const qs = arxivIds && arxivIds.length ? `?arxiv_ids=${encodeURIComponent(arxivIds.join(','))}` : ''
  const res = await fetch(`${BASE}/papers${qs}`)
  if (!res.ok) {
    throw new Error(await res.text())
  }
  return res.json()
}

export async function deletePaper(arxivId: string): Promise<void> {
  return del(`/papers/${encodeURIComponent(arxivId)}`)
}

export async function listSearchHistory(): Promise<SearchHistoryItem[]> {
  return get<SearchHistoryItem[]>('/search/history')
}

export async function getSearchHistory(id: number): Promise<SearchHistoryDetail> {
  return get<SearchHistoryDetail>(`/search/history/${id}`)
}

export async function deleteSearchHistory(id: number): Promise<void> {
  return del(`/search/history/${id}`)
}

export async function clearSearchHistory(): Promise<void> {
  return del('/search/history')
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

export async function testLlmConnection(config: Partial<LlmConfig>): Promise<LlmTestResult> {
  return post<LlmTestResult>('/llm/test', config)
}

export async function getLlmModels(params: { base_url: string; api_key: string }): Promise<string[]> {
  const res = await post<{ models: string[] }>('/llm/models', params)
  return res.models
}

export async function listPlatforms(): Promise<PlatformStatus[]> {
  return get<PlatformStatus[]>('/platforms')
}

export async function loginPlatform(platform: string): Promise<PlatformStatus> {
  return post<PlatformStatus>(`/platforms/${platform}/login`, {})
}

export async function getPlatformStatus(platform: string): Promise<PlatformStatus> {
  return get<PlatformStatus>(`/platforms/${platform}/status`)
}

export async function logoutPlatform(platform: string): Promise<PlatformStatus> {
  return post<PlatformStatus>(`/platforms/${platform}/logout`, {})
}

export async function completePlatformLogin(platform: string): Promise<PlatformStatus> {
  return post<PlatformStatus>(`/platforms/${platform}/login/complete`, {})
}

export async function cancelPlatformLogin(platform: string): Promise<PlatformStatus> {
  return post<PlatformStatus>(`/platforms/${platform}/login/cancel`, {})
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
  const qs = arxivIds && arxivIds.length ? `?arxiv_ids=${encodeURIComponent(arxivIds.join(','))}` : ''
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

export async function createInnovations(
  arxivIds: string[],
  count: number,
  language: AnalysisLanguage,
): Promise<InnovationRecord> {
  return post<InnovationRecord>('/innovations', { arxiv_ids: arxivIds, count, language })
}

export async function listInnovations(): Promise<InnovationHistoryItem[]> {
  return get<InnovationHistoryItem[]>('/innovations')
}

export async function getInnovation(id: number): Promise<InnovationRecord> {
  return get<InnovationRecord>(`/innovations/${id}`)
}

export async function deleteInnovation(id: number): Promise<void> {
  return del(`/innovations/${id}`)
}

export async function clearInnovations(): Promise<void> {
  return del('/innovations')
}

export async function exportInnovationMarkdown(id: number): Promise<string> {
  const res = await fetch(`${BASE}/innovations/${id}/export`)
  if (!res.ok) throw new Error(await res.text())
  return res.text()
}

export interface CreateExperimentParams {
  source_type: 'innovation' | 'papers'
  innovation_id?: number | null
  arxiv_ids?: string[]
  count: number
  language: AnalysisLanguage
}

export async function createExperiment(params: CreateExperimentParams): Promise<ExperimentRecord> {
  return post<ExperimentRecord>('/experiments', params)
}

export async function getExperiment(id: number): Promise<ExperimentRecord> {
  return get<ExperimentRecord>(`/experiments/${id}`)
}

export async function exportExperimentMarkdown(id: number): Promise<string> {
  const res = await fetch(`${BASE}/experiments/${id}/export`)
  if (!res.ok) throw new Error(await res.text())
  return res.text()
}

export async function listExperiments(): Promise<ExperimentHistoryItem[]> {
  return get<ExperimentHistoryItem[]>('/experiments')
}

export async function deleteExperiment(id: number): Promise<void> {
  return del(`/experiments/${id}`)
}

export async function clearExperiments(): Promise<void> {
  return del('/experiments')
}

export async function listServers(): Promise<Server[]> {
  return get<Server[]>('/servers')
}

export async function createServer(input: ServerInput): Promise<Server> {
  return post<Server>('/servers', input)
}

export async function updateServer(id: string, input: ServerInput): Promise<Server> {
  return put<Server>(`/servers/${id}`, input)
}

export async function deleteServer(id: string): Promise<void> {
  return del(`/servers/${id}`)
}

export async function testServer(id: string): Promise<ServerTestResult> {
  return post<ServerTestResult>(`/servers/${id}/test`, {})
}

export async function deployClone(
  id: string,
  body: { repo_url: string; target_dir: string },
): Promise<CloneResult> {
  return post<CloneResult>(`/servers/${id}/deploy/clone`, body)
}

export async function deployUpload(
  id: string,
  body: { local_path: string; remote_path: string },
): Promise<UploadResult> {
  return post<UploadResult>(`/servers/${id}/deploy/upload`, body)
}

export async function deployUploadFiles(
  id: string,
  files: File[],
  remotePath: string,
): Promise<UploadResult> {
  const form = new FormData()
  for (const file of files) {
    const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name
    form.append('files', file, rel)
  }
  form.append('remote_path', remotePath)
  const res = await fetch(`${BASE}/servers/${id}/deploy/upload`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    await throwForStatus(res)
  }
  return res.json()
}

export async function monitorServer(id: string): Promise<MonitorData> {
  return post<MonitorData>(`/servers/${id}/monitor`, {})
}

export async function execCommand(id: string, command: string): Promise<ExecResult> {
  return post<ExecResult>(`/servers/${id}/exec`, { command })
}

export async function agentChat(
  sessionId: string | null,
  message: string,
): Promise<AgentChatResult> {
  return post<AgentChatResult>('/agent/chat', { session_id: sessionId, message })
}

export async function agentApprove(
  sessionId: string,
  approve: boolean,
): Promise<AgentChatResult> {
  return post<AgentChatResult>('/agent/approve', { session_id: sessionId, approve })
}

export async function listAgentSessions(): Promise<AgentSessionItem[]> {
  return get<AgentSessionItem[]>('/agent/sessions')
}

export async function createAgentSession(): Promise<AgentSessionItem> {
  return post<AgentSessionItem>('/agent/sessions', {})
}

export async function getAgentSession(id: string): Promise<AgentSessionDetail> {
  return get<AgentSessionDetail>(`/agent/sessions/${id}`)
}

export async function renameAgentSession(id: string, title: string): Promise<AgentSessionItem> {
  return put<AgentSessionItem>(`/agent/sessions/${id}`, { title })
}

export async function deleteAgentSession(id: string): Promise<void> {
  return del(`/agent/sessions/${id}`)
}
