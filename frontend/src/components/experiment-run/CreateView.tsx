import { Alert, Button, Input, Radio, Select, Space, Typography } from 'antd'
import { PlayCircleOutlined } from '@ant-design/icons'
import type { Server } from '../../types'
import { STEPS, STEP_LABELS } from './constants'
import type { Step } from './constants'
import styles from './ExperimentRunPanel.module.css'

interface CreateViewProps {
  servers: Server[]
  serverId: string | null
  onServerChange: (serverId: string | null) => void
  workdir: string
  onWorkdirChange: (workdir: string) => void
  syncMode: 'clone' | 'skip'
  onSyncModeChange: (syncMode: 'clone' | 'skip') => void
  repoUrl: string
  onRepoUrlChange: (repoUrl: string) => void
  stepCommands: Record<Step, string>
  onStepCommandChange: (step: Step, command: string) => void
  onStart: () => void
  testing: boolean
  onTestServer: () => void
  creating: boolean
}

export default function CreateView({
  servers,
  serverId,
  onServerChange,
  workdir,
  onWorkdirChange,
  syncMode,
  onSyncModeChange,
  repoUrl,
  onRepoUrlChange,
  stepCommands,
  onStepCommandChange,
  onStart,
  testing,
  onTestServer,
  creating,
}: CreateViewProps) {
  return (
    <Space direction="vertical" size={12} className={styles.fullWidth}>
      <Space wrap size={16}>
        <Space size={8}>
          <Typography.Text type="secondary">目标服务器</Typography.Text>
          <Select
            className={styles.serverSelect}
            placeholder="选择服务器"
            value={serverId}
            onChange={onServerChange}
            options={servers.map((s) => ({ value: s.id, label: s.name }))}
            notFoundContent="暂无服务器，请先到「服务器」页添加"
          />
          <Button loading={testing} disabled={!serverId} onClick={() => void onTestServer()}>
            测试连接
          </Button>
        </Space>
        <Space size={8}>
          <Typography.Text type="secondary">工作目录</Typography.Text>
          <Input
            className={styles.workdirInput}
            value={workdir}
            onChange={(e) => onWorkdirChange(e.target.value)}
            placeholder="~/openlab-experiments/{id}"
          />
        </Space>
      </Space>

      <div>
        <Typography.Text type="secondary">同步代码：</Typography.Text>
        <Radio.Group
          value={syncMode}
          onChange={(e) => onSyncModeChange(e.target.value)}
          className={styles.syncModeGroup}
        >
          <Radio value="clone">git clone</Radio>
          <Radio value="skip">跳过（代码已就位）</Radio>
        </Radio.Group>
        {syncMode === 'clone' && (
          <Input
            className={styles.repoUrlInput}
            placeholder="https://github.com/org/repo.git"
            value={repoUrl}
            onChange={(e) => onRepoUrlChange(e.target.value)}
          />
        )}
      </div>

      <div className="section-title">执行步骤命令（可编辑）</div>
      {STEPS.map((s) => (
        <div key={s} className={styles.stepField}>
          <Typography.Text type="secondary">{STEP_LABELS[s]}</Typography.Text>
          <Input.TextArea
            rows={2}
            value={stepCommands[s]}
            onChange={(e) => onStepCommandChange(s, e.target.value)}
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
        onClick={() => void onStart()}
      >
        开始执行
      </Button>
    </Space>
  )
}
