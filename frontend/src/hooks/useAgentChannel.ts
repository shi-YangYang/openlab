import { useCallback, useEffect, useRef, useState } from 'react'
import { terminalWsUrl } from '../api'
import type { AgentApprovalScope, AgentWsEvent } from '../types'

export type ConnectionState = 'connecting' | 'open' | 'reconnecting' | 'closed'

const MAX_RETRIES = 5
const BASE_DELAY_MS = 1000

interface UseAgentChannelOptions {
  sessionId: string | null
  onEvent: (event: AgentWsEvent) => void
}

interface SendChatOptions {
  model?: string
  reasoningEffort?: string
}

export interface AgentChannel {
  connectionState: ConnectionState
  sendChat: (message: string, options?: SendChatOptions) => boolean
  sendApprove: (approve: boolean, scope?: AgentApprovalScope) => boolean
  sendStop: () => boolean
}

export function useAgentChannel({ sessionId, onEvent }: UseAgentChannelOptions): AgentChannel {
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting')
  const socketRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const timerRef = useRef<number | null>(null)
  const disposedRef = useRef(false)
  const manualCloseRef = useRef(false)
  const onEventRef = useRef(onEvent)

  useEffect(() => {
    onEventRef.current = onEvent
  })

  useEffect(() => {
    disposedRef.current = false
    manualCloseRef.current = false
    retriesRef.current = 0

    const scheduleReconnect = () => {
      if (disposedRef.current || manualCloseRef.current) return
      if (retriesRef.current >= MAX_RETRIES) {
        setConnectionState('closed')
        return
      }
      const delay = BASE_DELAY_MS * Math.pow(2, retriesRef.current)
      retriesRef.current += 1
      setConnectionState('reconnecting')
      timerRef.current = window.setTimeout(open, delay)
    }

    const open = () => {
      if (disposedRef.current) return
      setConnectionState(retriesRef.current === 0 ? 'connecting' : 'reconnecting')
      let socket: WebSocket
      try {
        socket = new WebSocket(terminalWsUrl(`/api/agent/ws${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''}`))
      } catch {
        scheduleReconnect()
        return
      }
      socketRef.current = socket

      socket.onopen = () => {
        retriesRef.current = 0
        setConnectionState('open')
      }
      socket.onmessage = (event) => {
        if (typeof event.data !== 'string') return
        try {
          const parsed = JSON.parse(event.data)
          if (parsed && typeof parsed.type === 'string') {
            onEventRef.current(parsed as AgentWsEvent)
          }
        } catch {
          // ignore non-JSON frames
        }
      }
      socket.onerror = () => {
        // onclose fires right after; nothing to do here.
      }
      socket.onclose = () => {
        if (socketRef.current !== socket) return
        socketRef.current = null
        if (manualCloseRef.current || disposedRef.current) {
          setConnectionState('closed')
          return
        }
        scheduleReconnect()
      }
    }

    open()

    return () => {
      disposedRef.current = true
      manualCloseRef.current = true
      if (timerRef.current != null) {
        window.clearTimeout(timerRef.current)
        timerRef.current = null
      }
      const socket = socketRef.current
      if (socket) {
        socket.onopen = null
        socket.onmessage = null
        socket.onerror = null
        socket.onclose = null
        try {
          socket.close()
        } catch {
          // ignore
        }
        socketRef.current = null
      }
    }
  }, [sessionId])

  const sendRaw = useCallback((payload: Record<string, unknown>): boolean => {
    const socket = socketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) return false
    socket.send(JSON.stringify(payload))
    return true
  }, [])

  const sendChat = useCallback(
    (message: string, options?: SendChatOptions): boolean => {
      const payload: Record<string, unknown> = { type: 'chat', message }
      if (options?.model) payload.model = options.model
      if (options?.reasoningEffort) payload.reasoning_effort = options.reasoningEffort
      return sendRaw(payload)
    },
    [sendRaw],
  )

  const sendApprove = useCallback(
    (approve: boolean, scope: AgentApprovalScope = 'once'): boolean =>
      sendRaw({ type: 'approve', approve, scope }),
    [sendRaw],
  )

  const sendStop = useCallback((): boolean => sendRaw({ type: 'stop' }), [sendRaw])

  return { connectionState, sendChat, sendApprove, sendStop }
}
