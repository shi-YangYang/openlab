import { useCallback, useEffect, useState } from 'react'
import {
  App as AntApp,
  Button,
  Card,
  Divider,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { TableProps } from 'antd'
import { DeleteOutlined, DownloadOutlined, EyeOutlined } from '@ant-design/icons'
import {
  deleteExperiment,
  exportExperimentMarkdown,
  getExperiment,
  listExperiments,
} from '../api'
import type { ExperimentHistoryItem, ExperimentRecord } from '../types'

const STATUS_META: Record<string, { color: string; label: string }> = {
  pending: { color: 'processing', label: '生成中' },
  running: { color: 'processing', label: '生成中' },
  done: { color: 'success', label: '完成' },
  failed: { color: 'error', label: '失败' },
}

const LANGUAGE_LABEL: Record<string, string> = { zh: '中文', en: 'English' }

function downloadText(text: string, filename: string) {
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function ExperimentHistoryList() {
  const { message } = AntApp.useApp()
  const [items, setItems] = useState<ExperimentHistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<ExperimentRecord | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [exportingId, setExportingId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await listExperiments())
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载实验方案历史失败')
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    void load()
  }, [load])

  const handleView = async (item: ExperimentHistoryItem) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      setDetail(await getExperiment(item.id))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载实验方案快照失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const handleExport = async (item: ExperimentHistoryItem) => {
    setExportingId(item.id)
    try {
      const text = await exportExperimentMarkdown(item.id)
      downloadText(text, `experiments-${item.id}.md`)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导出失败')
    } finally {
      setExportingId(null)
    }
  }

  const handleDelete = async (item: ExperimentHistoryItem) => {
    try {
      await deleteExperiment(item.id)
      message.success('已删除')
      void load()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '删除失败')
    }
  }

  const columns: TableProps<ExperimentHistoryItem>['columns'] = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 190,
    },
    {
      title: '来源',
      dataIndex: 'source_label',
      key: 'source_label',
      width: 180,
      ellipsis: true,
    },
    {
      title: '语言',
      dataIndex: 'language',
      key: 'language',
      width: 90,
      render: (l: string) => LANGUAGE_LABEL[l] ?? l,
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
      title: '方案数',
      dataIndex: 'plan_count',
      key: 'plan_count',
      width: 90,
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_: unknown, r) => (
        <Space size={4}>
          <Button size="small" icon={<EyeOutlined />} onClick={() => void handleView(r)}>
            查看
          </Button>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            disabled={r.status !== 'done'}
            loading={exportingId === r.id}
            onClick={() => void handleExport(r)}
          >
            导出
          </Button>
          <Popconfirm title="确定删除该条实验方案？" onConfirm={() => void handleDelete(r)}>
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
    <Card title="实验方案历史">
      <Table
        rowKey="id"
        dataSource={items}
        columns={columns}
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        size="middle"
      />

      <Modal
        title="实验方案快照"
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
          content.map((plan, i) => (
            <Card key={i} size="small" title={`方案 ${i + 1}`} style={{ marginBottom: 12 }}>
              <Typography.Paragraph>
                <Typography.Text strong>假设：</Typography.Text>
                {plan.hypothesis}
              </Typography.Paragraph>
              <Typography.Paragraph>
                <Typography.Text strong>目标：</Typography.Text>
                {plan.goal}
              </Typography.Paragraph>
              <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                数据集
              </Divider>
              <ul>{plan.datasets.map((d, j) => <li key={j}>{d}</li>)}</ul>
              <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                基线
              </Divider>
              <ul>{plan.baselines.map((b, j) => <li key={j}>{b}</li>)}</ul>
              <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                评价指标
              </Divider>
              <ul>{plan.metrics.map((m, j) => <li key={j}>{m}</li>)}</ul>
            </Card>
          ))
        ) : (
          <Typography.Text type="secondary">该实验方案暂无内容快照。</Typography.Text>
        )}
      </Modal>
    </Card>
  )
}
