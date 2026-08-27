import { useCallback, useEffect, useRef, useState, isValidElement, type ReactNode } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Collapse,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import {
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  ExportOutlined,
  PlusOutlined,
  RobotOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  deleteAgentSession,
  exportAgentSession,
  getAgentSession,
  getLlmConfig,
  listAgentSessions,
  renameAgentSession,
} from '../api'
import { useAgentChannel } from '../hooks/useAgentChannel'
import type {
  AgentPendingApproval,
  AgentSessionItem,
  AgentSessionUsage,
  AgentToolCall,
  AgentUsageInfo,
  AgentWsEvent,
  LlmModelInfo,
} from '../types'

interface Turn {
  role: 'user' | 'assistant'
  text: string
  toolCalls: AgentToolCall[]
}

const STATUS_META: Record<string, { color: string; label: string }> = {
  done: { color: 'green', label: '完成' },
  error: { color: 'red', label: '失败' },
  rejected: { color: 'orange', label: '已拒绝' },
}

const COPY_STYLE_TAG = `
.turn-wrap{position:relative}
.turn-wrap .turn-copy{opacity:0;transition:opacity .15s}
.turn-wrap:hover .turn-copy{opacity:1}
.md-code{position:relative}
.md-code .code-copy{opacity:0;transition:opacity .15s}
.md-code:hover .code-copy{opacity:1}
`

