import { useMemo, useState } from 'react'
import { Button, Card, Input, Space, Tag } from 'antd'
import { BulbOutlined, DownloadOutlined, ExperimentOutlined, FileSearchOutlined, SearchOutlined, TeamOutlined } from '@ant-design/icons'
import PaperTable from './PaperTable'
import type { PaperWorkspace } from '../hooks/usePaperWorkspace'

interface Props {
  title: string
  workspace: PaperWorkspace
}

export default function PaperWorkspace({ title, workspace }: Props) {
  const {
    papers,
    loading,
    downloading,
    selectedIds,
    setSelectedIds,
    statusMap,
    downloadProgressMap,
    analysisStatusMap,
    analyzingBatch,
    handleDownload,
    handleBatchAnalyze,
    handleOpenReview,
    handleOpenInnovation,
    handleOpenExperiment,
    handleAnalyzeOne,
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
          <Button icon={<ExperimentOutlined />} disabled={!papers.length} onClick={handleOpenExperiment}>
            生成实验方案
          </Button>
        </Space>
      }
    >
      <PaperTable
        papers={filteredPapers}
        loading={loading}
        selectedIds={selectedIds}
        onSelect={setSelectedIds}
        statusMap={statusMap}
        downloadProgressMap={downloadProgressMap}
        showStatus={showStatus}
        analysisStatusMap={analysisStatusMap}
        showAnalysisStatus={Object.keys(analysisStatusMap).length > 0}
        onAnalyze={handleAnalyzeOne}
      />
    </Card>
  )
}
