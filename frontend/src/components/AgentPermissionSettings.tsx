import { useEffect, useRef, useState } from 'react'
import { App as AntApp, Alert, Button, Input, Radio, Space, Spin, Tag, Typography } from 'antd'
import type { InputRef } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { usePermissions } from '../hooks/usePermissions'
import { AGENT_PERMISSION_MODES } from '../types'
import type { AgentPermissionMode } from '../types'

export default function AgentPermissionSettings() {
  const { message, modal } = AntApp.useApp()
  const {
    loaded,
    error,
    mode,
    commandWhitelist,
    updateMode,
    updateWhitelist,
    resetAll,
    resetWhitelist,
    reload,
  } = usePermissions()
  const [inputVisible, setInputVisible] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const inputRef = useRef<InputRef>(null)

  useEffect(() => {
    if (inputVisible) inputRef.current?.focus()
  }, [inputVisible])

  const handleModeChange = (value: AgentPermissionMode) => {
    if (value === mode) return
    if (value === 'full') {
      modal.confirm({
        title: '切换为完全访问模式？',
        content:
          '全部工具（含远程命令、部署与实验操作）将自动执行、不再逐次询问；仅破坏性命令黑名单仍会强制确认。',
        okText: '确认切换',
        okButtonProps: { danger: true },
        cancelText: '取消',
        onOk: () => updateMode('full'),
      })
      return
    }
    void updateMode(value)
  }

  const addWhitelistEntry = () => {
    const entry = inputValue.trim()
    if (!entry) return
    if (commandWhitelist.includes(entry)) {
      message.warning('该规则已存在')
      setInputValue('')
      return
    }
    setInputValue('')
    void updateWhitelist([...commandWhitelist, entry])
  }

  const removeWhitelistEntry = (entry: string) => {
    void updateWhitelist(commandWhitelist.filter((item) => item !== entry))
  }

  const handleResetAll = () => {
    modal.confirm({
      title: '恢复默认权限配置？',
      content: '将恢复为标准模式与默认远程命令白名单。',
      okText: '恢复默认',
      cancelText: '取消',
      onOk: () => resetAll(),
    })
  }

  const handleResetWhitelist = () => {
    void resetWhitelist().then((ok) => {
      if (ok) message.success('已恢复默认白名单')
    })
  }

  if (error) {
    return (
      <Alert
        type="warning"
        showIcon
        message="加载 Agent 权限失败"
        description={error}
        action={
          <Button size="small" onClick={reload}>
            重试
          </Button>
        }
      />
    )
  }

  if (!loaded) {
    return (
      <div style={{ textAlign: 'center', padding: 24 }}>
        <Spin />
      </div>
    )
  }

  return (
    <div>
      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
        权限模式全局唯一，在任何入口修改后立即生效。破坏性命令与删除服务器等安全底线操作在任何模式下都会要求确认，不可配置。
      </Typography.Text>
      <Radio.Group
        value={mode}
        onChange={(e) => handleModeChange(e.target.value)}
        style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
      >
        {AGENT_PERMISSION_MODES.map((item) => (
          <Radio key={item.value} value={item.value}>
            <Typography.Text strong={item.value === 'standard'}>
              {item.label}
              {item.value === 'standard' ? '（推荐）' : ''}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
              {item.description}
            </Typography.Text>
          </Radio>
        ))}
      </Radio.Group>

      <Typography.Title level={5} style={{ marginTop: 20, marginBottom: 8 }}>
        远程命令白名单
      </Typography.Title>
      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
        命中白名单的远程只读命令自动执行（支持 fnmatch 通配，如 nvidia-smi*）；仅标准模式生效，其他模式下不生效。
      </Typography.Text>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
        {commandWhitelist.map((entry) => (
          <Tag key={entry} closable onClose={() => removeWhitelistEntry(entry)}>
            {entry}
          </Tag>
        ))}
        {inputVisible ? (
          <Input
            ref={inputRef}
            size="small"
            style={{ width: 180 }}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onPressEnter={addWhitelistEntry}
            onBlur={addWhitelistEntry}
            placeholder="如 git pull*"
          />
        ) : (
          <Tag
            onClick={() => setInputVisible(true)}
            style={{ cursor: 'pointer', background: '#fafafa', borderStyle: 'dashed' }}
          >
            <PlusOutlined /> 添加规则
          </Tag>
        )}
      </div>
      <Space style={{ marginTop: 12 }}>
        <Button size="small" onClick={handleResetWhitelist}>
          恢复默认白名单
        </Button>
        <Button size="small" onClick={handleResetAll}>
          恢复默认
        </Button>
      </Space>
    </div>
  )
}