function formatValue(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function formatTime(value?: string): string {
  if (!value) return ''
  return String(value).replace('T', ' ').replace('Z', '').slice(0, 16)
}

function runningStatusLabel(status?: string): string {
  if (status === 'thinking') return '思考中…'
  if (status && status.startsWith('executing:')) {
    return `执行中：${status.slice('executing:'.length).trim()}`
  }
  return 'Agent 正在执行…'
}

function nodeText(node: ReactNode): string {
  if (node == null || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(nodeText).join('')
  if (isValidElement(node)) {
    const props = node.props as { children?: ReactNode }
    return nodeText(props.children)
  }
  return ''
}

export default function AgentPage() {
  const { message } = AntApp.useApp()
  const [sessions, setSessions] = useState<AgentSessionItem[]>([])
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [statusLabel, setStatusLabel] = useState('')
  const [pendingApproval, setPendingApproval] = useState<AgentPendingApproval | null>(null)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [models, setModels] = useState<LlmModelInfo[]>([])
  const [model, setModel] = useState<string | undefined>(undefined)
  const [reasoningEffort, setReasoningEffort] = useState<string | undefined>(undefined)
  const [usage, setUsage] = useState<AgentSessionUsage | null>(null)
  const [compactedVisible, setCompactedVisible] = useState(false)
  const [groupDefaults, setGroupDefaults] = useState<{ model: string }>({
    model: '',
  })

  const currentIdRef = useRef<string | null>(null)
  const compactTimerRef = useRef<number | null>(null)
  const wasDisconnectedRef = useRef(false)
  const renamingRef = useRef<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    currentIdRef.current = currentId
  }, [currentId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, statusLabel, loading, running])

  useEffect(
    () => () => {
      if (compactTimerRef.current != null) {
        window.clearTimeout(compactTimerRef.current)
      }
    },
    [],
  )

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true)
    try {
      setSessions(await listAgentSessions())
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载会话列表失败')
    } finally {
      setSessionsLoading(false)
    }
  }, [message])

  const refreshDetail = useCallback(
    async (id: string) => {
      try {
        const detail = await getAgentSession(id)
        if (currentIdRef.current !== id) return
        setUsage(detail.usage ?? null)
        setMessages(
          detail.messages.map((m) => ({
            role: m.role === 'user' ? 'user' : 'assistant',
            text: m.content,
            toolCalls: [],
          })),
        )
        if (detail.running) {
          setRunning(true)
          setStatusLabel(runningStatusLabel(detail.status))
        } else {
          setRunning(false)
          setStatusLabel('')
        }
      } catch (e) {
        setRunning(false)
        message.error(e instanceof Error ? e.message : '加载会话失败')
      }
    },
    [message],
  )

  const clearRunState = useCallback(() => {
    setRunning(false)
    setLoading(false)
    setStatusLabel('')
  }, [])

  const applyDone = useCallback(
    (reply: string | null, usageInfo: AgentUsageInfo) => {
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last && last.role === 'assistant') {
          next[next.length - 1] = { ...last, text: reply ?? '' }
        } else {
          next.push({ role: 'assistant', text: reply ?? '', toolCalls: [] })
        }
        return next
      })
      setUsage({
        input_tokens: usageInfo.input_tokens,
        output_tokens: usageInfo.output_tokens,
        total_tokens: usageInfo.total_tokens,
        message_count: usageInfo.message_count,
        last_input_tokens: usageInfo.input_tokens,
        last_output_tokens: usageInfo.output_tokens,
      })
      const sid = currentIdRef.current
      if (sid) {
        void getAgentSession(sid)
          .then((d) => {
            if (currentIdRef.current !== sid) return
            if (d.usage) setUsage(d.usage)
          })
          .catch(() => {})
      }
      clearRunState()
      void loadSessions()
    },
    [clearRunState, loadSessions],
  )

  const handleEvent = useCallback(
    (event: AgentWsEvent) => {
      switch (event.type) {
        case 'session':
          setCurrentId(event.session_id)
          void loadSessions()
          break
        case 'status':
          setStatusLabel(runningStatusLabel(event.text))
          setRunning(true)
          setLoading(false)
          break
        case 'token':
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last && last.role === 'assistant') {
              next[next.length - 1] = { ...last, text: last.text + event.delta }
            } else {
              next.push({ role: 'assistant', text: event.delta, toolCalls: [] })
            }
            return next
          })
          break
        case 'tool_call':
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last && last.role === 'assistant') {
              next[next.length - 1] = {
                ...last,
                toolCalls: [...last.toolCalls, event.entry],
              }
            } else {
              next.push({ role: 'assistant', text: '', toolCalls: [event.entry] })
            }
            return next
          })
          break
        case 'pending_approval':
          setPendingApproval({ tool: event.tool, args: event.args })
          clearRunState()
          break
        case 'done':
          applyDone(event.reply, event.usage)
          break
        case 'stopped':
          message.info('本次执行已中断，已保留部分内容')
          clearRunState()
          {
            const sid = currentIdRef.current
            if (sid) void refreshDetail(sid)
          }
          break
        case 'error':
          message.error(event.message)
          clearRunState()
          break
        case 'compacted':
          setCompactedVisible(true)
          if (compactTimerRef.current != null) {
            window.clearTimeout(compactTimerRef.current)
          }
          compactTimerRef.current = window.setTimeout(() => {
            setCompactedVisible(false)
          }, 6000)
          break
      }
    },
    [applyDone, clearRunState, loadSessions, message, refreshDetail],
  )

  const channel = useAgentChannel({ sessionId: currentId, onEvent: handleEvent })
  const { connectionState } = channel

  useEffect(() => {
    if (connectionState === 'reconnecting' || connectionState === 'closed') {
      wasDisconnectedRef.current = true
      return
    }
    if (connectionState === 'open' && wasDisconnectedRef.current) {
      wasDisconnectedRef.current = false
      const sid = currentIdRef.current
      if (sid) void refreshDetail(sid)
    }
  }, [connectionState, refreshDetail])

  const offline = connectionState !== 'open'

  const resetSelections = useCallback(() => {
    setModel(groupDefaults.model)
    setReasoningEffort(undefined)
  }, [groupDefaults])

  const handleModelChange = (value: string | undefined) => {
    setModel(value)
    setReasoningEffort(undefined)
  }

  useEffect(() => {
    let cancelled = false
    getLlmConfig()
      .then((cfg) => {
        if (cancelled) return
        const group = cfg.groups.find((g) => g.id === cfg.active_group) ?? cfg.groups[0]
        if (group) {
          setModels(group.models)
          const defaultModelId = group.default_model || group.models[0]?.id || ''
          const defaults = {
            model: defaultModelId,
          }
          setGroupDefaults(defaults)
          setModel(defaults.model)
          setReasoningEffort(undefined)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    void (async () => {
      setSessionsLoading(true)
      try {
        const list = await listAgentSessions()
        setSessions(list)
        if (list.length > 0) {
          setCurrentId(list[0].id)
          await refreshDetail(list[0].id)
        }
      } catch (e) {
        message.error(e instanceof Error ? e.message : '加载会话失败')
      } finally {
        setSessionsLoading(false)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSelect = (id: string) => {
    if (id === currentId) return
    clearRunState()
    setPendingApproval(null)
    setMessages([])
    setUsage(null)
    setCurrentId(id)
    void refreshDetail(id)
  }

  const handleNew = () => {
    clearRunState()
    setPendingApproval(null)
    setMessages([])
    setUsage(null)
    setInput('')
    resetSelections()
    setCurrentId(null)
  }

  const handleSend = () => {
    const text = input.trim()
    if (!text || loading || running || offline) return
    setInput('')
    setStatusLabel('')
    setLoading(true)
    setMessages((prev) => [...prev, { role: 'user', text, toolCalls: [] }])
    const ok = channel.sendChat(text, { model, reasoningEffort })
    if (!ok) {
      message.error('连接未就绪，请稍后再试')
      setLoading(false)
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last && last.role === 'user' && last.text === text) next.pop()
        return next
      })
    }
  }

  const handleStop = () => {
    if (offline) return
    const ok = channel.sendStop()
    if (ok) {
      setStatusLabel('正在停止…')
    } else {
      message.error('发送停止指令失败')
    }
  }

  const respondApproval = (approve: boolean) => {
    if (!pendingApproval || offline) return
    const ok = channel.sendApprove(approve)
    if (ok) {
      setPendingApproval(null)
      setRunning(true)
      setStatusLabel(approve ? '正在执行批准的操作…' : '')
    } else {
      message.error('发送确认指令失败，请重试')
    }
  }

  const handleExport = async (id: string) => {
    try {
      await exportAgentSession(id)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导出失败')
    }
  }

  const copyText = async (text: string) => {
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      message.success('已复制')
    } catch {
      message.error('复制失败')
    }
  }

  const startRename = (item: AgentSessionItem) => {
    renamingRef.current = item.id
    setRenamingId(item.id)
    setRenameValue(item.title || '')
  }

  const commitRename = async () => {
    const id = renamingRef.current
    if (!id) return
    renamingRef.current = null
    setRenamingId(null)
    const title = renameValue.trim()
    if (!title) return
    try {
      const updated = await renameAgentSession(id, title)
      setSessions((prev) => prev.map((s) => (s.id === id ? updated : s)))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '重命名失败')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteAgentSession(id)
      const remaining = sessions.filter((s) => s.id !== id)
      setSessions(remaining)
      if (id === currentId) {
        clearRunState()
        setPendingApproval(null)
        setMessages([])
        setUsage(null)
        setCurrentId(null)
        if (remaining.length > 0) handleSelect(remaining[0].id)
      }
      message.success('已删除')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '删除失败')
    }
  }

  const selectedModel = models.find((m) => m.id === model)
  const contextLength = selectedModel?.context_length || null
  const lastInput = usage?.last_input_tokens ?? 0
  const reasoningEffortOptions = [
    { value: '', label: '默认（不设置）' },
    ...(selectedModel?.reasoning_efforts ?? []).map((e) => ({ value: e, label: e })),
  ]

  const markdownComponents: Components = {
    pre: ({ children }) => {
      const text = nodeText(children)
      return (
        <div className="md-code">
          <pre>{children}</pre>
          <Tooltip title="复制代码">
            <Button
              className="code-copy"
              size="small"
              type="text"
              icon={<CopyOutlined />}
              onClick={() => void copyText(text)}
            />
          </Tooltip>
        </div>
      )
    },
  }

  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
      <style>{COPY_STYLE_TAG}</style>
      <div
        style={{
          width: 240,
          flexShrink: 0,
          background: '#fff',
          border: '1px solid #f0f0f0',
          borderRadius: 8,
        }}
      >
        <div style={{ padding: 12, borderBottom: '1px solid #f0f0f0' }}>
          <Button block icon={<PlusOutlined />} onClick={handleNew}>
            新建会话
          </Button>
        </div>
        <div style={{ maxHeight: 'calc(100vh - 240px)', overflowY: 'auto' }}>
          {sessionsLoading && sessions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <Spin size="small" />
            </div>
          ) : sessions.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无会话"
              style={{ padding: 24 }}
            />
          ) : (
            sessions.map((item) => (
              <div
                key={item.id}
                onClick={() => handleSelect(item.id)}
                style={{
                  padding: '10px 12px',
                  cursor: 'pointer',
                  background: item.id === currentId ? '#e6f4ff' : 'transparent',
                  borderBottom: '1px solid #f5f5f5',
                }}
              >
                {renamingId === item.id ? (
                  <Input
                    size="small"
                    autoFocus
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onPressEnter={(e) => (e.target as HTMLInputElement).blur()}
                    onBlur={() => void commitRename()}
                  />
                ) : (
                  <>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      <Typography.Text
                        ellipsis
                        strong={item.id === currentId}
                        style={{ flex: 1, minWidth: 0 }}
                      >
                        {item.title || '新会话'}
                      </Typography.Text>
                      <Space size={0} onClick={(e) => e.stopPropagation()}>
                        <Button
                          type="text"
                          size="small"
                          icon={<EditOutlined />}
                          onClick={() => startRename(item)}
                        />
                        <Popconfirm
                          title="确认删除该会话？"
                          onConfirm={() => void handleDelete(item.id)}
                        >
                          <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                        </Popconfirm>
                      </Space>
                    </div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {formatTime(item.updated_at)}
                    </Typography.Text>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      <div style={{ flex: 1, minWidth: 0, background: '#fff', border: '1px solid #f0f0f0', borderRadius: 8 }}>
        {(connectionState === 'reconnecting' || connectionState === 'closed') && (
          <Alert
            type={connectionState === 'closed' ? 'error' : 'warning'}
            showIcon
            style={{ borderRadius: 0 }}
            message={
              connectionState === 'closed'
                ? '连接已断开且自动重连失败'
                : '连接中断，正在自动重连…'
            }
            description={
              connectionState === 'closed'
                ? '请检查后端服务是否可用，刷新页面或重新选择会话以重建连接。'
                : undefined
            }
          />
        )}
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid #f0f0f0',
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <Space size={8}>
            <Typography.Text type="secondary">模型</Typography.Text>
            <Select
              size="small"
              style={{ minWidth: 200 }}
              value={model}
              onChange={handleModelChange}
              showSearch
              optionFilterProp="label"
              placeholder="选择模型"
              options={models.map((m) => ({ value: m.id, label: m.id }))}
            />
          </Space>
          <Space size={8}>
            <Typography.Text type="secondary">思考强度</Typography.Text>
            <Select
              size="small"
              style={{ minWidth: 130 }}
              placeholder="默认"
              value={reasoningEffort ?? ''}
              onChange={(v) => setReasoningEffort(v || undefined)}
              options={reasoningEffortOptions}
            />
          </Space>
          {compactedVisible && (
            <Tag color="geekblue">已压缩早期历史</Tag>
          )}
          <Space size={8} style={{ marginLeft: 'auto' }}>
            {usage && (
              <Typography.Text type="secondary">
                {contextLength
                  ? `上下文 ${lastInput.toLocaleString()} / ${contextLength.toLocaleString()} tokens（${Math.round(
                      (lastInput / contextLength) * 100,
                    )}%）`
                  : `上下文 ${lastInput.toLocaleString()} tokens`}
              </Typography.Text>
            )}
            <Button
              size="small"
              icon={<ExportOutlined />}
              disabled={!currentId || offline}
              onClick={() => currentId && void handleExport(currentId)}
            >
              导出 Markdown
            </Button>
          </Space>
        </div>
        <div
          style={{
            height: 'calc(100vh - 240px)',
            overflowY: 'auto',
            padding: 16,
            background: '#fafafa',
          }}
        >
          {messages.length === 0 && !loading && !running ? (
            <Empty
              style={{ marginTop: 140 }}
              image={<RobotOutlined style={{ fontSize: 48, color: '#bfbfbf' }} />}
              description="输入一个科研目标，Agent 将自主调用工具完成任务"
            />
          ) : (
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              {messages.map((turn, i) =>
                turn.role === 'user' ? (
                  <div key={i} className="turn-wrap" style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <Tooltip title="复制原文">
                      <Button
                        className="turn-copy"
                        size="small"
                        type="text"
                        icon={<CopyOutlined />}
                        style={{ position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)' }}
                        onClick={() => void copyText(turn.text)}
                      />
                    </Tooltip>
                    <div
                      style={{
                        maxWidth: '75%',
                        background: '#1677ff',
                        color: '#fff',
                        padding: '8px 12px',
                        borderRadius: 8,
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {turn.text}
                    </div>
                  </div>
                ) : (
                  <div key={i} className="turn-wrap" style={{ display: 'flex', justifyContent: 'flex-start' }}>
                    <div
                      style={{
                        maxWidth: '85%',
                        background: '#fff',
                        padding: '8px 12px',
                        borderRadius: 8,
                        border: '1px solid #eee',
                      }}
                    >
                      {turn.text ? (
                        <div className="markdown">
                          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                            {turn.text}
                          </ReactMarkdown>
                        </div>
                      ) : null}
                      {turn.toolCalls.length > 0 && (
                        <Collapse
                          ghost
                          size="small"
                          items={turn.toolCalls.map((call, j) => {
                            const meta = STATUS_META[call.status] ?? {
                              color: 'default',
                              label: call.status,
                            }
                            return {
                              key: `${i}-${j}`,
                              label: (
                                <Space size={6}>
                                  <Typography.Text code>{call.tool}</Typography.Text>
                                  <Tag color={meta.color}>{meta.label}</Tag>
                                </Space>
                              ),
                              children: (
                                <div style={{ fontSize: 12 }}>
                                  <Typography.Text type="secondary">参数：</Typography.Text>
                                  <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
                                    {formatValue(call.args)}
                                  </pre>
                                  <Typography.Text type="secondary">结果：</Typography.Text>
                                  <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
                                    {formatValue(call.result)}
                                  </pre>
                                </div>
                              ),
                            }
                          })}
                        />
                      )}
                    </div>
                    <Tooltip title="复制原文">
                      <Button
                        className="turn-copy"
                        size="small"
                        type="text"
                        icon={<CopyOutlined />}
                        style={{ position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)' }}
                        onClick={() => void copyText(turn.text)}
                      />
                    </Tooltip>
                  </div>
                ),
              )}
              {(loading || running) && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#999' }}>
                  <Spin size="small" />
                  <Typography.Text type="secondary">
                    {statusLabel || 'Agent 正在执行…'}
                  </Typography.Text>
                </div>
              )}
              <div ref={bottomRef} />
            </Space>
          )}
        </div>

        {pendingApproval && (
          <Alert
            type="warning"
            showIcon
            style={{ margin: '0 16px 12px' }}
            message={`Agent 请求执行危险操作：${pendingApproval.tool}`}
            description="请在下方确认弹窗中选择「允许」或「拒绝」。"
          />
        )}

        <div style={{ padding: 16 }}>
          <Space.Compact style={{ width: '100%' }}>
            <Input.TextArea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onPressEnter={(e) => {
                if (!e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder={
                connectionState === 'reconnecting' || connectionState === 'closed'
                  ? '连接不可用，等待恢复…'
                  : '例如：搜索注意力机制相关论文，下载并分析前 2 篇'
              }
              autoSize={{ minRows: 4, maxRows: 10 }}
              disabled={offline || running || !!pendingApproval}
            />
            {running && !offline ? (
              <Button danger icon={<StopOutlined />} onClick={handleStop}>
                停止
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={loading}
                disabled={offline || running || !!pendingApproval}
              >
                发送
              </Button>
            )}
          </Space.Compact>
        </div>
      </div>

      <Modal
        title="危险命令确认"
        open={!!pendingApproval}
        closable={false}
        maskClosable={false}
        footer={[
          <Button key="reject" danger disabled={offline} onClick={() => respondApproval(false)}>
            拒绝
          </Button>,
          <Button key="allow" type="primary" disabled={offline} onClick={() => respondApproval(true)}>
            允许执行
          </Button>,
        ]}
      >
        <Typography.Paragraph>
          Agent 想执行危险操作
          <Typography.Text code>{pendingApproval?.tool}</Typography.Text>
          ，请确认以下参数：
        </Typography.Paragraph>
        <pre
          style={{
            background: '#fafafa',
            padding: 12,
            borderRadius: 6,
            whiteSpace: 'pre-wrap',
          }}
        >
          {pendingApproval ? formatValue(pendingApproval.args) : ''}
        </pre>
      </Modal>
    </div>
  )
}
