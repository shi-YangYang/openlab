import { useCallback, useEffect, useRef, useState, isValidElement, type ReactNode } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Collapse,
  Divider,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Popover,
  Progress,
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
  FileImageOutlined,
  FileOutlined,
  PlusOutlined,
  RobotOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  apiUrl,
  deleteAgentSession,
  exportAgentSession,
  getAgentSession,
  getLlmConfig,
  listAgentSessions,
  renameAgentSession,
  uploadAgentAttachment,
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
  time?: string
  files?: string[]
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

function hhmmNow(): string {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function extractCommand(args: unknown): string | null {
  if (!args || typeof args !== 'object') return null
  const obj = args as Record<string, unknown>
  if (typeof obj.command === 'string' && obj.command.trim()) return obj.command
  const nested = obj.args
  if (nested && typeof nested === 'object') {
    const command = (nested as Record<string, unknown>).command
    if (typeof command === 'string' && command.trim()) return command
  }
  return null
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
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([])

  const currentIdRef = useRef<string | null>(null)
  const compactTimerRef = useRef<number | null>(null)
  const wasDisconnectedRef = useRef(false)
  const renamingRef = useRef<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const dirInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    currentIdRef.current = currentId
  }, [currentId])

  const attachDirectoryInput = useCallback((el: HTMLInputElement | null) => {
    dirInputRef.current = el
    if (el) el.setAttribute('webkitdirectory', '')
  }, [])

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
        setMessages((prev) =>
          detail.messages.map((m, i) => {
            const role: Turn['role'] = m.role === 'user' ? 'user' : 'assistant'
            const old = prev[i]
            return {
              role,
              text: m.content,
              toolCalls: [],
              time: old && old.role === role ? old.time : undefined,
            }
          }),
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
          next[next.length - 1] = { ...last, text: reply ?? '', time: hhmmNow() }
        } else {
          next.push({ role: 'assistant', text: reply ?? '', toolCalls: [], time: hhmmNow() })
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
              next.push({ role: 'assistant', text: event.delta, toolCalls: [], time: hhmmNow() })
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
              next.push({
                role: 'assistant',
                text: '',
                toolCalls: [event.entry],
                time: hhmmNow(),
              })
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
          message.info('任务已中断')
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

  const reloadConfig = useCallback(async () => {
    try {
      const cfg = await getLlmConfig()
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
    } catch {
      // ignore transient errors
    }
  }, [])

  useEffect(() => {
    void reloadConfig()
  }, [reloadConfig])

  useEffect(() => {
    const handler = () => {
      void reloadConfig()
    }
    window.addEventListener('storage', handler)
    window.addEventListener('openlab:llm-updated', handler)
    return () => {
      window.removeEventListener('storage', handler)
      window.removeEventListener('openlab:llm-updated', handler)
    }
  }, [reloadConfig])

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
    setUploadedFiles([])
    setCurrentId(id)
    void refreshDetail(id)
  }

  const handleNew = () => {
    clearRunState()
    setPendingApproval(null)
    setMessages([])
    setUsage(null)
    setInput('')
    setUploadedFiles([])
    resetSelections()
    setCurrentId(null)
  }

  const handleSend = () => {
    const text = input.trim()
    if (!text || loading || running || offline || uploading) return
    const attachments = [...uploadedFiles]
    const notice =
      attachments.length > 0
        ? `${text}\n\n[附件]\n${attachments.map((p) => `- ${p}`).join('\n')}`
        : text
    setInput('')
    setUploadedFiles([])
    setStatusLabel('')
    setLoading(true)
    const hhmm = hhmmNow()
    setMessages((prev) => [
      ...prev,
      { role: 'user', text, toolCalls: [], time: hhmm, files: attachments },
    ])
    const ok = channel.sendChat(notice, { model, reasoningEffort })
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

  const handleUploadFiles = async (files: File[]) => {
    if (files.length === 0) return
    const sid = currentIdRef.current
    if (!sid) {
      message.warning('请先发送消息创建会话')
      return
    }
    const paths: string[] = []
    setUploading(true)
    try {
      for (const file of files) {
        const rel = file.webkitRelativePath || file.name
        const result = await uploadAgentAttachment(sid, file, rel)
        paths.push(result.path)
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : '上传失败')
      return
    } finally {
      setUploading(false)
    }
    setUploadedFiles((prev) => Array.from(new Set([...prev, ...paths])))
    message.success(`已上传 ${paths.length} 个文件，发送消息时将一并提交给 Agent`)
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
        setUploadedFiles([])
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
  const approvalCommand = pendingApproval ? extractCommand(pendingApproval.args) : null
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

  const uploadMenu = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 128 }}>
      <Button size="small" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
        添加文件 / 文件夹
      </Button>
      <Divider style={{ margin: '4px 0' }} />
      <Typography.Text type="secondary" style={{ fontSize: 12, textAlign: 'center' }}>
        更多功能开发中…
      </Typography.Text>
    </div>
  )

  return (
    <div style={{ display: 'flex', alignItems: 'stretch', height: 'calc(100vh - 36px)', overflow: 'hidden' }}>
      <style>{COPY_STYLE_TAG}</style>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? [])
          e.target.value = ''
          void handleUploadFiles(files)
        }}
      />
      <input
        ref={attachDirectoryInput}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? [])
          e.target.value = ''
          void handleUploadFiles(files)
        }}
      />
      <div
        style={{
          width: 240,
          flexShrink: 0,
          background: '#fff',
          border: '1px solid #f0f0f0',
          borderRadius: 8,
        }}
      >
        <div style={{ padding: '12px 12px 12px 0', borderBottom: '1px solid #f0f0f0' }}>
          <Button block icon={<PlusOutlined />} onClick={handleNew}>
            新建会话
          </Button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
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
                      {item.status === 'interrupted' && (
                        <Tag
                          color="orange"
                          style={{ fontSize: 12, lineHeight: '18px', marginInlineEnd: 0 }}
                        >
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
                            onClick={() => void handleExport(item.id)}
                          />
                        </Tooltip>
                        <Button
                          type="text"
                          size="small"
                          icon={<EditOutlined />}
                          onClick={() => startRename(item)}
                        />
                        <Popconfirm
                          title={
                            item.running
                              ? '该会话正在运行，删除将终止任务并删除记录？'
                              : '确认删除该会话？'
                          }
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

      <div style={{ flex: 1, minWidth: 0, minHeight: 0, background: '#fff', border: '1px solid #f0f0f0', borderRadius: 8, display: 'flex', flexDirection: 'column' }}>
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
        {compactedVisible && (
          <div style={{ padding: '8px 16px 0' }}>
            <Tag color="geekblue">已压缩早期历史</Tag>
          </div>
        )}
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            padding: '16px 16px 16px 0',
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
                      {turn.files && turn.files.length > 0 && (
                        <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 4 }}>
                          {turn.files.map((f) => {
                            const isImg = /\.(png|jpe?g|gif|webp|bmp)$/i.test(f)
                            return (
                              <a
                                key={f}
                                href={apiUrl(`/api/agent/sessions/${currentId}/attachments/${encodeURIComponent(f)}`)}
                                target="_blank"
                                rel="noreferrer"
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 6,
                                  background: 'rgba(255,255,255,0.2)',
                                  borderRadius: 6,
                                  padding: '4px 8px',
                                  color: '#fff',
                                  fontSize: 12,
                                  width: 'fit-content',
                                }}
                              >
                                {isImg ? <FileImageOutlined /> : <FileOutlined />}
                                <span>{f.split('/').pop()}</span>
                              </a>
                            )
                          })}
                        </div>
                      )}
                      {turn.time && (
                        <div style={{ textAlign: 'right', marginTop: 2 }}>
                          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                            {turn.time}
                          </Typography.Text>
                        </div>
                      )}
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
                          defaultActiveKey={turn.toolCalls
                            .map((c, j) =>
                              ['error', 'rejected'].includes(c.status) ? `${i}-${j}` : null,
                            )
                            .filter(Boolean) as string[]}
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
                      {turn.time && (
                        <Typography.Text
                          type="secondary"
                          style={{ fontSize: 12, display: 'inline-block' }}
                        >
                          {turn.time}
                        </Typography.Text>
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

        <div style={{ padding: '16px 16px 8px 0' }}>
          {uploadedFiles.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
              {uploadedFiles.map((p) => (
                <Tag
                  key={p}
                  closable
                  color={/\.(png|jpe?g|gif|webp|bmp)$/i.test(p) ? 'cyan' : undefined}
                  onClose={() => setUploadedFiles((prev) => prev.filter((f) => f !== p))}
                >
                  {p}
                </Tag>
              ))}
            </div>
          )}
          <div
            style={{
              border: dragOver ? '2px dashed #1677ff' : '2px solid transparent',
              borderRadius: 6,
              padding: dragOver ? 4 : 6,
              background: dragOver ? 'rgba(22,119,255,0.06)' : undefined,
              transition: 'border-color 0.2s, background 0.2s',
            }}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={(e) => {
              e.preventDefault()
              setDragOver(false)
            }}
            onDrop={(e) => {
              e.preventDefault()
              setDragOver(false)
              const dropped = Array.from(e.dataTransfer.files ?? [])
              if (dropped.length) void handleUploadFiles(dropped)
            }}
          >
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
                  : dragOver
                    ? '松开鼠标即可添加文件'
                    : '输入目标后按 Enter 发送（Shift+Enter 换行），也可拖入文件'
              }
              autoSize={{ minRows: 4, maxRows: 10 }}
              disabled={offline || running || !!pendingApproval}
            />
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              marginTop: 8,
              flexWrap: 'wrap',
            }}
          >
            <Popover content={uploadMenu} trigger="click">
              <Button size="small" icon={<PlusOutlined />} loading={uploading} />
            </Popover>
            <Space size={4} wrap>
              <Select
                size="small"
                style={{ minWidth: 180 }}
                value={model}
                onChange={handleModelChange}
                showSearch
                optionFilterProp="label"
                placeholder="选择模型"
                options={models.map((m) => ({ value: m.id, label: m.id }))}
              />
              <Select
                size="small"
                style={{ minWidth: 110 }}
                placeholder="思考强度"
                value={reasoningEffort ?? ''}
                onChange={(v) => setReasoningEffort(v || undefined)}
                options={reasoningEffortOptions}
              />
            </Space>
            <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
              <Tooltip
                title={
                  usage
                    ? contextLength
                      ? `上下文 ${lastInput.toLocaleString()} / ${contextLength.toLocaleString()} tokens（${Math.round(
                          (lastInput / contextLength) * 100,
                        )}%）`
                      : `已用 ${lastInput.toLocaleString()} tokens`
                    : '暂无用量统计'
                }
              >
                {usage ? (
                  <Progress
                    type="circle"
                    size={22}
                    percent={
                      contextLength ? Math.min(100, Math.round((lastInput / contextLength) * 100)) : 100
                    }
                    showInfo={false}
                    strokeColor={
                      contextLength && lastInput / contextLength > 0.8 ? '#faad14' : '#1677ff'
                    }
                  />
                ) : (
                  <Progress type="circle" size={22} percent={0} showInfo={false} />
                )}
              </Tooltip>
            </div>
            <div style={{ flex: 1 }} />
            {running && !offline ? (
              <Button danger icon={<StopOutlined />} onClick={handleStop} disabled={uploading}>
                停止
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={loading}
                disabled={offline || !!pendingApproval || uploading}
              >
                发送
              </Button>
            )}
          </div>
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
        {approvalCommand ? (
          <>
            <pre
              style={{
                background: '#1e1e1e',
                color: '#fff',
                padding: 12,
                borderRadius: 6,
                fontFamily: 'Consolas, Monaco, monospace',
                fontSize: 14,
                whiteSpace: 'pre-wrap',
              }}
            >
              {approvalCommand}
            </pre>
            <Collapse
              ghost
              size="small"
              items={[
                {
                  key: 'full-args',
                  label: '完整参数',
                  children: (
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
                  ),
                },
              ]}
            />
          </>
        ) : (
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
        )}
      </Modal>
    </div>
  )
}
