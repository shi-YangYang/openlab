import { useEffect, useState } from 'react'
import styles from './AgentPage.module.css'

export type AgentActivityPhase = 'thinking' | 'streaming' | 'executing'

export interface AgentActivity {
  phase: AgentActivityPhase
  tool: string | null
  startedAt: number
}

interface AgentRunningIndicatorProps {
  activity: AgentActivity | null
  pendingApproval: boolean
  stopPending: boolean
  fallbackVisible: boolean
  align?: 'start' | 'end'
}

export default function AgentRunningIndicator({
  activity,
  pendingApproval,
  stopPending,
  fallbackVisible,
  align = 'start',
}: AgentRunningIndicatorProps) {
  const [now, setNow] = useState(() => Date.now())
  const startedAt = activity?.startedAt ?? 0
  const timing = !!activity && (activity.phase === 'thinking' || activity.phase === 'executing')

  useEffect(() => {
    if (!timing) return
    setNow(Date.now())
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [timing, startedAt])

  const elapsed = Math.max(0, Math.floor((now - startedAt) / 1000))
  let text = 'Agent 正在执行…'
  if (pendingApproval) {
    text = '等待你的确认'
  } else if (stopPending) {
    text = '正在停止…'
  } else if (activity?.phase === 'thinking') {
    text = `思考中 · ${elapsed}s`
  } else if (activity?.phase === 'executing') {
    text = `执行中：${activity.tool || '工具'} · ${elapsed}s`
  } else if (activity?.phase === 'streaming') {
    text = '正在回复…'
  } else if (!fallbackVisible) {
    text = ''
  }

  return (
    <div className={`${styles.runIndicator} ${align === 'end' ? styles.runIndicatorEnd : ''}`}>
      <span className={`${styles.runDot} ${pendingApproval ? styles.runDotPending : ''}`} />
      <span>{text}</span>
    </div>
  )
}
