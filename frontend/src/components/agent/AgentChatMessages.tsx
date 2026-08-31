import { Button, Collapse, Empty, Space, Tag, Tooltip, Typography } from 'antd'
import { CopyOutlined, FileImageOutlined, FileOutlined, RobotOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import { isValidElement, useState, type ReactNode, type RefObject } from 'react'
import { apiUrl } from '../../api'
import type { AgentPendingApproval, Turn } from '../../types'
import type { AgentActivity } from './AgentRunningIndicator'
import AgentRunningIndicator from './AgentRunningIndicator'
import styles from './AgentPage.module.css'

const STATUS_META: Record<string, { color: string; label: string }> = {
  done: { color: 'green', label: '完成' },
  error: { color: 'red', label: '失败' },
  rejected: { color: 'orange', label: '已拒绝' },
}

interface AgentChatMessagesProps {
  messages: Turn[]
  loading: boolean
  running: boolean
  activity: AgentActivity | null
  pendingApproval: AgentPendingApproval | null
  stopPending: boolean
  bottomRef: RefObject<HTMLDivElement>
  sessionId: string | null
  onCopyText: (text: string) => void
}

type Block =
  | { kind: 'turn'; index: number; key: string }
  | { kind: 'group'; start: number; end: number; key: string }

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

// djb2: stable 32-bit hash over content, so group keys survive message
// insertion (index-based keys would shift groups and leak manual open state).
function hash32(input: string): string {
  let hash = 5381
  for (let i = 0; i < input.length; i++) {
    hash = ((hash << 5) + hash + input.charCodeAt(i)) | 0
  }
  return (hash >>> 0).toString(36)
}

function groupKeyOf(turn: Turn): string {
  const call = turn.toolCalls[0]
  const callPart = call
    ? `${call.tool}|${call.status}|${formatValue(call.args).slice(0, 64)}`
    : ''
  return hash32(`${turn.time ?? ''}|${(turn.text || '').slice(0, 32)}|${callPart}`)
}

function splitBlocks(messages: Turn[]): Block[] {
  const blocks: Block[] = []
  let i = 0
  while (i < messages.length) {
    const turn = messages[i]
    if (turn.role === 'assistant' && turn.intermediate) {
      let j = i + 1
      while (j < messages.length && messages[j].role === 'assistant' && messages[j].intermediate) j++
      blocks.push({ kind: 'group', start: i, end: j, key: `g${groupKeyOf(messages[i])}` })
      i = j
    } else {
      blocks.push({ kind: 'turn', index: i, key: `t${i}` })
      i++
    }
  }
  return blocks
}

export default function AgentChatMessages({
  messages,
  loading,
  running,
  activity,
  pendingApproval,
  stopPending,
  bottomRef,
  sessionId,
  onCopyText,
}: AgentChatMessagesProps) {
  const [manualTouched, setManualTouched] = useState<Record<string, boolean>>({})
  const [manualOpen, setManualOpen] = useState<Record<string, boolean>>({})

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

  const renderToolCalls = (turn: Turn, keyPrefix: string) => {
    if (turn.toolCalls.length === 0) return null
    return (
      <Collapse
        ghost
        size="small"
        defaultActiveKey={turn.toolCalls
          .map((c, j) =>
            ['error', 'rejected'].includes(c.status) ? `${keyPrefix}-${j}` : null,
          )
          .filter(Boolean) as string[]}
        items={turn.toolCalls.map((call, j) => {
          const meta = STATUS_META[call.status] ?? {
            color: 'default',
            label: call.status,
          }
          return {
            key: `${keyPrefix}-${j}`,
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
    )
  }

  const renderMarkdown = (text: string) => (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {text}
      </ReactMarkdown>
    </div>
  )

  const blocks = splitBlocks(messages)
  const lastGroupKey = [...blocks].reverse().find((b) => b.kind === 'group')?.key ?? null

  const isGroupOpen = (key: string) => {
    if (manualTouched[key]) return !!manualOpen[key]
    return running && key === lastGroupKey
  }

  const handleGroupToggle = (key: string, open: boolean) => {
    setManualTouched((prev) => ({ ...prev, [key]: true }))
    setManualOpen((prev) => ({ ...prev, [key]: open }))
  }

  const showIndicator =
    !!pendingApproval || stopPending || !!activity || loading || running

  const renderIndicator = (align: 'start' | 'end' = 'start') => {
    if (!showIndicator) return null
    return (
      <AgentRunningIndicator
        activity={activity}
        pendingApproval={!!pendingApproval}
        stopPending={stopPending}
        fallbackVisible={loading || running}
        align={align}
      />
    )
  }

  const renderGroup = (block: Block & { kind: 'group' }) => {
    const turns = messages.slice(block.start, block.end)
    const key = block.key
    return (
      <div key={key} className={styles.processGroup}>
        <Collapse
          ghost
          size="small"
          activeKey={isGroupOpen(key) ? [key] : []}
          onChange={(keys) => {
            const open = Array.isArray(keys) ? keys.includes(key) : keys === key
            handleGroupToggle(key, open)
          }}
          items={[
            {
              key,
              label: <span className={styles.processLabel}>思考与过程 · {turns.length} 步</span>,
              children: (
                <div className={styles.processBody}>
                  {turns.map((turn, k) => (
                    <div key={k} className={styles.processTurn}>
                      {turn.text ? renderMarkdown(turn.text) : null}
                      {renderToolCalls(turn, `${key}-${k}`)}
                    </div>
                  ))}
                  {block.end === messages.length ? renderIndicator() : null}
                </div>
              ),
            },
          ]}
        />
      </div>
    )
  }

  const renderTurn = (block: Block & { kind: 'turn' }) => {
    const turn = messages[block.index]
    const isLast = block.index === messages.length - 1
    if (turn.role === 'user') {
      return (
        <div key={block.key} className={`${styles.turnWrap} ${styles.turnRowEnd}`}>
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
          {isLast ? renderIndicator('end') : null}
        </div>
      )
    }
    return (
      <div key={block.key} className={`${styles.turnWrap} ${styles.turnRowStart}`}>
        <div className={styles.assistantBubble}>
          {turn.text ? renderMarkdown(turn.text) : null}
          {renderToolCalls(turn, block.key)}
        </div>
        {renderToolbar(turn, 'start')}
        {isLast ? renderIndicator('start') : null}
      </div>
    )
  }

  return (
    <div className={styles.messagesScroll}>
      {messages.length === 0 ? (
        showIndicator ? (
          <div className={styles.emptyIndicator}>{renderIndicator()}</div>
        ) : (
          <Empty
            className={styles.messagesEmpty}
            image={<RobotOutlined className={styles.emptyIcon} />}
            description="输入一个科研目标，Agent 将自主调用工具完成任务"
          />
        )
      ) : (
        <Space direction="vertical" size={32} className={styles.messagesList}>
          {blocks.map((block) => (block.kind === 'group' ? renderGroup(block) : renderTurn(block)))}
          <div ref={bottomRef} />
        </Space>
      )}
    </div>
  )
}
