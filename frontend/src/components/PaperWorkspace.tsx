import { useMemo, useState } from 'react'
import { Button, Card, Input, Popconfirm, Space, Tag } from 'antd'
import { BulbOutlined, DeleteOutlined, DownloadOutlined, FileSearchOutlined, SearchOutlined, TeamOutlined, UploadOutlined } from '@ant-design/icons'
import PaperTable from './PaperTable'
import type { PaperWorkspace } from '../hooks/usePaperWorkspace'

interface Props {
  title: string
  workspace: PaperWorkspace
  onUploadPdf?: () => void
  allowDelete?: boolean
}

export default function PaperWorkspace({ title, workspace, onUploadPdf, allowDelete = false }: Props) {
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

  const filteredPapers = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return papers
    return papers.filter((p) => {
      const title = (p.title || '').toLowerCase()
      const authors = (p.authors || []).join(' ').toLowerCase()
      return title.includes(kw) || authors.includes(kw)
    })
  }, [papers, keyword])

  const showStatus = Object.keys(statusMap).length > 0

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
          {onUploadPdf && (
            <Button icon={<UploadOutlined />} onClick={onUploadPdf}>
              上传 PDF
            </Button>
          )}
          {allowDelete && (
            <Popconfirm
              title={`确定删除选中的 ${selectedIds.length} 篇论文？将同时清理本地 PDF。`}
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
      <PaperTable
        papers={filteredPapers}
        loading={loading}
        selectedIds={selectedIds}
        onSelect={setSelectedIds}
        statusMap={statusMap}
        errorMap={errorMap}
        downloadProgressMap={downloadProgressMap}
        showStatus={showStatus}
        analysisStatusMap={analysisStatusMap}
        showAnalysisStatus={Object.keys(analysisStatusMap).length > 0}
        onAnalyze={handleAnalyzeOne}
        onDelete={allowDelete ? handleDeleteOne : undefined}
      />
    </Card>
  )
}
