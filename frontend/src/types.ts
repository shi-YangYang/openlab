export interface Paper {
  arxiv_id: string
  title: string
  authors: string[]
  abstract: string
  categories: string[]
  published: string
  pdf_url: string
}

export interface PaperRecord extends Paper {
  id?: number
  local_pdf_path?: string | null
  status?: string
  progress?: number
  created_at?: string
}

export interface SearchBase {
  max_results: number
  date_from?: string
  date_to?: string
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
