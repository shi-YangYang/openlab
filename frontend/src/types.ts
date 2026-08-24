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
  created_at?: string
}

export interface SearchBase {
  max_results: number
  category?: string
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
