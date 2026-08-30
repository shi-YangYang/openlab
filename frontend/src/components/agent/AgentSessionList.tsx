import { Button, Empty, Input, Popconfirm, Space, Spin, Tag, Tooltip, Typography } from 'antd'
import { DeleteOutlined, EditOutlined, ExportOutlined, PlusOutlined } from '@ant-design/icons'
import type { ChangeEvent, KeyboardEvent } from 'react'
import type { AgentSessionItem } from '../../types'
import styles from './AgentPage.module.css'

interface AgentSessionListProps {
  sessions: AgentSessionItem[]
  sessionsLoading: boolean
  currentId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onExport: (id: string) => void
  onRename: (item: AgentSessionItem) => void
  renamingId: string | null
  renameValue: string
  setRenameValue: (value: string) => void
  commitRename: () => void
  offline: boolean
}

function formatTime(value?: string): string {
  if (!value) return ''
  return String(value).replace('T', ' ').replace('Z', '').slice(0, 16)
}

export default function AgentSessionList({
  sessions,
  sessionsLoading,
  currentId,
  onSelect,
  onNew,
  onDelete,
  onExport,
  onRename,
  renamingId,
  renameValue,
  setRenameValue,
  commitRename,
  offline,
}: AgentSessionListProps) {
  const handleRenameChange = (e: ChangeEvent<HTMLInputElement>) => {
    setRenameValue(e.target.value)
  }

  const handleRenamePressEnter = (e: KeyboardEvent<HTMLInputElement>) => {
    const target = e.target as HTMLInputElement
    target.blur()
  }

  const handleRenameBlur = () => {
    void commitRename()
  }

  return (
    <div className={styles.sessionPanel}>
      <div className={styles.sessionHeader}>
        <Button block icon={<PlusOutlined />} onClick={onNew}>
          新建会话
        </Button>
      </div>
      <div className={styles.sessionList}>
        {sessionsLoading && sessions.length === 0 ? (
          <div className={styles.sessionLoading}>
            <Spin size="small" />
          </div>
        ) : sessions.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无会话"
            className={styles.sessionEmpty}
          />
        ) : (
          sessions.map((item) => (
            <div
              key={item.id}
              onClick={() => onSelect(item.id)}
              className={`${styles.sessionItem} ${item.id === currentId ? styles.sessionItemActive : ''}`}
            >
              {renamingId === item.id ? (
                <Input
                  size="small"
                  autoFocus
                  value={renameValue}
                  onChange={handleRenameChange}
                  onPressEnter={handleRenamePressEnter}
                  onBlur={handleRenameBlur}
                />
              ) : (
                <>
                  <div className={styles.sessionItemMain}>
                    <Typography.Text
                      ellipsis
                      strong={item.id === currentId}
                      className={styles.sessionTitle}
                    >
                      {item.title || '新会话'}
                    </Typography.Text>
                    {item.status === 'interrupted' && (
                      <Tag color="orange" className={styles.sessionTag}>
                        已中断
                      </Tag>
                    )}
                    <Space size={0} onClick={(e) => e.stopPropagation()}>
                      <Tooltip title="导出 Markdown">
                        <Button
                          type="text"
                          size="small"
                          icon={<ExportOutlined />}
                          disabled={offline}
                          onClick={() => onExport(item.id)}
                        />
                      </Tooltip>
                      <Button
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => onRename(item)}
                      />
                      <Popconfirm
                        title={
                          item.running
                            ? '该会话正在运行，删除将终止任务并删除记录？'
                            : '确认删除该会话？'
                        }
                        onConfirm={() => onDelete(item.id)}
                      >
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    </Space>
                  </div>
                  <Typography.Text type="secondary" className={styles.sessionTime}>
                    {formatTime(item.updated_at)}
                  </Typography.Text>
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
