import { useCallback, useEffect, useRef, useState } from 'react'
import { App as AntApp, Input, Modal } from 'antd'
import { createExperimentRun, getExperimentRun, listExperimentRuns, listServers, startExperimentRun, testServer, terminalWsUrl } from '../../api'
import type { ExperimentRecord, ExperimentRun, Server } from '../../types'
import { STEP_LABELS } from './constants'
import type { Step, StepState } from './constants'
import CreateView from './CreateView'
import RunView from './RunView'

interface ExperimentRunPanelProps {
  open: boolean
  onClose: () => void
  experiment: ExperimentRecord
}

export default function ExperimentRunPanel({ open, onClose, experiment }: ExperimentRunPanelProps) {
  const { message } = AntApp.useApp()
  const [servers, setServers] = useState<Server[]>([])
  const [serverId, setServerId] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [workdir, setWorkdir] = useState('')
  const [syncMode, setSyncMode] = useState<'clone' | 'skip'>('skip')
  const [repoUrl, setRepoUrl] = useState('')
  const [stepCommands, setStepCommands] = useState<Record<Step, string>>({ sync_code: '', setup_env: '', launch_training: '' })
  const [creating, setCreating] = useState(false)
  const [runId, setRunId] = useState<number | null>(null)
  const [runStatus, setRunStatus] = useState('pending')
  const [runError, setRunError] = useState('')
  const [stepStates, setStepStates] = useState<Record<string, StepState>>({})
  const [logs, setLogs] = useState<string[]>([])
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState('')
  const [failedStep, setFailedStep] = useState<Step | null>(null)
  const [retryCommand, setRetryCommand] = useState('')
  const [retryOpen, setRetryOpen] = useState(false)
  const [disconnected, setDisconnected] = useState(false)
  const socketRef = useRef<WebSocket | null>(null)
  const adoptedExpRef = useRef<number | null>(null)
  const runIdRef = useRef<number | null>(null)
  const runStatusRef = useRef('pending')
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimerRef = useRef<number | null>(null)
  const wsClosedByUsRef = useRef(false)

  useEffect(() => { runIdRef.current = runId }, [runId])

  useEffect(() => { runStatusRef.current = runStatus }, [runStatus])

  useEffect(() => {
    if (!open) return
    listServers()
      .then((list) => {
        setServers(list)
        if (list.length > 0) setServerId((prev) => prev ?? list[0].id)
      })
      .catch(() => message.error('加载服务器列表失败'))
    setWorkdir(`~/openlab-experiments/${experiment.id ?? 0}`)
  }, [open, experiment.id])

  useEffect(() => {
    return () => {
      wsClosedByUsRef.current = true
      if (reconnectTimerRef.current != null) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [open])

  const handleTestServer = async () => {
    if (!serverId) return
    setTesting(true)
    try {
      const res = await testServer(serverId)
      if (res.ok) message.success(`连接成功（${res.latency_ms ?? '-'} ms）`)
      else message.error(res.message || '连接失败')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '连接失败')
    } finally {
      setTesting(false)
    }
  }

  const applyRunDetail = useCallback((detail: ExperimentRun) => {
    setRunStatus(detail.status)
    if (detail.status === 'paused') {
      setRunError(detail.error || '')
      if (detail.current_step) setFailedStep(detail.current_step as Step)
    }
    if (detail.current_step) {
      setStepStates((prev) => ({
        ...prev,
        [detail.current_step]: detail.status === 'paused' ? 'failed' : 'running',
      }))
    }
    if (detail.log_tail) setLogs(detail.log_tail.split('\n'))
  }, [])

  const connectWs = useCallback((id: number) => {
    reconnectAttemptsRef.current = 0
    setDisconnected(false)
    wsClosedByUsRef.current = false

    const connect = () => {
      const ws = new WebSocket(terminalWsUrl(`/api/experiment-runs/ws?run_id=${id}`))
      socketRef.current = ws
      ws.onopen = () => {
        reconnectAttemptsRef.current = 0
        setDisconnected(false)
        const rid = runIdRef.current
        if (rid != null) {
          void getExperimentRun(rid).then((detail) => applyRunDetail(detail)).catch(() => {})
        }
      }
      ws.onmessage = (event) => {
        let data: Record<string, unknown>
        try {
          data = JSON.parse(event.data as string)
        } catch {
          return
        }
        if (data.type === 'log') {
          setLogs((prev) => {
            const next = [...prev, String(data.line ?? '')]
            return next.length > 5000 ? next.slice(next.length - 5000) : next
          })
        } else if (data.type === 'step') {
          const step = String(data.step)
          const st = String(data.status) as StepState
          setStepStates((prev) => ({ ...prev, [step]: st }))
          if (st === 'failed') setFailedStep(step as Step)
        } else if (data.type === 'status') {
          const st = String(data.status)
          setRunStatus(st)
          if (data.error) setRunError(String(data.error))
        }
      }
      ws.onclose = () => {
        if (socketRef.current === ws) socketRef.current = null
        if (wsClosedByUsRef.current) return
        if (!['preparing', 'running', 'paused'].includes(runStatusRef.current)) return
        if (reconnectAttemptsRef.current >= 5) return
        const delay = 1000 * 2 ** reconnectAttemptsRef.current
        reconnectAttemptsRef.current += 1
        setDisconnected(true)
        reconnectTimerRef.current = window.setTimeout(() => {
          reconnectTimerRef.current = null
          if (!wsClosedByUsRef.current) connect()
        }, delay)
      }
    }

    connect()
  }, [applyRunDetail])

  useEffect(() => {
    if (!open || runId != null || experiment?.id == null) return
    if (adoptedExpRef.current === experiment.id) return
    adoptedExpRef.current = experiment.id
    void (async () => {
      try {
        const runs = await listExperimentRuns()
        const active = runs.filter(
          (r) => r.experiment_id === experiment.id && ['preparing', 'running', 'paused'].includes(r.status),
        )
        if (active.length === 0) return
        const latest = active.reduce((a, b) => ((a.updated_at ?? '') >= (b.updated_at ?? '') ? a : b))
        setRunId(latest.id)
        setRunStatus(latest.status)
        connectWs(latest.id)
        const detail = await getExperimentRun(latest.id)
        applyRunDetail(detail)
      } catch {
        // ignore adoption failures; the creation view stays usable
      }
    })()
  }, [open, runId, experiment.id, connectWs, applyRunDetail])

  const handleStart = async () => {
    if (!serverId) {
      message.error('请选择服务器')
      return
    }
    setCreating(true)
    try {
      const run = await createExperimentRun({
        experiment_id: experiment.id ?? 0,
        server_id: serverId,
        mode: 'manual',
        remote_workdir: workdir.trim(),
        repo_url: syncMode === 'clone' ? repoUrl.trim() : '',
      })
      setRunId(run.id)
      setRunStatus('pending')
      connectWs(run.id)
      await startExperimentRun(run.id, { ...stepCommands })
      message.success('实验运行已开始')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '启动失败')
    } finally {
      setCreating(false)
    }
  }

  const handleStepCommandChange = (step: Step, command: string) => setStepCommands((prev) => ({ ...prev, [step]: command }))

  const sendWs = (payload: Record<string, unknown>) => {
    const ws = socketRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload))
      return true
    }
    message.error('通道未连接，无法发送指令')
    return false
  }

  const handleStop = () => {
    if (!sendWs({ type: 'stop' })) return
    setRunStatus('stopped')
    message.info('已请求终止任务')
  }

  const handleSkipFailed = () => {
    if (!failedStep) return
    if (!sendWs({ action: 'skip', step: failedStep })) return
    setRunStatus('running')
    setFailedStep(null)
  }

  const handleShowRetryModal = () => {
    if (!failedStep) return
    setRetryCommand(stepCommands[failedStep] ?? '')
    setRetryOpen(true)
  }

  const handleRetrySubmit = () => {
    if (!failedStep || !sendWs({ action: 'retry', step: failedStep, command: retryCommand })) return
    setStepCommands((prev) => ({ ...prev, [failedStep]: retryCommand }))
    setRunStatus('running')
    setFailedStep(null)
    setRetryOpen(false)
    message.success('已重新执行该步骤')
  }

  const handleToggleAutoScroll = () => setAutoScroll((v) => !v)

  return (
    <div>
      {!runId ? (
        <CreateView
          servers={servers}
          serverId={serverId}
          onServerChange={setServerId}
          workdir={workdir}
          onWorkdirChange={setWorkdir}
          syncMode={syncMode}
          onSyncModeChange={setSyncMode}
          repoUrl={repoUrl}
          onRepoUrlChange={setRepoUrl}
          stepCommands={stepCommands}
          onStepCommandChange={handleStepCommandChange}
          onStart={handleStart}
          testing={testing}
          onTestServer={handleTestServer}
          creating={creating}
        />
      ) : (
        <RunView
          runId={runId}
          runStatus={runStatus}
          runError={runError}
          stepStates={stepStates}
          failedStep={failedStep}
          logs={logs}
          autoScroll={autoScroll}
          onAutoScrollToggle={handleToggleAutoScroll}
          filter={filter}
          onFilterChange={setFilter}
          onStop={handleStop}
          onRetry={handleShowRetryModal}
          onSkip={handleSkipFailed}
          disconnected={disconnected}
        />
      )}
      <Modal
        title={failedStep ? `修改命令后重试：${STEP_LABELS[failedStep]}` : '修改命令'}
        open={retryOpen}
        onOk={handleRetrySubmit}
        onCancel={() => setRetryOpen(false)}
        width={640}
      >
        <Input.TextArea rows={4} value={retryCommand} onChange={(e) => setRetryCommand(e.target.value)} />
      </Modal>
    </div>
  )
}
