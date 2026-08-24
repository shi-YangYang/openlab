import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  App as AntApp,
  Button,
  Card,
  Divider,
  Input,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { TableProps } from 'antd'
import { ClearOutlined, DeleteOutlined, ExperimentOutlined, EyeOutlined, ReadOutlined, SearchOutlined } from '@ant-design/icons'
import { clearInnovations, deleteInnovation, getInnovation, listInnovations, listPapers } from '../api'
import type { InnovationHistoryItem, InnovationRecord, PaperRecord } from '../types'
import { basePaperColumns, paperActionColumn } from './PaperTable'
import ExperimentModal from './ExperimentModal'

const STATUS_META: Record<string, { color: string; label: string }> = {
  pending: { color: 'processing', label: '生成中' },
  running: { color: 'processing', label: '生成中' },
  done: { color: 'success', label: '完成' },
  failed: { color: 'error', label: '失败' },
}

interface Props {
  onAnalyze: (arxivId: string) => void
}

export default function InnovationHistoryList({ onAnalyze }: Props) {
  const { message } = AntApp.useApp()
  const [items, setItems] = useState<InnovationHistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<InnovationRecord | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [sourcePapers, setSourcePapers] = useState<PaperRecord[]>([])
  const [sourceOpen, setSourceOpen] = useState(false)
  const [sourceLoading, setSourceLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [experimentInnovationId, setExperimentInnovationId] = useState<number | null>(null)
  const [experimentOpen, setExperimentOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await listInnovations())
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载创新点历史失败')
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    void load()
  }, [load])

  const handleView = async (item: InnovationHistoryItem) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      setDetail(await getInnovation(item.id))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载创新点快照失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const handleViewSources = async (item: InnovationHistoryItem) => {
    if (!item.arxiv_ids.length) {
      message.info('该创新点无来源论文')
      return
    }
    setSourceOpen(true)
    setSourceLoading(true)
    setSourcePapers([])
    try {
      setSourcePapers(await listPapers(item.arxiv_ids))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载来源论文失败')
    } finally {
      setSourceLoading(false)
    }
  }

  const handleDelete = async (item: InnovationHistoryItem) => {
    try {
      await deleteInnovation(item.id)
      message.success('已删除')
      void load()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '删除失败')
    }
  }

  const handleGenerateExperiment = (item: InnovationHistoryItem) => {
    setExperimentInnovationId(item.id)
    setExperimentOpen(true)
  }

  const handleClear = async () => {
    try {
      await clearInnovations()
      message.success('已删除全部创新点历史')
      void load()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '清空失败')
    }
  }

  const filteredItems = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return items
    return items.filter((item) =>
      (item.arxiv_ids || []).join(' ').toLowerCase().includes(kw),
    )
  }, [items, keyword])

  const columns: TableProps<InnovationHistoryItem>['columns'] = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 190,
    },
    {
      title: '来源论文',
      key: 'arxiv_ids',
      width: 120,
      render: (_: unknown, r) => <Typography.Text>{r.paper_count} 篇</Typography.Text>,
    },
    {
      title: '创新点数量',
      dataIndex: 'innovation_count',
      key: 'innovation_count',
      width: 110,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => {
        const meta = STATUS_META[s] ?? { color: 'default', label: s }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 300,
      render: (_: unknown, r) => (
        <Space size={4}>
          <Button size="small" icon={<EyeOutlined />} onClick={() => void handleView(r)}>
            查看
          </Button>
          <Button size="small" icon={<ReadOutlined />} onClick={() => void handleViewSources(r)}>
            来源
          </Button>
          <Button
            size="small"
            icon={<ExperimentOutlined />}
            disabled={r.status !== 'done'}
            onClick={() => handleGenerateExperiment(r)}
          >
            实验方案
          </Button>
          <Popconfirm title="确定删除该条创新点历史？" onConfirm={() => void handleDelete(r)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const content = detail?.content

  return (
    <Card
      title="创新点历史"
      extra={
        <Space wrap>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="按来源论文 arXiv ID 过滤"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 200 }}
          />
          <Popconfirm title="确认删除全部创新点历史？" onConfirm={() => void handleClear()}>
            <Button danger icon={<ClearOutlined />} disabled={!items.length}>
              删除全部
            </Button>
          </Popconfirm>
        </Space>
      }
    >
      <Table
        rowKey="id"
        dataSource={filteredItems}
        columns={columns}
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        size="middle"
      />

      <Modal
        title="创新点快照"
        open={detailLoading || detail != null}
        onCancel={() => setDetail(null)}
        footer={null}
        width={720}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <Spin tip="加载中..." />
          </div>
        ) : detail == null ? null : content && content.length ? (
          content.map((point, i) => (
            <Card
              key={i}
              size="small"
              title={`创新点 ${i + 1}：${point.title}`}
              style={{ marginBottom: 12 }}
            >
              <Typography.Paragraph>{point.description}</Typography.Paragraph>
              <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                创新依据
              </Divider>
              <ul>{point.basis.map((b, j) => <li key={j}>{b}</li>)}</ul>
              <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                预期贡献
              </Divider>
              <Typography.Paragraph>{point.expected_contribution}</Typography.Paragraph>
            </Card>
          ))
        ) : (
          <Typography.Text type="secondary">该创新点历史暂无内容快照。</Typography.Text>
        )}
      </Modal>

      <Modal
        title="来源论文"
        open={sourceOpen}
        onCancel={() => setSourceOpen(false)}
        footer={null}
        width={800}
      >
        {sourceLoading ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <Spin tip="加载中..." />
          </div>
        ) : sourcePapers.length ? (
          <Table
            rowKey="arxiv_id"
            dataSource={sourcePapers}
            columns={[
              ...basePaperColumns(),
              paperActionColumn(
                onAnalyze,
                Object.fromEntries(sourcePapers.map((p) => [p.arxiv_id, p.status ?? ''])),
              ),
            ]}
            pagination={{ pageSize: 10, showSizeChanger: false, hideOnSinglePage: true }}
            size="small"
          />
        ) : (
          <Typography.Text type="secondary">暂无来源论文。</Typography.Text>
        )}
      </Modal>

      <ExperimentModal
        sourceType="innovation"
        innovationId={experimentInnovationId}
        arxivIds={[]}
        open={experimentOpen}
        onClose={() => setExperimentOpen(false)}
      />
    </Card>
  )
}
