import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Input,
  Modal,
  Radio,
  Select,
  Space,
  Tag,
  Typography,
} from 'antd'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  MinusCircleOutlined,
  PlayCircleOutlined,
  StopOutlined,
} from '@ant-design/icons'
import {
  createExperimentRun,
  listServers,
  startExperimentRun,
  testServer,
  terminalWsUrl,
} from '../api'
import type { ExperimentRecord, Server } from '../types'

const STEPS = ['sync_code', 'setup_env', 'launch_training'] as const
type Step = (typeof STEPS)[number]

const STEP_LABELS: Record<Step, string> = {
  sync_code: '同步代码',
  setup_env: '环境准备',
  launch_training: '启动训练',
}

type StepState = 'pending' | 'running' | 'success' | 'failed' | 'retrying' | 'skipped'

function stepIcon(state: StepState) {
  if (state === 'running') return <LoadingOutlined style={{ color: '#1677ff' }} />
  if (state === 'success') return <CheckCircleOutlined style={{ color: '#52c41a' }} />
  if (state === 'failed') return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
  if (state === 'skipped') return <MinusCircleOutlined style={{ color: '#999' }} />
  if (state === 'retrying') return <LoadingOutlined style={{ color: '#faad14' }} />
  return <ClockCircleOutlined style={{ color: '#bbb' }} />
}

interface Props {
  open: boolean
  onClose: () => void
  experiment: ExperimentRecord
}

