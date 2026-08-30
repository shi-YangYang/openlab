import { Button, Collapse, Empty, Space, Spin, Tag, Tooltip, Typography } from 'antd'
import { CopyOutlined, FileImageOutlined, FileOutlined, RobotOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import { isValidElement, type ReactNode, type RefObject } from 'react'
import { apiUrl } from '../../api'
import type { AgentToolCall } from '../../types'
import styles from './AgentPage.module.css'

const STATUS_META: Record<string, { color: string; label: string }> = {
  done: { color: 'green', label: '完成' },
  error: { color: 'red', label: '失败' },
  rejected: { color: 'orange', label: '已拒绝' },
}

export interface Turn {
  role: 'user' | 'assistant'
  text: string
  toolCalls: AgentToolCall[]
  time?: string | null
  model?: string | null
  files?: string[]
}

interface AgentChatMessagesProps {
  messages: Turn[]
  loading: boolean
  running: boolean
  statusLabel: string
  bottomRef: RefObject<HTMLDivElement>
  sessionId: string | null
  onCopyText: (text: string) => void
}

export function formatValue(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
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

export default function AgentChatMessages({
  messages,
  loading,
  running,
  statusLabel,
  bottomRef,
  sessionId,
  onCopyText,
}: AgentChatMessagesProps) {
  const markdownComponents: Components = {
    pre: ({ children }) => {
      const text = nodeText(children)
      return (
        <div className={styles.mdCode}>
          <pre>{children}</pre>
          <Tooltip title="复制代码">
            <Button
              className={styles.codeCopy}
              size="small"
              type="text"
              icon={<CopyOutlined />}
              onClick={() => void onCopyText(text)}
            />
          </Tooltip>
        </div>
      )
    },
  }

  const renderToolbar = (turn: Turn, align: 'start' | 'end') => (
    <div
      className={`${styles.turnToolbar} ${
        align === 'end' ? styles.turnToolbarEnd : styles.turnToolbarStart
      }`}
    >
      {turn.model ? (
        <Tooltip title={turn.model}>
          <span className={styles.toolbarModel}>{turn.model}</span>
        </Tooltip>
      ) : (
        <span className={styles.toolbarModel}>-</span>
      )}
      <span className={styles.toolbarTime}>{turn.time || '-'}</span>
      <Tooltip title="复制">
        <Button
          className={styles.toolbarCopy}
          size="small"
          type="text"
          icon={<CopyOutlined />}
          onClick={() => void onCopyText(turn.text)}
        />
      </Tooltip>
    </div>
  )

  return (
    <div className={styles.messagesScroll}>
      {messages.length === 0 && !loading && !running ? (
        <Empty
          className={styles.messagesEmpty}
          image={<RobotOutlined className={styles.emptyIcon} />}
          description="输入一个科研目标，Agent 将自主调用工具完成任务"
        />
      ) : (
        <Space direction="vertical" size={32} className={styles.messagesList}>
          {messages.map((turn, i) =>
            turn.role === 'user' ? (
              <div key={i} className={`${styles.turnWrap} ${styles.turnRowEnd}`}>
                <div className={styles.userBubble}>
                  {turn.text}
                  {turn.files && turn.files.length > 0 && (
                    <div className={styles.fileList}>
                      {turn.files.map((f) => {
                        const isImg = /\.(png|jpe?g|gif|webp|bmp)$/i.test(f)
                        return (
                          <a
                            key={f}
                            href={apiUrl(`/api/agent/sessions/${sessionId}/attachments/${encodeURIComponent(f)}`)}
                            target="_blank"
                            rel="noreferrer"
                            className="file-chip"
                          >
                            {isImg ? <FileImageOutlined /> : <FileOutlined />}
                            <span>{f.split('/').pop()}</span>
                          </a>
                        )
                      })}
                    </div>
                  )}
                </div>
                {renderToolbar(turn, 'end')}
              </div>
            ) : (
              <div key={i} className={`${styles.turnWrap} ${styles.turnRowStart}`}>
                <div className={styles.assistantBubble}>
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
                            <div className={styles.toolDetail}>
                              <Typography.Text type="secondary">参数：</Typography.Text>
                              <pre className={styles.toolPre}>{formatValue(call.args)}</pre>
                              <Typography.Text type="secondary">结果：</Typography.Text>
                              <pre className={styles.toolPre}>{formatValue(call.result)}</pre>
                            </div>
                          ),
                        }
                      })}
                    />
                  )}
                </div>
                {renderToolbar(turn, 'start')}
              </div>
            ),
          )}
          {(loading || running) && (
            <div className={styles.statusRow}>
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
  )
}
