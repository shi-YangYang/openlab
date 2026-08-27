import { Button, Popconfirm, Progress, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { TableProps } from 'antd'
import { DeleteOutlined, FilePdfOutlined, FileSearchOutlined, LinkOutlined } from '@ant-design/icons'
import type { AnalysisStatusInfo, Paper } from '../types'

export const SOURCE_LABELS: Record<string, string> = {
  arxiv: 'arXiv',
  semantic_scholar: 'Semantic Scholar',
  baidu_xueshu: '百度学术',
  cnki: '知网 CNKI',
  upload: '个人上传',
}

const STATUS_META: Record<string, { color: string; label: string }> = {
  pending: { color: 'gold', label: '待下载' },
  downloading: { color: 'processing', label: '下载中' },
  downloaded: { color: 'success', label: '已下载' },
  skipped: { color: 'default', label: '已存在' },
}

const ANALYSIS_STATUS_META: Record<string, { color: string; label: string }> = {
  pending: { color: 'gold', label: '待分析' },
  running: { color: 'processing', label: '分析中' },
  done: { color: 'success', label: '已完成' },
  failed: { color: 'error', label: '失败' },
}

interface Props {
  papers: Paper[]
  loading: boolean
  selectedIds: string[]
  onSelect: (ids: string[]) => void
  statusMap: Record<string, string>
  errorMap?: Record<string, string>
  downloadProgressMap?: Record<string, number>
  showStatus: boolean
  analysisStatusMap?: Record<string, AnalysisStatusInfo>
  showAnalysisStatus?: boolean
  onAnalyze?: (arxivId: string) => void
  onDelete?: (arxivId: string) => void
}

export function basePaperColumns(): NonNullable<TableProps<Paper>['columns']> {
  return [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (t: string, r: Paper) => {
        const isArxiv = !r.source || r.source === 'arxiv'
        const href = isArxiv ? `https://arxiv.org/abs/${r.arxiv_id}` : (r.url || '')
        if (!href) return <Typography.Text>{t}</Typography.Text>
        return (
          <Typography.Link href={href} target="_blank" rel="noreferrer">
            {t}
          </Typography.Link>
        )
      },
    },
    {
      title: '作者',
      dataIndex: 'authors',
      key: 'authors',
      ellipsis: true,
      render: (a: string[]) => a?.join(', '),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 130,
      render: (s: string) => <Tag>{SOURCE_LABELS[s] ?? s ?? '-'}</Tag>,
    },
    {
      title: '日期',
      dataIndex: 'published',
      key: 'published',
      width: 110,
      render: (d: string) => (d || '').slice(0, 10),
    },
  ]
}

export function paperActionColumn(
  onAnalyze: (arxivId: string) => void,
  statusMap: Record<string, string>,
  onDelete?: (arxivId: string) => void,
): NonNullable<TableProps<Paper>['columns']>[number] {
  return {
    title: '操作',
    key: 'actions',
    width: 280,
    render: (_: unknown, r: Paper) => {
      const downloaded = statusMap[r.arxiv_id] === 'downloaded'
      const isArxiv = !r.source || r.source === 'arxiv'
      const isBaidu = r.source === 'baidu_xueshu'
      return (
        <Space size={4}>
          {!isBaidu && (
            <Tooltip title={downloaded ? undefined : '请先下载该论文'}>
              <Button
                size="small"
                icon={<FileSearchOutlined />}
                disabled={!downloaded}
                onClick={() => onAnalyze(r.arxiv_id)}
              >
                分析
              </Button>
            </Tooltip>
          )}
          {!isArxiv && r.url && (
            <Button
              size="small"
              type="link"
              icon={<LinkOutlined />}
              href={r.url}
              target="_blank"
              rel="noreferrer"
            >
              查看原文
            </Button>
          )}
          {downloaded && (
            <Button
              size="small"
              type="link"
              icon={<FilePdfOutlined />}
              href={`/api/papers/${r.arxiv_id}/pdf`}
              target="_blank"
              rel="noreferrer"
            >
              查看论文
            </Button>
          )}
          {onDelete && (
            <Popconfirm title="确定删除该论文？将同时清理本地 PDF。" onConfirm={() => onDelete(r.arxiv_id)}>
              <Button size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      )
    },
  }
}

export default function PaperTable({
  papers,
  loading,
  selectedIds,
  onSelect,
  statusMap,
  errorMap = {},
  downloadProgressMap = {},
  showStatus,
  analysisStatusMap = {},
  showAnalysisStatus = false,
  onAnalyze,
  onDelete,
}: Props) {
  const columns = basePaperColumns()

  if (showStatus) {
    columns.push({
      title: '状态',
      key: 'status',
      width: 150,
      render: (_: unknown, r: Paper) => {
        const s = statusMap[r.arxiv_id]
        if (!s) return '-'
        if (s === 'downloading') {
          return (
            <Progress
              percent={downloadProgressMap[r.arxiv_id] ?? 0}
              size="small"
              style={{ width: 100 }}
            />
          )
        }
        if (s === 'failed') {
          const reason = errorMap[r.arxiv_id] || '失败'
          return <Tag color="error">{reason}</Tag>
        }
        const meta = STATUS_META[s] ?? { color: 'default', label: s }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    })
  }

  if (showAnalysisStatus) {
    columns.push({
      title: '分析',
      key: 'analysis_status',
      width: 220,
      render: (_: unknown, r: Paper) => {
        const info = analysisStatusMap[r.arxiv_id]
        if (!info) return '-'
        if (info.status === 'running') {
          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <Progress
                percent={info.progress ?? 0}
                size="small"
                showInfo={false}
              />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {`${info.progress ?? 0}%${info.message ? ` ${info.message}` : ''}`}
              </Typography.Text>
            </div>
          )
        }
        const meta = ANALYSIS_STATUS_META[info.status] ?? { color: 'default', label: info.status }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    })
  }

  if (onAnalyze) {
    columns.push(paperActionColumn(onAnalyze, statusMap, onDelete))
  }

  return (
    <Table
      rowKey="arxiv_id"
      dataSource={papers}
      columns={columns}
      loading={loading}
      rowSelection={{
        selectedRowKeys: selectedIds,
        onChange: (keys) => onSelect(keys.map(String)),
        preserveSelectedRowKeys: true,
      }}
      expandable={{
        expandedRowRender: (r: Paper) => (
          <Typography.Paragraph style={{ margin: 0 }}>{r.abstract}</Typography.Paragraph>
        ),
      }}
      pagination={{ pageSize: 10, showSizeChanger: true, pageSizeOptions: [10, 20, 50, 100] }}
      size="middle"
    />
  )
}