export default function ExperimentRunPanel({ open, onClose, experiment }: Props) {
  const { message } = AntApp.useApp()
  const [servers, setServers] = useState<Server[]>([])
  const [serverId, setServerId] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [workdir, setWorkdir] = useState('')
  const [syncMode, setSyncMode] = useState<'clone' | 'skip'>('skip')
  const [repoUrl, setRepoUrl] = useState('')
  const [stepCommands, setStepCommands] = useState<Record<Step, string>>({
    sync_code: '',
    setup_env: '',
    launch_training: '',
  })
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
  const logBoxRef = useRef<HTMLDivElement>(null)
  const socketRef = useRef<WebSocket | null>(null)

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
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [open])

  useEffect(() => {
    if (autoScroll && logBoxRef.current) {
      logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight
    }
  }, [logs, autoScroll])

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

  const connectWs = useCallback((id: number) => {
    const ws = new WebSocket(terminalWsUrl(`/api/experiment-runs/ws?run_id=${id}`))
    socketRef.current = ws
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
    }
  }, [])

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

  const showRetryModal = () => {
    if (!failedStep) return
    setRetryCommand(stepCommands[failedStep] ?? '')
    setRetryOpen(true)
  }

  const handleRetrySubmit = () => {
    if (!failedStep || !sendWs({ action: 'retry', step: failedStep, command: retryCommand })) {
      return
    }
    setStepCommands((prev) => ({ ...prev, [failedStep]: retryCommand }))
    setRunStatus('running')
    setFailedStep(null)
    setRetryOpen(false)
    message.success('已重新执行该步骤')
  }

  const paused = runStatus === 'paused'

  const filteredLogs = filter.trim()
    ? logs.filter((l) => l.toLowerCase().includes(filter.trim().toLowerCase()))
    : logs

  return (
    <div>
      {!runId ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Space wrap size={16}>
            <Space size={8}>
              <Typography.Text type="secondary">目标服务器</Typography.Text>
              <Select
                style={{ minWidth: 220 }}
                placeholder="选择服务器"
                value={serverId}
                onChange={setServerId}
                options={servers.map((s) => ({ value: s.id, label: s.name }))}
                notFoundContent="暂无服务器，请先到「服务器」页添加"
              />
              <Button loading={testing} disabled={!serverId} onClick={() => void handleTestServer()}>
                测试连接
              </Button>
            </Space>
            <Space size={8}>
              <Typography.Text type="secondary">工作目录</Typography.Text>
              <Input
                style={{ width: 260 }}
                value={workdir}
                onChange={(e) => setWorkdir(e.target.value)}
                placeholder="~/openlab-experiments/{id}"
              />
            </Space>
          </Space>

          <div>
            <Typography.Text type="secondary">同步代码：</Typography.Text>
            <Radio.Group
              value={syncMode}
              onChange={(e) => setSyncMode(e.target.value)}
              style={{ marginLeft: 8 }}
            >
              <Radio value="clone">git clone</Radio>
              <Radio value="skip">跳过（代码已就位）</Radio>
            </Radio.Group>
            {syncMode === 'clone' && (
              <Input
                style={{ width: 320, marginLeft: 8 }}
                placeholder="https://github.com/org/repo.git"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
              />
            )}
          </div>

          <Typography.Title level={5} style={{ marginBottom: 4 }}>
            执行步骤命令（可编辑）
          </Typography.Title>
          {STEPS.map((s) => (
            <div key={s} style={{ marginBottom: 8 }}>
              <Typography.Text type="secondary">{STEP_LABELS[s]}</Typography.Text>
              <Input.TextArea
                rows={2}
                value={stepCommands[s]}
                onChange={(e) =>
                  setStepCommands((prev) => ({ ...prev, [s]: e.target.value }))
                }
                placeholder={
                  s === 'sync_code'
                    ? '留空表示使用上方 git clone；否则填自定义同步命令'
                    : ''
                }
              />
            </div>
          ))}

          <Alert
            type="info"
            showIcon
            message="提示：也可以在 Agent 页用一句话发起（如“在 xx 服务器上运行实验方案 yy”），由 Agent 全程主导。"
          />

          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={creating}
            disabled={!serverId}
            onClick={() => void handleStart()}
          >
            开始执行
          </Button>
        </Space>
      ) : (
        <div style={{ display: 'flex', gap: 16 }}>
          <div style={{ width: 200, flexShrink: 0 }}>
            <Typography.Title level={5}>步骤</Typography.Title>
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              {STEPS.map((s) => {
                const state = stepStates[s]
                const isFailed = (state === 'failed' || (paused && failedStep === s)) ?? false
                return (
                  <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {stepIcon(isFailed ? 'failed' : (state ?? 'pending'))}
                    <span>{STEP_LABELS[s]}</span>
                    {state && state !== 'pending' && <Tag style={{ fontSize: 11 }}>{state}</Tag>}
                  </div>
                )
              })}
            </Space>
            {runStatus !== 'stopped' && runStatus !== 'succeeded' && (
              <Button danger block icon={<StopOutlined />} style={{ marginTop: 16 }} onClick={handleStop}>
                停止任务
              </Button>
            )}
            {(runStatus === 'stopped' || runStatus === 'succeeded') && (
              <Tag color={runStatus === 'succeeded' ? 'green' : 'orange'} style={{ marginTop: 16 }}>
                {runStatus === 'succeeded' ? '已完成' : '已终止'}
              </Tag>
            )}
          </div>
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
            {paused && (
              <Alert
                type="error"
                showIcon
                style={{ marginBottom: 8 }}
                message={`失败暂停：${runError || '未知原因'}`}
                action={
                  <Space direction="vertical" size={4} style={{ marginTop: 8, width: '100%' }}>
                    <Button block onClick={showRetryModal}>
                      改命令重试
                    </Button>
                    <Button block onClick={handleSkipFailed} disabled={!failedStep}>
                      跳过此步
                    </Button>
                  </Space>
                }
              />
            )}
            <Space style={{ marginBottom: 8 }} wrap>
              <Input
                allowClear
                size="small"
                placeholder="过滤日志关键词"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                style={{ width: 180 }}
              />
              {filter.trim() && (
                <Typography.Text type="secondary">命中 {filteredLogs.length} 行</Typography.Text>
              )}
              <Button size="small" onClick={() => setAutoScroll((v) => !v)}>
                {autoScroll ? '暂停滚动' : '恢复滚动'}
              </Button>
            </Space>
            <div
              ref={logBoxRef}
              style={{
                height: 380,
                overflowY: 'auto',
                background: '#1e1e1e',
                color: '#d4d4d4',
                padding: 10,
                borderRadius: 6,
                fontFamily: 'Consolas, Monaco, monospace',
                fontSize: 12,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {filteredLogs.length === 0 ? (
                <span style={{ color: '#666' }}>等待输出…</span>
              ) : (
                filteredLogs.map((line, i) => <div key={i}>{line}</div>)
              )}
            </div>
          </div>
        </div>
      )}
      <Modal
        title={failedStep ? `修改命令后重试：${STEP_LABELS[failedStep]}` : '修改命令'}
        open={retryOpen}
        onOk={handleRetrySubmit}
        onCancel={() => setRetryOpen(false)}
        width={640}
      >
        <Input.TextArea
          rows={4}
          value={retryCommand}
          onChange={(e) => setRetryCommand(e.target.value)}
        />
      </Modal>
    </div>
  )
}
