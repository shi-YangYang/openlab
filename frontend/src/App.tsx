import { useCallback, useEffect, useState } from 'react'
import { App as AntApp, Card, Layout, Menu, Typography } from 'antd'
import {
  BookOutlined,
  HistoryOutlined,
  InfoCircleOutlined,
  SearchOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import SearchForm, { SearchFormValues } from './components/SearchForm'
import PaperWorkspace from './components/PaperWorkspace'
import SearchHistoryList from './components/SearchHistoryList'
import LlmConfigForm from './components/LlmConfigForm'
import AnalysisModal from './components/AnalysisModal'
import ReviewModal from './components/ReviewModal'
import { usePaperWorkspace } from './hooks/usePaperWorkspace'
import { searchPapers, searchTopic } from './api'
import type { AnalysisRecord, Paper, SearchHistoryDetail } from './types'

const { Header, Content } = Layout

type PageKey = 'search' | 'library' | 'history' | 'settings'

const MENU_ITEMS: MenuProps['items'] = [
  { key: 'search', icon: <SearchOutlined />, label: '搜索' },
  { key: 'library', icon: <BookOutlined />, label: '论文库' },
  { key: 'history', icon: <HistoryOutlined />, label: '历史搜索' },
  { key: 'settings', icon: <SettingOutlined />, label: '设置' },
]

export default function App() {
  const { message } = AntApp.useApp()
  const [page, setPage] = useState<PageKey>('search')
  const [llmQuery, setLlmQuery] = useState<string | null>(null)
  const [analyzeTarget, setAnalyzeTarget] = useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [reviewIds, setReviewIds] = useState<string[]>([])
  const [reviewOpen, setReviewOpen] = useState(false)

  const openAnalyze = useCallback((arxivId: string) => {
    setAnalyzeTarget(arxivId)
    setDrawerOpen(true)
  }, [])

  const openReview = useCallback((ids: string[]) => {
    setReviewIds(ids)
    setReviewOpen(true)
  }, [])

  const searchWorkspace = usePaperWorkspace({
    onAnalyzeOne: openAnalyze,
    onOpenReview: openReview,
  })
  const libraryWorkspace = usePaperWorkspace({
    onAnalyzeOne: openAnalyze,
    onOpenReview: openReview,
  })

  useEffect(() => {
    void libraryWorkspace.loadLibrary()
  }, [])

  const handleSearch = async (values: SearchFormValues) => {
    const params = {
      max_results: values.max_results,
      date_from: values.date_range?.[0]?.format('YYYY-MM-DD'),
      date_to: values.date_range?.[1]?.format('YYYY-MM-DD'),
    }
    searchWorkspace.setLoading(true)
    setLlmQuery(null)
    try {
      let result: Paper[]
      if (values.mode === 'topic') {
        const res = await searchTopic({ topic: values.query, ...params })
        setLlmQuery(res.query)
        result = res.papers
      } else {
        result = await searchPapers({ query: values.query, ...params })
      }
      searchWorkspace.setResults(result)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '搜索失败')
    } finally {
      searchWorkspace.setLoading(false)
    }
  }

  const handleRestore = (detail: SearchHistoryDetail) => {
    searchWorkspace.setResults(detail.papers)
    setLlmQuery(null)
    setPage('search')
  }

  const handleAnalysisStatus = useCallback(
    (rec: AnalysisRecord) => {
      searchWorkspace.handleAnalysisStatus(rec)
      libraryWorkspace.handleAnalysisStatus(rec)
    },
    [searchWorkspace.handleAnalysisStatus, libraryWorkspace.handleAnalysisStatus],
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginRight: 32, whiteSpace: 'nowrap' }}>
          openlab
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[page]}
          items={MENU_ITEMS}
          onClick={(e) => setPage(e.key as PageKey)}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Header>
      <Content style={{ maxWidth: 1200, width: '100%', margin: '0 auto', padding: 24 }}>
        {page === 'search' && (
          <>
            <Card style={{ marginBottom: 16 }}>
              <SearchForm loading={searchWorkspace.loading} onSubmit={handleSearch} />
              {llmQuery && (
                <Typography.Text
                  type="secondary"
                  style={{ display: 'block', marginTop: 12 }}
                >
                  <InfoCircleOutlined style={{ marginRight: 6 }} />
                  已根据主题拆解为检索式：
                  <Typography.Text code>{llmQuery}</Typography.Text>
                </Typography.Text>
              )}
            </Card>
            <PaperWorkspace
              title={`搜索结果（${searchWorkspace.papers.length}）`}
              workspace={searchWorkspace}
            />
          </>
        )}

        {page === 'library' && (
          <PaperWorkspace
            title={`论文库（${libraryWorkspace.papers.length}）`}
            workspace={libraryWorkspace}
          />
        )}

        {page === 'history' && <SearchHistoryList onRestore={handleRestore} />}

        {page === 'settings' && (
          <Card title="LLM 配置">
            <LlmConfigForm />
          </Card>
        )}

        <AnalysisModal
          arxivId={analyzeTarget}
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          onStatusChange={handleAnalysisStatus}
        />
        <ReviewModal
          arxivIds={reviewIds}
          open={reviewOpen}
          onClose={() => setReviewOpen(false)}
        />
      </Content>
    </Layout>
  )
}
