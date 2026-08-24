import { useCallback, useEffect, useState } from 'react'
import { App as AntApp, Button, Card, Popconfirm, Space, Table, Tag, Typography } from 'antd'
import type { TableProps } from 'antd'
import { ClearOutlined, DeleteOutlined } from '@ant-design/icons'
import {
  clearSearchHistory,
  deleteSearchHistory,
  getSearchHistory,
  listSearchHistory,
} from '../api'
import type { SearchHistoryDetail, SearchHistoryItem } from '../types'

interface Props {
  onRestore: (detail: SearchHistoryDetail) => void
}

const MODE_META: Record<string, { color: string; label: string }> = {
  keyword: { color: 'blue', label: '关键词' },
  topic: { color: 'purple', label: '主题' },
}

export default function SearchHistoryList({ onRestore }: Props) {
  const { message } = AntApp.useApp()
  const [items, setItems] = useState<SearchHistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [restoringId, setRestoringId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await listSearchHistory())
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载历史失败')
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    void load()
  }, [load])

  const handleRestore = async (item: SearchHistoryItem) => {
    setRestoringId(item.id)
    try {
      const detail = await getSearchHistory(item.id)
      onRestore(detail)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '恢复快照失败')
    } finally {
      setRestoringId(null)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteSearchHistory(id)
      message.success('已删除')
      void load()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '删除失败')
    }
  }

  const handleClear = async () => {
    try {
      await clearSearchHistory()
      message.success('已清空全部历史')
      void load()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '清空失败')
    }
  }

  const columns: TableProps<SearchHistoryItem>['columns'] = [
    {
      title: '查询',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
      render: (q: string, r) => (
        <Typography.Link onClick={() => void handleRestore(r)}>{q}</Typography.Link>
      ),
    },
    {
      title: '模式',
      dataIndex: 'mode',
      key: 'mode',
      width: 100,
      render: (m: string) => {
        const meta = MODE_META[m] ?? { color: 'default', label: m }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    },
    {
      title: '结果数',
      dataIndex: 'paper_count',
      key: 'paper_count',
      width: 90,
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 200,
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_: unknown, r) => (
        <Space>
          <Button size="small" loading={restoringId === r.id} onClick={() => void handleRestore(r)}>
            恢复
          </Button>
          <Popconfirm title="确认删除该条历史？" onConfirm={() => void handleDelete(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Card
      title="搜索历史"
      extra={
        <Popconfirm title="确认清空全部历史？" onConfirm={() => void handleClear()}>
          <Button danger icon={<ClearOutlined />} disabled={!items.length}>
            清空全部
          </Button>
        </Popconfirm>
      }
    >
      <Table
        rowKey="id"
        dataSource={items}
        columns={columns}
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        size="middle"
      />
    </Card>
  )
}
