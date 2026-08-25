import { useCallback, useEffect, useState } from 'react'
import { App as AntApp, Card, Layout, Menu, Spin, Tabs, Typography } from 'antd'
import { Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  BookOutlined,
  CloudServerOutlined,
  HistoryOutlined,
  InfoCircleOutlined,
  RobotOutlined,
  SearchOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import SearchForm, { SearchFormValues } from './components/SearchForm'
import PaperWorkspace from './components/PaperWorkspace'
import SearchHistoryList from './components/SearchHistoryList'
import InnovationHistoryList from './components/InnovationHistoryList'
import LlmConfigForm from './components/LlmConfigForm'
import ServersPage from './components/ServersPage'
import ServerDetailPage from './components/ServerDetailPage'
import AnalysisModal from './components/AnalysisModal'
import ReviewModal from './components/ReviewModal'
import InnovationModal from './components/InnovationModal'
import ExperimentModal from './components/ExperimentModal'
import AgentPage from './components/AgentPage'
import { usePaperWorkspace } from './hooks/usePaperWorkspace'
import { listServers, searchPapers, searchTopic } from './api'
import type { AnalysisRecord, Paper, SearchHistoryDetail, Server } from './types'

const { Header, Content } = Layout

type PageKey = 'search' | 'library' | 'history' | 'servers' | 'agent' | 'settings'

const MENU_ITEMS: MenuProps['items'] = [
  { key: 'search', icon: <SearchOutlined />, label: '搜索' },
  { key: 'library', icon: <BookOutlined />, label: '论文库' },
  { key: 'history', icon: <HistoryOutlined />, label: '历史' },
  { key: 'servers', icon: <CloudServerOutlined />, label: '服务器' },
  { key: 'agent', icon: <RobotOutlined />, label: 'Agent' },
  { key: 'settings', icon: <SettingOutlined />, label: '设置' },
]

function ServerDetailRoute() {
  const { serverId } = useParams()
  const navigate = useNavigate()
  const [server, setServer] = useState<Server | null>(null)

  useEffect(() => {
    let active = true
    listServers()
      .then((list) => {
        if (active) setServer(list.find((s) => s.id === serverId) ?? null)
      })
      .catch(() => {
        if (active) setServer(null)
      })
    return () => {
      active = false
    }
  }, [serverId])

  if (!server) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin />
      </div>
    )
  }
  return <ServerDetailPage server={server} onBack={() => navigate('/servers')} />
}

export default function App() {
  const { message } = AntApp.useApp()
  const navigate = useNavigate()
  const location = useLocation()
  const [llmQuery, setLlmQuery] = useState<string | null>(null)
  const [analyzeTarget, setAnalyzeTarget] = useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [reviewIds, setReviewIds] = useState<string[]>([])
  const [reviewOpen, setReviewOpen] = useState(false)
  const [innovationIds, setInnovationIds] = useState<string[]>([])
  const [innovationOpen, setInnovationOpen] = useState(false)
  const [experimentIds, setExperimentIds] = useState<string[]>([])
  const [experimentOpen, setExperimentOpen] = useState(false)

  const openAnalyze = useCallback((arxivId: string) => {
    setAnalyzeTarget(arxivId)
    setDrawerOpen(true)
  }, [])

  const openReview = useCallback((ids: string[]) => {
    setReviewIds(ids)
    setReviewOpen(true)
  }, [])

  const openInnovation = useCallback((ids: string[]) => {
    setInnovationIds(ids)
    setInnovationOpen(true)
  }, [])

  const openExperiment = useCallback((ids: string[]) => {
    setExperimentIds(ids)
    setExperimentOpen(true)
  }, [])

  const searchWorkspace = usePaperWorkspace({
    onAnalyzeOne: openAnalyze,
    onOpenReview: openReview,
    onOpenInnovation: openInnovation,
    onOpenExperiment: openExperiment,
  })
  const libraryWorkspace = usePaperWorkspace({
    onAnalyzeOne: openAnalyze,
    onOpenReview: openReview,
    onOpenInnovation: openInnovation,
    onOpenExperiment: openExperiment,
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
    navigate('/search')
  }

  const handleAnalysisStatus = useCallback(
    (rec: AnalysisRecord) => {
      searchWorkspace.handleAnalysisStatus(rec)
      libraryWorkspace.handleAnalysisStatus(rec)
    },
    [searchWorkspace.handleAnalysisStatus, libraryWorkspace.handleAnalysisStatus],
  )

  const selectedKey = (location.pathname.split('/')[1] || 'search') as PageKey

  const searchPage = (
    <>
      <Card style={{ marginBottom: 16 }}>
        <SearchForm loading={searchWorkspace.loading} onSubmit={handleSearch} />
        {llmQuery && (
          <Typography.Text type="secondary" style={{ display: 'block', marginTop: 12 }}>
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
  )

  const libraryPage = (
    <PaperWorkspace
      title={`论文库（${libraryWorkspace.papers.length}）`}
      workspace={libraryWorkspace}
    />
  )

  const historyPage = (
    <Tabs
      defaultActiveKey="search"
      items={[
        {
          key: 'search',
          label: '搜索历史',
          children: <SearchHistoryList onRestore={handleRestore} />,
        },
        {
          key: 'innovation',
          label: '创新点历史',
          children: <InnovationHistoryList onAnalyze={openAnalyze} />,
        },
      ]}
    />
  )

  const settingsPage = (
    <Card title="LLM 配置">
      <LlmConfigForm />
    </Card>
  )

  return (
    <Layout>
      <Header style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginRight: 32, whiteSpace: 'nowrap' }}>
          openlab
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={MENU_ITEMS}
          onClick={(e) => navigate(`/${e.key}`)}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Header>
      <Content style={{ maxWidth: 1200, width: '100%', margin: '0 auto', padding: 24 }}>
        <Routes>
          <Route path="/" element={<Navigate to="/search" replace />} />
          <Route path="/search" element={searchPage} />
          <Route path="/library" element={libraryPage} />
          <Route path="/history" element={historyPage} />
          <Route path="/servers" element={<ServersPage onOpenDetail={(s) => navigate(`/servers/${s.id}`)} />} />
          <Route path="/servers/:serverId" element={<ServerDetailRoute />} />
          <Route path="/agent" element={<AgentPage />} />
          <Route path="/settings" element={settingsPage} />
          <Route path="*" element={<Navigate to="/search" replace />} />
        </Routes>

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
        <InnovationModal
          arxivIds={innovationIds}
          open={innovationOpen}
          onClose={() => setInnovationOpen(false)}
        />
        <ExperimentModal
          sourceType="papers"
          arxivIds={experimentIds}
          open={experimentOpen}
          onClose={() => setExperimentOpen(false)}
        />
      </Content>
    </Layout>
  )
}
