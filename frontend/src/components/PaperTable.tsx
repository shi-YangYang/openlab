import { Table, Tag, Typography } from 'antd'
import type { TableProps } from 'antd'
import type { Paper } from '../types'

const STATUS_META: Record<string, { color: string; label: string }> = {
  pending: { color: 'gold', label: '待下载' },
  downloading: { color: 'processing', label: '下载中' },
  downloaded: { color: 'success', label: '已下载' },
  failed: { color: 'error', label: '失败' },
  skipped: { color: 'default', label: '已存在' },
}

interface Props {
  papers: Paper[]
  loading: boolean
  selectedIds: string[]
  onSelect: (ids: string[]) => void
  statusMap: Record<string, string>
  showStatus: boolean
}

export default function PaperTable({
  papers,
  loading,
  selectedIds,
  onSelect,
  statusMap,
  showStatus,
}: Props) {
  const columns: TableProps<Paper>['columns'] = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (t: string, r: Paper) => (
        <Typography.Link href={`https://arxiv.org/abs/${r.arxiv_id}`} target="_blank" rel="noreferrer">
          {t}
        </Typography.Link>
      ),
    },
    {
      title: '作者',
      dataIndex: 'authors',
      key: 'authors',
      ellipsis: true,
      render: (a: string[]) => a?.join(', '),
    },
    {
      title: '分类',
      dataIndex: 'categories',
      key: 'categories',
      width: 170,
      render: (c: string[]) => c?.map((x) => <Tag key={x}>{x}</Tag>),
    },
    {
      title: '日期',
      dataIndex: 'published',
      key: 'published',
      width: 110,
      render: (d: string) => (d || '').slice(0, 10),
    },
    {
      title: 'arXiv ID',
      dataIndex: 'arxiv_id',
      key: 'arxiv_id',
      width: 120,
      render: (id: string) => <Typography.Text code>{id}</Typography.Text>,
    },
  ]

  if (showStatus) {
    columns.push({
      title: '状态',
      key: 'status',
      width: 110,
      render: (_: unknown, r: Paper) => {
        const s = statusMap[r.arxiv_id]
        if (!s) return '-'
        const meta = STATUS_META[s] ?? { color: 'default', label: s }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    })
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
      pagination={{ pageSize: 10, showSizeChanger: false }}
      size="middle"
    />
  )
}
