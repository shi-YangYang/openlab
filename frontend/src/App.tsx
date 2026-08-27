import { useCallback, useEffect, useState } from 'react'
import { App as AntApp, Card, Collapse, Layout, Menu, Spin, Typography } from 'antd'
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
import ExperimentHistoryList from './components/ExperimentHistoryList'
import LlmConfigForm from './components/LlmConfigForm'
import ProxySettings from './components/ProxySettings'
import PlatformLogin from './components/PlatformLogin'
import ServersPage from './components/ServersPage'
import ServerDetailPage from './components/ServerDetailPage'
import PaperAnalysisPage from './components/PaperAnalysisPage'
import ReviewPage from './components/ReviewPage'
import InnovationPage from './components/InnovationPage'
import ExperimentPage from './components/ExperimentPage'
import AgentPage from './components/AgentPage'
import UploadPdfModal from './components/UploadPdfModal'
import { usePaperWorkspace } from './hooks/usePaperWorkspace'
import { listServers, searchPapers, searchTopic } from './api'
import type { Paper, SearchFallback, SearchHistoryDetail, Server } from './types'

const { Header, Content } = Layout

const MENU_ITEMS: MenuProps['items'] = [
  { key: 'search', icon: <SearchOutlined />, label: '搜索' },
  { key: 'library', icon: <BookOutlined />, label: '论文库' },
  {
    key: 'history',
    icon: <HistoryOutlined />,
    label: '历史',
    children: [
      { key: 'history/search', label: '搜索历史' },
      { key: 'history/innovation', label: '创新点历史' },
      { key: 'history/experiment', label: '实验方案' },
    ],
  },
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
  const [fallbacks, setFallbacks] = useState<SearchFallback[]>([])
  const [uploadOpen, setUploadOpen] = useState(false)

  const openAnalyze = useCallback(
    (arxivId: string) => {
      navigate(`/papers/${arxivId}/analysis`)
    },
    [navigate],
  )

  const openReview = useCallback(
    (ids: string[]) => {
      navigate(`/papers/review?ids=${ids.join(',')}`)
    },
    [navigate],
  )

  const openInnovation = useCallback(
    (ids: string[]) => {
      navigate(`/papers/innovation?ids=${ids.join(',')}`)
    },
    [navigate],
  )

  const searchWorkspace = usePaperWorkspace({
    onAnalyzeOne: openAnalyze,
    onOpenReview: openReview,
    onOpenInnovation: openInnovation,
  })
  const libraryWorkspace = usePaperWorkspace({
    onAnalyzeOne: openAnalyze,
    onOpenReview: openReview,
    onOpenInnovation: openInnovation,
  })

  useEffect(() => {
    if (location.pathname === '/library') {
      void libraryWorkspace.loadLibrary()
    }
  }, [location.pathname, libraryWorkspace.loadLibrary])

  const handleSearch = async (values: SearchFormValues) => {
    const params = {
      max_results: values.max_results,
      date_from: values.date_range?.[0]?.format('YYYY-MM-DD'),
      date_to: values.date_range?.[1]?.format('YYYY-MM-DD'),
      platforms: values.platforms,
    }
    searchWorkspace.setLoading(true)
    setLlmQuery(null)
    setFallbacks([])
    try {
      let result: Paper[]
      if (values.mode === 'topic') {
        const res = await searchTopic({ topic: values.query, ...params })
        setLlmQuery(res.query)
        result = res.papers
        setFallbacks(res.fallbacks ?? [])
      } else {
        const res = await searchPapers({ query: values.query, ...params })
        result = res.papers
        setFallbacks(res.fallbacks ?? [])
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
    setFallbacks([])
    navigate('/search')
  }

  const rawPath = location.pathname
  const selectedKey = rawPath === '/history'
    ? 'history/search'
    : rawPath.startsWith('/history/')
      ? rawPath.slice(1)
      : rawPath.split('/')[1] || 'search'

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
        {fallbacks.length > 0 && (
          <div style={{ marginTop: 12 }}>
            {fallbacks.map((f) => (
              <Typography.Text key={f.platform} type="warning" style={{ display: 'block' }}>
                <InfoCircleOutlined style={{ marginRight: 6 }} />
                {f.need_login
                  ? `「${f.platform}」需要登录，请到设置页完成登录后重试。`
                  : f.expired
                    ? `「${f.platform}」登录态已过期，请到设置页重新登录。`
                    : `「${f.platform}」搜索失败${f.message ? `：${f.message}` : ''}。`}
                <Typography.Link
                  href={f.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ marginLeft: 8 }}
                >
                  前往平台搜索页
                </Typography.Link>
              </Typography.Text>
            ))}
          </div>
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
      onUploadPdf={() => setUploadOpen(true)}
      allowDelete
    />
  )

  const settingsPage = (
    <Collapse
      defaultActiveKey={[]}
      items={[
        { key: 'platform-login', label: '平台登录', children: <PlatformLogin /> },
        { key: 'llm', label: 'LLM 配置', children: <LlmConfigForm /> },
        { key: 'proxy', label: '网络代理', children: <ProxySettings /> },
      ]}
    />
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
          builtinPlacements={{
            bottomLeft: { points: ['tc', 'bc'], overflow: { adjustX: 1, adjustY: 1 } },
          }}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Header>
      <Content style={{ maxWidth: 1600, width: '100%', margin: '0 auto', padding: 24 }}>
        <Routes>
          <Route path="/" element={<Navigate to="/search" replace />} />
          <Route path="/search" element={searchPage} />
          <Route path="/library" element={libraryPage} />
          <Route path="/history" element={<Navigate to="/history/search" replace />} />
          <Route path="/history/search" element={<SearchHistoryList onRestore={handleRestore} />} />
          <Route path="/history/innovation" element={<InnovationHistoryList onAnalyze={openAnalyze} />} />
          <Route path="/history/experiment" element={<ExperimentHistoryList />} />
          <Route path="/servers" element={<ServersPage onOpenDetail={(s) => navigate(`/servers/${s.id}`)} />} />
          <Route path="/servers/:serverId" element={<ServerDetailRoute />} />
          <Route path="/papers/:arxivId/analysis" element={<PaperAnalysisPage />} />
          <Route path="/papers/review" element={<ReviewPage />} />
          <Route path="/papers/innovation" element={<InnovationPage />} />
          <Route path="/papers/experiment" element={<ExperimentPage />} />
          <Route path="/agent" element={<AgentPage />} />
          <Route path="/settings" element={settingsPage} />
          <Route path="*" element={<Navigate to="/search" replace />} />
        </Routes>

        <UploadPdfModal
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onSaved={() => void libraryWorkspace.loadLibrary()}
        />
      </Content>
    </Layout>
  )
}
