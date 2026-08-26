import { useEffect, useRef, useState } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { Button, Space, Tag, Typography } from 'antd'
import { terminalWsUrl } from '../api'

type ConnState = 'connecting' | 'connected' | 'error' | 'disconnected'

const STATE_META: Record<ConnState, { text: string; color: string }> = {
  connecting: { text: '连接中', color: 'processing' },
  connected: { text: '已连接', color: 'success' },
  error: { text: '错误', color: 'error' },
  disconnected: { text: '已断开', color: 'default' },
}

interface TerminalViewProps {
  path: string
}

export default function TerminalView({ path }: TerminalViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<Terminal | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const [state, setState] = useState<ConnState>('connecting')
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    setState('connecting')
    setError('')

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      scrollback: 1000,
    })
    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(container)
    fitAddon.fit()
    termRef.current = term

    const socket = new WebSocket(terminalWsUrl(path))
    socketRef.current = socket

    const sendResize = () => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
      }
    }

    term.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(data)
      }
    })

    term.onResize(() => {
      fitAddon.fit()
      sendResize()
    })

    socket.onopen = () => {
      setState('connected')
      sendResize()
    }

    socket.onmessage = (event) => {
      if (typeof event.data !== 'string') return
      try {
        const message = JSON.parse(event.data) as { type?: string; message?: unknown }
        if (message?.type === 'error') {
          setState('error')
          setError(typeof message.message === 'string' ? message.message : '连接失败')
          return
        }
      } catch {
        // not JSON -> terminal output
      }
      term.write(event.data)
    }

    socket.onerror = () => {
      setState('error')
      setError('连接失败')
    }

    socket.onclose = () => {
      if (socketRef.current === socket) {
        setState((prev) => (prev === 'error' ? prev : 'disconnected'))
      }
    }

    const onWindowResize = () => {
      fitAddon.fit()
      sendResize()
    }
    window.addEventListener('resize', onWindowResize)

    return () => {
      window.removeEventListener('resize', onWindowResize)
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
      term.dispose()
      termRef.current = null
    }
  }, [path, attempt])

  const disconnect = () => {
    const socket = socketRef.current
    if (socket) {
      try {
        socket.close()
      } catch {
        // ignore
      }
    }
  }

  const reconnect = () => {
    setAttempt((n) => n + 1)
  }

  const meta = STATE_META[state]

  return (
    <div>
      <Space style={{ marginBottom: 8 }}>
        <Tag color={meta.color}>{meta.text}</Tag>
        {state === 'connected' ? (
          <Button size="small" onClick={disconnect}>
            断开
          </Button>
        ) : (
          <Button size="small" onClick={reconnect}>
            重连
          </Button>
        )}
      </Space>
      {error && (
        <Typography.Text type="danger" style={{ display: 'block', marginBottom: 8 }}>
          {error}
        </Typography.Text>
      )}
      <div
        ref={containerRef}
        style={{
          background: '#1e1e1e',
          padding: 8,
          borderRadius: 4,
          height: 320,
          overflow: 'hidden',
        }}
      />
    </div>
  )
}
