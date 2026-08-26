export interface Paper {
  arxiv_id: string
  title: string
  authors: string[]
  abstract: string
  categories: string[]
  published: string
  pdf_url: string
  source?: string
  url?: string
}

export interface PaperRecord extends Paper {
  id?: number
  local_pdf_path?: string | null
  status?: string
  progress?: number
  error?: string | null
  created_at?: string
}

export type SearchPlatform = 'arxiv' | 'semantic_scholar' | 'baidu_xueshu' | 'cnki'

export const SEARCH_PLATFORMS: { value: SearchPlatform; label: string }[] = [
  { value: 'arxiv', label: 'arXiv' },
  { value: 'semantic_scholar', label: 'Semantic Scholar' },
  { value: 'baidu_xueshu', label: '百度学术' },
  { value: 'cnki', label: '知网 CNKI' },
]

export interface SearchFallback {
  platform: string
  url: string
  need_login?: boolean
  expired?: boolean
}

export type PlatformState = 'not_logged_in' | 'logging_in' | 'logged_in' | 'expired'

export interface PlatformStatus {
  platform: string
  state: PlatformState
}

export interface SearchResult {
  papers: Paper[]
  fallbacks: SearchFallback[]
}

export interface SearchBase {
  max_results: number
  date_from?: string
  date_to?: string
  platforms?: SearchPlatform[]
}

export interface SearchParams extends SearchBase {
  query: string
}

export interface TopicSearchParams extends SearchBase {
  topic: string
}

export interface TopicSearchResult {
  query: string
  papers: Paper[]
  fallbacks: SearchFallback[]
}

export interface PaperMetadata {
  title: string
  authors: string[]
  abstract: string
  published: string
}

export interface PaperUploadResult {
  pdf_token: string
  paper: PaperMetadata
}

export interface DownloadResult {
  accepted: string[]
  skipped: string[]
}

export interface SearchHistoryItem {
  id: number
  query: string
  mode: string
  paper_count: number
  created_at?: string
}

export interface SearchHistoryDetail {
  id: number
  query: string
  mode: string
  papers: Paper[]
  created_at?: string
}

export interface LlmPreset {
  name: string
  base_url: string
  default_model: string
}

export interface LlmConfig {
  base_url: string
  api_key: string
  model: string
}

export interface LlmTestResult {
  ok: boolean
  message: string
  latency_ms?: number | null
}

export interface AnalysisSummary {
  research_problem: string
  method: string
  contributions: string[]
  conclusion: string
}

export interface AnalysisExperiments {
  datasets: string[]
  baselines: string[]
  metrics: string[]
  key_results: string
}

export interface PaperAnalysis {
  summary: AnalysisSummary
  experiments: AnalysisExperiments
  limitations: string
  future_work: string
  keywords: string[]
  tags: string[]
}

export interface AnalysisRecord {
  id?: number
  arxiv_id: string
  content: PaperAnalysis | null
  language: string
  status: string
  error?: string | null
  progress?: number
  message?: string | null
  created_at?: string
  updated_at?: string
}

export interface AnalysisStatusInfo {
  status: string
  progress?: number
  message?: string | null
}

export interface ReviewResult {
  common_themes: string[]
  differences: string[]
  research_gaps: string[]
  summary: string
}

export interface ReviewRecord {
  id?: number
  arxiv_ids: string[]
  content: ReviewResult | null
  language: string
  status: string
  error?: string | null
  progress?: number
  created_at?: string
}

export interface InnovationPoint {
  title: string
  description: string
  basis: string[]
  expected_contribution: string
}

export interface InnovationRecord {
  id?: number
  arxiv_ids: string[]
  content: InnovationPoint[] | null
  language: string
  status: string
  error?: string | null
  progress?: number
  created_at?: string
}

export interface InnovationHistoryItem {
  id: number
  arxiv_ids: string[]
  paper_count: number
  innovation_count: number
  language: string
  status: string
  created_at?: string
}

export type AnalysisLanguage = 'zh' | 'en'

export interface ExperimentPlan {
  hypothesis: string
  goal: string
  datasets: string[]
  baselines: string[]
  metrics: string[]
}

export interface ExperimentRecord {
  id?: number
  source_type: string
  innovation_id?: number | null
  arxiv_ids: string[]
  content: ExperimentPlan[] | null
  language: string
  status: string
  error?: string | null
  progress?: number
  created_at?: string
}

export type ServerAuthType = 'password' | 'key'

export interface Server {
  id: string
  name: string
  host: string
  username: string
  port: number
  auth_type: ServerAuthType
  has_password: boolean
  has_key: boolean
}

export interface ServerInput {
  name: string
  host: string
  username: string
  port?: number
  auth_type?: ServerAuthType
  password?: string
  private_key?: string
}

export interface ServerTestResult {
  ok: boolean
  message: string
  latency_ms?: number | null
}

export interface CloneResult {
  output: string
}

export interface UploadResult {
  message: string
  files: number
}

export interface GpuInfo {
  index: number
  name: string
  utilization: number
  memory_used_mb: number
  memory_total_mb: number
}

export interface MemoryInfo {
  used_mb: number
  total_mb: number
}

export interface DiskInfo {
  filesystem: string
  size: string
  used: string
  use_percent?: number | null
  mount: string
}

export interface MonitorData {
  gpu: GpuInfo[]
  load: number[]
  memory: MemoryInfo | null
  disk: DiskInfo[]
  processes: string[]
  raw: Record<string, string>
}

export interface ExecResult {
  output: string
}

export interface AgentToolCall {
  tool: string
  args: Record<string, unknown>
  result: unknown
  status: string
}

export interface AgentPendingApproval {
  tool: string
  args: Record<string, unknown>
}

export interface AgentChatResult {
  session_id: string
  reply: string | null
  tool_calls: AgentToolCall[]
  pending_approval: AgentPendingApproval | null
}

export interface AgentSessionItem {
  id: string
  title: string
  created_at?: string
  updated_at?: string
  running?: boolean
  status?: string
}

export interface AgentSessionMessage {
  role: string
  content: string
}

export interface AgentSessionDetail extends AgentSessionItem {
  messages: AgentSessionMessage[]
}
