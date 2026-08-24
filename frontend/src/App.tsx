import { useCallback, useState } from 'react'
import { Alert, App as AntApp, Button, Card, Col, Row, Space, Tag, Typography } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import SearchForm, { SearchFormValues } from './components/SearchForm'
import PaperTable from './components/PaperTable'
import LlmConfigForm from './components/LlmConfigForm'
import { downloadPapers, listPapers, searchPapers, searchTopic } from './api'
import type { Paper } from './types'

export default function App() {
  const { message } = AntApp.useApp()
  const [papers, setPapers] = useState<Paper[]>([])
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [statusMap, setStatusMap] = useState<Record<string, string>>({})
  const [llmQuery, setLlmQuery] = useState<string | null>(null)

  const refreshStatuses = useCallback(async (ids: string[]) => {
    try {
      const records = await listPapers(ids)
      const map: Record<string, string> = {}
      for (const r of records) map[r.arxiv_id] = r.status ?? ''
      setStatusMap((prev) => ({ ...prev, ...map }))
    } catch {
      // ignore status refresh errors
    }
  }, [])

  const pollStatuses = useCallback(async (ids: string[]) => {
    const deadline = Date.now() + 180000
    while (Date.now() < deadline) {
      try {
        const records = await listPapers(ids)
        const map: Record<string, string> = {}
        for (const r of records) map[r.arxiv_id] = r.status ?? ''
        setStatusMap((prev) => ({ ...prev, ...map }))
        const terminal = records.every(
          (r) => r.status === 'downloaded' || r.status === 'failed',
        )
        if (terminal) return
      } catch {
        // ignore transient errors and keep polling
      }
      await new Promise((res) => setTimeout(res, 1500))
    }
  }, [])

  const handleSearch = async (values: SearchFormValues) => {
    const params = {
      max_results: values.max_results,
      category: values.category || undefined,
      date_from: values.date_range?.[0]?.format('YYYY-MM-DD'),
      date_to: values.date_range?.[1]?.format('YYYY-MM-DD'),
    }
    setLoading(true)
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
      setPapers(result)
      setSelectedIds([])
      if (result.length) void refreshStatuses(result.map((p) => p.arxiv_id))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '搜索失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async () => {
    const targets = selectedIds.length
      ? papers.filter((p) => selectedIds.includes(p.arxiv_id))
      : papers
    if (!targets.length) {
      message.warning('没有可下载的论文')
      return
    }
    setDownloading(true)
    try {
      const res = await downloadPapers(targets)
      const next: Record<string, string> = {}
      for (const id of res.accepted) next[id] = 'downloading'
      for (const id of res.skipped) next[id] = 'downloaded'
      setStatusMap((prev) => ({ ...prev, ...next }))
      message.info(`下载已提交：新增 ${res.accepted.length} 篇，跳过已存在 ${res.skipped.length} 篇`)
      if (res.accepted.length) void pollStatuses(res.accepted)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '下载失败')
    } finally {
      setDownloading(false)
    }
  }

  const showStatus = Object.keys(statusMap).length > 0

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>
      <Typography.Title level={3}>openlab · 文献搜索与下载（arXiv）</Typography.Title>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={16}>
          <Card>
            <SearchForm loading={loading} onSubmit={handleSearch} />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="LLM 配置">
            <LlmConfigForm />
          </Card>
        </Col>
      </Row>
      {llmQuery && (
        <Alert
          style={{ marginBottom: 16 }}
          type="info"
          showIcon
          message="LLM 拆解检索式"
          description={llmQuery}
        />
      )}
      <Card
        title={`搜索结果（${papers.length}）`}
        extra={
          <Space>
            {papers.length > 0 && (
              <Tag>{selectedIds.length ? `已选 ${selectedIds.length} 篇` : '将下载全部'}</Tag>
            )}
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              loading={downloading}
              disabled={!papers.length}
              onClick={handleDownload}
            >
              {selectedIds.length ? '下载选中' : '下载全部'}
            </Button>
          </Space>
        }
      >
        <PaperTable
          papers={papers}
          loading={loading}
          selectedIds={selectedIds}
          onSelect={setSelectedIds}
          statusMap={statusMap}
          showStatus={showStatus}
        />
      </Card>
    </div>
  )
}
