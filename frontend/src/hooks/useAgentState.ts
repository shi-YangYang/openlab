import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react'
import { App as AntApp } from 'antd'
import {
  deleteAgentSession,
  exportAgentSession,
  getAgentSession,
  getLlmConfig,
  listAgentSessions,
  renameAgentSession,
  uploadAgentAttachment,
} from '../api'
import { useAgentChannel } from './useAgentChannel'
import type {
  AgentApprovalScope,
  AgentPendingApproval,
  AgentSessionItem,
  AgentSessionUsage,
  AgentUsageInfo,
  AgentWsEvent,
  LlmModelInfo,
  Turn,
} from '../types'
import type { AgentActivity } from '../components/agent/AgentRunningIndicator'

function timestampNow(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`
}

function activityFromStatus(text: string): AgentActivity | null {
  const value = (text || '').trim()
  if (!value) return null
  if (value === 'thinking') {
    return { phase: 'thinking', tool: null, startedAt: Date.now() }
  }
  if (value.startsWith('executing:')) {
    const raw = value.slice('executing:'.length).trim()
    const tool = raw.replace(/\s*\(第\d+步\)\s*$/, '').trim()
    return { phase: 'executing', tool: tool || raw, startedAt: Date.now() }
  }
  return null
}

function lastRunStart(messages: Turn[]): number {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'user') return i
  }
  return -1
}

export function useAgentState() {
  const { message } = AntApp.useApp()
  const [sessions, setSessions] = useState<AgentSessionItem[]>([])
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [activity, setActivity] = useState<AgentActivity | null>(null)
  const [stopPending, setStopPending] = useState(false)
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
  const activeModelRef = useRef<string | null>(null)
  const compactTimerRef = useRef<number | null>(null)
  const wasDisconnectedRef = useRef(false)
  const renamingRef = useRef<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    currentIdRef.current = currentId
  }, [currentId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activity, loading, running])

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
              toolCalls: m.toolCalls ?? [],
              intermediate: m.intermediate ?? false,
              time: m.time ?? (old && old.role === role ? old.time : undefined),
              model: m.model ?? (old && old.role === role ? old.model : undefined),
            }
          }),
        )
        if (detail.running) {
          setRunning(true)
          setActivity(activityFromStatus(detail.status ?? ''))
        } else {
          setRunning(false)
          setActivity(null)
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
    setActivity(null)
    setStopPending(false)
  }, [])

  const applyDone = useCallback(
    (reply: string | null, usageInfo: AgentUsageInfo) => {
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last && last.role === 'assistant' && !last.intermediate && last.toolCalls.length === 0) {
          next[next.length - 1] = { ...last, text: reply || last.text, time: timestampNow() }
        } else if (last && last.role === 'assistant' && !reply) {
          // 运行以工具调用收尾且无最终文本：保留现状，不产生空回复轮
        } else {
          next.push({
            role: 'assistant',
            text: reply ?? '',
            toolCalls: [],
            intermediate: false,
            time: timestampNow(),
            model: activeModelRef.current,
          })
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
          setRunning(true)
          setLoading(false)
          setActivity(activityFromStatus(event.text))
          break
        case 'token': {
          setActivity((prev) =>
            prev && prev.phase === 'streaming'
              ? prev
              : { phase: 'streaming', tool: null, startedAt: Date.now() },
          )
          setMessages((prev) => {
            const next = [...prev]
            const runStart = lastRunStart(next)
            const last = next[next.length - 1]
            const inRun = runStart >= 0 && next.length - 1 > runStart
            if (
              last &&
              last.role === 'assistant' &&
              inRun &&
              !last.intermediate &&
              last.toolCalls.length === 0
            ) {
              next[next.length - 1] = { ...last, text: last.text + event.delta }
            } else {
              next.push({
                role: 'assistant',
                text: event.delta,
                toolCalls: [],
                intermediate: false,
                time: timestampNow(),
                model: activeModelRef.current,
              })
            }
            return next
          })
          break
        }
        case 'tool_call':
          setMessages((prev) => {
            const next = [...prev]
            const runStart = lastRunStart(next)
            for (let k = runStart + 1; k < next.length; k++) {
              const t = next[k]
              if (t.role === 'assistant' && !t.intermediate) {
                next[k] = { ...t, intermediate: true }
              }
            }
            const last = next[next.length - 1]
            const inRun = runStart >= 0 && next.length - 1 > runStart
            if (last && last.role === 'assistant' && inRun && last.toolCalls.length === 0) {
              next[next.length - 1] = {
                ...last,
                toolCalls: [...last.toolCalls, event.entry],
                intermediate: true,
              }
            } else {
              next.push({
                role: 'assistant',
                text: '',
                toolCalls: [event.entry],
                intermediate: true,
                time: timestampNow(),
                model: activeModelRef.current,
              })
            }
            return next
          })
          break
        case 'pending_approval':
          setPendingApproval({ tool: event.tool, args: event.args })
          setActivity(null)
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
    setLoading(true)
    const effectiveModel = model || groupDefaults.model || null
    activeModelRef.current = effectiveModel
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        text,
        toolCalls: [],
        time: timestampNow(),
        model: effectiveModel,
        files: attachments,
      },
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
      setStopPending(true)
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

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = Array.from(e.dataTransfer.files ?? [])
    if (dropped.length) void handleUploadFiles(dropped)
  }

  const handleRemoveFile = (path: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f !== path))
  }

  const respondApproval = (approve: boolean, scope: AgentApprovalScope = 'once') => {
    if (!pendingApproval || offline) return
    const ok = channel.sendApprove(approve, scope)
    if (ok) {
      setPendingApproval(null)
      setRunning(true)
      setActivity({ phase: 'thinking', tool: null, startedAt: Date.now() })
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

  const handleExportCurrent = () => {
    if (currentId) void handleExport(currentId)
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
  const reasoningEffortOptions = [
    { value: '', label: '默认（不设置）' },
    ...(selectedModel?.reasoning_efforts ?? []).map((e) => ({ value: e, label: e })),
  ]

  return {
    sessions,
    sessionsLoading,
    currentId,
    messages,
    input,
    setInput,
    loading,
    running,
    activity,
    stopPending,
    pendingApproval,
    renamingId,
    renameValue,
    setRenameValue,
    models,
    model,
    handleModelChange,
    reasoningEffort,
    setReasoningEffort,
    usage,
    contextLength,
    reasoningEffortOptions,
    compactedVisible,
    uploading,
    dragOver,
    uploadedFiles,
    connectionState,
    offline,
    bottomRef,
    handleSelect,
    handleNew,
    handleSend,
    handleStop,
    handleUploadFiles,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleRemoveFile,
    respondApproval,
    handleExport,
    handleExportCurrent,
    copyText,
    startRename,
    commitRename,
    handleDelete,
  }
}
