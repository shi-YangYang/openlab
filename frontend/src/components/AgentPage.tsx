import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Collapse,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd'
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  RobotOutlined,
  SendOutlined,
} from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  agentApprove,
  agentChat,
  createAgentSession,
  deleteAgentSession,
  getAgentSession,
  listAgentSessions,
  renameAgentSession,
} from '../api'
import type {
  AgentChatResult,
  AgentPendingApproval,
  AgentSessionItem,
  AgentToolCall,
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

export default function AgentPage() {
  const { message } = AntApp.useApp()
  const [sessions, setSessions] = useState<AgentSessionItem[]>([])
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [pendingApproval, setPendingApproval] = useState<AgentPendingApproval | null>(null)
  const [approving, setApproving] = useState(false)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const renamingRef = useRef<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const pollTimerRef = useRef<number | null>(null)
  const currentIdRef = useRef<string | null>(null)

  useEffect(() => {
    currentIdRef.current = currentId
  }, [currentId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

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

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current != null) {
      window.clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  const loadSessionDetail = useCallback(
    async (id: string) => {
      try {
        const detail = await getAgentSession(id)
        if (currentIdRef.current !== id) return
        setMessages(
          detail.messages.map((m) => ({
            role: m.role === 'user' ? 'user' : 'assistant',
            text: m.content,
            toolCalls: [],
          })),
        )
        if (detail.running) {
          setRunning(true)
          pollTimerRef.current = window.setTimeout(() => void loadSessionDetail(id), 2000)
        } else {
          setRunning(false)
        }
      } catch (e) {
        setRunning(false)
        message.error(e instanceof Error ? e.message : '加载会话失败')
      }
    },
    [message],
  )

  useEffect(() => stopPolling, [stopPolling])

  useEffect(() => {
    void (async () => {
      setSessionsLoading(true)
      try {
        const list = await listAgentSessions()
        setSessions(list)
        if (list.length > 0) {
          setCurrentId(list[0].id)
          await loadSessionDetail(list[0].id)
        } else {
          const created = await createAgentSession()
          setSessions([created])
          setCurrentId(created.id)
        }
      } catch (e) {
        message.error(e instanceof Error ? e.message : '加载会话失败')
      } finally {
        setSessionsLoading(false)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const applyResult = (res: AgentChatResult) => {
    setCurrentId(res.session_id)
    if (res.pending_approval) setPendingApproval(res.pending_approval)
    setMessages((prev) => {
      const next = [...prev]
      const last = next[next.length - 1]
      if (last && last.role === 'assistant' && !last.text) {
        last.toolCalls = [...last.toolCalls, ...res.tool_calls]
        if (res.reply) last.text = res.reply
      } else {
        next.push({
          role: 'assistant',
          text: res.reply ?? '',
          toolCalls: res.tool_calls,
        })
      }
      return next
    })
  }

  const handleSelect = async (id: string) => {
    if (id === currentId) return
    stopPolling()
    setRunning(false)
    setCurrentId(id)
    setPendingApproval(null)
    await loadSessionDetail(id)
  }

  const handleNew = async () => {
    try {
      stopPolling()
      setRunning(false)
      const created = await createAgentSession()
      setSessions((prev) => [created, ...prev])
      setCurrentId(created.id)
      setMessages([])
      setPendingApproval(null)
      setInput('')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '新建会话失败')
    }
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setLoading(true)
    try {
      let sid = currentId
      if (!sid) {
        const created = await createAgentSession()
        setSessions((prev) => [created, ...prev])
        sid = created.id
        setCurrentId(sid)
      }
      setMessages((prev) => [...prev, { role: 'user', text, toolCalls: [] }])
      setSessions((prev) =>
        prev.map((s) => (s.id === sid ? { ...s, title: text.slice(0, 30) } : s)),
      )
      const res = await agentChat(sid, text)
      applyResult(res)
      void loadSessions()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (approve: boolean) => {
    if (!currentId) return
    setApproving(true)
    try {
      const res = await agentApprove(currentId, approve)
      setPendingApproval(null)
      applyResult(res)
      void loadSessions()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '确认操作失败')
    } finally {
      setApproving(false)
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
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (id === currentId) {
        setCurrentId(null)
        setMessages([])
        setPendingApproval(null)
      }
      message.success('已删除')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '删除失败')
    }
  }

  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
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
          <Button block type="primary" icon={<PlusOutlined />} onClick={() => void handleNew()}>
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
                onClick={() => void handleSelect(item.id)}
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
        <div
          style={{
            height: 'calc(100vh - 240px)',
            overflowY: 'auto',
            padding: 16,
            background: '#fafafa',
          }}
        >
          {messages.length === 0 && !loading ? (
            <Empty
              style={{ marginTop: 140 }}
              image={<RobotOutlined style={{ fontSize: 48, color: '#bfbfbf' }} />}
              description="输入一个科研目标，Agent 将自主调用工具完成任务"
            />
          ) : (
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              {messages.map((turn, i) =>
                turn.role === 'user' ? (
                  <div key={i} style={{ display: 'flex', justifyContent: 'flex-end' }}>
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
                  <div key={i} style={{ display: 'flex', justifyContent: 'flex-start' }}>
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
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.text}</ReactMarkdown>
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
                  </div>
                ),
              )}
              {(loading || running) && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#999' }}>
                  <Spin size="small" />
                  <Typography.Text type="secondary">Agent 正在执行…</Typography.Text>
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
                  void handleSend()
                }
              }}
              placeholder="例如：搜索注意力机制相关论文，下载并分析前 2 篇"
              autoSize={{ minRows: 1, maxRows: 4 }}
              disabled={loading || running || !!pendingApproval}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={() => void handleSend()}
              loading={loading}
              disabled={running || !!pendingApproval}
            >
              发送
            </Button>
          </Space.Compact>
        </div>
      </div>

      <Modal
        title="危险命令确认"
        open={!!pendingApproval}
        closable={false}
        maskClosable={false}
        footer={[
          <Button key="reject" danger onClick={() => void handleApprove(false)} loading={approving}>
            拒绝
          </Button>,
          <Button key="allow" type="primary" onClick={() => void handleApprove(true)} loading={approving}>
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
