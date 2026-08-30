import type { MouseEvent } from 'react'
import { Button, List, Select, Space, Tag, Typography } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import type { LlmGroup } from '../../types'
import styles from './LlmConfigForm.module.css'

interface LlmConfigGroupListProps {
  groups: LlmGroup[]
  activeGroup: string
  selectedId: string | null
  onSelect: (id: string) => void
  onAdd: () => void
  onDelete: (id: string) => void
  onActiveChange: (id: string) => void
}

export default function LlmConfigGroupList({
  groups,
  activeGroup,
  selectedId,
  onSelect,
  onAdd,
  onDelete,
  onActiveChange,
}: LlmConfigGroupListProps) {
  const activeOptions = groups.map((g) => ({ value: g.id, label: g.name || g.id }))

  const handleDeleteClick = (event: MouseEvent<HTMLElement>, id: string) => {
    event.stopPropagation()
    onDelete(id)
  }

  return (
    <Space direction="vertical" className={styles.fullWidth} size={8}>
      <Typography.Text strong>配置组</Typography.Text>
      <Button block icon={<PlusOutlined />} onClick={onAdd}>
        新增配置组
      </Button>
      <Typography.Text type="secondary">当前使用组</Typography.Text>
      <Select value={activeGroup} options={activeOptions} onChange={onActiveChange} />
      <List
        size="small"
        dataSource={groups}
        renderItem={(group) => (
          <List.Item
            onClick={() => onSelect(group.id)}
            className={
              group.id === selectedId
                ? `${styles.groupItem} ${styles.groupItemSelected}`
                : styles.groupItem
            }
            actions={[
              <Button
                key="del"
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={(e) => handleDeleteClick(e, group.id)}
              />,
            ]}
          >
            <Space size={4} direction="vertical" className={styles.fullWidth}>
              <Space size={4}>
                <Typography.Text ellipsis strong={group.id === activeGroup}>
                  {group.name || group.id}
                </Typography.Text>
                {group.id === activeGroup && <Tag color="blue">当前使用</Tag>}
              </Space>
              <Typography.Text type="secondary" className={styles.defaultModelText} ellipsis>
                {group.default_model || '未设置默认模型'}
              </Typography.Text>
            </Space>
          </List.Item>
        )}
      />
    </Space>
  )
}
