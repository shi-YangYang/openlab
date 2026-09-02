import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { App as AntApp, Button, Card, Dropdown, Empty, Input, Modal, Popconfirm, Space, Tag, Tooltip, Typography } from 'antd'
import type { MenuProps } from 'antd'
import { BulbOutlined, DeleteOutlined, DownloadOutlined, ExportOutlined, FilePdfOutlined, FileSearchOutlined, SearchOutlined, TeamOutlined, TranslationOutlined, UploadOutlined } from '@ant-design/icons'
import PaperTable from './PaperTable'
import { apiUrl, exportCitations, getLlmConfig, getTranslation, getTranslationProgress, searchLibrary, startTranslation } from '../api'
import type { LibrarySearchHit } from '../types'
import type { PaperWorkspace } from '../hooks/usePaperWorkspace'

interface Props {
  title: string
  workspace: PaperWorkspace
  onUploadPdf?: () => void
  allowDelete?: boolean
}

interface TranslateState {
  progress: number
  message: string
  phase: 'idle' | 'running' | 'done'
}

export default function PaperWorkspace({ title, workspace, onUploadPdf, allowDelete = false }: Props) {
  const { message } = AntApp.useApp()
  const {
    papers,
    loading,
    downloading,
    selectedIds,
    setSelectedIds,
    statusMap,
    errorMap,
    downloadProgressMap,
    analysisStatusMap,
    analyzingBatch,
    deleting,
    handleDownload,
    handleBatchAnalyze,
    handleOpenReview,
    handleOpenInnovation,
    handleAnalyzeOne,
    handleDeleteOne,
    handleDeleteMany,
  } = workspace

  const [keyword, setKeyword] = useState('')
  const [exportingCitations, setExportingCitations] = useState(false)
  const [libraryQuery, setLibraryQuery] = useState('')
  const [librarySearching, setLibrarySearching] = useState(false)
  const [libraryResults, setLibraryResults] = useState<LibrarySearchHit[] | null>(null)
  const [translateState, setTranslateState] = useState<Record<string, TranslateState>>({})
  const [translatingCount, setTranslatingCount] = useState(0)
  const [translateError, setTranslateError] = useState<Record<string, string>>({})
  const [confirmTranslate, setConfirmTranslate] = useState<string | null>(null)
  const [viewTranslation, setViewTranslation] = useState<{
    open: boolean
    arxivId: string
    title: string
    content: string
  }>({ open: false, arxivId: '', title: '', content: '' })
  const pollTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) window.clearTimeout(pollTimerRef.current)
    }
  }, [])

  const pollTranslation = useCallback(
    (arxivId: string) => {
      if (pollTimerRef.current) window.clearTimeout(pollTimerRef.current)
      const tick = async () => {
        try {
          const res = await getTranslationProgress(arxivId)
          if (res.translated) {
            setTranslateState((prev) => ({
              ...prev,
              [arxivId]: { progress: 100, message: '翻译完成', phase: 'done' },
            }))
            setTranslatingCount((c) => Math.max(0, c - 1))
            message.success('论文翻译完成')
            return
          }
          setTranslateState((prev) => ({
            ...prev,
            [arxivId]: {
              progress: res.progress ?? 0,
              message: res.message || '',
              phase: 'running',
            },
          }))
        } catch {
          // transient error; keep polling
        }
        pollTimerRef.current = window.setTimeout(() => void tick(), 3000)
      }
      void tick()
    },
    [message],
  )

  const doTranslate = async (arxivId: string) => {
    setTranslateState((prev) => ({
      ...prev,
      [arxivId]: { progress: 2, message: '排队中', phase: 'running' },
    }))
    setTranslatingCount((c) => c + 1)
    try {
      await startTranslation(arxivId, 'zh')
      pollTranslation(arxivId)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '发起翻译失败'
      message.error(msg)
      setTranslateError((prev) => ({ ...prev, [arxivId]: msg }))
      setTranslateState((prev) => ({ ...prev, [arxivId]: { progress: 0, message: '', phase: 'idle' } }))
      setTranslatingCount((c) => Math.max(0, c - 1))
    }
  }

  const handleTranslate = async (arxivId: string) => {
    // Pre-check LLM config
    try {
      const cfg = await getLlmConfig()
      const group = cfg.groups.find((g) => g.id === cfg.active_group) ?? cfg.groups[0]
      if (!group || !group.api_key) {
        message.warning('请先到设置页配置 LLM API Key，否则无法翻译')
        return
      }
    } catch {
      message.warning('无法检查 LLM 配置，请确认后端正常运行')
      return
    }
    // Show confirmation dialog (token cost notice)
    setConfirmTranslate(arxivId)
  }

  const handleConfirmTranslate = async () => {
    const id = confirmTranslate
    setConfirmTranslate(null)
    if (id) await doTranslate(id)
  }

  const handleViewTranslation = async (arxivId: string) => {
    try {
      const res = await getTranslation(arxivId)
      if (!res.translated || !res.content) {
        message.warning('翻译文件不存在，请重新翻译')
        setTranslateState((prev) => ({ ...prev, [arxivId]: { progress: 0, message: '', phase: 'idle' } }))
        return
      }
      const paper = workspace.papers.find((p) => p.arxiv_id === arxivId)
      setViewTranslation({
        open: true,
        arxivId,
        title: paper?.title || arxivId,
        content: res.content,
      })
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载翻译失败')
    }
  }

  const filteredPapers = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return papers
    return papers.filter((p) => {
      const title = (p.title || '').toLowerCase()
      const authors = (p.authors || []).join(' ').toLowerCase()
      return title.includes(kw) || authors.includes(kw)
    })
  }, [papers, keyword])

  const handleLibrarySearch = useCallback(
    async (value: string) => {
      const q = value.trim()
      if (!q) return
      setLibrarySearching(true)
      try {
        const hits = await searchLibrary(q)
        setLibraryResults(hits)
        if (!hits.length) message.info('库内没有匹配的论文，可尝试其他关键词')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '库内检索失败')
      } finally {
        setLibrarySearching(false)
      }
    },
    [message],
  )

  const handleClearLibrarySearch = useCallback(() => {
    setLibraryResults(null)
    setLibraryQuery('')
  }, [])

  const citationMenuItems: MenuProps['items'] = [
    { key: 'bibtex', label: 'BibTeX（papers.bib）' },
    { key: 'gbt7714', label: 'GB/T 7714（references.txt）' },
  ]

  const handleExportCitations = async (format: 'bibtex' | 'gbt7714') => {
    if (!selectedIds.length) {
      message.warning('请先选择至少一篇论文')
      return
    }
    setExportingCitations(true)
    try {
      await exportCitations(selectedIds, format)
      message.success('引用已导出')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导出引用失败')
    } finally {
      setExportingCitations(false)
    }
  }

  // Library full-text results replace the plain filter view when active.
  const displayPapers = libraryResults ?? filteredPapers

  const showStatus = Object.keys(statusMap).length > 0
  const showTranslate = translatingCount > 0 || papers.length > 0

  return (
    <Card
      title={title}
      extra={
        <Space wrap>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="按标题/作者过滤"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 200 }}
          />
          {papers.length > 0 && (
            <Tag>{selectedIds.length ? `已选 ${selectedIds.length} 篇` : '将作用于全部'}</Tag>
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
          <Button
            icon={<FileSearchOutlined />}
            loading={analyzingBatch}
            disabled={!papers.length}
            onClick={handleBatchAnalyze}
          >
            {selectedIds.length ? '分析选中' : '分析全部'}
          </Button>
          <Button icon={<TeamOutlined />} disabled={papers.length < 2} onClick={handleOpenReview}>
            对比综述
          </Button>
          <Button icon={<BulbOutlined />} disabled={!papers.length} onClick={handleOpenInnovation}>
            生成创新点
          </Button>
          <Dropdown
            menu={{
              items: citationMenuItems,
              onClick: ({ key }) => void handleExportCitations(key as 'bibtex' | 'gbt7714'),
            }}
            disabled={selectedIds.length < 1}
          >
            <Button
              icon={<ExportOutlined />}
              loading={exportingCitations}
              disabled={selectedIds.length < 1}
              title={selectedIds.length ? '' : '请先在列表中勾选论文'}
            >
              导出引用
            </Button>
          </Dropdown>
          {onUploadPdf && (
            <Button icon={<UploadOutlined />} onClick={onUploadPdf}>
              上传 PDF
            </Button>
          )}
          {allowDelete && (
            <Popconfirm
              title={`确定删除选中的 ${selectedIds.length} 篇论文？将同时清理本地 PDF 与翻译。`}
              disabled={!selectedIds.length}
              onConfirm={() => void handleDeleteMany(selectedIds)}
            >
              <Button danger icon={<DeleteOutlined />} loading={deleting} disabled={!selectedIds.length}>
                删除选中
              </Button>
            </Popconfirm>
          )}
        </Space>
      }
    >
      <Space wrap style={{ marginBottom: 16 }}>
        <Input.Search
          allowClear
          placeholder="库内全文检索：标题/摘要/分析/关键词"
          value={libraryQuery}
          onChange={(e) => setLibraryQuery(e.target.value)}
          onSearch={(v) => void handleLibrarySearch(v)}
          onClear={handleClearLibrarySearch}
          enterButton
          loading={librarySearching}
          style={{ width: 320 }}
        />
        {libraryResults !== null && (
          <Button onClick={handleClearLibrarySearch}>
            清除检索（{libraryResults.length} 条结果）
          </Button>
        )}
      </Space>
      {libraryResults !== null && libraryResults.length === 0 ? (
        <Empty description="无检索结果，试试其他关键词或清除检索" />
      ) : (
        <PaperTable
          papers={displayPapers}
          loading={loading || librarySearching}
          selectedIds={selectedIds}
          onSelect={setSelectedIds}
          statusMap={statusMap}
          errorMap={errorMap}
          downloadProgressMap={downloadProgressMap}
          showStatus={showStatus}
          analysisStatusMap={analysisStatusMap}
          showAnalysisStatus={Object.keys(analysisStatusMap).length > 0}
          onAnalyze={handleAnalyzeOne}
          translateState={showTranslate ? translateState : undefined}
          translateError={translateError}
          onTranslate={allowDelete ? (id) => void handleTranslate(id) : undefined}
          onViewTranslation={allowDelete ? (id) => void handleViewTranslation(id) : undefined}
        />
      )}

      <Modal
        title={
          <Space>
            <TranslationOutlined />
            <span>论文翻译：{viewTranslation.title || viewTranslation.arxivId}</span>
          </Space>
        }
        open={viewTranslation.open}
        onCancel={() => setViewTranslation((v) => ({ ...v, open: false }))}
        footer={
          <Button
            type="primary"
            icon={<FilePdfOutlined />}
            href={apiUrl(`/api/papers/${encodeURIComponent(viewTranslation.arxivId)}/translation/pdf`)}
            target="_blank"
          >
            打开翻译 PDF
          </Button>
        }
        width={900}
      >
        <div
          style={{
            maxHeight: '65vh',
            overflowY: 'auto',
            background: '#fafafa',
            padding: 16,
            borderRadius: 6,
          }}
          className="markdown"
        >
          <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontFamily: 'inherit' }}>
            {viewTranslation.content}
          </pre>
        </div>
      </Modal>

      <Modal
        title="开始翻译论文"
        open={!!confirmTranslate}
        onOk={() => void handleConfirmTranslate()}
        onCancel={() => setConfirmTranslate(null)}
        okText="开始翻译"
        cancelText="取消"
      >
        <Typography.Paragraph>
          翻译将使用 LLM 对论文全文逐段翻译，请注意：
        </Typography.Paragraph>
        <ul style={{ paddingLeft: 20, fontSize: 13 }}>
          <li>翻译耗时取决于论文长度，通常需要 <b>1-5 分钟</b></li>
          <li>将消耗较多 LLM <b>token 额度</b>（一篇论文约 5-20 万 token）</li>
          <li>翻译期间请勿关闭页面，进度条会实时更新</li>
          <li>翻译完成后可在线查看译文或打开排版 PDF</li>
        </ul>
      </Modal>
    </Card>
  )
}
