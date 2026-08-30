import { useEffect, useRef } from 'react'
import { Alert, App as AntApp, Button, Input, Space, Tag, Typography } from 'antd'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  MinusCircleOutlined,
  StopOutlined,
} from '@ant-design/icons'
import { STEPS, STEP_LABELS } from './constants'
import type { Step, StepState } from './constants'
import styles from './ExperimentRunPanel.module.css'

interface RunViewProps {
  runId: number | null
  runStatus: string
  runError: string
  stepStates: Record<string, StepState>
  failedStep: Step | null
  logs: string[]
  autoScroll: boolean
  onAutoScrollToggle: () => void
  filter: string
  onFilterChange: (filter: string) => void
  onStop: () => void
  onRetry: () => void
  onSkip: () => void
  disconnected: boolean
}

function stepIcon(state: StepState) {
  if (state === 'running') return <LoadingOutlined className={styles.iconRunning} />
  if (state === 'success') return <CheckCircleOutlined className={styles.iconSuccess} />
  if (state === 'failed') return <CloseCircleOutlined className={styles.iconFailed} />
  if (state === 'skipped') return <MinusCircleOutlined className={styles.iconSkipped} />
  if (state === 'retrying') return <LoadingOutlined className={styles.iconRetrying} />
  return <ClockCircleOutlined className={styles.iconPending} />
}

export default function RunView({
  runId,
  runStatus,
  runError,
  stepStates,
  failedStep,
  logs,
  autoScroll,
  onAutoScrollToggle,
  filter,
  onFilterChange,
  onStop,
  onRetry,
  onSkip,
  disconnected,
}: RunViewProps) {
  const { message } = AntApp.useApp()
  const logBoxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (autoScroll && logBoxRef.current) {
      logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const paused = runStatus === 'paused'

  const filteredLogs = filter.trim()
    ? logs.filter((l) => l.toLowerCase().includes(filter.trim().toLowerCase()))
    : logs

  const handleCopyLogs = async () => {
    try {
      await navigator.clipboard.writeText(filteredLogs.join('\n'))
      message.success('已复制')
    } catch {
      message.error('复制失败')
    }
  }

  const handleDownloadLogs = () => {
    const blob = new Blob([filteredLogs.join('\n')], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `experiment-run-${runId}.log`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className={styles.runLayout}>
      <div className={styles.stepsSidebar}>
        <div className="section-title">步骤</div>
        <Space direction="vertical" size={10} className={styles.fullWidth}>
          {STEPS.map((s) => {
            const state = stepStates[s]
            const isFailed = (state === 'failed' || (paused && failedStep === s)) ?? false
            return (
              <div key={s} className={styles.stepRow}>
                {stepIcon(isFailed ? 'failed' : (state ?? 'pending'))}
                <span>{STEP_LABELS[s]}</span>
                {state && state !== 'pending' && <Tag className={styles.stateTag}>{state}</Tag>}
              </div>
            )
          })}
        </Space>
        {runStatus !== 'stopped' && runStatus !== 'succeeded' && (
          <Button danger block icon={<StopOutlined />} className={styles.stopButton} onClick={onStop}>
            停止任务
          </Button>
        )}
        {(runStatus === 'stopped' || runStatus === 'succeeded') && (
          <Tag color={runStatus === 'succeeded' ? 'green' : 'orange'} className={styles.finishedTag}>
            {runStatus === 'succeeded' ? '已完成' : '已终止'}
          </Tag>
        )}
      </div>
      <div className={styles.logColumn}>
        {paused && (
          <Alert
            type="error"
            showIcon
            className={styles.sectionAlert}
            message={`失败暂停：${runError || '未知原因'}`}
            action={
              <Space direction="vertical" size={4} className={styles.alertActions}>
                <Button block onClick={onRetry}>
                  改命令重试
                </Button>
                <Button block onClick={onSkip} disabled={!failedStep}>
                  跳过此步
                </Button>
              </Space>
            }
          />
        )}
        <Space className={styles.logToolbar} wrap>
          <Input
            allowClear
            size="small"
            placeholder="过滤日志关键词"
            value={filter}
            onChange={(e) => onFilterChange(e.target.value)}
            className={styles.filterInput}
          />
          {filter.trim() && (
            <Typography.Text type="secondary">命中 {filteredLogs.length} 行</Typography.Text>
          )}
          <Button size="small" onClick={onAutoScrollToggle}>
            {autoScroll ? '暂停滚动' : '恢复滚动'}
          </Button>
          <Button
            size="small"
            disabled={filteredLogs.length === 0}
            onClick={() => void handleCopyLogs()}
          >
            复制日志
          </Button>
          <Button size="small" disabled={filteredLogs.length === 0} onClick={handleDownloadLogs}>
            下载日志
          </Button>
        </Space>
        {disconnected && (
          <Alert type="warning" showIcon className={styles.sectionAlert} message="日志连接中断，正在重连…" />
        )}
        <div ref={logBoxRef} className={`log-area ${styles.logBox}`}>
          {filteredLogs.length === 0 ? (
            <span className={styles.logEmpty}>等待输出…</span>
          ) : (
            filteredLogs.map((line, i) => <div key={i}>{line}</div>)
          )}
        </div>
      </div>
    </div>
  )
}
