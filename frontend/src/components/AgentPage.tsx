import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Collapse,
  Empty,
  Input,
  Modal,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd'
import { ClearOutlined, RobotOutlined, SendOutlined } from '@ant-design/icons'
import { agentApprove, agentChat } from '../api'
import type { AgentChatResult, AgentPendingApproval, AgentToolCall } from '../types'

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

export default function AgentPage() {
  const { message } = AntApp.useApp()
  const [messages, setMessages] = useState<Turn[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [pendingApproval, setPendingApproval] = useState<AgentPendingApproval | null>(null)
  const [approving, setApproving] = useState(false)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const applyResult = (res: AgentChatResult) => {
    setSessionId(res.session_id)
    if (res.pending_approval) {
      setPendingApproval(res.pending_approval)
    }
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

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text, toolCalls: [] }])
    setLoading(true)
    try {
      const res = await agentChat(sessionId, text)
      applyResult(res)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (approve: boolean) => {
    if (!sessionId) return
    setApproving(true)
    try {
      const res = await agentApprove(sessionId, approve)
      setPendingApproval(null)
      applyResult(res)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '确认操作失败')
    } finally {
      setApproving(false)
    }
  }

  const handleReset = () => {
    setMessages([])
    setSessionId(null)
    setPendingApproval(null)
    setInput('')
  }

  return (
    <Card
      title="科研 Agent"
      extra={
        <Button icon={<ClearOutlined />} onClick={handleReset} disabled={loading}>
          新会话
        </Button>
      }
    >
      <div
        style={{
          height: 460,
          overflowY: 'auto',
          border: '1px solid #f0f0f0',
          borderRadius: 8,
          padding: 16,
          marginBottom: 16,
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
                    <Typography.Paragraph style={{ marginBottom: turn.toolCalls.length ? 8 : 0, whiteSpace: 'pre-wrap' }}>
                      {turn.text || (
                        <Typography.Text type="secondary">（等待危险操作确认…）</Typography.Text>
                      )}
                    </Typography.Paragraph>
                    {turn.toolCalls.length > 0 && (
                      <Collapse
                        ghost
                        size="small"
                        items={turn.toolCalls.map((call, j) => {
                          const meta = STATUS_META[call.status] ?? { color: 'default', label: call.status }
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
                                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{formatValue(call.args)}</pre>
                                <Typography.Text type="secondary">结果：</Typography.Text>
                                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{formatValue(call.result)}</pre>
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
            {loading && (
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
          style={{ marginBottom: 12 }}
          message={`Agent 请求执行危险操作：${pendingApproval.tool}`}
          description="请在下方确认弹窗中选择「允许」或「拒绝」。"
        />
      )}

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
          disabled={loading || !!pendingApproval}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={() => void handleSend()}
          loading={loading}
          disabled={!!pendingApproval}
        >
          发送
        </Button>
      </Space.Compact>

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
    </Card>
  )
}
